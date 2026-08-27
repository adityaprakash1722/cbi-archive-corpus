#!/usr/bin/env python3
r"""Check tracked data, explicitly marked facts, and known documentation regressions.

    python outputs\cbi-research\scripts\check_manifest_invariants.py

Runs in CI on every push. Its CI checks need no network or built index. When the
untracked Markdown corpus and v4 index are present locally, it also verifies the
hash chain from each Markdown file through its manifest to the index.

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

The broad prose scan is deliberately only a regression guard: it can identify
known superseded values but cannot prove arbitrary English prose correct. Facts
that must remain exact use machine-readable markers whose displayed values are
compared with the tracked CSV or JSON that owns them. A superseded value in
deliberate history must carry `<!-- historical -->` on the same line.
"""
from __future__ import annotations

import csv, hashlib, importlib.util, json, re, sqlite3, statistics, subprocess, sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RESEARCH = ROOT / "outputs" / "cbi-research"

# Dated records describe what was true on a day. Rewriting them to match the
# present would destroy the audit trail, so they are exempt by name.
EXEMPT_FILES = ("outputs/REMEDIATION-2026-08-26.md",)

# Converted pilot output is source material, not documentation. A statistical
# release that happens to say "16%" near the word "thin" is a coincidence.
EXEMPT_DIRECTORIES = ("/outputs/cbi-research/pilot/",)
# If git is unavailable, rglob also sees the untracked 202 MB working corpus.
FALLBACK_EXEMPT_DIRECTORIES = EXEMPT_DIRECTORIES + ("/outputs/cbi-research/corpus/",)
HISTORICAL = "<!-- historical -->"

# Exact facts use an explicit span so the checker validates the displayed value,
# not merely the presence of the right number somewhere nearby.
FACT_PATTERN = re.compile(
    r"<!--\s*fact:([a-z0-9_.-]+)\s*-->\s*"
    r"([0-9][0-9,]*(?:\.[0-9]+)?)\s*<!--\s*/fact\s*-->", re.I)
FACT_OPEN_PATTERN = re.compile(r"<!--\s*fact:", re.I)
FACT_CLOSE_PATTERN = re.compile(r"<!--\s*/fact\s*-->", re.I)

# Requiring the markers at their canonical locations prevents a table from
# escaping validation by deleting its marker. Every occurrence is checked.
REQUIRED_FACT_COUNTS = {
    ("PUBLISHING.md", "repo.tracked_files"): 2,
    ("STORAGE.md", "repo.tracked_files"): 1,
    ("STORAGE.md", "quality.grade.gappy"): 1,
    ("STORAGE.md", "quality.grade.garbled"): 1,
    ("STORAGE.md", "quality.grade.thin"): 1,
    ("STORAGE.md", "quality.grade.empty"): 1,
    ("outputs/CBI-ARCHIVE-ANALYSIS-METHOD.md", "quality.grade.ok"): 1,
    ("outputs/CBI-ARCHIVE-ANALYSIS-METHOD.md", "quality.grade.gappy"): 1,
    ("outputs/CBI-ARCHIVE-ANALYSIS-METHOD.md", "quality.grade.garbled"): 1,
    ("outputs/CBI-ARCHIVE-ANALYSIS-METHOD.md", "quality.grade.thin"): 1,
    ("outputs/CBI-ARCHIVE-ANALYSIS-METHOD.md", "quality.grade.empty"): 1,
    ("outputs/CBI-ARCHIVE-ANALYSIS-METHOD.md", "quality.median_nonspace_per_page"): 1,
    ("outputs/CBI-ARCHIVE-ANALYSIS-METHOD.md", "quality.empty_page_share_percent"): 1,
}

# How far from a number a keyword may sit and still be about it.
WINDOW = 160


def read_csv(path: Path) -> list[dict]:
    csv.field_size_limit(1 << 27)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(line.replace("\x00", "") for line in stream))


def git_tracked_paths(pattern: str | None = None) -> list[str] | None:
    """Return git's file list, or None when git is unavailable."""
    command = ["git", "ls-files"]
    if pattern:
        command.append(pattern)
    try:
        out = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                             check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return [line for line in out.splitlines() if line]


