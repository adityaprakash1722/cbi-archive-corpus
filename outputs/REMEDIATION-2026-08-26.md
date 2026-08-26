# Remediation pass, 26 August 2026

This records a correction pass run after an independent audit of the archive
project, and after Codex's own re-verification of that audit. It states what was
wrong, what was changed, and what is still open.

> **Follow-up verification:** a second review found 55 remaining provenance
> precedence errors and two silently omitted DOCX tables. Both are corrected in
> pipeline version `office-0.2.0` and index v3; counts in this note are v3 counts.

## 1. Findings, and who was right

| Finding | Verdict | Acted on |
|---|---|---|
| Stakeholder classifier keyed on the substring `response` only | Confirmed, material | Rewritten, tested, index rebuilt |
| 323 downloaded DOC/DOCX/ZIP/PPTX files never analysed | Confirmed, material | Converted and indexed |
| Workbook and provenance labels are filename heuristics presented as fact | Confirmed | Basis and confidence now stored per document |
| "Zero conversion errors" overstates extraction fidelity | Confirmed, limited impact | New QA pass and grades |
| Stale 423 MB partial index shares a filename with the real one | Confirmed | Warning file written, disambiguating filename used |
| Latent Python defects (silent 0% change, last-row assumption, no hierarchy guard) | Confirmed | Fixed; all figures reproduce identically |
| Safeheld and Imperium(L) do not exist | **The audit was wrong** | Both verified real; safeguarding candidate promoted |
| PSR treats APP fraud generally as unauthorised and fully reimbursable | **The audit was wrong** | Corrected below |
| Ireland-only economics are too small for venture scale | Substantially correct | Reflected in the revised opportunity view |
| The scorecard implies precision it does not have | Correct | Top two are now co-finalists |

### The two audit errors, stated plainly

**Safeheld and Imperium(L) are real.** Safeheld sells continuous reconciliation
and breach detection for client funds, assets and reserves. Imperium(L) Prism is
a reconciliation and safeguarding control platform for firms holding customer
money. The audit's web searches failed to surface either. That was a search
failure, not a fabrication by the original analysis.

