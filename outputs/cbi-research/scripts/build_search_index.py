#!/usr/bin/env python3
"""Build a page-addressable SQLite FTS5 index from the normalized Markdown corpus."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

from classify_provenance import classify


PAGE_PATTERN = re.compile(
    r"<!-- source-page: (\d+) -->\s*\n<a id=\"page-\d+\"></a>\s*\n",
    re.MULTILINE,
)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, action="append", required=True,
                        help="corpus directory containing conversion-manifest.csv; repeatable")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--database-name", default="cbi-corpus.sqlite",
                        help="SQLite filename written inside --output")
    parser.add_argument("--audit-csv", type=Path)
    parser.add_argument("--progress-every", type=int, default=250)
    return parser.parse_args()


def parse_frontmatter(markdown: str) -> tuple[dict, str]:
    if not markdown.startswith("---\n"):
        raise ValueError("Markdown file has no frontmatter")
    end = markdown.find("\n---\n", 4)
    if end == -1:
        raise ValueError("Markdown frontmatter is not closed")
    metadata: dict = {}
    for line in markdown[4:end].splitlines():
        key, separator, value = line.partition(":")
        if not separator:
            continue
        metadata[key.strip()] = json.loads(value.strip())
    return metadata, markdown[end + 5 :]


def split_pages(body: str) -> list[tuple[int, str]]:
    matches = list(PAGE_PATTERN.finditer(body))
    pages: list[tuple[int, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        pages.append((int(match.group(1)), body[match.end() : end].strip()))
    return pages


def clean_title(text: str) -> str | None:
    for line in text.splitlines():
        if not re.match(r"^#{1,6}\s+", line):
            continue
        title = re.sub(r"^#{1,6}\s+", "", line)
        title = re.sub(r"[*_`#<>]", "", title).strip()
        if title:
            return title[:500]
    return None


def title_from_url(url: str) -> str | None:
    name = Path(unquote(urlparse(url).path)).stem
    title = re.sub(r"[-_]+", " ", name)
    title = re.sub(r"\s+", " ", title).strip()
    return title[:500] or None


def initialize(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        PRAGMA journal_mode=WAL;
        PRAGMA synchronous=NORMAL;
        PRAGMA temp_store=MEMORY;
        DROP TABLE IF EXISTS pages_fts;
        DROP TABLE IF EXISTS pages;
        DROP TABLE IF EXISTS documents;
        CREATE TABLE documents (
          document_id TEXT PRIMARY KEY,
          source_sha256 TEXT NOT NULL UNIQUE,
          source_url TEXT NOT NULL,
          source_urls_json TEXT NOT NULL,
          source_alias_count INTEGER NOT NULL,
          source_file TEXT NOT NULL,
          source_bytes INTEGER,
          markdown_file TEXT NOT NULL,
          markdown_sha256 TEXT,
          title TEXT,
          pdf_title TEXT,
          pdf_author TEXT,
          pdf_creator TEXT,
          pdf_creation_date TEXT,
          document_class TEXT NOT NULL,
          authorship TEXT NOT NULL,
          classification_basis TEXT NOT NULL,
          classification_confidence TEXT NOT NULL,
          page_basis TEXT NOT NULL,
          source_format TEXT,
          consultation_id TEXT,
          page_count INTEGER NOT NULL,
          extraction_engine TEXT NOT NULL,
          extraction_engine_version TEXT,
          ocr_enabled INTEGER NOT NULL,
          quality_low_text INTEGER NOT NULL,
          quality_empty_pages INTEGER NOT NULL
        );
        CREATE TABLE pages (
          document_id TEXT NOT NULL REFERENCES documents(document_id),
          page_number INTEGER NOT NULL,
          text TEXT NOT NULL,
          characters INTEGER NOT NULL,
          PRIMARY KEY (document_id, page_number)
        );
        CREATE VIRTUAL TABLE pages_fts USING fts5(
          document_id UNINDEXED,
          page_number UNINDEXED,
          title,
          text,
          tokenize='unicode61 remove_diacritics 2'
        );
        CREATE INDEX pages_document_id ON pages(document_id);
        CREATE INDEX documents_authorship ON documents(authorship);
        CREATE INDEX documents_class ON documents(document_class);
        """
    )