def tracked_markdown() -> list[Path]:
    """Ask git, so CI and a local run see exactly the same files."""
    tracked = git_tracked_paths("*.md")
    if tracked is None:
        print("  WARNING: git unavailable, falling back to a filesystem walk")
        paths = []
        for path in sorted(ROOT.rglob("*.md")):
            relative = "/" + path.relative_to(ROOT).as_posix()
            if path.relative_to(ROOT).as_posix() not in EXEMPT_FILES \
                    and not any(part in relative for part in FALLBACK_EXEMPT_DIRECTORIES):
                paths.append(path)
        return paths
    return [ROOT / line for line in tracked
            if line and line not in EXEMPT_FILES
            and not any(part in "/" + line for part in EXEMPT_DIRECTORIES)]


def classifier_assertion_count() -> int:
    """Load the regression case lists instead of duplicating their total."""
    path = RESEARCH / "scripts" / "test_classify_provenance.py"
    spec = importlib.util.spec_from_file_location("cbi_classifier_regressions", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    scripts = str(path.parent)
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    spec.loader.exec_module(module)
    return len(module.CASES) + len(module.CONTENT_CASES) + len(module.CLASS_CASES)


def decimal_value(text: str) -> Decimal:
    """Parse a human-formatted number such as 5,486 or 0.61 exactly."""
    return Decimal(text.replace(",", ""))


def index_hash_counts(rows: list[tuple[str, str]], expected: dict[str, str]) -> tuple[int, int, int]:
    """Return stale, unexpected and missing SHA counts for an index."""
    index_hashes = {sha for sha, _ in rows}
    stale = sum(1 for sha, stored in rows
                if sha in expected and stored != expected[sha])
    unexpected = len(index_hashes - expected.keys())
    missing = len(expected.keys() - index_hashes)
    return stale, unexpected, missing


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
    blob_summary = json.loads(
        (ROOT / "publish" / "blob-summary.json").read_text(encoding="utf-8"))
    quality_summary = json.loads(
        (RESEARCH / "qa" / "extraction-quality-summary.json").read_text(encoding="utf-8"))
    tracked = git_tracked_paths()
    tracked_file_count = len(tracked) if tracked is not None else None

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
    check("catalogue matches its summary", blob_summary["files_laid_out"], len(catalog))
    check("catalogue keys carrying a blobs/ prefix",
          sum(1 for r in catalog if r["key"].startswith("blobs/")), 0)
    check("summary layout string", blob_summary["layout"], "<sha[0:2]>/<sha[2:4]>/<sha256><ext>")

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
    total_pages = sum(int(row["pages"]) for row in quality)
    total_empty_pages = sum(int(row["empty_pages"]) for row in quality)
    empty_page_share = round(total_empty_pages / max(total_pages, 1), 4)
    median_nonspace = round(statistics.median(
        float(row["nonspace_per_page"]) for row in quality), 1)
    scripts = sorted(p.name for p in (RESEARCH / "scripts").glob("*.py"))
    assertions = classifier_assertion_count()

    print("\nderived from the tracked data")
    for label, value in sorted(authorship.items()):
        print(f"  authorship {label:36} {value:>14,}")
    print(f"  {'documents graded ok / below ok':48} {clean:>8,} / {flagged:,}")
    print(f"  {'Python scripts':48} {len(scripts):>14,}")
    print(f"  {'classifier assertions':48} {assertions:>14,}")
    if tracked_file_count is not None:
        print(f"  {'git-tracked files':48} {tracked_file_count:>14,}")

    check("quality summary document count", quality_summary["documents_assessed"], len(quality))
    check("quality summary page count", quality_summary["total_pages"], total_pages)
    check("quality summary empty-page count", quality_summary["total_empty_pages"], total_empty_pages)
    check("quality summary empty-page share", quality_summary["empty_page_share"], empty_page_share)
    check("quality summary grade distribution", quality_summary["grades"], grades)
    check("quality summary median density", quality_summary["median_nonspace_per_page"], median_nonspace)
    check("quality summary flagged count", quality_summary["flagged_documents"], flagged)

    # The documented script count must match what is on disk.
    for name in ("CLAUDE.md", "AGENTS.md", "STORAGE.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        match = re.search(r"(\d+) Python files", text)
        check(f"{name} documented script count",
              int(match.group(1)) if match else None, len(scripts))

    expected_facts: dict[str, int | float | Decimal] = {
        **{f"quality.grade.{grade}": count for grade, count in grades.items()},
        "quality.median_nonspace_per_page": quality_summary["median_nonspace_per_page"],
        "quality.empty_page_share_percent": (
            Decimal(str(quality_summary["empty_page_share"])) * Decimal(100)),
    }
    if tracked_file_count is not None:
        expected_facts["repo.tracked_files"] = tracked_file_count

    # Known superseded figures remain useful regression guards, but this list is
    # not described as a proof that arbitrary prose is correct. Exact canonical
    # values are protected independently by the fact markers below.
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
        (63, ["gappy"], grades.get("gappy", 0), "`gappy` document count"),
        (16, ["thin"], grades.get("thin", 0), "`thin` document count"),
    ]

    print("\ntracked documentation facts and known-regression guards")
    scanned = tracked_markdown()
    hits = 0
    fact_counts: dict[tuple[str, str], int] = {}
    for path in scanned:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        lines = text.splitlines()
        relative = path.relative_to(ROOT).as_posix()

        fact_matches = list(FACT_PATTERN.finditer(text))
        malformed = (len(FACT_OPEN_PATTERN.findall(text)) - len(fact_matches)
                     + len(FACT_CLOSE_PATTERN.findall(text)) - len(fact_matches))
        if malformed:
            problems.append(f"{relative}: {malformed} malformed canonical fact marker(s)")
            hits += malformed
        for match in fact_matches:
            key, displayed = match.groups()
            key = key.lower()
            fact_counts[(relative, key)] = fact_counts.get((relative, key), 0) + 1
            if key not in expected_facts:
                problems.append(f"{relative}:{text.count(chr(10), 0, match.start()) + 1} "
                                f"unknown canonical fact {key!r}")
                hits += 1
                continue
            try:
                got = decimal_value(displayed)
                want = Decimal(str(expected_facts[key]))
            except InvalidOperation:
                problems.append(f"{relative}:{text.count(chr(10), 0, match.start()) + 1} "
                                f"invalid displayed value {displayed!r} for {key}")
                hits += 1
                continue
            if got != want:
                problems.append(f"{relative}:{text.count(chr(10), 0, match.start()) + 1} "
                                f"canonical fact {key}: got {displayed}, want {want}")
                hits += 1

        for stale, keywords, current, why in facts:
            if stale == current:
                continue
            for offset in number_near(text, stale, keywords):
                line_number = text.count("\n", 0, offset)
                if HISTORICAL in lines[line_number]:
                    continue
                problems.append(
                    f"{relative}:{line_number + 1} stale {why}: {stale:,} where the data says "
                    f"{current:,}. Add {HISTORICAL} to that line if it is deliberate history.")
                hits += 1
        # Strings that are simply wrong wherever they appear.
        for pattern, why in ((r"/resolve/main/blobs/", "blobs/ URL that 404s"),
                             (r"(?:raw archive|tier 3)[^\n]{0,100}"
                              r"(?:not yet uploaded|still outstanding)",
                              "raw archive described as unpublished"),
                             (r"\bmaster(?: branch)?\s+(?:is\s+)?at\s+`?[0-9a-f]{7,40}`?",
                              "mutable master branch pinned as current in tracked prose"),
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

    for location, want_count in REQUIRED_FACT_COUNTS.items():
        got_count = fact_counts.get(location, 0)
        if got_count != want_count:
            problems.append(
                f"{location[0]} canonical fact {location[1]} occurs {got_count} time(s), "
                f"want {want_count}")
            hits += 1
    check(f"documentation guard failures across {len(scanned)} tracked files", hits, 0)

    # The Markdown corpus and the built index are both untracked, so this runs
    # locally and skips in CI.
    #
    # The first version of this compared the Markdown files against the manifest
    # only. That would have passed during the exact failure it claimed to
    # prevent: the real defect was file == manifest but index != either, because
    # the OCR pass rebuilt the index before the manifest was synced. Both edges
    # of the triangle are checked now.
    print("\nlocal corpus and index, when present")
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
        index_rows = list(connection.execute(
            "SELECT source_sha256, markdown_sha256 FROM documents"))
        connection.close()
        stale_index, unexpected_index, missing_index = index_hash_counts(
            index_rows, file_hash)
        check("index document rows", len(index_rows), len(file_hash))
        check("index source hashes absent from the corpus", unexpected_index, 0)
        check("corpus source hashes absent from the index", missing_index, 0)
        check("index rows whose markdown_sha256 is stale", stale_index, 0)

    print()
    if problems:
        print(f"FAIL: {len(problems)} problem(s)")
        for line in problems[:40]:
            print("  " + line)
        if len(problems) > 40:
            print(f"  ... and {len(problems) - 40} more")
        return 1
    print("PASS. Structural, canonical-fact, known-regression and available local hash checks pass.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
