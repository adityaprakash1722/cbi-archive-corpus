#!/usr/bin/env python3
r"""Materialise the page-anchored Markdown corpus from the published Parquet.

    python outputs\cbi-research\scripts\materialize_markdown.py --output work\markdown
    python outputs\cbi-research\scripts\materialize_markdown.py --database <v3.sqlite> --output work\markdown

Why this exists
---------------
The Markdown corpus (5,569 files, 202 MB) is deliberately not published: its text
goes out as `pages.parquet` instead, which is a better shape for analysis and a
third of the size. That leaves one hole. `make index` reads the Markdown, so a
fresh clone could not rebuild the index at all: the only copy of the Markdown was
on the maintainer's disk.

This closes that hole by regenerating the Markdown from what is published.

Materialise, not rebuild
------------------------
`markdown_sha256` from the conversion manifest will not match what this writes,
so this is materialisation rather than reconstruction. Measured against the
original corpus, document by document:

  * The page region, meaning everything from the first `<!-- source-page: -->`
    marker onward, comes out **byte-identical for 5,550 of 5,568 documents**.
  * The 18 that differ do so only in carriage returns. The index strips `\r`
    on ingest (zero pages corpus-wide contain one), so a source that carried
    Windows line endings inside its extracted text cannot get them back. 16 of
    the 18 are members of ZIP archives, which is where such text tends to live.
  * The frontmatter always differs. `documents.parquet` drops four fields the
    original carried: `source_file`, `extraction_engine_version`,
    `extraction_pipeline_version` and `markdown_sha256`. Two are recoverable
    from the published conversion manifest, but that manifest covers the 5,246
    PDFs only, so the 322 Office documents get thinner frontmatter until it is
    published too. A `materialized_from` line is added so no file can be
    mistaken for an original.

The page bodies themselves are exact: the same strings the index holds and the
same strings extracted from the sources. If you need byte-identical artefacts,
you need the original files, not this script.
"""
from __future__ import annotations

import argparse, csv, json, sqlite3
from pathlib import Path

CORPUS = "https://huggingface.co/datasets/{user}/cbi-archive-corpus/resolve/main/data"
MANIFEST = "https://huggingface.co/datasets/{user}/cbi-archive-corpus/resolve/main/manifests"

FIELDS = ["document_id", "source_url", "source_alias_count", "source_sha256",
          "source_bytes", "page_count", "extraction_engine", "ocr_enabled",
          "quality_low_text", "quality_empty_pages",
          # The indexer reads these two from the frontmatter, not the manifest,
          # and silently defaults them to "source-page" and "pdf" when they are
          # absent. Omitting them mislabels every Office and archive document.
          "page_basis", "source_format"]


def yaml_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if value is None:
        return '""'
    return json.dumps(str(value))


def frontmatter(document: dict, aliases: list, extra: dict) -> str:
    lines = ["---"]
    lines.append("document_id: " + yaml_value(document["document_id"]))
    lines.append("source_url: " + yaml_value(document["source_url"]))
    lines.append("source_urls: " + json.dumps(aliases))
    lines.append("source_alias_count: " + str(document["source_alias_count"]))
    if extra.get("source_file"):
        lines.append("source_file: " + yaml_value(extra["source_file"]))
    lines.append("source_sha256: " + yaml_value(document["source_sha256"]))
    lines.append("source_bytes: " + str(document["source_bytes"]))
    lines.append("source_pages: " + str(document["page_count"]))
    lines.append("extraction_engine: " + yaml_value(document["extraction_engine"]))
    if extra.get("engine_version"):
        lines.append("extraction_engine_version: " + yaml_value(extra["engine_version"]))
    lines.append("detected_source_format: " + yaml_value(document["source_format"]))
    lines.append("page_basis: " + yaml_value(document["page_basis"]))
    lines.append("ocr_enabled: " + yaml_value(bool(document["ocr_enabled"])))
    lines.append("quality_low_text: " + yaml_value(bool(document["quality_low_text"])))
    lines.append("quality_empty_pages: " + str(document["quality_empty_pages"]))
    lines.append("materialized_from: " + json.dumps(
        "documents.parquet + pages.parquet; not byte-identical to the original conversion"))
    lines.append("---")
    return "\n".join(lines)


