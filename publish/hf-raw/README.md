---
pretty_name: Central Bank of Ireland Archive, Original Source Files
license: other
license_name: mixed-see-rights-and-reuse
language:
  - en
tags:
  - regulation
  - finance
  - ireland
  - public-sector
  - primary-sources
size_categories:
  - 1K<n<10K
configs:
  - config_name: catalog
    data_files:
      - split: train
        path: blob-catalog.csv
---

# Central Bank of Ireland Archive: original source files

**6,309 original files, 6.56 GB.** Every PDF, spreadsheet, Word document and
archive gathered from the Central Bank of Ireland's public website, stored by
content hash so that a search result can be turned back into the document a
human would actually read.

This is the **raw tier**. If you want the text, you almost certainly want
[`aditya487/cbi-archive-corpus`](https://huggingface.co/datasets/aditya487/cbi-archive-corpus)
instead: 5,568 documents and 89,242 page or pseudo-page rows as Parquet, queryable over
HTTPS without downloading anything.

Come here when the text is not enough: charts, diagrams, scanned pages, tables
that did not survive extraction, and the 87 documents graded below `ok`.

## How files are addressed

Every file lives at its own SHA-256:

```
<first 2 hex chars>/<next 2>/<full sha256><extension>
```

So `ae0acdc7...b49e.pdf` is at `ae/0a/ae0acdc7...b49e.pdf`. The identifier and
the location are the same string, which means no lookup service is needed to get
from a search hit to the original:

```
search the text  ->  source_sha256  ->  ae/0a/ae0acdc7....pdf
```

`source_sha256` appears on every row of `documents.parquet` in the corpus
dataset, so the two repositories join without any shared infrastructure.

**Note for anyone reading older documentation:** files are at the repository
root, not under a `blobs/` prefix. Some early drafts said otherwise and were
wrong.

## What is here

| Format | Files |
|---|---:|
| PDF | 5,246 |
| XLSX | 447 |
| CSV | 246 |
| DOCX | 201 |
| DOC | 71 |
| ZIP | 49 |
| XLS | 42 |
| XML | 5 |
| PPTX | 2 |

These are URL/path-declared formats. Magic-byte checks found three `.pdf` paths
containing Word bytes, one containing HTML, and two `.docx` paths containing PDF
bytes. The raw objects are preserved unchanged; converters dispatch on detected
content where necessary.

Plus three metadata files:

- **`blob-catalog.csv`** maps every hash to its path, format, byte count, and
  every URL that served it, including aliases. 6,309 rows.
- **`blob-summary.json`** records how the tree was built, including the 654
  duplicate copies collapsed by content addressing, which saved 917 MB.
- **`page-catalog.csv`** maps immutable HTML page-context snapshots to source
  URLs. It is empty for the August 2026 snapshot because the original crawler
  retained referrer URLs/statuses but not HTML bodies. Future refreshed pages
  are stored under `page-context/<sha-prefix>/<sha256>.html` by default.

## Getting a file

```bash
python get_source.py --search "operational resilience" --limit 3 --fetch
```

`get_source.py` lives in the
[GitHub repository](https://github.com/adityaprakash1722/cbi-archive-corpus).
It searches the Parquet text, resolves the hash, downloads the original, and
verifies the SHA-256 before writing it. Or fetch directly:

```
https://huggingface.co/datasets/aditya487/cbi-archive-raw/resolve/main/ae/0a/<sha256>.pdf
```

For a reproducible citation, replace `main` with the immutable `raw_revision`
recorded in `RELEASE.lock.json` in the GitHub repository.

The Hub exposes SHA-256 metadata for the 5,296 files stored through LFS. The
remaining 1,013 are ordinary Git blobs, for which the tree API proves path and
size but does not expose the file's SHA-256. `blob-catalog.csv` carries the
expected hash for all 6,309; `publish/verify_dataset.py` checks every pinned path
and size and every available LFS hash.

## Rights and reuse

**Read this before redistributing.**

These documents were published by the Central Bank of Ireland on its public
website. They are gathered here for research. Copyright and database rights
remain with the Central Bank of Ireland and, where applicable, with the third
parties who wrote the submissions.

- **71 files** carry an explicit Creative Commons Attribution 4.0 licence, from
  the Bank's open-data portal.
- **6,238 files** carry no explicit licence. Their reuse rests on the Central
  Bank's website terms, which **exclude personal information and third-party
  rights** from the general permission to reuse.

That exclusion is the reason this repository is framed as research material
rather than as an open dataset. It is a mirror of public documents, offered so
that findings drawn from the text can be checked against the originals.

### Personal data

Roughly a third of these documents are consultation submissions, most from banks,
insurers, law firms and trade bodies. **A small number are from private
individuals writing in a personal capacity.**

The corpus has been screened for personal data. Findings, in full:

- **No national identifiers.** All 17 candidates matching the Irish PPS number
  pattern turned out to be **company VAT numbers**, which share the same shape
  (seven digits and a letter). Every one appeared on a corporate letterhead.
- **No personal payment details.** All 4 IBAN matches are the Central Bank's own
  published accounts for levy and fee payments.
- **18 candidates** were manually reviewed: nine are private individuals and
  nine are people writing in a public or professional role. Twelve of the 18
  are stakeholder documents. The nine private submissions are 0.52% of the
  1,739 stakeholder documents in v5.2. The decisions are recorded in
  `RIGHTS-REVIEW.md` and `qa/individual-submission-review.csv`.
- Email addresses and phone numbers appear widely but are overwhelmingly
  corporate contact points already printed on letterheads.
- The Central Bank applies its own redaction upstream: 206 documents reference
  redaction, and some personal email addresses arrive already masked.

The full method and results are in `RIGHTS-REVIEW.md` in the GitHub repository.

### Takedown

**If you are named in one of these documents and would prefer not to be, the
material will be removed. No justification is required and no argument will be
made.**

Open a discussion on this dataset, or contact the maintainer through the
[GitHub repository](https://github.com/adityaprakash1722/cbi-archive-corpus).
Please include the SHA-256 or the URL if you have it, though a description is
enough.

The same applies to any rights holder who objects to a document being mirrored
here.

## What this is not

- **Not official.** Not affiliated with, endorsed by, or connected to the Central
  Bank of Ireland.
- **Not authoritative.** For the current text of any regulation, rule or
  guidance, go to centralbank.ie. Documents here are a snapshot taken in August
  2026 and some are many years old and superseded.
- **Not complete.** It is what a crawl of the public site found, not the Bank's
  full record.
- **Not advice.** Nothing here is legal, financial or regulatory advice.

## One thing that will mislead you if you skip it

The corpus contains two kinds of document that read alike and mean the opposite:
the regulator setting expectations, and firms lobbying the regulator about them.
A consultation response from a bank arguing that a requirement is
disproportionate is **advocacy**, not a regulatory finding, and treating it as
one is the easiest way to produce confidently wrong analysis from this data.

Use `institutional_voice`, not the legacy `authorship` field, for this decision.
v5.2 labels 338 documents `cbi-institutional`, 1,739 `stakeholder`, three
`external-authority`, two each `cbi-staff`, `judicial-tribunal`, `third-party`
and `mixed`, and 3,480 `unknown`. The large unknown class
is deliberate: a file being hosted on centralbank.ie is not proof that the Bank
authored it. Check `voice_review_status` and the page-level fields before quoting.

## Citation

```bibtex
@misc{cbi_archive_raw_2026,
  title  = {Central Bank of Ireland Archive: Original Source Files},
  author = {Prakash, Aditya},
  year   = {2026},
  url    = {https://huggingface.co/datasets/aditya487/cbi-archive-raw}
}
```
