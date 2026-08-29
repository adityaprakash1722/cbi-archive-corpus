#!/usr/bin/env python3
"""Prove the published dataset is live and correct from a temporary download.

    python publish\\verify_dataset.py aditya487

The verifier securely downloads the two pinned Parquet artifacts, checks their
hashes and queries the temporary copies with DuckDB. This is deliberately more
portable than DuckDB's direct HTTPS reader, which can fail to discover the
Windows certificate store behind a managed TLS proxy. The temporary files are
removed before exit; ordinary users can still query the Hub URLs directly.
"""
from __future__ import annotations

import argparse, hashlib, tempfile, urllib.request
from pathlib import Path

from release_lock import load as load_release

def download_sha256(url: str, target: Path) -> str:
    digest = hashlib.sha256()
    request = urllib.request.Request(url, headers={"User-Agent": "cbi-dataset-verifier/1"})
    with urllib.request.urlopen(request) as response, target.open("wb") as output:
        while chunk := response.read(1 << 20):
            output.write(chunk)
            digest.update(chunk)
    return digest.hexdigest()


def sql_path(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")


def main() -> int:
    release = load_release()
    parser = argparse.ArgumentParser()
    parser.add_argument("user", nargs="?", default="aditya487")
    parser.add_argument("--revision", default=release["hugging_face"]["corpus_revision"])
    parser.add_argument("--skip-hashes", action="store_true",
                        help="skip downloading and hashing the two Parquet artifacts")
    args = parser.parse_args()
    user = args.user.strip()
    locked_revision = release["hugging_face"]["corpus_revision"]
    if args.revision != locked_revision:
        parser.error("--revision must match RELEASE.lock.json; update the lock before verifying a release")
    expected = release["expected"]
    expected_authorship = expected["authorship"]

    try:
        import duckdb
    except ImportError:
        print("duckdb is not installed:  pip install duckdb")
        return 1

    base = (f"https://huggingface.co/datasets/{user}/cbi-archive-corpus/"
            f"resolve/{args.revision}/data")
    docs_url, pages_url = f"{base}/documents.parquet", f"{base}/pages.parquet"
    cache = tempfile.TemporaryDirectory(prefix="cbi-verify-")
    cache_path = Path(cache.name)
    docs_file, pages_file = cache_path / "documents.parquet", cache_path / "pages.parquet"
    downloaded_hashes = {
        "data/documents.parquet": download_sha256(docs_url, docs_file),
        "data/pages.parquet": download_sha256(pages_url, pages_file),
    }
    docs, pages = sql_path(docs_file), sql_path(pages_file)
    connection = duckdb.connect()
    failures = []

    print(f"reading pinned release {args.revision}\n")

    if not args.skip_hashes:
        print("0. locked artifact hashes")
        for path in ("data/documents.parquet", "data/pages.parquet"):
            got = downloaded_hashes[path]
            want = release["artifacts"][path]
            ok = got == want
            print(f"   {path:24s} {got[:16]}  {'ok' if ok else 'MISMATCH'}")
            if not ok:
                failures.append(f"{path}: {got} != {want}")

    print("1. authorship split")
    rows = connection.execute(
        f"SELECT authorship, count(*) FROM read_parquet('{docs}') GROUP BY 1 ORDER BY 2 DESC"
    ).fetchall()
    actual = dict(rows)
    if set(actual) != set(expected_authorship):
        failures.append(f"authorship labels: {sorted(actual)} != {sorted(expected_authorship)}")
    for label, expected_count in expected_authorship.items():
        got = actual.get(label, 0)
        ok = got == expected_count
        print(f"   {label:14s} {got:6d}   expected {expected_count:6d}   {'ok' if ok else 'MISMATCH'}")
        if not ok:
            failures.append(f"{label}: {got} != {expected_count}")

    print("\n2. totals")
    documents = connection.execute(f"SELECT count(*) FROM read_parquet('{docs}')").fetchone()[0]
    page_rows = connection.execute(f"SELECT count(*) FROM read_parquet('{pages}')").fetchone()[0]
    for label, got, expected_count in (("documents", documents, expected["documents"]),
                                       ("pages", page_rows, expected["pages"])):
        ok = got == expected_count
        print(f"   {label:14s} {got:6d}   expected {expected_count:6d}   {'ok' if ok else 'MISMATCH'}")
        if not ok:
            failures.append(f"{label}: {got} != {expected_count}")

    print("\n3. a real query: what the regulator says about operational resilience")
    rows = connection.execute(f"""
        SELECT d.title, p.page_number
        FROM read_parquet('{pages}') p
        JOIN read_parquet('{docs}') d USING (document_id)
        WHERE p.authorship = 'central-bank'
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
            WHERE p.authorship = '{authorship}' AND lower(p.text) LIKE '%disproportionate%'
        """).fetchone()[0]
        voice = "regulator" if authorship == "central-bank" else "industry advocacy"
        print(f"   {count:4d} {authorship:14s} documents say 'disproportionate'  ({voice})")

    print()
    if failures:
        print("FAILED:")
        for f in failures:
            print("  -", f)
        cache.cleanup()
        return 1
    print(f"PASS. The corpus is live and queryable at "
          f"https://huggingface.co/datasets/{user}/cbi-archive-corpus")
    print("The verified temporary download has been removed.")
    cache.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
