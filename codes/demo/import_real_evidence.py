"""Import curated NSCLC/EGFR v0.1 research evidence into a DEDICATED Neo4j instance.

From the OncoKG project root:
    python3 codes/demo/import_real_evidence.py --dry-run
    python3 codes/demo/import_real_evidence.py

Safeguards:
- Refuses a populated database without this dataset's ownership marker.
- Never deletes data or changes the existing synthetic demo files.
- A repeated import of the identical JSON is idempotent.
- Different JSON for an existing dataset ID is rejected (manual review required).
- FLAURA overall PFS evidence does NOT get a L858R-specific relationship.
"""

import argparse
import hashlib
import json
from getpass import getpass
from pathlib import Path

from neo4j import GraphDatabase
from neo4j.exceptions import DriverError, Neo4jError

from validate_evidence import validate

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA = ROOT / "data" / "curated" / "egfr_l858r_evidence_v0_1.json"


def read_and_check(path):
    errors = validate(path)
    if errors:
        raise ValueError("Evidence validation failed:\n" + "\n".join(errors))
    raw = path.read_bytes()
    data = json.loads(raw)
    if data.get("dataset_id") != "ONCOKG-NSCLC-EGFR-REAL-EVIDENCE-V0.1":
        raise ValueError("Unexpected dataset_id: this importer only supports real evidence v0.1.")
    claims = data["claims"]
    if sorted(c["kind"] for c in claims) != ["APPROVED_INDICATION", "TRIAL_OUTCOME"]:
        raise ValueError("Expected exactly one FDA indication and one trial outcome claim.")
    return data, hashlib.sha256(raw).hexdigest()


def assemble_graph(data, digest):
    """Generate nodes and links from the already validated v0.1 JSON.

    The only variant-specific assertion is the FDA indication claim; the trial
    outcome covers a mixed EGFR-variant population and is *not* tied to L858R.
    """
    dataset_id = data["dataset_id"]
    nodes = []
    links = []

    def node(label, **props):
        nodes.append((label, props))

    def link(start_label, start_id, relation, end_label, end_id):
        links.append((start_label, start_id, relation, end_label, end_id))

    node("Dataset", id=dataset_id, source_sha256=digest,
         research_only=True, created_at=data["created_at"],
         scope_json=json.dumps(data["scope"], ensure_ascii=False, sort_keys=True))
    gene_id = "GENE:EGFR"
    variant_id = "VARIANT:EGFR:L858R"
    disease_id = "DISEASE:NSCLC"
    drug_id = "DRUG:OSIMERTINIB"
    node("Gene", id=gene_id, symbol="EGFR")
    node("Variant", id=variant_id, protein_label="L858R", gene_symbol="EGFR")
    node("Disease", id=disease_id, code="NSCLC", name="non-small-cell lung cancer")
    node("Drug", id=drug_id, name="osimertinib")
    link("Variant", variant_id, "IN_GENE", "Gene", gene_id)

    for claim in data["claims"]:
        context = claim["clinical_context"]
        c_id = claim["id"]
        if claim["drug"].lower() != "osimertinib":
            raise ValueError(f"Unexpected drug in {c_id}.")
        if "NSCLC" not in claim["disease"]:
            raise ValueError(f"Unexpected disease in {c_id}.")
        claim_props = {
            "id": c_id,
            "kind": claim["kind"],
            "curation_status": claim["curation_status"],
            "notes": claim.get("notes", ""),
            "research_only": True,
            "clinical_context_json": json.dumps(context, ensure_ascii=False, sort_keys=True),
        }
        if claim["kind"] == "APPROVED_INDICATION":
            if claim["variant"] != "EGFR L858R":
                raise ValueError("This FDA claim must be scoped to EGFR L858R.")
            claim_props.update({
                "population": context["population"],
                "disease_stage": context["disease_stage"],
                "treatment_line": context["treatment_line"],
                "treatment_regimen": context["treatment_regimen"],
                "variant_alternative_operator": context["variant_alternative_operator"],
                  "permitted_variant_alternatives": context["permitted_variant_alternatives"],
            })
            link("Claim", c_id, "REQUIRES_VARIANT", "Variant", variant_id)
        else:
            if claim["variant"] is not None or claim["outcome"]["is_l858r_only_result"] is not False:
                raise ValueError("FLAURA overall outcome cannot be a L858R-specific claim.")
            outcome = claim["outcome"]
            claim_props.update({
                "analysis_population": outcome["analysis_population"],
                "outcome_name": outcome["name"],
                "outcome_unit": outcome["unit"],
                "outcome_osimertinib": outcome["osimertinib"],
                "outcome_comparator": outcome["comparator"],
                "is_l858r_only_result": False,
                "outcome_json": json.dumps(outcome, ensure_ascii=False, sort_keys=True),
            })
        node("Claim", **claim_props)
        ev = claim["evidence"]
        ev_props = {"id": ev["id"], "source_type": ev["source_type"],
                    "title": ev["title"], "publisher": ev["publisher"],
                    "url": ev["source_url"], "locator": ev["locator"],
                    "accessed_at": ev["accessed_at"]}
        for key in ("pmid", "doi", "source_updated", "published_year"):
            if key in ev:
                ev_props[key] = ev[key]
        node("Evidence", **ev_props)
        link("Dataset", dataset_id, "CONTAINS_CLAIM", "Claim", c_id)
        link("Claim", c_id, "ABOUT_DRUG", "Drug", drug_id)
        link("Claim", c_id, "IN_DISEASE", "Disease", disease_id)
        link("Claim", c_id, "HAS_EVIDENCE", "Evidence", ev["id"])

    # Duplicated node IDs inside a label are a data modeling error.
    keys = [(label, props["id"]) for label, props in nodes]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate node IDs in the curated evidence.")
    return nodes, links


