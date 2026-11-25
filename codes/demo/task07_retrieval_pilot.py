"""Compare evidence-claim ranking and resistance-review flag coverage without an LLM."""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path
from statistics import mean

from benchmark_task07 import sha256_file
from condition_retrieval import (
    ALLOWED_CLAIMS, BASE_FILE, CASES_FILE, ROOT, T790M_FILE,
    evaluate, load_sources, offline_claims, validate_case,
)
from safety_triage import evidence_triage

PILOT = ROOT / "data/benchmarks/task07_retrieval_pilot_v0_1.json"
REFERENCE = "developer_annotated_synthetic_pilot_pending_independent_review"
STATUS_ORDER = {
    "CONTEXT_MATCHED": 0, "NEEDS_INFORMATION": 1, "NOT_EVALUATED": 2, "NOT_MATCHED": 3,
}


def read_cases(path: Path = PILOT) -> list[dict]:
    pilot = json.loads(path.read_text(encoding="utf-8"))
    if pilot["reference_type"] != REFERENCE or not pilot["cases"]:
        raise ValueError("Expected a nonempty developer-annotated synthetic pilot.")
    dev_cases = json.loads(CASES_FILE.read_text(encoding="utf-8"))["cases"]
    seen_ids = {case["case_id"] for case in dev_cases}
    seen_contexts = {case_fingerprint(case) for case in dev_cases}
    for entry in pilot["cases"]:
        case = entry["case"]
        validate_case(case)
        fingerprint = case_fingerprint(case)
        if case["case_id"] in seen_ids or fingerprint in seen_contexts:
            raise ValueError("Duplicate pilot case ID or case context.")
        seen_ids.add(case["case_id"])
        seen_contexts.add(fingerprint)
        matched = entry["matched_claim_ids"]
        missing = entry["needs_information_claim_ids"]
        labels = matched + missing
        if len(set(labels)) != len(labels) or not set(labels) <= ALLOWED_CLAIMS:
            raise ValueError("Duplicate, conflicting, or unknown claim annotation.")
        if type(entry["resistance_review"]) is not bool or not entry["rationale"].strip():
            raise ValueError("Every pilot case requires a review label and an annotation rationale.")
    return pilot["cases"]


def case_fingerprint(case: dict) -> str:
    context = {key: value for key, value in case.items() if key != "case_id" and value is not None}
    for key in ("variants", "prior_drugs"):
        if key in context:
            context[key] = sorted({item.strip().lower() for item in context[key]})
    return json.dumps(context, sort_keys=True)


def tokens(value: object) -> list[str]:
    return re.findall(r"[a-z0-9]+", json.dumps(value, ensure_ascii=False).lower())


def claim_text_fields(base: dict, t790m: dict) -> dict[str, list]:
    documents = {}
    for dataset in (base, t790m):
        for claim in dataset["claims"]:
            source = claim.get("source") or claim["evidence"]
            documents[claim["id"]] = [
                source["title"], claim["kind"], claim["disease"], claim["variant"],
                claim.get("drugs") or claim["drug"], claim["clinical_context"],
                claim.get("evidence_scope") or claim.get("notes"),
            ]
    return documents


def claim_documents(base: dict, t790m: dict) -> dict[str, list[str]]:
    return {claim_id: tokens(fields) for claim_id, fields in claim_text_fields(base, t790m).items()}


def case_query_fields(case: dict) -> dict:
    return {key: value for key, value in case.items()
            if key not in {"case_id", "synthetic"} and value is not None}


def bm25_scores(query: list[str], documents: dict[str, list[str]]) -> dict[str, float]:
    average_length = mean(map(len, documents.values()))
    terms = sorted({token.lower() for token in query})
    counts = {cid: Counter(text) for cid, text in documents.items()}
    scores = dict.fromkeys(documents, 0.0)
    k1, b = 1.2, 0.75
    for term in terms:
        document_frequency = sum(term in counter for counter in counts.values())
        idf = math.log1p((len(documents) - document_frequency + 0.5) / (document_frequency + 0.5))
        for cid, counter in counts.items():
            frequency = counter[term]
            normalizer = k1 * (1 - b + b * len(documents[cid]) / average_length)
            scores[cid] += idf * (frequency * (k1 + 1)) / (frequency + normalizer)
    return scores


def rank_claims(scores: dict[str, float], statuses: dict[str, str] | None = None) -> list[str]:
    if statuses is None:
        return sorted(scores, key=lambda cid: (-scores[cid], cid))
    return sorted(scores, key=lambda cid: (STATUS_ORDER[statuses[cid]], -scores[cid], cid))


def score_ranking(ranking: list[str], relevant: set[str], k: int) -> dict:
    top = ranking[:k]
    hits = sum(cid in relevant for cid in top)
    return {
        "hits": hits,
        "retrieved": len(top),
        "precision": hits / len(top),
        "recall": hits / len(relevant) if relevant else None,
        "reciprocal_rank": next((1 / i for i, cid in enumerate(ranking, 1) if cid in relevant), 0.0)
        if relevant else None,
    }


