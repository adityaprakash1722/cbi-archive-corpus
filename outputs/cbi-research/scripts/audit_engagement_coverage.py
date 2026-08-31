#!/usr/bin/env python3
"""Inventory canonical CP/DP identifiers and expose snapshot coverage gaps.

An absent number is not proof that a consultation never existed. It means only
that no document carrying that canonical identifier is present in this crawl
snapshot. Keeping that distinction in the output prevents the archive from
silently presenting a partial sequence as an exhaustive register.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--maximum-cp", type=int, default=171)
    args = parser.parse_args()

    connection = sqlite3.connect(f"file:{args.database.resolve()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    rows = []
    for number in range(1, args.maximum_cp + 1):
        identifier = f"cp{number}"
        counts = dict(connection.execute(
            "SELECT document_class, COUNT(*) FROM documents "
            "WHERE consultation_id = ? GROUP BY document_class", (identifier,)))
        documents = sum(counts.values())
        proposals = counts.get("cbi-consultation-material", 0)
        responses = counts.get("stakeholder-consultation-submission", 0)
        feedback = counts.get("cbi-consultation-feedback", 0)
        rows.append({
            "engagement_id": identifier,
            "engagement_type": "consultation-paper",
            "sequence_number": number,
            "snapshot_status": "present" if documents else "absent-from-snapshot",
            "documents": documents,
            "central_bank_proposal_or_material": proposals,
            "stakeholder_submissions": responses,
            "central_bank_feedback": feedback,
            "complete_argumentative_loop": bool(proposals and responses and feedback),
            "interpretation": (
                "documents present in the 2026-08-25 crawl snapshot" if documents else
                "no canonical identifier found; this is a coverage gap, not proof of non-existence"),
        })

    discussion = connection.execute(
        "SELECT engagement_id, COUNT(*) AS documents, "
        "SUM(authorship = 'stakeholder') AS stakeholder, "
        "SUM(authorship = 'central-bank') AS central_bank, "
        "SUM(authorship = 'mixed') AS mixed "
        "FROM documents WHERE engagement_id LIKE 'dp%' GROUP BY engagement_id"
    ).fetchall()
    connection.close()
    for item in sorted(discussion, key=lambda row: int(re.search(r"\d+", row[0]).group())):
        number = int(re.search(r"\d+", item["engagement_id"]).group())
        rows.append({
            "engagement_id": item["engagement_id"],
            "engagement_type": "discussion-paper",
            "sequence_number": number,
            "snapshot_status": "present",
            "documents": item["documents"],
            "central_bank_proposal_or_material": item["central_bank"],
            "stakeholder_submissions": item["stakeholder"],
            "central_bank_feedback": 0,
            "complete_argumentative_loop": False,
            "interpretation": "documents present in the 2026-08-25 crawl snapshot",
        })

    args.output.mkdir(parents=True, exist_ok=True)
    csv_path = args.output / "engagement-coverage.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    cp_rows = [row for row in rows if row["engagement_type"] == "consultation-paper"]
    summary = {
        "snapshot_date": "2026-08-25",
        "canonical_cp_range_audited": [1, args.maximum_cp],
        "cp_identifiers_present": sum(row["snapshot_status"] == "present" for row in cp_rows),
        "cp_identifiers_absent_from_snapshot": [
            row["engagement_id"] for row in cp_rows if row["snapshot_status"] != "present"],
        "complete_argumentative_loops": sum(row["complete_argumentative_loop"] for row in cp_rows),
        "discussion_paper_identifiers_present": len(discussion),
        "caution": ("Sequence gaps measure this snapshot's coverage. They do not establish that a "
                    "number was never issued or that the Central Bank site is itself complete."),
    }
    (args.output / "engagement-coverage-summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
