#!/usr/bin/env python3
"""Bring a fresh machine up to a working corpus.

The heavy artifacts are deliberately not in git: 6.56 GB of raw source, 202 MB of
Markdown, and 1.94 GB of SQLite indices that are build products. What travels is
47 MB of Parquet. This script fetches it and, if asked, rebuilds the local index.

    python3 bootstrap.py --dataset <user>/cbi-archive-corpus
    python3 bootstrap.py --dataset <user>/cbi-archive-corpus --index
"""
from __future__ import annotations

import argparse, hashlib, json, sys, urllib.request
from pathlib import Path

BASE = "https://huggingface.co/datasets/{dataset}/resolve/main/{path}"
WANTED = [
    "data/documents.parquet",
    "data/pages.parquet",
    "data/dataset-summary.json",
    "manifests/files.csv.zst",
    "manifests/provenance-classification.csv.zst",
    "manifests/extraction-quality.csv.zst",
]


def fetch(dataset: str, path: str, destination: Path) -> int:
    url = BASE.format(dataset=dataset, path=path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    total = 0
    with urllib.request.urlopen(url) as response, destination.open("wb") as out:
        while chunk := response.read(1 << 20):
            out.write(chunk)
            digest.update(chunk)
            total += len(chunk)
            print(f"\r  {path}  {total/1e6:7.1f} MB", end="", flush=True)
    print(f"\r  {path}  {total/1e6:7.1f} MB  sha256={digest.hexdigest()[:16]}")
    return total


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True, help="e.g. yourname/cbi-archive-corpus")
    ap.add_argument("--output", type=Path, default=Path("corpus-data"))
    ap.add_argument("--index", action="store_true", help="also rebuild the SQLite index")
    args = ap.parse_args()

    print(f"fetching {args.dataset}")
    total = sum(fetch(args.dataset, path, args.output / path) for path in WANTED)
    print(f"\n{total/1e6:.1f} MB into {args.output.resolve()}")

    summary_path = args.output / "data/dataset-summary.json"
    if summary_path.is_file():
        summary = json.loads(summary_path.read_text())
        print(f"corpus: {summary['documents']} documents, {summary['pages']} pages")

    if args.index:
        print("\nRebuilding the SQLite index needs the Markdown corpus, which is not")
        print("published. Either run the pipeline from the raw archive, or query the")
        print("Parquet directly, which is what it is there for:\n")
        print("  import pyarrow.parquet as pq")
        print(f"  pages = pq.read_table('{args.output}/data/pages.parquet')")
        print("\nor without downloading at all:\n")
        print("  duckdb -c \"SELECT * FROM "
              f"'https://huggingface.co/datasets/{args.dataset}/resolve/main/data/pages.parquet' LIMIT 5\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