def summarize_rankings(results: list[dict]) -> dict:
    positive = [row for row in results if row["recall"] is not None]
    return {
        "positive_cases": len(positive),
        "no_positive_cases": len(results) - len(positive),
        "macro_precision_all_cases": mean(row["precision"] for row in results),
        "macro_recall_positive_cases": mean(row["recall"] for row in positive) if positive else None,
        "mrr_positive_cases": mean(row["reciprocal_rank"] for row in positive) if positive else None,
    }


def binary_counts(pairs: list[tuple[bool, bool]]) -> dict:
    counts = Counter(pairs)
    tp, fp, fn, tn = (counts[key] for key in ((True, True), (False, True), (True, False), (False, False)))
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
    }


def run_pilot(cases: list[dict], base: dict, t790m: dict, k: int) -> dict:
    rows = offline_claims(base, t790m)
    documents = claim_documents(base, t790m)
    outcomes = []
    for entry in cases:
        case = entry["case"]
        context = evaluate(case, rows, "offline_curated_json_graph_shaped")
        triage = evidence_triage(case, context)
        flags = triage["drug_mentions_for_research_review"]
        if (triage["auto_exclusions"] or triage["candidate_treatments_generated"]
                or any(f["automatic_exclusion"] or f["cleared_as_safe"] or f["recommended"] for f in flags)):
            raise ValueError("Unexpected automatic action or treatment assertion in triage.")
        statuses = {row["claim_id"]: row["status"] for row in context["results"]}
        variant_statuses = {
            row["id"]: (
                "NOT_EVALUATED" if not row["variants"] else
                "CONTEXT_MATCHED" if set(row["variants"]) & set(case["variants"]) else "NOT_MATCHED"
            )
            for row in rows
        }
        # Use the same lexical query, candidate universe, and tie-break across all modes.
        query = tokens(case_query_fields(case))
        lexical_scores = bm25_scores(query, documents)
        rankings = {
            "lexical_bm25": rank_claims(lexical_scores),
            "variant_only_rerank": rank_claims(lexical_scores, variant_statuses),
            "full_context_rerank": rank_claims(lexical_scores, statuses),
        }
        relevant = set(entry["matched_claim_ids"])
        outcomes.append({
            "case_id": case["case_id"],
            "reference": {key: value for key, value in entry.items() if key != "case"},
            "rankings": rankings,
            "ranking_scores": {mode: score_ranking(order, relevant, k) for mode, order in rankings.items()},
            "variant_only_statuses": variant_statuses,
            "full_context_statuses": statuses,
            "source_urls_by_claim": {row["claim_id"]: row["source_urls"] for row in context["results"]},
            "triage_flags_by_drug": {
                flag["drug_mentioned_not_recommended"]: flag["research_flag"] for flag in flags
            },
            "resistance_review_emitted": any(
                flag["research_flag"] == "RESISTANCE_ASSOCIATION_REVIEW" for flag in flags
            ),
        })

    metrics = {
        mode: summarize_rankings([outcome["ranking_scores"][mode] for outcome in outcomes])
        for mode in outcomes[0]["rankings"]
    }
    for mode in ("variant_only", "full_context"):
        metrics[mode + "_needs_information"] = binary_counts([
            (cid in outcome["reference"]["needs_information_claim_ids"], state == "NEEDS_INFORMATION")
            for outcome in outcomes for cid, state in outcome[mode + "_statuses"].items()
        ])
        metrics[mode + "_match_presence"] = binary_counts([
            (bool(outcome["reference"]["matched_claim_ids"]),
             "CONTEXT_MATCHED" in outcome[mode + "_statuses"].values())
            for outcome in outcomes
        ])
    for mode in ("triage_enabled", "triage_removed"):
        metrics[mode + "_resistance_review"] = binary_counts([
            (outcome["reference"]["resistance_review"],
             mode == "triage_enabled" and outcome["resistance_review_emitted"])
            for outcome in outcomes
        ])
    return {"k": k, "case_count": len(outcomes), "metrics": metrics, "cases": outcomes}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--k", type=int, default=3, choices=range(1, len(ALLOWED_CLAIMS) + 1))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        cases = read_cases()
        base, t790m, _ = load_sources()
        report = {
            "benchmark_id": "ONCOKG-TASK07-RETRIEVAL-PILOT-V0.1",
            "reference_type": REFERENCE, "synthetic_only": True, "independently_adjudicated": False,
            "origin": "offline_curated_json_graph_shaped",
            "file_sha256": {str(path.relative_to(ROOT)): sha256_file(path)
                            for path in (PILOT, BASE_FILE, T790M_FILE, CASES_FILE, Path(__file__).resolve(),
                                         ROOT / "codes/demo/condition_retrieval.py",
                                         ROOT / "codes/demo/safety_triage.py")},
            **run_pilot(cases, base, t790m, args.k),
        }
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as output:
                json.dump(report, output, indent=2, sort_keys=True)
                output.write("\n")
        else:
            print(json.dumps(report, indent=2, sort_keys=True))
    except (OSError, KeyError, TypeError, ValueError) as error:
        parser.exit(1, f"STOP: {error}\n")


if __name__ == "__main__":
    main()
