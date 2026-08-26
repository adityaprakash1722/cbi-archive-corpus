#!/usr/bin/env python3
r"""Scan the corpus for personal data before republishing it in bulk.

    python outputs\cbi-research\scripts\scan_personal_data.py \
      --database outputs\cbi-research\index\cbi-corpus-v3-5568docs.sqlite \
      --output outputs\cbi-research\qa

Why this is not paranoia
------------------------
Every document here was already public on centralbank.ie. That is not the same
as being publishable in bulk. An individual's consultation response sitting on a
regulator's website is findable by someone who goes looking for it; the same
response inside a downloadable corpus, indexed and full-text searchable, is
findable by someone who was not looking for it at all. The legal shorthand is
practical obscurity, and removing it is a real change in exposure even when
every input was technically public.

The Central Bank's own reuse terms exclude personal information and third-party
rights from the general permission to reuse. Only 71 of 6,984 downloaded files
carry an explicit licence (CC-BY-4.0, from the open-data portal). The remaining
6,913 carry none, so reuse rests on the site terms, and those terms carve out
exactly this category.

What this reports, and what it does not
---------------------------------------
This is a *screening* tool. It finds candidates by pattern and it is
deliberately noisy: an Irish phone pattern will match a document reference
number, and a PPSN pattern will match plenty of things that are not PPSNs. The
output is a worklist for a human, not a verdict.

It prints and stores counts, never values. A scan that leaks the data it is
looking for has defeated itself, so matched strings are hashed and truncated in
the CSV and never printed.
"""
from __future__ import annotations

import argparse, csv, hashlib, json, re, sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

# Ordered most to least alarming. Each is a screen, not a determination.
PATTERNS = [
    ("ppsn", "Irish PPS number shape",
     re.compile(r"\b\d{7}[A-W][A-IW]?\b")),
    ("iban", "IBAN shape",
     re.compile(r"\bIE\d{2}[A-Z]{4}\d{14}\b")),
    ("email_personal", "Email with a personal-looking local part",
     re.compile(r"\b[A-Za-z]+[._][A-Za-z]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("email_any", "Any email address",
     re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("phone_ie", "Irish phone number shape",
     re.compile(r"\b(?:\+353|0)\s?(?:1|2\d|4\d|5\d|6\d|7\d|9\d|8[35679])\s?\d{3}\s?\d{3,4}\b")),
    ("dob", "Date of birth label",
     re.compile(r"\b(?:date of birth|d\.o\.b\.|dob)\b[\s:]*\d", re.I)),
    ("signature", "Signature block",
     re.compile(r"\b(?:yours sincerely|yours faithfully|kind regards|signed)\b", re.I)),
    ("home_address", "Home address label",
     re.compile(r"\b(?:home address|private address|residential address)\b", re.I)),
    ("personal_capacity", "Written as a private individual",
     re.compile(r"\b(?:in a personal capacity|as a private individual|as a member of the public|"
                r"i am writing as a|private citizen|as an individual)\b", re.I)),
]

# Local parts that are a role, not a person. Screened out of email_personal.
ROLE_LOCAL = re.compile(
    r"^(?:info|admin|office|enquiries|enquiry|contact|support|hello|general|reception|"
    r"secretary|compliance|legal|press|media|policy|consultation|consultations|"
    r"submissions|feedback|mail|post|help|sales|accounts)$", re.I)


def token(value: str) -> str:
    """A short stable hash, so duplicates can be counted without storing the value."""
    return hashlib.sha256(value.lower().encode("utf-8")).hexdigest()[:12]


def scan(database: Path, output: Path) -> dict:
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    documents = {
        row["document_id"]: row
        for row in connection.execute(
            "SELECT document_id, source_sha256, source_url, title, authorship, "
            "consultation_id, document_class FROM documents")
    }

    hits: dict[str, Counter] = defaultdict(Counter)
    distinct: dict[str, set] = defaultdict(set)
    pages_scanned = 0

    for row in connection.execute("SELECT document_id, text FROM pages"):
        pages_scanned += 1
        text = row["text"]
        if not text:
            continue
        document_id = row["document_id"]
        for name, _label, pattern in PATTERNS:
            found = pattern.findall(text)
            if not found:
                continue
            if name == "email_personal":
                found = [f for f in found
                         if not ROLE_LOCAL.match(f.split("@")[0].split(".")[0])]
                if not found:
                    continue
            hits[document_id][name] += len(found)
            if name in ("email_any", "email_personal", "ppsn", "iban"):
                for value in found:
                    distinct[name].add(token(value))

    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for document_id, counter in hits.items():
        document = documents.get(document_id)
        if document is None:
            continue
        record = {
            "document_id": document_id,
            "source_sha256": document["source_sha256"],
            "authorship": document["authorship"],
            "document_class": document["document_class"],
            "consultation_id": document["consultation_id"] or "",
            "title": (document["title"] or "")[:120],
            "source_url": document["source_url"],
        }
        for name, _label, _pattern in PATTERNS:
            record[name] = counter.get(name, 0)
        record["signal_count"] = sum(1 for n, _l, _p in PATTERNS if counter.get(n))
        rows.append(record)

    rows.sort(key=lambda r: (-r["signal_count"], -r["email_personal"], -r["phone_ie"]))
    csv_path = output / "personal-data-scan.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    by_authorship: dict[str, Counter] = defaultdict(Counter)
    for record in rows:
        for name, _label, _pattern in PATTERNS:
            if record[name]:
                by_authorship[record["authorship"]][name] += 1

    summary = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pages_scanned": pages_scanned,
        "documents_total": len(documents),
        "documents_with_any_signal": len(rows),
        "method": "Pattern screening. Candidates for human review, not determinations. "
                  "Values are never stored; only counts and truncated hashes.",
        "patterns": {name: label for name, label, _ in PATTERNS},
        "documents_by_pattern": {
            name: sum(1 for r in rows if r[name]) for name, _l, _p in PATTERNS},
        "documents_by_pattern_and_authorship": {
            a: dict(c) for a, c in by_authorship.items()},
        "distinct_values_seen": {k: len(v) for k, v in distinct.items()},
    }
    (output / "personal-data-scan.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    summary = scan(args.database, args.output)
    print(f"scanned {summary['pages_scanned']:,} pages across "
          f"{summary['documents_total']:,} documents")
    print(f"{summary['documents_with_any_signal']:,} documents carry at least one signal\n")
    width = max(len(label) for _n, label, _p in PATTERNS)
    for name, label, _pattern in PATTERNS:
        total = summary["documents_by_pattern"][name]
        by = summary["documents_by_pattern_and_authorship"]
        stake = by.get("stakeholder", {}).get(name, 0)
        bank = by.get("central-bank", {}).get(name, 0)
        print(f"  {label:{width}}  {total:>5} docs   "
              f"(stakeholder {stake:>4}, central-bank {bank:>4})")
    print("\nvalues were counted, never stored. see qa/personal-data-scan.csv "
          "for the per-document worklist")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
