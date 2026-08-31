#!/usr/bin/env python3
"""Build the compressed, auditable manifest layer for Hugging Face.

The input CSV bytes are preserved exactly inside deterministic Zstandard frames.
Generated CSVs are UTF-8 without a BOM and use LF line endings; upstream source
files are never rewritten because their original bytes are part of the archive.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "files.csv.zst": ROOT / "outputs/cbi-archive/cbi-data/manifests/files.csv",
    "conversion-manifest.csv.zst":
        ROOT / "outputs/cbi-research/corpus/conversion-manifest.csv",
    "conversion-manifest-office.csv.zst":
        ROOT / "outputs/cbi-research/corpus/office/conversion-manifest.csv",
    "provenance-classification.csv.zst":
        ROOT / "outputs/cbi-research/qa/provenance-classification.csv",
    "extraction-quality.csv.zst":
        ROOT / "outputs/cbi-research/qa/extraction-quality.csv",
    "authorship-overrides.csv.zst":
        ROOT / "outputs/cbi-research/qa/authorship-overrides.csv",
    "page-authorship-overrides.csv.zst":
        ROOT / "outputs/cbi-research/qa/page-authorship-overrides.csv",
    "conversion-exclusions.csv.zst":
        ROOT / "outputs/cbi-research/qa/conversion-exclusions.csv",
    "engagement-coverage.csv.zst":
        ROOT / "outputs/cbi-research/qa/engagement-coverage.csv",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "publish/hf/manifests")
    args = parser.parse_args()
    try:
        import pyarrow as pa
    except ImportError:
        parser.error("pyarrow is required: pip install pyarrow")

    args.output.mkdir(parents=True, exist_ok=True)
    result = {}
    for name, source in SOURCES.items():
        payload = source.read_bytes()
        target = args.output / name
        compressed = bytes(pa.compress(payload, codec="zstd", asbytes=True))
        target.write_bytes(compressed)
        result[name] = {
            "source": source.relative_to(ROOT).as_posix(),
            "source_bytes": len(payload),
            "compressed_bytes": len(compressed),
            "sha256": hashlib.sha256(compressed).hexdigest(),
        }
        print(f"{name}: {len(payload):,} -> {len(compressed):,} bytes")
    summary = args.output / "manifest-build-summary.json"
    summary.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
