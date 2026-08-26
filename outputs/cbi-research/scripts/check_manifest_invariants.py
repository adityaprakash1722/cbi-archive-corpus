#!/usr/bin/env python3
r"""Check the tracked manifests agree with themselves and with the documentation.

    python outputs\cbi-research\scripts\check_manifest_invariants.py

This runs in CI on every push. It needs no network and no built index: it reads
only files tracked in git, so it catches the class of defect that kept recurring
here, which is a number in a document drifting away from the data it describes.

It does not check the corpus itself. `test_fresh_rebuild.py` does that, and it
needs the network.
"""
from __future__ import annotations

import csv, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RESEARCH = ROOT / "outputs" / "cbi-research"


def read_csv(path: Path) -> list[dict]:
    csv.field_size_limit(1 << 27)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        # Some PDF metadata carries NUL bytes, which csv refuses to parse.
        return list(csv.DictReader(line.replace("\x00", "") for line in stream))


def main() -> int:
    problems: list[str] = []

    def check(label: str, got, want) -> None:
        mark = "ok" if got == want else "FAIL"
        if got != want:
            problems.append(f"{label}: got {got}, want {want}")
        print(f"  {label:46} {str(got):>12}  {mark}")

    pdf = read_csv(RESEARCH / "corpus" / "conversion-manifest.csv")
    office = read_csv(RESEARCH / "corpus" / "office" / "conversion-manifest.csv")
    quality = read_csv(RESEARCH / "qa" / "extraction-quality.csv")
    catalog = read_csv(ROOT / "publish" / "blob-catalog.csv")
    summary = json.loads((ROOT / "publish" / "blob-summary.json").read_text(encoding="utf-8"))

    print("manifest row counts")
    check("PDF conversion manifest rows", len(pdf), 5246)
    check("Office conversion manifest rows", len(office), 323)
    check("extraction-quality rows", len(quality), 5568)
    check("blob catalogue rows", len(catalog), 6309)

    print("\ninternal consistency")
    shared = {r["source_sha256"] for r in pdf} & {r["source_sha256"] for r in office}
    check("hashes in both conversion manifests", len(shared), 1)
    check("unique documents across both manifests",
          len({r["source_sha256"] for r in pdf} | {r["source_sha256"] for r in office}), 5568)
    check("blob catalogue unique hashes", len({r["sha256"] for r in catalog}), 6309)
    check("catalogue matches its summary", summary["files_laid_out"], len(catalog))

    print("\npublished layout")
    prefixed = [r for r in catalog if r["key"].startswith("blobs/")]
    check("catalogue keys carrying a blobs/ prefix", len(prefixed), 0)
    check("summary layout string", summary["layout"],
          "<sha[0:2]>/<sha[2:4]>/<sha256><ext>")

    print("\nextraction grades")
    grades: dict[str, int] = {}
    for row in quality:
        grades[row["extraction_grade"]] = grades.get(row["extraction_grade"], 0) + 1
    flagged = sum(count for grade, count in grades.items() if grade != "ok")
    check("documents graded below ok", flagged, 82)

    print("\ndocumentation")
    scripts = sorted(p.name for p in (RESEARCH / "scripts").glob("*.py"))
    for name in ("CLAUDE.md", "AGENTS.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        match = re.search(r"the whole pipeline, (\d+) Python files", text)
        check(f"{name} script count", int(match.group(1)) if match else None, len(scripts))
        check(f"{name} names no superseded index",
              "cbi-corpus-v3-5568docs.sqlite` | 5,568 | **Yes" in text, False)
    storage = (ROOT / "STORAGE.md").read_text(encoding="utf-8")
    check("STORAGE.md has no blobs/ URL", "/resolve/main/blobs/" in storage, False)
    upload = (ROOT / "publish" / "UPLOAD.md").read_text(encoding="utf-8")
    check("UPLOAD.md expects the current split", "central-bank   3809" in upload, True)

    print()
    if problems:
        print(f"FAIL: {len(problems)} invariant(s) broken")
        for line in problems:
            print("  " + line)
        return 1
    print("PASS. Every tracked manifest agrees with itself and the documentation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
