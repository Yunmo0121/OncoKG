import argparse
import json
from getpass import getpass
from pathlib import Path

from neo4j import GraphDatabase
from neo4j.exceptions import DriverError, Neo4jError

from demo import evaluate
from validate_seed import validate_demo_seed


CLAIM_QUERY = """
MATCH (claim:Claim)-[:IN_DISEASE]->(disease:Disease {id: $disease_id})
MATCH (claim)-[:ABOUT_DRUG]->(drug:Drug)
OPTIONAL MATCH (claim)-[:HAS_EVIDENCE]->(e:Evidence)
WITH claim, disease, drug, e ORDER BY e.id
WITH claim, disease, drug, collect(properties(e)) AS evidence
RETURN claim {.*,
    disease_id: disease.id,
    drug_id: drug.id,
    variant_ids: [(claim)-[:REQUIRES_VARIANT]->(v:Variant) | v.id],
    prior_drug_id: head([(claim)-[:REQUIRES_PROGRESSION_ON]->(p:Drug) | p.id]),
    evidence_ids: [item IN evidence | item.id],
    evidence: evidence
} AS claim_row
ORDER BY claim_row.id
"""

CLAIM_FIELDS = (
    "id", "kind", "disease_id", "drug_id", "setting", "line", "region",
    "condition_code", "prior_drug_id",
)
EVIDENCE_FIELDS = ("source", "release", "record_id", "locator", "url", "grade_scheme", "grade_raw")


def fetch_claims(tx, disease_id):
    result = tx.run(CLAIM_QUERY, disease_id=disease_id)
    return [record["claim_row"] for record in result]


def check_graph_rows(graph_claims, seed_claims, seed_evidence):
    expected_claims = {claim["id"]: claim for claim in seed_claims}
    if sorted(claim["id"] for claim in graph_claims) != sorted(expected_claims):
        raise ValueError("The claim IDs in Neo4j differ from seed.json for this disease.")

    evidence_by_id = {item["id"]: item for item in seed_evidence}
    for claim in graph_claims:
        expected = expected_claims[claim["id"]]
        for field in CLAIM_FIELDS:
            if claim.get(field) != expected.get(field):
                raise ValueError(f"Claim {claim['id']} differs in {field}.")
        for field in ("variant_ids", "evidence_ids"):
            if sorted(claim[field]) != sorted(expected[field]):
                raise ValueError(f"Claim {claim['id']} differs in {field}.")
        for evidence in claim["evidence"]:
            original = evidence_by_id[evidence["id"]]
            for field in EVIDENCE_FIELDS:
                if evidence.get(field) != original.get(field):
                    raise ValueError(f"Evidence {evidence['id']} differs in {field}.")


def main():
    parser = argparse.ArgumentParser(description="Read an OncoKG demo case from Neo4j and compare it with JSON.")
    parser.add_argument("--database", default="oncokg")
    parser.add_argument("--uri", default="neo4j://127.0.0.1:7687")
    parser.add_argument("--username", default="neo4j")
    args = parser.parse_args()

    demo_dir = Path(__file__).resolve().parent
    try:
        seed = json.loads((demo_dir / "seed.json").read_text(encoding="utf-8"))
        case = json.loads((demo_dir / "case.json").read_text(encoding="utf-8"))
        validate_demo_seed(seed)
        if not isinstance(case, dict) or not isinstance(case.get("disease_id"), str):
            raise ValueError("case.json must provide a disease_id string.")

        disease_id = case["disease_id"]
        seed_claims = [claim for claim in seed["claims"] if claim["disease_id"] == disease_id]
        password = getpass("Neo4j password: ")
        with GraphDatabase.driver(args.uri, auth=(args.username, password)) as driver:
            with driver.session(database=args.database) as session:
                graph_claims = session.execute_read(fetch_claims, disease_id)

        check_graph_rows(graph_claims, seed_claims, seed["evidence"])
        results = {}
        for filter_conflicts in (True, False):
            expected = evaluate(seed["claims"], case, filter_conflicts=filter_conflicts)
            actual = evaluate(graph_claims, case, filter_conflicts=filter_conflicts)
            if actual != expected:
                raise ValueError(f"Neo4j and JSON decisions differ with filter_conflicts={filter_conflicts}.")
            results[filter_conflicts] = actual
    except (OSError, ValueError, DriverError, Neo4jError) as error:
        parser.exit(1, f"Demo failed: {error}\n")

    print(f"Read {len(graph_claims)} claims for {disease_id} from Neo4j.")
    for claim in graph_claims:
        for evidence in claim["evidence"]:
            print(f"{claim['id']} -> {evidence['id']} ({evidence['source']} {evidence['locator']})")
    for filter_conflicts, result in results.items():
        print(f"Filter {'on' if filter_conflicts else 'off'}: {result['status']}")
        for candidate in result["candidates"]:
            print(f"  {candidate['drug_id']}: {candidate['status']}")
    print("Neo4j and JSON results match.")


if __name__ == "__main__":
    main()
