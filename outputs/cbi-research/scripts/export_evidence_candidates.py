#!/usr/bin/env python3
"""Export page-level evidence candidates from the CBI FTS corpus.

This is a discovery aid, not a quotation generator. Every candidate retains the
source document hash, source URL, Markdown path, and PDF page so that material
claims can be checked against the normalized page and rendered original.
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
import time
from pathlib import Path


PAIN_QUERY = (
    "gap OR gaps OR challenge OR challenges OR burden OR burdens OR manual OR "
    "difficult OR difficulty OR inadequate OR error OR errors OR harm OR failure OR "
    "failures OR delay OR delays OR costly OR shortage OR obstacle OR friction OR "
    "vulnerable OR vulnerability OR concern OR concerns OR deficiency OR deficiencies"
)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--per-topic", type=int, default=15)
    parser.add_argument("--candidate-pool", type=int, default=1500)
    return parser.parse_args()


def ranked_pages(
    connection: sqlite3.Connection,
    query: str,
    limit: int,
) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT f.document_id, f.page_number,
               bm25(pages_fts, 0.0, 0.0, 1.5, 1.0) AS relevance,
               snippet(pages_fts, 3, '<<', '>>', ' … ', 56) AS candidate_excerpt,
               d.title, d.source_url, d.markdown_file, d.source_sha256,
               d.pdf_creation_date, d.document_class, d.consultation_id,
               d.published_at, d.analysis_year, pg.authorship AS page_authorship,
               pg.authorship_basis AS page_authorship_basis,
               d.page_count, d.ocr_enabled,
               d.quality_low_text
        FROM pages_fts AS f
        JOIN pages AS pg USING(document_id, page_number)
        JOIN documents AS d ON d.document_id = f.document_id
        WHERE pages_fts MATCH ?
        ORDER BY relevance, d.title, f.page_number
        LIMIT ?
        """,
        (query, limit),
    ).fetchall()


def distinct_documents(rows: list[sqlite3.Row], limit: int) -> list[sqlite3.Row]:
    selected: list[sqlite3.Row] = []
    seen: set[str] = set()
    for row in rows:
        if row["document_id"] in seen:
            continue
        selected.append(row)
        seen.add(row["document_id"])
        if len(selected) == limit:
            break
    return selected


def main() -> int:
    args = arguments()
    if args.per_topic < 1 or args.candidate_pool < args.per_topic:
        raise SystemExit("--per-topic must be positive and --candidate-pool must be at least --per-topic")

    topics = json.loads(args.queries.resolve().read_text(encoding="utf-8"))
    connection = sqlite3.connect(args.database.resolve())
    connection.row_factory = sqlite3.Row
    output_rows: list[dict] = []
    started = time.monotonic()
    try:
        for topic in topics:
            modes = (
                ("relevance", topic["query"]),
                ("pain-signal", f"({topic['query']}) AND ({PAIN_QUERY})"),
            )
            for mode, query in modes:
                candidates = ranked_pages(connection, query, args.candidate_pool)
                selected = distinct_documents(candidates, args.per_topic)
                for rank, row in enumerate(selected, 1):
                    output_rows.append(
                        {
                            "topic_id": topic["id"],
                            "topic_label": topic["label"],
                            "mode": mode,
                            "rank": rank,
                            "document_id": row["document_id"],
                            "source_sha256": row["source_sha256"],
                            "title": row["title"],
                            "source_url": row["source_url"],
                            "markdown_file": row["markdown_file"],
                            "source_page": row["page_number"],
                            "document_pages": row["page_count"],
                            "pdf_creation_date": row["pdf_creation_date"],
                            "published_at": row["published_at"],
                            "analysis_year": row["analysis_year"],
                            "page_authorship": row["page_authorship"],
                            "page_authorship_basis": row["page_authorship_basis"],
                            "document_class": row["document_class"],
                            "consultation_id": row["consultation_id"],
                            "ocr_enabled": bool(row["ocr_enabled"]),
                            "quality_low_text": bool(row["quality_low_text"]),
                            "fts_relevance": row["relevance"],
                            # Extracted page text can carry spaces before a
                            # newline. Preserve content while removing only
                            # line-end whitespace so generated CSV/JSON passes
                            # cross-platform diff checks.
                            "candidate_excerpt": "\n".join(
                                line.rstrip() for line in row["candidate_excerpt"].splitlines()),
                            "verification_status": "unverified-candidate",
                        }
                    )
                print(
                    f"{topic['id']} [{mode}]: {len(selected)} distinct documents "
                    f"from {len(candidates)} ranked pages",
                    flush=True,
                )
    finally:
        connection.close()

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    json_payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "candidate_rows": len(output_rows),
        "method": {
            "unit": "best-ranked matching page per distinct document",
            "modes": {
                "relevance": "topic query only",
                "pain-signal": "topic query intersected with explicit problem-language cues",
            },
            "warning": "Candidate excerpts must be checked against the normalized page and rendered source PDF before quotation.",
        },
        "candidates": output_rows,
    }
    (output / "evidence-candidates.json").write_text(
        json.dumps(json_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    fieldnames = list(output_rows[0]) if output_rows else [
        "topic_id",
        "topic_label",
        "mode",
        "rank",
        "document_id",
        "source_sha256",
        "title",
        "source_url",
        "markdown_file",
        "source_page",
        "document_pages",
        "pdf_creation_date",
        "document_class",
        "consultation_id",
        "ocr_enabled",
        "quality_low_text",
        "fts_relevance",
        "candidate_excerpt",
        "verification_status",
    ]
    with (output / "evidence-candidates.csv").open(
            "w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(output_rows)
    print(f"Exported {len(output_rows)} evidence candidates", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