def main() -> int:
    args = arguments()
    corpus = [c.resolve() for c in args.corpus]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if Path(args.database_name).name != args.database_name or not args.database_name.endswith(".sqlite"):
        raise ValueError("--database-name must be a .sqlite filename, not a path")
    manifest = []
    seen_shas: set[str] = set()
    for corpus_root in corpus:
        with (corpus_root / "conversion-manifest.csv").open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                if row["status"] not in {"success", "low_text"}:
                    continue
                if row["source_sha256"] in seen_shas:
                    print(f"skipping duplicate SHA across corpora: {row['source_sha256']}", flush=True)
                    continue
                seen_shas.add(row["source_sha256"])
                row["_root"] = corpus_root
                manifest.append(row)
    print(f"manifest rows across {len(corpus)} corpora: {len(manifest)}", flush=True)
    audit: dict[str, dict] = {}
    if args.audit_csv:
        # Some PDF metadata fields carry embedded NUL bytes, which csv refuses to
        # parse. They are meaningless here, so strip them on the way in.
        with args.audit_csv.resolve().open(encoding="utf-8-sig", newline="") as stream:
            cleaned = (line.replace("\x00", "") for line in stream)
            audit = {row["sha256"]: row for row in csv.DictReader(cleaned)}

    database_path = output / args.database_name
    connection = sqlite3.connect(database_path)
    initialize(connection)
    started = time.monotonic()
    indexed_documents = 0
    indexed_pages = 0
    failures: list[dict] = []
    document_classes: dict[str, int] = {}
    authorship_counts: dict[str, int] = {}
    confidence_counts: dict[str, int] = {}
    try:
        for index, row in enumerate(manifest, 1):
            markdown_path = row["_root"] / row["markdown_file"].replace("\\", "/")  # manifests written on Windows carry backslashes
            try:
                markdown = markdown_path.read_text(encoding="utf-8")
                metadata, body = parse_frontmatter(markdown)
                pages = split_pages(body)
                expected_pages = int(row.get("pages") or metadata.get("source_pages") or 0)
                if len(pages) != expected_pages:
                    raise ValueError(f"page marker mismatch: expected {expected_pages}, found {len(pages)}")
                document_id = metadata["document_id"]
                audit_row = audit.get(metadata["source_sha256"], {})
                pdf_title = audit_row.get("title") or None
                heading_title = clean_title(body)
                if heading_title and heading_title.casefold() in {"contents", "table of contents", "introduction"}:
                    heading_title = None
                title = pdf_title or heading_title or title_from_url(metadata["source_url"])
                source_urls = metadata.get("source_urls") or [metadata["source_url"]]
                opening = "\n".join(text for _number, text in pages[:2])[:20000]
                provenance = classify(metadata["source_url"], opening)
                document_class = provenance.document_class
                consultation_id = provenance.consultation_id
                connection.execute(
                    """
                    INSERT INTO documents (
                      document_id, source_sha256, source_url, source_urls_json,
                      source_alias_count, source_file, source_bytes, markdown_file,
                      markdown_sha256, title, pdf_title, pdf_author, pdf_creator,
                      pdf_creation_date, document_class, authorship,
                      classification_basis, classification_confidence, page_basis,
                      source_format, consultation_id,
                      page_count, extraction_engine,
                      extraction_engine_version, ocr_enabled, quality_low_text,
                      quality_empty_pages
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        document_id,
                        metadata["source_sha256"],
                        metadata["source_url"],
                        json.dumps(source_urls, ensure_ascii=False),
                        len(source_urls),
                        metadata["source_file"],
                        metadata.get("source_bytes"),
                        row["markdown_file"],
                        row.get("markdown_sha256"),
                        title,
                        pdf_title,
                        audit_row.get("author") or None,
                        audit_row.get("creator") or None,
                        audit_row.get("creation_date") or None,
                        document_class,
                        provenance.authorship,
                        provenance.basis,
                        provenance.confidence,
                        metadata.get("page_basis") or "source-page",
                        metadata.get("detected_source_format") or "pdf",
                        consultation_id,
                        len(pages),
                        metadata["extraction_engine"],
                        metadata.get("extraction_engine_version"),
                        int(bool(metadata.get("ocr_enabled"))),
                        int(bool(metadata.get("quality_low_text"))),
                        int(metadata.get("quality_empty_pages") or 0),
                    ),
                )
                for page_number, text in pages:
                    connection.execute(
                        "INSERT INTO pages VALUES (?, ?, ?, ?)",
                        (document_id, page_number, text, len(text)),
                    )
                    connection.execute(
                        "INSERT INTO pages_fts VALUES (?, ?, ?, ?)",
                        (document_id, page_number, title or "", text),
                    )
                indexed_documents += 1
                indexed_pages += len(pages)
            except Exception as exc:
                failures.append({
                    "source_sha256": row.get("source_sha256"),
                    "markdown_file": row.get("markdown_file"),
                    "error": f"{type(exc).__name__}: {exc}"[:2000],
                })
            if index % args.progress_every == 0:
                connection.commit()
                print(f"Indexed {index}/{len(manifest)} manifest records; pages={indexed_pages}; failures={len(failures)}", flush=True)
        connection.commit()
        connection.execute("PRAGMA optimize")
        connection.commit()
        authorship_counts = {
            row[0]: row[1]
            for row in connection.execute(
                "SELECT authorship, COUNT(*) FROM documents GROUP BY authorship ORDER BY COUNT(*) DESC"
            ).fetchall()
        }
        confidence_counts = {
            row[0]: row[1]
            for row in connection.execute(
                "SELECT classification_confidence, COUNT(*) FROM documents GROUP BY classification_confidence"
            ).fetchall()
        }
        document_classes = {
            row[0]: row[1]
            for row in connection.execute(
                "SELECT document_class, COUNT(*) FROM documents GROUP BY document_class ORDER BY COUNT(*) DESC"
            ).fetchall()
        }
        # Leave a single quiescent, portable SQLite artifact. WAL is useful while
        # ingesting, but a copied database must not depend on unshipped sidecars.
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.commit()
    finally:
        connection.close()

    summary = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "manifest_records": len(manifest),
        "indexed_documents": indexed_documents,
        "indexed_pages": indexed_pages,
        "authorship": authorship_counts,
        "classification_confidence": confidence_counts,
        "document_classes": document_classes,
        "failures": len(failures),
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "database_bytes": database_path.stat().st_size,
        "database_file": database_path.name,
    }
    (output / "index-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (output / "index-failures.json").write_text(json.dumps(failures, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
