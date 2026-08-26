#!/usr/bin/env python3
r"""Prove a fresh clone can rebuild the index from the published data alone.

    python outputs\cbi-research\scripts\test_fresh_rebuild.py

Why this exists
---------------
The project promises that anyone can clone the repository, pull the published
Parquet, and rebuild the search index. That promise was made before it was
tested, and when it was finally tested it failed three separate ways:

  * `make materialize` wrote every document into `corpus/markdown`, while the
    indexer reads Office documents from `corpus/office/markdown`. 323 documents
    would have been silently absent.
  * The materialiser omitted `page_basis` and `source_format` from the
    frontmatter. The indexer reads those two from the frontmatter, not the
    manifest, and silently defaults them to `source-page` and `pdf`, which
    mislabels all 326 non-PDF documents.
  * One SHA-256 appears in both conversion manifests, having been converted by
    both pipelines. Writing it once left the PDF manifest pointing at a missing
    file and the rebuild one document short.

None of those raise an error loudly. Two produce a plausible-looking index that
is quietly wrong, which is the worst kind of failure for a corpus whose whole
value is being checkable. Hence a test rather than a comment.

What it does
------------
Materialises the Markdown from Hugging Face into a temporary directory, builds
an index from it, and asserts the result matches the published dataset summary.
Nothing in the working tree is touched. Takes a few minutes, mostly download.

Exit code 0 means a fresh clone would work.
"""
from __future__ import annotations

import argparse, json, sqlite3, subprocess, sys, tempfile, urllib.request
from pathlib import Path

SUMMARY = ("https://huggingface.co/datasets/{user}/cbi-archive-corpus"
           "/resolve/main/data/dataset-summary.json")

# Structural facts a correct rebuild must reproduce. Counts that come from the
# published summary are checked against it rather than hardcoded; these are the
# ones the summary does not carry.
EXPECTED_NON_DEFAULT_PAGE_BASIS = 320
EXPECTED_NON_PDF_FORMAT = 326


def run(command: list[str]) -> None:
    print("  $ " + " ".join(str(c) for c in command), flush=True)
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout[-3000:])
        print(result.stderr[-3000:], file=sys.stderr)
        raise SystemExit(f"command failed: {' '.join(str(c) for c in command)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default="aditya487")
    parser.add_argument("--keep", action="store_true", help="do not delete the temp tree")
    args = parser.parse_args()

    scripts = Path(__file__).resolve().parent
    published = json.loads(urllib.request.urlopen(SUMMARY.format(user=args.user)).read())
    print(f"published summary: {published['documents']} documents, {published['pages']} pages")

    workspace = Path(tempfile.mkdtemp(prefix="cbi-fresh-"))
    print(f"workspace: {workspace}\n")
    try:
        print("1. materialise the Markdown corpus from the published Parquet")
        run([sys.executable, scripts / "materialize_markdown.py",
             "--user", args.user, "--output", workspace / "corpus"])

        print("\n2. build an index from it")
        (workspace / "index").mkdir(parents=True, exist_ok=True)
        run([sys.executable, scripts / "build_search_index.py",
             "--corpus", workspace / "corpus",
             "--corpus", workspace / "corpus" / "office",
             "--output", workspace / "index",
             "--database-name", "fresh.sqlite"])

        print("\n3. check the result")
        failures = json.loads((workspace / "index" / "index-failures.json").read_text())
        connection = sqlite3.connect(workspace / "index" / "fresh.sqlite")

        def scalar(query: str) -> int:
            return connection.execute(query).fetchone()[0] or 0

        checks = [
            ("index failures", len(failures), 0),
            ("documents", scalar("SELECT COUNT(*) FROM documents"), published["documents"]),
            ("pages", scalar("SELECT COUNT(*) FROM pages"), published["pages"]),
            ("non-default page_basis",
             scalar("SELECT COUNT(*) FROM documents WHERE page_basis != 'source-page'"),
             EXPECTED_NON_DEFAULT_PAGE_BASIS),
            ("non-pdf source_format",
             scalar("SELECT COUNT(*) FROM documents WHERE source_format != 'pdf'"),
             EXPECTED_NON_PDF_FORMAT),
        ]
        bad = []
        for label, got, want in checks:
            mark = "ok" if got == want else "FAIL"
            if got != want:
                bad.append(label)
            print(f"   {label:26} got {got:>8,}  want {want:>8,}  {mark}")

        if failures:
            print("\n   first failure:", json.dumps(failures[0])[:300])
        if bad:
            print(f"\nFAIL: {', '.join(bad)}")
            return 1
        print("\nPASS. A fresh clone can rebuild the index from the published data.")
        return 0
    finally:
        if args.keep:
            print(f"\nkept {workspace}")
        else:
            import shutil
            shutil.rmtree(workspace, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
