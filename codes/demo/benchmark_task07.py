"""OncoKG Task 07A -- regression benchmark for EXISTING synthetic prototype.

This is an engineering smoke/regression test, NOT an independent clinical benchmark.
Run from the OncoKG project root:
  codes/demo/.venv/bin/python codes/demo/benchmark_task07.py --offline
  codes/demo/.venv/bin/python codes/demo/benchmark_task07.py --db

Offline requires no API keys and never makes network calls. --db reads Neo4j only.
Neither mode calls a language model, changes databases or makes drug recommendations.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from getpass import getpass
from pathlib import Path

from condition_retrieval import (
    ALLOWED_CLAIMS, ROOT, load_sources, offline_claims, read_db_tx,
    verify_against_curated, verify_records,
)
from safety_triage import evidence_triage, load_case

DEFAULT_EXPECTATIONS = ROOT / "data/benchmarks/task07_regression_expectations_v0_1.json"
DEFAULT_OUTPUT_DIR = ROOT / "docs/results/task07_v0_1"
EXPECTED_STATES = {"CONTEXT_MATCHED", "NOT_MATCHED", "NEEDS_INFORMATION", "NOT_EVALUATED"}
EXPECTED_CASE_IDS = {
    "SYN-T790M-001", "SYN-L858R-002", "SYN-T790M-UNKNOWN-003", "SYN-T790M-NO-PRIOR-004"
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_expectations(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("reference_type") != "developer_defined_regression_expectations_NOT_independent_medical_gold":
        raise ValueError("Only explicitly marked non-clinical engineering expectations are supported.")
    claim_ids = payload.get("claims_order")
    cases = payload.get("cases")
    if not isinstance(claim_ids, list) or set(claim_ids) != ALLOWED_CLAIMS or len(claim_ids) != 5:
        raise ValueError("Benchmark Claim inventory must match five known v0.2 claims exactly.")
    if not isinstance(cases, dict) or set(cases) != EXPECTED_CASE_IDS:
        raise ValueError("Expected exactly the four existing synthetic case IDs.")
    for case_id, target in cases.items():
        if len(target.get("statuses", [])) != 5 or any(s not in EXPECTED_STATES for s in target["statuses"]):
            raise ValueError(f"Invalid expected statuses: {case_id}")
        if set(target.get("flags", {})) != {"erlotinib", "gefitinib", "osimertinib"}:
            raise ValueError(f"Incomplete research flags: {case_id}")
        if not all(isinstance(v, str) and v for v in target["flags"].values()):
            raise ValueError("Invalid flag value")
    return payload


def get_rows(use_db: bool, uri: str, username: str, database: str) -> tuple[list[dict], str]:
    base, t790m, hashes = load_sources()
    expected = offline_claims(base, t790m)
    if not use_db:
        verify_records(expected)
        return expected, "offline_curated_json"
    from neo4j import GraphDatabase
    with GraphDatabase.driver(uri, auth=(username, getpass("Password for OncoKG-Real: "))) as driver:
        driver.verify_connectivity()
        with driver.session(database=database) as session:
            rows = session.execute_read(read_db_tx, hashes)
    verify_against_curated(rows, expected)
    return rows, "verified_neo4j_read_only"


def compare(predictions: list[dict], expectations: dict) -> tuple[list[dict], list[dict], dict]:
    """Compare external prediction records to frozen engineering expectations.

    Expects {case_id, status_by_claim, flags_by_drug, unsafe_auto_actions}.
    Pure function; useful for unit tests of the scoring method.
    """
    index = {p["case_id"]: p for p in predictions}
    if len(index) != len(predictions) or set(index) != set(expectations["cases"]):
        raise ValueError("Prediction cases are missing, duplicated or unexpected.")
    status_rows, flag_rows = [], []
    for case_id in sorted(index):
        p = index[case_id]
        expected = expectations["cases"][case_id]
        claim_order = expectations["claims_order"]
        status_map = p["status_by_claim"]
        if set(status_map) != set(claim_order):
            raise ValueError(f"Missing or unknown claims in {case_id}")
        flag_map = p["flags_by_drug"]
        if set(flag_map) != set(expected["flags"]):
            raise ValueError(f"Missing or unknown drug flags in {case_id}")
        if p.get("unsafe_auto_actions") != 0:
            raise ValueError(f"Safety invariant violated: automatic action in {case_id}")
        for cid, gold in zip(claim_order, expected["statuses"]):
            pred = status_map[cid]
            if pred not in EXPECTED_STATES:
                raise ValueError(f"Unknown status {pred!r}")
            status_rows.append({
                "case_id": case_id, "claim_id": cid,
                "expected_engineering_status": gold, "actual_status": pred,
                "agree": pred == gold,
            })
        for drug, flag in sorted(expected["flags"].items()):
            flag_rows.append({
                "case_id": case_id, "drug": drug,
                "expected_engineering_flag": flag,
                "actual_flag": flag_map[drug], "agree": flag_map[drug] == flag,
            })
    assessed = [r for r in status_rows if r["expected_engineering_status"] != "NOT_EVALUATED"]
    metrics = {
        "case_count": len(predictions),
        "claim_comparisons": len(status_rows),
        "research_flag_comparisons": len(flag_rows),
        "engineering_status_agreement": sum(r["agree"] for r in status_rows) / len(status_rows),
        "engineering_status_agreement_excluding_not_evaluated": sum(r["agree"] for r in assessed) / len(assessed),
        "engineering_flag_agreement": sum(r["agree"] for r in flag_rows) / len(flag_rows),
        "auto_exclusions": 0,
        "clinical_accuracy_estimate": None,
        "real_llm_benchmark_score": None,
        "vector_rag_benchmark_score": None,
        "independently_adjudicated": False,
    }
    return status_rows, flag_rows, metrics


def run_benchmark(rows: list[dict], expectations: dict, origin: str) -> dict:
    from condition_retrieval import evaluate
    predictions = []
    source_records = []
    for case_id in sorted(expectations["cases"]):
        case = load_case(case_id)
        context_report = evaluate(case, rows, origin)
        safety_report = evidence_triage(case, context_report)
        status_by_claim = {r["claim_id"]: r["status"] for r in context_report["results"]}
        flags_by_drug = {
            r["drug_mentioned_not_recommended"]: r["research_flag"]
            for r in safety_report["drug_mentions_for_research_review"]
        }
        unsafe = len(safety_report["auto_exclusions"]) + len(safety_report["candidate_treatments_generated"])
        unsafe += sum(
            bool(r["automatic_exclusion"] or r["cleared_as_safe"] or r["recommended"])
            for r in safety_report["drug_mentions_for_research_review"]
        )
        predictions.append({
            "case_id": case_id, "status_by_claim": status_by_claim,
            "flags_by_drug": flags_by_drug, "unsafe_auto_actions": unsafe,
        })
        for r in context_report["results"]:
            source_records.append({"case_id": case_id, "claim_id": r["claim_id"],
                                   "source_urls": list(r["source_urls"])})
    status_rows, flag_rows, metrics = compare(predictions, expectations)
    return {"predictions": predictions, "status_rows": status_rows, "flag_rows": flag_rows,
            "source_records": source_records, "metrics": metrics}


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Task 07A: engineering regression checks, NOT clinical evaluation")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--offline", action="store_true", help="No Neo4j or API access")
    mode.add_argument("--db", action="store_true", help="Read-only Neo4j with v0.2 fingerprint verification")
    parser.add_argument("--expectations", type=Path, default=DEFAULT_EXPECTATIONS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--uri", default="bolt://localhost:7687")
    parser.add_argument("--username", default="neo4j")
    parser.add_argument("--database", default="neo4j")
    args = parser.parse_args()
    try:
        oracle = read_expectations(args.expectations)
        rows, origin = get_rows(args.db, args.uri, args.username, args.database)
        results = run_benchmark(rows, oracle, origin)
        fingerprints = {}
        for path in (
            args.expectations,
            ROOT / "data/samples/synthetic_nsclc_cases_v0_1.json",
            ROOT / "data/curated/egfr_l858r_evidence_v0_1.json",
            ROOT / "data/curated/egfr_t790m_evidence_extraction_v0_2.json",
            ROOT / "codes/demo/condition_retrieval.py",
            ROOT / "codes/demo/safety_triage.py",
        ):
            path = path.resolve()
            label = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else path.name
            fingerprints[label] = sha256_file(path)
        report = {
            "benchmark_id": oracle["benchmark_id"],
            "benchmark_type": oracle["reference_type"],
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "origin": origin, "synthetic_only": True, "no_llm_api_calls": True,
            "not_clinically_validated": True,
            "limitations": [
                "Engineering expected labels were derived from intended prototype rules, not external clinical review.",
                "These four cases were already used during module development; this is NOT a held-out evaluation.",
                "Matching the current system's expected outputs cannot demonstrate medical correctness or KG-Agent superiority.",
                "Independent reference labeling and actual LLM/Vector RAG baselines have NOT been done.",
            ],
            "metrics": results["metrics"], "file_sha256": fingerprints,
            "comparisons": results["status_rows"],
            "research_flags": results["flag_rows"],
            "claim_provenance": results["source_records"],
        }
        args.output_dir.mkdir(parents=True, exist_ok=True)
        json_path = args.output_dir / "task07_engineering_regression.json"
        json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        write_csv(args.output_dir / "task07_claim_comparisons.csv", results["status_rows"])
        write_csv(args.output_dir / "task07_flag_comparisons.csv", results["flag_rows"])
        m = report["metrics"]
        mismatches = any(not r["agree"] for r in results["status_rows"] + results["flag_rows"])
        outcome = "FAIL" if mismatches else "PASS"
        print(f"{outcome}: {m['case_count']} synthetic cases; {m['claim_comparisons']} claim checks; "
              f"{m['research_flag_comparisons']} research-flag checks.")
        print(f"Engineering status agreement: {m['engineering_status_agreement']:.1%}; "
              f"flag agreement: {m['engineering_flag_agreement']:.1%}.")
        print("NOT a clinical benchmark, held-out test, or LLM-versus-RAG comparison.")
        print(f"Local reports saved under: {args.output_dir}")
        if mismatches:
            parser.exit(1, "REGRESSION CHECK FAILED: inspect comparison CSV files.\n")
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        parser.exit(1, f"STOP: {exc}\n")


if __name__ == "__main__":
    main()
