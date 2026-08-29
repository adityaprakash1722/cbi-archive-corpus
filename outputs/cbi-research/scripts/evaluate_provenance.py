#!/usr/bin/env python3
"""Evaluate document authorship against a separately maintained human-labelled set."""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--minimum-accuracy", type=float, default=0.90)
    args = parser.parse_args()

    with args.gold.open(encoding="utf-8-sig", newline="") as stream:
        gold = list(csv.DictReader(stream))
    connection = sqlite3.connect(f"file:{args.database.resolve()}?mode=ro", uri=True)
    predicted = {
        sha: (authorship, confidence, basis)
        for sha, authorship, confidence, basis in connection.execute(
            "SELECT source_sha256, authorship, classification_confidence, "
            "classification_basis FROM documents")
    }
    connection.close()

    confusion: dict[str, Counter] = defaultdict(Counter)
    by_confidence: dict[str, Counter] = defaultdict(Counter)
    errors = []
    for row in gold:
        actual = predicted.get(row["source_sha256"])
        if not actual:
            errors.append({**row, "predicted": "missing", "confidence": "", "basis": ""})
            continue
        label, confidence, basis = actual
        correct = label == row["gold_authorship"]
        confusion[row["gold_authorship"]][label] += 1
        by_confidence[confidence]["correct" if correct else "wrong"] += 1
        if not correct:
            errors.append({**row, "predicted": label, "confidence": confidence, "basis": basis})

    accuracy = (len(gold) - len(errors)) / len(gold) if gold else 0
    payload = {
        "sample_design": "Deterministic pseudo-random SHA ordering, stratified across the v4 labels, "
                         "plus the discovered mixed composite and two audited non-consultation "
                         "stakeholder submissions. Labels were assigned by opening the text.",
        "documents": len(gold),
        "correct": len(gold) - len(errors),
        "accuracy": round(accuracy, 4),
        "confusion": {key: dict(value) for key, value in confusion.items()},
        "by_confidence": {key: dict(value) for key, value in by_confidence.items()},
        "errors": errors,
        "caution": "This small audit sample is an error detector, not a population accuracy estimate.",
    }
    print(json.dumps(payload, indent=2))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return 0 if accuracy >= args.minimum_accuracy and not any(
        error["predicted"] == "missing" for error in errors) else 1


if __name__ == "__main__":
    raise SystemExit(main())
