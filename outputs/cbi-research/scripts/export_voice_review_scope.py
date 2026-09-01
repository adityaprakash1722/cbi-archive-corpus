#!/usr/bin/env python3
"""Export the deterministic v5.2 institutional-voice review worklist.

This is a review queue, not a gold set and not an accuracy estimate.  It makes
the higher-risk part of the corpus finite and reproducible while retaining the
safe ``unknown`` default for everything that has not been evidenced.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
import time
from collections import Counter
from pathlib import Path


EXTERNAL_OR_TRIBUNAL = re.compile(
    r"\b(?:imf|international monetary fund|world bank|oecd|ecb|european central bank|"
    r"european commission|esma|eiopa|eba|ifsat|appeal tribunal|tribunal|court|"
    r"mr justice|mrs justice|justice [a-z]|prof(?:essor)?\.? [a-z])\b",
    re.IGNORECASE,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    with sqlite3.connect(args.database.resolve()) as connection:
        connection.row_factory = sqlite3.Row
        documents = connection.execute(
            """
            SELECT source_sha256, title, source_url, source_page_url,
                   source_format, document_class, document_role, consultation_id,
                   engagement_id, authorship, legacy_authorship,
                   institutional_voice, voice_review_status, voice_evidence,
                   classification_basis, classification_confidence, author_org,
                   page_count
            FROM documents
            ORDER BY source_sha256
            """
        ).fetchall()

    rows: list[dict[str, object]] = []
    for item in documents:
        row = dict(item)
        reasons: list[str] = []
        engagement_id = (row.get("engagement_id") or "").lower()
        basis = row.get("classification_basis") or ""
        voice = row.get("institutional_voice") or "unknown"
        haystack = " ".join(
            str(row.get(field) or "")
            for field in ("title", "source_url", "source_page_url", "author_org")
        )

        if engagement_id.startswith("dp"):
            reasons.append("discussion-paper population")
        if basis.startswith("content-"):
            reasons.append("content-scored consultation edge case")
        if voice == "unknown" and EXTERNAL_OR_TRIBUNAL.search(haystack):
            reasons.append("unknown external-authority or tribunal candidate")

        if not reasons:
            continue

        rows.append({
            **row,
            "scope_reason": "; ".join(reasons),
            "review_state": (
                "already-manually-adjudicated"
                if row.get("voice_review_status") == "manual"
                else "pending-independent-review"
            ),
            "reviewer_1_voice": "",
            "reviewer_1_evidence": "",
            "reviewer_2_voice": "",
            "reviewer_2_evidence": "",
            "resolution": "",
            "resolution_notes": "",
        })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else [
        "source_sha256", "scope_reason", "review_state", "reviewer_1_voice",
        "reviewer_1_evidence", "reviewer_2_voice", "reviewer_2_evidence",
        "resolution", "resolution_notes",
    ]
    with args.output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    reason_counts: Counter[str] = Counter()
    for row in rows:
        for reason in str(row["scope_reason"]).split("; "):
            reason_counts[reason] += 1
    summary = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "database": str(args.database.resolve()),
        "database_sha256": sha256_file(args.database),
        "documents_in_scope": len(rows),
        "scope_reason_counts_nonexclusive": dict(sorted(reason_counts.items())),
        "current_voice": dict(Counter(
            str(row["institutional_voice"]) for row in rows).most_common()),
        "review_state": dict(Counter(
            str(row["review_state"]) for row in rows).most_common()),
        "methodological_status": "review queue; not a gold set or accuracy sample",
    }
    summary_path = args.output.with_name(args.output.stem + "-summary.json")
    summary_path.write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
