"""Read immutable Hugging Face coordinates from RELEASE.lock.json."""
from __future__ import annotations

import json
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "RELEASE.lock.json"


def load() -> dict:
    return json.loads(PATH.read_text(encoding="utf-8"))
