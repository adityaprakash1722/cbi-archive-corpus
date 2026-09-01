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
  suspect    plausible text whose expansion or repetition indicates semantic corruption
  thin       below 200 non-space characters per page on average
  gappy      at least 30% of pages hold almost no text
  garbled    at least 200 Unicode replacement characters, or 1 per 500 chars
  empty      effectively no extractable text
"""
from __future__ import annotations
import argparse, csv, hashlib, json, re, statistics, time
from collections import Counter
from pathlib import Path

THIN_CHARS_PER_PAGE = 200
GAPPY_EMPTY_RATIO = 0.30
GARBLED_ABSOLUTE = 200
GARBLED_RATE = 1 / 500
MAX_OUTPUT_EXPANSION = 5.0
MAX_REPEATED_LINE_SHARE = 0.50
MAX_PAGE_CHARACTERS = 500_000
MAX_DEDUPLICATED_PAGE_DUPLICATION_SHARE = 0.04
PAGE_PATTERN = re.compile(
    r'<!-- source-page: (\d+) -->\s*\n<a id="page-\d+"></a>\s*\n', re.MULTILINE)


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


def semantic_flags(row: dict) -> list[str]:
    """Catch corruption that density and replacement-character tests cannot see."""
    flags: list[str] = []
    try:
        expansion = float(row.get("output_expansion_ratio") or 0)
    except ValueError:
        expansion = 0
    try:
        repeated = float(row.get("repeated_line_share") or 0)
    except ValueError:
        repeated = 0
    try:
        longest = int(float(row.get("max_page_characters") or 0))
    except ValueError:
        longest = 0
    if expansion > MAX_OUTPUT_EXPANSION:
        flags.append(f"output/source visible-text expansion is {expansion:.1f}x")
    if repeated > MAX_REPEATED_LINE_SHARE:
        flags.append(f"{repeated:.0%} of output characters are repeated lines")
    if longest > MAX_PAGE_CHARACTERS:
        flags.append(f"one page contains {longest:,} characters")
    return flags


def load(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def markdown_pages(path: Path) -> list[str]:
    payload = path.read_text(encoding="utf-8")
    end = payload.find("\n---\n", 4)
    body = payload[end + 5:] if end >= 0 else payload
    matches = list(PAGE_PATTERN.finditer(body))
    return [
        body[match.end():(matches[index + 1].start()
                          if index + 1 < len(matches) else len(body))].strip()
        for index, match in enumerate(matches)
    ]


def duplicate_page_metrics(rows: list[dict]) -> dict:
    """Measure literal page reuse, both before and after document deduplication."""
    documents: dict[str, list[str]] = {}
    for row in rows:
        root = Path(row["_manifest_path"]).parent
        path = root / (row.get("markdown_file") or "").replace("\\", "/")
        documents[row["source_sha256"]] = markdown_pages(path)

    def measure(selected: list[list[str]]) -> tuple[int, int, int]:
        counts: Counter[str] = Counter()
        lengths: dict[str, int] = {}
        nonempty = 0
        for pages in selected:
            for page in pages:
                if not page.strip():
                    continue
                nonempty += 1
                digest = hashlib.sha256(page.encode("utf-8")).hexdigest()
                counts[digest] += 1
                lengths[digest] = len(page)
        excess_rows = sum(count - 1 for count in counts.values() if count > 1)
        excess_characters = sum(
            (count - 1) * lengths[digest]
            for digest, count in counts.items() if count > 1)
        return nonempty, excess_rows, excess_characters

    all_nonempty, all_rows, all_characters = measure(list(documents.values()))
    unique_documents: dict[str, list[str]] = {}
    for pages in documents.values():
        digest = hashlib.sha256("\x1e".join(pages).encode("utf-8")).hexdigest()
        unique_documents.setdefault(digest, pages)
    unique_nonempty, unique_rows, unique_characters = measure(list(unique_documents.values()))
    return {
        "nonempty_pages": all_nonempty,
        "exact_document_text_clusters": len(unique_documents),
        "exact_duplicate_nonempty_page_excess": all_rows,
        "exact_duplicate_nonempty_page_excess_characters": all_characters,
        "after_exact_document_dedup_nonempty_pages": unique_nonempty,
        "after_exact_document_dedup_page_excess": unique_rows,
        "after_exact_document_dedup_page_excess_characters": unique_characters,
    }


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
        resolved_manifest = manifest.resolve()
        for row in load(resolved_manifest):
            row["_manifest"] = "pdf" if manifest.parent.name == "corpus" else manifest.parent.name
            row["_manifest_path"] = str(resolved_manifest)
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
        flags = semantic_flags(row)
        if flags and verdict == "ok":
            verdict = "suspect"
            detail = "; ".join(flags)
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
            "source_text_characters": as_int(row, "source_text_characters"),
            "output_expansion_ratio": row.get("output_expansion_ratio", ""),
            "max_page_characters": as_int(row, "max_page_characters"),
            "repeated_line_share": row.get("repeated_line_share", ""),
            "semantic_quality_flags": "; ".join(flags),
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
    duplication = duplicate_page_metrics([
        row for row in rows if row.get("status") in {"success", "low_text"}
    ])
    total_characters = sum(as_int(row, "characters") for row in rows)
    deduplicated_duplicate_share = round(
        duplication["after_exact_document_dedup_page_excess_characters"] /
        max(total_characters, 1), 4)
    gate_failures = []
    suspect_count = sum(r["extraction_grade"] == "suspect" for r in graded)
    if suspect_count:
        gate_failures.append(f"{suspect_count} documents failed semantic extraction QA")
    if deduplicated_duplicate_share > MAX_DEDUPLICATED_PAGE_DUPLICATION_SHARE:
        gate_failures.append(
            f"post-document-dedup exact-page repetition is {deduplicated_duplicate_share:.2%}")
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
        **duplication,
        "total_extracted_characters": total_characters,
        "after_exact_document_dedup_page_duplication_share": deduplicated_duplicate_share,
        "maximum_allowed_page_duplication_share": MAX_DEDUPLICATED_PAGE_DUPLICATION_SHARE,
        "semantic_gate_failures": gate_failures,
        "passed": not gate_failures,
    }
    (args.output / "extraction-quality-summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(summary, indent=2))
    return 0 if not gate_failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
