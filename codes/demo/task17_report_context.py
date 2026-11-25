"""Build bounded, local mock evidence reports from Task 15 development rankings."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from benchmark_task07 import sha256_file
from condition_retrieval import ALLOWED_CLAIMS, evaluate, load_sources, offline_claims
from mock_report import build_mock_report
from safety_triage import evidence_triage
from task07_retrieval_pilot import PILOT, REFERENCE, read_cases
from task08_multihop import supplemental_source_links
from task13_evaluation import write_json
from task16_retrieval_audit import index_rankings


def build_ranked_report(trusted: dict, ranking: list[str], k: int, *, include_review_details: bool = False) -> dict:
    claims = {row["claim_id"]: row for row in trusted["evidence_claims"]}
    retrieved = ranking[:k]
    evidence = [
        {field: claims[cid][field] for field in (
            "claim_id", "claim_type", "context_status", "status_explanation",
            "source_urls", "review_status",
        )}
        for cid in retrieved
    ]
    missing = [item for item in trusted["missing_information"] if item["claim_id"] in retrieved]
    counts = Counter(row["context_status"] for row in evidence)
    lines = [f"{row['claim_id']}: {row['status_explanation']} Sources: {', '.join(row['source_urls'])}"
             for row in evidence]
    lines.extend(f"{item['claim_id']}: {item['check']}" for item in missing)
    if not evidence:
        lines.append("No evidence was retrieved for this synthetic case.")
    elif not counts["CONTEXT_MATCHED"]:
        lines.append("The retrieved evidence did not establish a context match within this snapshot.")
    report = {
        "case_id": trusted["case_id"], "synthetic": True, "research_only": True,
        "generation_mode": "DETERMINISTIC_MOCK_NO_LLM", "llm_api_called": False,
        "evidence": evidence, "missing_information": missing, "summary_lines": lines,
        "status_counts": dict(counts), "limitations": trusted["limitations"],
        "treatment_recommendations": [], "automatic_exclusions": [], "safety_clearances": [],
        "disclaimer": trusted["disclaimer"],
    }
    if include_review_details:
        for row in evidence:
            row["supplemental_source_links"] = supplemental_source_links(row["claim_id"], row["source_urls"])
        report["research_review_flags"] = [
            flag for flag in trusted["safety_evidence_flags"]
            if flag["supporting_claim_ids"] and set(flag["supporting_claim_ids"]).issubset(retrieved)
        ]
        report["review_scope"] = "RETRIEVED_SUPPORT_ONLY"
    return report


def run_experiment(ranking_report: dict, known: list[dict], graph_rows: list[dict],
                   hashes: dict, pilot_hash: str, k: int, *, include_review_details: bool = False) -> dict:
    rankings, trusted = prepare_experiment(ranking_report, known, graph_rows, hashes, pilot_hash)
    methods = {}
    for method, orders in rankings.items():
        reports = [build_ranked_report(trusted[cid], orders[cid], k, include_review_details=include_review_details)
                   for cid in sorted(trusted)]
        methods[method] = {
            "retrieved_claim_slots": sum(len(report["evidence"]) for report in reports),
            "cases_with_context_match": sum(bool(r["status_counts"].get("CONTEXT_MATCHED")) for r in reports),
            "cases_with_missing_information": sum(bool(r["missing_information"]) for r in reports),
            "reports": reports,
        }
    return {
        "reference_type": REFERENCE, "official_evaluation": False, "k": k,
        "case_count": len(trusted), "oncokg_dataset_sha256": hashes,
        "pilot_sha256": pilot_hash, "methods": methods,
    }


def prepare_experiment(ranking_report: dict, known: list[dict], graph_rows: list[dict],
                       hashes: dict, pilot_hash: str) -> tuple[dict, dict]:
    if (ranking_report["reference_type"] != REFERENCE
            or ranking_report["official_evaluation"] is not False
            or ranking_report["pilot_sha256"] != pilot_hash
            or ranking_report["oncokg_dataset_sha256"] != hashes):
        raise ValueError("Task 15 case or evidence snapshot does not match the local inputs.")
    cases = {entry["case"]["case_id"]: entry["case"] for entry in known}
    rankings = index_rankings(ranking_report["rankings"], set(cases))
    trusted = {}
    for cid, case in cases.items():
        context = evaluate(case, graph_rows, "offline_curated_json_graph_shaped")
        trusted[cid] = build_mock_report(case, context, evidence_triage(case, context))
    return rankings, trusted


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--k", type=int, choices=range(1, len(ALLOWED_CLAIMS) + 1), default=3)
    parser.add_argument("--include-review-details", action="store_true",
                        help="Add Task 18 supplemental provenance and retrieval-scoped research flags.")
    args = parser.parse_args()
    try:
        raw = args.report.read_bytes()
        base, t790m, hashes = load_sources()
        result = run_experiment(json.loads(raw), read_cases(), offline_claims(base, t790m),
                                hashes, sha256_file(PILOT), args.k,
                                include_review_details=args.include_review_details)
        result["task15_report_sha256"] = hashlib.sha256(raw).hexdigest()
        write_json(args.output, result)
    except (OSError, KeyError, TypeError, ValueError) as error:
        parser.exit(1, f"STOP: {error}\n")


if __name__ == "__main__":
    main()
