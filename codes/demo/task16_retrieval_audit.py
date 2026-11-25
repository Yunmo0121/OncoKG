"""Audit development rankings across cutoffs and leave-one-case-out subsets."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from benchmark_task07 import sha256_file
from condition_retrieval import ALLOWED_CLAIMS
from task07_retrieval_pilot import PILOT, REFERENCE, read_cases, summarize_rankings
from task13_evaluation import score_claim_ranking, write_json
from task15_retrieval_comparison import BASELINE, DENSE, FUSED

METHODS = (BASELINE, DENSE, FUSED, "kg_path_2hop", "kg_path_4hop",
           "kg_context_2hop", "kg_context_4hop")
COMPARISONS = (
    (BASELINE, FUSED),
    (BASELINE, "kg_context_2hop"),
    ("kg_path_2hop", "kg_context_2hop"),
    ("kg_path_2hop", "kg_path_4hop"),
    ("kg_context_2hop", "kg_context_4hop"),
)
METRICS = ("macro_precision_all_cases", "macro_recall_positive_cases", "mrr_positive_cases")


def index_rankings(rankings: dict, case_ids: set[str]) -> dict:
    if set(rankings) != set(METHODS):
        raise ValueError("Expected all seven Task 15 ranking methods.")
    indexed = {}
    for method in METHODS:
        indexed[method] = {}
        for row in rankings[method]:
            case_id, ids = row["case_id"], row["claim_ids"]
            if (case_id not in case_ids or case_id in indexed[method] or not isinstance(ids, list)
                    or len(ids) != len(set(ids)) or not set(ids) <= ALLOWED_CLAIMS):
                raise ValueError(f"Invalid ranking for {method}, case {case_id}.")
            indexed[method][case_id] = ids
        if indexed[method].keys() != case_ids:
            raise ValueError(f"Missing cases for {method}.")
    return indexed


def metric_deltas(baseline: dict, candidate: dict) -> dict:
    return {metric: candidate[metric] - baseline[metric]
            if baseline[metric] is not None and candidate[metric] is not None else None
            for metric in METRICS}


def compare_pair(left: str, right: str, rankings: dict, scores: dict,
                 summary: dict, k: int) -> dict:
    cases = sorted(scores[left])
    changes = []
    directions = Counter()
    for case_id in cases:
        before, after = rankings[left][case_id][:k], rankings[right][case_id][:k]
        delta = scores[right][case_id]["hits"] - scores[left][case_id]["hits"]
        directions[(delta > 0) - (delta < 0)] += 1
        if before != after:
            changes.append({
                "case_id": case_id, "before_top_k": before, "after_top_k": after,
                "hit_delta": delta, "added": [cid for cid in after if cid not in before],
                "removed": [cid for cid in before if cid not in after],
            })

    # Drop the same case from both systems to keep the comparison paired.
    omissions = {}
    for omitted in cases:
        if len(cases) > 1:
            a, b = (summarize_rankings([scores[method][cid] for cid in cases if cid != omitted])
                    for method in (left, right))
            omissions[omitted] = metric_deltas(a, b)
    ranges = {}
    for metric in METRICS:
        values = [row[metric] for row in omissions.values() if row[metric] is not None]
        ranges[metric] = {"min": min(values), "max": max(values)} if values else None

    return {
        "baseline": left, "candidate": right, "delta": metric_deltas(summary[left], summary[right]),
        "case_hit_direction": {"improved": directions[1], "tied": directions[0], "worsened": directions[-1]},
        "changed_top_k": changes, "leave_one_out_deltas": omissions, "leave_one_out_ranges": ranges,
    }


def audit(report: dict, known: list[dict], pilot_sha256: str) -> dict:
    if (report["reference_type"] != REFERENCE or report["official_evaluation"] is not False
            or report["pilot_sha256"] != pilot_sha256):
        raise ValueError("Expected the Task 15 report for the matching development fixture.")
    if type(report["k"]) is not int or not 1 <= report["k"] <= len(ALLOWED_CLAIMS):
        raise ValueError("Task 15 report cutoff is outside the claim inventory.")
    relevant = {entry["case"]["case_id"]: set(entry["matched_claim_ids"]) for entry in known}
    rankings = index_rankings(report["rankings"], set(relevant))
    cutoffs = {}
    for k in range(1, len(ALLOWED_CLAIMS) + 1):
        scores = {method: {cid: score_claim_ranking(order, relevant[cid], k)
                           for cid, order in cases.items()}
                  for method, cases in rankings.items()}
        summary = {method: summarize_rankings(list(cases.values())) for method, cases in scores.items()}
        if k == report["k"] and summary != report["metrics"]:
            raise ValueError("Recomputed metrics differ from the Task 15 report.")
        cutoffs[str(k)] = {
            "metrics": summary,
            "short_rank_lists": {method: sum(item["retrieved"] < k for item in rows.values())
                                 for method, rows in scores.items()},
            "paired_comparisons": [compare_pair(a, b, rankings, scores, summary, k)
                                   for a, b in COMPARISONS],
        }
    return {"reference_type": REFERENCE, "official_evaluation": False, "pilot_sha256": pilot_sha256,
            "case_count": len(relevant), "claim_count": len(ALLOWED_CLAIMS),
            "oncokg_dataset_sha256": report["oncokg_dataset_sha256"], "cutoffs": cutoffs}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True, help="Task 15 development JSON report.")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        raw = args.report.read_bytes()
        result = audit(json.loads(raw), read_cases(), sha256_file(PILOT))
        result["task15_report_sha256"] = hashlib.sha256(raw).hexdigest()
        write_json(args.output, result)
    except (OSError, KeyError, TypeError, ValueError) as error:
        parser.exit(1, f"STOP: {error}\n")


if __name__ == "__main__":
    main()
