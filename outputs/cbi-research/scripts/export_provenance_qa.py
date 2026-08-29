#!/usr/bin/env python3
"""Export an auditable document-level provenance comparison between indexes."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import time
from collections import Counter
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--previous-database", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    previous: dict[str, tuple[str, str]] = {}
    if args.previous_database:
        with sqlite3.connect(args.previous_database.resolve()) as connection:
            for sha, document_class, stored_authorship in connection.execute(
                "SELECT source_sha256, document_class, authorship FROM documents"
            ):
                authorship = (stored_authorship or
                              ("stakeholder" if document_class.startswith("stakeholder-")
                               else "central-bank"))
                previous[sha] = (document_class, authorship)

    with sqlite3.connect(args.database.resolve()) as connection:
        connection.row_factory = sqlite3.Row
        current = connection.execute(
            """
            SELECT source_sha256, source_url, source_format, document_class,
                   authorship, classification_basis, classification_confidence,
                   consultation_id, page_count, extraction_selection_basis,
                   alternate_extraction_count, published_at, published_at_basis,
                   analysis_year, analysis_year_basis, source_page_url, retrieved_at
            FROM documents ORDER BY source_url, source_sha256
            """
        ).fetchall()

    rows = []
    for item in current:
        old_class, old_authorship = previous.get(item["source_sha256"], ("", ""))
        rows.append({
            **dict(item),
            "previous_document_class": old_class,
            "previous_authorship": old_authorship,
            "change": (
                "new-document" if not old_class
                else "reclassified" if (old_class != item["document_class"] or
                                         old_authorship != item["authorship"])
                else "unchanged"
            ),
        })

    args.output.mkdir(parents=True, exist_ok=True)
    csv_path = args.output / "provenance-classification.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "database": str(args.database.resolve()),
        "previous_database": str(args.previous_database.resolve()) if args.previous_database else None,
        "documents": len(rows),
        "authorship": dict(Counter(row["authorship"] for row in rows).most_common()),
        "confidence": dict(Counter(row["classification_confidence"] for row in rows).most_common()),
        "change_vs_previous": dict(Counter(row["change"] for row in rows).most_common()),
        "moved_to_stakeholder": sum(
            row["authorship"] == "stakeholder" and row["previous_authorship"] not in {"", "stakeholder"}
            for row in rows
        ),
        "moved_to_unresolved": sum(
            row["authorship"] == "unresolved" and
            row["previous_authorship"] not in {"", "unresolved"}
            for row in rows
        ),
        "moved_to_central_bank": sum(
            row["authorship"] == "central-bank" and
            row["previous_authorship"] not in {"", "central-bank"}
            for row in rows
        ),
        "moved_to_mixed": sum(
            row["authorship"] == "mixed" and row["previous_authorship"] != "mixed"
            for row in rows
        ),
        "basis_breakdown": dict(Counter(row["classification_basis"] for row in rows).most_common()),
        "page_authorship": {},
    }
    with sqlite3.connect(args.database.resolve()) as connection:
        summary["page_authorship"] = dict(connection.execute(
            "SELECT authorship, COUNT(*) FROM pages GROUP BY authorship ORDER BY COUNT(*) DESC"
        ).fetchall())
    (args.output / "provenance-classification-summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
