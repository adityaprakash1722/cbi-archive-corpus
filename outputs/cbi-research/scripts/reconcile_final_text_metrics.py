#!/usr/bin/env python3
"""Make conversion metadata describe the final, published page text.

Recovery passes can replace page bodies after conversion. The old pipeline updated
only the files it touched, leaving three competing answers for page quality: the
Markdown frontmatter, conversion manifests, and published page text. This script
makes the final page text canonical and updates the other two layers together.

Metric semantics are deliberately explicit:

* ``characters`` is the length of ``"\n".join(final_page_text)``.
* ``nonspace_characters`` counts Unicode characters for which ``isspace()`` is false.
* ``empty_pages`` means near-blank pages with fewer than 30 non-space characters.
* ``replacement_characters`` counts U+FFFD in the final page text.

Use ``--check`` in CI. A normal run rewrites only changed Markdown frontmatter and
then updates each conversion manifest, including its Markdown byte count and hash.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path


PAGE_PATTERN = re.compile(
    r'<!-- source-page: (\d+) -->\s*\n<a id="page-\d+"></a>\s*\n', re.MULTILINE)


def parse_markdown(payload: str) -> tuple[list[str], str, list[str]]:
    if not payload.startswith("---\n"):
        raise ValueError("Markdown file has no frontmatter")
    end = payload.find("\n---\n", 4)
    if end < 0:
        raise ValueError("Markdown frontmatter is not closed")
    frontmatter = payload[4:end].splitlines()
    body = payload[end + 5:]
    matches = list(PAGE_PATTERN.finditer(body))
    pages = []
    for index, match in enumerate(matches):
        finish = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        pages.append(body[match.end():finish].strip())
    return frontmatter, body, pages


def metrics(pages: list[str]) -> dict[str, int | float | bool]:
    text = "\n".join(pages)
    nonspace = sum(not character.isspace() for character in text)
    empty = sum(sum(not character.isspace() for character in page) < 30 for page in pages)
    lines = text.splitlines()
    return {
        "pages": len(pages),
        "characters": len(text),
        "nonspace_characters": nonspace,
        "lines": len(lines),
        "headings": sum(bool(re.match(r"^#{1,6}\s", line.lstrip())) for line in lines),
        "table_rows": sum(line.lstrip().startswith("|") for line in lines),
        "replacement_characters": text.count("\ufffd"),
        "empty_pages": empty,
        "empty_page_ratio": round(empty / len(pages), 4) if pages else 0.0,
        "nonspace_per_page": round(nonspace / len(pages), 1) if pages else 0.0,
        "low_text": nonspace < max(100, len(pages) * 40),
    }


def yaml_scalar(value: int | bool) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def update_frontmatter(lines: list[str], values: dict[str, int | bool]) -> tuple[list[str], bool]:
    replacements = {
        "source_pages": values["pages"],
        "quality_low_text": values["low_text"],
        "quality_empty_pages": values["empty_pages"],
    }
    found = set()
    changed = False
    output = []
    for line in lines:
        key, separator, _old = line.partition(":")
        key = key.strip()
        if separator and key in replacements:
            found.add(key)
            new = f"{key}: {yaml_scalar(replacements[key])}"
            changed = changed or new != line
            output.append(new)
        else:
            output.append(line)
    missing = replacements.keys() - found
    if missing:
        raise ValueError("missing canonical frontmatter keys: " + ", ".join(sorted(missing)))
    return output, changed


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def reconcile(corpus: Path, check_only: bool) -> tuple[int, int]:
    manifest_path = corpus / "conversion-manifest.csv"
    with manifest_path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(line.replace("\x00", "") for line in stream)
        fields = list(reader.fieldnames or [])
        rows = list(reader)

    drift = rewritten = 0
    for row in rows:
        if row.get("status") not in {"success", "low_text"}:
            continue
        path = corpus / (row["markdown_file"] or "").replace("\\", "/")
        original_bytes = path.read_bytes()
        payload = original_bytes.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
        frontmatter, body, pages = parse_markdown(payload)
        final = metrics(pages)
        updated_frontmatter, frontmatter_changed = update_frontmatter(frontmatter, final)
        new_payload = "---\n" + "\n".join(updated_frontmatter) + "\n---\n" + body
        encoded = new_payload.encode("utf-8")
        payload_changed = encoded != original_bytes

        updates = {key: final[key] for key in (
            "pages", "characters", "nonspace_characters", "lines",
            "replacement_characters", "empty_pages", "low_text")}
        for optional in ("headings", "table_rows", "empty_page_ratio", "nonspace_per_page"):
            if optional in fields:
                updates[optional] = final[optional]
        updates["status"] = "low_text" if final["low_text"] else "success"
        updates["markdown_bytes"] = len(encoded)
        updates["markdown_sha256"] = hashlib.sha256(encoded).hexdigest()

        row_drift = payload_changed
        for key, value in updates.items():
            rendered = str(value)
            if (row.get(key) or "") != rendered:
                row_drift = True
            row[key] = rendered
        if row_drift:
            drift += 1
            if not check_only:
                path.write_text(new_payload, encoding="utf-8", newline="\n")
                rewritten += int(payload_changed)

    if not check_only:
        write_csv(manifest_path, rows, fields)
        summary_path = corpus / "conversion-summary.json"
        if summary_path.is_file():
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            summary.update({
                "records": len(rows),
                "source_bytes": sum(int(row.get("source_bytes") or 0) for row in rows),
                "markdown_bytes": sum(int(row.get("markdown_bytes") or 0) for row in rows),
                "pages": sum(int(row.get("pages") or 0) for row in rows),
                "characters": sum(int(row.get("characters") or 0) for row in rows),
                "metric_basis": "final-page-text",
                "near_blank_page_definition": "fewer than 30 Unicode non-space characters",
            })
            statuses: dict[str, int] = {}
            for row in rows:
                statuses[row["status"]] = statuses.get(row["status"], 0) + 1
            summary["statuses"] = statuses
            summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    return drift, rewritten


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, action="append", required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    total_drift = total_rewritten = 0
    for corpus in args.corpus:
        drift, rewritten = reconcile(corpus.resolve(), args.check)
        total_drift += drift
        total_rewritten += rewritten
        print(f"{corpus}: {drift} rows drifted; {rewritten} Markdown files rewritten")
    if args.check and total_drift:
        print(f"FAIL: {total_drift} conversion rows do not describe the final page text")
        return 1
    print(f"PASS: final-text metrics reconciled across {len(args.corpus)} corpora")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
