#!/usr/bin/env python3
"""Post-conversion extraction-quality QA.

Why this is separate from validate_corpus.py
--------------------------------------------
``validate_corpus.py`` verifies that artifacts are internally consistent: source
hashes, Markdown hashes, byte counts, sequential page markers, page counts,
orphans. It cannot detect a document whose pages are structurally perfect and
substantively blank, because nothing it checks looks at how much text a page
holds. That is why the corpus reports "zero conversion errors" while six
documents carry a majority of empty pages.

This script adds the missing content checks and produces a graded report. It
changes no corpus file; it tells you which documents to distrust.

Grades
------
  ok         nothing anomalous
  thin       below 200 non-space characters per page on average
  gappy      at least 30% of pages hold almost no text
  garbled    at least 200 Unicode replacement characters, or 1 per 500 chars
  empty      effectively no extractable text
"""
from __future__ import annotations
import argparse, csv, json, statistics, time
from collections import Counter
from pathlib import Path

THIN_CHARS_PER_PAGE = 200
GAPPY_EMPTY_RATIO = 0.30
GARBLED_ABSOLUTE = 200
GARBLED_RATE = 1 / 500


def grade(pages: int, nonspace: int, empty: int, replacements: int) -> tuple[str, str]:
    if pages <= 0 or nonspace < 100:
        return "empty", "no extractable text"
    density = nonspace / pages
    empty_ratio = empty / pages
    if replacements >= GARBLED_ABSOLUTE or (nonspace and replacements / nonspace >= GARBLED_RATE):
        return "garbled", f"{replacements} replacement characters over {nonspace} non-space characters"
    if empty_ratio >= GAPPY_EMPTY_RATIO:
        return "gappy", f"{empty}/{pages} pages hold under 30 non-space characters ({empty_ratio:.0%})"
    if density < THIN_CHARS_PER_PAGE:
        return "thin", f"{density:.0f} non-space characters per page"
    return "ok", ""


def load(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, action="append", required=True,
                    help="conversion-manifest.csv; repeatable")
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--extraction-preferences-csv", type=Path,
                    help="same duplicate-extraction choices used by the indexer")
    args = ap.parse_args()

    candidates: dict[str, list[dict]] = {}
    for manifest in args.manifest:
        for row in load(manifest.resolve()):
            row["_manifest"] = "pdf" if manifest.parent.name == "corpus" else manifest.parent.name
            candidates.setdefault(row["source_sha256"], []).append(row)

    preferences = {
        row["source_sha256"]: row for row in
        load(args.extraction_preferences_csv.resolve())
    } if args.extraction_preferences_csv else {}
    rows = []
    duplicate_manifest_rows = 0
    for sha, choices in candidates.items():
        if len(choices) == 1:
            rows.append(choices[0])
            continue
        duplicate_manifest_rows += len(choices) - 1
        preference = preferences.get(sha)
        if not preference:
            raise ValueError(f"duplicate extraction {sha} has no explicit preference")
        selected = [row for row in choices
                    if row["_manifest"] == preference["preferred_corpus"]]
        if len(selected) != 1:
            raise ValueError(f"duplicate extraction preference for {sha} matched {len(selected)} rows")
        rows.append(selected[0])

    def as_int(row, key):
        try:
            return int(row.get(key) or 0)
        except ValueError:
            return 0

    graded = []
    for row in rows:
        if row.get("status") not in {"success", "low_text"}:
            continue
        pages = as_int(row, "pages")
        nonspace = as_int(row, "nonspace_characters")
        empty = as_int(row, "empty_pages")
        replacements = as_int(row, "replacement_characters")
        verdict, detail = grade(pages, nonspace, empty, replacements)
        graded.append({
            "source_sha256": row["source_sha256"], "source_url": row["url"],
            "corpus": row["_manifest"], "format": row.get("format", "PDF"),
            "engine": row.get("engine", ""), "ocr": row.get("ocr", ""),
            "page_basis": row.get("page_basis", "source-page"),
            "pages": pages, "empty_pages": empty,
            "empty_page_ratio": round(empty / pages, 4) if pages else 0,
            "nonspace_characters": nonspace,
            "nonspace_per_page": round(nonspace / pages, 1) if pages else 0,
            "replacement_characters": replacements,
            "manifest_status": row["status"], "extraction_grade": verdict, "detail": detail,
        })

    graded.sort(key=lambda r: (r["extraction_grade"] == "ok", r["nonspace_per_page"]))
    args.output.mkdir(parents=True, exist_ok=True)
    fields = list(graded[0]) if graded else []
    with (args.output / "extraction-quality.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader(); w.writerows(graded)
    flagged = [r for r in graded if r["extraction_grade"] != "ok"]
    with (args.output / "extraction-quality-flagged.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader(); w.writerows(flagged)

    densities = [r["nonspace_per_page"] for r in graded if r["pages"]]
    summary = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "documents_assessed": len(graded),
        "duplicate_manifest_rows_deduplicated_by_sha256": duplicate_manifest_rows,
        "total_pages": sum(r["pages"] for r in graded),
        "total_empty_pages": sum(r["empty_pages"] for r in graded),
        "empty_page_share": round(sum(r["empty_pages"] for r in graded) / max(sum(r["pages"] for r in graded), 1), 4),
        "grades": dict(Counter(r["extraction_grade"] for r in graded).most_common()),
        "documents_with_any_replacement_characters": sum(1 for r in graded if r["replacement_characters"]),
        "median_nonspace_per_page": round(statistics.median(densities), 1) if densities else 0,
        "flagged_documents": len(flagged),
        "flagged_pages": sum(r["pages"] for r in flagged),
        "note": ("Grades describe extraction fidelity, not conversion success. A document can pass "
                 "every structural check in validate_corpus.py and still be graded gappy or garbled."),
        "metric_basis": "final-page-text",
        "near_blank_page_definition": "fewer than 30 Unicode non-space characters",
    }
    (args.output / "extraction-quality-summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
