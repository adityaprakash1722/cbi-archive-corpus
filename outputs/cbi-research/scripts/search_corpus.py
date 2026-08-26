#!/usr/bin/env python3
"""Search the page-level corpus index and return citation-ready results."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("query", help="SQLite FTS5 query")
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = arguments()
    connection = sqlite3.connect(args.database.resolve())
    connection.row_factory = sqlite3.Row
    try:
        try:
            rows = connection.execute(
                """
                SELECT
                  d.document_id,
                  d.source_sha256,
                  d.title,
                  d.source_url,
                  d.markdown_file,
                  d.ocr_enabled,
                  p.page_number,
                  bm25(pages_fts, 0.0, 0.0, 1.0, 1.0) AS rank,
                  snippet(pages_fts, 3, '[', ']', ' ... ', 36) AS snippet
                FROM pages_fts AS p
                JOIN documents AS d USING (document_id)
                WHERE pages_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (args.query, args.limit),
            ).fetchall()
        except sqlite3.OperationalError as exc:
            print(
                f"Invalid FTS5 query: {exc}. Put hyphenated terms and exact phrases in double quotes.",
                file=sys.stderr,
            )
            return 2
    finally:
        connection.close()

    results = [dict(row) for row in rows]
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for index, row in enumerate(results, 1):
            ocr_label = " [OCR]" if row["ocr_enabled"] else ""
            print(f"{index}. {row['title'] or '(untitled)'} - page {row['page_number']}{ocr_label}")
            print(f"   {row['source_url']}")
            print(f"   {row['snippet'].replace(chr(10), ' ')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
