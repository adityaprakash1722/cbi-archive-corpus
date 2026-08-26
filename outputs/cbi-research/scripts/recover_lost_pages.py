#!/usr/bin/env python3
r"""Recover page text that the original conversion dropped.

    python outputs\cbi-research\scripts\recover_lost_pages.py \
      --database outputs\cbi-research\index\cbi-corpus-v3-5568docs.sqlite \
      --blobs publish\blobs --catalog publish\blob-catalog.csv \
      --corpus outputs\cbi-research\corpus --output outputs\cbi-research\qa

The bug this fixes
------------------
`pymupdf4llm` returns an empty string for pages that carry a full-page
background image, even when the page has a perfectly good text layer underneath.
Its layout pass decides the page is image-dominated and gives up. Plain
`page.get_text()` reads the same pages without difficulty.

The clearest case is a 22-page prohibition notice where 20 pages came out empty
and 43,085 characters of text were sitting in the file the whole time. Every
page of it carries a letterhead image.

What gets recovered
-------------------
Every empty page whose source PDF still yields text. That is deliberate: the
instruction was to preserve everything, so page furniture is recovered along
with substance rather than filtered out by a threshold.

Be aware of the split, because it matters for analysis:

  * about 95% of recovered pages yield under 200 characters, and are running
    headers, footers, page numbers and section labels. Treating these as empty
    was defensible.
  * 37 pages across 9 documents yield 500 characters or more, totalling roughly
    94,000 characters. That is genuine lost content, and it is why this exists.

Pages that hold only an image, only vector drawing, or nothing at all are left
alone and reported separately. Image-only pages need OCR, which this script does
not do.

Every recovery is written to a manifest so the change is auditable and
reversible.
"""
from __future__ import annotations

import argparse, csv, json, re, sqlite3
from datetime import datetime, timezone
from pathlib import Path


