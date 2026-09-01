# Corpus v5.1 errata

Status: superseded by v5.2. Published 31 August 2026 after independent review.

Do not use v5.1 `authorship = 'central-bank'` as a regulator-only filter.
The underlying source bytes, content hashes, URLs, and page-to-source joins remain
valid. The defects are in the semantic labels, two DOCX text extractions, and
several release claims described below.

## Speaker labels

v5.1 described `central-bank` as "the regulator speaking". At least 19 rows did
not meet that definition:

- 15 responses to Discussion Paper 5, covering 104 pages, were stakeholder
  submissions from AA, AEMA, Allianz, Aviva, BPFI, Brokers Ireland, Harvest,
  Insurance Ireland, Irish Life, Lloyd's, Mortgage Insight, the Pensions
  Council, Trustee Decisions, Vanguard, and Zurich.
- one Maples response to CP77, covering two pages, was stakeholder advocacy.
- three IMF reports, covering 266 pages, were external-authority assessments.

The 19 corrections are SHA-keyed in
`outputs/cbi-research/qa/authorship-overrides.csv`. They cover 372 pages in
total. This is a demonstrated lower bound on v5.1 error, not a population error
rate.

The root cause was ontological. v5.1 used one field for several different facts:
the hosting website, apparent author, document role, and institutional voice.
Of its 3,844 `central-bank` rows, 3,489 came from the non-consultation directory
default alone, 311 from filename rules, seven from content scoring, and 37 from
manual review.

v5.2 separates:

- `host`
- `author_org`
- `document_role`
- `institutional_voice`
- `voice_review_status`
- `voice_evidence`

Files known only to be hosted on centralbank.ie are `institutional_voice =
'unknown'`. They are not silently promoted to CBI speech. The v5.1-compatible
result is retained as `legacy_authorship` for migration only.

## DOCX extraction

Two v5.1 DOCX rows, SHA-256 `3e18fdce...e6a9` and `96dbc5c7...9b48`, each
contained the same 3,071,759-character page despite their source OOXML carrying
about 75,000 visible characters. Together they contributed 6,143,518 characters,
or 3.217% of the v5.1 text.

The v5.1 extractor enumerated paragraphs and tables separately. That reordered
interleaved content and repeated merged table cells. v5.2 walks OOXML body
elements in document order, reads merged cells once, preserves relevant
ancillary parts, and adds expansion, maximum-page-length, repeated-line, and
exact-page-duplication QA. The corrected extracts contain 155,854 and 155,092
characters, both about 2.0 times the source-visible OOXML text rather than about
40 times.

## Other corrected claims

- The raw Hugging Face repository had no explicit data configuration. Its
  viewer recursively interpreted ZIP members as PDFs and exposed 107,860
  pseudo-rows. v5.2 configures the viewer to display `blob-catalog.csv`.
- Only 5,296 of 6,309 raw files expose SHA-256 through Hub LFS metadata. The
  other 1,013 are ordinary Git blobs. v5.2's verifier checks every path and
  size, plus every available LFS content hash.
- `build_blob_tree.py` used to exit successfully after missing sources and
  trusted existing destinations. v5.2 fails on missing, wrong-size, or
  wrong-hash blobs.
- Thirty-three titles containing one space bypassed fallback logic. v5.2 strips
  title inputs and has no blank title.
- One CP54 submission inherited the impossible year 1980 from malformed PDF
  creation metadata. v5.2 rejects pre-1990 PDF proxy years. Publication time is
  still sparse: only 72 rows have explicit publication dates, so the remaining
  proxy years must not be used as a dependable publication-volume series.
- One two-URL source reported `source_alias_count = 1`. v5.2 unions manifest
  aliases by source hash and reports two.
- A rights note described all 18 individually reviewed candidates as private
  submissions. Nine are private individuals and nine are public-role writers;
  twelve of the 18 are stakeholder rows.
- The Office conversion manifest covers DOC, DOCX, PPTX, and ZIP, not Excel.
- v5.1's fresh rebuild compared six of thirteen published page fields. v5.2
  compares every published page column against the rebuilt joined row.

## Safe use of v5.1

v5.1 remains suitable for locating text, resolving a result to its preserved
source hash, and checking the original document. It is not suitable for an
unverified "what the Central Bank says" query, regulator-only model training,
or extraction-sensitive analysis of the two affected DOCX files.

Use v5.2 and filter on `institutional_voice` plus `voice_review_status`. For any
material claim, keep the source hash, page or structural anchor, original URL,
and raw-file link.
