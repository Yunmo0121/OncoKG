"""Replay two-hop context rankings with four-hop backfill for short lists."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from benchmark_task07 import sha256_file
from condition_retrieval import load_sources, offline_claims
from task07_retrieval_pilot import PILOT, REFERENCE, read_cases
from task13_evaluation import write_json
from task17_report_context import prepare_experiment
from task21_report_coverage import audit_coverage

PRIMARY = "kg_context_2hop"
EXPANDED = "kg_context_4hop"
BACKFILL = "kg_context_2hop_then_4hop"


def append_expanded_candidates(primary: list[str], expanded: list[str]) -> list[str]:
    seen = set(primary)
    if not seen.issubset(expanded):
        raise ValueError("The four-hop candidate set must contain the two-hop candidates.")
    return primary + [claim for claim in expanded if claim not in seen]


def audit_backfill(rankings: dict, trusted: dict) -> dict:
    combined = {cid: append_expanded_candidates(order, rankings[EXPANDED][cid])
                for cid, order in rankings[PRIMARY].items()}
    coverage = audit_coverage({
        PRIMARY: rankings[PRIMARY], EXPANDED: rankings[EXPANDED], BACKFILL: combined,
    }, trusted)
    cutoffs = {}
    for cutoff, results in coverage.items():
        k = int(cutoff)
        additions = []
        for cid in sorted(combined):
            primary = rankings[PRIMARY][cid][:k]
            proposed = combined[cid][:k]
            if proposed != primary:
                additions.append({"case_id": cid, "two_hop_prefix": primary,
                                  "appended_claim_ids": proposed[len(primary):]})
        cutoffs[cutoff] = {
            "cases_using_backfill": len(additions),
            "appended_claim_count": sum(len(row["appended_claim_ids"]) for row in additions),
            "additions": additions,
            "coverage": results,
        }
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
            "execution_mode": "SAVED_RANKING_REPLAY", "case_count": len(trusted),
            "task15_report_sha256": hashlib.sha256(raw).hexdigest(),
            "oncokg_dataset_sha256": hashes, "pilot_sha256": pilot_hash,
            "cutoffs": audit_backfill(rankings, trusted),
        })
    except (OSError, KeyError, TypeError, ValueError) as error:
        parser.exit(1, f"STOP: {error}\n")


if __name__ == "__main__":
    main()
