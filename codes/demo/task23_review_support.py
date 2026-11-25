"""Replay a conservative evidence selection rule at a fixed report budget."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from benchmark_task07 import sha256_file
from condition_retrieval import ALLOWED_CLAIMS, load_sources, offline_claims
from task07_retrieval_pilot import PILOT, REFERENCE, STATUS_ORDER, read_cases
from task13_evaluation import write_json
from task15_retrieval_comparison import BASELINE
from task17_report_context import build_ranked_report, prepare_experiment
from task21_report_coverage import coverage_rows, report_items, summarize
from task22_graph_backfill import BACKFILL, EXPANDED, PRIMARY, append_expanded_candidates

K = 3
REVIEW_SUPPORT = "kg_context_2hop_with_review_support"
LEXICAL_CONTEXT = "lexical_bm25_with_context_priority"
LEXICAL_REVIEW_SUPPORT = "lexical_bm25_with_review_support"
TARGET_FLAGS = {"RESISTANCE_ASSOCIATION_REVIEW", "RESISTANCE_CONTEXT_INCOMPLETE"}
SUPPORT_STATUSES = {"CONTEXT_MATCHED", "NEEDS_INFORMATION"}
REPLACEABLE_STATUSES = {"NOT_MATCHED", "NOT_EVALUATED"}


def select_with_review_support(
    primary: list[str], expanded: list[str], candidate_claims: dict[str, dict],
    *, applicability_limits: dict[str, set[str]] | None = None,
) -> tuple[list[str], list[dict]]:
    """Keep protected rows and sourced limits on currently displayed claims."""
    applicability_limits = applicability_limits or {}
    selected = primary[:K]
    decisions = []
    for claim_id in expanded:
        claim = candidate_claims[claim_id]
        if (claim["claim_type"] != "RESISTANCE_ASSOCIATION"
                or claim["context_status"] not in SUPPORT_STATUSES):
            continue
        decision = {"claim_id": claim_id, "context_status": claim["context_status"]}
        if not any(url.startswith("https://") for url in claim["source_urls"]):
            decision["action"] = "MISSING_SOURCE"
        elif claim_id in selected:
            decision["action"] = "ALREADY_VISIBLE"
        elif len(selected) < K:
            selected.append(claim_id)
            decision["action"] = "APPEND"
        else:
            replaceable = [i for i in reversed(range(K))
                           if candidate_claims[selected[i]]["context_status"] in REPLACEABLE_STATUSES]
            protected_limits = {
                selected[i]: sorted(applicability_limits[selected[i]].intersection(selected) - {selected[i]})
                for i in replaceable if selected[i] in applicability_limits
                and any(url.startswith("https://") for url in candidate_claims[selected[i]].get("source_urls", []))
            }
            protected_limits = {row: targets for row, targets in protected_limits.items() if targets}
            slot = next((i for i in replaceable if selected[i] not in protected_limits), None)
            if protected_limits:
                decision["protected_applicability_limits"] = protected_limits
            if slot is None:
                decision["action"] = "NO_REPLACEABLE_SLOT"
            else:
                decision.update(action="REPLACE", replaced_claim_id=selected[slot])
                selected[slot] = claim_id
        decisions.append(decision)
    return selected, decisions


def audit_items(report: dict) -> dict[str, set[tuple]]:
    items = report_items(report)
    # A single source set can support identical flags for multiple drug mentions.
    items["targeted_review_support"] = {
        (flag, supporting_claims)
        for _, flag, supporting_claims in items.pop("review_flags")
        if flag in TARGET_FLAGS
    }
    return items


def run_audit(rankings: dict, trusted: dict) -> dict:
    methods = (PRIMARY, EXPANDED, BACKFILL, REVIEW_SUPPORT, BASELINE, LEXICAL_CONTEXT, LEXICAL_REVIEW_SUPPORT)
    reports_by_method = {method: [] for method in methods}
    decisions_by_case = []
    lexical_decisions_by_case = []
    for case_id in sorted(trusted):
        primary, expanded = (rankings[method][case_id] for method in (PRIMARY, EXPANDED))
        lexical = rankings[BASELINE][case_id]
        backfill = append_expanded_candidates(primary, expanded)
        trusted_report = trusted[case_id]
        claims = {row["claim_id"]: row for row in trusted_report["evidence_claims"]}
        candidates = {claim_id: claims[claim_id] for claim_id in expanded}
        selected, decisions = select_with_review_support(primary, expanded, candidates)
        decisions_by_case.append({"case_id": case_id, "candidate_decisions": decisions,
                                  "ranking_changed": selected != primary[:K]})

        lexical_candidates = {claim_id: claims[claim_id] for claim_id in lexical}
        lexical_selected, lexical_decisions = select_with_review_support(lexical, lexical, lexical_candidates)
        lexical_context = sorted(lexical, key=lambda claim_id: STATUS_ORDER[lexical_candidates[claim_id]["context_status"]])
        lexical_decisions_by_case.append({"case_id": case_id, "candidate_decisions": lexical_decisions,
                                          "ranking_changed": lexical_selected != lexical[:K]})

        # Evaluate against the snapshot only after selection.
        reference = build_ranked_report(trusted_report, sorted(ALLOWED_CLAIMS), len(ALLOWED_CLAIMS),
                                        include_review_details=True)
        reference_items = audit_items(reference)
        orders = {PRIMARY: primary, EXPANDED: expanded, BACKFILL: backfill, REVIEW_SUPPORT: selected,
                  BASELINE: lexical, LEXICAL_CONTEXT: lexical_context, LEXICAL_REVIEW_SUPPORT: lexical_selected}
        for method, order in orders.items():
            report = build_ranked_report(trusted_report, order, K, include_review_details=True)
            reports_by_method[method].append({
                "case_id": case_id, "selected_claim_ids": order[:K],
                "coverage": coverage_rows(reference_items, audit_items(report)),
            })
    return {
        "k": K,
        "graph_decisions": decisions_by_case,
        "lexical_decisions": lexical_decisions_by_case,
        "methods": {method: {"summary": summarize(cases), "cases": cases}
                    for method, cases in reports_by_method.items()},
    }


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
            "execution_mode": "SAVED_RANKING_REPLAY",
            "coverage_reference": "FULL_LOCAL_SNAPSHOT_PROTOTYPE_OUTPUT",
            "case_count": len(trusted), "task15_report_sha256": hashlib.sha256(raw).hexdigest(),
            "oncokg_dataset_sha256": hashes, "pilot_sha256": pilot_hash,
            **run_audit(rankings, trusted),
        })
    except (OSError, KeyError, TypeError, ValueError) as error:
        parser.exit(1, f"STOP: {error}\n")


if __name__ == "__main__":
    main()
