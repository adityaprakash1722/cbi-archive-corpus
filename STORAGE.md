# Storage architecture

Audience: an agent or engineer picking this project up cold. This explains where
every artifact lives, why it lives there, and how to get at it. Read `AGENTS.md`
first for the working rules; this document is the map.

---

## 1. The principle

The obvious approach is to put everything in one place. That fails here, because
the project's artifacts differ by four orders of magnitude in size and by
infinite orders in how hard they are to recreate.

Artifacts are therefore tiered by **cost to recreate**, not by size:

| Cost to recreate | Example | Consequence |
|---|---|---|
| Impossible | the crawl snapshot of 25 Aug 2026 | must be preserved |
| Expensive | extracted and classified text | publish it, do not regenerate |
| Trivial | the SQLite search index, under a minute | never store, always rebuild |

A 663 MB file that rebuilds in under a minute is not data. It is a build product,
and syncing it is paying to move something you can recreate faster than you can
download it. A 48 MB Parquet pair representing 180 million characters of extracted,
hash-verified, provenance-classified text is the opposite: small, and
irreplaceable without re-running a multi-hour pipeline.

---

## 2. Where everything is

### Tier 1: the project

**GitHub, `adityaprakash1722/cbi-archive-corpus`.** The repository contains
<!-- fact:repo.tracked_files -->273<!-- /fact --> repository files and occupies about
53 MB checked out and about 16 MB as packed Git objects.

The whole pipeline, every manifest, every analysis output, and the documents.
Small enough that a full clone is instant.

```
.gitignore .gitattributes CLAUDE.md AGENTS.md README.md STORAGE.md Makefile
outputs/
  IRELAND-FINANCIAL-SYSTEM-AND-STARTUP-THESIS.md   the analysis
  CBI-ARCHIVE-ANALYSIS-METHOD.md                   corpus construction and limits
  REMEDIATION-2026-08-26.md                        what was wrong and got fixed
  cbi-archive/
    cbi-archive.mjs                      crawler, zero-dependency Node, 12 tests
    cbi-data/manifests/files.csv         6,984 rows: URL, SHA-256, bytes, referrers
    cbi-data/manifests/failed-urls.csv   21 rows, all HTTP 404
    cbi-data/manifests/summary.json      crawl totals
    cbi-data/metadata/ckan-packages.json open-data catalogue metadata
  cbi-research/
    scripts/                             33 Python files, the whole pipeline
    corpus/conversion-manifest.csv       5,246 rows, PDF conversion record
    corpus/office/conversion-manifest.csv  323 rows, Office and ZIP record
    qa/                                  validation, provenance, extraction grades
    structured/                          CSV, workbook and XML profiling
    analysis-v5.2/                       current topic scan and evidence candidates
    index/README.md                      which database to use
publish/                                 publishing scripts and the dataset card
work/                                    working notes: ledger, system map, screens
```

### Tier 2: the corpus

**Hugging Face dataset, `aditya487/cbi-archive-corpus`. About 51 MB.**

The text extracted from every source document, with full provenance. This is the
working surface: nearly every question is answerable here.

```
data/documents.parquet      5,568 rows, 1.20 MB
data/pages.parquet         89,242 rows, 46.8 MB, 179,924,863 characters
data/dataset-summary.json
manifests/files.csv.zst
manifests/conversion-manifest.csv.zst
manifests/provenance-classification.csv.zst
manifests/extraction-quality.csv.zst
manifests/authorship-overrides.csv.zst
manifests/page-authorship-overrides.csv.zst
manifests/conversion-exclusions.csv.zst
manifests/engagement-coverage.csv.zst
README.md                   dataset card, drives the HF viewer
ATTRIBUTION.md              attribution used where the Irish PSI terms apply
```

Those figures describe the v5.2 release candidate. `RELEASE.lock.json` identifies
the published release's immutable Git and Hugging Face revisions and hashes.

### Tier 3: the source

**Hugging Face dataset, `aditya487/cbi-archive-raw`. 6.56 GB.**

The original PDFs and spreadsheets, content-addressed. Cold: needed only when a
document must be seen rather than read.

```
<sha[0:2]>/<sha[2:4]>/<sha256><ext>          6,309 files
blob-catalog.csv                             hash, key, format, bytes, every URL
blob-summary.json                            layout and dedupe record
page-catalog.csv                             future HTML source-page snapshots; empty for August 2026
```

### Not stored anywhere

