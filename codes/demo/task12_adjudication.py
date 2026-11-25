"""Compare two OncoKG reviewer CSVs and prepare a blank adjudication worksheet."""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from benchmark_task07 import sha256_file
from task11_review_pack import ANNOTATION_FIELDS, write_csv

LABELS = {"CONTEXT_MATCHED", "NOT_MATCHED", "NEEDS_INFORMATION", "NOT_EVALUATED"}
REVIEW_FIELDS = ANNOTATION_FIELDS[2:]
OUTPUT_FIELDS = (*ANNOTATION_FIELDS[:2], "status",
                 *(f"{reviewer}_{field}" for reviewer in ("a", "b") for field in REVIEW_FIELDS),
                 "final_label", "final_reason", "final_source_location")
PACKET_FILES = ("annotation.csv", "cases.csv", "sources.csv", "README.md")


def read_annotations(path: Path, expected_keys: set[tuple[str, str]] | None = None) -> dict:
    annotations = {}
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file, strict=True)
        if (reader.fieldnames is None or len(reader.fieldnames) != len(ANNOTATION_FIELDS)
                or set(reader.fieldnames) != set(ANNOTATION_FIELDS)):
            raise ValueError(f"{path.name} must use the original annotation columns.")
        for row in reader:
            if None in row or None in row.values():
                raise ValueError(f"Malformed CSV row in {path.name} near line {reader.line_num}.")
            key = (row["case_id"], row["claim_id"])
            if not all(key) or (expected_keys is not None and key not in expected_keys):
                raise ValueError(f"Unknown case/claim pair in {path.name}: {key}")
            if key in annotations:
                raise ValueError(f"Duplicate case/claim pair in {path.name}: {key}")
            label = row["label"].strip()
            if label and label not in LABELS:
                raise ValueError(f"Invalid label in {path.name} for {key}.")
            if label and not all(row[field].strip() for field in ("reason", "source_location")):
                raise ValueError(f"A completed label requires a reason and source location in {path.name} for {key}.")
            annotations[key] = {field: row[field] for field in REVIEW_FIELDS}
    return annotations


def read_packet(directory: Path) -> tuple[dict, list[tuple[str, str]]]:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    for name in PACKET_FILES:
        if sha256_file(directory / name) != manifest["files_sha256"][name]:
            raise ValueError(f"Reviewer packet checksum mismatch: {name}")
    if manifest["reference_status"] != "AWAITING_INDEPENDENT_ANNOTATION":
        raise ValueError("Expected the original unlabelled Task 11 reviewer packet.")
    template = read_annotations(directory / "annotation.csv")
    case_ids = {case_id for case_id, _ in template}
    claim_ids = {claim_id for _, claim_id in template}
    if (any(any(row.values()) for row in template.values())
            or len(template) != manifest["annotation_rows"]
            or len(case_ids) != manifest["case_count"] or len(claim_ids) != manifest["claim_count"]
            or len(template) != len(case_ids) * len(claim_ids)):
        raise ValueError("The original template must cover each case and claim once with blank labels.")
    return manifest, list(template)


def compare_annotations(keys: list[tuple[str, str]], left: dict, right: dict) -> tuple[dict, list[dict]]:
    counts = Counter()
    rows = []
    for case_id, claim_id in keys:
        key = (case_id, claim_id)
        a, b = left.get(key, {}), right.get(key, {})
        a_label, b_label = a.get("label", "").strip(), b.get("label", "").strip()
        if a_label and b_label:
            status = "AGREE" if a_label == b_label else "DISAGREE"
        elif a_label:
            status = "MISSING_B"
        elif b_label:
            status = "MISSING_A"
        else:
            status = "MISSING_BOTH"
        counts[status] += 1
        rows.append({
            "case_id": case_id, "claim_id": claim_id, "status": status,
            **{f"{name}_{field}": review.get(field, "")
               for name, review in (("a", a), ("b", b)) for field in REVIEW_FIELDS},
            "final_label": "", "final_reason": "", "final_source_location": "",
        })

    paired = counts["AGREE"] + counts["DISAGREE"]
    summary = {
        "expected_pair_count": len(keys), "paired_label_count": paired,
        "exact_agreement": counts["AGREE"] / paired if paired else None,
        "status_counts": {status: counts[status]
                          for status in ("AGREE", "DISAGREE", "MISSING_A", "MISSING_B", "MISSING_BOTH")},
    }
    return summary, rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet-dir", type=Path, required=True, help="Original unpacked Task 11 packet.")
    parser.add_argument("--reviewer-a", type=Path, required=True)
    parser.add_argument("--reviewer-b", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.reviewer_a.samefile(args.reviewer_b):
            raise ValueError("Supply two separate reviewer files.")
        manifest, keys = read_packet(args.packet_dir)
        left, right = (read_annotations(path, set(keys)) for path in (args.reviewer_a, args.reviewer_b))
        summary, rows = compare_annotations(keys, left, right)
        summary.update({
            "review_set_id": manifest["review_set_id"],
            "reference_status": "PENDING_ADJUDICATION",
            "packet_manifest_sha256": sha256_file(args.packet_dir / "manifest.json"),
            "reviewer_csv_sha256": {"a": sha256_file(args.reviewer_a), "b": sha256_file(args.reviewer_b)},
        })
        args.output_dir.mkdir(parents=True, exist_ok=False)
        write_csv(args.output_dir / "adjudication.csv", OUTPUT_FIELDS, rows)
        (args.output_dir / "agreement.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"Prepared worksheet for {len(rows)} case/claim pairs; {summary['paired_label_count']} jointly labelled.")
    except (KeyError, OSError, ValueError, csv.Error) as error:
        parser.exit(1, f"STOP: {error}\n")


if __name__ == "__main__":
    main()
