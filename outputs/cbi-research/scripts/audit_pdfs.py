#!/usr/bin/env python3
"""Resumable structural audit of the downloaded Central Bank PDF corpus."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit

from pypdf import PdfReader


def url_key(url: str) -> tuple[str, str, tuple[tuple[str, str], ...]]:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").casefold().removeprefix("www.")
    return host, unquote(parsed.path).casefold(), tuple(sorted(parse_qsl(parsed.query)))


def nested_document_key(url: str) -> tuple[str, str, tuple[tuple[str, str], ...]] | None:
    parsed = urlsplit(url)
    decoded_path = unquote(parsed.path)
    start = decoded_path.casefold().find("/docs/default-source/")
    if start <= 0:
        return None
    return "centralbank.ie", decoded_path[start:].casefold(), tuple(sorted(parse_qsl(parsed.query)))


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-files", type=int, default=0)
    parser.add_argument("--progress-every", type=int, default=50)
    return parser.parse_args()


def sampled_page_numbers(page_count: int) -> list[int]:
    if page_count <= 0:
        return []
    candidates = [0, page_count // 4, page_count // 2, (3 * page_count) // 4, page_count - 1]
    return sorted(set(min(page_count - 1, max(0, number)) for number in candidates))


def safe_metadata(reader: PdfReader) -> dict[str, str | None]:
    try:
        metadata = reader.metadata or {}
        return {
            "title": str(metadata.get("/Title") or "") or None,
            "author": str(metadata.get("/Author") or "") or None,
            "creator": str(metadata.get("/Creator") or "") or None,
            "producer": str(metadata.get("/Producer") or "") or None,
            "creation_date": str(metadata.get("/CreationDate") or "") or None,
        }
    except Exception:
        return {"title": None, "author": None, "creator": None, "producer": None, "creation_date": None}


def inspect_pdf(archive: Path, record: dict) -> dict:
    started = time.monotonic()
    local_path = archive / record["localPath"].replace("\\", "/")  # manifest paths are written on Windows
    result = {
        "url": record["url"],
        "source_urls": record.get("source_urls", [record["url"]]),
        "alias_count": len(record.get("source_urls", [record["url"]])),
        "localPath": record["localPath"],
        "sha256": record.get("sha256"),
        "bytes": record.get("downloadedBytes") or local_path.stat().st_size,
        "page_count": None,
        "sample_pages": [],
        "sampled_chars": 0,
        "sampled_nonspace_chars": 0,
        "empty_sample_pages": 0,
        "encrypted": False,
        "suspected_image_only": False,
        "status": "ok",
        "error": None,
        "seconds": None,
    }
    try:
        reader = PdfReader(local_path, strict=False)
        result["encrypted"] = bool(reader.is_encrypted)
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:
                result["status"] = "encrypted"
                return result
        page_count = len(reader.pages)
        result["page_count"] = page_count
        result.update(safe_metadata(reader))
        pages = sampled_page_numbers(page_count)
        result["sample_pages"] = [number + 1 for number in pages]
        characters = 0
        nonspace = 0
        empty = 0
        for number in pages:
            try:
                text = reader.pages[number].extract_text() or ""
            except Exception:
                text = ""
            characters += len(text)
            compact = "".join(text.split())
            nonspace += len(compact)
            if len(compact) < 30:
                empty += 1
        result["sampled_chars"] = characters
        result["sampled_nonspace_chars"] = nonspace
        result["empty_sample_pages"] = empty
        result["suspected_image_only"] = bool(pages) and empty == len(pages)
        if page_count == 0:
            result["status"] = "zero_pages"
        elif result["suspected_image_only"]:
            result["status"] = "likely_ocr"
    except Exception as exc:
        result["status"] = "error"
        result["error"] = f"{type(exc).__name__}: {exc}"[:1000]
    finally:
        result["seconds"] = round(time.monotonic() - started, 4)
    return result


def percentile(values: list[int], fraction: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = round((len(ordered) - 1) * fraction)
    return ordered[index]


def write_outputs(output: Path, rows: list[dict], elapsed: float) -> None:
    output.mkdir(parents=True, exist_ok=True)
    fields = [
        "url", "source_urls", "alias_count", "localPath", "sha256", "bytes", "page_count", "sample_pages",
        "sampled_chars", "sampled_nonspace_chars", "empty_sample_pages", "encrypted",
        "suspected_image_only", "status", "error", "title", "author", "creator",
        "producer", "creation_date", "seconds",
    ]
    with (output / "pdf-audit.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in sorted(rows, key=lambda item: item["url"]):
            rendered = dict(row)
            rendered["sample_pages"] = " | ".join(map(str, row.get("sample_pages") or []))
            rendered["source_urls"] = " | ".join(row.get("source_urls") or [row["url"]])
            writer.writerow(rendered)

    page_counts = [int(row["page_count"]) for row in rows if isinstance(row.get("page_count"), int)]
    byte_counts = [int(row["bytes"]) for row in rows if row.get("bytes")]
    summary = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "audited_files": len(rows),
        "status_counts": dict(sorted(Counter(row["status"] for row in rows).items())),
        "suspected_image_only": sum(bool(row.get("suspected_image_only")) for row in rows),
        "encrypted": sum(bool(row.get("encrypted")) for row in rows),
        "total_pages": sum(page_counts),
        "pages": {
            "median": statistics.median(page_counts) if page_counts else 0,
            "p90": percentile(page_counts, 0.9),
            "p99": percentile(page_counts, 0.99),
            "maximum": max(page_counts, default=0),
        },
        "total_bytes": sum(byte_counts),
        "bytes": {
            "median": statistics.median(byte_counts) if byte_counts else 0,
            "p90": percentile(byte_counts, 0.9),
            "p99": percentile(byte_counts, 0.99),
            "maximum": max(byte_counts, default=0),
        },
        "audit_elapsed_seconds": round(elapsed, 2),
    }
    (output / "pdf-audit-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = arguments()
    archive = args.archive.resolve()
    output = args.output.resolve()
    state = json.loads((archive / "archive-state.json").read_text(encoding="utf-8"))
    url_records = [
        record for record in state["files"].values()
        if record.get("status") == "downloaded" and str(record.get("format", "")).upper() == "PDF"
    ]
    url_records.sort(key=lambda item: item["url"])
    records_by_url = {url_key(record["url"]): record for record in url_records}
    reconciled_aliases: dict[str, list[str]] = {}
    retained_url_records = []
    for record in url_records:
        target = records_by_url.get(nested_document_key(record["url"]))
        if target and target["sha256"] != record["sha256"]:
            reconciled_aliases.setdefault(target["sha256"], []).append(record["url"])
            continue
        retained_url_records.append(record)
    grouped: dict[str, dict] = {}
    for record in retained_url_records:
        sha256 = record["sha256"]
        if sha256 not in grouped:
            grouped[sha256] = {**record, "source_urls": [], "source_files": []}
        grouped[sha256]["source_urls"].append(record["url"])
        grouped[sha256]["source_files"].append(record["localPath"])
    for sha256, aliases in reconciled_aliases.items():
        if sha256 in grouped:
            grouped[sha256]["source_urls"].extend(aliases)
    records = list(grouped.values())
    if args.max_files:
        records = records[: args.max_files]

    output.mkdir(parents=True, exist_ok=True)
    journal_path = output / "pdf-audit.jsonl"
    completed: dict[str, dict] = {}
    if journal_path.exists():
        for line in journal_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            completed[row["sha256"]] = row

    started = time.monotonic()
    pending = [record for record in records if record.get("sha256") not in completed]
    print(f"PDF records: {len(records)}; already audited: {len(records) - len(pending)}; pending: {len(pending)}", flush=True)
    with journal_path.open("a", encoding="utf-8") as journal:
        for index, record in enumerate(pending, 1):
            row = inspect_pdf(archive, record)
            journal.write(json.dumps(row, ensure_ascii=False) + "\n")
            journal.flush()
            completed[row["sha256"]] = row
            if index % args.progress_every == 0 or index == len(pending):
                rate = index / max(time.monotonic() - started, 0.001)
                print(
                    f"Audited {index}/{len(pending)} pending ({rate:.2f} files/s); "
                    f"latest={row['status']} pages={row['page_count']}",
                    flush=True,
                )

    rows = []
    for record in records:
        if record.get("sha256") not in completed:
            continue
        row = dict(completed[record["sha256"]])
        row["url"] = record["url"]
        row["source_urls"] = record["source_urls"]
        row["alias_count"] = len(record["source_urls"])
        rows.append(row)
    write_outputs(output, rows, time.monotonic() - started)
    print(f"Wrote {output / 'pdf-audit-summary.json'}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
