#!/usr/bin/env python3
r"""Check tracked data, explicitly marked facts, and known documentation regressions.

    python outputs\cbi-research\scripts\check_manifest_invariants.py

Runs in CI on every push. Its CI checks need no network or built index. When the
untracked Markdown corpus and v5.2 index are present locally, it also verifies the
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

import argparse, csv, hashlib, importlib.util, json, re, sqlite3, statistics, subprocess, sys
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
NOT_A_POPULATION_COUNT = "<!-- not-a-population-count -->"

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
    ("STORAGE.md", "voice.cbi-institutional"): 1,
    ("STORAGE.md", "voice.stakeholder"): 1,
    ("STORAGE.md", "voice.unknown"): 1,
    ("STORAGE.md", "voice.mixed"): 1,
    ("STORAGE.md", "classifier.assertions"): 1,
    ("STORAGE.md", "audit.documents"): 1,
    ("outputs/CBI-ARCHIVE-ANALYSIS-METHOD.md", "voice.cbi-institutional"): 1,
    ("outputs/CBI-ARCHIVE-ANALYSIS-METHOD.md", "voice.stakeholder"): 1,
    ("outputs/CBI-ARCHIVE-ANALYSIS-METHOD.md", "voice.unknown"): 1,
    ("outputs/CBI-ARCHIVE-ANALYSIS-METHOD.md", "voice.mixed"): 1,
    ("outputs/CBI-ARCHIVE-ANALYSIS-METHOD.md", "classifier.assertions"): 1,
    ("outputs/CBI-ARCHIVE-ANALYSIS-METHOD.md", "audit.documents"): 1,
    ("outputs/CBI-ARCHIVE-ANALYSIS-METHOD.md", "audit.correct"): 1,
}

# How far from a number a keyword may sit and still be about it.
WINDOW = 160


def read_csv(path: Path) -> list[dict]:
    csv.field_size_limit(1 << 27)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(line.replace("\x00", "") for line in stream))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines()
            if line.strip()]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def local_release_artifact(name: str) -> Path:
    """Map a lock key to the exact local bytes uploaded for that artifact."""
    if name.startswith(("data/", "manifests/")):
        return ROOT / "publish" / "hf" / name
    return ROOT / name


def git_tracked_paths(pattern: str | None = None) -> list[str] | None:
    """Return files that would be present after a commit, or None without git.

    Including non-ignored untracked files makes canonical repository-file counts
    checkable before a commit as well as after it. It also catches exactly the
    accidental-artifact escape that the count is intended to guard.
    """
    command = ["git", "ls-files", "--cached", "--others", "--exclude-standard"]
    if pattern:
        command += ["--", pattern]
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
    return (len(module.CASES) + len(module.CONTENT_CASES) + len(module.CLASS_CASES)
            + len(module.ID_CASES) * 2 + len(module.VOICE_CASES) * 3)


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
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--allow-release-drift", action="store_true",
        help="pre-publication mode: report but do not fail on RELEASE.lock.json drift",
    )
    args = parser.parse_args()
    problems: list[str] = []

    def check(label: str, got, want) -> None:
        ok = got == want
        if not ok:
            problems.append(f"{label}: got {got}, want {want}")
        print(f"  {label:48} {str(got):>14}  {'ok' if ok else 'FAIL'}")

    def release_check(label: str, got, want) -> None:
        if args.allow_release_drift:
            state = "matches" if got == want else "expected pre-publication drift"
            print(f"  {label:48} {str(got):>14}  {state}")
            return
        check(label, got, want)

    pdf = read_csv(RESEARCH / "corpus" / "conversion-manifest.csv")
    office = read_csv(RESEARCH / "corpus" / "office" / "conversion-manifest.csv")
    quality = read_csv(RESEARCH / "qa" / "extraction-quality.csv")
    provenance = read_csv(RESEARCH / "qa" / "provenance-classification.csv")
    catalog = read_csv(ROOT / "publish" / "blob-catalog.csv")
    blob_summary = json.loads(
        (ROOT / "publish" / "blob-summary.json").read_text(encoding="utf-8"))
    raw_validation = json.loads(
        (RESEARCH / "qa" / "raw-archive-validation.json").read_text(encoding="utf-8"))
    quality_summary = json.loads(
        (RESEARCH / "qa" / "extraction-quality-summary.json").read_text(encoding="utf-8"))
    corpus_validation = json.loads(
        (RESEARCH / "qa" / "corpus-validation.json").read_text(encoding="utf-8"))
    authorship_gold = read_csv(RESEARCH / "qa" / "authorship-gold.csv")
    authorship_evaluation = json.loads(
        (RESEARCH / "qa" / "authorship-evaluation.json").read_text(encoding="utf-8"))
    release = json.loads((ROOT / "RELEASE.lock.json").read_text(encoding="utf-8"))
    page_overrides = read_csv(RESEARCH / "qa" / "page-authorship-overrides.csv")
    authorship_overrides = read_csv(RESEARCH / "qa" / "authorship-overrides.csv")
    conversion_exclusions = read_csv(RESEARCH / "qa" / "conversion-exclusions.csv")
    engagement_coverage = read_csv(RESEARCH / "qa" / "engagement-coverage.csv")
    engagement_summary = json.loads(
        (RESEARCH / "qa" / "engagement-coverage-summary.json").read_text(encoding="utf-8"))
    voice_scope = read_csv(RESEARCH / "qa" / "voice-review-scope.csv")
    voice_scope_summary = json.loads(
        (RESEARCH / "qa" / "voice-review-scope-summary.json").read_text(encoding="utf-8"))
    individual_review = read_csv(RESEARCH / "qa" / "individual-submission-review.csv")
    extraction_preferences = read_csv(RESEARCH / "qa" / "extraction-preferences.csv")
    file_manifest = read_csv(ROOT / "outputs" / "cbi-archive" / "cbi-data" /
                             "manifests" / "files.csv")
    page_manifest = read_csv(ROOT / "outputs" / "cbi-archive" / "cbi-data" /
                             "manifests" / "page-snapshots.csv")
    page_catalog = read_csv(ROOT / "publish" / "page-catalog.csv")
    pdf_journal = read_jsonl(RESEARCH / "corpus" / "conversion-journal.jsonl")
    tracked = git_tracked_paths()
    tracked_file_count = len(tracked) if tracked is not None else None

    print("structure")
    check("PDF conversion manifest rows", len(pdf), 5246)
    check("Office conversion manifest rows", len(office), 323)
    check("extraction-quality rows", len(quality), 5568)
    check("full PDF and Office validation failures", corpus_validation.get("failures"), 0)
    check("full validation unique source hashes",
          corpus_validation.get("manifest_unique_shas"), 5568)
    check("full validation physical conversion records",
          corpus_validation.get("manifest_records"), 5569)
    check("blob catalogue rows", len(catalog), 6309)
    check("blob catalogue unique hashes", len({r["sha256"] for r in catalog}), 6309)
    check("blob catalogue unique keys", len({r["key"] for r in catalog}), 6309)
    check("hashes in both conversion manifests",
          len({r["source_sha256"] for r in pdf} & {r["source_sha256"] for r in office}), 1)
    check("unique documents across both manifests",
          len({r["source_sha256"] for r in pdf} | {r["source_sha256"] for r in office}), 5568)
    check("catalogue matches its summary", blob_summary["files_laid_out"], len(catalog))
    check("full raw validation passed", raw_validation.get("passed"), True)
    check("full raw validation unique objects",
          raw_validation.get("unique_downloaded_files"), len(catalog))
    check("full raw validation bytes",
          raw_validation.get("bytes_hashed"), blob_summary.get("total_bytes"))
    check("catalogue keys carrying a blobs/ prefix",
          sum(1 for r in catalog if r["key"].startswith("blobs/")), 0)
    check("summary layout string", blob_summary["layout"], "<sha[0:2]>/<sha[2:4]>/<sha256><ext>")
    check("files.csv local paths using backslashes",
          sum("\\" in (row.get("localPath") or "") for row in file_manifest), 0)
    check("page snapshot manifest rows", len(page_manifest), 11371)
    check("page snapshot catalogue agrees with raw summary", len(page_catalog),
          blob_summary.get("page_snapshots_laid_out", 0))
    check("legacy snapshot rows claiming archived HTML bodies",
          sum(bool(row.get("htmlSha256") or row.get("archiveKey")) for row in page_manifest), 0)
    check("archived page keys are deterministic",
          sum(1 for row in page_manifest if row.get("htmlSha256") and
              row.get("archiveKey") !=
              f"page-context/{row['htmlSha256'][:2]}/{row['htmlSha256']}.html"), 0)
    release_check("release-lock schema version", release.get("schema_version"), 2)
    release_check("release-lock corpus revision is immutable",
          bool(re.fullmatch(r"[0-9a-f]{40}",
                            release.get("hugging_face", {}).get("corpus_revision", ""))), True)
    release_check("release-lock raw revision is immutable",
          bool(re.fullmatch(r"[0-9a-f]{40}",
                            release.get("hugging_face", {}).get("raw_revision", ""))), True)
    release_check("release-lock artifact hashes are SHA-256",
          all(re.fullmatch(r"[0-9a-f]{64}", value or "")
              for value in release.get("artifacts", {}).values()), True)
    for name, wanted in release.get("artifacts", {}).items():
        path = local_release_artifact(name)
        if not path.is_file() and name in {
                "data/documents.parquet", "data/pages.parquet"}:
            print(f"  release-lock bytes {name:29} {'not in git':>14}  skipped")
            continue
        release_check(f"release-lock bytes {name}",
                      sha256_file(path) if path.is_file() else None, wanted)
    release_check("release-lock expected document count",
          release.get("expected", {}).get("documents"), 5568)
    overlap = {row["source_sha256"] for row in pdf} & {
        row["source_sha256"] for row in office}
    check("duplicate extractions with explicit preferences",
          {row["source_sha256"] for row in extraction_preferences}, overlap)
    check("mixed documents with page-authorship overrides",
          len({row["source_sha256"] for row in page_overrides}), 2)
    check("authorship adjudication rows", len(authorship_overrides), 114)
    check("authorship adjudication hashes unique",
          len({row["source_sha256"] for row in authorship_overrides}), len(authorship_overrides))
    check("conversion exclusion rows", len(conversion_exclusions), 1)
    journal_hashes = {row.get("source_sha256") for row in pdf_journal if row.get("source_sha256")}
    pdf_hashes = {row["source_sha256"] for row in pdf}
    excluded_hashes = {row["source_sha256"] for row in conversion_exclusions}
    check("PDF journal accounted for by manifest plus exclusions",
          journal_hashes == pdf_hashes | excluded_hashes, True)
    check("conversion exclusions absent from converted PDF manifest",
          len(excluded_hashes & pdf_hashes), 0)
    check("engagement coverage CSV rows", len(engagement_coverage), 182)
    check("engagement coverage CP identifiers present",
          sum(row["engagement_type"] == "consultation-paper" and
              row["snapshot_status"] == "present" for row in engagement_coverage),
          engagement_summary["cp_identifiers_present"])
    check("engagement coverage complete loops",
          sum((row.get("complete_argumentative_loop") or "").lower() == "true"
              for row in engagement_coverage), engagement_summary["complete_argumentative_loops"])
    check("voice review scope rows", len(voice_scope),
          voice_scope_summary["documents_in_scope"])
    check("voice review scope hashes unique",
          len({row["source_sha256"] for row in voice_scope}), len(voice_scope))
    check("authorship audit covers every gold row",
          authorship_evaluation.get("documents"), len(authorship_gold))
    check("authorship audit has no detected errors",
          authorship_evaluation.get("correct"), len(authorship_gold))

    authorship: dict[str, int] = {}
    for row in provenance:
        key = row.get("authorship") or row.get("new_authorship") or ""
        authorship[key] = authorship.get(key, 0) + 1
    institutional_voice: dict[str, int] = {}
    for row in provenance:
        key = row.get("institutional_voice") or ""
        institutional_voice[key] = institutional_voice.get(key, 0) + 1
    confidence: dict[str, int] = {}
    for row in provenance:
        key = row.get("classification_confidence") or ""
        confidence[key] = confidence.get(key, 0) + 1
    adjudicated = {row["source_sha256"] for row in provenance
                   if row.get("classification_basis", "").startswith("adjudicated:")}
    check("adjudication hashes carried into provenance",
          adjudicated == {row["source_sha256"] for row in authorship_overrides}, True)
    check("current unresolved document count", authorship.get("unresolved", 0), 3480)
    release_check("release-lock expected authorship split",
          release.get("expected", {}).get("authorship"), authorship)
    release_check("release-lock expected institutional-voice split",
          release.get("expected", {}).get("institutional_voice"), institutional_voice)
    current_by_sha = {row["source_sha256"]: row["authorship"] for row in provenance}
    check("rights-review candidates with stale authorship",
          sum(current_by_sha.get(row["source_sha256"]) != row.get("authorship")
              for row in individual_review), 0)

    canonical_csvs = [
        RESEARCH / "corpus" / "conversion-manifest.csv",
        RESEARCH / "corpus" / "office" / "conversion-manifest.csv",
        RESEARCH / "qa" / "provenance-classification.csv",
        RESEARCH / "qa" / "extraction-quality.csv",
        RESEARCH / "qa" / "authorship-overrides.csv",
        RESEARCH / "qa" / "page-authorship-overrides.csv",
        RESEARCH / "qa" / "conversion-exclusions.csv",
        RESEARCH / "qa" / "engagement-coverage.csv",
        RESEARCH / "qa" / "voice-review-scope.csv",
        RESEARCH / "qa" / "individual-submission-review.csv",
        RESEARCH / "qa" / "corpus-validation-failures.csv",
        RESEARCH / "qa" / "corpus-validation-warnings.csv",
        ROOT / "publish" / "blob-catalog.csv",
        ROOT / "publish" / "page-catalog.csv",
    ]
    check("generated CSVs with a UTF-8 BOM",
          sum(path.read_bytes().startswith(b"\xef\xbb\xbf") for path in canonical_csvs), 0)
    check("generated CSVs containing CRLF",
          sum(b"\r\n" in path.read_bytes() for path in canonical_csvs), 0)
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
    for label, value in sorted(institutional_voice.items()):
        print(f"  institutional voice {label:27} {value:>14,}")
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
        **{f"voice.{label}": institutional_voice.get(label, 0)
           for label in ("cbi-institutional", "stakeholder", "unknown", "mixed")},
        "classifier.assertions": assertions,
        "audit.documents": len(authorship_gold),
        "audit.correct": authorship_evaluation.get("correct", 0),
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
        (3809, ["central-bank", "central bank document"], authorship.get("central-bank", 0),
         "central-bank count"),
        (1671, ["stakeholder"], authorship.get("stakeholder", 0), "stakeholder count"),
        (1656, ["stakeholder"], authorship.get("stakeholder", 0), "stakeholder count"),
        (89, ["unresolved"], authorship.get("unresolved", 0), "unresolved count"),
        (103, ["unresolved"], authorship.get("unresolved", 0), "unresolved count"),
        (105, ["unresolved"], authorship.get("unresolved", 0), "unresolved count"),
        (105, ["confidence", "low "], confidence.get("low", 0), "low-confidence count"),
        (125, ["confidence", "medium"], confidence.get("medium", 0), "medium-confidence count"),
        (5340, ["confidence", "high"], confidence.get("high", 0), "high-confidence count"),
        (123, ["confidence", "medium"], confidence.get("medium", 0), "medium-confidence count"),
        (97, ["assertion", "regression test", "classifier", "test_classify"],
         assertions, "assertion count"),
        (94, ["assertion", "regression test", "classifier", "test_classify"],
         assertions, "assertion count"),
        (102, ["assertion", "regression test", "classifier", "test_classify"],
         assertions, "assertion count"),
        (104, ["assertion", "regression test", "classifier", "test_classify"],
         assertions, "assertion count"),
        (123, ["assertion", "regression test", "classifier", "test_classify"],
         assertions, "assertion count"),
        (30, ["audit sample", "human-reviewed sample", "human-labelled audit", "30/30"],
         len(authorship_gold), "human-audit sample size"),
        (82, ["flag", "graded", "extraction", "extract badly", "below `ok`"],
         flagged, "documents graded below ok"),
        (81, ["flag", "graded", "extraction", "extract badly", "below `ok`"],
         flagged, "documents graded below ok"),
        (112, ["flag", "graded", "extraction", "extract badly", "below `ok`"],
         flagged, "documents graded below ok"),
        (5486, ["clean", "graded", "extraction", "| ok |"], clean,
         "documents graded ok"),
        (5456, ["clean", "graded", "extraction", "| ok |"], clean, "documents graded ok"),
        (63, ["gappy"], grades.get("gappy", 0), "`gappy` document count"),
        (26, ["garbled"], grades.get("garbled", 0), "`garbled` document count"),
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
                if (HISTORICAL in lines[line_number]
                        or NOT_A_POPULATION_COUNT in lines[line_number]):
                    continue
                problems.append(
                    f"{relative}:{line_number + 1} stale {why}: {stale:,} where the data says "
                                 f"{current:,}. Add {HISTORICAL} for deliberate history or "
                                 f"{NOT_A_POPULATION_COUNT} for an unrelated measure.")
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
    file_candidates: dict[str, dict[str, str]] = {}
    stale_manifest = missing = 0
    for corpus_name, where, rows in (("pdf", "", pdf), ("office", "office", office)):
        root = RESEARCH / "corpus" / where if where else RESEARCH / "corpus"
        for row in rows:
            path = root / (row["markdown_file"] or "").replace("\\", "/")
            if not path.is_file():
                missing += 1
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            file_candidates.setdefault(row["source_sha256"], {})[corpus_name] = digest
            if digest != row.get("markdown_sha256"):
                stale_manifest += 1
    preferred = {row["source_sha256"]: row["preferred_corpus"]
                 for row in extraction_preferences}
    for sha, candidates in file_candidates.items():
        if len(candidates) == 1:
            file_hash[sha] = next(iter(candidates.values()))
            continue
        choice = preferred.get(sha)
        if choice not in candidates:
            problems.append(f"duplicate extraction {sha} has no valid preference")
            continue
        file_hash[sha] = candidates[choice]
    if missing == len(pdf) + len(office):
        print("  corpus not present, skipped (this is normal in CI)")
    else:
        check("Markdown files whose hash differs from the manifest", stale_manifest, 0)
        check("manifest rows with no Markdown file on disk", missing, 0)

    index = RESEARCH / "index" / "cbi-corpus-v5.2-5568docs.sqlite"
    if not index.is_file() or not file_hash:
        print("  index not present, skipped (this is normal in CI)")
    else:
        connection = sqlite3.connect(index)
        index_rows = list(connection.execute(
            "SELECT source_sha256, markdown_sha256 FROM documents"))
        stale_index, unexpected_index, missing_index = index_hash_counts(
            index_rows, file_hash)
        check("index document rows", len(index_rows), len(file_hash))
        check("index source hashes absent from the corpus", unexpected_index, 0)
        check("corpus source hashes absent from the index", missing_index, 0)
        check("index rows whose markdown_sha256 is stale", stale_index, 0)
        check("index documents with a future analysis year",
              connection.execute(
                  "SELECT COUNT(*) FROM documents WHERE analysis_year > 2026").fetchone()[0], 0)
        consultation_ids = [row[0] for row in connection.execute(
            "SELECT DISTINCT consultation_id FROM documents WHERE consultation_id IS NOT NULL")]
        engagement_ids = [row[0] for row in connection.execute(
            "SELECT DISTINCT engagement_id FROM documents WHERE engagement_id IS NOT NULL")]
        check("index noncanonical consultation identifiers",
              sum(not re.fullmatch(r"cp[1-9][0-9]*[a-z]?", value)
                  for value in consultation_ids), 0)
        check("index noncanonical engagement identifiers",
              sum(not re.fullmatch(r"(?:cp|dp)[1-9][0-9]*[a-z]?", value)
                  for value in engagement_ids), 0)
        check("misfiled /cp71/ documents not normalised to cp70",
              connection.execute(
                  "SELECT COUNT(*) FROM documents WHERE lower(source_url) LIKE '%/cp71/%' "
                  "AND consultation_id != 'cp70'").fetchone()[0], 0)
        check("/cp071/ documents not normalised to cp71",
              connection.execute(
                  "SELECT COUNT(*) FROM documents WHERE lower(source_url) LIKE '%/cp071/%' "
                  "AND consultation_id != 'cp71'").fetchone()[0], 0)
        check("index mixed-document count",
              connection.execute(
                  "SELECT COUNT(*) FROM documents WHERE authorship = 'mixed'").fetchone()[0], 2)
        check("index unresolved-document count",
              connection.execute(
                  "SELECT COUNT(*) FROM documents WHERE authorship = 'unresolved'").fetchone()[0],
              authorship.get("unresolved", 0))
        check("index pages without page-level authorship",
              connection.execute(
                  "SELECT COUNT(*) FROM pages WHERE authorship IS NULL OR authorship = ''").fetchone()[0], 0)
        check("index pages without institutional voice",
              connection.execute(
                  "SELECT COUNT(*) FROM pages WHERE institutional_voice IS NULL "
                  "OR institutional_voice = ''").fetchone()[0], 0)
        check("index pages without voice review status",
              connection.execute(
                  "SELECT COUNT(*) FROM pages WHERE voice_review_status IS NULL "
                  "OR voice_review_status = ''").fetchone()[0], 0)
        check("index quality empty-page total",
              connection.execute("SELECT SUM(quality_empty_pages) FROM documents").fetchone()[0],
              total_empty_pages)
        direct_empty = direct_replacements = 0
        for page_text, in connection.execute("SELECT text FROM pages"):
            text_value = page_text or ""
            direct_empty += len("".join(text_value.split())) < 30
            direct_replacements += text_value.count("\ufffd")
        check("page text recomputation of near-blank pages", direct_empty, total_empty_pages)
        check("page text recomputation of replacement characters", direct_replacements,
              sum(int(row["replacement_characters"]) for row in quality))
        check("content cluster rows with inconsistent sizes",
              connection.execute("""
                  SELECT COUNT(*) FROM (
                    SELECT content_cluster_id
                    FROM documents
                    GROUP BY content_cluster_id
                    HAVING COUNT(*) != MIN(content_cluster_size)
                       OR MIN(content_cluster_size) != MAX(content_cluster_size)
                  )
              """).fetchone()[0], 0)
        check("index documents without exact-content hashes",
              connection.execute(
                  "SELECT COUNT(*) FROM documents WHERE content_sha256 IS NULL "
                  "OR length(content_sha256) != 64").fetchone()[0], 0)
        connection.close()

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
