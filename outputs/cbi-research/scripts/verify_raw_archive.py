#!/usr/bin/env python3
"""Hash every unique downloaded source, including structured and excluded files."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--progress-every", type=int, default=500)
    args = parser.parse_args()
    archive = args.archive.resolve()
    with (archive / "manifests" / "files.csv").open(
            encoding="utf-8-sig", newline="") as stream:
        downloaded = [row for row in csv.DictReader(stream)
                      if row.get("status") == "downloaded"]
    unique: dict[str, dict] = {}
    for row in downloaded:
        unique.setdefault(row["sha256"], row)

    failures = []
    checked_bytes = 0
    started = time.monotonic()
    for index, (sha, row) in enumerate(sorted(unique.items()), 1):
        path = archive / row["localPath"].replace("\\", "/")
        if not path.is_file():
            failures.append({"sha256": sha, "check": "missing", "path": str(path)})
            continue
        size = path.stat().st_size
        want_size = int(row.get("downloadedBytes") or 0)
        if size != want_size:
            failures.append({"sha256": sha, "check": "size",
                             "path": str(path), "got": size, "want": want_size})
            continue
        got = sha256_file(path)
        checked_bytes += size
        if got != sha:
            failures.append({"sha256": sha, "check": "sha256",
                             "path": str(path), "got": got, "want": sha})
        if index % args.progress_every == 0:
            print(f"  {index}/{len(unique)} files, failures={len(failures)}", flush=True)

    args.output.mkdir(parents=True, exist_ok=True)
    summary = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "download_records": len(downloaded),
        "unique_downloaded_files": len(unique),
        "bytes_hashed": checked_bytes,
        "failures": len(failures),
        "passed": not failures,
        "scope": "every unique downloaded hash, including structured and excluded objects",
        "elapsed_seconds": round(time.monotonic() - started, 2),
    }
    (args.output / "raw-archive-validation.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    (args.output / "raw-archive-validation-failures.json").write_text(
        json.dumps(failures, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(summary, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
