#!/usr/bin/env python3
"""Parse and profile the small XML subset of the CBI archive."""

from __future__ import annotations

import argparse
import csv
import json
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def main() -> int:
    args = arguments()
    archive = args.archive.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with args.catalog.resolve().open(encoding="utf-8-sig", newline="") as stream:
        entries = [row for row in csv.DictReader(stream) if row["format"] == "XML"]

    rows: list[dict[str, Any]] = []
    for entry in entries:
        path = archive / entry["local_path"].replace("\\", "/")  # manifest paths are written on Windows
        status = "parsed"
        error = ""
        root_tag = ""
        elements = 0
        max_depth = 0
        tag_counts: Counter[str] = Counter()
        namespaces: set[str] = set()
        sample_text: list[str] = []
        try:
            root = ET.parse(path).getroot()
            root_tag = local_name(root.tag)
            stack = [(root, 1)]
            while stack:
                element, depth = stack.pop()
                elements += 1
                max_depth = max(max_depth, depth)
                tag_counts[local_name(element.tag)] += 1
                if element.tag.startswith("{"):
                    namespaces.add(element.tag[1:].split("}", 1)[0])
                text = " ".join((element.text or "").split())
                if text and len(sample_text) < 15:
                    sample_text.append(text[:200])
                stack.extend((child, depth + 1) for child in reversed(list(element)))
        except Exception as exc:
            status = "error"
            error = f"{type(exc).__name__}: {exc}"[:1000]
        rows.append({
            "sha256": entry["sha256"],
            "bytes": int(entry["bytes"]),
            "status": status,
            "root_tag": root_tag,
            "element_count": elements,
            "max_depth": max_depth,
            "namespace_count": len(namespaces),
            "namespaces": " | ".join(sorted(namespaces)),
            "common_tags": " | ".join(f"{tag}:{count}" for tag, count in tag_counts.most_common(20)),
            "sample_text": " | ".join(sample_text),
            "error": error,
            "canonical_url": entry["canonical_url"],
            "local_path": entry["local_path"],
        })

    fields = list(rows[0]) if rows else []
    with (output / "xml-profile.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "logical_xml_files": len(rows),
        "parsed": sum(row["status"] == "parsed" for row in rows),
        "errors": sum(row["status"] == "error" for row in rows),
        "total_elements": sum(row["element_count"] for row in rows),
        "purpose": "All five files are regulatory reporting examples/schemas, not economic observations.",
    }
    (output / "xml-profile.json").write_text(
        json.dumps({"summary": summary, "files": rows}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
