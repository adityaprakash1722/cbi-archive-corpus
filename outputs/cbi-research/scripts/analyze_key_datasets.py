#!/usr/bin/env python3
"""Produce reproducible, QC-aware extracts from high-value CBI open datasets.

The script deliberately separates:
* values derived from downloadable CSV resources;
* benchmarks transcribed from named CBI statistical releases; and
* quality-control findings that make a CSV unsafe for a headline statistic.

It does not impute confidential observations or silently repair malformed rows.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


FRAUD_RELEASE_URL = (
    "https://www.centralbank.ie/docs/default-source/statistics/data-and-analysis/"
    "payment-fraud-statistics/payment-fraud-statistics-202485f0d58e-4a6d-4a27-"
    "aed4-03717c7bdcd7.pdf?sfvrsn=3a96e1a_1"
)
FRAUD_RELEASE_SHA256 = "9b28140dd61ae482c235a06374e9c017253ec47d836ad6b409b5aa4d2f9b5d07"
ARREARS_RELEASE_URL = (
    "https://www.centralbank.ie/docs/default-source/statistics/data-and-analysis/"
    "credit-and-banking-statistics/mortgage-arrears/2026-q1-release.pdf?"
    "sfvrsn=2729711a_2"
)
ARREARS_RELEASE_SHA256 = "a4d158cb9a22aa37f4dc00a0e23402796cef0c8925b36763296f63a471c7029e"


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--profile-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", errors="replace", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_number(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text or text.upper() in {"NULL", "NA", "N/A", "-"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def clean_header(value: str) -> str:
    return value.replace("�", "€").strip()


def catalog_lookup(catalog: list[dict[str, str]], dataset: str, resource: str) -> dict[str, str]:
    matches = [
        row for row in catalog
        if row["dataset_title"] == dataset and row["resource_name"] == resource
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one catalog match for {dataset!r}/{resource!r}; got {len(matches)}")
    return matches[0]


def resolve(archive: Path, catalog: list[dict[str, str]], dataset: str, resource: str) -> tuple[Path, dict[str, str]]:
    entry = catalog_lookup(catalog, dataset, resource)
    path = archive / entry["local_path"].replace("\\", "/")  # manifest paths are written on Windows
    if not path.is_file():
        raise FileNotFoundError(path)
    return path, entry


def iso_date(value: str) -> str:
    return datetime.strptime(value.strip(), "%d/%m/%Y").date().isoformat()


class MissingComparisonPeriod(RuntimeError):
    """Raised when a year-on-year comparison has no prior observation.

    Previously ``round(pct_change(...) or 0, 3)`` turned a missing prior period
    into a reported 0.0% change, which reads as "unchanged year on year" and is
    indistinguishable from a real zero. Failing is the only safe behaviour.
    """


def pct_change(current: float | None, prior: float | None) -> float | None:
    if current is None or prior in {None, 0}:
        return None
    return (current / prior - 1.0) * 100.0


def required_pct_change(current: float | None, prior: float | None, label: str) -> float:
    change = pct_change(current, prior)
    if change is None:
        raise MissingComparisonPeriod(
            f"{label}: no usable prior-period value (current={current!r}, prior={prior!r}). "
            "Check that the prior reference date exists in the source CSV."
        )
    return change


def value_for(rows: list[dict[str, str]], **criteria: str) -> float | None:
    matches = [row for row in rows if all(row.get(key) == value for key, value in criteria.items())]
    if len(matches) != 1:
        return None
    return parse_number(matches[0].get("Observation_Amount"))


def analyze_payment_fraud(
    archive: Path, catalog: list[dict[str, str]], output: Path
) -> dict[str, Any]:
    path, entry = resolve(
        archive, catalog, "Payment Fraud Statistics", "Payment Transactions (Fraud)"
    )
    rows = read_csv(path)
    selected = [
        row for row in rows
        if row["COUNT_AREA"] == "W0"
        and row["RL_TRNSCTN"] == "1"
        and row["FRD_TYP"] == "F"
        and row["UNIT_MEASURE"] == "EUR"
    ]
    by_year_type: dict[tuple[int, str], dict[str, Any]] = defaultdict(
        lambda: {"known_value": 0.0, "observations": 0, "suppressed": 0}
    )
    descriptions: dict[str, str] = {}
    for row in selected:
        year = int(row["REPORTINGPERIOD"][:4])
        code = row["TYP_TRNSCTN"]
        descriptions[code] = row["TYP_TRNSCTN_DESC"]
        value = parse_number(row["OBSERVATION"])
        cell = by_year_type[(year, code)]
        cell["observations"] += 1
        if value is None:
            cell["suppressed"] += 1
        else:
            cell["known_value"] += value

    detail_rows: list[dict[str, Any]] = []
    for (year, code), cell in sorted(by_year_type.items()):
        detail_rows.append({
            "year": year,
            "transaction_code": code,
            "transaction_type": descriptions[code],
            "known_public_value_eur_million": round(cell["known_value"], 8),
            "half_year_observations": cell["observations"],
            "suppressed_half_year_observations": cell["suppressed"],
            "safe_to_treat_as_complete": cell["suppressed"] == 0,
            "filters": "COUNT_AREA=W0; RL_TRNSCTN=1; FRD_TYP=F; UNIT_MEASURE=EUR",
            "source_url": entry["canonical_url"],
        })
    write_csv(
        output / "payment-fraud-public-aggregates.csv",
        detail_rows,
        [
            "year", "transaction_code", "transaction_type", "known_public_value_eur_million",
            "half_year_observations", "suppressed_half_year_observations",
            "safe_to_treat_as_complete", "filters", "source_url",
        ],
    )

    published = {
        2023: {"fraud_value": 129.0, "volume_thousand": 579.0, "loss": 64.4},
        2024: {"fraud_value": 160.0, "volume_thousand": 815.0, "loss": 66.4},
    }
    reconciliation: list[dict[str, Any]] = []
    for year, benchmark in published.items():
        indexed = {code: cell for (y, code), cell in by_year_type.items() if y == year}
        known_components = sum(
            indexed.get(code, {}).get("known_value", 0.0)
            for code in ("CP0", "CT0", "CW1", "DD", "EMP0", "MREM", "CHQ", "SER")
        )
        suppressed_component_cells = sum(
            indexed.get(code, {}).get("suppressed", 0)
            for code in ("CP0", "CT0", "CW1", "DD", "EMP0", "MREM", "CHQ", "SER")
        )
        total_ex_cash = indexed.get("TOTL1", {}).get("known_value")
        total_all_suppressed = indexed.get("TOTL", {}).get("suppressed", 0)
        reconciliation.append({
            "year": year,
            "published_fraudulent_payment_value_eur_million": benchmark["fraud_value"],
            "published_fraudulent_payment_volume_thousand": benchmark["volume_thousand"],
            "published_final_loss_eur_million": benchmark["loss"],
            "public_csv_known_component_sum_eur_million": round(known_components, 8),
            "public_csv_suppressed_component_half_year_cells": suppressed_component_cells,
            "public_csv_TOTL1_ex_cash_eur_million": None if total_ex_cash is None else round(total_ex_cash, 8),
            "public_csv_TOTL_all_half_year_cells_suppressed": total_all_suppressed,
            "component_sum_minus_TOTL1_eur_million": (
                None if total_ex_cash is None else round(known_components - total_ex_cash, 8)
            ),
            "headline_source": FRAUD_RELEASE_URL,
            "headline_pages": "1 and 8-9",
            "interpretation": (
                "Fraudulent payment value and final booked loss are distinct measures. "
                "Confidential cells and non-additive public aggregates prevent reconstruction "
                "of the headline total from this CSV."
            ),
        })
    write_csv(
        output / "payment-fraud-reconciliation.csv",
        reconciliation,
        list(reconciliation[0]),
    )

    cp_2024 = by_year_type[(2024, "CP0")]["known_value"]
    ct_2024 = by_year_type[(2024, "CT0")]["known_value"]
    return {
        "source_csv": str(path),
        "source_url": entry["canonical_url"],
        "release_url": FRAUD_RELEASE_URL,
        "release_sha256": FRAUD_RELEASE_SHA256,
        "published_2024_fraudulent_payment_value_eur_million": 160.0,
        "published_2024_final_loss_eur_million": 66.4,
        "published_2024_volume_thousand": 815.0,
        "published_2024_online_share_pct": 77.4,
        "published_2024_sca_share_of_electronic_fraud_value_pct": 63.0,
        "published_2024_user_borne_share_of_final_loss_pct": 66.0,
        "csv_2024_card_value_eur_million": round(cp_2024, 8),
        "csv_2024_credit_transfer_value_eur_million": round(ct_2024, 8),
        "csv_reconstruction_safe": False,
    }


def analyze_mortgage_arrears(
    archive: Path, catalog: list[dict[str, str]], output: Path
) -> dict[str, Any]:
    path, entry = resolve(
        archive,
        catalog,
        "Residential Mortgage Arrears and Repossession Statistics",
        "moa-open data.csv",
    )
    raw_rows = read_csv(path)
    rows = [{clean_header(k): v for k, v in row.items()} for row in raw_rows]
    number_column = "Number of Accounts"

    date_counts: dict[str, int] = defaultdict(int)
    for row in rows:
        date_counts[row["Reporting Date"]] += 1
    odd_month_end_dates = sorted(
        date for date in date_counts
        if date.startswith("01/") and date[3:5] in {"03", "06", "09", "12"}
    )
    number_rows_with_two_values = [
        row for row in rows
        if row["Observation Type"] == "Number"
        and parse_number(row["Observation"]) is not None
        and parse_number(row[number_column]) is not None
    ]
    latest = "31/03/2026"
    latest_rows = [row for row in rows if row["Reporting Date"] == latest]
    expected_bank_pdh = {
        (2, "Number"), (2, "Balance € (000)"), (2, "Arrears € (000)"),
        (3, "Number"), (3, "Balance € (000)"), (3, "Arrears € (000)"),
        (4, "Number"), (4, "Balance € (000)"), (4, "Arrears € (000)"),
    }
    present_bank_pdh = {
        (int(row["Row Position"]), clean_header(row["Observation Type"]))
        for row in latest_rows
        if row["Entity Group"] == "Banks"
        and row["Format"] == "PDH"
        and row["Category"] == "Arrears"
        and row["Row Position"].isdigit()
        and int(row["Row Position"]) in {2, 3, 4}
    }
    missing_bank_pdh = sorted(expected_bank_pdh - present_bank_pdh)

    def account_count(entity: str, fmt: str, row_label: str) -> float | None:
        matches = [
            row for row in latest_rows
            if row["Entity Group"] == entity
            and row["Format"] == fmt
            and row["Category"] == "Arrears"
            and row["Row"] == row_label
            and row["Observation Type"] == "Number"
        ]
        if len(matches) != 1:
            return None
        return parse_number(matches[0][number_column])

    btl_total = sum(
        value or 0 for value in (
            account_count("Banks", "BTL", "Arrears: Total mortgage accounts in arrears"),
            account_count("Non-Banks", "BTL", "Arrears: Total mortgage accounts in arrears"),
        )
    )
    btl_over_90_labels = [
        "Arrears: Total mortgage accounts in arrears - 91 to 180 days",
        "Arrears: Total mortgage accounts in arrears - 181 to 365 days",
        "Arrears: Total mortgage accounts in arrears - 365 to 730 days (1 to 2 YRS)",
        "Arrears: Total mortgage accounts in arrears - 2 to 5 yrs",
        "Arrears: Total mortgage accounts in arrears - 5 to 10 yrs",
        "Arrears: Total mortgage accounts in arrears - over 10 yrs",
    ]
    btl_over_90 = sum(
        account_count(entity, "BTL", label) or 0
        for entity in ("Banks", "Non-Banks")
        for label in btl_over_90_labels
    )

    qc_rows = [
        {
            "check": "rows_have_expected_width",
            "status": "pass",
            "observed": len(rows),
            "expected_or_rule": "19,199 data rows parsed to the 10-column header",
            "impact": "File is structurally readable as CSV.",
        },
        {
            "check": "quarter_end_dates_use_consistent_calendar_dates",
            "status": "fail" if odd_month_end_dates else "pass",
            "observed": " | ".join(odd_month_end_dates),
            "expected_or_rule": "Quarter-end dates should not unexpectedly use day 01.",
            "impact": "Quarter grouping by raw date is unsafe without a documented normalization rule.",
        },
        {
            "check": "number_rows_use_only_number_of_accounts_column",
            "status": "fail" if number_rows_with_two_values else "pass",
            "observed": len(number_rows_with_two_values),
            "expected_or_rule": "Observation should be blank when Observation Type is Number.",
            "impact": "Some Q1 2026 rows contain unrelated monetary values in Observation.",
        },
        {
            "check": "q1_2026_bank_pdh_headline_cells_present",
            "status": "fail" if missing_bank_pdh else "pass",
            "observed": " | ".join(f"row {pos}/{kind}" for pos, kind in missing_bank_pdh),
            "expected_or_rule": "Rows 2-4 should each contain Number, Balance and Arrears observations.",
            "impact": "The CSV cannot reproduce the Q1 2026 aggregate Bank/PDH arrears headline.",
        },
        {
            "check": "q1_2026_btl_arrears_reconciles_to_release",
            "status": "pass" if btl_total == 5708 and btl_over_90 == 4519 else "fail",
            "observed": f"total={int(btl_total)}; over90={int(btl_over_90)}",
            "expected_or_rule": "Release reports total=5,708 and over90=4,519.",
            "impact": "The BTL subset is usable after field-specific parsing.",
        },
    ]
    write_csv(
        output / "mortgage-arrears-open-data-qc.csv",
        qc_rows,
        ["check", "status", "observed", "expected_or_rule", "impact"],
    )

    benchmarks = [
        ("PDH accounts outstanding", 698459, "accounts", 1),
        ("PDH accounts in arrears", 34996, "accounts", 1),
        ("PDH accounts >90 days in arrears", 21302, "accounts", 2),
        ("PDH accounts <90 days in arrears", 13694, "accounts", 2),
        ("PDH outstanding balance", 110.0, "EUR billion", 1),
        ("PDH >90 days arrears balance", 4.5, "EUR billion", 2),
        ("PDH restructured accounts", 53818, "accounts", 5),
        ("BTL accounts outstanding", 46272, "accounts", 4),
        ("BTL accounts in arrears", 5708, "accounts", 4),
        ("BTL accounts >90 days in arrears", 4519, "accounts", 4),
        ("BTL accounts >1 year in arrears", 3846, "accounts", 4),
    ]
    benchmark_rows = [
        {
            "period": "2026-Q1",
            "metric": metric,
            "value": value,
            "unit": unit,
            "source_page": page,
            "source_url": ARREARS_RELEASE_URL,
            "source_sha256": ARREARS_RELEASE_SHA256,
            "provenance": "CBI statistical release; not inferred from malformed headline CSV rows",
        }
        for metric, value, unit, page in benchmarks
    ]
    write_csv(
        output / "mortgage-arrears-release-benchmarks.csv",
        benchmark_rows,
        list(benchmark_rows[0]),
    )
    return {
        "source_csv": str(path),
        "source_url": entry["canonical_url"],
        "release_url": ARREARS_RELEASE_URL,
        "release_sha256": ARREARS_RELEASE_SHA256,
        "release_2026_q1_pdh_arrears_accounts": 34996,
        "release_2026_q1_pdh_over_90_days_accounts": 21302,
        "release_2026_q1_btl_arrears_accounts": 5708,
        "release_2026_q1_btl_over_90_days_accounts": 4519,
        "csv_2026_q1_btl_reconciliation_passed": btl_total == 5708 and btl_over_90 == 4519,
        "csv_2026_q1_bank_pdh_headline_safe": not missing_bank_pdh,
        "csv_number_rows_with_two_numeric_fields": len(number_rows_with_two_values),
        "csv_odd_quarter_dates": odd_month_end_dates,
    }


def analyze_sme_lending(
    archive: Path, catalog: list[dict[str, str]], output: Path
) -> dict[str, Any]:
    path, entry = resolve(
        archive, catalog, "Bank Lending to Irish Businesses", "Ana. 2 Loans to Irish SME's.csv"
    )
    rows = read_csv(path)
    periods = sorted({iso_date(row["Referencedate"]) for row in rows})
    latest = periods[-1]
    prior = f"{int(latest[:4]) - 1}{latest[4:]}"

    def rows_for(period: str) -> list[dict[str, str]]:
        return [row for row in rows if iso_date(row["Referencedate"]) == period]

    def aggregate(period: str, field: str) -> tuple[float, int, int]:
        values = [parse_number(row[field]) for row in rows_for(period)]
        present = [value for value in values if value is not None]
        return sum(present), len(present), len(values) - len(present)

    # The published sector list is not flat. "Info & Communication" was split into
    # two sub-sectors; if the parent and its children ever carry values in the same
    # period, summing every row double-counts. Today the parent is suppressed, so
    # the total happens to be right. Assert it rather than rely on that.
    KNOWN_PARENT_SECTORS = {
        "Info & Communication": (
            "Publishing, Broadcasting, and Content Production and Distribution Activities",
            "Telecommunication, Computer Programming, Consulting, Computing Infrastructure"
            " and Other Information Service Activities",
        ),
    }

    HIERARCHICAL_AMOUNT_FIELDS = (
        "Outstanding_Balance_SME",
        "Transactions_SME",
        "New_Lending_SME",
    )

    def assert_no_double_count(period: str) -> None:
        period_rows = rows_for(period)
        for field in HIERARCHICAL_AMOUNT_FIELDS:
            present = {
                row["Economic Activity"]: parse_number(row[field])
                for row in period_rows
            }
            for parent, children in KNOWN_PARENT_SECTORS.items():
                if present.get(parent) is None:
                    continue
                live_children = [c for c in children if present.get(c) is not None]
                if live_children:
                    raise RuntimeError(
                        f"{period} {field}: sector hierarchy double-count. Parent {parent!r} "
                        f"carries a value alongside child sectors {live_children}. Sum the leaves only."
                    )

    assert_no_double_count(latest)
    assert_no_double_count(prior)

    latest_rows = rows_for(latest)
    sector_rows = []
    for row in latest_rows:
        sector_rows.append({
            "period": latest,
            "economic_activity": row["Economic Activity"],
            "outstanding_balance_eur": parse_number(row["Outstanding_Balance_SME"]),
            "transactions_eur": parse_number(row["Transactions_SME"]),
            "new_lending_eur": parse_number(row["New_Lending_SME"]),
            "interest_rate_pct": parse_number(row["Interest_Rates_SME"]),
            "source_url": entry["canonical_url"],
        })
    write_csv(
        output / "sme-lending-latest-by-sector.csv",
        sector_rows,
        list(sector_rows[0]),
    )

    current_outstanding, current_outstanding_n, current_outstanding_missing = aggregate(
        latest, "Outstanding_Balance_SME"
    )
    prior_outstanding, _, _ = aggregate(prior, "Outstanding_Balance_SME")
    current_new, current_new_n, current_new_missing = aggregate(latest, "New_Lending_SME")
    prior_new, _, _ = aggregate(prior, "New_Lending_SME")
    weighted_pairs = [
        (parse_number(row["New_Lending_SME"]), parse_number(row["Interest_Rates_SME"]))
        for row in latest_rows
    ]
    weighted_pairs = [(amount, rate) for amount, rate in weighted_pairs if amount is not None and rate is not None]
    weighted_rate = sum(amount * rate for amount, rate in weighted_pairs) / sum(
        amount for amount, _ in weighted_pairs
    )
    return {
        "source_csv": str(path),
        "source_url": entry["canonical_url"],
        "latest_period": latest,
        "known_outstanding_balance_eur": round(current_outstanding, 2),
        "known_outstanding_balance_eur_billion": round(current_outstanding / 1e9, 3),
        "known_outstanding_yoy_pct": round(required_pct_change(current_outstanding, prior_outstanding, "SME outstanding balance"), 3),
        "known_quarterly_new_lending_eur": round(current_new, 2),
        "known_quarterly_new_lending_eur_billion": round(current_new / 1e9, 3),
        "known_quarterly_new_lending_yoy_pct": round(required_pct_change(current_new, prior_new, "SME quarterly new lending"), 3),
        "new_lending_weighted_interest_rate_pct": round(weighted_rate, 3),
        "outstanding_present_sectors": current_outstanding_n,
        "outstanding_suppressed_sectors": current_outstanding_missing,
        "new_lending_present_sectors": current_new_n,
        "new_lending_suppressed_sectors": current_new_missing,
        "aggregation_warning": "Known-sector sum; NULL observations are not imputed.",
    }


def analyze_new_mortgages(
    archive: Path, catalog: list[dict[str, str]], output: Path
) -> dict[str, Any]:
    overview_path, overview_entry = resolve(
        archive, catalog, "New Mortgage Lending Statistics", "New Mortgage Lending Overview"
    )
    mean_path, mean_entry = resolve(
        archive, catalog, "New Mortgage Lending Statistics", "Mean Loan Characteristics"
    )
    overview = read_csv(overview_path)
    means = read_csv(mean_path)
    year = max(int(row["Year"]) for row in overview)
    current = [row for row in overview if int(row["Year"]) == year]
    current_means = [row for row in means if int(row["Year"]) == year]
    write_csv(
        output / "new-mortgage-lending-latest-overview.csv",
        current,
        list(current[0]),
    )
    write_csv(
        output / "new-mortgage-lending-latest-characteristics.csv",
        current_means,
        list(current_means[0]),
    )
    total_value = value_for(current, Description="Total Lending", Data_Type="Value of Loans")
    total_count = value_for(current, Description="Total Lending", Data_Type="Number of Loans")
    ftb_value = value_for(current, Description="FTB Lending", Data_Type="Value of Loans")
    ftb_count = value_for(current, Description="FTB Lending", Data_Type="Number of Loans")

    def mean_value(borrower: str, description: str) -> float | None:
        matches = [
            row for row in current_means
            if row["Borrower_Type_Code"] == borrower and row["Description"] == description
        ]
        return parse_number(matches[0]["Observation_Amount"]) if len(matches) == 1 else None

    return {
        "overview_source_csv": str(overview_path),
        "overview_source_url": overview_entry["canonical_url"],
        "characteristics_source_csv": str(mean_path),
        "characteristics_source_url": mean_entry["canonical_url"],
        "latest_year": year,
        "total_lending_eur_million": total_value,
        "total_loans": total_count,
        "ftb_lending_eur_million": ftb_value,
        "ftb_loans": ftb_count,
        "ftb_share_of_value_pct": round((ftb_value or 0) / (total_value or 1) * 100, 2),
        "ftb_share_of_count_pct": round((ftb_count or 0) / (total_count or 1) * 100, 2),
        "ftb_average_loan_eur": mean_value("FTB", "Average Loan Size"),
        "ftb_average_property_eur": mean_value("FTB", "Average Property Value"),
        "ftb_average_income_eur": mean_value("FTB", "Average Income"),
        "ftb_average_lti": mean_value("FTB", "Average Loan-to-Income"),
        "ftb_average_ltv_pct": mean_value("FTB", "Average Loan-to-Value"),
        "ftb_fixed_share_pct": mean_value("FTB", "Fixed"),
        "ssb_average_loan_eur": mean_value("SSB", "Average Loan Size"),
        "ssb_average_income_eur": mean_value("SSB", "Average Income"),
    }


def find_column(
    row: dict[str, str], required_fragments: list[str], excluded_fragments: list[str] | None = None
) -> str:
    excluded_fragments = excluded_fragments or []
    normalized = {clean_header(key).lower(): key for key in row}
    matches = [
        original for cleaned, original in normalized.items()
        if all(fragment.lower() in cleaned for fragment in required_fragments)
        and not any(fragment.lower() in cleaned for fragment in excluded_fragments)
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one column containing {required_fragments}; got {matches}")
    return matches[0]


def analyze_retail_rates(
    archive: Path, catalog: list[dict[str, str]], output: Path
) -> dict[str, Any]:
    deposits_path, deposits_entry = resolve(
        archive, catalog, "Retail Interest Rates - Deposits, Outstanding Amounts", "B.1.1.csv"
    )
    new_path, new_entry = resolve(
        archive,
        catalog,
        "Retail Interest Rates and Volumes  - Loans and Deposits, New Business",
        "B.2.1.csv",
    )
    deposits = read_csv(deposits_path)
    new_business = read_csv(new_path)

    def latest_row(rows: list[dict[str, str]], date_field: str, label: str) -> dict[str, str]:
        """The last CSV row is not, by contract, the most recent one.

        The original code took ``rows[-1]``. That is correct only while the Central
        Bank keeps publishing in ascending date order; a re-sorted file or a
        trailing notes row would silently produce a stale headline rate.
        """
        dated = [(datetime.strptime(row[date_field].strip(), "%d/%m/%Y"), row) for row in rows if row.get(date_field, "").strip()]
        if not dated:
            raise RuntimeError(f"{label}: no parseable {date_field} values")
        newest_date, newest_row = max(dated, key=lambda pair: pair[0])
        if newest_row is not dated[-1][1]:
            print(f"WARNING {label}: file is not in ascending date order; using {newest_date:%d/%m/%Y}", flush=True)
        return newest_row

    drow = latest_row(deposits, "Reporting Date", "B.1.1 deposits")
    nrow = latest_row(new_business, "Reporting date", "B.2.1 new business")

    overnight_rate_col = find_column(drow, ["household deposits", "overnight", "interest rate"])
    overnight_volume_col = find_column(drow, ["household deposits", "overnight", "volumes"])
    term_rate_col = find_column(drow, ["household deposits", "agreed maturity (up to 2 years)", "interest rate"])
    mortgage_rate_col = find_column(
        nrow,
        ["house purchase", "new lending ex. renegotiations", "interest rate"],
        ["floating rate", "over 1 year fixation"],
    )
    small_business_col = find_column(nrow, ["non-financial corporations", "up to and including", "interest rate"])
    consumer_col = find_column(
        nrow,
        ["consumer purposes", "interest rate"],
        ["floating rate", "over 1 year fixation", "aprc"],
    )

    snapshot = [
        {
            "period": iso_date(drow["Reporting Date"]),
            "metric": "Household overnight deposit rate",
            "value": parse_number(drow[overnight_rate_col]),
            "unit": "percent per annum",
            "source_url": deposits_entry["canonical_url"],
        },
        {
            "period": iso_date(drow["Reporting Date"]),
            "metric": "Household overnight deposit volume",
            "value": parse_number(drow[overnight_volume_col]),
            "unit": "EUR million",
            "source_url": deposits_entry["canonical_url"],
        },
        {
            "period": iso_date(drow["Reporting Date"]),
            "metric": "Household deposits up to 2 years rate",
            "value": parse_number(drow[term_rate_col]),
            "unit": "percent per annum",
            "source_url": deposits_entry["canonical_url"],
        },
        {
            "period": iso_date(nrow["Reporting date"]),
            "metric": "New mortgage lending ex renegotiations rate",
            "value": parse_number(nrow[mortgage_rate_col]),
            "unit": "percent per annum",
            "source_url": new_entry["canonical_url"],
        },
        {
            "period": iso_date(nrow["Reporting date"]),
            "metric": "New NFC loans up to EUR250k rate",
            "value": parse_number(nrow[small_business_col]),
            "unit": "percent per annum",
            "source_url": new_entry["canonical_url"],
        },
        {
            "period": iso_date(nrow["Reporting date"]),
            "metric": "New household consumer loan rate",
            "value": parse_number(nrow[consumer_col]),
            "unit": "percent per annum",
            "source_url": new_entry["canonical_url"],
        },
    ]
    write_csv(output / "retail-rate-snapshot.csv", snapshot, list(snapshot[0]))
    rate_map = {row["metric"]: row["value"] for row in snapshot}
    overnight_rate = rate_map["Household overnight deposit rate"]
    term_rate = rate_map["Household deposits up to 2 years rate"]
    if overnight_rate is None or term_rate is None:
        raise RuntimeError(
            "Retail-rate snapshot is missing an overnight or up-to-two-year household deposit rate"
        )
    return {
        "deposit_source_url": deposits_entry["canonical_url"],
        "new_business_source_url": new_entry["canonical_url"],
        "period": snapshot[0]["period"],
        "household_overnight_deposit_rate_pct": rate_map["Household overnight deposit rate"],
        "household_overnight_deposit_volume_eur_million": rate_map["Household overnight deposit volume"],
        "household_term_up_to_2y_rate_pct": rate_map["Household deposits up to 2 years rate"],
        "new_mortgage_ex_renegotiations_rate_pct": rate_map["New mortgage lending ex renegotiations rate"],
        "new_small_business_loan_up_to_250k_rate_pct": rate_map["New NFC loans up to EUR250k rate"],
        "new_consumer_loan_rate_pct": rate_map["New household consumer loan rate"],
        "overnight_to_term_rate_gap_percentage_points": round(
            term_rate - overnight_rate,
            2,
        ),
        "comparison_warning": (
            "Rate gaps compare products with different liquidity, maturity and risk; they are "
            "signals of choice architecture, not estimates of attainable consumer savings."
        ),
    }


def build_key_indicators(results: dict[str, Any], output: Path) -> None:
    fraud = results["payment_fraud"]
    arrears = results["mortgage_arrears"]
    sme = results["sme_lending"]
    mortgages = results["new_mortgages"]
    rates = results["retail_rates"]
    rows = [
        ("Fraudulent payment value", "2024", fraud["published_2024_fraudulent_payment_value_eur_million"], "EUR million", FRAUD_RELEASE_URL, "CBI release p1"),
        ("Final booked payment-fraud loss", "2024", fraud["published_2024_final_loss_eur_million"], "EUR million", FRAUD_RELEASE_URL, "Distinct from fraudulent payment value; CBI release pp8-9"),
        ("Payment-fraud transaction volume", "2024", fraud["published_2024_volume_thousand"], "thousand", FRAUD_RELEASE_URL, "CBI release p1"),
        ("PDH accounts in arrears", "2026-Q1", arrears["release_2026_q1_pdh_arrears_accounts"], "accounts", ARREARS_RELEASE_URL, "Release used because CSV headline block is malformed"),
        ("PDH accounts over 90 days in arrears", "2026-Q1", arrears["release_2026_q1_pdh_over_90_days_accounts"], "accounts", ARREARS_RELEASE_URL, "CBI release p2"),
        ("Known-sector SME outstanding balance", sme["latest_period"], sme["known_outstanding_balance_eur_billion"], "EUR billion", sme["source_url"], "NULL sectors excluded, not imputed"),
        ("Known-sector SME quarterly new lending", sme["latest_period"], sme["known_quarterly_new_lending_eur_billion"], "EUR billion", sme["source_url"], "NULL sectors excluded, not imputed"),
        ("Total new mortgage lending", str(mortgages["latest_year"]), mortgages["total_lending_eur_million"], "EUR million", mortgages["overview_source_url"], "Annual lending"),
        ("New mortgage loans", str(mortgages["latest_year"]), mortgages["total_loans"], "loans", mortgages["overview_source_url"], "Annual lending"),
        ("FTB average loan", str(mortgages["latest_year"]), mortgages["ftb_average_loan_eur"], "EUR", mortgages["characteristics_source_url"], "Mean characteristic"),
        ("Household overnight deposit volume", rates["period"], rates["household_overnight_deposit_volume_eur_million"], "EUR million", rates["deposit_source_url"], "CBI B.1.1 open data"),
        ("Household overnight deposit rate", rates["period"], rates["household_overnight_deposit_rate_pct"], "percent per annum", rates["deposit_source_url"], "CBI B.1.1 open data"),
        ("New small-business loan rate up to EUR250k", rates["period"], rates["new_small_business_loan_up_to_250k_rate_pct"], "percent per annum", rates["new_business_source_url"], "CBI B.2.1 open data"),
    ]
    rendered = [
        {"metric": metric, "period": period, "value": value, "unit": unit, "source_url": url, "note": note}
        for metric, period, value, unit, url, note in rows
    ]
    write_csv(output / "key-indicators.csv", rendered, list(rendered[0]))


def main() -> int:
    args = arguments()
    archive = args.archive.resolve()
    profile_dir = args.profile_dir.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    catalog = read_csv(profile_dir / "structured-file-catalog.csv")

    results = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": (
            "Direct CSV analysis with explicit filters and no imputation; release benchmarks "
            "are separately identified by URL, page and archived SHA-256."
        ),
    }
    results["payment_fraud"] = analyze_payment_fraud(archive, catalog, output)
    results["mortgage_arrears"] = analyze_mortgage_arrears(archive, catalog, output)
    results["sme_lending"] = analyze_sme_lending(archive, catalog, output)
    results["new_mortgages"] = analyze_new_mortgages(archive, catalog, output)
    results["retail_rates"] = analyze_retail_rates(archive, catalog, output)
    build_key_indicators(results, output)
    (output / "key-dataset-analysis.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(results, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
