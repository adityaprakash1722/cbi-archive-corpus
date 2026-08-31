# Which index file to use

Six SQLite databases sit in this directory, and a seventh, stale one exists under
`work/live-index/`. They are not interchangeable.

| File | Documents | Pages | Use it? |
|---|---:|---:|---|
| `cbi-corpus-v5.1-5568docs.sqlite` | 5,568 | 88,783 | **Yes.** Current. Adjudicated authorship, canonical CP/DP keys, final-text quality metrics and exact-text clusters. |
| `cbi-corpus-v5-5568docs.sqlite` | 5,568 | 88,783 | Superseded. 89 unresolved documents, unnormalised identifiers and quality counts that did not describe the final page text. | <!-- historical -->
| `cbi-corpus-v4-5568docs.sqlite` | 5,568 | 88,782 | Superseded. Adds 441,610 characters of page text the converter had dropped. |
| `cbi-corpus-v3-5568docs.sqlite` | 5,568 | 88,782 | Superseded. Correct provenance, but 1,425 pages are blank that should not be. |
| `cbi-corpus-v2-5568docs.sqlite` | 5,568 | 88,782 | Superseded. Includes office files, but 55 stakeholder documents are misattributed. |
| `cbi-corpus.sqlite` | 5,246 | 88,106 | Superseded. PDF only, and its provenance classes are wrong (see below). |
| `../../../work/live-index/cbi-corpus.sqlite` | 3,259 | 57,368 | **No.** Partial build from a run that was still converting. |

## What changed in v5.1

1. **Every formerly unresolved document was opened and adjudicated.** The 89 <!-- historical -->
   decisions are keyed by source SHA-256 in `qa/authorship-overrides.csv`: 37
   Central Bank, 51 stakeholder, and one mixed public-response compilation.
   Page ranges are explicit for both mixed documents.
2. **Consultation identifiers are canonical.** `cp071` and `cp-156` are now
   `cp71` and `cp156`. `engagement_id` extends the join key to 11 discussion
   paper series (`dpN`) without pretending they are consultation papers.
3. **Quality describes the released text.** The conversion manifests,
   Markdown frontmatter, SQLite and QA report now derive near-blank pages from
   the final page bodies. The reconciled grades are 5,481 `ok`, 36 `gappy`, 25
   `garbled`, 19 `thin` and 7 `empty`.
4. **Exact-text duplicates are explicit.** `content_sha256`,
   `content_cluster_id` and `content_cluster_size` preserve every source record
   while allowing analyses to count repeated content once.
5. **Release bytes are portable.** Generated CSVs use UTF-8 without a BOM and
   LF endings; release-lock checks hash the actual artifacts rather than only
   validating the shape of the hash strings.

v5.1 SHA-256:
`aa779f4bba4ec5b783d3cedeebaa20fbba638bc5e6fcb4f716872affb086fed8`.

## What changed in v5

1. **Mixed authorship is modelled at page level.** One 114-page engagement
   compilation has Central Bank framing on pages 1–5 and stakeholder/public
   submissions on pages 6–114. The container is `mixed`; every page carries its
   actual voice and the audit basis.
2. **Time-series fields are safe to use.** Raw `pdf_creation_date` remains
   available, but `analysis_year` excludes future timestamps and
   `published_at` requires explicit source/referrer evidence.
3. **Duplicate extraction selection is explicit.** SHA `6d106f8c…` now selects
   the canonical two-page DOCX extraction instead of silently taking the
   inferior one-page PDF-pipeline alias. The extra page explains the row-count
   increase.
4. **The CP76 encoding failure is OCR-recovered.** Five pages that were 94%
   replacement characters now hold 11,206 readable characters.
5. **Provenance was 3,807 Central Bank / 1,671 stakeholder / 89 unresolved / one <!-- historical -->
   mixed document.** 104 classifier regressions and a small 32-document human <!-- historical -->
   audit sample cover the known failure modes.

v5 SHA-256 (superseded):
`3dbd6a91e33969475e07d02cb106259e9041dab86b0041524cffee36e66f2d34`.

## What changed in v4

1. **441,610 characters of page text were recovered.** `pymupdf4llm` returns an
   empty string for any page carrying a full-page background image, even where a
   readable text layer sits underneath. 1,167 pages were re-extracted directly
   and 258 image-only pages by OCR. Empty pages fell from 1,723 to 298 and
   documents graded below `ok` from 112 to 82.  <!-- historical -->

2. **One classifier correction.** The Bank's own *Central Credit Register
   Feedback Response to CP93* was labelled `stakeholder` because it contains
   "response to cp". Four decision-maker phrases now outrank that cue: only the
   body making the decision counts the submissions it received, thanks the
   parties who made them, and sets out next steps.

   Authorship was **3,809 / 1,656 / 103**. Two documents moved from `unresolved`  <!-- historical -->
   to `central-bank` once their opening pages had text to classify.

## What changed in v3

1. **Provenance was wrong in v1.** The original classifier treated a
   consultation-hosted document as a stakeholder submission only if its filename
   contained the substring `response`. Files named `cp45-submission-from-aib.pdf`
   and `cp51-feedback-from-generali-paneurope.pdf`, and files published under the
   responder's bare name such as `blackrock.pdf`, were all filed as Central Bank
   material. The classifier reads filename
   attribution cues, Central Bank document-type cues, and, where the filename says
   nothing, the opening pages of the document itself.

   v2 still let generic terms such as `discussion-paper`, `consultation-on` and
   `rulebook` outrank explicit response/submission attribution. v3 reverses that
   precedence while retaining narrow issuer-specific exceptions.

   Stakeholder documents: **1,134 in v1, 1,601 in v2, 1,656 in v3 and v4.** 103  <!-- historical -->
   documents were labelled `unresolved`, which means the evidence was genuinely
   ambiguous and the document must not be counted as Central Bank material.

2. **323 documents were missing.** The PDF pipeline filtered `format == "PDF"`,
   so 201 DOCX, 71 DOC, 49 ZIP and 2 PPTX files were downloaded but never
   converted or indexed. They are now in `../corpus/office/`.

3. **New columns.** `authorship`, `classification_basis`,
   `classification_confidence`, `page_basis` and `source_format`. Every label is
   auditable: `classification_basis` records the rule that produced it.

4. **Portable database artifact.** v3 and v4 checkpoint and remove their build-time WAL,
   so the named `.sqlite` file is self-contained. The unversioned legacy database
   still has sidecars and should not be copied or queried as the current index.

## Querying by authorship

```sql
SELECT COUNT(*) FROM documents WHERE authorship = 'stakeholder';
SELECT document_class, COUNT(*) FROM documents
 WHERE authorship = 'central-bank' GROUP BY document_class;
```

Never treat `authorship = 'unresolved'` as Central Bank material. That default is
exactly what produced the v1 error.

## A caution about page anchors

PDF documents carry true source-page anchors. Documents from the office corpus
record `page_basis`, which may be `single-pseudo-page` (the format has no pages,
so the whole document is "page 1"), `slide`, `explicit-page-break` or
`archive-member`. Only `source-page` and `slide` are safe to cite as locations.