def read_status(tx, dataset_id):
    count = tx.run("MATCH (n) RETURN count(n) AS total").single(strict=True)["total"]
    owned = tx.run("MATCH (d:Dataset {id: $id}) RETURN d.source_sha256 AS sha",
                   id=dataset_id).single()
    return count, None if owned is None else owned["sha"]


def check_destination(tx, dataset_id, digest):
    count, marker_sha = read_status(tx, dataset_id)
    if count > 0 and marker_sha is None:
        raise ValueError(
            "Refusing to import into a populated database that has no matching Dataset marker. "
            "Create and start a separate empty local Neo4j instance for real evidence."
        )
    if marker_sha is not None and marker_sha != digest:
        raise ValueError(
            "The stored dataset has a different SHA256. Review changes before importing a new version."
        )


def import_tx(tx, nodes, links, dataset_id, digest):
    # Check inside the same transaction as the writes; no deletion anywhere.
    check_destination(tx, dataset_id, digest)
    for label, props in nodes:
        tx.run(f"MERGE (n:{label} {{id: $id}}) SET n += $properties",
               id=props["id"], properties=props).consume()
    for src_label, src_id, relationship, dst_label, dst_id in links:
        record = tx.run(
            f"MATCH (a:{src_label} {{id: $src_id}}) "
            f"MATCH (b:{dst_label} {{id: $dst_id}}) "
            f"MERGE (a)-[r:{relationship}]->(b) "
            "RETURN count(r) AS created",
            src_id=src_id, dst_id=dst_id,
        ).single(strict=True)
        if record["created"] != 1:
            raise ValueError(f"Unable to link {src_label}:{src_id} to {dst_label}:{dst_id}.")
    return len(nodes), len(links)


def main():
    parser = argparse.ArgumentParser(description="Import research-only real evidence to a fresh Neo4j instance.")
    parser.add_argument("--input", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--uri", default="bolt://localhost:7687")
    parser.add_argument("--username", default="neo4j")
    parser.add_argument("--database", default="neo4j")
    parser.add_argument("--dry-run", action="store_true", help="Validate and preview; no DB connection")
    args = parser.parse_args()
    try:
        data, digest = read_and_check(args.input)
        nodes, links = assemble_graph(data, digest)
        if args.dry_run:
            print(f"DRY RUN PASS: {len(data['claims'])} claims, {len(nodes)} nodes, {len(links)} relationships.")
            print("No database connection or changes were made.")
            for claim in data["claims"]:
                print(f"  {claim['id']} [{claim['kind']}]")
            return
        password = getpass("Password for your DEDICATED real-evidence Neo4j instance: ")
        with GraphDatabase.driver(args.uri, auth=(args.username, password)) as driver:
            driver.verify_connectivity()
            with driver.session(database=args.database) as session:
                node_count, link_count = session.execute_write(
                    import_tx, nodes, links, data["dataset_id"], digest
                )
        print(f"IMPORT PASS: {node_count} expected nodes, {link_count} expected relationships.")
        print("Curated research evidence imported; independent medical review still required.")
    except (OSError, KeyError, TypeError, ValueError, DriverError, Neo4jError) as error:
        parser.exit(1, f"IMPORT FAILED (no partial data changes): {error}\n")


if __name__ == "__main__":
    main()
