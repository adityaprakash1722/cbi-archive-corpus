#!/usr/bin/env python3
"""Catalog structured archive files and stream-profile official open-data CSVs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


FORMATS = {"CSV", "XLSX", "XLS", "XML"}


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--progress-every", type=int, default=10)
    return parser.parse_args()


def choose_encoding(path: Path) -> str:
    prefix = path.read_bytes()[:4]
    if prefix.startswith(b"\xff\xfe") or prefix.startswith(b"\xfe\xff"):
        return "utf-16"
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            with path.open(encoding=encoding, newline="") as stream:
                stream.read(65536)
            return encoding
        except UnicodeDecodeError:
            continue
    return "latin-1"


def clean_sample(rows: Iterable[list[str]], limit: int = 5) -> list[list[str]]:
    sample = []
    for row in rows:
        sample.append([value[:500] for value in row])
        if len(sample) >= limit:
            break
    return sample


def profile_csv(path: Path) -> dict:
    started = time.monotonic()
    encoding = choose_encoding(path)
    row_count = 0
    max_columns = 0
    column_counts: Counter[int] = Counter()
    sample: list[list[str]] = []
    with path.open(encoding=encoding, errors="replace", newline="") as stream:
        reader = csv.reader(stream)
        for row in reader:
            row_count += 1
            columns = len(row)
            max_columns = max(max_columns, columns)
            column_counts[columns] += 1
            if len(sample) < 5:
                sample.append([value[:500] for value in row])
    header = sample[0] if sample else []
    return {
        "encoding": encoding,
        "rows_including_header": row_count,
        "data_rows": max(row_count - 1, 0),
        "max_columns": max_columns,
        "common_column_counts": [
            {"columns": columns, "rows": count}
            for columns, count in column_counts.most_common(5)
        ],
        "header": header,
        "sample_rows": sample[1:],
        "seconds": round(time.monotonic() - started, 3),
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = arguments()
    archive = args.archive.resolve()
    output = args.output.resolve()
    manifest = archive / "manifests" / "files.csv"
    with manifest.open(encoding="utf-8-sig", newline="") as stream:
        records = [
            row for row in csv.DictReader(stream)
            if row.get("status") == "downloaded" and row.get("format", "").upper() in FORMATS
        ]

    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in records:
        grouped[row["sha256"]].append(row)

    catalog = []
    for sha256, aliases in grouped.items():
        canonical = aliases[0]
        local_path = archive / canonical["localPath"].replace("\\", "/")  # manifest paths are written on Windows
        catalog.append({
            "sha256": sha256,
            "format": canonical["format"].upper(),
            "bytes": int(canonical.get("downloadedBytes") or local_path.stat().st_size),
            "source": canonical.get("source", ""),
            "dataset_title": canonical.get("datasetTitle", ""),
            "resource_name": canonical.get("resourceName", ""),
            "local_path": canonical["localPath"],
            "canonical_url": canonical["url"],
            "url_alias_count": len(aliases),
            "all_urls": " | ".join(sorted({row["url"] for row in aliases})),
            "referrers": " | ".join(sorted({row.get("referrers", "") for row in aliases if row.get("referrers")})),
        })
    catalog.sort(key=lambda row: (row["format"], row["dataset_title"], row["resource_name"], row["canonical_url"]))

    all_csvs = [row for row in catalog if row["format"] == "CSV"]
    profiles = []
    for index, row in enumerate(all_csvs, 1):
        path = archive / row["local_path"].replace("\\", "/")  # manifest paths are written on Windows
        profile = {**row, **profile_csv(path)}
        actual_sha = sha256_file(path)
        profile["hash_verified"] = actual_sha == row["sha256"]
        profiles.append(profile)
        if index % args.progress_every == 0 or index == len(all_csvs):
            print(f"Profiled {index}/{len(all_csvs)} CSVs", flush=True)

    output.mkdir(parents=True, exist_ok=True)
    write_csv(
        output / "structured-file-catalog.csv",
        catalog,
        [
            "sha256", "format", "bytes", "source", "dataset_title", "resource_name", "local_path",
            "canonical_url", "url_alias_count", "all_urls", "referrers",
        ],
    )
    def render_profiles(source_rows: list[dict]) -> list[dict]:
        rendered_rows = []
        for row in source_rows:
            rendered = dict(row)
            rendered["header"] = " | ".join(row["header"])
            rendered["common_column_counts"] = json.dumps(row["common_column_counts"], ensure_ascii=False)
            rendered["sample_rows"] = json.dumps(row["sample_rows"], ensure_ascii=False)
            rendered_rows.append(rendered)
        return rendered_rows

    profile_rows = render_profiles(profiles)
    official_profiles = [row for row in profiles if row["source"] == "opendata"]
    official_profile_rows = render_profiles(official_profiles)
    profile_fields = [
        "sha256", "source", "dataset_title", "resource_name", "bytes", "data_rows", "max_columns", "encoding",
        "header", "common_column_counts", "hash_verified", "seconds", "canonical_url", "local_path",
        "sample_rows",
    ]
    write_csv(output / "all-csv-profile.csv", profile_rows, profile_fields)
    write_csv(output / "open-data-csv-profile.csv", official_profile_rows, profile_fields)
    (output / "all-csv-profile.json").write_text(
        json.dumps({"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "resources": profiles}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (output / "open-data-csv-profile.json").write_text(
        json.dumps({"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "resources": official_profiles}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    summary = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "downloaded_structured_url_records": len(records),
        "logical_structured_files": len(catalog),
        "logical_by_format": dict(sorted(Counter(row["format"] for row in catalog).items())),
        "all_logical_csvs": len(profiles),
        "all_csv_bytes": sum(row["bytes"] for row in profiles),
        "all_csv_rows_including_headers": sum(row["rows_including_header"] for row in profiles),
        "official_open_data_csvs": len(official_profiles),
        "official_open_data_bytes": sum(row["bytes"] for row in official_profiles),
        "official_open_data_rows_including_headers": sum(row["rows_including_header"] for row in official_profiles),
        "hash_failures": sum(not row["hash_verified"] for row in profiles),
    }
    (output / "structured-profile-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    return 0 if summary["hash_failures"] == 0 else 1
if __name__ == "__main__":
    raise SystemExit(main())