| Artifact | Size | Why not |
|---|---:|---|
| `cbi-corpus-v5.2-5568docs.sqlite` | 663 MB | current; rebuilds via `make materialize && make index` |
| `cbi-corpus-v5.1-5568docs.sqlite` | 674 MB | superseded; unsafe speaker labels and two corrupt DOCX extractions |
| `cbi-corpus-v5-5568docs.sqlite` | 673 MB | superseded; unresolved authorship and unreconciled final-text metrics |
| `cbi-corpus-v4-5568docs.sqlite` | 664 MB | superseded; document-level voice and inferior duplicate extraction |
| `cbi-corpus-v3-5568docs.sqlite` | 663 MB | superseded, 441,610 characters of page text missing |
| `cbi-corpus-v2-5568docs.sqlite` | 663 MB | superseded, 55 provenance errors |
| `cbi-corpus.sqlite` | 619 MB | superseded, wrong provenance, no office corpus |
| `work/live-index/cbi-corpus.sqlite` | 423 MB | partial build from an interrupted run |
| `corpus/markdown/`, `corpus/office/markdown/` | 202 MB | superseded by Parquet |
| `archive-state.json` | 16 MB | crawler resume state, regenerable |
| `work/pdf-env`, `pip-cache`, `python-deps` | ~30 MB | build environments |

1.70 GB of superseded indices can be deleted at any time. `make clean-artifacts`
lists them.

---

## 3. The join key

The three tiers are joined by **SHA-256**, and by nothing else. No lookup
service, no index, no mapping table.

```
GitHub        files.csv                  url            -> sha256
Hugging Face  documents.parquet          document       -> source_sha256
Hugging Face  ab/cd/abcd....pdf          sha256          IS the address
```

Tier 3 is **content-addressed**: the file's name is its hash, so the identifier
and the location are the same string. Getting from a search result to the
original document therefore needs no resolution step:

```
search text -> source_sha256 -> <sha[0:2]>/<sha[2:4]>/<sha><ext>
```

Three properties follow, and all three are load-bearing:

1. **Deduplication is automatic.** 654 of the 6,963 downloads were byte-identical
   content served at more than one URL. Under content addressing they are one
   object. 7.476 GB becomes 6.559 GB with no logic.
2. **Every fetch is self-verifying.** Hash what you received and compare it to
   the filename. A mismatch means corruption or tampering, detectable offline.
3. **Provenance survives the rename.** `blob-catalog.csv` keeps every URL that
   served each hash, so the alias set is not lost when the URL path is dropped.

---

## 4. Schemas

### `documents.parquet`, 5,568 rows, one per logical document

| # | Column | Type | Notes |
|---:|---|---|---|
| 0 | `document_id` | string | `cbi:<sha256>`, the join key to pages |
| 1 | `source_sha256` | string | join key to Tier 3 blobs |
| 2 | `source_url` | string | canonical URL, alphabetically first of the aliases |
| 3 | `source_alias_count` | int64 | how many URLs served this content |
| 4 | `source_bytes` | int64 | size of the original file |
| 5 | `title` | string | PDF metadata title, else first heading, else derived from URL |
| 6 | `pdf_author` | string | from PDF metadata, often null |
| 7 | `pdf_creation_date` | string | raw PDF metadata; retained but never trusted as publication time |
| 8 | `published_at` | string | explicit date found in source/referrer metadata; usually null |
| 9 | `published_at_basis` | string | evidence for `published_at` |
| 10 | `analysis_year` | int64 | analysis proxy, never later than the 2026 snapshot |
| 11 | `analysis_year_basis` | string | explicit publication date or plausible PDF creation-date proxy |
| 12 | `retrieved_at` | string | crawler retrieval/check timestamp |
| 13 | `source_page_url` | string | page that referred to the downloaded file |
| 14 | `source_last_modified_at` | string | HTTP metadata where available |
| 15 | `document_class` | string | 15 values, see index summary |
| 16 | `authorship` | string | compatibility projection; not safe for v5.2 voice filtering |
| 17 | `legacy_authorship` | string | exact pre-v5.2 compatibility label |
| 18 | `host` | string | service that hosts the file, not its speaker |
| 19 | `author_org` | string | evidenced issuer where known |
| 20 | `document_role` | string | functional role, independent of issuer |
| 21 | `institutional_voice` | string | voice taxonomy described below |
| 22 | `voice_review_status` | string | `rule-classified`, `manual-reviewed`, or `unreviewed` |
| 23 | `voice_evidence` | string | rule or adjudication evidence for the voice label |
| 24 | `classification_basis` | string | legacy classifier/audit decision trail |
| 25 | `classification_confidence` | string | high 1,950 / medium 138 / low 3,480 |
| 26 | `page_basis` | string | what a page anchor means, see below |
| 27 | `source_format` | string | detected from magic bytes, not the file extension |
| 28 | `consultation_id` | string | e.g. `cp158`, null outside consultations |
| 29 | `engagement_id` | string | canonical `cpN` or `dpN` join key |
| 30 | `page_count` | int64 | |
| 31 | `extraction_engine` | string | exact engine and version evidence where recorded |
| 32 | `ocr_enabled` | int64 | 0 or 1 |
| 33 | `quality_low_text` | int64 | 0 or 1 |
| 34 | `quality_empty_pages` | int64 | final-text pages with fewer than 30 non-space characters |
| 35 | `extraction_selection_basis` | string | why this extraction won when a hash had alternatives |
| 36 | `alternate_extraction_count` | int64 | number of non-selected conversions for the same hash |
| 37 | `content_sha256` | string | SHA-256 of the ordered final page text |
| 38 | `content_cluster_id` | string | exact-text duplicate cluster key |
| 39 | `content_cluster_size` | int64 | documents carrying exactly the same extracted text |

