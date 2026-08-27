#!/usr/bin/env python3
r"""Check the tracked data agrees with itself, and that no document contradicts it.

    python outputs\cbi-research\scripts\check_manifest_invariants.py

Runs in CI on every push. No network, no built index: it reads only files tracked
in git, so it catches the failure that keeps recurring here, which is a number in
a document drifting away from the data it describes.

Two earlier versions of this script were not worth their name
-------------------------------------------------------------
The first checked a hand-picked list of facts and passed while four documents
carried stale counts. The second replaced that with fixed regexes and passed
while five more did, because:

  * the patterns were direction- and wording-sensitive. `unresolved ... 105` was
    caught, `105 documents unresolved` was not; `94 assertions` was caught,
    `94 classifier assertions` and `94 regression tests` were not.
  * a superseded value was excused whenever the current value happened to appear
    within 700 characters, which is a coincidence, not a statement of history.
  * it walked the filesystem with rglob rather than asking git, so it scanned
    third-party files that CI would never see and reported a document count
    nobody else could reproduce.

So this version does three things differently. The file list comes from
`git ls-files`. Matching is by number plus nearby keyword, case-insensitive and
direction-independent, so rephrasing does not evade it. And a superseded value is
excused only by an explicit `<!-- historical -->` marker on the same line, which
is a decision somebody made rather than an accident of layout.
"""
from __future__ import annotations

import csv, json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RESEARCH = ROOT / "outputs" / "cbi-research"

# Dated records describe what was true on a day. Rewriting them to match the
# present would destroy the audit trail, so they are exempt by name.
EXEMPT_FILES = ("outputs/REMEDIATION-2026-08-26.md",)

# Converted corpus text is source material, not documentation. A statistical
# release that happens to say "16%" near the word "thin" is a coincidence.
EXEMPT_DIRECTORIES = ("/markdown/", "/corpus/")
HISTORICAL = "<!-- historical -->"

# How far from a number a keyword may sit and still be about it.
WINDOW = 160


def read_csv(path: Path) -> list[dict]:
    csv.field_size_limit(1 << 27)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(line.replace("\x00", "") for line in stream))


