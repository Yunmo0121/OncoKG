import json
from getpass import getpass
from pathlib import Path

from neo4j import GraphDatabase
from neo4j.exceptions import DriverError, Neo4jError

from demo import evaluate
from demo_neo4j import check_graph_rows, fetch_claims
from validate_seed import validate_demo_seed


DRUG_A = "DEMO:DRUG_A"
DRUG_B = "DEMO:DRUG_B"
T790M = "HGVS:NM_005228.5:c.2369C>T"
CONDITION = "DEMO:CONDITION_X"


def build_checks(case):
    condition_unknown = dict(case["conditions"])
    condition_unknown.pop(CONDITION)

    return [
        ("Original case", case, True, {DRUG_A: "REVIEW", DRUG_B: "BLOCKED"}, []),
        ("Condition unrecorded", {**case, "conditions": condition_unknown}, True,
         {DRUG_A: "REVIEW", DRUG_B: "NEEDS_CONTEXT"}, []),
        ("Condition explicitly absent", {**case, "conditions": {**case["conditions"], CONDITION: False}}, True,
         {DRUG_A: "REVIEW", DRUG_B: "NO_RULE_HIT"}, [DRUG_B]),
        ("T790M explicitly absent", {**case, "variants": {**case["variants"], T790M: False}}, True,
         {DRUG_A: "NO_RULE_HIT", DRUG_B: "BLOCKED"}, [DRUG_A]),
        ("Prior treatment history incomplete", {**case, "history": [], "history_complete": False}, True,
         {DRUG_A: "NEEDS_CONTEXT", DRUG_B: "BLOCKED"}, []),
        ("Disease outside the demo", {**case, "disease_id": "DEMO:OTHER_DISEASE"}, True, {}, []),
        ("Conflict filtering disabled", case, False,
         {DRUG_A: "NOT_EVALUATED", DRUG_B: "NOT_EVALUATED"}, [DRUG_A, DRUG_B]),
    ]


def run_checks(session, seed, checks):
    passed = 0
    for name, case, filter_conflicts, expected_candidates, expected_forwarded in checks:
        disease_id = case["disease_id"]
        seed_claims = [claim for claim in seed["claims"] if claim["disease_id"] == disease_id]
        claims = session.execute_read(fetch_claims, disease_id)
        check_graph_rows(claims, seed_claims, seed["evidence"])

        result = evaluate(claims, case, filter_conflicts=filter_conflicts)
        candidates = {item["drug_id"]: item["status"] for item in result["candidates"]}
        expected_status = "CANDIDATES_FOUND" if expected_candidates else "NO_MATCHING_EVIDENCE"
        if (result["status"], candidates, result["forwarded_drug_ids"]) != (
            expected_status, expected_candidates, expected_forwarded
        ):
            print(f"FAIL {name}")
            print(f"  Expected: {expected_status}, {expected_candidates}, forwarded={expected_forwarded}")
            print(f"  Actual:   {result['status']}, {candidates}, forwarded={result['forwarded_drug_ids']}")
            continue

        passed += 1
        summary = ", ".join(f"{drug_id}={status}" for drug_id, status in candidates.items())
        print(f"PASS {name}: {summary or result['status']}")
    return passed


def main():
    demo_dir = Path(__file__).resolve().parent
    try:
        seed = json.loads((demo_dir / "seed.json").read_text(encoding="utf-8"))
        case = json.loads((demo_dir / "case.json").read_text(encoding="utf-8"))
        validate_demo_seed(seed)
        checks = build_checks(case)

        password = getpass("Neo4j password: ")
        with GraphDatabase.driver("neo4j://127.0.0.1:7687", auth=("neo4j", password)) as driver:
            with driver.session(database="oncokg") as session:
                passed = run_checks(session, seed, checks)
    except (OSError, ValueError, KeyError, DriverError, Neo4jError) as error:
        raise SystemExit(f"Case checks stopped: {error}") from error

    print(f"Passed {passed}/{len(checks)} case checks.")
    if passed != len(checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()