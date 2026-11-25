"""Freeze a completed OncoKG review and score evidence rankings against it."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from benchmark_task07 import sha256_file
from task07_retrieval_pilot import score_ranking, summarize_rankings
from task12_adjudication import LABELS, OUTPUT_FIELDS, compare_annotations, read_annotations, read_packet

FINAL_FIELDS = ("final_label", "final_reason", "final_source_location")
FINAL_LABELS = LABELS | {"UNRESOLVED"}
FROZEN_STATUS = "FROZEN_ADJUDICATED_REFERENCE"


def score_claim_ranking(ranking: list[str], relevant: set[str], k: int) -> dict:
    if ranking:
        row = score_ranking(ranking, relevant, k)
    else:
        missing = 0.0 if relevant else None
        row = {"hits": 0, "retrieved": 0, "recall": missing, "reciprocal_rank": missing}
    return {**row, "precision": row["hits"] / k}


def freeze_reference(packet: Path, reviewer_a: Path, reviewer_b: Path, adjudication: Path) -> dict:
    if reviewer_a.samefile(reviewer_b):
        raise ValueError("Supply two separate reviewer files.")
    manifest, keys = read_packet(packet)
    expected_keys = set(keys)
    left, right = (read_annotations(path, expected_keys) for path in (reviewer_a, reviewer_b))
    _, original_rows = compare_annotations(keys, left, right)
    originals = {(row["case_id"], row["claim_id"]): row for row in original_rows}
    final_rows = {}

    with adjudication.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file, strict=True)
        if tuple(reader.fieldnames or ()) != OUTPUT_FIELDS:
            raise ValueError("Use the Task 12 adjudication worksheet columns.")
        for row in reader:
            if None in row or None in row.values():
                raise ValueError(f"Malformed adjudication row near line {reader.line_num}.")
            key = (row["case_id"], row["claim_id"])
            if key not in originals or key in final_rows:
                raise ValueError(f"Unknown or duplicate adjudication pair: {key}.")
            if any(row[field] != originals[key][field] for field in OUTPUT_FIELDS if field not in FINAL_FIELDS):
                raise ValueError(f"Original review or status was edited for {key}.")
            label, reason, location = (row[field].strip() for field in FINAL_FIELDS)
            if label not in FINAL_LABELS or not reason or not location:
                raise ValueError(f"Complete the final label, reason and source location for {key}.")
            final_rows[key] = {"case_id": key[0], "claim_id": key[1], "label": label,
                               "reason": reason, "source_location": location}

    if final_rows.keys() != expected_keys:
        raise ValueError(f"Missing adjudication pairs: {sorted(expected_keys - final_rows.keys())}.")
    labels = Counter(row["label"] for row in final_rows.values())
    return {
        "review_set_id": manifest["review_set_id"], "reference_status": FROZEN_STATUS,
        "packet_manifest_sha256": sha256_file(packet / "manifest.json"),
        "case_fixture_sha256": manifest["case_fixture_sha256"],
        "oncokg_dataset_sha256": manifest["oncokg_dataset_sha256"],
        "reviewer_csv_sha256": {"a": sha256_file(reviewer_a), "b": sha256_file(reviewer_b)},
        "adjudication_csv_sha256": sha256_file(adjudication),
        "label_counts": dict(labels), "annotations": [final_rows[key] for key in keys],
    }


def evaluate_rankings(reference: dict, predictions: dict, reference_hash: str, k: int) -> dict:
    if reference["reference_status"] != FROZEN_STATUS:
        raise ValueError("Scoring requires a frozen adjudicated reference.")
    if predictions["reference_sha256"] != reference_hash:
        raise ValueError("The ranking file names a different reference hash.")
    snapshot_key = "oncokg_dataset_sha256"
    if (snapshot_key in reference and snapshot_key in predictions
            and predictions[snapshot_key] != reference[snapshot_key]):
        raise ValueError("The ranking file uses a different evidence snapshot.")
    if not isinstance(predictions["system_id"], str) or not predictions["system_id"].strip():
        raise ValueError("The ranking file requires a nonempty system_id.")

    labels_by_case = defaultdict(dict)
    expected_claims = {row["claim_id"] for row in reference["annotations"]}
    for row in reference["annotations"]:
        labels = labels_by_case[row["case_id"]]
        if row["label"] not in FINAL_LABELS or row["claim_id"] in labels:
            raise ValueError("Invalid label or duplicate reference annotation.")
        labels[row["claim_id"]] = row["label"]
    if not labels_by_case or any(labels.keys() != expected_claims for labels in labels_by_case.values()):
        raise ValueError("A frozen reference must cover each case/claim pair once.")
    if not 1 <= k <= len(expected_claims):
        raise ValueError("k must be within the frozen claim inventory.")

    by_case = {}
    for row in predictions["cases"]:
        case_id, ranking = row["case_id"], row["claim_ids"]
        if case_id not in labels_by_case or case_id in by_case:
            raise ValueError(f"Unknown or duplicate prediction case: {case_id}.")
        if (not isinstance(ranking, list) or len(ranking) != len(set(ranking))
                or not set(ranking) <= expected_claims):
            raise ValueError(f"Invalid, duplicate or unknown claims in ranking for {case_id}.")
        by_case[case_id] = ranking
    if by_case.keys() != labels_by_case.keys():
        raise ValueError("Rankings must include every case, with [] for no results.")

    results, excluded = [], []
    for case_id, labels in sorted(labels_by_case.items()):
        if "UNRESOLVED" in labels.values():
            excluded.append(case_id)
            continue
        relevant = {claim_id for claim_id, label in labels.items() if label == "CONTEXT_MATCHED"}
        results.append({"case_id": case_id, **score_claim_ranking(by_case[case_id], relevant, k)})

    return {
        "review_set_id": reference["review_set_id"], "reference_sha256": reference_hash,
        "system_id": predictions["system_id"], "k": k,
        "total_cases": len(labels_by_case), "scored_cases": len(results),
        "excluded_unresolved_case_ids": excluded,
        "metrics": summarize_rankings(results) if results else None, "cases": results,
    }


def write_json(path: Path, content: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as file:
        json.dump(content, file, indent=2, sort_keys=True)
        file.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    freeze = commands.add_parser("freeze", help="Verify and freeze a completed adjudication worksheet.")
    for name in ("packet-dir", "reviewer-a", "reviewer-b", "adjudication", "output"):
        freeze.add_argument("--" + name, type=Path, required=True)
    score = commands.add_parser("score", help="Score a system's ranked Claim IDs.")
    for name in ("reference", "predictions", "output"):
        score.add_argument("--" + name, type=Path, required=True)
    score.add_argument("--k", type=int, default=3)
    args = parser.parse_args()
    try:
        if args.command == "freeze":
            result = freeze_reference(args.packet_dir, args.reviewer_a, args.reviewer_b, args.adjudication)
        else:
            raw_reference = args.reference.read_bytes()
            raw_predictions = args.predictions.read_bytes()
            result = evaluate_rankings(json.loads(raw_reference), json.loads(raw_predictions),
                                       hashlib.sha256(raw_reference).hexdigest(), args.k)
            result["predictions_sha256"] = hashlib.sha256(raw_predictions).hexdigest()
        write_json(args.output, result)
    except (KeyError, OSError, TypeError, ValueError, csv.Error) as error:
        parser.exit(1, f"STOP: {error}\n")


if __name__ == "__main__":
    main()
