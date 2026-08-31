#!/usr/bin/env python3
"""Build a page-addressable SQLite FTS5 index from the normalized Markdown corpus."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
import sys
import time
from datetime import date, datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

from classify_provenance import Provenance, classify


PAGE_PATTERN = re.compile(
    r"<!-- source-page: (\d+) -->\s*\n<a id=\"page-\d+\"></a>\s*\n",
    re.MULTILINE,
)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, action="append", required=True,
                        help="corpus directory containing conversion-manifest.csv; repeatable")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--database-name", default="cbi-corpus.sqlite",
                        help="SQLite filename written inside --output")
    parser.add_argument("--audit-csv", type=Path)
    parser.add_argument("--files-csv", type=Path,
                        help="crawl manifest, used for referrer and HTTP date metadata")
    parser.add_argument("--snapshot-date", default="2026-08-25",
                        help="crawl snapshot date, YYYY-MM-DD")
    parser.add_argument("--page-authorship-csv", type=Path,
                        help="audited page ranges for mixed-authorship documents")
    parser.add_argument("--authorship-overrides-csv", type=Path,
                        help="SHA-keyed document adjudications after opening-page review")
    parser.add_argument("--extraction-preferences-csv", type=Path,
                        help="required choices when a SHA has more than one extraction")
    parser.add_argument("--progress-every", type=int, default=250)
    return parser.parse_args()


def parse_frontmatter(markdown: str) -> tuple[dict, str]:
    if not markdown.startswith("---\n"):
        raise ValueError("Markdown file has no frontmatter")
    end = markdown.find("\n---\n", 4)
    if end == -1:
        raise ValueError("Markdown frontmatter is not closed")
    metadata: dict = {}
    for line in markdown[4:end].splitlines():
        key, separator, value = line.partition(":")
        if not separator:
            continue
        metadata[key.strip()] = json.loads(value.strip())
    return metadata, markdown[end + 5 :]


def split_pages(body: str) -> list[tuple[int, str]]:
    matches = list(PAGE_PATTERN.finditer(body))
    pages: list[tuple[int, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        pages.append((int(match.group(1)), body[match.end() : end].strip()))
    return pages


def clean_title(text: str) -> str | None:
    for line in text.splitlines():
        if not re.match(r"^#{1,6}\s+", line):
            continue
        title = re.sub(r"^#{1,6}\s+", "", line)
        title = re.sub(r"[*_`#<>]", "", title).strip()
        if title:
            return title[:500]
    return None


def title_from_url(url: str) -> str | None:
    name = Path(unquote(urlparse(url).path)).stem
    title = re.sub(r"[-_]+", " ", name)
    title = re.sub(r"\s+", " ", title).strip()
    return title[:500] or None


MONTHS = {
    name.casefold(): number for number, name in enumerate(
        ("", "january", "february", "march", "april", "may", "june", "july",
         "august", "september", "october", "november", "december")
    ) if name
}
PUBLISHED_DATE = re.compile(
    r"published[-_ ]+(?P<day>[0-3]?\d)[-_ ]+(?P<month>[a-z]+)[-_ ]+(?P<year>20\d{2})",
    re.I,
)


def explicit_published_date(value: str | None) -> str | None:
    """Read only dates explicitly introduced by the word 'published'.

    This deliberately does not promote a PDF creation timestamp or an arbitrary
    date in a filename to publication time.
    """
    match = PUBLISHED_DATE.search(unquote(value or ""))
    if not match:
        return None
    month = MONTHS.get(match.group("month").casefold())
    if not month:
        return None
    try:
        return date(int(match.group("year")), month, int(match.group("day"))).isoformat()
    except ValueError:
        return None


def pdf_creation_year(value: str | None, maximum: int) -> int | None:
    match = re.match(r"D:([12]\d{3})", value or "")
    if not match:
        return None
    year = int(match.group(1))
    return year if 1900 <= year <= maximum else None


def temporal_metadata(url: str, pdf_date: str | None, source: dict,
                      snapshot_date: str) -> dict:
    snapshot_year = date.fromisoformat(snapshot_date).year
    published_at = explicit_published_date(url)
    basis = "source-url-explicit-published-date" if published_at else None
    if not published_at:
        for referrer in source.get("referrers", []):
            published_at = explicit_published_date(referrer)
            if published_at:
                basis = "referrer-url-explicit-published-date"
                break
    if published_at:
        analysis_year = int(published_at[:4])
        analysis_basis = basis
    else:
        analysis_year = pdf_creation_year(pdf_date, snapshot_year)
        analysis_basis = "pdf-creation-date-proxy" if analysis_year else None
    return {
        "published_at": published_at,
        "published_at_basis": basis,
        "analysis_year": analysis_year,
        "analysis_year_basis": analysis_basis,
        "retrieved_at": snapshot_date,
        "source_page_url": next(iter(source.get("referrers", [])), None),
        "source_last_modified_at": source.get("lastModified") or None,
    }


def read_keyed_csv(path: Path | None, key: str) -> dict[str, dict]:
    if not path:
        return {}
    with path.resolve().open(encoding="utf-8-sig", newline="") as stream:
        return {row[key]: row for row in csv.DictReader(stream)}


def source_metadata(path: Path | None) -> dict[str, dict]:
    if not path:
        return {}
    result: dict[str, dict] = {}
    with path.resolve().open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            sha = row.get("sha256") or ""
            if not sha:
                continue
            item = result.setdefault(sha, {"referrers": [], "lastModified": None})
            item["referrers"].extend(
                ref.strip() for ref in (row.get("referrers") or "").split("|") if ref.strip()
            )
            item["lastModified"] = item["lastModified"] or row.get("lastModified") or None
    for item in result.values():
        item["referrers"] = sorted(set(item["referrers"]))
    return result


def page_authorship_overrides(path: Path | None) -> dict[str, list[dict]]:
    if not path:
        return {}
    result: dict[str, list[dict]] = {}
    with path.resolve().open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            row["start_page"] = int(row["start_page"])
            row["end_page"] = int(row["end_page"])
            if row["authorship"] not in {"central-bank", "stakeholder", "unresolved"}:
                raise ValueError(f"invalid page authorship: {row['authorship']}")
            result.setdefault(row["source_sha256"], []).append(row)
    return result


def document_authorship_overrides(path: Path | None) -> dict[str, dict]:
    if not path:
        return {}
    result = read_keyed_csv(path, "source_sha256")
    for sha, row in result.items():
        if row["authorship"] not in {"central-bank", "stakeholder", "mixed", "unresolved"}:
            raise ValueError(f"invalid document authorship override for {sha}: {row['authorship']}")
        if row["classification_confidence"] not in {"high", "medium", "low"}:
            raise ValueError(
                f"invalid classification confidence override for {sha}: "
                f"{row['classification_confidence']}")
    return result


def page_provenance(sha: str, page_number: int, document_authorship: str,
                    document_basis: str, overrides: dict[str, list[dict]]) -> tuple[str, str]:
    matches = [row for row in overrides.get(sha, [])
               if row["start_page"] <= page_number <= row["end_page"]]
    if len(matches) > 1:
        raise ValueError(f"overlapping page-authorship overrides for {sha} page {page_number}")
    if matches:
        return matches[0]["authorship"], matches[0]["basis"]
    if document_authorship == "mixed":
        raise ValueError(f"mixed document {sha} has no authorship override for page {page_number}")
    return document_authorship, "document:" + document_basis


def initialize(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        PRAGMA journal_mode=WAL;
        PRAGMA synchronous=NORMAL;
        PRAGMA temp_store=MEMORY;
        DROP TABLE IF EXISTS pages_fts;
        DROP TABLE IF EXISTS pages;
        DROP TABLE IF EXISTS documents;
        CREATE TABLE documents (
          document_id TEXT PRIMARY KEY,
          source_sha256 TEXT NOT NULL UNIQUE,
          source_url TEXT NOT NULL,
          source_urls_json TEXT NOT NULL,
          source_alias_count INTEGER NOT NULL,
          source_file TEXT NOT NULL,
          source_bytes INTEGER,
          markdown_file TEXT NOT NULL,
          markdown_sha256 TEXT,
          title TEXT,
          pdf_title TEXT,
          pdf_author TEXT,
          pdf_creator TEXT,
          pdf_creation_date TEXT,
          published_at TEXT,
          published_at_basis TEXT,
          analysis_year INTEGER,
          analysis_year_basis TEXT,
          retrieved_at TEXT NOT NULL,
          source_page_url TEXT,
          source_last_modified_at TEXT,
          document_class TEXT NOT NULL,
          authorship TEXT NOT NULL,
          classification_basis TEXT NOT NULL,
          classification_confidence TEXT NOT NULL,
          page_basis TEXT NOT NULL,
          source_format TEXT,
          consultation_id TEXT,
          engagement_id TEXT,
          page_count INTEGER NOT NULL,
          extraction_engine TEXT NOT NULL,
          extraction_engine_version TEXT,
          ocr_enabled INTEGER NOT NULL,
          quality_low_text INTEGER NOT NULL,
          quality_empty_pages INTEGER NOT NULL
          ,extraction_selection_basis TEXT NOT NULL
          ,alternate_extraction_count INTEGER NOT NULL
          ,content_sha256 TEXT NOT NULL
          ,content_cluster_id TEXT NOT NULL
          ,content_cluster_size INTEGER NOT NULL
        );
        CREATE TABLE pages (
          document_id TEXT NOT NULL REFERENCES documents(document_id),
          page_number INTEGER NOT NULL,
          authorship TEXT NOT NULL,
          authorship_basis TEXT NOT NULL,
          text TEXT NOT NULL,
          characters INTEGER NOT NULL,
          PRIMARY KEY (document_id, page_number)
        );
        CREATE VIRTUAL TABLE pages_fts USING fts5(
          document_id UNINDEXED,
          page_number UNINDEXED,
          title,
          text,
          tokenize='unicode61 remove_diacritics 2'
        );
        CREATE INDEX pages_document_id ON pages(document_id);
        CREATE INDEX pages_authorship ON pages(authorship);
        CREATE INDEX documents_authorship ON documents(authorship);
        CREATE INDEX documents_class ON documents(document_class);
        CREATE INDEX documents_engagement ON documents(engagement_id);
        CREATE INDEX documents_content_cluster ON documents(content_cluster_id);
        """
    )


