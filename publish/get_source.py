#!/usr/bin/env python3
r"""Go from a search result back to the original PDF, from any machine.

    python publish\get_source.py --search "operational resilience"
    python publish\get_source.py --sha e5dabf14e1e876c484b3fd0d9b4fe86925befc868391e73aeddd6b0218a3a6cc
    python publish\get_source.py --url https://www.centralbank.ie/docs/.../something.pdf

How the three pieces are joined
-------------------------------
There is no lookup service and no database. The join key is the SHA-256 hash,
and it appears in all three places:

    GitHub        files.csv maps every source URL to its SHA-256
    Hugging Face  documents.parquet carries source_sha256 on every document
    Hugging Face  the raw repo stores each file at <ab>/<cd>/<sha256><ext>

So a hash found by searching the text is literally the address of the original
document. Content addressing means the identifier and the location are the same
thing, which is why no index is needed to get from one to the other.

The extension is the one part the hash does not tell you. `source_format` is not
reliable for this: three documents are recorded as `docx_mislabeled_as_pdf` and
are published under two different extensions between them. So the format gives
an ordered list of candidates and the first one that resolves wins.
"""
from __future__ import annotations

import argparse, hashlib, sys, urllib.error, urllib.request
from pathlib import Path

CORPUS = "https://huggingface.co/datasets/{user}/cbi-archive-corpus/resolve/main/data"
MANIFEST = "https://huggingface.co/datasets/{user}/cbi-archive-corpus/resolve/main/manifests/files.csv.zst"
RAW = "https://huggingface.co/datasets/{user}/cbi-archive-raw/resolve/main"

# source_format -> extensions to try, in order. Verified against the published
# blob catalogue: every one of the 6,309 files resolves through this table.
EXTENSIONS = {
    "pdf": ["pdf"],
    "DOC": ["doc"],
    "DOCX": ["docx"],
    "PPTX": ["pptx"],
    "ZIP": ["zip"],
    "PDF (served as DOCX)": ["docx"],
    "docx_mislabeled_as_pdf": ["docx", "pdf"],
    "legacy_doc_mislabeled_as_pdf": ["pdf"],
}


def blob_url(user: str, sha: str, extension: str) -> str:
    return f"{RAW.format(user=user)}/{sha[:2]}/{sha[2:4]}/{sha}.{extension}"


def exists(url: str) -> bool:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD")):
            return True
    except urllib.error.HTTPError:
        return False


def resolve(user: str, sha: str, source_format: str | None) -> str | None:
    """Return the live blob URL, or None if nothing resolves."""
    candidates = EXTENSIONS.get(source_format or "pdf", ["pdf", "docx", "doc", "zip", "pptx"])
    for extension in candidates:
        url = blob_url(user, sha, extension)
        if exists(url):
            return url
    return None


def download(url: str, destination: Path, expected_sha: str) -> int:
    """Download to a temporary name, verify the hash, then move into place.

    A half-written or corrupted file must never be left sitting at the final
    path looking like a good one, so nothing is renamed until the bytes hash to
    the name they are being filed under.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".partial")
    digest = hashlib.sha256()
    total = 0
    try:
        with urllib.request.urlopen(url) as response, partial.open("wb") as out:
            while chunk := response.read(1 << 20):
                out.write(chunk)
                digest.update(chunk)
                total += len(chunk)
                print(f"\r  {total/1e6:6.1f} MB", end="", flush=True)
        print()
        actual = digest.hexdigest()
        if actual != expected_sha:
            partial.unlink(missing_ok=True)
            raise ValueError(f"hash mismatch: expected {expected_sha[:16]}..., got {actual[:16]}...")
        partial.replace(destination)
        return total
    except BaseException:
        partial.unlink(missing_ok=True)
        raise


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="aditya487")
    ap.add_argument("--sha")
    ap.add_argument("--url")
    ap.add_argument("--search", help="find documents whose text contains this")
    ap.add_argument("--authorship", choices=["central-bank", "stakeholder", "unresolved"])
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--out", type=Path, default=Path("downloaded-sources"))
    ap.add_argument("--fetch", action="store_true", help="download the matches, not just list them")
    args = ap.parse_args()

    try:
        import duckdb
    except ImportError:
        print("pip install duckdb")
        return 1

    documents = f"{CORPUS.format(user=args.user)}/documents.parquet"
    pages = f"{CORPUS.format(user=args.user)}/pages.parquet"
    columns = ("source_sha256, title, source_url, source_bytes, source_format, authorship")
    connection = duckdb.connect()
    connection.execute("INSTALL httpfs; LOAD httpfs;")

    if args.sha:
        matches = connection.execute(
            f"SELECT {columns} FROM read_parquet('{documents}') WHERE source_sha256 = ?",
            [args.sha]).fetchall()
    elif args.url:
        # 491 documents were served under more than one URL, and documents.parquet
        # keeps only the canonical one plus a count. Resolve through the download
        # manifest, which carries every URL, or a perfectly valid alias silently
        # returns nothing.
        matches = connection.execute(
            f"SELECT {columns} FROM read_parquet('{documents}') WHERE source_sha256 IN "
            f"(SELECT sha256 FROM read_csv_auto('{MANIFEST.format(user=args.user)}') WHERE url = ?)",
            [args.url]).fetchall()
    elif args.search:
        clause = f"AND d.authorship = '{args.authorship}'" if args.authorship else ""
        matches = connection.execute(f"""
            SELECT DISTINCT d.source_sha256, d.title, d.source_url, d.source_bytes,
                   d.source_format, d.authorship
            FROM read_parquet('{pages}') p JOIN read_parquet('{documents}') d USING (document_id)
            WHERE lower(p.text) LIKE '%' || lower(?) || '%' {clause}
            LIMIT {args.limit}""", [args.search]).fetchall()
    else:
        ap.print_help()
        return 2

    if not matches:
        print("no matches")
        return 1

    print(f"{len(matches)} match(es)\n")
    failures = 0
    for sha, title, url, size, fmt, authorship in matches:
        blob = resolve(args.user, sha, fmt)
        print(f"  {(title or '(untitled)')[:66]}")
        print(f"    authorship : {authorship}")
        print(f"    size       : {(size or 0)/1e6:.1f} MB")
        print(f"    original   : {url}")
        print(f"    sha256     : {sha}")
        print(f"    blob       : {blob or 'UNRESOLVED (no extension matched)'}")
        if blob is None:
            failures += 1
        elif args.fetch:
            destination = args.out / f"{sha[:12]}.{blob.rsplit('.', 1)[-1]}"
            print(f"    downloading to {destination}")
            try:
                download(blob, destination, sha)
                print(f"    verified   : sha256 matches")
            except Exception as exc:
                failures += 1
                print(f"    FAILED: {exc}")
        print()

    if not args.fetch:
        print("Add --fetch to download the originals.")
    if failures:
        print(f"{failures} of {len(matches)} failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