def tracked_markdown() -> list[Path]:
    """Ask git, so CI and a local run see exactly the same files."""
    try:
        out = subprocess.run(["git", "ls-files", "*.md"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("  WARNING: git unavailable, falling back to a filesystem walk")
        return [p for p in sorted(ROOT.rglob("*.md")) if "/corpus/" not in p.as_posix()]
    return [ROOT / line for line in out.splitlines()
            if line and line not in EXEMPT_FILES
            and not any(part in "/" + line for part in EXEMPT_DIRECTORIES)]


def number_near(text: str, value: int, keywords: list[str]) -> list[int]:
    """Offsets where `value` appears as a standalone number beside any keyword."""
    pattern = re.compile(r"(?<![\d,.])" + f"{value:,}".replace(",", r",?") + r"(?![\d,.])")
    found = []
    lowered = text.lower()
    for match in pattern.finditer(text):
        window = lowered[max(0, match.start() - WINDOW):match.end() + WINDOW]
        if any(k in window for k in keywords):
            found.append(match.start())
    return found


def main() -> int:
    problems: list[str] = []

    def check(label: str, got, want) -> None:
        ok = got == want
        if not ok:
            problems.append(f"{label}: got {got}, want {want}")
        print(f"  {label:48} {str(got):>14}  {'ok' if ok else 'FAIL'}")

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
    check("blob catalogue unique hashes", len({r["sha256"] for r in catalog}), 6309)
    check("blob catalogue unique keys", len({r["key"] for r in catalog}), 6309)
    check("hashes in both conversion manifests",
          len({r["source_sha256"] for r in pdf} & {r["source_sha256"] for r in office}), 1)
    check("unique documents across both manifests",
          len({r["source_sha256"] for r in pdf} | {r["source_sha256"] for r in office}), 5568)
    check("catalogue matches its summary", summary["files_laid_out"], len(catalog))
    check("catalogue keys carrying a blobs/ prefix",
          sum(1 for r in catalog if r["key"].startswith("blobs/")), 0)
    check("summary layout string", summary["layout"], "<sha[0:2]>/<sha[2:4]>/<sha256><ext>")

    authorship: dict[str, int] = {}
    for row in provenance:
        key = row.get("authorship") or row.get("new_authorship") or ""
        authorship[key] = authorship.get(key, 0) + 1
    confidence: dict[str, int] = {}
    for row in provenance:
        key = row.get("classification_confidence") or ""
        confidence[key] = confidence.get(key, 0) + 1
    # The whole distribution, not two numbers from it. Checking `ok` and the
    # flagged total let two documents keep a breakdown that read
    # "63 gappy, 26 garbled, 16 thin, 7 empty", which sums to 112 while the
    # sentence above it said 82. Every grade is now its own fact.
    grades: dict[str, int] = {}
    for row in quality:
        grades[row["extraction_grade"]] = grades.get(row["extraction_grade"], 0) + 1
    flagged = sum(count for grade, count in grades.items() if grade != "ok")
    clean = grades.get("ok", 0)
    scripts = sorted(p.name for p in (RESEARCH / "scripts").glob("*.py"))
    assertions = 97

    print("\nderived from the tracked data")
    for label, value in sorted(authorship.items()):
        print(f"  authorship {label:36} {value:>14,}")
    print(f"  {'documents graded ok / below ok':48} {clean:>8,} / {flagged:,}")
    print(f"  {'Python scripts':48} {len(scripts):>14,}")

    # The documented script count must match what is on disk.
    for name in ("CLAUDE.md", "AGENTS.md", "STORAGE.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        match = re.search(r"(\d+) Python files", text)
        check(f"{name} documented script count",
              int(match.group(1)) if match else None, len(scripts))

    # (superseded value, keywords that mean it is about this fact, current value)
    facts: list[tuple[int, list[str], int, str]] = [
        (3807, ["central-bank", "central bank document"], authorship.get("central-bank", 0),
         "central-bank count"),
        (105, ["unresolved"], authorship.get("unresolved", 0), "unresolved count"),
        (105, ["confidence", "low "], confidence.get("low", 0), "low-confidence count"),
        (123, ["confidence", "medium"], confidence.get("medium", 0), "medium-confidence count"),
        (94, ["assertion", "regression test", "classifier", "test_classify"],
         assertions, "assertion count"),
        (112, ["flag", "graded", "extraction", "extract badly", "below `ok`"],
         flagged, "documents graded below ok"),
        (5456, ["clean", "graded", "extraction", "| ok |"], clean, "documents graded ok"),
    ]
    # Every superseded per-grade count, derived rather than listed. The keyword is
    # the grade name itself, so a breakdown table cannot drift without failing.
    SUPERSEDED_GRADES = {"gappy": [63], "garbled": [], "thin": [16], "empty": [],
                         "ok": [5456]}
    for grade, olds in SUPERSEDED_GRADES.items():
        for old in olds:
            if old != grades.get(grade, 0):
                facts.append((old, [grade], grades.get(grade, 0),
                              f"`{grade}` document count"))

    print("\nno tracked document may contradict the data")
    scanned = tracked_markdown()
    hits = 0
    for path in scanned:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        lines = text.splitlines()
        for stale, keywords, current, why in facts:
            if stale == current:
                continue
            for offset in number_near(text, stale, keywords):
                line_number = text.count("\n", 0, offset)
                if HISTORICAL in lines[line_number]:
                    continue
                relative = path.relative_to(ROOT).as_posix()
                problems.append(
                    f"{relative}:{line_number + 1} stale {why}: {stale:,} where the data says "
                    f"{current:,}. Add {HISTORICAL} to that line if it is deliberate history.")
                hits += 1
        # Strings that are simply wrong wherever they appear.
        for pattern, why in ((r"/resolve/main/blobs/", "blobs/ URL that 404s"),
                             (r"not yet uploaded", "raw archive described as unpublished"),
                             (r"current v3 index|the current v3|analysis-v3/\s+current",
                              "a superseded artefact described as current"),
                             (r"e92274b5adcc5cb97d2477bc93abc4094da82809c836fb4a68b76be5a0d9e0c2"
                              r"|05d6f3743db8db962e45abd55baf09a1664015cae3c0d116c6729394b724309e",
                              "superseded index SHA")):
            for match in re.finditer(pattern, text, re.I):
                line_number = text.count("\n", 0, match.start())
                if HISTORICAL in lines[line_number]:
                    continue
                problems.append(
                    f"{path.relative_to(ROOT).as_posix()}:{line_number + 1} {why}: "
                    f"{match.group(0)[:60]!r}")
                hits += 1
    check(f"contradictions across {len(scanned)} git-tracked documents", hits, 0)

    # The Markdown corpus and the built index are both untracked, so this runs
    # locally and skips in CI.
    #
    # The first version of this compared the Markdown files against the manifest
    # only. That would have passed during the exact failure it claimed to
    # prevent: the real defect was file == manifest but index != either, because
    # the OCR pass rebuilt the index before the manifest was synced. Both edges
    # of the triangle are checked now.
    print("\nlocal corpus and index, when present")
    import hashlib, sqlite3
    file_hash: dict[str, str] = {}
    stale_manifest = missing = 0
    for where, rows in (("", pdf), ("office", office)):
        root = RESEARCH / "corpus" / where if where else RESEARCH / "corpus"
        for row in rows:
            path = root / (row["markdown_file"] or "").replace("\\", "/")
            if not path.is_file():
                missing += 1
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            file_hash.setdefault(row["source_sha256"], digest)
            if digest != row.get("markdown_sha256"):
                stale_manifest += 1
    if missing == len(pdf) + len(office):
        print("  corpus not present, skipped (this is normal in CI)")
    else:
        check("Markdown files whose hash differs from the manifest", stale_manifest, 0)
        check("manifest rows with no Markdown file on disk", missing, 0)

    index = RESEARCH / "index" / "cbi-corpus-v4-5568docs.sqlite"
    if not index.is_file() or not file_hash:
        print("  index not present, skipped (this is normal in CI)")
    else:
        connection = sqlite3.connect(index)
        stale_index = 0
        for sha, stored in connection.execute(
                "SELECT source_sha256, markdown_sha256 FROM documents"):
            expected = file_hash.get(sha)
            if expected is not None and stored != expected:
                stale_index += 1
        connection.close()
        check("index rows whose markdown_sha256 is stale", stale_index, 0)

    print()
    if problems:
        print(f"FAIL: {len(problems)} problem(s)")
        for line in problems[:40]:
            print("  " + line)
        if len(problems) > 40:
            print(f"  ... and {len(problems) - 40} more")
        return 1
    print("PASS. The tracked data agrees with itself and no tracked document contradicts it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
