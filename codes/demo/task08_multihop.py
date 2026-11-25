"""Compare read-only, typed two-hop and four-hop evidence paths for synthetic cases."""
from __future__ import annotations

import argparse
import json
from getpass import getpass
from pathlib import Path

from condition_retrieval import (
    CASES_FILE, evaluate, load_sources, offline_claims, read_db_tx,
    validate_case, verify_against_curated,
)

ORIGIN = "verified_neo4j_oncokg_real_read_only"
HOP_BUDGETS = (2, 4)
AURA3_PFS_CLAIM = "AURA3-2017-T790M-OVERALL-PFS"
AURA3_PMID = "27959700"
AURA3_PRIMARY_URL = f"https://pubmed.ncbi.nlm.nih.gov/{AURA3_PMID}/"

# Each branch is a typed path template. Shared entities allow discovery, not inference.
PATH_QUERY = """
UNWIND $variants AS protein
MATCH (variant:Variant {protein_label: protein, gene_symbol: $gene})
MATCH (disease:Disease {code: $disease})
CALL (variant, disease) {
    MATCH path = (variant)<-[:REQUIRES_VARIANT]-(claim:Claim)
        -[:HAS_EVIDENCE]->(evidence:Evidence)
    RETURN path, claim, evidence, 'DIRECT_VARIANT' AS scope
    UNION ALL
    WITH variant WHERE $max_hops >= 4
    MATCH path = (variant)-[:IN_GENE]->(:Gene)<-[:IN_GENE]-(peer:Variant)
        <-[:REQUIRES_VARIANT]-(claim:Claim)-[:HAS_EVIDENCE]->(evidence:Evidence)
    WHERE peer <> variant
    RETURN path, claim, evidence, 'OTHER_VARIANT_SAME_GENE' AS scope
    UNION ALL
    WITH variant, disease WHERE $max_hops >= 4
    MATCH path = (variant)<-[:REQUIRES_VARIANT]-(bridge:Claim)
        -[:IN_DISEASE]->(disease)<-[:IN_DISEASE]-(claim:Claim)
        -[:HAS_EVIDENCE]->(evidence:Evidence)
    WHERE NOT EXISTS { MATCH (claim)-[:REQUIRES_VARIANT]->(:Variant) }
          AND EXISTS {
              MATCH (bridge_dataset:Dataset)-[:CONTAINS_CLAIM]->(bridge)
              WHERE bridge_dataset.id IN $dataset_ids
          }
    RETURN path, claim, evidence, 'DISEASE_BACKGROUND' AS scope
}
MATCH (dataset:Dataset)-[:CONTAINS_CLAIM]->(claim)
WHERE dataset.id IN $dataset_ids AND EXISTS { MATCH (claim)-[:IN_DISEASE]->(disease) }
RETURN variant.protein_label AS anchor_variant, scope, length(path) AS hops,
       claim.id AS claim_id, dataset.id AS dataset_id,
       [n IN nodes(path) | {id: n.id, labels: labels(n)}] AS nodes,
       [r IN relationships(path) | {type: type(r), from_id: startNode(r).id,
                                    to_id: endNode(r).id}] AS relationships,
       evidence {.id, .title, .url, locator: coalesce(evidence.locator, evidence.section),
                 .pmid, .doi} AS source
ORDER BY anchor_variant, hops, scope, claim_id, [n IN nodes(path) | n.id]
"""


def select_cases(case_id: str | None) -> list[dict]:
    cases = json.loads(CASES_FILE.read_text(encoding="utf-8"))["cases"]
    if case_id is not None:
        cases = [case for case in cases if case["case_id"] == case_id]
        if len(cases) != 1:
            raise ValueError(f"Unknown synthetic case or duplicate case ID: {case_id}")
    if not cases:
        raise ValueError("The synthetic case fixture is empty.")
    for case in cases:
        validate_case(case)
    return cases


def supplemental_source_links(claim_id: str, source_urls: list[str]) -> list[dict]:
    if claim_id != AURA3_PFS_CLAIM:
        return []
    if AURA3_PRIMARY_URL not in source_urls:
        raise ValueError("AURA3 publication does not match the reviewed PFS source.")
    return [{
        "kind": "CIVIC_CURATOR_SUMMARY", "url": "https://civicdb.org/links/evidence_items/1867",
        "publication_pmid": AURA3_PMID, "civic_release": "01-Nov-2026",
        "linked_scope": "PFS_ONLY", "review_status": "PENDING_ONCOKG_REVIEW",
    }]


