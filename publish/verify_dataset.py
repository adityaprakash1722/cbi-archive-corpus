#!/usr/bin/env python3
"""Prove every locked public artifact is live and byte-identical.

    python publish\\verify_dataset.py aditya487

The verifier downloads every corpus and raw-catalog artifact named in
RELEASE.lock.json, checks its SHA-256, then queries the temporary Parquet copies
with DuckDB. This proves the lock describes the bytes actually available at both
immutable Hub revisions, rather than merely checking two convenient files.
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

    cache = tempfile.TemporaryDirectory(prefix="cbi-verify-")
    cache_path = Path(cache.name)
    downloaded_hashes: dict[str, str] = {}
    downloaded_files: dict[str, Path] = {}
    corpus_repo = release["hugging_face"]["corpus_repo"]
    raw_repo = release["hugging_face"]["raw_repo"]
    raw_revision = release["hugging_face"]["raw_revision"]
    print(f"reading pinned corpus {args.revision}")
    print(f"and pinned raw metadata {raw_revision}\n")
    for name in release["artifacts"]:
        is_raw = name.startswith("publish/")
        repo = raw_repo if is_raw else corpus_repo
        revision = raw_revision if is_raw else args.revision
        remote_name = name.removeprefix("publish/") if is_raw else name
        url = f"https://huggingface.co/datasets/{repo}/resolve/{revision}/{remote_name}"
        target = cache_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        downloaded_hashes[name] = download_sha256(url, target)
        downloaded_files[name] = target

    docs_file = downloaded_files["data/documents.parquet"]
    pages_file = downloaded_files["data/pages.parquet"]
    docs, pages = sql_path(docs_file), sql_path(pages_file)
    connection = duckdb.connect()
    failures = []

    print("0. locked artifact hashes")
    for path, want in release["artifacts"].items():
        got = downloaded_hashes[path]
        ok = got == want
        print(f"   {path:54s} {got[:16]}  {'ok' if ok else 'MISMATCH'}")
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
