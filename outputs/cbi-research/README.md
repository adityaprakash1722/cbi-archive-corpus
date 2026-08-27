# Central Bank of Ireland Research Corpus

This project normalizes the downloaded Central Bank of Ireland public archive into a research corpus with page-level provenance. It is designed for evidence-led financial-system analysis, not lossy bulk summarization.

## Corpus audit

The content-level audit found:

- 5,874 downloaded PDF URLs.
- 5,246 logical PDF documents after SHA-256 deduplication and malformed-alias reconciliation.
- 88,106 source pages/pseudo-pages and 4.22 GB of unique PDF content.
- 4,701 PDFs converted from native text.
- 541 PDFs converted with targeted OCR.
- 4 Office files served with a `.pdf` name; all four were recovered.
- 627 byte-identical duplicate URL records across 491 content groups, plus one malformed HTML alias.

Every duplicate URL remains attached to the canonical content record as an alias. This prevents repeated documents from biasing topic frequencies and trend analysis.

## Extraction decision

Microsoft MarkItDown 0.1.7 and PyMuPDF4LLM 1.28.2 were tested on the same pilot documents. MarkItDown was faster, but flattened nearly all headings, reconstructed no tables in the sample, and did not reliably preserve PDF page boundaries. PyMuPDF4LLM preserved page chunks and recovered substantially more document structure, so it is the production PDF engine.

RapidOCR is invoked only for PDFs whose sampled pages contain no meaningful native text. Native text is never replaced with OCR when it is usable.

Each Markdown document contains:

- A content-derived document ID.
- The source SHA-256 and byte count.
- Every known source URL alias.
- Converter and pipeline versions.
- OCR and quality flags.
- An explicit anchor and comment for every source page.

## Output layout

```text
cbi-research/
  audit/
    pdf-audit.csv
    pdf-audit.jsonl
    pdf-audit-summary.json
  corpus/
    markdown/<sha-prefix>/<sha256>.md
    conversion-journal.jsonl
    conversion-manifest.csv
    conversion-summary.json
    office/
      markdown/<sha-prefix>/<sha256>.md
      conversion-journal.jsonl
      conversion-manifest.csv
      conversion-summary.json
  pilot/
    ...benchmark outputs...
  scripts/
    audit_pdfs.py
    convert_pdfs.py
    validate_corpus.py
    build_search_index.py
    search_corpus.py
    run_topic_scan.py
    export_evidence_candidates.py
    profile_structured_data.py
    profile_workbooks.py
    profile_xml.py
    analyze_key_datasets.py
    classify_provenance.py
    test_classify_provenance.py
    convert_office.py
    qa_extraction_quality.py
    export_provenance_qa.py
  structured/
    structured-file-catalog.csv
    all-csv-profile.csv
    workbooks/
    xml/
    analysis/
```

The journal files make both stages resumable. Markdown output is sharded by hash to avoid very large directories and Windows path collisions.

## Reproduce

Create an isolated Python environment and install the pinned dependencies:

```powershell
python -m venv .\work\pdf-env
.\work\pdf-env\Scripts\python.exe -m pip install -r .\outputs\cbi-research\requirements.txt
```

Install LibreOffice and ensure `soffice` is on `PATH` before converting legacy
`.doc` files or using DOCX package fallback.

Audit unique PDFs:

```powershell
python .\outputs\cbi-research\scripts\audit_pdfs.py `
  --archive .\outputs\cbi-archive\cbi-data `
  --output .\outputs\cbi-research\audit
```

Convert native-text documents:

```powershell
python .\outputs\cbi-research\scripts\convert_pdfs.py `
  --archive .\outputs\cbi-archive\cbi-data `
  --output .\outputs\cbi-research\corpus `
  --audit-csv .\outputs\cbi-research\audit\pdf-audit.csv `
  --exclude-likely-ocr --workers 3
```

Convert scan candidates with OCR:

```powershell
python .\outputs\cbi-research\scripts\convert_pdfs.py `
  --archive .\outputs\cbi-archive\cbi-data `
  --output .\outputs\cbi-research\corpus `
  --audit-csv .\outputs\cbi-research\audit\pdf-audit.csv `
  --only-likely-ocr --ocr --workers 3
```

Convert the office/archive corpus:

