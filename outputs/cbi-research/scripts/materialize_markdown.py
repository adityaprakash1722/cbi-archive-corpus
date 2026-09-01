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
  * The frontmatter always differs. Both published conversion manifests are
    read, covering 5,246 PDF-pipeline rows and 323 Office-pipeline rows, so
    `source_file` and engine-version metadata can be restored. A
    `materialized_from` line is added so no file can be mistaken for an
    original conversion artefact.

The page bodies themselves are exact: the same strings the index holds and the
same strings extracted from the sources. If you need byte-identical artefacts,
you need the original files, not this script.
"""
from __future__ import annotations

import argparse, csv, json, shutil, sqlite3, tempfile, urllib.request
from pathlib import Path

from release_lock import corpus_revision

CORPUS = "https://huggingface.co/datasets/{user}/cbi-archive-corpus/resolve/{revision}/data"
MANIFEST = "https://huggingface.co/datasets/{user}/cbi-archive-corpus/resolve/{revision}/manifests"

FIELDS = ["document_id", "source_url", "source_alias_count", "source_sha256",
          "source_bytes", "page_count", "extraction_engine", "ocr_enabled",
          "quality_low_text", "quality_empty_pages",
          # The indexer reads these two from the frontmatter, not the manifest,
          # and silently defaults them to "source-page" and "pdf" when they are
          # absent. Omitting them mislabels every Office and archive document.
          "page_basis", "source_format"]
OPTIONAL_FIELDS = [
    "title", "document_class", "authorship", "legacy_authorship", "host", "author_org",
    "document_role", "institutional_voice", "voice_review_status", "voice_evidence",
    "classification_basis",
    "classification_confidence", "consultation_id", "engagement_id", "published_at",
    "published_at_basis", "analysis_year", "analysis_year_basis", "retrieved_at",
    "source_page_url", "source_last_modified_at", "extraction_selection_basis",
    "alternate_extraction_count", "content_sha256", "content_cluster_id",
    "content_cluster_size",
]


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
    lines.append("source_alias_count: " + str(len(aliases) or document["source_alias_count"]))
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
    # Preserve release-level semantics as data. Re-running today's classifier
    # against an older release is not reconstruction; it is reclassification.
    for key in OPTIONAL_FIELDS:
        lines.append("published_" + key + ": " + json.dumps(document.get(key)))
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
    for page in pages:
        number, text = page[:2]
        parts.append("<!-- source-page: " + str(number) + " -->\n" +
                     '<a id="page-' + str(number) + '"></a>\n\n' + text + "\n\n")
    return "\n\n" + "".join(parts).rstrip() + "\n"


def from_remote(user: str, revision: str):
    import duckdb
    # DuckDB's HTTPS extension does not consistently discover the Windows
    # certificate store (notably behind managed TLS proxies). Python's HTTPS
    # client does. A materialisation needs every row anyway, so download the two
    # Parquet tables and three compressed manifests into a temporary verified
    # cache, then let DuckDB read the local copies. TLS verification remains on.
    cache = tempfile.TemporaryDirectory(prefix="cbi-published-")
    cache_path = Path(cache.name)
    base = CORPUS.format(user=user, revision=revision)
    manifest_base = MANIFEST.format(user=user, revision=revision)
    remote_files = {
        "documents.parquet": base + "/documents.parquet",
        "pages.parquet": base + "/pages.parquet",
        "files.csv.zst": manifest_base + "/files.csv.zst",
        "conversion-manifest.csv.zst": manifest_base + "/conversion-manifest.csv.zst",
        "conversion-manifest-office.csv.zst":
            manifest_base + "/conversion-manifest-office.csv.zst",
    }
    for name, url in remote_files.items():
        target = cache_path / name
        request = urllib.request.Request(url, headers={"User-Agent": "cbi-corpus-materializer/1"})
        with urllib.request.urlopen(request) as source, target.open("wb") as destination:
            shutil.copyfileobj(source, destination)
        print("  downloaded " + name + ": " + f"{target.stat().st_size:,}" + " bytes",
              flush=True)

    def sql_path(name: str) -> str:
        return (cache_path / name).resolve().as_posix().replace("'", "''")

    connection = duckdb.connect()
    documents_url = sql_path("documents.parquet")
    available = {row[0] for row in connection.execute(
        "DESCRIBE SELECT * FROM read_parquet('" + documents_url + "')").fetchall()}
    selected = FIELDS + [field for field in OPTIONAL_FIELDS if field in available]
    rows = connection.execute(
        "SELECT " + ", ".join(selected) + " FROM read_parquet('" + documents_url + "')"
    ).fetchall()
    documents = []
    for row in rows:
        document = {field: None for field in OPTIONAL_FIELDS}
        document.update(dict(zip(selected, row)))
        documents.append(document)

    aliases = {}
    for sha, url in connection.execute(
            "SELECT sha256, url FROM read_csv_auto('" + sql_path("files.csv.zst") +
            "') WHERE sha256 IS NOT NULL").fetchall():
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
                "SELECT * FROM read_csv_auto('" + sql_path(name) +
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

            # The two manifests record the engine version in different columns.
            # The PDF one uses `engine_version`. The Office one has no such
            # column, and its `pipeline_version` is the pipeline's version, not
            # the engine's: for the 322 Office documents the value the index
            # carries is the `engine` column, which reads like
            # "python-docx 1.2.0+xml-table-fallback". `pipeline_version` must
            # therefore come last, or the two rows that have both end up with
            # "office-0.2.0" where the canonical value is the engine string.
            version = column("engine_version") or column("engine") or column("pipeline_version")
            # Keyed by corpus as well as hash. One SHA-256 sits in both
            # manifests with a different source_file in each, a .pdf and a
            # .docx, so a hash-only key lets whichever manifest is read last
            # overwrite the other.
            # Aliases come from the manifest, not from files.csv. files.csv maps
            # every URL to its hash, so aggregating it by hash gives the union
            # across both corpora: the one document converted by both pipelines
            # was served as .pdf and .docx, and the union says two aliases where
            # each corpus canonically records one.
            urls = [u.strip() for u in (column("source_urls") or "").split("|") if u.strip()]
            extra[(sha, where)] = {
                "source_file": column("source_file"),
                "engine_version": version,
                "urls": urls or [column("url")] if column("url") else urls,
            }
            corpus_of.setdefault(sha, set()).add(where)
            manifest_rows.setdefault(where, []).append(dict(zip(columns, row)))
        print("  read " + name + ": " + str(len(rows)) + " rows", flush=True)

    pages_url = sql_path("pages.parquet")
    page_columns = {row[0] for row in connection.execute(
        "DESCRIBE SELECT * FROM read_parquet('" + pages_url + "')").fetchall()}
    page_select = "document_id, page_number, text"
    if "authorship" in page_columns:
        page_select += ", authorship"
    for field in ("authorship_basis", "institutional_voice",
                  "voice_review_status", "voice_evidence"):
        if field in page_columns:
            page_select += ", " + field
    pages = {}
    for row in connection.execute(
            "SELECT " + page_select + " FROM read_parquet('" + pages_url +
            "') ORDER BY document_id, page_number").fetchall():
        pages.setdefault(row[0], []).append(tuple(row[1:]))
    connection.close()
    cache.cleanup()
    return documents, aliases, extra, pages, corpus_of, manifest_rows


def from_local(database: Path, corpus: Path):
    """Read a local index, taking the corpus split from the local manifests.

    The obvious shortcut, reading `markdown_file` and looking for an `office/`
    prefix, does not work: every row records its path relative to its own corpus
    root, so all 5,568 begin with `markdown/` and the split is invisible. Taking
    it from the two manifests is both correct and the same rule the remote path
    uses.
    """
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    document_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(documents)")
    }
    required = set(FIELDS + ["source_urls_json", "source_sha256"])
    missing_required = sorted(required - document_columns)
    if missing_required:
        raise ValueError(
            "local index lacks required document columns: " + ", ".join(missing_required))
    selected = FIELDS + [field for field in OPTIONAL_FIELDS if field in document_columns]
    selected += [field for field in
                 ("source_urls_json", "source_file", "extraction_engine_version", "markdown_file")
                 if field in document_columns]
    documents = []
    for row in connection.execute("SELECT " + ", ".join(selected) + " FROM documents"):
        document = {field: None for field in OPTIONAL_FIELDS}
        document.update(dict(row))
        document.setdefault("source_urls_json", "[]")
        documents.append(document)
    aliases = {d["source_sha256"]: json.loads(d["source_urls_json"] or "[]") for d in documents}

    extra: dict = {}
    corpus_of: dict = {}
    manifest_rows: dict = {}
    csv.field_size_limit(1 << 27)
    for where, path in (("pdf", corpus / "conversion-manifest.csv"),
                        ("office", corpus / "office" / "conversion-manifest.csv")):
        if not path.is_file():
            print("  no manifest at " + str(path) + ", skipped", flush=True)
            continue
        with path.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(line.replace("\x00", "") for line in stream))
        for row in rows:
            sha = row["source_sha256"]
            urls = [u.strip() for u in (row.get("source_urls") or "").split("|") if u.strip()]
            corpus_of.setdefault(sha, set()).add(where)
            extra[(sha, where)] = {
                "source_file": row.get("source_file"),
                "engine_version": (row.get("engine_version") or row.get("engine")
                                   or row.get("pipeline_version")),
                "urls": urls or ([row["url"]] if row.get("url") else []),
            }
            manifest_rows.setdefault(where, []).append(row)
        print("  read " + str(path) + ": " + str(len(rows)) + " rows", flush=True)

    page_columns = {row[1] for row in connection.execute("PRAGMA table_info(pages)")}
    page_select = ["document_id", "page_number", "text"]
    page_select += [field for field in ("authorship", "authorship_basis",
                                        "institutional_voice", "voice_review_status",
                                        "voice_evidence")
                    if field in page_columns]
    document_authorship = {d["document_id"]: d.get("authorship") for d in documents}
    document_voice = {d["document_id"]: d.get("institutional_voice") for d in documents}
    pages = {}
    for row in connection.execute(
            "SELECT " + ", ".join(page_select) + " FROM pages "
            "ORDER BY document_id, page_number"):
        page_authorship = (row["authorship"] if "authorship" in page_columns
                           else document_authorship.get(row["document_id"]))
        page_basis = (row["authorship_basis"] if "authorship_basis" in page_columns
                      else "document-level-authorship")
        page_voice = (row["institutional_voice"] if "institutional_voice" in page_columns
                      else document_voice.get(row["document_id"]))
        review_status = (row["voice_review_status"] if "voice_review_status" in page_columns
                         else "unreviewed")
        evidence = (row["voice_evidence"] if "voice_evidence" in page_columns
                    else page_basis)
        pages.setdefault(row["document_id"], []).append(
            (row["page_number"], row["text"], page_authorship, page_basis,
             page_voice, review_status, evidence))
    return documents, aliases, extra, pages, corpus_of, manifest_rows


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
            writer = csv.DictWriter(
                stream, fieldnames=list(rows[0].keys()), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        print("  wrote " + str(target) + ": " + str(len(rows)) + " rows", flush=True)


def write_extraction_preferences(output: Path, documents: list[dict],
                                 corpus_of: dict[str, set[str]]) -> None:
    """Preserve which duplicate extraction the published release selected.

    The current public release selected the .pdf alias; the corrected release
    selects the canonical .docx. A materialiser must reproduce whichever
    release it is reading rather than silently applying today's preference to
    yesterday's data.
    """
    rows = []
    by_sha = {document["source_sha256"]: document for document in documents}
    for sha, corpora in corpus_of.items():
        if len(corpora) < 2:
            continue
        document = by_sha[sha]
        url_path = document["source_url"].split("?", 1)[0].casefold()
        preferred = "office" if url_path.endswith((".docx", ".doc", ".pptx", ".zip")) else "pdf"
        rows.append({
            "source_sha256": sha,
            "preferred_corpus": preferred,
            "basis": "published-release-selection",
            "notes": "Generated from the canonical source_url in documents.parquet.",
        })
    if not rows:
        return
    target = output / "extraction-preferences.csv"
    with target.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print("  wrote " + str(target) + ": " + str(len(rows)) + " rows", flush=True)


def write_page_authorship(output: Path, documents: list[dict], pages: dict) -> None:
    """Materialise contiguous page-voice ranges for mixed documents."""
    rows = []
    for document in documents:
        if document.get("authorship") != "mixed":
            continue
        values = pages.get(document["document_id"], [])
        if not values or len(values[0]) < 4:
            raise ValueError("published mixed document lacks page-level authorship")
        start = previous = values[0][0]
        authorship, basis = values[0][2], values[0][3]
        voice = values[0][4] if len(values[0]) > 4 else None
        status = values[0][5] if len(values[0]) > 5 else "manual-reviewed"
        evidence = values[0][6] if len(values[0]) > 6 else basis
        for value in values[1:]:
            number, current_authorship, current_basis = value[0], value[2], value[3]
            current_voice = value[4] if len(value) > 4 else None
            current_status = value[5] if len(value) > 5 else "manual-reviewed"
            current_evidence = value[6] if len(value) > 6 else current_basis
            if ((current_authorship, current_basis, current_voice, current_status, current_evidence) !=
                    (authorship, basis, voice, status, evidence)):
                rows.append({"source_sha256": document["source_sha256"],
                             "start_page": start, "end_page": previous,
                             "authorship": authorship, "basis": basis,
                             "institutional_voice": voice, "review_status": status,
                             "review_evidence": evidence})
                start = number
                authorship, basis = current_authorship, current_basis
                voice, status, evidence = current_voice, current_status, current_evidence
            previous = number
        rows.append({"source_sha256": document["source_sha256"],
                     "start_page": start, "end_page": previous,
                     "authorship": authorship, "basis": basis,
                     "institutional_voice": voice, "review_status": status,
                     "review_evidence": evidence})
    target = output / "page-authorship-overrides.csv"
    fields = ["source_sha256", "start_page", "end_page", "authorship", "basis",
              "institutional_voice", "review_status", "review_evidence"]
    with target.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print("  wrote " + str(target) + ": " + str(len(rows)) + " rows", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default="aditya487", help="Hugging Face namespace to read from")
    parser.add_argument("--revision", default=corpus_revision(),
                        help="immutable HF corpus revision (defaults to RELEASE.lock.json)")
    parser.add_argument("--database", type=Path, help="read a local SQLite index instead")
    parser.add_argument("--corpus", type=Path,
                        default=Path("outputs/cbi-research/corpus"),
                        help="with --database, where the local conversion manifests live")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, help="stop after this many documents, for spot checks")
    args = parser.parse_args()

    if args.database:
        print("reading local index " + str(args.database), flush=True)
        documents, aliases, extra, pages, corpus_of, manifest_rows = from_local(
            args.database, args.corpus)
    else:
        print("reading published Parquet for " + args.user, flush=True)
        documents, aliases, extra, pages, corpus_of, manifest_rows = from_remote(
            args.user, args.revision)

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
        fallback_aliases = aliases.get(sha) or [document["source_url"]]
        # The two corpora are indexed separately, so each document has to land in
        # the one its manifest describes. One SHA-256 appears in both manifests,
        # having been converted by both pipelines, and it needs a file in each:
        # that is why the original corpus holds 5,569 files for 5,568 documents.
        for where in sorted(corpus_of.get(sha) or {"pdf"}):
            detail = extra.get((sha, where), {})
            if not detail.get("source_file"):
                thin += 1
            known = sorted(set(detail.get("urls") or fallback_aliases))
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
        write_extraction_preferences(args.output, documents, corpus_of)
        write_page_authorship(args.output, documents, pages)

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
