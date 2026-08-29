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

import argparse, csv, json, shutil, sqlite3, subprocess, sys, tempfile, urllib.request
from pathlib import Path

from release_lock import corpus_revision

SUMMARY = ("https://huggingface.co/datasets/{user}/cbi-archive-corpus"
           "/resolve/{revision}/data/dataset-summary.json")

def sql_parquet(path: Path) -> str:
    """Return a DuckDB read_parquet expression for a verified local download."""
    escaped = path.resolve().as_posix().replace("'", "''")
    return "read_parquet('" + escaped + "')"


def download(url: str, target: Path) -> None:
    """Download through Python's verified HTTPS client for Windows portability."""
    target.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "cbi-fresh-rebuild-test/1"})
    with urllib.request.urlopen(request) as source, target.open("wb") as destination:
        shutil.copyfileobj(source, destination)


def remote_scalar(documents: Path, query: str) -> int:
    """Evaluate one scalar against a verified copy of the pinned table."""
    import duckdb
    remote = duckdb.connect()
    return remote.execute(query.replace("{documents}", sql_parquet(documents))).fetchone()[0]


def page_row_mismatches(connection, pages: Path) -> tuple[int, list[str]]:
    """Compare every common page column against the published pages table.

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
    table = sql_parquet(pages)
    remote_columns = [row[0] for row in remote.execute(
        "DESCRIBE SELECT * FROM " + table).fetchall()]
    local_columns = [row[1] for row in connection.execute("PRAGMA table_info(pages)")]
    columns = [column for column in remote_columns if column in local_columns]
    required = {"document_id", "page_number", "text", "characters"}
    if not required.issubset(columns):
        missing = sorted(required - set(columns))
        raise RuntimeError("page comparison lacks required columns: " + ", ".join(missing))
    value_columns = [column for column in columns
                     if column not in ("document_id", "page_number")]
    select = "document_id, page_number, " + ", ".join(value_columns)
    published = {
        (row[0], row[1]): row[2:] for row in remote.execute(
            "SELECT " + select + " FROM " + table).fetchall()}
    mismatched = 0
    seen = 0
    for row in connection.execute("SELECT " + select + " FROM pages"):
        did, number, values = row[0], row[1], row[2:]
        seen += 1
        want = published.get((did, number))
        if want is None or tuple(values) != tuple(want):
            mismatched += 1
    if seen != len(published):
        mismatched += abs(seen - len(published))
    return mismatched, ["document_id", "page_number"] + value_columns


def manifest_mismatches(connection, field: str, manifests: Path,
                        preferences: Path) -> int:
    """Compare a rebuilt column against the tracked conversion manifests.

    `extraction_engine_version` and `source_file` are dropped from the published
    Parquet, so the published data cannot referee them. The manifests can, and
    both of these were wrong in a rebuild that a passing test had blessed: the
    engine version because the Office manifest records it in a different column
    from the PDF one, and source_file because the one hash present in both
    manifests was keyed without regard to which corpus it came from.
    """
    csv.field_size_limit(1 << 27)
    preferred = {}
    if preferences.is_file():
        with preferences.open(encoding="utf-8-sig", newline="") as stream:
            preferred = {row["source_sha256"]: row["preferred_corpus"]
                         for row in csv.DictReader(stream)}
    candidates: dict[str, dict[str, str]] = {}
    for corpus_name, path in (("pdf", manifests / "conversion-manifest.csv"),
                              ("office", manifests / "office" / "conversion-manifest.csv")):
        if not path.is_file():
            continue
        with path.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(line.replace("\x00", "") for line in stream):
                value = ((row.get(field) or row.get("engine") or row.get("pipeline_version"))
                         if field == "engine_version" else row.get(field))
                candidates.setdefault(row["source_sha256"], {})[corpus_name] = value or ""
    canonical = {}
    for sha, by_corpus in candidates.items():
        if len(by_corpus) == 1:
            canonical[sha] = next(iter(by_corpus.values()))
        else:
            choice = preferred.get(sha)
            if choice not in by_corpus:
                raise RuntimeError("duplicate manifest row has no valid extraction preference: " + sha)
            canonical[sha] = by_corpus[choice]
    column = "extraction_engine_version" if field == "engine_version" else field
    mismatched = 0
    for sha, got in connection.execute(
            "SELECT source_sha256, " + column + " FROM documents"):
        want = canonical.get(sha)
        if want is not None and (got or "") != want:
            mismatched += 1
    return mismatched


def untitled_in_published(documents: Path) -> int:
    """How many published documents carry no title, so the rebuild can match it."""
    try:
        import duckdb
    except ImportError:
        return 0
    remote = duckdb.connect()
    return remote.execute(
        "SELECT COUNT(*) FROM " + sql_parquet(documents) + " "
        "WHERE title IS NULL OR trim(title) = ''").fetchone()[0]


def compare_against_published(connection, documents: Path):
    """Compare the rebuilt index row by row against the published documents table."""
    try:
        import duckdb
    except ImportError:
        print("   (duckdb not installed, skipping the column comparison)")
        return []
    remote = duckdb.connect()
    table = sql_parquet(documents)
    remote_columns = [row[0] for row in remote.execute(
        "DESCRIBE SELECT * FROM " + table).fetchall()]
    local_columns = {row[1] for row in connection.execute("PRAGMA table_info(documents)")}
    compared_columns = [column for column in remote_columns
                        if column != "document_id" and column in local_columns]
    missing_columns = [column for column in remote_columns
                       if column != "document_id" and column not in local_columns]
    published = {
        row[0]: row[1:] for row in remote.execute(
            "SELECT document_id, " + ", ".join(compared_columns) +
            " FROM " + table).fetchall()}
    local = {
        row[0]: row[1:] for row in connection.execute(
            "SELECT document_id, " + ", ".join(compared_columns) + " FROM documents")}
    results = []
    for column in missing_columns:
        results.append(("missing published column: " + column, len(published)))
    for position, column in enumerate(compared_columns):
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
    parser.add_argument("--revision", default=corpus_revision(),
                        help="immutable HF revision (defaults to RELEASE.lock.json)")
    parser.add_argument("--keep", action="store_true", help="do not delete the temp tree")
    args = parser.parse_args()

    scripts = Path(__file__).resolve().parent
    published = json.loads(urllib.request.urlopen(
        SUMMARY.format(user=args.user, revision=args.revision)).read())
    print(f"published summary: {published['documents']} documents, {published['pages']} pages")

    workspace = Path(tempfile.mkdtemp(prefix="cbi-fresh-"))
    print(f"workspace: {workspace}\n")
    try:
        print("1. materialise the Markdown corpus from the published Parquet")
        run([sys.executable, scripts / "materialize_markdown.py",
             "--user", args.user, "--revision", args.revision,
             "--output", workspace / "corpus"])

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
                   "--database-name", "fresh.sqlite",
                   "--page-authorship-csv", workspace / "corpus" / "page-authorship-overrides.csv",
                   "--extraction-preferences-csv", workspace / "corpus" / "extraction-preferences.csv"]
        if audit.is_file():
            command += ["--audit-csv", audit]
        else:
            print(f"   WARNING: {audit} missing, titles will not be checked")
        run(command)

        print("\n3. check the result")
        failures = json.loads((workspace / "index" / "index-failures.json").read_text())
        connection = sqlite3.connect(workspace / "index" / "fresh.sqlite")

        print("   downloading pinned Parquet for row-by-row comparison")
        published_dir = workspace / "published"
        documents_parquet = published_dir / "documents.parquet"
        pages_parquet = published_dir / "pages.parquet"
        data_url = ("https://huggingface.co/datasets/" + args.user +
                    "/cbi-archive-corpus/resolve/" + args.revision + "/data/")
        download(data_url + "documents.parquet", documents_parquet)
        download(data_url + "pages.parquet", pages_parquet)

        def scalar(query: str) -> int:
            return connection.execute(query).fetchone()[0] or 0

        expected_non_default_page_basis = remote_scalar(
            documents_parquet,
            "SELECT COUNT(*) FROM {documents} WHERE page_basis != 'source-page'")
        expected_non_pdf = remote_scalar(
            documents_parquet,
            "SELECT COUNT(*) FROM {documents} WHERE source_format != 'pdf'")
        page_mismatches, compared_page_columns = page_row_mismatches(
            connection, pages_parquet)
        checks = [
            ("index failures", len(failures), 0),
            ("documents", scalar("SELECT COUNT(*) FROM documents"), published["documents"]),
            ("pages", scalar("SELECT COUNT(*) FROM pages"), published["pages"]),
            ("non-default page_basis",
             scalar("SELECT COUNT(*) FROM documents WHERE page_basis != 'source-page'"),
             expected_non_default_page_basis),
            ("non-pdf source_format",
             scalar("SELECT COUNT(*) FROM documents WHERE source_format != 'pdf'"),
             expected_non_pdf),
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
             untitled_in_published(documents_parquet)),
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
             manifest_mismatches(connection, "engine_version", workspace / "corpus",
                                 workspace / "corpus" / "extraction-preferences.csv"), 0),
            ("source_file differing from the manifests",
             manifest_mismatches(connection, "source_file", workspace / "corpus",
                                 workspace / "corpus" / "extraction-preferences.csv"), 0),
            # The whole point of the corpus: every published page row, text and
            # page-level provenance included.
            ("page rows differing from published",
             page_mismatches, 0),
            # markdown_sha256 is deliberately NOT checked here. It records the
            # hash of the original conversion, and the materialised Markdown is
            # documented as not byte-identical to that, so it can never match in
            # a rebuild. The invariant that caught the real stale-hash bug is
            # "the index agrees with the local corpus", which needs the corpus
            # and so lives in check_manifest_invariants.py.
        ]

        # Column-by-column comparison against the published Parquet, which is the
        # thing a fresh clone is actually trying to reproduce.
        compared = compare_against_published(connection, documents_parquet)
        print("   page columns compared: " + ", ".join(compared_page_columns))

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
