#!/usr/bin/env python3
"""Re-extract the three DOCX files that exposed v5.1 semantic corruption.

Unlike the fresh-rebuild test, this starts from pinned original source bytes.
It is intentionally small enough for CI while still guarding the real merged-
cell expansion and body-order defects found by the independent review.
"""
from __future__ import annotations

import hashlib
import tempfile
import urllib.request
from pathlib import Path

from convert_office import convert_docx, metrics
from release_lock import load as load_release


CASES = {
    "1d448305c620622abe4b95336ad2fd2656182645bc1bf06c86c4783587c059df": {
        "pages": 4, "maximum_characters": 10_000,
    },
    "96dbc5c7251acd9920a19c502500603dbcb557be9359e590214e4acf78039b48": {
        "pages": 6, "maximum_characters": 200_000,
    },
    "3e18fdce72542fb575172df7fd41d9a02995302795917c958d87ae417a93e6a9": {
        "pages": 8, "maximum_characters": 200_000,
    },
}


def main() -> int:
    release = load_release()
    repo = release["hugging_face"]["raw_repo"]
    revision = release["hugging_face"]["raw_revision"]
    assertions = 0
    with tempfile.TemporaryDirectory(prefix="cbi-raw-docx-") as directory:
        root = Path(directory)
        for sha, expected in CASES.items():
            path = root / (sha + ".docx")
            url = (f"https://huggingface.co/datasets/{repo}/resolve/{revision}/"
                   f"{sha[:2]}/{sha[2:4]}/{sha}.docx")
            request = urllib.request.Request(url, headers={"User-Agent": "cbi-raw-fixture/1"})
            with urllib.request.urlopen(request) as response:
                payload = response.read()
            assert hashlib.sha256(payload).hexdigest() == sha
            assertions += 1
            path.write_bytes(payload)
            pages, engine, basis, diagnostics = convert_docx(path)
            result = metrics(pages)
            assert engine == "ooxml-body-order 1.0"
            assert basis == "explicit-page-break"
            assert len(pages) == expected["pages"]
            assert result["characters"] < expected["maximum_characters"]
            assert diagnostics["output_expansion_ratio"] < 5
            assertions += 5
    print(f"PASS {assertions} assertions against 3 pinned raw DOCX sources")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
