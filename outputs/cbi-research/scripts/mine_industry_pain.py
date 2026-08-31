#!/usr/bin/env python3
"""Find operational pain that Irish regulated firms report about themselves.

Why this exists
---------------
The topic scan measures how often a subject appears anywhere in the archive.
That answers "what does the Central Bank publish about", which is a poor proxy
for "what is expensive and unsolved for the firms". This script asks a different
question, using the authorship axis that only became reliable after the
provenance classifier was rewritten:

  * how many *stakeholder submissions* raise a given operational pain
  * across how many distinct consultations
  * over how many years
  * and how much does *Central Bank* material engage with the same thing

Persistence is the signal, not volume. A pain raised by many firms across many
separate consultations over fifteen years is a pain nobody has solved. A pain
raised loudly in one consultation is a reaction to one policy.

Everything here is a discovery layer. Counts locate documents to read; they do
not rank importance, and no conclusion should leave this script without someone
reading the underlying pages.
"""
from __future__ import annotations
import argparse, csv, json, sqlite3, time
from pathlib import Path

# Operational-pain vocabulary. Each theme is deliberately narrow: these are the
# words a compliance or operations lead uses when describing cost, not the words
# a policymaker uses when describing objectives.
THEMES = [
    ("compliance_cost",     "Cost and disproportionality",
     '"disproportionate" OR "disproportionately" OR "cost of compliance" OR "compliance burden" '
     'OR "administrative burden" OR "resource intensive" OR "resource-intensive" OR "significant cost"'),
    ("duplication",         "Duplicated effort and re-reporting",
     '"duplication" OR "duplicative" OR "already provided" OR "already reported" OR "same information" '
     'OR "multiple returns" OR "re-submit" OR "resubmit"'),
    ("manual_effort",       "Manual work and spreadsheets",
     '"manual" OR "manually" OR "spreadsheet" OR "spreadsheets" OR "re-key" OR "rekey" OR "paper-based"'),
    ("proportionality",     "Proportionality and smaller firms",
     '"proportionality" OR "proportionate" OR "smaller firms" OR "smaller entities" OR "small firms" '
     'OR "one size fits all" OR "one-size-fits-all"'),
    ("implementation_time", "Implementation timelines",
     '"implementation period" OR "lead time" OR "lead-in" OR "insufficient time" OR "not feasible" '
     'OR "transitional period" OR "sufficient time"'),
    ("ambiguity",           "Unclear requirements",
     '"unclear" OR "ambiguous" OR "ambiguity" OR "further clarity" OR "additional clarity" '
     'OR "clarification is" OR "we would welcome clarity"'),
    ("definitions",         "Definitions and inconsistency",
     '"definition" AND (unclear OR inconsistent OR differs OR differ OR aligned OR alignment)'),
    ("systems_change",      "IT and system change",
     '"system changes" OR "systems changes" OR "IT systems" OR "legacy system" OR "legacy systems" '
     'OR "system build" OR "system development" OR "technology investment"'),
    ("data_quality",        "Data quality and reconciliation",
     '"data quality" OR "data governance" OR "reconciliation" OR "reconcile" OR "data integrity"'),
    ("reporting_burden",    "Regulatory reporting mechanics",
     '(reporting OR "returns" OR "return") AND (burden OR frequency OR template OR templates OR taxonomy OR XBRL)'),
    ("outsourcing",         "Outsourcing and third parties",
     '"outsourcing" OR "outsourced" OR "third party" OR "third-party" OR "intragroup" OR "intra-group"'),
    ("authorisation_delay", "Authorisation and approval friction",
     '"authorisation process" OR "approval process" OR "application process" OR "delays" OR "timeframes"'),
    ("fitness_probity",     "Individual approval and vetting",
     '"fitness and probity" OR "pre-approval" OR "PCF" OR "controlled function"'),
    ("customer_comms",      "Customer disclosure mechanics",
     '"disclosure requirements" OR "customer communication" OR "information overload" OR "warning statement"'),
    ("complaints_ops",      "Complaints handling operations",
     '"complaints handling" OR "complaint handling" OR "root cause" OR "root-cause" OR "complaints process"'),
    ("fraud_ops",           "Fraud and scam handling",
     'fraud OR scam OR scams OR "authorised push payment" OR "money mule" OR impersonation'),
    ("safeguarding_ops",    "Safeguarding client money",
     '"safeguarding" OR "client money" OR "client assets" OR "segregation of funds" OR "safeguarded funds"'),
    ("vulnerability",       "Vulnerable customers in practice",
     '"vulnerable customer" OR "vulnerable customers" OR "vulnerability" OR "in vulnerable circumstances"'),
    ("switching_ops",       "Switching and portability mechanics",
     '"switching" OR "switch" OR "portability" OR "account transfer"'),
    ("credit_union_ops",    "Credit union operating constraints",
     '"credit union" OR "credit unions" OR "common bond" OR "CUSO"'),
]


