# Central Bank of Ireland Archive: Analysis Method and Reproducibility Note

> **Revision, 26 August 2026.** This note was corrected after an independent
> audit found three errors: the stakeholder-submission safeguard did not work,
> 323 downloaded documents were never analysed, and "zero conversion errors"
> described exception counts rather than extraction fidelity. Figures below are
> the corrected ones. `REMEDIATION-2026-08-26.md` records what changed and why.
>
> **Revision, 29 August 2026.** v5 adds page-level voice for a mixed composite,
> validated temporal fields, explicit duplicate-extraction selection and the
> targeted CP76 OCR repair. Counts below describe v5 unless marked historical.

## Purpose

This note documents how the downloaded Central Bank of Ireland archive was turned into
a defensible research corpus. The goal was evidence-led system and startup analysis,
not bulk summarisation.

## Archive coverage

- Crawl snapshot: 25 August 2026.
- Sitemap URLs discovered: 11,371.
- Open-data catalogue datasets: 39, with 71 resources.
- Download records: 6,984; 6,963 downloaded and 21 official failures/404 responses.
- Downloaded size: 7.476 GB (6.96 GiB).
- Logical structured files: 246 CSV, 447 XLSX, 42 XLS and five XML.
- Logical PDF documents: 5,246 after SHA-256 deduplication and alias reconciliation.
- Logical office and archive documents: 201 DOCX, 71 DOC, 49 ZIP and two PPTX,
  323 in total, 387 MB. These were downloaded but not analysed in the first pass
  because the conversion pipeline filtered on `format == "PDF"`. They are now
  converted and indexed.
- Total analysed documents: 5,568 after removing one file served under both a
  `.pdf` and a `.docx` URL with identical bytes.
- Five duplicate aliases were quarantined; aliases remain represented in provenance.
- Format labels derived from URL extensions are wrong in both directions. Four
  Office files are served as `.pdf`, and two PDFs are served as `.docx`. The
  converters now dispatch on magic bytes rather than on the extension.

The 21 failed URLs are recorded rather than presented as downloaded content. “Everything”
means everything recoverable from the crawl snapshot, not a claim that no unpublished,
unlinked, blocked or subsequently published resource exists. Until this revision it
also did not mean everything downloaded: the 323 office and archive files above were
absent from the corpus, the index and every topic count.

## PDF pipeline

Microsoft MarkItDown and PyMuPDF4LLM were benchmarked on the same sample. MarkItDown was
faster but flattened headings/tables and did not reliably preserve page boundaries.
PyMuPDF4LLM was selected for native PDF extraction because page-level provenance was a
hard requirement. RapidOCR was used only for scan candidates or specifically identified
sparse-native files. MarkItDown recovered four Office documents served as `.pdf`.

Final conversion:

- 5,246 source hashes and 5,246 Markdown files.
- 88,106 pages/pseudo-pages.
- 4,701 native PyMuPDF4LLM conversions.
- 541 OCR conversions.
- Four mislabelled Office recoveries.
- 5,237 normal successes and nine explainable low-text results.
- Zero conversion errors, meaning no conversion raised an exception. It does not
  mean every page extracted cleanly; see Extraction quality below.

The office and archive pipeline (`scripts/convert_office.py`) adds:

- 323 source hashes and 323 Markdown files, 678 pages, zero errors.
- DOCX through python-docx. Three packages with unusual relationship targets use
  LibreOffice; two PDFs served as DOCX dispatch to the PDF converter; and two
  irregular merged-cell tables use a raw-XML fallback so table text is not lost.
- DOC through LibreOffice headless. This replaces an earlier routine that kept
  only the single longest printable run from the binary stream and discarded the
  rest of the document.
- PPTX at one page per slide.
- ZIP as an inventory: member listing, suffix profile and target namespaces, plus
  full text of documentation members only. Most of these archives are XBRL
  taxonomy packages. Transcribing their schema bodies produced 705 MB of Markdown
  and 100,216 pseudo-pages, which would have swamped every topic count with
  machine schema, so schema is profiled rather than transcribed.
- Every office document records `page_basis`. Only `source-page` and `slide` are
  real locations. `single-pseudo-page` means "this document", not "this page",
  and must not be cited as a page reference.

Every Markdown document records its content-derived ID, source hash, byte count, URL
aliases, converter, OCR flags and explicit source-page anchors.

## Validation

The final validator independently checked:

- every source SHA-256;
- every generated Markdown SHA-256;
- one output per logical source hash;
- sequential page markers and expected page counts;
- orphan outputs and missing outputs; and
- documented exception status.

Result: **pass, zero failures, zero warnings and zero orphans**. Nine low-text files are
two heavily redacted prohibition notices and seven video-tutorial placeholders. One
server-error HTML alias previously saved with a PDF suffix was verified as malformed
and excluded; its valid document alias remains in the corpus.