The competitive conclusion needed a second correction. [Guardexia](https://guardexia.com/ps25-12/)
explicitly markets both UK PS25/12 and EU PSD2 Article 10 support, while
[Safeheld](https://safeheld.com/) markets EU PSD2/MiCA and global safeguarding.
[Imperium(L)](https://www.imperiuml.com/payments-e-money-cass-15/) is clearly
UK CASS-focused. An Ireland-specific adapter may still be useful, but the public
evidence does **not** establish it as an empty category or defensible moat. That
must be tested in competitive and buyer discovery.

**The PSR provision is narrower than the audit claimed.** The audit asserted that
the Payment Services Regulation would treat APP fraud generally as an unauthorised
transaction requiring full reimbursement. It does not. Article 59 of the
[Council's 2026 compromise text](https://data.consilium.europa.eu/doc/document/ST-8221-2026-INIT/en/pdf)
covers
impersonation specifically: a third party pretending to be an employee of the
consumer's payment service provider, using communication channels attributed to
that provider. The resulting payments
remain **authorised transactions** subject to a special liability rule, not
unauthorised ones. Reimbursement is conditional on the consumer reporting the
fraud to police and notifying the provider without undue delay, and is defeated by
fraud or gross negligence on the consumer's part, which the provider must prove.
Refund or a reasoned refusal is due within 15 business days once notified.

The strategic conclusion still moves, just less dramatically than the audit
suggested. The PSR creates monitoring liability, reimbursement and investigation
workflows, fraud-data reporting and mandatory information-sharing arrangements
between providers. That is real demand for consistent evidence capture and police
reporting, and it is also a reason a scheme operator or a large vendor may absorb
the workflow. It belongs in kill test 1 alongside the BPFI vendor question.

## 2. Provenance classification

The original rule, in `build_search_index.py`:

```python
if "response" in name and not any(cue in name for cue in central_bank_cues):
    return "stakeholder-consultation-submission", consultation_id
```

Three families of stakeholder document escaped it:

1. **"submission"**: 289 files, for example `cp45-submission-from-aib.pdf` and
   `cp45-submission-from-bank-of-ireland.pdf`, filed as Central Bank material.
2. **"feedback-from"**: 123 files, for example
   `cp51-feedback-from-generali-paneurope.pdf`, filed as Central Bank *feedback
   statements*. That class was 215 documents, of which only 81 were genuine Bank
   feedback statements. It was 57% mislabelled.
3. **Bare responder names**: `blackrock.pdf`, `northern-trust-(ireland)-limited.pdf`,
   `alternative-investment-management-association.pdf`. No filename cue exists, so
   no filename rule can ever resolve these.

Family 3 is why the fix is not simply a longer keyword list.
`scripts/classify_provenance.py` runs two passes:

- **Pass 1, filename and path.** Central Bank document types (feedback statement,
  note, an exact public-response title, or a bare `cpNN` filename) take priority
  only where the cue is issuer-specific. Explicit attribution then outranks generic
  words such as consultation paper, discussion paper, guidance and rulebook. That keeps
  `note-from-the-financial-regulator-in-relation-to-submissions-received-on-cp43`
  correctly Bank material. Attribution cues then catch submission, response,
  feedback-from, comments-from and cover-letter-from, including the two
  misspellings that actually occur in the archive ("reponse", "repsonse").
- **Pass 2, document text.** For anything pass 1 cannot resolve, the opening two
  pages are scored against issuer-voice phrases ("this consultation paper",
  "closing date for submissions", "the central bank invites") and respondent-voice
  phrases ("we welcome the opportunity", "yours sincerely", "on behalf of our
  members"). A bare citation of "Consultation Paper CP76" is weighted at 1, not 3,
  because a respondent naturally cites the consultation it is answering. Getting
  that weight wrong put the Irish League of Credit Unions on the Bank's side of
  the line in an intermediate run.

Anything still undecided is `unresolved`. That is a real answer, and it must not
be counted as Central Bank material.

| | Original | Corrected |
|---|---:|---:|
| Central Bank | 4,112 | 3,807 |
| Stakeholder | 1,134 | 1,656 |
| Unresolved | 0 | 105 |

Confidence: 5,340 high, 123 medium (content-decided), 105 low. Every document
stores `classification_basis`, the rule that produced its label. Full
before-and-after trail: `cbi-research/qa/provenance-classification.csv`.

`scripts/test_classify_provenance.py` holds 94 assertions, including all 55
precedence-conflict filenames found by the follow-up audit, as well as all three
families, the Central Bank override, the misspellings, discussion papers, and the
content pass in both directions. It passes.

### Corrected topic scan

| Topic | Documents | Stakeholder | Previously reported | Understated by |
|---|---:|---:|---:|---:|
| Payments | 1,667 | 322 | 219 | 47% |
| Complaints and redress | 1,117 | 274 | 136 | 101% |
| Fraud and scams | 508 | 133 | 95 | 40% |
| Consumer harm | 609 | 252 | 166 | 52% |
| Data quality | 116 | 8 | 4 | 100% |

## 3. The 323 missing documents

`convert_pdfs.py` filters `format == "PDF"`, so nothing else was ever converted.

| Format | Files | Handling |
|---|---:|---|
| DOCX | 201 | python-docx, headings and tables preserved; LibreOffice fallback |
| DOC | 71 | LibreOffice headless |
| ZIP | 49 | Inventory and profile, documentation members in full |
| PPTX | 2 | One page per slide, speaker notes included |

All 323 convert with zero errors. 678 pages, 19 MB of Markdown.

Three decisions worth recording:

**ZIP files are profiled, not transcribed.** The first run dumped every member
body and produced 705 MB of Markdown across 100,216 pseudo-pages, against 88,106
real pages in the entire PDF corpus. These are XBRL taxonomy packages: one
contained 31,185 schema files. Indexing that would have made machine schema
dominate every topic count, which is exactly the frequency bias the analysis is
meant to avoid. The member listing, suffix profile and target namespaces are the
evidence; schema bodies are not.

**Five DOCX packages need package-level recovery:** three unusual
`word/#Contents` relationship targets use the LibreOffice fallback, and two files
are actually PDFs served with a `.docx` extension. Two additional DOCX files contain
irregular merged-cell grids. They now use a loss-avoiding raw-XML table fallback;
the earlier converter silently dropped material tables while still reporting success.

**The last two were PDFs served with a `.docx` extension.** This is the mirror
image of the four Office files served as `.pdf` that the original pipeline found.
Converters now dispatch on magic bytes rather than the URL extension, and those two
files get real page anchors. One of them turned out to be byte-identical to a file
already in the PDF corpus, so the indexer's duplicate-SHA guard dropped it. The
final corpus is 5,568 documents, not 5,569.

**Honesty about anchors.** Every office document records `page_basis`. 179 of 323
are `single-pseudo-page`, meaning the format has no pages and the whole document is
"page 1". Those are searchable but not page-citable. Only `source-page` and `slide`
are real locations.

## 4. Extraction quality

`scripts/qa_extraction_quality.py` adds the check structural validation cannot
make: how much text a page actually holds.

| Grade | Documents |
|---|---:|
| ok | 5,456 |
| gappy (30%+ of pages nearly blank) | 63 |
| garbled (encoding damage) | 26 |
| thin (under 200 characters per page) | 16 |
| empty | 7 |

Median density is 1,619 non-space characters per page and 2.44% of pages are
effectively empty, so the corpus is in good shape. But "zero conversion errors"
means zero exceptions, not zero content loss, and the method note now says so.
Flagged documents: `cbi-research/qa/extraction-quality-flagged.csv`.

## 5. Code fixes

| Defect | Fix |
|---|---|
| Missing SME comparison period reported as a real 0.0% change | Raises `MissingComparisonPeriod` |
| Retail rates assumed the last CSV row is the latest period | Takes the maximum date and warns if the file is not ascending |
| SME sector sum had no parent/child double-count guard | Checks outstanding balance, transactions and new lending for parent/child overlap |
| Missing retail-rate observation was silently replaced with zero | Missing required comparison rates now raise an error |
| DOCX merged-table errors were swallowed | Whole table is rebuilt from raw Word XML and the fallback is recorded |
| Legacy `.doc` extraction kept only the longest printable run | Keeps every run in stream order; LibreOffice path preferred |
| Seven scripts joined Windows manifest paths without normalising | Separator normalised; the pipeline now runs on Linux too |
| `pdf-audit.csv` contains NUL bytes and broke `csv` on Python 3.10 | Stripped on read |
| No Python tests anywhere | 94 assertions for the classifier, including all 55 audited conflicts |

**Reproducibility check.** After those changes, the full structured-data analysis
was re-run from scratch on Linux and compared field by field against the original
Windows output. Every analytical value is identical: the €14.647bn SME balance,
the 2.08% decline, the 12.78% new-lending rise, the 5.04% weighted rate, the
€15.459bn and 48,896 mortgage figures, and all five June 2026 retail rates. The
only differences are the absolute source file paths.

## 6. What is still open

1. **DORA and regulatory reporting were scored against an incomplete corpus.**
   They should be re-scored against the office corpus. The 49 ZIPs are mainly
   Solvency/reporting taxonomy packs and are not, by themselves, DORA evidence;
   the newly indexed DORA PPTX and DOCX are the directly relevant additions.
2. **Fraud response and safeguarding are co-finalists**, separated by 0.25 points
   on a model whose inputs are integers on eight subjective dimensions. Both need
   parallel buyer discovery. The scorecard should not pick between them.
3. **Portability is untested and it decides the venture case.** The claimed moat
   is Irish implementation detail; the claimed path to scale is EU expansion. Those
   pull in opposite directions and there is no kill test for it. Two non-Irish PSP
   interviews in days 1 to 20 would settle it.
4. **Kill test 1 should widen** from "is the BPFI database vendor building this"
   to "will an Irish or EU scheme-level claims system be mandated", given what the
   PSR does to reimbursement workflows and what Pay.UK's RCMS shows about how the
   UK answered the same question.
5. **105 documents remain unresolved.** Mostly genuine Bank publications with
   blank cover pages. They can be resolved by reading them, and they must not be
   silently absorbed into Central Bank counts in the meantime.
6. **Housekeeping.** `work/live-index/` holds a stale 423 MB partial index and now
   carries a warning file. `work/pdf-env`, `work/pip-cache` and `work/python-deps`
   are build artifacts. Roughly 450 MB can be deleted.
7. **PyMuPDF is AGPL-3.0.** Fine for private research, not for a hosted product
   without a commercial licence from Artifex.

## 7. Files added or changed

**New**
```
cbi-research/scripts/classify_provenance.py
cbi-research/scripts/test_classify_provenance.py
cbi-research/scripts/convert_office.py
cbi-research/scripts/qa_extraction_quality.py
cbi-research/scripts/export_provenance_qa.py
cbi-research/corpus/office/               323 documents, manifest, journal, summary
cbi-research/index/cbi-corpus-v3-5568docs.sqlite
cbi-research/index/README.md              which database to use
cbi-research/analysis-v3/                 corrected topic scan and evidence candidates
cbi-research/qa/provenance-classification.csv
cbi-research/qa/extraction-quality*.csv, extraction-quality-summary.json
cbi-research/qa/remediation-verification.json
work/live-index/STALE-DO-NOT-USE.md
outputs/REMEDIATION-2026-08-26.md
```

**Changed**
```
cbi-research/scripts/build_search_index.py     new classifier, multi-corpus, new columns
cbi-research/scripts/run_topic_scan.py         authorship breakdown
cbi-research/scripts/analyze_key_datasets.py   three defects fixed
cbi-research/scripts/convert_pdfs.py           legacy .doc, quality metrics
cbi-research/scripts/{audit_pdfs,validate_corpus,profile_*}.py   path portability
outputs/CBI-ARCHIVE-ANALYSIS-METHOD.md         corrected in place
outputs/IRELAND-FINANCIAL-SYSTEM-AND-STARTUP-THESIS.md   corrected in place
```

**Unchanged**
```
cbi-archive/          the crawl and its manifests. No error was found here.
cbi-research/corpus/  the 5,246 PDF conversions. Verified, not rebuilt.
cbi-research/index/cbi-corpus.sqlite   superseded but left in place
```

## 8. Revised phase status

| Phase | Status |
|---|---|
| Crawl, download, manifest | Complete |
| PDF conversion | Complete |
| Office and archive conversion | Complete (was missing entirely) |
| Structured-data processing | Complete |
| Whole-archive searchable corpus | Complete |
| Provenance classification | Corrected and tested |
| Extraction QA | Added |
| Opportunity ranking | Provisional: two co-finalists, two candidates to re-score |
| Final thesis | Corrected v1, not publication-final |