def counts(cur, query: str, authorship: str) -> dict:
    row = cur.execute(
        """
        SELECT COUNT(DISTINCT d.document_id) AS documents,
               COUNT(*)                      AS pages,
               COUNT(DISTINCT d.consultation_id) AS consultations
        FROM pages_fts AS p
        JOIN pages AS pg USING(document_id, page_number)
        JOIN documents AS d USING(document_id)
        WHERE pages_fts MATCH ? AND pg.authorship = ?
        """, (query, authorship)).fetchone()
    years = [
        int(y) for (y,) in cur.execute(
            """
            SELECT DISTINCT d.analysis_year AS y
            FROM pages_fts AS p
            JOIN pages AS pg USING(document_id, page_number)
            JOIN documents AS d USING(document_id)
            WHERE pages_fts MATCH ? AND pg.authorship = ?
              AND d.analysis_year IS NOT NULL
            """, (query, authorship)).fetchall()
    ]
    return {"documents": row["documents"], "pages": row["pages"],
            "consultations": row["consultations"],
            "years_present": len(years),
            "first_year": min(years) if years else None,
            "last_year": max(years) if years else None}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    con = sqlite3.connect(f"file:{args.database.resolve()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # A mixed container can contribute to both denominators, but only through
    # pages whose audited page-level authorship matches the requested voice.
    total_stake = cur.execute(
        "SELECT COUNT(DISTINCT document_id) FROM pages WHERE authorship='stakeholder'"
    ).fetchone()[0]
    total_cbi = cur.execute(
        "SELECT COUNT(DISTINCT document_id) FROM pages WHERE authorship='central-bank'"
    ).fetchone()[0]

    rows = []
    for theme_id, label, query in THEMES:
        stake = counts(cur, query, "stakeholder")
        cbi = counts(cur, query, "central-bank")
        # Persistence: raised in many separate consultations, over a long span.
        persistence = stake["consultations"] * stake["years_present"]
        # Attention gap: how much more of the industry raises it than the share of
        # Central Bank material that engages with it. Above 1.0 means firms talk
        # about it more than the regulator's own corpus does.
        stake_share = stake["documents"] / total_stake if total_stake else 0
        cbi_share = cbi["documents"] / total_cbi if total_cbi else 0
        rows.append({
            "theme": theme_id, "label": label,
            "stakeholder_documents": stake["documents"],
            "stakeholder_share_pct": round(100 * stake_share, 1),
            "consultations": stake["consultations"],
            "years_present": stake["years_present"],
            "first_year": stake["first_year"], "last_year": stake["last_year"],
            "persistence_score": persistence,
            "cbi_documents": cbi["documents"],
            "cbi_share_pct": round(100 * cbi_share, 1),
            "industry_vs_regulator_ratio": round(stake_share / cbi_share, 2) if cbi_share else None,
            "query": query,
        })

    rows.sort(key=lambda r: -r["persistence_score"])
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / "industry-pain-scan.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n"); w.writeheader(); w.writerows(rows)
    (args.output / "industry-pain-scan.json").write_text(
        json.dumps({"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "stakeholder_documents_total": total_stake,
                    "central_bank_documents_total": total_cbi,
                    "method": "Discovery layer only. Counts locate documents to read. "
                              "Authorship is page-level; mixed containers can contribute to both voices.",
                    "themes": rows}, indent=2) + "\n", encoding="utf-8", newline="\n")

    print(f"stakeholder corpus: {total_stake}   central bank corpus: {total_cbi}\n")
    print(f"{'theme':22s} {'docs':>5s} {'%':>5s} {'cons':>5s} {'span':>11s} {'persist':>8s} {'vs CBI':>7s}")
    for r in rows:
        span = f"{r['first_year']}-{r['last_year']}" if r["first_year"] else "n/a"
        ratio = f"{r['industry_vs_regulator_ratio']:.2f}" if r["industry_vs_regulator_ratio"] else "n/a"
        print(f"{r['theme']:22s} {r['stakeholder_documents']:5d} {r['stakeholder_share_pct']:5.1f} "
              f"{r['consultations']:5d} {span:>11s} {r['persistence_score']:8d} {ratio:>7s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
