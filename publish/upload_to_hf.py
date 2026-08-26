#!/usr/bin/env python3
"""Upload the dataset without needing the `hf` command on PATH.

The huggingface_hub package installs an `hf.exe` launcher, but Microsoft Store
Python puts it in a directory Windows does not search. This script calls the same
library directly, so PATH is irrelevant.

    python publish\\upload_to_hf.py YOUR_USERNAME

It asks for your token if you have not logged in already.
"""
from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2 or "/" in sys.argv[1]:
        print("usage: python publish/upload_to_hf.py YOUR_HF_USERNAME")
        print("  (just the username, not username/dataset-name)")
        return 2
    username = sys.argv[1].strip()
    repo_id = f"{username}/cbi-archive-corpus"

    try:
        from huggingface_hub import HfApi, login
        from huggingface_hub.errors import HfHubHTTPError
    except ImportError:
        print("huggingface_hub is not installed. Run:")
        print("  pip install -U huggingface_hub")
        return 1

    folder = Path(__file__).resolve().parent / "hf"
    if not folder.is_dir():
        print(f"cannot find {folder}")
        return 1
    files = sorted(p for p in folder.rglob("*") if p.is_file())
    total = sum(p.stat().st_size for p in files)
    print(f"uploading {len(files)} files, {total/1e6:.1f} MB, to {repo_id}\n")
    for p in files:
        print(f"  {p.stat().st_size/1e6:8.1f} MB  {p.relative_to(folder).as_posix()}")

    api = HfApi()
    try:
        who = api.whoami()
        print(f"\nlogged in as {who['name']}")
    except Exception:
        print("\nNot logged in yet.")
        print("Get a WRITE token at https://huggingface.co/settings/tokens")
        print("Paste it below. Nothing will appear on screen as you paste; that is normal.")
        login()
        who = api.whoami()
        print(f"logged in as {who['name']}")

    if who["name"] != username:
        print(f"\nWARNING: you are logged in as '{who['name']}' but asked to upload to '{username}'.")
        if input("continue anyway? [y/N] ").strip().lower() != "y":
            return 1

    try:
        api.create_repo(repo_id=repo_id, repo_type="dataset", exist_ok=True)
        print(f"\nrepository ready: https://huggingface.co/datasets/{repo_id}")
        api.upload_folder(
            folder_path=str(folder),
            repo_id=repo_id,
            repo_type="dataset",
            commit_message="Central Bank of Ireland public archive corpus",
        )
    except HfHubHTTPError as exc:
        print(f"\nupload failed: {exc}")
        if "401" in str(exc) or "403" in str(exc):
            print("\nThat is almost certainly a READ token. You need a WRITE token.")
            print("Make one at https://huggingface.co/settings/tokens, then delete the")
            print("cached one and try again:")
            print("  python -c \"from huggingface_hub import logout; logout()\"")
        return 1

    print(f"\nDone. Open https://huggingface.co/datasets/{repo_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