### Extraction quality

Structural validation cannot see a document whose pages are perfectly formed and
substantively blank, because nothing it checks looks at how much text a page
holds. `scripts/qa_extraction_quality.py` adds that missing test and grades all
5,568 unique converted documents after SHA-256 deduplication across manifests:

| Grade | Documents | Meaning |
|---|---:|---|
| ok | <!-- fact:quality.grade.ok -->5,487<!-- /fact --> | nothing anomalous |
| gappy | <!-- fact:quality.grade.gappy -->30<!-- /fact --> | at least 30% of pages hold almost no text |
| garbled | <!-- fact:quality.grade.garbled -->25<!-- /fact --> | 200 or more replacement characters, or one per 500 characters |
| thin | <!-- fact:quality.grade.thin -->19<!-- /fact --> | under 200 non-space characters per page |
| empty | <!-- fact:quality.grade.empty -->7<!-- /fact --> | no usable extractable text |

Median density is <!-- fact:quality.median_nonspace_per_page -->1,624<!-- /fact -->
non-space characters per page and
<!-- fact:quality.empty_page_share_percent -->0.61<!-- /fact -->% of all pages are
effectively empty, down from 2.44% before the recovery pass. 142 documents
contain Unicode replacement characters, the worst
carrying 11,371. Chart-heavy statistical releases extract with visible damage: the
Q1 2026 arrears release renders "March" as "~~M~~ arch" in places. Every figure
quoted from that release was rechecked against the page and is correct, but the
prose around it is unreliable. The 81 flagged documents are listed in
`qa/extraction-quality-flagged.csv`.

## Search and provenance model

The 673 MB SQLite index (`index/cbi-corpus-v5-5568docs.sqlite`) contains 5,568
documents and 88,783 pages.

**The original provenance model did not work, and this is the most serious error
the audit found.** A consultation-hosted document was classed as a stakeholder
submission if and only if its filename contained the substring `response`. That
missed three families:

1. `cp45-submission-from-aib.pdf` and 288 others saying "submission";
2. `cp51-feedback-from-generali-paneurope.pdf` and 122 others saying
   "feedback-from", which were filed as Central Bank *feedback statements*;
3. documents published under the responder's bare name, such as `blackrock.pdf`,
   which carry no cue at all.

Family 3 cannot be resolved from a filename, so classification is now two-pass.
`scripts/classify_provenance.py` reads attribution cues and Central Bank
document-type cues from the filename, and where those are silent it reads the
opening pages of the document. Issuer-specific Central Bank cues win first;
explicit stakeholder attribution then wins over generic words such as
`discussion-paper`, `consultation-on` and `rulebook`. This keeps
`note-from-the-financial-regulator-in-relation-to-submissions-received-on-cp43`
correctly classed as Bank material without misclassifying stakeholder responses
that name the document they answer. Two manually audited stakeholder submissions
outside the consultation archive are exact exceptions rather than a general
filename guess. <!-- fact:classifier.assertions -->104<!-- /fact --> regression assertions, including all 55
conflict filenames found in the follow-up audit, in
`scripts/test_classify_provenance.py` cover all of the above.

Corrected counts:

| | Original | Corrected |
|---|---:|---:|
| Central Bank documents | 4,112 | <!-- fact:authorship.central-bank -->3,807<!-- /fact --> |
| Stakeholder submissions | 1,134 | <!-- fact:authorship.stakeholder -->1,671<!-- /fact --> |
| Mixed composite | 0 | <!-- fact:authorship.mixed -->1<!-- /fact --> |
| Unresolved | 0 | <!-- fact:authorship.unresolved -->89<!-- /fact --> |

`unresolved` is a real answer. Those 89 documents are genuinely ambiguous and must
not be counted as Central Bank material, which is precisely the default that caused
the original error. Every document now stores the rule that classified it
(`classification_basis`) and a confidence (high 5,342, medium 137, low 89). The
full before-and-after trail is in `qa/provenance-classification.csv`.

One 114-page strategic-plan engagement compilation contains five pages of Bank
framing followed by stakeholder/public submissions. It is labelled `mixed`, and
the `pages` table records the actual voice on each page. A deterministic
<!-- fact:audit.documents -->32<!-- /fact -->-document human-reviewed sample, stratified over the previous labels and
including this composite, is stored in `qa/authorship-gold.csv`; its perfect
<!-- fact:audit.correct -->32<!-- /fact -->/32 result is a small error-detection exercise, not a population accuracy claim.

v5 also separates raw time metadata from analysis time. `pdf_creation_date` is
preserved even when implausible; 27 documents contain a 2031 timestamp.
`analysis_year` rejects anything after the 2026 crawl snapshot, while
`published_at` is populated only from explicit publication evidence (72
documents). All 5,568 rows retain `retrieved_at` and `source_page_url`.

