"""Read the repository's immutable published-release coordinates."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PATH = ROOT / "RELEASE.lock.json"


def load() -> dict:
    return json.loads(PATH.read_text(encoding="utf-8"))


def corpus_revision() -> str:
    return load()["hugging_face"]["corpus_revision"]


def raw_revision() -> str:
    return load()["hugging_face"]["raw_revision"]


def corpus_repo() -> str:
    return load()["hugging_face"]["corpus_repo"]