def page_block(number: int) -> re.Pattern:
    """Match one page's marker, anchor and body, up to the next marker or EOF."""
    return re.compile(
        r"(<!-- source-page: " + str(number) + r" -->\n"
        r"<a id=\"page-" + str(number) + r"\"></a>\n)"
        r"(.*?)"
        r"(?=<!-- source-page: \d+ -->|\Z)",
        re.S)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--blobs", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True,
                        help="root holding markdown/ and office/markdown/")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--ocr", action="store_true",
                        help="render and recognise image-only pages (needs Tesseract)")
    parser.add_argument("--dpi", type=int, default=200,
                        help="render resolution for OCR; 200 is a good balance")
    args = parser.parse_args()

    import pymupdf

    catalog = {row["sha256"]: row["key"] for row in
               csv.DictReader(args.catalog.open(newline="", encoding="utf-8-sig"))}
    connection = sqlite3.connect(args.database)
    connection.row_factory = sqlite3.Row

    documents = list(connection.execute(
        "SELECT document_id, source_sha256, markdown_file, title, authorship, page_count "
        "FROM documents WHERE quality_empty_pages > 0"))

    recovered, skipped = [], {"image-only": 0, "vector-only": 0, "blank": 0,
                              "source-missing": 0, "unopenable": 0, "no-markdown": 0,
                              "page-out-of-range": 0, "marker-not-found": 0}
    touched_files = 0

    for document in documents:
        key = catalog.get(document["source_sha256"])
        source = args.blobs / key if key else None
        if source is None or not source.exists():
            skipped["source-missing"] += 1
            continue
        try:
            pdf = pymupdf.open(source)
        except Exception:
            skipped["unopenable"] += 1
            continue

        empty = [row["page_number"] for row in connection.execute(
            "SELECT page_number FROM pages WHERE document_id=? AND "
            "(text IS NULL OR trim(text)='') ORDER BY page_number",
            (document["document_id"],))]

        wins, ocr_pages = [], []
        for number in empty:
            if number - 1 >= len(pdf):
                skipped["page-out-of-range"] += 1
                continue
            page = pdf[number - 1]
            text = page.get_text().strip()
            if text:
                wins.append((number, text))
            elif page.get_images(full=True):
                if not args.ocr:
                    skipped["image-only"] += 1
                    continue
                # The page carries an image and no text layer, so the only way
                # to read it is to render and recognise it.
                try:
                    textpage = page.get_textpage_ocr(flags=0, dpi=args.dpi, full=True)
                    text = page.get_text(textpage=textpage).strip()
                except Exception:
                    skipped["ocr-failed"] = skipped.get("ocr-failed", 0) + 1
                    continue
                if text:
                    wins.append((number, text))
                    ocr_pages.append(number)
                else:
                    skipped["ocr-found-nothing"] = skipped.get("ocr-found-nothing", 0) + 1
            elif page.get_drawings():
                skipped["vector-only"] += 1
            else:
                skipped["blank"] += 1
        pdf.close()
        if not wins:
            continue

        relative = (document["markdown_file"] or "").replace("\\", "/")
        markdown = args.corpus / relative
        if not markdown.exists():
            markdown = args.corpus / "office" / relative
        if not markdown.exists():
            skipped["no-markdown"] += 1
            continue

        content = markdown.read_text(encoding="utf-8", newline="")
        changed = False
        for number, text in wins:
            pattern = page_block(number)
            match = pattern.search(content)
            if not match:
                skipped["marker-not-found"] += 1
                continue
            if match.group(2).strip():
                continue  # something is already there; never overwrite
            content = (content[:match.start(2)] + "\n" + text + "\n\n" +
                       content[match.end(2):])
            changed = True
            recovered.append({
                "document_id": document["document_id"],
                "source_sha256": document["source_sha256"],
                "page_number": number,
                "characters": len(text),
                "method": "ocr" if number in ocr_pages else "text-layer",
                "authorship": document["authorship"],
                "title": (document["title"] or "")[:100],
            })
        if changed and not args.dry_run:
            markdown.write_text(content, encoding="utf-8", newline="\n")
            touched_files += 1

    args.output.mkdir(parents=True, exist_ok=True)
    if recovered:
        path = args.output / "recovered-pages.csv"
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(recovered[0].keys()))
            writer.writeheader()
            writer.writerows(recovered)

    substantial = [r for r in recovered if r["characters"] >= 500]
    summary = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "dry_run": args.dry_run,
        "documents_examined": len(documents),
        "markdown_files_rewritten": touched_files,
        "pages_recovered": len(recovered),
        "characters_recovered": sum(r["characters"] for r in recovered),
        "documents_affected": len({r["document_id"] for r in recovered}),
        "substantial_pages_500_plus": len(substantial),
        "substantial_characters": sum(r["characters"] for r in substantial),
        "substantial_documents": len({r["document_id"] for r in substantial}),
        "by_method": {
            "text-layer": sum(1 for r in recovered if r["method"] == "text-layer"),
            "ocr": sum(1 for r in recovered if r["method"] == "ocr"),
        },
        "ocr_enabled": args.ocr,
        "not_recovered": skipped,
        "note": "Existing page text is never overwritten. Without --ocr, image-only "
                "pages are left alone and counted under not_recovered.",
    }
    (args.output / "recovered-pages.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(f"examined {summary['documents_examined']} documents with empty pages")
    print(f"recovered {summary['pages_recovered']:,} pages, "
          f"{summary['characters_recovered']:,} characters, "
          f"across {summary['documents_affected']} documents")
    print(f"  of which substantial (500+ chars): "
          f"{summary['substantial_pages_500_plus']} pages, "
          f"{summary['substantial_characters']:,} characters, "
          f"{summary['substantial_documents']} documents")
    print(f"  by method: text-layer {summary['by_method']['text-layer']:,}, "
          f"OCR {summary['by_method']['ocr']:,}")
    print(f"rewrote {touched_files} Markdown files"
          + (" (DRY RUN, nothing written)" if args.dry_run else ""))
    print("not recovered:")
    for reason, count in sorted(skipped.items(), key=lambda x: -x[1]):
        if count:
            print(f"  {reason:20} {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
