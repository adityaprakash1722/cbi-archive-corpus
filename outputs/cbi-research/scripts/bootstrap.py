#!/usr/bin/env python3
"""Bring a fresh machine up to a working corpus.

The heavy artifacts are deliberately not in git: 6.56 GB of raw source, 202 MB of
Markdown, and 1.94 GB of SQLite indices that are build products. What travels is
47 MB of Parquet. This script fetches it and, if asked, rebuilds the local index.

    python3 bootstrap.py --dataset <user>/cbi-archive-corpus
    python3 bootstrap.py --dataset <user>/cbi-archive-corpus --index
"""
from __future__ import annotations

import argparse, hashlib, json, subprocess, sys, urllib.request
from pathlib import Path

from release_lock import corpus_repo, corpus_revision, load as load_release

BASE = "https://huggingface.co/datasets/{dataset}/resolve/{revision}/{path}"
WANTED = [
    "data/documents.parquet",
    "data/pages.parquet",
    "data/dataset-summary.json",
    "manifests/files.csv.zst",
    "manifests/provenance-classification.csv.zst",
    "manifests/extraction-quality.csv.zst",
    # Both conversion manifests. materialize_markdown.py reads them to restore
    # source_file and engine version to the frontmatter, and without the Office
    # one the 323 non-PDF documents come out thinner than they need to be.
    "manifests/conversion-manifest.csv.zst",
    "manifests/conversion-manifest-office.csv.zst",
]


def fetch(dataset: str, revision: str, path: str, destination: Path,
          expected_sha256: str | None) -> int:
    url = BASE.format(dataset=dataset, revision=revision, path=path)
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
    if expected_sha256 and digest.hexdigest() != expected_sha256:
        destination.unlink(missing_ok=True)
        raise ValueError(
            f"release-lock hash mismatch for {path}: got {digest.hexdigest()}, "
            f"want {expected_sha256}")
    return total


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default=corpus_repo(), help="e.g. yourname/cbi-archive-corpus")
    ap.add_argument("--revision", default=corpus_revision(),
                    help="immutable HF revision (defaults to RELEASE.lock.json)")
    ap.add_argument("--output", type=Path, default=Path("corpus-data"))
    ap.add_argument("--index", action="store_true", help="also rebuild the SQLite index")
    args = ap.parse_args()

    release = load_release()
    expected = release["artifacts"] if args.revision == corpus_revision() else {}
    print(f"fetching {args.dataset} at immutable revision {args.revision}")
    total = sum(fetch(args.dataset, args.revision, path, args.output / path,
                      expected.get(path)) for path in WANTED)
    print(f"\n{total/1e6:.1f} MB into {args.output.resolve()}")

    summary_path = args.output / "data/dataset-summary.json"
    if summary_path.is_file():
        summary = json.loads(summary_path.read_text())
        print(f"corpus: {summary['documents']} documents, {summary['pages']} pages")

    if args.index:
        scripts = Path(__file__).resolve().parent
        research = scripts.parent
        corpus = args.output / "corpus"
        index = args.output / "index"
        index.mkdir(parents=True, exist_ok=True)
        user = args.dataset.split("/", 1)[0]
        materialize = [sys.executable, str(scripts / "materialize_markdown.py"),
                       "--user", user, "--revision", args.revision,
                       "--output", str(corpus)]
        build = [sys.executable, str(scripts / "build_search_index.py"),
                 "--corpus", str(corpus), "--corpus", str(corpus / "office"),
                 "--output", str(index), "--database-name", "cbi-corpus.sqlite",
                 "--snapshot-date", release["crawl_snapshot_date"],
                 "--page-authorship-csv", str(corpus / "page-authorship-overrides.csv"),
                 "--extraction-preferences-csv", str(corpus / "extraction-preferences.csv")]
        audit = research / "audit" / "pdf-audit.csv"
        if audit.is_file():
            build += ["--audit-csv", str(audit)]
        print("\nmaterialising Markdown and rebuilding the SQLite index", flush=True)
        subprocess.run(materialize, check=True)
        subprocess.run(build, check=True)
        print(f"index: {(index / 'cbi-corpus.sqlite').resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
