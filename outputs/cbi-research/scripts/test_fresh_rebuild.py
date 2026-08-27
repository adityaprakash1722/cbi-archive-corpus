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

import argparse, csv, json, sqlite3, subprocess, sys, tempfile, urllib.request
from pathlib import Path

SUMMARY = ("https://huggingface.co/datasets/{user}/cbi-archive-corpus"
           "/resolve/main/data/dataset-summary.json")

# Structural facts a correct rebuild must reproduce. Counts that come from the
# published summary are checked against it rather than hardcoded; these are the
# ones the summary does not carry.
EXPECTED_NON_DEFAULT_PAGE_BASIS = 320
EXPECTED_NON_PDF_FORMAT = 326


# Every column the published documents.parquet carries. Comparing a hand-picked
# subset is how the last two rounds of defects survived a passing test: the
# columns nobody thought to list were exactly the ones that were wrong.
COMPARED_COLUMNS = ["title", "authorship", "classification_basis",
                    "classification_confidence", "page_basis", "source_format",
                    "document_class", "consultation_id", "page_count",
                    "extraction_engine", "ocr_enabled", "source_url",
                    "source_alias_count", "source_bytes", "source_sha256",
                    "pdf_author", "pdf_creation_date", "quality_low_text",
                    "quality_empty_pages"]


def page_text_mismatches(connection, user: str) -> int:
    """Compare every page row, text included, against the published pages table.

    The document table is not the corpus. A rebuild could match all nineteen
    document columns and still hand back different text, and until this existed
    nothing in CI would have noticed. It is the expensive check, roughly 190
    million characters on each side, and it is the one that actually protects
    the thing the corpus is for.
    """
    try:
        import duckdb
    except ImportError:
        print("   (duckdb not installed, skipping the page comparison)")
        return 0
    remote = duckdb.connect()
    remote.execute("INSTALL httpfs; LOAD httpfs;")
    url = ("https://huggingface.co/datasets/" + user +
           "/cbi-archive-corpus/resolve/main/data/pages.parquet")
    published = {
        (row[0], row[1]): (row[2], row[3]) for row in remote.execute(
            "SELECT document_id, page_number, text, characters "
            "FROM read_parquet('" + url + "')").fetchall()}
    mismatched = 0
    seen = 0
    for did, number, text, characters in connection.execute(
            "SELECT document_id, page_number, text, characters FROM pages"):
        seen += 1
        want = published.get((did, number))
        if want is None or (text or "") != (want[0] or "") or characters != want[1]:
            mismatched += 1
    if seen != len(published):
        mismatched += abs(seen - len(published))
    return mismatched


def manifest_mismatches(connection, field: str) -> int:
    """Compare a rebuilt column against the tracked conversion manifests.

    `extraction_engine_version` and `source_file` are dropped from the published
    Parquet, so the published data cannot referee them. The manifests can, and
    both of these were wrong in a rebuild that a passing test had blessed: the
    engine version because the Office manifest records it in a different column
    from the PDF one, and source_file because the one hash present in both
    manifests was keyed without regard to which corpus it came from.
    """
    manifests = Path(__file__).resolve().parents[1] / "corpus"
    csv.field_size_limit(1 << 27)
    canonical: dict[str, str] = {}
    for path in (manifests / "conversion-manifest.csv",
                 manifests / "office" / "conversion-manifest.csv"):
        if not path.is_file():
            continue
        with path.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(line.replace("\x00", "") for line in stream):
                value = (row.get(field) or row.get("engine") if field == "engine_version"
                         else row.get(field))
                # First writer wins, matching how the indexer dedupes by hash.
                canonical.setdefault(row["source_sha256"], value or "")
    column = "extraction_engine_version" if field == "engine_version" else field
    mismatched = 0
    for sha, got in connection.execute(
            "SELECT source_sha256, " + column + " FROM documents"):
        want = canonical.get(sha)
        if want is not None and (got or "") != want:
            mismatched += 1
    return mismatched


def untitled_in_published(user: str) -> int:
    """How many published documents carry no title, so the rebuild can match it."""
    try:
        import duckdb
    except ImportError:
        return 0
    remote = duckdb.connect()
    remote.execute("INSTALL httpfs; LOAD httpfs;")
    url = ("https://huggingface.co/datasets/" + user +
           "/cbi-archive-corpus/resolve/main/data/documents.parquet")
    return remote.execute(
        "SELECT COUNT(*) FROM read_parquet('" + url + "') "
        "WHERE title IS NULL OR trim(title) = ''").fetchone()[0]


