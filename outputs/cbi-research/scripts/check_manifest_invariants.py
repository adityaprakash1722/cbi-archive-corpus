#!/usr/bin/env python3
r"""Check the tracked data agrees with itself, and that no document contradicts it.

    python outputs\cbi-research\scripts\check_manifest_invariants.py

This runs in CI on every push. It needs no network and no built index: it reads
only files tracked in git, so it catches the failure that keeps recurring here,
which is a number in a document drifting away from the data it describes.

Why it is written this way
--------------------------
The first version of this script checked a hand-picked list of facts and passed
while four documents still carried stale counts. Checking what you remembered to
check is not an invariant, it is a to-do list you already finished.

So the numbers are derived from the tracked data, and then **every** Markdown
document is scanned for values that contradict them. A new stale number in a
file nobody thought about still fails.

What it deliberately does not check
-----------------------------------
Dated records under `outputs/REMEDIATION-*.md` describe what was true on a
particular day. Rewriting those to match current reality would destroy the audit
trail, so they are exempt. So is the Markdown corpus itself, which is source
text rather than documentation.
"""
from __future__ import annotations

import csv, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RESEARCH = ROOT / "outputs" / "cbi-research"
EXEMPT = ("/corpus/", "REMEDIATION-", "node_modules", "/.git/")


def read_csv(path: Path) -> list[dict]:
    csv.field_size_limit(1 << 27)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(line.replace("\x00", "") for line in stream))


def documents_to_scan() -> list[Path]:
    return [p for p in sorted(ROOT.rglob("*.md"))
            if not any(part in str(p).replace("\\", "/") for part in EXEMPT)]


def main() -> int:
    problems: list[str] = []

    def check(label: str, got, want) -> None:
        ok = got == want
        if not ok:
            problems.append(f"{label}: got {got}, want {want}")
        print(f"  {label:46} {str(got):>14}  {'ok' if ok else 'FAIL'}")

    pdf = read_csv(RESEARCH / "corpus" / "conversion-manifest.csv")
    office = read_csv(RESEARCH / "corpus" / "office" / "conversion-manifest.csv")
    quality = read_csv(RESEARCH / "qa" / "extraction-quality.csv")
    provenance = read_csv(RESEARCH / "qa" / "provenance-classification.csv")
    catalog = read_csv(ROOT / "publish" / "blob-catalog.csv")
    summary = json.loads((ROOT / "publish" / "blob-summary.json").read_text(encoding="utf-8"))

    print("structure")
    check("PDF conversion manifest rows", len(pdf), 5246)
    check("Office conversion manifest rows", len(office), 323)
    check("extraction-quality rows", len(quality), 5568)
    check("blob catalogue rows", len(catalog), 6309)
    shared = {r["source_sha256"] for r in pdf} & {r["source_sha256"] for r in office}
    check("hashes in both conversion manifests", len(shared), 1)
    check("unique documents across both manifests",
          len({r["source_sha256"] for r in pdf} | {r["source_sha256"] for r in office}), 5568)
    check("catalogue matches its summary", summary["files_laid_out"], len(catalog))
    check("catalogue keys carrying a blobs/ prefix",
          sum(1 for r in catalog if r["key"].startswith("blobs/")), 0)
    check("summary layout string", summary["layout"], "<sha[0:2]>/<sha[2:4]>/<sha256><ext>")

    # Everything below is derived, so the expected values cannot drift from the data.
    authorship: dict[str, int] = {}
    for row in provenance:
        key = row.get("authorship") or row.get("new_authorship") or ""
        authorship[key] = authorship.get(key, 0) + 1
    flagged = sum(1 for r in quality if r["extraction_grade"] != "ok")
    scripts = sorted(p.name for p in (RESEARCH / "scripts").glob("*.py"))

    print("\nderived from the tracked data")
    for label, value in sorted(authorship.items()):
        print(f"  authorship {label:34} {value:>14,}")
    print(f"  {'documents graded below ok':46} {flagged:>14,}")
    print(f"  {'Python scripts':46} {len(scripts):>14,}")

    # Superseded values, each paired with the current one. A document may state a
    # superseded number when it is describing history, but only if the current
    # value appears beside it: that is the difference between a record and a
    # contradiction. `None` means the value is never acceptable.
    forbidden: list[tuple[str, str, str | None]] = [
        (r"\b3,?807\b", "central-bank count",
         str(authorship.get("central-bank", 0))),
        (r"unresolved[^\n]{0,24}\b105\b", "unresolved count",
         str(authorship.get("unresolved", 0))),
        (r"\b94 (?:regression )?assertions\b", "assertion count", "97"),
        (r"\b112 documents\b", "documents graded below ok", str(flagged)),
        (r"190[.,]502[,.]323|190\.5 million", "character count", "190,943,933|190.9"),
        (r"e92274b5adcc5cb97d2477bc93abc4094da82809c836fb4a68b76be5a0d9e0c2",
         "v3 index SHA", None),
        (r"05d6f3743db8db962e45abd55baf09a1664015cae3c0d116c6729394b724309e",
         "superseded v4 SHA", None),
        (r"/resolve/main/blobs/", "blobs/ URL that 404s", None),
        (r"not yet uploaded", "raw archive described as unpublished", None),
        (r"current v3 index|the current v3", "v3 described as current", None),
    ]

    print("\nno document may contradict the data")
    scanned = documents_to_scan()
    hits = 0
    for path in scanned:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern, why, current in forbidden:
            for match in re.finditer(pattern, text):
                if current:
                    # Accept it as history if the current value is stated nearby.
                    window = text[max(0, match.start() - 700):match.end() + 700]
                    if any(re.search(re.escape(value), window) for value in current.split("|")):
                        continue
                line = text.count("\n", 0, match.start()) + 1
                relative = path.relative_to(ROOT).as_posix()
                problems.append(
                    f"{relative}:{line} stale {why} ({match.group(0)!r})"
                    + (f", and {current} is not stated nearby" if current else ""))
                hits += 1
    check(f"stale values across {len(scanned)} documents", hits, 0)

    # analysis-v4 exists, so nothing should present analysis-v3 as the current scan.
    if (RESEARCH / "analysis-v4").is_dir():
        stale_analysis = 0
        for path in scanned:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for match in re.finditer(r"analysis-v3/[a-z-]+\.(?:csv|json)", text):
                if "analysis-v4" not in text[max(0, match.start() - 400):match.end() + 400]:
                    problems.append(
                        f"{path.relative_to(ROOT).as_posix()} cites {match.group(0)} "
                        f"with no mention of analysis-v4 nearby")
                    stale_analysis += 1
        check("documents citing analysis-v3 as current", stale_analysis, 0)

    print()
    if problems:
        print(f"FAIL: {len(problems)} problem(s)")
        for line in problems[:40]:
            print("  " + line)
        if len(problems) > 40:
            print(f"  ... and {len(problems) - 40} more")
        return 1
    print("PASS. The tracked data agrees with itself and no document contradicts it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