def body(pages: list) -> str:
    """Reassemble the page bodies using the original conversion's spacing.

    Every page is marker, anchor, blank line, text, blank line. Doing it that
    way rather than joining pages with separators is what makes empty pages come
    out right: they contribute their anchor and two blank lines, which is
    exactly what the converter wrote. The trailing run is then trimmed to a
    single newline, since the converter ends every file that way.
    """
    parts = []
    for number, text in pages:
        parts.append("<!-- source-page: " + str(number) + " -->\n" +
                     '<a id="page-' + str(number) + '"></a>\n\n' + text + "\n\n")
    return "\n\n" + "".join(parts).rstrip() + "\n"


def from_remote(user: str):
    import duckdb
    connection = duckdb.connect()
    connection.execute("INSTALL httpfs; LOAD httpfs;")
    base = CORPUS.format(user=user)
    manifests = MANIFEST.format(user=user)
    rows = connection.execute(
        "SELECT " + ", ".join(FIELDS) + " FROM read_parquet('" + base + "/documents.parquet')"
    ).fetchall()
    documents = [dict(zip(FIELDS, row)) for row in rows]

    aliases = {}
    for sha, url in connection.execute(
            "SELECT sha256, url FROM read_csv_auto('" + manifests +
            "/files.csv.zst') WHERE sha256 IS NOT NULL").fetchall():
        aliases.setdefault(sha, []).append(url)

    # Both conversion manifests. The PDF one covers 5,246 documents and the
    # Office one the remaining 323; reading only the first leaves the Office
    # corpus without source_file in its frontmatter.
    #
    # The two do not share a schema. The PDF manifest records `engine_version`,
    # the Office one records `pipeline_version` instead, so the columns are
    # matched by name rather than by position.
    extra = {}
    # Which of the two corpora each document belongs to. The indexer is given
    # corpus/ and corpus/office/ separately, each with its own manifest, so a
    # document written to the wrong one is simply not indexed.
    corpus_of = {}
    manifest_rows = {}
    for name in ("conversion-manifest.csv.zst", "conversion-manifest-office.csv.zst"):
        try:
            cursor = connection.execute(
                "SELECT * FROM read_csv_auto('" + manifests + "/" + name +
                "', all_varchar=true)")
            columns = [d[0] for d in cursor.description]
            rows = cursor.fetchall()
        except Exception as exc:
            print("  could not read " + name + ": " + str(exc).split("\n")[0], flush=True)
            continue
        if "source_sha256" not in columns:
            print("  " + name + " has no source_sha256 column, skipped", flush=True)
            continue
        index = {c: i for i, c in enumerate(columns)}
        where = "office" if "office" in name else "pdf"
        for row in rows:
            sha = row[index["source_sha256"]]

            def column(name_: str):
                position = index.get(name_)
                return row[position] if position is not None else None

            # The two manifests record the engine version in different columns,
            # and the Office one records it nowhere useful: `engine_version` is
            # absent and `pipeline_version` is blank, while the value the index
            # carries is the engine name itself. Fall through all three.
            version = column("engine_version") or column("pipeline_version") or column("engine")
            # Keyed by corpus as well as hash. One SHA-256 sits in both
            # manifests with a different source_file in each, a .pdf and a
            # .docx, so a hash-only key lets whichever manifest is read last
            # overwrite the other.
            extra[(sha, where)] = {
                "source_file": column("source_file"),
                "engine_version": version,
            }
            corpus_of.setdefault(sha, set()).add(where)
            manifest_rows.setdefault(where, []).append(dict(zip(columns, row)))
        print("  read " + name + ": " + str(len(rows)) + " rows", flush=True)

    pages = {}
    for did, number, text in connection.execute(
            "SELECT document_id, page_number, text FROM read_parquet('" + base +
            "/pages.parquet') ORDER BY document_id, page_number").fetchall():
        pages.setdefault(did, []).append((number, text))
    return documents, aliases, extra, pages, corpus_of, manifest_rows


