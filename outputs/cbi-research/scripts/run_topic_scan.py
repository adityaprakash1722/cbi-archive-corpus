#!/usr/bin/env python3
"""Run a transparent first-pass topic scan over the page-level FTS index."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
import time
from pathlib import Path


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--top-documents", type=int, default=10)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    queries = json.loads(args.queries.read_text(encoding="utf-8"))
    connection = sqlite3.connect(args.database.resolve())
    connection.row_factory = sqlite3.Row
    results: list[dict] = []
    started = time.monotonic()
    try:
        for topic in queries:
            totals = connection.execute(
                """
                SELECT COUNT(*) AS matching_pages, COUNT(DISTINCT document_id) AS matching_documents
                FROM pages_fts WHERE pages_fts MATCH ?
                """,
                (topic["query"],),
            ).fetchone()
            top_documents = connection.execute(
                """
                SELECT d.document_id, d.title, d.source_url, d.document_class,
                       d.consultation_id, COUNT(*) AS matching_pages,
                       MIN(p.page_number) AS first_matching_page
                FROM pages_fts AS p
                JOIN documents AS d USING(document_id)
                WHERE pages_fts MATCH ?
                GROUP BY d.document_id
                ORDER BY matching_pages DESC, d.title
                LIMIT ?
                """,
                (topic["query"], args.top_documents),
            ).fetchall()
            by_voice = connection.execute(
                """
                SELECT pg.institutional_voice, COUNT(DISTINCT p.document_id) AS matching_documents,
                       COUNT(*) AS matching_pages
                FROM pages_fts AS p
                JOIN pages AS pg USING(document_id, page_number)
                WHERE pages_fts MATCH ?
                GROUP BY pg.institutional_voice
                ORDER BY matching_documents DESC
                """,
                (topic["query"],),
            ).fetchall()
            by_document_class = connection.execute(
                """
                SELECT d.document_class, COUNT(DISTINCT p.document_id) AS matching_documents,
                       COUNT(*) AS matching_pages
                FROM pages_fts AS p
                JOIN documents AS d USING(document_id)
                WHERE pages_fts MATCH ?
                GROUP BY d.document_class
                ORDER BY matching_documents DESC, matching_pages DESC, d.document_class
                """,
                (topic["query"],),
            ).fetchall()
            by_analysis_year = connection.execute(
                """
                SELECT CASE
                         WHEN d.analysis_year IS NOT NULL THEN CAST(d.analysis_year AS TEXT)
                         ELSE 'unknown'
                       END AS analysis_year,
                       COUNT(DISTINCT p.document_id) AS matching_documents,
                       COUNT(*) AS matching_pages
                FROM pages_fts AS p
                JOIN documents AS d USING(document_id)
                WHERE pages_fts MATCH ?
                GROUP BY analysis_year
                ORDER BY analysis_year
                """,
                (topic["query"],),
            ).fetchall()
            results.append({
                **topic,
                "matching_documents": totals["matching_documents"],
                "matching_pages": totals["matching_pages"],
                "by_institutional_voice": {
                    row["institutional_voice"]: row["matching_documents"] for row in by_voice},
                "stakeholder_documents": next(
                    (row["matching_documents"] for row in by_voice
                     if row["institutional_voice"] == "stakeholder"), 0
                ),
                "unknown_voice_documents": next(
                    (row["matching_documents"] for row in by_voice
                     if row["institutional_voice"] == "unknown"), 0
                ),
                "by_document_class": [dict(row) for row in by_document_class],
                "by_analysis_year": [dict(row) for row in by_analysis_year],
                "top_documents": [dict(row) for row in top_documents],
            })
            print(
                f"{topic['id']}: {totals['matching_documents']} documents / {totals['matching_pages']} pages",
                flush=True,
            )
    finally:
        connection.close()

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "topics": results,
    }
    (output / "topic-scan.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n")
    with (output / "topic-scan.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["id", "label", "query", "matching_documents",
                                                        "matching_pages", "stakeholder_documents",
                                                        "unknown_voice_documents"], lineterminator="\n")
        writer.writeheader()
        for result in results:
            writer.writerow({key: result[key] for key in writer.fieldnames})
    return 0


if __name__ == "__main__":
    sys.exit(main())