def main() -> int:
    args = arguments()
    corpus = [c.resolve() for c in args.corpus]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if Path(args.database_name).name != args.database_name or not args.database_name.endswith(".sqlite"):
        raise ValueError("--database-name must be a .sqlite filename, not a path")
    candidates: dict[str, list[dict]] = {}
    for corpus_root in corpus:
        corpus_name = "office" if corpus_root.name.casefold() == "office" else "pdf"
        with (corpus_root / "conversion-manifest.csv").open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                if row["status"] not in {"success", "low_text"}:
                    continue
                row["_root"] = corpus_root
                row["_corpus"] = corpus_name
                candidates.setdefault(row["source_sha256"], []).append(row)
    preferences = read_keyed_csv(args.extraction_preferences_csv, "source_sha256")
    manifest = []
    for sha, choices in candidates.items():
        if len(choices) == 1:
            selected = choices[0]
            selected["_selection_basis"] = "only-candidate"
        else:
            preference = preferences.get(sha)
            if not preference:
                raise ValueError(
                    f"SHA {sha} has {len(choices)} extractions but no explicit preference")
            matches = [row for row in choices if row["_corpus"] == preference["preferred_corpus"]]
            if len(matches) != 1:
                raise ValueError(
                    f"preference for {sha} selects {preference['preferred_corpus']!r}, "
                    f"found {len(matches)} matching candidates")
            selected = matches[0]
            selected["_selection_basis"] = "explicit-preference:" + preference["basis"]
            print(f"selected {selected['_corpus']} extraction for duplicate SHA {sha}", flush=True)
        selected["_alternate_extraction_count"] = len(choices) - 1
        manifest.append(selected)
    print(f"manifest rows across {len(corpus)} corpora: {len(manifest)}", flush=True)
    audit: dict[str, dict] = {}
    if args.audit_csv:
        # Some PDF metadata fields carry embedded NUL bytes, which csv refuses to
        # parse. They are meaningless here, so strip them on the way in.
        with args.audit_csv.resolve().open(encoding="utf-8-sig", newline="") as stream:
            cleaned = (line.replace("\x00", "") for line in stream)
            audit = {row["sha256"]: row for row in csv.DictReader(cleaned)}
    sources = source_metadata(args.files_csv)
    page_overrides = page_authorship_overrides(args.page_authorship_csv)
    document_overrides = document_authorship_overrides(args.authorship_overrides_csv)

    database_path = output / args.database_name
    # A rebuild must start from an empty SQLite file. Dropping tables in an
    # existing database leaves free pages behind, so identical inputs can yield
    # a larger file and a different SHA-256 on the second run. The index is a
    # build artifact; replacing only this explicitly named output is expected.
    database_path.unlink(missing_ok=True)
    database_path.with_name(database_path.name + "-wal").unlink(missing_ok=True)
    database_path.with_name(database_path.name + "-shm").unlink(missing_ok=True)
    connection = sqlite3.connect(database_path)
    initialize(connection)
    started = time.monotonic()
    indexed_documents = 0
    indexed_pages = 0
    failures: list[dict] = []
    document_classes: dict[str, int] = {}
    authorship_counts: dict[str, int] = {}
    confidence_counts: dict[str, int] = {}
    try:
        for index, row in enumerate(manifest, 1):
            markdown_path = row["_root"] / row["markdown_file"].replace("\\", "/")  # manifests written on Windows carry backslashes
            try:
                markdown = markdown_path.read_text(encoding="utf-8")
                metadata, body = parse_frontmatter(markdown)
                pages = split_pages(body)
                expected_pages = int(row.get("pages") or metadata.get("source_pages") or 0)
                if len(pages) != expected_pages:
                    raise ValueError(f"page marker mismatch: expected {expected_pages}, found {len(pages)}")
                document_id = metadata["document_id"]
                audit_row = audit.get(metadata["source_sha256"], {})
                pdf_title = audit_row.get("title") or None
                heading_title = clean_title(body)
                if heading_title and heading_title.casefold() in {"contents", "table of contents", "introduction"}:
                    heading_title = None
                materialized = bool(metadata.get("materialized_from"))
                title = (metadata.get("published_title") if materialized
                         else pdf_title or heading_title or title_from_url(metadata["source_url"]))
                source_urls = metadata.get("source_urls") or [metadata["source_url"]]
                opening = "\n".join(text for _number, text in pages[:2])[:20000]
                if materialized and metadata.get("published_authorship"):
                    provenance = Provenance(
                        authorship=metadata["published_authorship"],
                        document_class=metadata["published_document_class"],
                        consultation_id=metadata.get("published_consultation_id"),
                        engagement_id=metadata.get("published_engagement_id"),
                        basis=metadata["published_classification_basis"],
                        confidence=metadata["published_classification_confidence"],
                    )
                else:
                    provenance = classify(metadata["source_url"], opening)
                    override = document_overrides.get(metadata["source_sha256"])
                    if override:
                        provenance = Provenance(
                            authorship=override["authorship"],
                            document_class=override["document_class"],
                            consultation_id=provenance.consultation_id,
                            engagement_id=provenance.engagement_id,
                            basis="adjudicated:" + override["evidence_basis"],
                            confidence=override["classification_confidence"],
                        )
                document_class = provenance.document_class
                consultation_id = provenance.consultation_id
                engagement_id = provenance.engagement_id
                page_nonspace = [sum(not character.isspace() for character in text)
                                 for _number, text in pages]
                quality_empty_pages = sum(value < 30 for value in page_nonspace)
                content_sha256 = hashlib.sha256(
                    "\x1e".join(text for _number, text in pages).encode("utf-8")
                ).hexdigest()
                if materialized and metadata.get("published_retrieved_at"):
                    date_fields = {
                        key: metadata.get("published_" + key) for key in (
                            "published_at", "published_at_basis", "analysis_year",
                            "analysis_year_basis", "retrieved_at", "source_page_url",
                            "source_last_modified_at")
                    }
                else:
                    date_fields = temporal_metadata(
                        metadata["source_url"], audit_row.get("creation_date") or None,
                        sources.get(metadata["source_sha256"], {}), args.snapshot_date)
                connection.execute(
                    """
                    INSERT INTO documents (
                      document_id, source_sha256, source_url, source_urls_json,
                      source_alias_count, source_file, source_bytes, markdown_file,
                      markdown_sha256, title, pdf_title, pdf_author, pdf_creator,
                      pdf_creation_date, published_at, published_at_basis,
                      analysis_year, analysis_year_basis, retrieved_at,
                      source_page_url, source_last_modified_at,
                      document_class, authorship,
                      classification_basis, classification_confidence, page_basis,
                      source_format, consultation_id, engagement_id,
                      page_count, extraction_engine,
                      extraction_engine_version, ocr_enabled, quality_low_text,
                      quality_empty_pages, extraction_selection_basis,
                      alternate_extraction_count, content_sha256,
                      content_cluster_id, content_cluster_size
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        document_id,
                        metadata["source_sha256"],
                        metadata["source_url"],
                        json.dumps(source_urls, ensure_ascii=False),
                        len(source_urls),
                        metadata["source_file"],
                        metadata.get("source_bytes"),
                        row["markdown_file"],
                        row.get("markdown_sha256"),
                        title,
                        pdf_title,
                        audit_row.get("author") or None,
                        audit_row.get("creator") or None,
                        audit_row.get("creation_date") or None,
                        date_fields["published_at"],
                        date_fields["published_at_basis"],
                        date_fields["analysis_year"],
                        date_fields["analysis_year_basis"],
                        date_fields["retrieved_at"],
                        date_fields["source_page_url"],
                        date_fields["source_last_modified_at"],
                        document_class,
                        provenance.authorship,
                        provenance.basis,
                        provenance.confidence,
                        metadata.get("page_basis") or "source-page",
                        metadata.get("detected_source_format") or "pdf",
                        consultation_id,
                        engagement_id,
                        len(pages),
                        metadata["extraction_engine"],
                        metadata.get("extraction_engine_version"),
                        int(bool(metadata.get("ocr_enabled"))),
                        int(bool(metadata.get("quality_low_text"))),
                        quality_empty_pages,
                        (metadata.get("published_extraction_selection_basis")
                         or row["_selection_basis"]),
                        (metadata.get("published_alternate_extraction_count")
                         if metadata.get("published_alternate_extraction_count") is not None
                         else row["_alternate_extraction_count"]),
                        content_sha256,
                        content_sha256,
                        0,
                    ),
                )
                for page_number, text in pages:
                    page_authorship, page_basis = page_provenance(
                        metadata["source_sha256"], page_number, provenance.authorship,
                        provenance.basis, page_overrides)
                    connection.execute(
                        "INSERT INTO pages VALUES (?, ?, ?, ?, ?, ?)",
                        (document_id, page_number, page_authorship, page_basis, text, len(text)),
                    )
                    connection.execute(
                        "INSERT INTO pages_fts VALUES (?, ?, ?, ?)",
                        (document_id, page_number, title or "", text),
                    )
                indexed_documents += 1
                indexed_pages += len(pages)
            except Exception as exc:
                failures.append({
                    "source_sha256": row.get("source_sha256"),
                    "markdown_file": row.get("markdown_file"),
                    "error": f"{type(exc).__name__}: {exc}"[:2000],
                })
            if index % args.progress_every == 0:
                connection.commit()
                print(f"Indexed {index}/{len(manifest)} manifest records; pages={indexed_pages}; failures={len(failures)}", flush=True)
        connection.commit()
        connection.execute(
            "CREATE TEMP TABLE content_counts AS "
            "SELECT content_cluster_id, COUNT(*) AS size FROM documents "
            "GROUP BY content_cluster_id")
        connection.execute(
            "UPDATE documents SET content_cluster_size = ("
            "SELECT size FROM content_counts "
            "WHERE content_counts.content_cluster_id = documents.content_cluster_id)")
        connection.commit()
        connection.execute("PRAGMA optimize")
        connection.commit()
        authorship_counts = {
            row[0]: row[1]
            for row in connection.execute(
                "SELECT authorship, COUNT(*) FROM documents GROUP BY authorship ORDER BY COUNT(*) DESC"
            ).fetchall()
        }
        confidence_counts = {
            row[0]: row[1]
            for row in connection.execute(
                "SELECT classification_confidence, COUNT(*) FROM documents GROUP BY classification_confidence"
            ).fetchall()
        }
        document_classes = {
            row[0]: row[1]
            for row in connection.execute(
                "SELECT document_class, COUNT(*) FROM documents GROUP BY document_class ORDER BY COUNT(*) DESC"
            ).fetchall()
        }
        # Leave a single quiescent, portable SQLite artifact. WAL is useful while
        # ingesting, but a copied database must not depend on unshipped sidecars.
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.commit()
    finally:
        connection.close()

    summary = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "manifest_records": len(manifest),
        "indexed_documents": indexed_documents,
        "indexed_pages": indexed_pages,
        "authorship": authorship_counts,
        "classification_confidence": confidence_counts,
        "document_classes": document_classes,
        "failures": len(failures),
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "database_bytes": database_path.stat().st_size,
        "database_file": database_path.name,
    }
    (output / "index-summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    (output / "index-failures.json").write_text(
        json.dumps(failures, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(summary, indent=2), flush=True)
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