def from_local(database: Path):
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    query = ("SELECT " + ", ".join(FIELDS) +
             ", source_urls_json, source_file, extraction_engine_version, markdown_file "
             "FROM documents")
    documents = [dict(row) for row in connection.execute(query)]
    aliases = {d["source_sha256"]: json.loads(d["source_urls_json"] or "[]") for d in documents}
    extra = {}
    # Locally the split is recoverable from the recorded Markdown path: the
    # Office pipeline writes under corpus/office.
    corpus_of = {}
    for d in documents:
        path = (d.get("markdown_file") or "").replace("\\", "/")
        where = "office" if path.startswith("office/") else "pdf"
        corpus_of.setdefault(d["source_sha256"], set()).add(where)
        extra[(d["source_sha256"], where)] = {
            "source_file": d["source_file"],
            "engine_version": d["extraction_engine_version"],
        }
    pages = {}
    for row in connection.execute("SELECT document_id, page_number, text FROM pages "
                                  "ORDER BY document_id, page_number"):
        pages.setdefault(row["document_id"], []).append((row["page_number"], row["text"]))
    return documents, aliases, extra, pages, corpus_of, {}


def write_manifests(output: Path, manifest_rows: dict) -> None:
    """Put each conversion manifest where the indexer looks for it.

    `make index` is handed corpus/ and corpus/office/ and reads
    conversion-manifest.csv from each. Materialising the Markdown without these
    leaves the tree unindexable, which is the whole point of materialising it.
    """
    for where, rows in manifest_rows.items():
        if not rows:
            continue
        target = (output / "conversion-manifest.csv" if where == "pdf"
                  else output / "office" / "conversion-manifest.csv")
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print("  wrote " + str(target) + ": " + str(len(rows)) + " rows", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default="aditya487", help="Hugging Face namespace to read from")
    parser.add_argument("--database", type=Path, help="read a local v3 SQLite index instead")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, help="stop after this many documents, for spot checks")
    args = parser.parse_args()

    if args.database:
        print("reading local index " + str(args.database), flush=True)
        documents, aliases, extra, pages, corpus_of, manifest_rows = from_local(args.database)
    else:
        print("reading published Parquet for " + args.user, flush=True)
        documents, aliases, extra, pages, corpus_of, manifest_rows = from_remote(args.user)

    written = thin = missing = files = 0
    counts = {"pdf": 0, "office": 0}
    for document in documents:
        if args.limit and written >= args.limit:
            break
        sha = document["source_sha256"]
        document_pages = pages.get(document["document_id"])
        if not document_pages:
            missing += 1
            continue
        known = sorted(set(aliases.get(sha) or [document["source_url"]]))
        # The two corpora are indexed separately, so each document has to land in
        # the one its manifest describes. One SHA-256 appears in both manifests,
        # having been converted by both pipelines, and it needs a file in each:
        # that is why the original corpus holds 5,569 files for 5,568 documents.
        for where in sorted(corpus_of.get(sha) or {"pdf"}):
            detail = extra.get((sha, where), {})
            if not detail.get("source_file"):
                thin += 1
            text = frontmatter(document, known, detail) + body(document_pages)
            counts[where] += 1
            root = args.output if where == "pdf" else args.output / "office"
            destination = root / "markdown" / sha[:2] / sha[2:4] / (sha + ".md")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(text, encoding="utf-8", newline="\n")
            files += 1
        written += 1

    if manifest_rows and not args.limit:
        write_manifests(args.output, manifest_rows)

    print("materialised " + str(written) + " documents as " + str(files) +
          " Markdown files into " + str(args.output))
    print("  " + str(counts["pdf"]) + " under markdown/, "
          + str(counts["office"]) + " under office/markdown/")
    print("  " + str(thin) + " have thinner frontmatter (no published conversion manifest row)")
    if missing:
        print("  " + str(missing) + " documents had no pages and were skipped")
    print("output is NOT byte-identical to the original conversion; see the module docstring")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