def compare_against_published(connection, user: str):
    """Compare the rebuilt index row by row against the published documents table."""
    try:
        import duckdb
    except ImportError:
        print("   (duckdb not installed, skipping the column comparison)")
        return []
    remote = duckdb.connect()
    remote.execute("INSTALL httpfs; LOAD httpfs;")
    url = ("https://huggingface.co/datasets/" + user +
           "/cbi-archive-corpus/resolve/main/data/documents.parquet")
    published = {
        row[0]: row[1:] for row in remote.execute(
            "SELECT document_id, " + ", ".join(COMPARED_COLUMNS) +
            " FROM read_parquet('" + url + "')").fetchall()}
    local = {
        row[0]: row[1:] for row in connection.execute(
            "SELECT document_id, " + ", ".join(COMPARED_COLUMNS) + " FROM documents")}
    results = []
    for position, column in enumerate(COMPARED_COLUMNS):
        differing = sum(
            1 for did, values in published.items()
            if did in local and str(local[did][position]) != str(values[position]))
        results.append((column, differing))
    missing = len(set(published) - set(local))
    if missing:
        results.append(("documents absent from rebuild", missing))
    return results


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
        # The audit CSV is tracked in git and `make index` passes it. Without it
        # the build still succeeds but every title falls back to a heading or the
        # URL, so a test that omits it proves less than the real build does.
        audit = scripts.parent / "audit" / "pdf-audit.csv"
        command = [sys.executable, scripts / "build_search_index.py",
                   "--corpus", workspace / "corpus",
                   "--corpus", workspace / "corpus" / "office",
                   "--output", workspace / "index",
                   "--database-name", "fresh.sqlite"]
        if audit.is_file():
            command += ["--audit-csv", audit]
        else:
            print(f"   WARNING: {audit} missing, titles will not be checked")
        run(command)

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
            # Metadata the earlier version of this test never looked at. Each of
            # these was silently wrong at some point and nothing caught it.
            #
            # Titles are compared against the published count rather than zero:
            # 33 documents are genuinely untitled at source, and asserting an
            # ideal instead of the actual target is how a test fails on correct
            # output. source_file and engine_version are not in the published
            # Parquet at all, so those two are absolute.
            ("documents missing a title",
             scalar("SELECT COUNT(*) FROM documents WHERE title IS NULL OR trim(title)=''"),
             untitled_in_published(args.user)),
            ("documents missing source_file",
             scalar("SELECT COUNT(*) FROM documents WHERE source_file IS NULL OR trim(source_file)=''"), 0),
            ("documents missing engine version",
             scalar("SELECT COUNT(*) FROM documents WHERE extraction_engine_version IS NULL "
                    "OR trim(extraction_engine_version)=''"), 0),
            # extraction_engine_version and source_file are not in the published
            # Parquet, so they cannot be compared against it. They are compared
            # against the tracked manifests instead, which is where a rebuild
            # gets them and where both were silently wrong.
            ("engine versions differing from the manifests",
             manifest_mismatches(connection, "engine_version"), 0),
            ("source_file differing from the manifests",
             manifest_mismatches(connection, "source_file"), 0),
            # The whole point of the corpus. 88,782 rows, text included.
            ("page rows differing from published",
             page_text_mismatches(connection, args.user), 0),
            # markdown_sha256 is deliberately NOT checked here. It records the
            # hash of the original conversion, and the materialised Markdown is
            # documented as not byte-identical to that, so it can never match in
            # a rebuild. The invariant that caught the real stale-hash bug is
            # "the index agrees with the local corpus", which needs the corpus
            # and so lives in check_manifest_invariants.py.
        ]

        # Column-by-column comparison against the published Parquet, which is the
        # thing a fresh clone is actually trying to reproduce.
        compared = compare_against_published(connection, args.user)

        bad = []
        for label, got, want in checks:
            mark = "ok" if got == want else "FAIL"
            if got != want:
                bad.append(label)
            print(f"   {label:30} got {got:>8,}  want {want:>8,}  {mark}")
        for label, differing in compared:
            mark = "ok" if differing == 0 else "FAIL"
            if differing:
                bad.append(label)
            print(f"   {label:30} {differing:>8,} differing rows          {mark}")

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
