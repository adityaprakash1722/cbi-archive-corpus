#!/usr/bin/env python3
"""Regression tests for the v5.2 OOXML body-order extractor."""

from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

from convert_office import convert_docx, metrics


W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def fixture(path: Path) -> None:
    document = f"""<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="{W}"><w:body>
  <w:p><w:r><w:t>Before table</w:t></w:r></w:p>
  <w:tbl>
    <w:tr><w:tc><w:tcPr><w:gridSpan w:val="2"/></w:tcPr><w:p><w:r><w:t>Merged heading</w:t></w:r></w:p></w:tc></w:tr>
    <w:tr><w:tc><w:tcPr><w:vMerge w:val="restart"/></w:tcPr><w:p><w:r><w:t>Vertical text</w:t></w:r></w:p></w:tc></w:tr>
    <w:tr><w:tc><w:tcPr><w:vMerge/></w:tcPr><w:p/></w:tc></w:tr>
  </w:tbl>
  <w:p><w:r><w:t>After table</w:t><w:br w:type="page"/><w:t>Second page</w:t></w:r></w:p>
</w:body></w:document>"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="cbi-docx-test-") as directory:
        path = Path(directory) / "ordered.docx"
        fixture(path)
        pages, engine, basis, diagnostics = convert_docx(path)
    assert engine == "ooxml-body-order 1.0"
    assert basis == "explicit-page-break"
    assert len(pages) == 2
    assert pages[0].index("Before table") < pages[0].index("Merged heading")
    assert pages[0].index("Merged heading") < pages[0].index("After table")
    assert "Second page" in pages[1]
    assert "Merged heading" not in pages[1]
    assert "| Merged heading |  |" in pages[0]
    assert pages[0].count("Merged heading") == 1
    assert pages[0].count("Vertical text") == 1
    assert diagnostics["output_expansion_ratio"] < 5
    result = metrics(pages)
    assert result["max_page_characters"] == max(map(len, pages))
    form_layout = metrics(["\n".join(["|  |  |  |"] * 100 + ["____________________"] * 100)])
    assert form_layout["repeated_line_share"] == 0
    duplicated_prose = metrics(["This is a deliberately repeated substantive sentence.\n" * 8])
    assert duplicated_prose["repeated_line_share"] > 0.5
    print("PASS 14 Office extraction assertions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
