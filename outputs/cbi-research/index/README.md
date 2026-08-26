# Which index file to use

Three SQLite databases sit in this directory, and a fourth, stale one exists under
`work/live-index/`. They are not interchangeable.

| File | Documents | Pages | Use it? |
|---|---:|---:|---|
| `cbi-corpus-v3-5568docs.sqlite` | 5,568 | 88,782 | **Yes.** Current. Corrected precedence and DOCX extraction; includes the office/archive corpus. |
| `cbi-corpus-v2-5568docs.sqlite` | 5,568 | 88,782 | Superseded. Includes office files, but 55 stakeholder documents are misattributed. |
| `cbi-corpus.sqlite` | 5,246 | 88,106 | Superseded. PDF only, and its provenance classes are wrong (see below). |
| `../../../work/live-index/cbi-corpus.sqlite` | 3,259 | 57,368 | **No.** Partial build from a run that was still converting. |

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

   Stakeholder documents: **1,134 in v1, 1,601 in v2, 1,656 in v3.** 105 documents are now
   labelled `unresolved`, which means the evidence is genuinely ambiguous and the
   document must not be counted as Central Bank material.

2. **323 documents were missing.** The PDF pipeline filtered `format == "PDF"`,
   so 201 DOCX, 71 DOC, 49 ZIP and 2 PPTX files were downloaded but never
   converted or indexed. They are now in `../corpus/office/`.

3. **New columns.** `authorship`, `classification_basis`,
   `classification_confidence`, `page_basis` and `source_format`. Every label is
   auditable: `classification_basis` records the rule that produced it.

4. **Portable database artifact.** v3 checkpoints and removes its build-time WAL,
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
