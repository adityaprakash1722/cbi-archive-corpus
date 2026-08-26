#!/usr/bin/env python3
"""Lay out the raw archive by content hash, ready to publish.

    python publish\\build_blob_tree.py

Why re-lay it out at all
------------------------
The crawler stored one file per URL, under a path mirroring the website. That
has two problems for publishing:

  1. 654 files are byte-identical content served at more than one URL, so the
     archive carries 0.92 GB of pure duplication.
  2. The paths are long, deeply nested and contain the `_long` directories the
     crawler invented to survive Windows path limits. They are meaningless to
     anyone else.

Addressing files by their SHA-256 fixes both. Duplicates collapse to one object
automatically, every file is independently verifiable, and `documents.parquet`
already carries `source_sha256`, so any row in the published corpus resolves to
its original document with no extra lookup table.

Disk cost
---------
Zero. This creates hard links, which are additional directory entries pointing at
the same bytes on disk, not copies. If hard links are unavailable, for example
across two drives, it falls back to copying and tells you.
"""
from __future__ import annotations

import argparse, csv, json, os, shutil, sys, time
from collections import Counter
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", type=Path,
                    default=Path("outputs/cbi-archive/cbi-data"))
    ap.add_argument("--output", type=Path, default=Path("publish/blobs"))
    ap.add_argument("--limit", type=int, default=0, help="stop after N files, for testing")
    args = ap.parse_args()

    archive = args.archive.resolve()
    manifest_path = archive / "manifests" / "files.csv"
    if not manifest_path.is_file():
        print(f"cannot find {manifest_path}")
        return 1

    csv.field_size_limit(1 << 27)
    with manifest_path.open(encoding="utf-8-sig", newline="") as stream:
        rows = [r for r in csv.DictReader(stream) if r["status"] == "downloaded"]

    # One entry per unique content hash. Keep every URL that served it, because
    # the aliases are part of the provenance and someone will want them.
    unique: dict[str, dict] = {}
    for row in sorted(rows, key=lambda r: r["url"]):
        entry = unique.setdefault(row["sha256"], {
            "sha256": row["sha256"], "format": row["format"].upper(),
            "bytes": int(row["downloadedBytes"] or 0),
            "local_path": row["localPath"], "urls": [],
            "content_type": row.get("contentType", ""),
            "dataset_title": row.get("datasetTitle", ""),
        })
        entry["urls"].append(row["url"])

    print(f"{len(rows)} download records -> {len(unique)} unique files")
    duplicated = len(rows) - len(unique)
    saved = sum(int(r["downloadedBytes"] or 0) for r in rows) - sum(e["bytes"] for e in unique.values())
    print(f"{duplicated} duplicate copies dropped, {saved/1e9:.2f} GB saved\n")

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    entries = list(unique.values())
    if args.limit:
        entries = entries[: args.limit]

    linked = copied = missing = existing = 0
    started = time.time()
    catalog = []
    for index, entry in enumerate(entries, 1):
        sha = entry["sha256"]
        source = archive / entry["local_path"].replace("\\", "/")
        suffix = Path(entry["local_path"]).suffix.lower() or f".{entry['format'].lower()}"
        # The key is the path inside the Hugging Face repository, and there the
        # files sit at the root: `hf upload <repo> publish/blobs .` uploads this
        # directory's *contents*. Writing "blobs/..." here would put a prefix in
        # the catalogue that does not exist in the published dataset, which is
        # exactly the mismatch that broke retrieval once already.
        key = f"{sha[:2]}/{sha[2:4]}/{sha}{suffix}"
        destination = output / key

        if not source.is_file():
            missing += 1
            continue
        if destination.is_file():
            existing += 1
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.link(source, destination)
                linked += 1
            except OSError:
                shutil.copy2(source, destination)
                copied += 1

        catalog.append({
            "sha256": sha, "key": key, "format": entry["format"],
            "bytes": entry["bytes"], "url_count": len(entry["urls"]),
            "canonical_url": entry["urls"][0],
            "all_urls": " | ".join(entry["urls"]),
            "dataset_title": entry["dataset_title"],
        })
        if index % 500 == 0:
            print(f"  {index}/{len(entries)}  {time.time()-started:.0f}s", flush=True)

    fields = ["sha256", "key", "format", "bytes", "url_count", "canonical_url",
              "all_urls", "dataset_title"]
    catalog_path = output.parent / "blob-catalog.csv"
    with catalog_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(catalog)

    total = sum(c["bytes"] for c in catalog)
    summary = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "download_records": len(rows),
        "unique_files": len(unique),
        "duplicate_copies_dropped": duplicated,
        "bytes_saved_by_dedupe": saved,
        "files_laid_out": len(catalog),
        "total_bytes": total,
        "by_format": dict(Counter(c["format"] for c in catalog).most_common()),
        "hard_linked": linked, "copied": copied,
        "already_present": existing, "source_missing": missing,
        "layout": "<sha[0:2]>/<sha[2:4]>/<sha256><ext>",
        "elapsed_seconds": round(time.time() - started, 1),
    }
    (output.parent / "blob-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print("\n" + json.dumps(summary, indent=2))
    if copied:
        print(f"\nNOTE: {copied} files were copied rather than hard linked, so this")
        print(f"cost about {sum(c['bytes'] for c in catalog)/1e9:.1f} GB of extra disk.")
    if missing:
        print(f"\nWARNING: {missing} files listed in the manifest were not on disk.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
