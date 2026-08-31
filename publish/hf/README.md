---
license: other
license_name: mixed-see-rights-and-reuse
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
public document archive. **5,568 documents, 88,783 source pages and 190,941,651
characters**, in about 48 MB of Parquet (about 51 MB including compressed audit
manifests).

This is an unofficial derived work. It is not published by, affiliated with, or
endorsed by the Central Bank of Ireland.

## What makes this different from a pile of scraped PDFs

Two things.

**Every page keeps its address.** Each row carries the source document's
SHA-256, its URL, and its page number in the original PDF. A claim found here
can be traced back to a specific page of a specific file whose bytes you can
verify. Nothing is a floating snippet.

**Every page is classified by who is speaking.** The Central Bank hosts two
very different kinds of document: material it authored, and submissions that
banks, insurers, trade bodies and individuals sent it during public
consultations. Those read alike and mean the opposite. A submission from a bank
arguing that a rule is burdensome is not a regulatory finding, and treating it
as one is the single easiest way to produce confidently wrong analysis from this
archive.

The document-level `authorship` column separates ordinary documents, while the
page table can separate voices inside a composite:

| authorship | documents | what it means |
|---|---:|---|
| `central-bank` | 3,844 | the regulator speaking |
| `stakeholder` | 1,722 | a respondent writing to the regulator: advocacy or consultation input |
| `mixed` | 2 | a composite; use page-level authorship |
| `unresolved` | 0 | retained as a valid schema value, but no v5.1 document remains unresolved |

`unresolved` remains a real answer, not a fallback to `central-bank`. In v5.1,
all 89 formerly unresolved records were adjudicated from their opening and <!-- historical -->
closing pages. The SHA-keyed decisions are published rather than hidden in
classifier code: 37 are Central Bank, 51 stakeholder and one mixed.

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
low. 116 regression assertions cover known failure modes. A separate reviewed
32-document regression set includes one mixed composite and two audited
submissions outside consultation folders. It was used during development, so
it is an error detector, not an independent holdout or a population accuracy
estimate.

## Files

| File | Rows | Size | Contents |
|---|---:|---:|---|
| `data/documents.parquet` | 5,568 | 1.19 MB | one row per document: URL, hashes, publication evidence, title, authorship, engagement, exact-content cluster and extraction metadata |
| `data/pages.parquet` | 88,783 | 46.8 MB | one row per source page, carrying full text and page-level authorship |
| `manifests/files.csv.zst` | 6,984 | 0.6 MB | the original download manifest: every URL, its SHA-256, bytes, content type, referrers |
| `manifests/conversion-manifest.csv.zst` | 5,246 | 0.8 MB | PDF to Markdown conversion record, per document |
| `manifests/conversion-manifest-office.csv.zst` | 323 | 51 KB | the same for Word, Excel, PowerPoint and ZIP sources |
| `manifests/provenance-classification.csv.zst` | 5,568 | 0.3 MB | full classification audit trail, including the previous label |
| `manifests/extraction-quality.csv.zst` | 5,568 | 0.3 MB | per-document extraction fidelity grades |
| `manifests/authorship-overrides.csv.zst` | 89 | 6 KB | SHA-keyed adjudications of every formerly unresolved document | <!-- historical -->
| `manifests/page-authorship-overrides.csv.zst` | 4 | <1 KB | audited page ranges for the two mixed composites |
| `manifests/conversion-exclusions.csv.zst` | 1 | <1 KB | the one downloaded HTML error body excluded from conversion |
| `manifests/engagement-coverage.csv.zst` | 182 | 2 KB | canonical CP/DP identifiers and document-class coverage |
| `manifests/manifest-build-summary.json` | 1 | <1 KB | hashes and row counts for every compressed manifest |

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
WHERE p.authorship = 'central-bank'
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
- **Engagement identifiers normalised:** `cp071`, `cp-71` and `CP71` map to
  `cp71`; discussion papers similarly map to `dpN`. The snapshot contains 149
  CP identifiers, 11 DP identifiers and 73 CPs with a proposal, stakeholder
  responses and a Central Bank feedback statement. The 22 gaps in CP1 to CP171
  are published as snapshot coverage gaps, not asserted to be unissued numbers.