### `pages.parquet`, 89,242 rows, one per page or pseudo-page

| # | Column | Type |
|---:|---|---|
| 0 | `document_id` | string |
| 1 | `source_sha256` | string |
| 2 | `page_number` | int32 |
| 3 | `authorship` | string |
| 4 | `authorship_basis` | string |
| 5 | `institutional_voice` | string |
| 6 | `voice_review_status` | string |
| 7 | `voice_evidence` | string |
| 8 | `document_class` | string |
| 9 | `page_basis` | string |
| 10 | `consultation_id` | string |
| 11 | `engagement_id` | string |
| 12 | `title` | string |
| 13 | `source_url` | string |
| 14 | `characters` | int32 |
| 15 | `text` | string |

Most descriptive columns are denormalised from `documents` deliberately.
`institutional_voice` is genuinely page-level so a composite can
contain regulator framing and stakeholder submissions without calling both the
same voice. Parquet is columnar, so unused columns cost nothing to read.

Both files use ZSTD compression. `pages.parquet` has 23 row groups, which is what
lets a reader skip most of the file when filtering.

`content_sha256` hashes the ordered final page strings separated by U+001E. It
forms 5,493 exact-text clusters. There are 140 documents in non-singleton
clusters; seven of those are the empty-document cluster, leaving 133 documents
with duplicated non-empty text and 69 excess non-empty records. Records are not
dropped because different URLs and publication contexts remain distinct
provenance. Use `content_cluster_id` when an analysis should count the text once.

### `institutional_voice`, the value that matters most

| Value | Documents | Meaning |
|---|---:|---|
| `cbi-institutional` | <!-- fact:voice.cbi-institutional -->338<!-- /fact --> | evidence-supported institutional Central Bank material |
| `stakeholder` | <!-- fact:voice.stakeholder -->1,739<!-- /fact --> | a respondent writing to the regulator; advocacy or consultation input |
| `unknown` | <!-- fact:voice.unknown -->3,480<!-- /fact --> | hosted by the Bank, but issuer/voice is not evidenced |
| `external-authority` | 3 | IMF-authored assessments hosted by the Bank |
| `cbi-staff` | 2 | attributable to a named staff member, not automatically the institution |
| `judicial-tribunal` | 2 | court or tribunal voice |
| `third-party` | 2 | other evidenced external speaker |
| `mixed` | <!-- fact:voice.mixed -->2<!-- /fact --> | composite with multiple voices; filter page rows |

Defaulting ambiguity to the regulator is the exact bug that put AIB's and Bank of
Ireland's lobbying positions into the Central Bank pile in an earlier version.
<!-- fact:classifier.assertions -->132<!-- /fact --> regression assertions, a
<!-- fact:audit.documents -->32<!-- /fact -->-document development set, and
114 SHA-keyed adjudications guard known failure modes. The 32-document set was
used during development, so it is an error detector, not a held-out accuracy
estimate. `VOICE-REVIEW-PROTOCOL.md` defines a separate 359-document review queue.

### `page_basis`, which decides whether a citation is valid

| Value | Meaning | Citable as a location |
|---|---|---|
| `source-page` | a true PDF page | **yes** |
| `slide` | one presentation slide | **yes** |
| `explicit-page-break` | author-inserted page break in a Word file | roughly |
| `single-pseudo-page` | the format has no pages; page 1 is the whole document | **no** |
| `archive-member` | one file inside a ZIP | no |

