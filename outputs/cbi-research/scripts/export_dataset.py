#!/usr/bin/env python3
"""Export the corpus to Parquet for portable, cross-machine access.

Why Parquet
-----------
The SQLite index is 663 MB and is a build artifact: it rebuilds from the
Markdown corpus in about eight seconds. Syncing it between machines is paying
to move something you can regenerate. Parquet is different:

  * it is columnar, so a query that touches three columns reads only those
  * DuckDB can query it over plain HTTPS without downloading the file, so a
    machine with no local copy can still search the whole corpus
  * the Hugging Face dataset viewer renders it natively
  * `datasets.load_dataset()` streams it in one line

Two tables are written:

  documents.parquet   one row per logical document, 5,568 rows
  pages.parquet       one row per source page, carrying the text

The split matters. Most questions ("how many stakeholder submissions mention
outsourcing") need only the small table plus a join, and never touch the 170 MB
of page text.
"""
from __future__ import annotations

import argparse, json, sqlite3, time
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

DOC_COLUMNS = [
    "document_id", "source_sha256", "source_url", "source_alias_count",
    "source_bytes", "title", "pdf_author", "pdf_creation_date",
    "published_at", "published_at_basis", "analysis_year", "analysis_year_basis",
    "retrieved_at", "source_page_url", "source_last_modified_at",
    "document_class", "authorship", "classification_basis",
    "classification_confidence", "page_basis", "source_format",
    "consultation_id", "engagement_id", "page_count", "extraction_engine", "ocr_enabled",
    "quality_low_text", "quality_empty_pages", "extraction_selection_basis",
    "alternate_extraction_count", "content_sha256", "content_cluster_id",
    "content_cluster_size",
]

PAGE_SCHEMA = pa.schema([
    ("document_id", pa.string()), ("source_sha256", pa.string()),
    ("page_number", pa.int32()), ("authorship", pa.string()),
    ("authorship_basis", pa.string()),
    ("document_class", pa.string()), ("page_basis", pa.string()),
    ("consultation_id", pa.string()), ("engagement_id", pa.string()),
    ("title", pa.string()),
    ("source_url", pa.string()), ("characters", pa.int32()),
    ("text", pa.string()),
])


def existing_columns(connection: sqlite3.Connection) -> list[str]:
    have = {row[1] for row in connection.execute("PRAGMA table_info(documents)")}
    missing = [c for c in DOC_COLUMNS if c not in have]
    if missing:
        print(f"  note: index lacks columns {missing}; they are omitted", flush=True)
    return [c for c in DOC_COLUMNS if c in have]


def write_documents(connection: sqlite3.Connection, out: Path) -> int:
    columns = existing_columns(connection)
    rows = connection.execute(f"SELECT {', '.join(columns)} FROM documents ORDER BY source_sha256").fetchall()
    table = pa.table({c: pa.array([r[i] for r in rows]) for i, c in enumerate(columns)})
    pq.write_table(table, out, compression="zstd", compression_level=9)
    return len(rows)


def write_pages(connection: sqlite3.Connection, out: Path, batch: int = 4000) -> int:
    writer = None
    total = 0
    query = """
        SELECT p.document_id, d.source_sha256, p.page_number, p.authorship,
               p.authorship_basis, d.document_class, d.page_basis, d.consultation_id,
               d.engagement_id, d.title,
               d.source_url, p.characters, p.text
        FROM pages AS p JOIN documents AS d USING(document_id)
        ORDER BY d.source_sha256, p.page_number
    """
    cursor = connection.execute(query)
    try:
        while True:
            chunk = cursor.fetchmany(batch)
            if not chunk:
                break
            columns = list(zip(*chunk))
            table = pa.table(
                {name: pa.array(columns[i], type=PAGE_SCHEMA.field(i).type)
                 for i, name in enumerate(PAGE_SCHEMA.names)},
                schema=PAGE_SCHEMA,
            )
            if writer is None:
                writer = pq.ParquetWriter(out, PAGE_SCHEMA, compression="zstd", compression_level=9)
            writer.write_table(table)
            total += len(chunk)
            if total % 20000 == 0:
                print(f"  pages {total}", flush=True)
    finally:
        if writer is not None:
            writer.close()
    return total


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    started = time.time()
    connection = sqlite3.connect(f"file:{args.database.resolve()}?mode=ro", uri=True)

    documents = write_documents(connection, args.output / "documents.parquet")
    print(f"  documents.parquet  {documents} rows", flush=True)
    pages = write_pages(connection, args.output / "pages.parquet")
    print(f"  pages.parquet      {pages} rows", flush=True)

    summary = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_index": args.database.name,
        "documents": documents,
        "pages": pages,
        "documents_parquet_bytes": (args.output / "documents.parquet").stat().st_size,
        "pages_parquet_bytes": (args.output / "pages.parquet").stat().st_size,
        "elapsed_seconds": round(time.time() - started, 1),
    }
    (args.output / "dataset-summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