```powershell
python .\outputs\cbi-research\scripts\convert_office.py `
  --archive .\outputs\cbi-archive\cbi-data `
  --output .\outputs\cbi-research\corpus\office
```

Validate every normalized artifact against its source and the logical audit:

```powershell
python .\outputs\cbi-research\scripts\validate_corpus.py `
  --archive .\outputs\cbi-archive\cbi-data `
  --corpus .\outputs\cbi-research\corpus `
  --audit-csv .\outputs\cbi-research\audit\pdf-audit.csv `
  --output .\outputs\cbi-research\qa
```

Build the page-level search index and first-pass evidence exports:

```powershell
python .\outputs\cbi-research\scripts\build_search_index.py `
  --corpus .\outputs\cbi-research\corpus `
  --corpus .\outputs\cbi-research\corpus\office `
  --output .\outputs\cbi-research\index `
  --audit-csv .\outputs\cbi-research\audit\pdf-audit.csv `
  --database-name cbi-corpus-v4-5568docs.sqlite

python .\outputs\cbi-research\scripts\run_topic_scan.py `
  --database .\outputs\cbi-research\index\cbi-corpus-v4-5568docs.sqlite `
  --queries .\outputs\cbi-research\topic_queries.json `
  --output .\outputs\cbi-research\analysis-v4

python .\outputs\cbi-research\scripts\export_evidence_candidates.py `
  --database .\outputs\cbi-research\index\cbi-corpus-v4-5568docs.sqlite `
  --queries .\outputs\cbi-research\topic_queries.json `
  --output .\outputs\cbi-research\analysis-v4

python .\outputs\cbi-research\scripts\export_provenance_qa.py `
  --database .\outputs\cbi-research\index\cbi-corpus-v4-5568docs.sqlite `
  --previous-database .\outputs\cbi-research\index\cbi-corpus.sqlite `
  --output .\outputs\cbi-research\qa
```

The index gives stakeholder consultation submissions their own provenance class.
They can reveal industry pain or objections, but they are not counted as Central
Bank findings merely because they are hosted on the Central Bank website.

Run extraction-density QA over both manifests (the script deduplicates by SHA-256):

```powershell
python .\outputs\cbi-research\scripts\qa_extraction_quality.py `
  --manifest .\outputs\cbi-research\corpus\conversion-manifest.csv `
  --manifest .\outputs\cbi-research\corpus\office\conversion-manifest.csv `
  --output .\outputs\cbi-research\qa
```

Profile and analyse the structured corpus:

```powershell
python .\outputs\cbi-research\scripts\profile_structured_data.py `
  --archive .\outputs\cbi-archive\cbi-data `
  --output .\outputs\cbi-research\structured

python .\outputs\cbi-research\scripts\profile_workbooks.py `
  --archive .\outputs\cbi-archive\cbi-data `
  --output .\outputs\cbi-research\structured\workbooks

python .\outputs\cbi-research\scripts\profile_xml.py `
  --archive .\outputs\cbi-archive\cbi-data `
  --output .\outputs\cbi-research\structured\xml

python .\outputs\cbi-research\scripts\analyze_key_datasets.py `
  --archive .\outputs\cbi-archive\cbi-data `
  --profile-dir .\outputs\cbi-research\structured `
  --output .\outputs\cbi-research\structured\analysis
```

The structured profile covers all 246 CSVs, 489 workbooks and five XML files. The key
analysis preserves suppressed values, records release/CSV discrepancies and does not
impute missing observations.

## Known limitations

- Markdown cannot faithfully represent every chart, map, diagram, complex form, or merged-cell table.
- OCR is searchable evidence, not a guaranteed transcription; important claims must be checked against the rendered source page.
- Four mislabeled Office files use file-signature recovery; the malformed HTML response is reconciled to its valid archived document.
- Spreadsheet and CSV sources should be analysed directly rather than inferred from charts embedded in PDFs.
- Successful parsing does not guarantee semantic validity; the mortgage-arrears CSV
  contains incomplete Q1 2026 PDH headline rows, and payment-fraud cells are suppressed
  in ways that prevent safe reconstruction of the published total.
- PyMuPDF is available under AGPL and commercial licensing terms. Review licensing before embedding this pipeline in a proprietary hosted product.
