---
license: cc-by-4.0
language:
  - en
pretty_name: Central Bank of Ireland Public Archive Corpus
size_categories:
  - 10K<n<100K
task_categories:
  - text-retrieval
  - question-answering
  - text-classification
tags:
  - finance
  - regulation
  - ireland
  - central-banking
  - public-sector-information
  - policy
configs:
  - config_name: pages
    data_files:
      - split: train
        path: data/pages.parquet
  - config_name: documents
    data_files:
      - split: train
        path: data/documents.parquet
---

# Central Bank of Ireland Public Archive Corpus

A page-anchored, provenance-classified corpus of the Central Bank of Ireland's
public document archive. **5,568 documents, 88,782 source pages, 190.5 million
characters**, in 47 MB of Parquet.

This is an unofficial derived work. It is not published by, affiliated with, or
endorsed by the Central Bank of Ireland.

## What makes this different from a pile of scraped PDFs

Two things.

**Every page keeps its address.** Each row carries the source document's
SHA-256, its URL, and its page number in the original PDF. A claim found here
can be traced back to a specific page of a specific file whose bytes you can
verify. Nothing is a floating snippet.

**Every document is classified by who wrote it.** The Central Bank hosts two
very different kinds of document: material it authored, and submissions that
banks, insurers, trade bodies and individuals sent it during public
consultations. Those read alike and mean the opposite. A submission from a bank
arguing that a rule is burdensome is not a regulatory finding, and treating it
as one is the single easiest way to produce confidently wrong analysis from this
archive.

The `authorship` column separates them:

| authorship | documents | what it means |
|---|---:|---|
| `central-bank` | 3,807 | the regulator speaking |
| `stakeholder` | 1,656 | a firm or trade body writing to the regulator, i.e. advocacy |
| `unresolved` | 105 | genuinely ambiguous, and deliberately not guessed |

`unresolved` is a real answer, not a gap. Do not fold it into `central-bank`.

### Why the classifier is not a keyword match

An earlier version of this classification treated a consultation-hosted document
as a submission only when its filename contained the string `response`. That
missed three whole families:

1. files named `cp45-submission-from-aib.pdf`
2. files named `cp51-feedback-from-generali-paneurope.pdf`, which were being
   filed as Central Bank *feedback statements*
3. files published under the responder's bare name, such as `blackrock.pdf`,
   which carry no cue in the filename at all

Family 3 cannot be resolved from a filename, so classification is two-pass:
filename attribution and Central Bank document-type cues first, then the opening
pages of the document itself where the filename is silent. Only a narrow set of
issuer-specific Central Bank cues takes precedence over stakeholder attribution,
which is what keeps
`note-from-the-financial-regulator-in-relation-to-submissions-received-on-cp43`
correctly attributed to the Bank. Generic document-type cues do not: they apply
only where the filename carries no attribution, because letting them win is the
defect that put AIB's and Bank of Ireland's submissions into the regulator's
pile in an earlier version. The rule that produced each label is stored in
`classification_basis`, with a `classification_confidence` of high, medium or
low. 94 regression assertions cover the classifier.

## Files

| File | Rows | Size | Contents |
|---|---:|---:|---|
| `data/documents.parquet` | 5,568 | 0.7 MB | one row per document: URL, hashes, title, authorship, class, page count, extraction metadata |
| `data/pages.parquet` | 88,782 | 46.6 MB | one row per source page, carrying the full text |
| `manifests/files.csv.zst` | 6,984 | 0.6 MB | the original download manifest: every URL, its SHA-256, bytes, content type, referrers |
| `manifests/conversion-manifest.csv.zst` | 5,246 | 0.8 MB | PDF to Markdown conversion record, per document |
| `manifests/provenance-classification.csv.zst` | 5,568 | 0.3 MB | full classification audit trail, including the previous label |
| `manifests/extraction-quality.csv.zst` | 5,568 | 0.3 MB | per-document extraction fidelity grades |

The split is deliberate. Most questions need only `documents.parquet`, which is
under a megabyte, and never touch the page text at all.

## Usage

```python
from datasets import load_dataset

docs = load_dataset("aditya487/cbi-archive-corpus", "documents", split="train")
pages = load_dataset("aditya487/cbi-archive-corpus", "pages", split="train")
```

Or query it without downloading anything, using DuckDB over HTTPS:

```sql
INSTALL httpfs; LOAD httpfs;
SELECT d.title, p.page_number, substr(p.text, 1, 200)
FROM  'https://huggingface.co/datasets/aditya487/cbi-archive-corpus/resolve/main/data/pages.parquet' p
JOIN  'https://huggingface.co/datasets/aditya487/cbi-archive-corpus/resolve/main/data/documents.parquet' d
  USING (document_id)
WHERE d.authorship = 'central-bank'
  AND lower(p.text) LIKE '%operational resilience%'
LIMIT 20;
```

Parquet is columnar, so that query reads only the columns it names.

## How the corpus was built

- **Crawl snapshot:** 25 August 2026, from `centralbank.ie`, `www.centralbank.ie`
  and the open-data portal, using the sitemap plus the CKAN open-data API.
- **Downloaded:** 6,963 files, 7.476 GB, with 21 URLs failing (all HTTP 404 and
  all recorded rather than silently dropped).
- **Deduplicated** by SHA-256: 6,309 unique files. 654 files were byte-identical
  content served at more than one URL.
- **Converted:** PDFs through PyMuPDF4LLM with page anchors preserved, selective
  RapidOCR for scanned documents, and a separate pipeline for the 323 DOCX, DOC,
  ZIP and PPTX files that a PDF-only filter had originally skipped.
- **Validated:** every source hash and every output hash recomputed from disk,
  page markers checked for sequence, orphans checked for. Zero failures.

## Limitations, stated plainly

- **`page_basis` is not always a page.** PDFs carry true source-page anchors.
  Office documents mostly have no page structure: 179 of the 323 are a single
  pseudo-page, meaning the anchor identifies the document, not a location within
  it. Only `source-page` and `slide` are safe to cite as positions.
- **112 documents are graded below `ok`** for extraction fidelity: 63 with
  substantially blank pages, 26 garbled by encoding damage, 16 thin, 7 empty.
  They are listed in `extraction-quality.csv.zst`. Chart-heavy statistical
  releases extract with visible damage even when their numbers survive intact.
- **ZIP archives are profiled, not transcribed.** Most are XBRL taxonomy
  packages; one held 31,185 schema files. Transcribing them produced 705 MB of
  Markdown and would have made machine schema dominate every word count. The
  member listing and namespace profile are included; schema bodies are not.
- **Publication volume is not importance.** A topic appearing in many documents
  usually means a consultation drew many responses, not that the topic matters
  more. Consultation submissions are advocacy and are written to persuade.
- **This is a dated snapshot.** It cannot contain anything unpublished, unlinked,
  blocked, or published after 25 August 2026.

## Licence and attribution

The underlying material is Irish Public Sector Information. The Central Bank's
re-use terms permit re-use subject to a licence consistent with CC BY 4.0.

> Contains Irish Public Sector Information licensed under a Creative Commons
> Attribution 4.0 International (CC BY 4.0) licence.

Individual resources may carry more restrictive or third-party terms. The CKAN
licence title and URL for each open-data resource are retained in
`manifests/files.csv.zst` so exceptions can be checked. The licence excludes
personal information, third-party rights, trademarks, crests, logos and official
symbols, and prohibits any implication of endorsement.

Modifications made here: conversion to Markdown and Parquet, deduplication by
content hash, provenance classification, and extraction-quality grading. No
source content was edited.