The first-pass topic scan is a discovery layer only. Examples:

| Topic | Matching documents | Matching pages | Stakeholder submissions | Previously reported |
|---|---:|---:|---:|---:|
| Payments | 1,669 | 6,390 | 326 | 219 |
| Complaints/redress | 1,118 | 3,197 | 279 | 136 |
| Fraud/scams | 510 | 1,135 | 137 | 95 |
| Consumer harm | 610 | 1,849 | 254 | 166 |
| Data quality | 116 | 204 | 8 | 4 |

The stakeholder column was understated by 40% to 101% in these examples.
Document totals also rise slightly because the office corpus is now included.

Counts were used to find sources, not rank social importance. Consultation bursts,
document length, repeated annual reporting and broad search terms all bias raw frequency.

## Structured-data pipeline

All 740 logical structured files were classified and profiled. CSVs were streamed so
that three datasets over 1.2 GB could be processed without loading them wholly into
memory. Workbooks were read without mutation and profiled at workbook/sheet level. Two
`.xls` URLs were XLSX containers; three protected legacy workbooks were read through
the known Microsoft read-only default password. All five XML files parsed successfully.

Key analyses operate directly on CSV observations with explicit filters and no imputation:

- payment-fraud reconciliation;
- mortgage-arrears CSV/release quality comparison;
- SME lending by sector;
- new mortgage lending and borrower characteristics; and
- retail deposit/loan rate snapshots.

Suppressed values remain null. Stocks, flows, percentages, loss measures and populations
are not combined without a stated transformation. A PDF release can override an incomplete
CSV headline only when the discrepancy is recorded, not silently repaired.

## Evidence rules

Every decision-relevant claim was evaluated against:

- source URL and content SHA-256;
- source page or structured observation;
- document class and institutional context;
- publication/effective date;
- definition, unit, population and timing; and
- whether it is a current rule, finding, proposal, stakeholder view, association or
  hypothesis.

Startup candidates required a strong official signal plus an identifiable buyer, narrow
MVP, lawful first deployment, competitor boundary and a cheap falsification test. Public-
policy importance alone did not qualify an opportunity.

## Reproducible outputs

The scripts and machine-readable results are in the `cbi-research` output directory:

- `scripts/audit_pdfs.py`
- `scripts/convert_pdfs.py`
- `scripts/validate_corpus.py`
- `scripts/build_search_index.py`
- `scripts/search_corpus.py`
- `scripts/run_topic_scan.py`
- `scripts/export_evidence_candidates.py`
- `scripts/profile_structured_data.py`
- `scripts/profile_workbooks.py`
- `scripts/profile_xml.py`
- `scripts/analyze_key_datasets.py`
- `scripts/classify_provenance.py` and `scripts/test_classify_provenance.py`
- `scripts/convert_office.py`
- `scripts/qa_extraction_quality.py`
- `scripts/export_provenance_qa.py`

Key result directories are `qa`, `index`, `analysis-v5`, and `structured`.

All scripts now run on Linux as well as Windows. Manifest paths are written with
Windows separators, and seven scripts joined them to a root without normalising, so
the pipeline was silently Windows-only. Re-running the full structured-data analysis
on Linux after that fix reproduces every published figure exactly; the only
differences in `key-dataset-analysis.json` are the absolute source paths.

## Limitations

- The crawl is a dated snapshot and cannot include inaccessible or later-published files.
- 89 consultation-hosted documents could not be attributed to the Bank or to a
  respondent and are labelled `unresolved`. Any count that needs a clean Central Bank
  denominator should exclude them rather than absorb them.
- Office and archive documents mostly have no page structure. 179 of 323 are a single
  pseudo-page, so they are searchable but not page-citable.
- ZIP taxonomy packages are inventoried and profiled, not transcribed. A claim that
  depends on the contents of a specific schema file needs that file opened.
- 81 documents are graded below `ok` for extraction fidelity, down from 112  <!-- historical -->
  after the v4 recovery pass recovered 441,610 characters the converter had
  dropped from pages carrying a full-page background image. Material claims from
  any of them require source-page review.
- Markdown does not preserve every visual chart, map, formula or complex merged-cell layout.
- OCR is searchable evidence, not guaranteed transcription; material claims require
  source-page review.
- Publication counts do not measure importance or incidence.
- Provider-level economics, workflow times, incident volumes and vendor contracts are
  not in the public archive and require primary research.
- Current legal and regulatory statements need rechecking at implementation because
  the Irish fraud database and EU PSR/PSD3 package are still moving.
- PyMuPDF licensing must be reviewed before embedding the pipeline in a proprietary
  hosted product.
