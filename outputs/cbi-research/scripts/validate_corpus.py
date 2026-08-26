#!/usr/bin/env python3
"""Validate completeness, hashes, provenance, and page structure of the corpus."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path


PAGE_PATTERN = re.compile(r'<!-- source-page: (\d+) -->\s*\n<a id="page-(\d+)"></a>')


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--audit-csv", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--progress-every", type=int, default=250)
    return parser.parse_args()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def parse_frontmatter(markdown: str) -> tuple[dict, str]:
    if not markdown.startswith("---\n"):
        raise ValueError("Markdown file has no frontmatter")
    end = markdown.find("\n---\n", 4)
    if end == -1:
        raise ValueError("Markdown frontmatter is not closed")
    metadata: dict = {}
    for line in markdown[4:end].splitlines():
        key, separator, value = line.partition(":")
        if separator:
            metadata[key.strip()] = json.loads(value.strip())
    return metadata, markdown[end + 5 :]


def main() -> int:
    args = arguments()
    corpus = args.corpus.resolve()
    archive = args.archive.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()

    with args.audit_csv.resolve().open(encoding="utf-8-sig", newline="") as stream:
        audit_rows = list(csv.DictReader(stream))
    expected = {row["sha256"]: row for row in audit_rows}
    manifest_path = corpus / "conversion-manifest.csv"
    with manifest_path.open(encoding="utf-8-sig", newline="") as stream:
        manifest_rows = list(csv.DictReader(stream))

    failures: list[dict] = []
    warnings: list[dict] = []
    manifest_shas = [row["source_sha256"] for row in manifest_rows]
    duplicate_manifest_shas = sorted(sha for sha, count in Counter(manifest_shas).items() if count > 1)
    for sha in duplicate_manifest_shas:
        failures.append({"source_sha256": sha, "check": "unique-manifest-row", "detail": "duplicate SHA in manifest"})

    manifest_by_sha = {row["source_sha256"]: row for row in manifest_rows}
    for sha in sorted(set(expected) - set(manifest_by_sha)):
        failures.append({"source_sha256": sha, "check": "completeness", "detail": "missing from conversion manifest"})
    for sha in sorted(set(manifest_by_sha) - set(expected)):
        failures.append({"source_sha256": sha, "check": "completeness", "detail": "not present in logical audit"})

    valid_markdown_paths: set[Path] = set()
    status_counts: Counter[str] = Counter()
    engine_counts: Counter[str] = Counter()
    total_pages = 0
    source_bytes_checked = 0
    markdown_bytes_checked = 0

    for index, row in enumerate(manifest_rows, 1):
        sha = row["source_sha256"]
        status_counts[row["status"]] += 1
        engine_counts[f"{row['engine']}|ocr={row['ocr']}"] += 1
        if row["status"] not in {"success", "low_text"}:
            failures.append({"source_sha256": sha, "check": "conversion-status", "detail": row["status"] + ": " + (row.get("error") or "")})
            continue
        markdown_path = (corpus / row["markdown_file"]).resolve()
        valid_markdown_paths.add(markdown_path)
        if not markdown_path.is_file():
            failures.append({"source_sha256": sha, "check": "markdown-file", "detail": f"missing: {markdown_path}"})
            continue
        try:
            payload = markdown_path.read_bytes()
            markdown_bytes_checked += len(payload)
            actual_markdown_sha = sha256_bytes(payload)
            if actual_markdown_sha != row["markdown_sha256"]:
                raise ValueError(f"Markdown SHA mismatch: {actual_markdown_sha}")
            if len(payload) != int(row["markdown_bytes"]):
                raise ValueError(f"Markdown byte count mismatch: {len(payload)}")
            metadata, body = parse_frontmatter(payload.decode("utf-8"))
            if metadata.get("source_sha256") != sha:
                raise ValueError("frontmatter source SHA mismatch")
            if metadata.get("source_file") != row["source_file"]:
                raise ValueError("frontmatter source path mismatch")
            if metadata.get("markdown_sha256"):
                warnings.append({"source_sha256": sha, "check": "self-hash", "detail": "frontmatter unexpectedly contains a Markdown self-hash"})
            markers = PAGE_PATTERN.findall(body)
            pages = int(row["pages"])
            total_pages += pages
            marker_numbers = [int(left) for left, right in markers if left == right]
            if len(markers) != len(marker_numbers):
                raise ValueError("source-page comment and anchor disagree")
            if marker_numbers != list(range(1, pages + 1)):
                raise ValueError(f"non-sequential page markers: expected 1..{pages}, found {len(marker_numbers)}")
            audit_row = expected.get(sha)
            if audit_row and audit_row["status"] in {"ok", "likely_ocr"}:
                audited_pages = int(audit_row["page_count"])
                if pages != audited_pages:
                    raise ValueError(f"page count differs from audit: manifest={pages}, audit={audited_pages}")
            source_path = (archive / row["source_file"].replace("\\", "/")).resolve()  # manifest paths are written on Windows
            if not source_path.is_file():
                raise ValueError(f"source file missing: {source_path}")
            actual_source_sha = sha256_file(source_path)
            source_bytes_checked += source_path.stat().st_size
            if actual_source_sha != sha:
                raise ValueError(f"source SHA mismatch: {actual_source_sha}")
        except Exception as exc:
            failures.append({"source_sha256": sha, "check": "artifact-validation", "detail": f"{type(exc).__name__}: {exc}"})
        if index % args.progress_every == 0:
            print(f"Validated {index}/{len(manifest_rows)} manifest records; failures={len(failures)}", flush=True)

    actual_markdown_paths = {path.resolve() for path in (corpus / "markdown").rglob("*.md")}
    orphan_paths = sorted(actual_markdown_paths - valid_markdown_paths)
    for path in orphan_paths:
        failures.append({"source_sha256": "", "check": "orphan-markdown", "detail": str(path)})

    summary = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "expected_logical_documents": len(expected),
        "manifest_records": len(manifest_rows),
        "manifest_unique_shas": len(set(manifest_shas)),
        "markdown_files": len(actual_markdown_paths),
        "total_pages": total_pages,
        "status_counts": dict(status_counts),
        "engine_counts": dict(engine_counts),
        "source_bytes_hashed": source_bytes_checked,
        "markdown_bytes_hashed": markdown_bytes_checked,
        "orphan_markdown_files": len(orphan_paths),
        "warnings": len(warnings),
        "failures": len(failures),
        "passed": not failures,
    }
    (output / "corpus-validation.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    with (output / "corpus-validation-failures.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["source_sha256", "check", "detail"])
        writer.writeheader()
        writer.writerows(failures)
    with (output / "corpus-validation-warnings.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["source_sha256", "check", "detail"])
        writer.writeheader()
        writer.writerows(warnings)
    print(json.dumps(summary, indent=2), flush=True)
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
