#!/usr/bin/env python3
"""Put your Hugging Face username into the placeholder spots.

The dataset card, the root README and the Makefile all contain example commands
with a `<user>` placeholder. Those examples are the first thing anyone reads, so
a wrong one is worse than none. Run this once, before uploading:

    python publish\\set-username.py your-hf-username
"""
import sys
from pathlib import Path

# "YOUR_USERNAME" is here because it is the obvious thing to type literally when
# a walkthrough says YOUR_USERNAME. Including it makes this script recoverable
# rather than one-shot.
TARGETS = {
    "publish/hf/README.md": ["<user>", "YOUR_USERNAME"],
    "README.md": ["<user>", "YOUR_USERNAME"],
    "Makefile": ["your-username", "YOUR_USERNAME"],
}

def main() -> int:
    if len(sys.argv) != 2 or "/" in sys.argv[1]:
        print("usage: python publish/set-username.py your-hf-username")
        print("  Use your ACTUAL username. Find it with:  hf auth whoami")
        return 2
    username = sys.argv[1].strip()
    if username.upper() in {"YOUR_USERNAME", "YOUR_HF_USERNAME", "USERNAME"}:
        print(f"'{username}' is the placeholder, not a username.")
        print("Find your real one with:  hf auth whoami")
        return 2
    root = Path(__file__).resolve().parent.parent
    changed = 0
    for relative, placeholders in TARGETS.items():
        path = root / relative
        if not path.is_file():
            print(f"  skip    {relative} (not found)")
            continue
        text = original = path.read_text(encoding="utf-8")
        for placeholder in placeholders:
            text = text.replace(placeholder, username)
        if text != original:
            path.write_text(text, encoding="utf-8", newline="\n")
            hits = sum(original.count(p) for p in placeholders)
            print(f"  updated {relative}  ({hits} replacements)")
            changed += 1
        else:
            print(f"  no change needed in {relative}")
    print(f"\n{changed} files updated. Your dataset will live at:")
    print(f"  https://huggingface.co/datasets/{username}/cbi-archive-corpus")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
