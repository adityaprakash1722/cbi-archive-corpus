# Working in this repository

A research corpus built from the Central Bank of Ireland's public archive, and
the analysis built on top of it. Read this before touching anything.

## The one rule that matters

**Check `authorship` before you quote anything.**

This archive contains two kinds of document that read alike and mean the
opposite:

- `authorship = 'central-bank'` (3,809 docs) is the regulator speaking. A
  finding, a rule, a supervisory expectation.
- `authorship = 'stakeholder'` (1,656 docs) is a bank, insurer or trade body
  writing **to** the regulator during a consultation. This is advocacy. These
  firms have a standing incentive to claim that requirements are burdensome and
  disproportionate.
- `authorship = 'unresolved'` (103 docs) is genuinely ambiguous. It is a real
  answer. **Never fold it into `central-bank`** — defaulting ambiguity to the
  regulator is the exact bug that put AIB's and Bank of Ireland's lobbying
  positions into the Central Bank pile in an earlier version.

Reporting a stakeholder claim as a regulatory finding is the single easiest way
to produce confidently wrong analysis from this data. If you cite a stakeholder
document, say so in the sentence.

## Which index to use

There are three SQLite files. Only one is current.

| File | Documents | Use |
|---|---:|---|
| `outputs/cbi-research/index/cbi-corpus-v4-5568docs.sqlite` | 5,568 | **Yes. This one.** |
| `cbi-corpus-v3-5568docs.sqlite` | 5,568 | Superseded. 441,610 characters of page text missing. |
| `cbi-corpus-v2-5568docs.sqlite` | 5,568 | Superseded. 55 provenance errors. |
| `cbi-corpus.sqlite` | 5,246 | Superseded. Wrong provenance, missing the office corpus. |
| `work/live-index/cbi-corpus.sqlite` | 3,259 | Never. Partial build from an interrupted run. |

v4 SHA-256: `a89923ba64a121792ba2f2776edb66fa9e8179f1914492cdfb17165efecd29ca`

None of these are in git. Run `make index` to build v4 locally, or `make fetch`
to pull the Parquet corpus, which is usually what you actually want.

## Layout

```
outputs/
  IRELAND-FINANCIAL-SYSTEM-AND-STARTUP-THESIS.md   the analysis
  CBI-ARCHIVE-ANALYSIS-METHOD.md                   how the corpus was built
  REMEDIATION-2026-08-26.md                        what was wrong and got fixed
  cbi-archive/
    cbi-archive.mjs                    the crawler, zero-dependency Node
    cbi-data/manifests/files.csv       every URL, SHA-256, bytes, referrers  [tracked]
    cbi-data/files/                    6.56 GB of raw source              [not tracked]
  cbi-research/
    scripts/                           the whole pipeline, 25 Python files
    corpus/conversion-manifest.csv     per-document conversion record     [tracked]
    corpus/markdown/                   202 MB of page-anchored Markdown   [not tracked]
    index/                             SQLite build artifacts             [not tracked]
    qa/                                validation, provenance and extraction grades
    structured/                        CSV, workbook and XML profiling
    analysis-v2/                       topic scan and evidence candidates
publish/hf/                            the public dataset, ready to upload
```

**`HANDOVER.md` first if you are new to this project.** It covers what the
research has actually found, what is unfinished, and two confident claims that
turned out to be wrong. The rest of the docs describe the corpus; that one
describes the work.

**`PUBLISHING.md`** covers why these services were chosen, the accounts, and the
runbook for updating each one. Read its decision log before proposing a change to
where anything is hosted.

**`RIGHTS-REVIEW.md`** is the personal-data and licence screen: what the
corpus actually contains, why the PPSN hits were all VAT numbers, and the 18
documents that need a human decision before wider sharing.

**`EXTRACTION-REVIEW.md`** reads the 33 flagged stakeholder documents and says
which of the bad extractions actually matter, and records the recovery pass
that cut them from 112 to 82. One document is 94% unreadable; the rest were
mostly scanned cover pages.

**`STORAGE.md` is the full map**: every artifact, where it lives, why, the Parquet
schemas, access patterns and rebuild commands. Read it before moving or fetching
anything.

## The three pieces and how they join

Nothing here is a monolith. The project lives in three places, joined by one key.

| Where | What | Size |
|---|---|---|
| GitHub | pipeline, manifests, analysis, docs | 10 MB |
| Hugging Face `cbi-archive-corpus` | the extracted text as Parquet | 47 MB |
| Hugging Face `cbi-archive-raw` | the original PDFs and spreadsheets | 6.56 GB |

**The join key is the SHA-256 hash**, and it appears in all three:

- `files.csv` in this repo maps every source URL to its hash
- `documents.parquet` carries `source_sha256` on every document
- the raw repo stores each file at `<ab>/<cd>/<sha256>.pdf`

Because the files are content-addressed, the identifier and the location are the
same string. No lookup service is needed to get from a search result to the
original document:

```
search the text  ->  source_sha256  ->  ab/cd/abcd....pdf
```

`publish/get_source.py` does this end to end. Reach for it when you need the
document as a human would see it, which mainly means charts, diagrams, scanned
pages, and any of the 82 documents graded as extracting badly.

For everything else, query the Parquet over HTTPS and download nothing. DuckDB
reads the file's footer, finds which byte ranges hold the columns you asked for,
and fetches only those.

## Gotchas that will cost you an hour

1. **Manifest paths use Windows separators.** `files.csv` and
   `conversion-manifest.csv` were written on Windows and contain backslashes.
   Every script normalises with `.replace("\\", "/")`. If you write a new one
   that joins a manifest path to a root, do the same or it will silently find
   nothing on Linux and macOS.
2. **`page_basis` is not always a page.** PDFs have true page anchors. Office
   documents mostly do not: 179 of 323 are `single-pseudo-page`, meaning the
   anchor identifies the document, not a position in it. Only `source-page` and
   `slide` are citable as locations.
3. **82 documents extract badly.** Graded `gappy`, `garbled`, `thin` or `empty`
   in `qa/extraction-quality.csv`. Chart-heavy statistical releases are the worst
   offenders and can render "March" as "~~M~~ arch" while their numbers survive
   intact. Check the grade before quoting prose from one.
4. **`pdf-audit.csv` contains NUL bytes** from PDF metadata. Strip them on read
   or Python's `csv` module raises.
5. **Counting is discovery, not evidence.** Topic hit counts mostly measure how
   many firms answered a given consultation. Two consultations, CP76 and CP88,
   contributed 277 credit union submissions between them and will skew any naive
   frequency analysis.

## Reproducing anything

```bash
make fetch      # pull the Parquet corpus (47 MB), no build needed
make materialize # regenerate the Markdown corpus from the Parquet, for a fresh clone
make index      # rebuild the v4 SQLite from the Markdown corpus (~15s)
make test       # classifier regression suite, 97 assertions
make test-fresh-rebuild   # prove a clone can rebuild the index from published data
make verify     # re-hash every source and output, check page markers
```

All figures in the thesis reproduce exactly from `scripts/analyze_key_datasets.py`.
That was checked field by field across platforms: the only differences are
absolute file paths.
