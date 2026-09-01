# Central Bank of Ireland archive: corpus and analysis

A crawl of the Central Bank of Ireland's public archive, turned into a
page-anchored, provenance-classified research corpus, plus the analysis built on
it.

**5,568 documents. 89,242 page or pseudo-page rows. 179,924,863 extracted characters.**

> v5.1 speaker labels are unsafe for regulator-only filtering and two DOCX
> extracts were materially corrupt. See `ERRATA-V5.1.md`. v5.2 replaces the
> overloaded label with evidence-bearing institutional voice fields.

| | |
|---|---|
| Crawl snapshot | 25 August 2026 |
| Downloaded | 6,963 files, 7.476 GB, 21 URLs failed (all 404, all recorded) |
| Unique by SHA-256 | 6,309 files, 6.559 GB |
| Corpus release v5.2 | 5,568 documents, 89,242 page or pseudo-page rows, 87 extraction cautions |
| Published as | 48.0 MB of Parquet plus auditable compressed manifests |

`RELEASE.lock.json` pins the published release's Git and Hugging Face revisions plus
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
- `ERRATA-V5.1.md` — the independent-review defects corrected in v5.2.

## Quick start

```bash
make fetch DATASET=aditya487/cbi-archive-corpus   # about 51 MB, no build required
make test                                      # provenance and Office extraction regressions
```

Or query the corpus without downloading it at all:

```sql
SELECT institutional_voice, voice_review_status, count(*)
FROM 'https://huggingface.co/datasets/aditya487/cbi-archive-corpus/resolve/9eb1a61caa3578257d9407eebb2f5bd27afd4acf/data/documents.parquet'
GROUP BY 1, 2;
```

## Rights and reuse

This is a mixed-rights corpus. Only 71 open-data resources carry explicit CC BY
4.0 metadata; the rest includes Central Bank material under its PSI terms and
stakeholder or personal submissions for which third-party rights may apply.

> Contains Irish Public Sector Information licensed under a Creative Commons
> Attribution 4.0 International (CC BY 4.0) licence.

Unofficial. Not affiliated with or endorsed by the Central Bank of Ireland.
Read `RIGHTS-REVIEW.md` before redistribution or commercial use.