179 of the 323 Office documents are `single-pseudo-page`.

---

## 5. Access patterns

Choose by what you need, not by what is convenient.

| Need | Tier | Method | Bytes moved |
|---|---|---|---|
| Count, group, filter | 2 | DuckDB over HTTPS | KB |
| Full-text search | 2 | DuckDB over HTTPS | MB |
| Read a page's text | 2 | DuckDB over HTTPS | KB |
| Repeated heavy analysis | 2 | download about 51 MB once | about 51 MB |
| Rebuild the SQLite index | 1+2 | `make index` | none |
| See a chart or scanned page | 3 | `get_source.py --fetch` | one file |
| Re-extract with a better tool | 3 | fetch the blob | one file |

### Querying without downloading

```sql
INSTALL httpfs; LOAD httpfs;
SELECT d.title, p.page_number
FROM  'https://huggingface.co/datasets/aditya487/cbi-archive-corpus/resolve/9eb1a61caa3578257d9407eebb2f5bd27afd4acf/data/pages.parquet' p
JOIN  'https://huggingface.co/datasets/aditya487/cbi-archive-corpus/resolve/9eb1a61caa3578257d9407eebb2f5bd27afd4acf/data/documents.parquet' d
  USING (document_id)
WHERE d.institutional_voice = 'cbi-institutional'
  AND d.voice_review_status IN ('rule-classified', 'manual-reviewed')
  AND lower(p.text) LIKE '%operational resilience%'
LIMIT 20;
```

This works because of two mechanisms in combination:

1. **Parquet is columnar and self-describing.** Values for one column are stored
   contiguously, and a footer at the end of the file maps every column and row
   group to a byte range.
2. **HTTP serves byte ranges.** A client sends `Range: bytes=X-Y`, the server
   replies `206 Partial Content`.

So a reader fetches the footer, a few KB, looks up which ranges hold the columns
in the query, and fetches only those. A query touching `institutional_voice` never reads
the 46 MB `text` column. `publish/demo_how_it_works.py` demonstrates this against
the live URL and times it against a full download.

### Downloading the corpus

```bash
python outputs/cbi-research/scripts/bootstrap.py --dataset aditya487/cbi-archive-corpus
```

### Retrieving an original document

```bash
python publish/get_source.py --search "operational resilience" --voice cbi-institutional --limit 3
python publish/get_source.py --sha e5dabf14e1e876c484b3fd0d9b4fe86925befc868391e73aeddd6b0218a3a6cc --fetch
```

Or construct the URL directly, since the hash is the address:

```
https://huggingface.co/datasets/aditya487/cbi-archive-raw/resolve/d7d79f81a981318f243139b4a55ff5caed2cfbd4/e5/da/e5dabf14....pdf
```

---

## 6. Rebuilding any layer

```bash
make index      # Tier 2 Markdown -> SQLite index, about 30 seconds on this machine
make dataset    # SQLite index -> Parquet, about 4 seconds
make test       # 132 classifier assertions plus Office extraction regressions
make verify     # re-hash every source and output, check page markers
```

Full pipeline from raw source, in order:

```
cbi-archive.mjs inventory|download   crawl and download        hours
audit_pdfs.py                        structural PDF audit
convert_pdfs.py                      PDF -> page-anchored Markdown
convert_office.py                    DOCX/DOC/ZIP/PPTX -> Markdown
validate_corpus.py                   re-hash everything, check structure
qa_extraction_quality.py             grade extraction fidelity
build_search_index.py                Markdown -> SQLite FTS5
run_topic_scan.py                    topic discovery
export_dataset.py                    SQLite -> Parquet
build_blob_tree.py                   content-address the raw files
```

Only the crawl is irreproducible: re-running it captures the site as it is
**now**, not as it was on 25 August 2026. Anything withdrawn since would be lost.
That is the reason Tier 3 is published rather than regenerated.

---

## 7. Integrity

Every layer is hash-verified, and the hashes chain.

| Check | What it proves |
|---|---|
| `files.csv` `sha256` per URL | the download matches what the server sent |
| `conversion-manifest.csv` `markdown_sha256` | the extracted text has not changed |
| `validate_corpus.py` | re-reads every source and output from disk and re-hashes |
| Tier 3 filename | any fetched blob verifies against its own name |
| v5.2 index SHA-256 | `0870a95847400e3419cded329ef0d7cba13403ba1ce186a303343c53d3225eb0` |
| `RELEASE.lock.json` | immutable Git/Hugging Face revisions and published-artifact hashes |

