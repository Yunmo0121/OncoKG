import argparse
import json
from getpass import getpass
from pathlib import Path

from neo4j import GraphDatabase
from neo4j.exceptions import DriverError, Neo4jError

from validate_seed import validate_demo_seed


NODE_SPECS = {
    "genes": ("Gene", ("symbol",)),
    "variants": ("Variant", ("hgvs_c", "protein_label")),
    "diseases": ("Disease", ("code", "name")),
    "drugs": ("Drug", ("name",)),
    "claims": ("Claim", ("kind", "setting", "line", "region", "condition_code")),
    "evidence": ("Evidence", ("source", "release", "record_id", "locator", "url", "grade_scheme", "grade_raw")),
}

RELATIONSHIP_SPECS = (
    ("variants", "IN_GENE", "genes", "gene_id"),
    ("claims", "IN_DISEASE", "diseases", "disease_id"),
    ("claims", "ABOUT_DRUG", "drugs", "drug_id"),
    ("claims", "REQUIRES_VARIANT", "variants", "variant_ids"),
    ("claims", "REQUIRES_PROGRESSION_ON", "drugs", "prior_drug_id"),
    ("claims", "HAS_EVIDENCE", "evidence", "evidence_ids"),
)


def node_rows(seed):
    """Convert validated records into Neo4j node properties."""
    rows_by_label = {}
    for group, (label, fields) in NODE_SPECS.items():
        rows = []
        for record in seed[group]:
            properties = {"id": record["id"]}
            for field in fields:
                value = record.get(field)
                if value is None:
                    continue
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"{label} {record['id']} has an invalid {field} value.")
                properties[field] = value
            if label == "Evidence" and ("grade_scheme" in properties) != ("grade_raw" in properties):
                raise ValueError(f"Evidence {record['id']} requires both grade fields when either is present.")
            rows.append(properties)
        rows_by_label[label] = rows
    return rows_by_label


def relationship_rows(seed):
    """Resolve each validated reference into a pair of endpoint IDs."""
    rows_by_pattern = {}
    for source_group, relationship, target_group, field in RELATIONSHIP_SPECS:
        source_label = NODE_SPECS[source_group][0]
        target_label = NODE_SPECS[target_group][0]
        rows = []
        for record in seed[source_group]:
            references = record.get(field, [])
            if isinstance(references, str):
                references = [references]
            for target_id in references:
                rows.append({"source_id": record["id"], "target_id": target_id})
        rows_by_pattern[source_label, relationship, target_label] = rows
    return rows_by_pattern


def merge_graph(tx, nodes_by_label, links_by_pattern):
    """Write the demo graph and verify its counts in one data transaction."""
    for label, rows in nodes_by_label.items():
        expected_properties = {row["id"]: row for row in rows}
        result = tx.run(
            f"""
            UNWIND $rows AS row
            MERGE (node:{label} {{id: row.id}})
            ON CREATE SET node += row
            RETURN node.id AS id, labels(node) AS labels, properties(node) AS properties
            """,
            rows=rows,
        )
        for record in result:
            if record["labels"] != [label] or record["properties"] != expected_properties[record["id"]]:
                raise ValueError(f"Existing {label} {record['id']} differs from the seed.")

    for (source_label, relationship, target_label), rows in links_by_pattern.items():
        result = tx.run(
            f"""
            UNWIND $rows AS row
            MATCH (source:{source_label} {{id: row.source_id}})
            MATCH (target:{target_label} {{id: row.target_id}})
            MERGE (source)-[link:{relationship}]->(target)
            RETURN count(link) AS link_count
            """,
            rows=rows,
        ).single(strict=True)
        if result["link_count"] != len(rows):
            raise ValueError(f"Unexpected number of {relationship} relationships.")

    counts = tx.run(
        """
        MATCH (node)
        WITH count(node) AS node_count
        OPTIONAL MATCH ()-[link]->()
        RETURN node_count, count(link) AS link_count
        """
    ).single(strict=True)
    expected_nodes = sum(len(rows) for rows in nodes_by_label.values())
    expected_links = sum(len(rows) for rows in links_by_pattern.values())
    if counts["node_count"] != expected_nodes or counts["link_count"] != expected_links:
        raise ValueError("The database contains data outside this demo seed. Select its dedicated database.")
    return counts["node_count"], counts["link_count"]


def main():
    parser = argparse.ArgumentParser(description="Import an OncoKG v0.1 demo seed into Neo4j.")
    parser.add_argument("seed_path", nargs="?", type=Path, default=Path(__file__).with_name("seed.json"))
    parser.add_argument("--uri", default="bolt://localhost:7687")
    parser.add_argument("--username", default="neo4j")
    parser.add_argument("--database", default="neo4j")
    args = parser.parse_args()

    try:
        with args.seed_path.open(encoding="utf-8") as file:
            seed = json.load(file)
        validate_demo_seed(seed)
        nodes_by_label = node_rows(seed)
        links_by_pattern = relationship_rows(seed)

        password = getpass("Neo4j password: ")
        with GraphDatabase.driver(args.uri, auth=(args.username, password)) as driver:
            driver.verify_connectivity()
            with driver.session(database=args.database) as session:
                for label in nodes_by_label:
                    session.run(
                        f"CREATE CONSTRAINT {label.lower()}_id IF NOT EXISTS "
                        f"FOR (node:{label}) REQUIRE node.id IS UNIQUE"
                    ).consume()
                node_count, link_count = session.execute_write(merge_graph, nodes_by_label, links_by_pattern)
    except (OSError, ValueError, DriverError, Neo4jError) as error:
        parser.exit(1, f"Import failed: {error}\n")

    print(f"Graph verified. Nodes: {node_count}. Relationships: {link_count}.")


if __name__ == "__main__":
    main()