def enrich_paths(paths: list[dict], context: dict) -> list[dict]:
    result = []
    for path in paths:
        claim_id = path["claim_id"]
        claim = context.get(claim_id)
        source = path["source"]
        if claim is None or source["url"] not in claim["source_urls"]:
            raise ValueError(f"Path provenance does not match the verified snapshot: {claim_id}")
        pmid = source.get("pmid")
        source_links = [{"kind": "GRAPH_SOURCE", "url": source["url"], "publication_pmid": pmid}]
        if claim_id == AURA3_PFS_CLAIM and pmid != AURA3_PMID:
            raise ValueError("AURA3 publication does not match the reviewed PFS source.")
        source_links.extend(supplemental_source_links(claim_id, [source["url"]]))
        result.append({
            **path,
            "source_links": source_links,
            "context_status": claim["status"],
            "missing_context": [check for check in claim["checks"] if check.startswith("MISSING:")],
            "warning": claim["warning"],
        })
    return result


def summarize_paths(paths: list[dict]) -> dict:
    return {
        "path_count": len(paths),
        "claim_ids": sorted({path["claim_id"] for path in paths}),
        "publication_pmids": sorted({path["source"]["pmid"] for path in paths
                                     if path["source"].get("pmid")}),
        "matched_claim_ids": sorted({path["claim_id"] for path in paths
                                     if path["context_status"] == "CONTEXT_MATCHED"}),
    }


def compare_cases(tx, cases: list[dict], expected_rows: list[dict], source_hashes: dict) -> dict:
    verified_rows = read_db_tx(tx, source_hashes)
    verify_against_curated(verified_rows, expected_rows)
    comparisons = []
    for case in cases:
        context = {claim["claim_id"]: claim
                   for claim in evaluate(case, verified_rows, ORIGIN)["results"]}
        budgets = {}
        for budget in HOP_BUDGETS:
            rows = tx.run(PATH_QUERY, variants=sorted(set(case["variants"])), gene=case["gene"],
                          disease=case["cancer_type"], max_hops=budget,
                          dataset_ids=list(source_hashes)).data()
            paths = enrich_paths(rows, context)
            budgets[str(budget)] = {**summarize_paths(paths), "paths": paths}

        baseline, expanded = (budgets[str(budget)] for budget in HOP_BUDGETS)
        comparisons.append({
            "case_id": case["case_id"],
            "budgets": budgets,
            "additional_claim_ids": sorted(set(expanded["claim_ids"]) - set(baseline["claim_ids"])),
            "additional_matched_claim_ids": sorted(set(expanded["matched_claim_ids"])
                                                   - set(baseline["matched_claim_ids"])),
        })
    return {
        "task": "Task 08 typed evidence paths", "origin": ORIGIN,
        "synthetic_only": True, "research_only": True,
        "dataset_sha256": source_hashes, "cases": comparisons,
    }


def main() -> None:
    from neo4j import GraphDatabase
    from neo4j.exceptions import DriverError, Neo4jError

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", help="Optional ID from the versioned synthetic case fixture.")
    parser.add_argument("--uri", default="bolt://localhost:7687")
    parser.add_argument("--database", default="neo4j")
    parser.add_argument("--user", default="neo4j")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        cases = select_cases(args.case_id)
        base, t790m, source_hashes = load_sources()
        expected_rows = offline_claims(base, t790m)
        auth = (args.user, getpass("Neo4j password: "))
        with GraphDatabase.driver(args.uri, auth=auth) as driver:
            with driver.session(database=args.database) as session:
                report = session.execute_read(compare_cases, cases, expected_rows, source_hashes)

        output = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as file:
                file.write(output + "\n")
        else:
            print(output)
    except (DriverError, Neo4jError) as error:
        parser.exit(1, f"STOP: Neo4j operation failed ({type(error).__name__}).\n")
    except (OSError, KeyError, TypeError, ValueError) as error:
        parser.exit(1, f"STOP: {error}\n")


if __name__ == "__main__":
    main()
