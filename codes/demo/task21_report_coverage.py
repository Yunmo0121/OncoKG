"""Measure which details a ranked development report retains from the full snapshot."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from benchmark_task07 import sha256_file
from condition_retrieval import ALLOWED_CLAIMS, load_sources, offline_claims
from task07_retrieval_pilot import PILOT, REFERENCE, read_cases
from task13_evaluation import write_json
from task17_report_context import build_ranked_report, prepare_experiment


def report_items(report: dict) -> dict[str, set[tuple]]:
    return {
        "context_matched_claims": {(e["claim_id"],) for e in report["evidence"]
                                   if e["context_status"] == "CONTEXT_MATCHED"},
        "missing_checks": {(m["claim_id"], m["check"]) for m in report["missing_information"]},
        "supplemental_links": {(e["claim_id"], link["url"])
                               for e in report["evidence"] for link in e["supplemental_source_links"]},
        "review_flags": {(f["drug_mentioned_not_recommended"], f["flag"], tuple(sorted(f["supporting_claim_ids"])))
                         for f in report["research_review_flags"]},
    }


def coverage_rows(reference: dict, observed: dict) -> dict:
    details = {}
    for category, available in reference.items():
        retained = observed[category]
        if not retained <= available:
            raise ValueError(f"Ranked report introduced {category} outside the full snapshot.")
        details[category] = {"available": len(available), "retained": len(retained),
                             "omitted": sorted(available - retained)}
    return details


def summarize(cases: list[dict]) -> dict:
    result = {}
    for category in cases[0]["coverage"]:
        items = [case["coverage"][category] for case in cases]
        total = sum(i["available"] for i in items)
        kept = sum(i["retained"] for i in items)
        result[category] = {
            "available": total, "retained": kept, "retained_fraction": kept / total if total else None,
            "cases_with_omissions": sum(i["retained"] < i["available"] for i in items),
        }
    return result


def audit_coverage(rankings: dict, trusted: dict) -> dict:
    reference = {
        cid: report_items(build_ranked_report(report, sorted(ALLOWED_CLAIMS), len(ALLOWED_CLAIMS),
                                              include_review_details=True))
        for cid, report in trusted.items()
    }
    cutoffs = {}
    for k in range(1, len(ALLOWED_CLAIMS) + 1):
        arm_results = {}
        for method, orders in rankings.items():
            cases = []
            for cid in sorted(trusted):
                current = build_ranked_report(trusted[cid], orders[cid], k, include_review_details=True)
                cases.append({"case_id": cid, "coverage": coverage_rows(reference[cid], report_items(current))})
            arm_results[method] = {"summary": summarize(cases), "cases": cases}
        cutoffs[str(k)] = arm_results
    return cutoffs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rankings", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        raw = args.rankings.read_bytes()
        base, t790m, hashes = load_sources()
        pilot_hash = sha256_file(PILOT)
        rankings, trusted = prepare_experiment(json.loads(raw), read_cases(), offline_claims(base, t790m),
                                               hashes, pilot_hash)
        write_json(args.output, {
            "reference_type": REFERENCE, "official_evaluation": False,
            "coverage_reference": "FULL_LOCAL_SNAPSHOT_PROTOTYPE_OUTPUT",
            "case_count": len(trusted), "claim_count": len(ALLOWED_CLAIMS),
            "task15_report_sha256": hashlib.sha256(raw).hexdigest(),
            "oncokg_dataset_sha256": hashes, "pilot_sha256": pilot_hash,
            "cutoffs": audit_coverage(rankings, trusted),
        })
    except (OSError, KeyError, TypeError, ValueError) as error:
        parser.exit(1, f"STOP: {error}\n")


if __name__ == "__main__":
    main()