- **Exact-content clusters retained:** 5,490 exact-text clusters cover 5,568
  documents; 146 documents belong to a cluster larger than one. Seven are the
  empty-document cluster, leaving 139 duplicated non-empty documents and 72
  excess non-empty records if text is counted once. They remain as
  separate records because their URLs and publication contexts differ. Use
  `content_cluster_id` to avoid double-counting identical text in analysis.

## Limitations, stated plainly

- **`page_basis` is not always a page.** PDFs carry true source-page anchors.
  Office documents mostly have no page structure: 179 of the 323 are a single
  pseudo-page, meaning the anchor identifies the document, not a location within
  it. Only `source-page` and `slide` are safe to cite as positions.
- **87 documents are graded below `ok`** for extraction fidelity: 36 with
  substantially blank pages, 25 garbled by encoding damage, 19 thin, 7 empty.
  They are listed in `extraction-quality.csv.zst`. Chart-heavy statistical
  releases extract with visible damage even when their numbers survive intact.
- **441,610 characters were recovered in a later pass** and are included here.
  The original converter returned nothing for pages carrying a full-page
  background image, even where a readable text layer sat underneath, so 1,167
  pages were re-extracted directly and a further 258 image-only pages were
  recovered by OCR. A later targeted OCR pass replaced five garbled CP76 pages
  with 11,206 readable characters. `recovered-pages.csv` in the GitHub
  repository is the cumulative OCR-page ledger; direct text-layer recoveries
  are reported separately in the extraction review.
- **Publication dates are sparse by design.** `published_at` is populated only
  where source/referrer metadata states an explicit date. `analysis_year` can
  additionally use a plausible PDF creation year, but future timestamps are
  rejected; raw `pdf_creation_date` is preserved as untrusted metadata.
- **ZIP archives are profiled, not transcribed.** Most are XBRL taxonomy
  packages; one held 31,185 schema files. Transcribing them produced 705 MB of
  Markdown and would have made machine schema dominate every word count. The
  member listing and namespace profile are included; schema bodies are not.
- **Publication volume is not importance.** A topic appearing in many documents
  usually means a consultation drew many responses, not that the topic matters
  more. Consultation submissions are advocacy and are written to persuade.
- **This is a dated snapshot.** It cannot contain anything unpublished, unlinked,
  blocked, or published after 25 August 2026.

## Rights, reuse and attribution

This is a mixed-rights corpus, so the machine-readable licence is deliberately
`other`, not blanket CC BY 4.0. Only 71 open-data resources carry explicit CC BY
4.0 metadata. Most Central Bank-authored material is covered by the site's PSI
reuse terms, while stakeholder submissions, personal information and other
third-party material may fall outside that permission.

> Contains Irish Public Sector Information licensed under a Creative Commons
> Attribution 4.0 International (CC BY 4.0) licence.

Use the attribution above when the PSI licence applies. The CKAN licence title
and URL for each open-data resource are retained in
`manifests/files.csv.zst` so exceptions can be checked. The licence excludes
personal information, third-party rights, trademarks, crests, logos and official
symbols, and prohibits any implication of endorsement.

See `RIGHTS-REVIEW.md` in the GitHub repository before redistributing text or
using the corpus commercially. This metadata change is conservative and is not
legal advice.

Modifications made here: conversion to Markdown and Parquet, deduplication by
content hash, provenance classification, extraction-quality grading, and OCR
replacement of five pages whose earlier text was 94% decoding noise. The
original source bytes remain unchanged in the raw archive.

All generated CSV audit artifacts are UTF-8 without a byte-order mark and use
LF line endings, so their locked hashes are stable across Windows and Unix.
