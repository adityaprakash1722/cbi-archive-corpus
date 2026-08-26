#!/usr/bin/env python3
"""Demonstrate that querying the corpus does not download the corpus.

    python publish\\demo_how_it_works.py aditya487

Runs the same question three ways and times each, so the difference is
something you watch happen rather than something you take on trust.
"""
from __future__ import annotations

import sys, time, urllib.request


def main() -> int:
    user = sys.argv[1] if len(sys.argv) == 2 else "aditya487"
    url = (f"https://huggingface.co/datasets/{user}/cbi-archive-corpus"
           f"/resolve/main/data/pages.parquet")

    try:
        import duckdb
    except ImportError:
        print("pip install duckdb")
        return 1

    print("STEP 1: ask the server about the file, without fetching it\n")
    request = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(request) as response:
        size = int(response.headers.get("Content-Length") or 0)
        ranges = response.headers.get("Accept-Ranges")
    print(f"  file size on server : {size/1e6:.1f} MB")
    print(f"  Accept-Ranges       : {ranges}")
    print("  'bytes' means the server will send any slice of the file you ask for.\n")

    print("STEP 2: fetch just the last 8 KB, the Parquet footer\n")
    request = urllib.request.Request(url, headers={"Range": f"bytes={size-8192}-{size-1}"})
    started = time.time()
    with urllib.request.urlopen(request) as response:
        footer = response.read()
    print(f"  got {len(footer)} bytes in {time.time()-started:.2f}s, status {response.status}")
    print("  Status 206 is 'Partial Content'. The footer holds the schema and a map")
    print("  of exactly which byte ranges contain which column.\n")

    connection = duckdb.connect()
    connection.execute("INSTALL httpfs; LOAD httpfs;")

    print("STEP 3: query one small column out of the 46 MB file\n")
    started = time.time()
    rows = connection.execute(
        f"SELECT authorship, count(*) FROM read_parquet('{url}') GROUP BY 1 ORDER BY 2 DESC"
    ).fetchall()
    query_seconds = time.time() - started
    for label, count in rows:
        print(f"  {label:14s} {count:6d}")
    print(f"\n  took {query_seconds:.1f}s\n")

    print("STEP 4: now actually download the whole file, for comparison\n")
    started = time.time()
    with urllib.request.urlopen(url) as response:
        downloaded = 0
        while chunk := response.read(1 << 20):
            downloaded += len(chunk)
            print(f"\r  {downloaded/1e6:6.1f} MB", end="", flush=True)
    download_seconds = time.time() - started
    print(f"\n  {downloaded/1e6:.1f} MB in {download_seconds:.1f}s\n")

    print("=" * 62)
    print(f"  query that answered the question : {query_seconds:6.1f}s")
    print(f"  downloading the same file        : {download_seconds:6.1f}s")
    if query_seconds > 0:
        print(f"  the query was {download_seconds/query_seconds:.0f}x faster because it never")
        print("  read the 46 MB text column at all. It read the footer, found where")
        print("  the 'authorship' column lived, and fetched only those bytes.")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
