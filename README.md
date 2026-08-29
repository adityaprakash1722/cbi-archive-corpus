# Central Bank of Ireland archive: corpus and analysis

A crawl of the Central Bank of Ireland's public archive, turned into a
page-anchored, provenance-classified research corpus, plus the analysis built on
it.

**5,568 documents. 88,783 source pages. 190,941,651 characters.**

| | |
|---|---|
| Crawl snapshot | 25 August 2026 |
| Downloaded | 6,963 files, 7.476 GB, 21 URLs failed (all 404, all recorded) |
| Unique by SHA-256 | 6,309 files, 6.559 GB |
| Corpus release v5 | 5,568 documents, 88,783 pages, zero conversion errors |
| Published as | 47 MB of Parquet |

`RELEASE.lock.json` pins the published v5 Git and Hugging Face revisions plus
the artifact hashes; scripts never silently substitute Hugging Face `main` for
that immutable release.

## Start here

- `CLAUDE.md` / `AGENTS.md` — read before touching anything. Explains the one
  rule that matters and the five gotchas that cost an hour each.
- `outputs/IRELAND-FINANCIAL-SYSTEM-AND-STARTUP-THESIS.md` — the analysis.
- `outputs/CBI-ARCHIVE-ANALYSIS-METHOD.md` — how the corpus was built and what
  its limits are.
- `outputs/REMEDIATION-2026-08-26.md` — what was wrong with the first version and
  how it was fixed. Worth reading before trusting anything.

## Quick start

```bash
make fetch DATASET=aditya487/cbi-archive-corpus   # 47 MB, no build required
make test                                      # 104 classifier assertions
```

Or query the corpus without downloading it at all:

```sql
SELECT authorship, count(*)
FROM 'https://huggingface.co/datasets/aditya487/cbi-archive-corpus/resolve/bcbd2e84bff7655794eb9985b5f6bd1e428d263e/data/documents.parquet'
GROUP BY 1;
```

## Rights and reuse

This is a mixed-rights corpus. Only 71 open-data resources carry explicit CC BY
4.0 metadata; the rest includes Central Bank material under its PSI terms and
stakeholder or personal submissions for which third-party rights may apply.

> Contains Irish Public Sector Information licensed under a Creative Commons
> Attribution 4.0 International (CC BY 4.0) licence.

Unofficial. Not affiliated with or endorsed by the Central Bank of Ireland.
Read `RIGHTS-REVIEW.md` before redistribution or commercial use.
