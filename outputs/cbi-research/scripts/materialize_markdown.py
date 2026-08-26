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

import argparse, json, sqlite3
from pathlib import Path

CORPUS = "https://huggingface.co/datasets/{user}/cbi-archive-corpus/resolve/main/data"
MANIFEST = "https://huggingface.co/datasets/{user}/cbi-archive-corpus/resolve/main/manifests"

FIELDS = ["document_id", "source_url", "source_alias_count", "source_sha256",
          "source_bytes", "page_count", "extraction_engine", "ocr_enabled",
          "quality_low_text", "quality_empty_pages"]


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
        version_column = next((c for c in ("engine_version", "pipeline_version")
                               if c in index), None)
        for row in rows:
            extra[row[index["source_sha256"]]] = {
                "source_file": row[index["source_file"]] if "source_file" in index else None,
                "engine_version": row[index[version_column]] if version_column else None,
            }
        print("  read " + name + ": " + str(len(rows)) + " rows", flush=True)

    pages = {}
    for did, number, text in connection.execute(
            "SELECT document_id, page_number, text FROM read_parquet('" + base +
            "/pages.parquet') ORDER BY document_id, page_number").fetchall():
        pages.setdefault(did, []).append((number, text))
    return documents, aliases, extra, pages


def from_local(database: Path):
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    query = ("SELECT " + ", ".join(FIELDS) +
             ", source_urls_json, source_file, extraction_engine_version FROM documents")
    documents = [dict(row) for row in connection.execute(query)]
    aliases = {d["source_sha256"]: json.loads(d["source_urls_json"] or "[]") for d in documents}
    extra = {d["source_sha256"]: {"source_file": d["source_file"],
                                 "engine_version": d["extraction_engine_version"]}
             for d in documents}
    pages = {}
    for row in connection.execute("SELECT document_id, page_number, text FROM pages "
                                  "ORDER BY document_id, page_number"):
        pages.setdefault(row["document_id"], []).append((row["page_number"], row["text"]))
    return documents, aliases, extra, pages


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default="aditya487", help="Hugging Face namespace to read from")
    parser.add_argument("--database", type=Path, help="read a local v3 SQLite index instead")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, help="stop after this many documents, for spot checks")
    args = parser.parse_args()

    if args.database:
        print("reading local index " + str(args.database), flush=True)
        documents, aliases, extra, pages = from_local(args.database)
    else:
        print("reading published Parquet for " + args.user, flush=True)
        documents, aliases, extra, pages = from_remote(args.user)

    written = thin = missing = 0
    for document in documents:
        if args.limit and written >= args.limit:
            break
        sha = document["source_sha256"]
        document_pages = pages.get(document["document_id"])
        if not document_pages:
            missing += 1
            continue
        detail = extra.get(sha, {})
        if not detail.get("source_file"):
            thin += 1
        known = sorted(set(aliases.get(sha) or [document["source_url"]]))
        text = frontmatter(document, known, detail) + body(document_pages)
        destination = args.output / sha[:2] / sha[2:4] / (sha + ".md")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text, encoding="utf-8", newline="\n")
        written += 1

    print("materialised " + str(written) + " Markdown files into " + str(args.output))
    print("  " + str(thin) + " have thinner frontmatter (no published conversion manifest row)")
    if missing:
        print("  " + str(missing) + " documents had no pages and were skipped")
    print("output is NOT byte-identical to the original conversion; see the module docstring")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
