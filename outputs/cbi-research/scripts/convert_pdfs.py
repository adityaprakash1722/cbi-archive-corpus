#!/usr/bin/env python3
"""Resumable, provenance-preserving PDF-to-Markdown conversion pipeline."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import os
import re
import shutil
import sys
import tempfile
import time
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, unquote, urlsplit


PIPELINE_VERSION = "0.1.0"


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
    parser.add_argument("--audit-csv", type=Path)
    parser.add_argument("--engine", choices=("pymupdf4llm", "markitdown"), default="pymupdf4llm")
    parser.add_argument("--ocr", action="store_true", help="Allow the selected engine to invoke OCR")
    parser.add_argument("--only-likely-ocr", action="store_true")
    parser.add_argument("--exclude-likely-ocr", action="store_true")
    parser.add_argument("--sha-file", type=Path, help="Optional newline-delimited SHA-256 allowlist")
    parser.add_argument(
        "--force-selected",
        action="store_true",
        help="Reconvert records in --sha-file even when a prior success exists",
    )
    parser.add_argument("--max-files", type=int, default=0)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--progress-every", type=int, default=25)
    return parser.parse_args()


def atomic_text_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def output_path(root: Path, sha256: str) -> Path:
    return root / "markdown" / sha256[:2] / sha256[2:4] / f"{sha256}.md"


def yaml_scalar(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def text_metrics(pages: list[str]) -> dict[str, int | float | bool]:
    text = "\n".join(pages)
    lines = text.splitlines()
    nonspace = len(re.sub(r"\s+", "", text))
    page_nonspace = [len(re.sub(r"\s+", "", page)) for page in pages]
    empty_pages = sum(count < 30 for count in page_nonspace)
    return {
        "characters": len(text),
        "nonspace_characters": nonspace,
        "lines": len(lines),
        "headings": sum(bool(re.match(r"^#{1,6}\s", line.lstrip())) for line in lines),
        "table_rows": sum(line.lstrip().startswith("|") for line in lines),
        "replacement_characters": text.count("\ufffd"),
        "empty_pages": empty_pages,
        "low_text": nonspace < max(100, len(pages) * 40),
        # Structural success is not extraction fidelity. A document can hold
        # sequential page markers and correct hashes while most of its pages are
        # blank. qa_extraction_quality.py grades on these two fields.
        "empty_page_ratio": round(empty_pages / len(pages), 4) if pages else 0.0,
        "nonspace_per_page": round(nonspace / len(pages), 1) if pages else 0.0,
    }


def markdown_document(
    record: dict,
    pages: list[str],
    engine: str,
    engine_version: str,
    metrics: dict,
    detected_format: str,
) -> str:
    frontmatter = {
        "document_id": f"cbi:{record['sha256']}",
        "source_url": record["url"],
        "source_urls": record.get("source_urls", [record["url"]]),
        "source_alias_count": len(record.get("source_urls", [record["url"]])),
        "source_file": record["localPath"],
        "source_sha256": record["sha256"],
        "source_bytes": record.get("downloadedBytes"),
        "source_pages": len(pages),
        "extraction_engine": engine,
        "extraction_engine_version": engine_version,
        "extraction_pipeline_version": PIPELINE_VERSION,
        "detected_source_format": detected_format,
        "ocr_enabled": bool(record.get("ocr")),
        "quality_low_text": bool(metrics["low_text"]),
        "quality_empty_pages": int(metrics["empty_pages"]),
    }
    rendered = ["---"]
    rendered.extend(f"{key}: {yaml_scalar(value)}" for key, value in frontmatter.items())
    rendered.extend(["---", ""])
    for page_number, page in enumerate(pages, 1):
        rendered.extend([
            f"<!-- source-page: {page_number} -->",
            f'<a id="page-{page_number}"></a>',
            "",
            page.strip(),
            "",
        ])
    return "\n".join(rendered).rstrip() + "\n"


def convert_with_pymupdf(source: Path, use_ocr: bool) -> tuple[list[str], str, str]:
    import pymupdf4llm

    chunks = pymupdf4llm.to_markdown(
        str(source),
        page_chunks=True,
        use_ocr=use_ocr,
        header=False,
        footer=False,
        show_progress=False,
    )
    if not isinstance(chunks, list):
        raise TypeError(f"Expected page chunks, received {type(chunks).__name__}")
    pages = [str(chunk.get("text") or "") for chunk in chunks]
    return pages, str(getattr(pymupdf4llm, "__version__", "unknown")), "pdf"


def convert_with_markitdown(source: Path) -> tuple[list[str], str, str]:
    from markitdown import MarkItDown

    conversion_source = source
    detected_format = "pdf"
    temporary_name: str | None = None
    legacy_text: str | None = None
    if zipfile.is_zipfile(source):
        with zipfile.ZipFile(source) as archive:
            if "word/document.xml" in archive.namelist():
                detected_format = "docx_mislabeled_as_pdf"
                with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as temporary:
                    temporary_name = temporary.name
                shutil.copyfile(source, temporary_name)
                conversion_source = Path(temporary_name)
    if source.read_bytes()[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        import olefile

        with olefile.OleFileIO(source) as ole:
            if ole.exists("WordDocument"):
                detected_format = "legacy_doc_mislabeled_as_pdf"
                stream = ole.openstream("WordDocument").read()
                candidates = []
                for raw in re.findall(rb"[\x09\x0a\x0d\x20-\xff]{20,}", stream):
                    decoded = raw.decode("cp1252", errors="ignore").strip()
                    ascii_ratio = sum(character in "\t\r\n" or 32 <= ord(character) < 127 for character in decoded) / max(len(decoded), 1)
                    if ascii_ratio >= 0.9 and sum(character.isalpha() for character in decoded) >= 10:
                        candidates.append(decoded)
                if candidates:
                    # Previously: max(candidates, key=len), which kept the single
                    # longest printable run and discarded every other fragment of
                    # the document. Keep them all, in stream order.
                    # For a full-fidelity conversion prefer convert_office.convert_doc,
                    # which routes the file through LibreOffice.
                    legacy_text = "\n\n".join(candidates)
    try:
        if legacy_text is not None:
            text = legacy_text
        else:
            text = MarkItDown(enable_plugins=False).convert(str(conversion_source)).text_content
    finally:
        if temporary_name:
            Path(temporary_name).unlink(missing_ok=True)
    pages = re.split(r"\f", text)
    if len(pages) > 1 and not pages[-1].strip():
        pages.pop()
    return pages, importlib.metadata.version("markitdown"), detected_format


def convert_one(task: dict) -> dict:
    started = time.monotonic()
    archive = Path(task["archive"])
    root = Path(task["output"])
    record = dict(task["record"])
    record["ocr"] = bool(task["ocr"])
    source = archive / record["localPath"].replace("\\", "/")  # manifest paths are written on Windows
    destination = output_path(root, record["sha256"])
    result = {
        "url": record["url"],
        "source_urls": record.get("source_urls", [record["url"]]),
        "alias_count": len(record.get("source_urls", [record["url"]])),
        "source_file": record["localPath"],
        "source_sha256": record["sha256"],
        "source_bytes": record.get("downloadedBytes"),
        "markdown_file": str(destination.relative_to(root)),
        "engine": task["engine"],
        "ocr": bool(task["ocr"]),
        "status": "success",
        "error": None,
    }
    try:
        if task["engine"] == "pymupdf4llm":
            pages, engine_version, detected_format = convert_with_pymupdf(source, bool(task["ocr"]))
        else:
            pages, engine_version, detected_format = convert_with_markitdown(source)
        metrics = text_metrics(pages)
        document = markdown_document(record, pages, task["engine"], engine_version, metrics, detected_format)
        atomic_text_write(destination, document)
        result.update(metrics)
        result.update({
            "engine_version": engine_version,
            "detected_format": detected_format,
            "pages": len(pages),
            "markdown_bytes": destination.stat().st_size,
            "markdown_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
            "status": "low_text" if metrics["low_text"] else "success",
        })
    except Exception as exc:
        result["status"] = "error"
        result["error"] = f"{type(exc).__name__}: {exc}"[:2000]
    result["seconds"] = round(time.monotonic() - started, 4)
    return result


def load_audit(path: Path | None) -> dict[str, dict]:
    if not path:
        return {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return {row["sha256"]: row for row in csv.DictReader(stream)}


def load_journal(path: Path, root: Path) -> dict[str, dict]:
    completed: dict[str, dict] = {}
    if not path.exists():
        return completed
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        destination = root / row.get("markdown_file", "")
        if row.get("status") in {"success", "low_text"} and destination.is_file():
            completed[row["source_sha256"]] = row
        elif row.get("status") == "error":
            completed[row["source_sha256"]] = row
    return completed


def write_manifest(root: Path, rows: list[dict]) -> None:
    fields = [
        "url", "source_urls", "alias_count", "source_file", "source_sha256", "source_bytes", "markdown_file",
        "markdown_bytes", "markdown_sha256", "engine", "engine_version", "detected_format", "ocr", "pages",
        "characters", "nonspace_characters", "lines", "headings", "table_rows",
        "replacement_characters", "empty_pages", "empty_page_ratio", "nonspace_per_page",
        "low_text", "status", "error", "seconds",
    ]
    root.mkdir(parents=True, exist_ok=True)
    with (root / "conversion-manifest.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in sorted(rows, key=lambda row: row["url"]):
            rendered = dict(row)
            rendered["source_urls"] = " | ".join(row.get("source_urls") or [row["url"]])
            writer.writerow(rendered)
    summary = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "pipeline_version": PIPELINE_VERSION,
        "records": len(rows),
        "statuses": {},
        "source_bytes": sum(int(row.get("source_bytes") or 0) for row in rows),
        "markdown_bytes": sum(int(row.get("markdown_bytes") or 0) for row in rows),
        "pages": sum(int(row.get("pages") or 0) for row in rows),
        "characters": sum(int(row.get("characters") or 0) for row in rows),
    }
    for row in rows:
        summary["statuses"][row["status"]] = summary["statuses"].get(row["status"], 0) + 1
    atomic_text_write(root / "conversion-summary.json", json.dumps(summary, indent=2) + "\n")


def main() -> int:
    args = arguments()
    if args.only_likely_ocr and args.exclude_likely_ocr:
        raise ValueError("--only-likely-ocr and --exclude-likely-ocr are mutually exclusive")
    if args.force_selected and not args.sha_file:
        raise ValueError("--force-selected requires --sha-file to prevent an unbounded corpus rewrite")
    archive = args.archive.resolve()
    root = args.output.resolve()
    state = json.loads((archive / "archive-state.json").read_text(encoding="utf-8"))
    url_records = [
        record for record in state["files"].values()
        if record.get("status") == "downloaded" and str(record.get("format", "")).upper() == "PDF"
    ]
    url_records.sort(key=lambda record: record["url"])
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
    all_record_shas = set(grouped)
    records = list(grouped.values())
    audit = load_audit(args.audit_csv.resolve() if args.audit_csv else None)
    if args.only_likely_ocr:
        records = [record for record in records if str(audit.get(record["sha256"], {}).get("suspected_image_only", "")).lower() == "true"]
    if args.exclude_likely_ocr:
        records = [record for record in records if str(audit.get(record["sha256"], {}).get("suspected_image_only", "")).lower() != "true"]
    if args.sha_file:
        allowed = {line.strip().lower() for line in args.sha_file.read_text(encoding="utf-8").splitlines() if line.strip()}
        records = [record for record in records if record["sha256"].lower() in allowed]
    records.sort(key=lambda record: record["url"])
    if args.max_files:
        records = records[: args.max_files]

    root.mkdir(parents=True, exist_ok=True)
    journal_path = root / "conversion-journal.jsonl"
    completed = load_journal(journal_path, root)
    pending = [
        record for record in records
        if args.force_selected
        or record["sha256"] not in completed
        or completed[record["sha256"]].get("status") == "error"
    ]
    print(f"Selected PDFs: {len(records)}; completed: {len(records) - len(pending)}; pending: {len(pending)}", flush=True)
    tasks = [
        {"archive": str(archive), "output": str(root), "record": record, "engine": args.engine, "ocr": args.ocr}
        for record in pending
    ]
    started = time.monotonic()
    with journal_path.open("a", encoding="utf-8") as journal:
        if args.workers == 1:
            iterator = ((index, convert_one(task)) for index, task in enumerate(tasks, 1))
            for index, result in iterator:
                journal.write(json.dumps(result, ensure_ascii=False) + "\n")
                journal.flush()
                completed[result["source_sha256"]] = result
                if index % args.progress_every == 0 or index == len(tasks):
                    rate = index / max(time.monotonic() - started, 0.001)
                    print(f"Converted {index}/{len(tasks)} ({rate:.2f} files/s); latest={result['status']}", flush=True)
        else:
            with ProcessPoolExecutor(max_workers=args.workers) as pool:
                future_map = {pool.submit(convert_one, task): index for index, task in enumerate(tasks, 1)}
                finished = 0
                for future in as_completed(future_map):
                    result = future.result()
                    finished += 1
                    journal.write(json.dumps(result, ensure_ascii=False) + "\n")
                    journal.flush()
                    completed[result["source_sha256"]] = result
                    if finished % args.progress_every == 0 or finished == len(tasks):
                        rate = finished / max(time.monotonic() - started, 0.001)
                        print(f"Converted {finished}/{len(tasks)} ({rate:.2f} files/s); latest={result['status']}", flush=True)

    rows = [row for sha256, row in completed.items() if sha256 in all_record_shas]
    write_manifest(root, rows)
    print(f"Wrote {root / 'conversion-summary.json'}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