`publish/verify_dataset.py` downloads the two pinned Parquet artifacts to a
temporary directory over certificate-verified HTTPS, checks their SHA-256
digests, then verifies the institutional-voice split, row totals, all raw object
paths and available LFS object IDs, and a real join query.

---

## 8. Gotchas

1. **Historical conversion-manifest paths may use Windows separators.** The
   crawler now emits portable `files.csv` paths. Scripts reading conversion
   manifests still normalise with `.replace("\\", "/")`.
2. **`pdf-audit.csv` contains NUL bytes** from PDF metadata. Strip them on read
   or Python's `csv` module raises `_csv.Error: line contains NUL`.
3. **Seven versioned or legacy SQLite files exist, one is current.** See
   `index/README.md`. A local v5.2 smoke build may also be present. The database
   at `work/live-index/` is a partial build covering 3,259 of 5,568 documents
   and carries no warning of its own.
4. **87 documents extract below `ok`**, graded in `qa/extraction-quality.csv`:
   <!-- fact:quality.grade.gappy -->36<!-- /fact --> `gappy`,
   <!-- fact:quality.grade.garbled -->25<!-- /fact --> `garbled`,
   <!-- fact:quality.grade.thin -->19<!-- /fact --> `thin`, and
   <!-- fact:quality.grade.empty -->7<!-- /fact --> `empty`. Chart-heavy statistical
   releases are the worst and can render "March" as "~~M~~ arch" while their
   numbers survive intact. Check the grade before quoting prose.
5. **Counting is discovery, not evidence.** Topic frequency mostly measures how
   many firms answered a consultation. CP76 and CP88 alone contributed 277 credit
   union submissions and will skew any naive frequency analysis.
6. **`publish/blobs/` must never enter git.** It is 6,309 hard links to 6.56 GB.
   `.gitignore` covers it; do not override.
7. **Format labels from URL extensions are wrong in both directions.** Four
   Office files are served as `.pdf`, and two PDFs are served as `.docx`.
   Converters dispatch on magic bytes. `source_format` reflects the detection,
   not the extension.

---

## 9. Scripts

| Script | Purpose |
|---|---|
| `scripts/bootstrap.py` | fetch the published corpus onto a fresh machine |
| `scripts/build_search_index.py` | Markdown to SQLite FTS5, multi-corpus |
| `scripts/classify_provenance.py` | issuer, role and institutional-voice classifier |
| `scripts/test_classify_provenance.py` | 132 regression assertions |
| `scripts/export_voice_review_scope.py` | deterministic high-risk voice-review queue |
| `scripts/evaluate_provenance.py` | evaluate against the reviewed regression set |
| `scripts/release_lock.py` | read and validate immutable release coordinates |
| `scripts/convert_pdfs.py` | PDF to page-anchored Markdown |
| `scripts/convert_office.py` | DOCX, DOC, ZIP, PPTX, magic-byte dispatch |
| `scripts/validate_corpus.py` | re-hash and structurally validate |
| `scripts/qa_extraction_quality.py` | grade extraction fidelity |
| `scripts/export_dataset.py` | SQLite to Parquet |
| `scripts/analyze_key_datasets.py` | the structured-data figures in the thesis |
| `scripts/mine_industry_pain.py` | persistent-pain scan over stakeholder voice |
| `publish/build_blob_tree.py` | content-address the raw archive |
| `publish/get_source.py` | search text, retrieve the original document |
| `publish/verify_dataset.py` | prove the published corpus is correct |
| `publish/demo_how_it_works.py` | demonstrate range-request querying |

---

## 10. Rights and reuse

The published datasets use mixed-rights metadata. Only 71 open-data resources
carry an explicit CC BY 4.0 licence. Other Central Bank-authored material may be
reusable under the site's PSI terms, but stakeholder submissions, personal
information and other third-party rights require separate care.

> Contains Irish Public Sector Information licensed under a Creative Commons
> Attribution 4.0 International (CC BY 4.0) licence.

Use the attribution above where the PSI licence applies. CKAN licence titles and
URLs are retained per resource in `files.csv`. The PSI licence
excludes personal information, third-party rights, trademarks, crests, logos and
official symbols, and prohibits implying endorsement.

See `RIGHTS-REVIEW.md`. This is a factual engineering note, not legal advice.

Note for anyone embedding this pipeline in a hosted product: **PyMuPDF is
AGPL-3.0**. Private research use is fine. Offering it as a network service
requires releasing your source under the same licence, or buying a commercial
licence from Artifex.
