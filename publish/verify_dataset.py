#!/usr/bin/env python3
"""Prove the published dataset is live and correct, without downloading it.

    python publish\\verify_dataset.py aditya487

Every query below reads from the Hugging Face URL directly. DuckDB fetches only
the byte ranges it needs from the Parquet file, which is the whole reason for
publishing in this format: a machine with no local copy can still search the
entire corpus.
"""
from __future__ import annotations

import sys

EXPECTED_AUTHORSHIP = {"central-bank": 3809, "stakeholder": 1656, "unresolved": 103}
EXPECTED_DOCUMENTS = 5568
EXPECTED_PAGES = 88782


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python publish/verify_dataset.py YOUR_HF_USERNAME")
        return 2
    user = sys.argv[1].strip()

    try:
        import duckdb
    except ImportError:
        print("duckdb is not installed:  pip install duckdb")
        return 1

    base = f"https://huggingface.co/datasets/{user}/cbi-archive-corpus/resolve/main/data"
    docs, pages = f"{base}/documents.parquet", f"{base}/pages.parquet"
    connection = duckdb.connect()
    connection.execute("INSTALL httpfs; LOAD httpfs;")
    failures = []

    print(f"reading {docs}\n")

    print("1. authorship split")
    rows = connection.execute(
        f"SELECT authorship, count(*) FROM read_parquet('{docs}') GROUP BY 1 ORDER BY 2 DESC"
    ).fetchall()
    actual = dict(rows)
    for label, expected in EXPECTED_AUTHORSHIP.items():
        got = actual.get(label, 0)
        ok = got == expected
        print(f"   {label:14s} {got:6d}   expected {expected:6d}   {'ok' if ok else 'MISMATCH'}")
        if not ok:
            failures.append(f"{label}: {got} != {expected}")

    print("\n2. totals")
    documents = connection.execute(f"SELECT count(*) FROM read_parquet('{docs}')").fetchone()[0]
    page_rows = connection.execute(f"SELECT count(*) FROM read_parquet('{pages}')").fetchone()[0]
    for label, got, expected in (("documents", documents, EXPECTED_DOCUMENTS),
                                 ("pages", page_rows, EXPECTED_PAGES)):
        ok = got == expected
        print(f"   {label:14s} {got:6d}   expected {expected:6d}   {'ok' if ok else 'MISMATCH'}")
        if not ok:
            failures.append(f"{label}: {got} != {expected}")

    print("\n3. a real query: what the regulator says about operational resilience")
    rows = connection.execute(f"""
        SELECT d.title, p.page_number
        FROM read_parquet('{pages}') p
        JOIN read_parquet('{docs}') d USING (document_id)
        WHERE d.authorship = 'central-bank'
          AND lower(p.text) LIKE '%operational resilience%'
        LIMIT 5
    """).fetchall()
    for title, page in rows:
        print(f"   p{page:<5d} {(title or '')[:66]}")
    if not rows:
        failures.append("the join query returned nothing")

    print("\n4. the discipline check: these two must never be mixed")
    for authorship in ("central-bank", "stakeholder"):
        count = connection.execute(f"""
            SELECT count(DISTINCT d.document_id)
            FROM read_parquet('{pages}') p JOIN read_parquet('{docs}') d USING (document_id)
            WHERE d.authorship = '{authorship}' AND lower(p.text) LIKE '%disproportionate%'
        """).fetchone()[0]
        voice = "regulator" if authorship == "central-bank" else "industry advocacy"
        print(f"   {count:4d} {authorship:14s} documents say 'disproportionate'  ({voice})")

    print()
    if failures:
        print("FAILED:")
        for f in failures:
            print("  -", f)
        return 1
    print(f"PASS. The corpus is live and queryable at "
          f"https://huggingface.co/datasets/{user}/cbi-archive-corpus")
    print("Nothing was downloaded to run any of the above.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
