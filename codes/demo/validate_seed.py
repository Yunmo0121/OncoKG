import argparse
import json
from pathlib import Path


NODE_FIELDS = {
    "genes": ("symbol",),
    "variants": ("hgvs_c",),
    "diseases": ("code", "name"),
    "drugs": ("name",),
    "claims": (),
    "evidence": ("source", "release", "record_id", "locator"),
}

CLAIM_OPTIONS = {
    "kind": ("SENSITIVITY", "RESISTANCE", "CONTRAINDICATION"),
    "setting": ("LOCALLY_ADVANCED", "METASTATIC", "ANY"),
    "line": ("1L", "2L", "3L_PLUS", "ANY"),
    "region": ("CN", "US", "ANY"),
}


def require_text(record, field, location):
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{location} requires a non-empty {field} string.")
    return value


def index_node_ids(seed):
    """Check node records and collect the IDs in each group."""
    ids_by_group = {}
    for group, required_fields in NODE_FIELDS.items():
        nodes = seed.get(group)
        if not isinstance(nodes, list):
            raise ValueError(f"The {group} field must be a list.")

        group_ids = set()
        for index, node in enumerate(nodes):
            location = f"{group}[{index}]"
            if not isinstance(node, dict):
                raise ValueError(f"{location} must be an object.")
            node_id = require_text(node, "id", location)
            if node_id in group_ids:
                raise ValueError(f"Duplicate ID in {group}: {node_id}")
            group_ids.add(node_id)
            for field in required_fields:
                require_text(node, field, location)

        ids_by_group[group] = group_ids
    return ids_by_group


def check_reference(value, valid_ids, location):
    if not isinstance(value, str) or value not in valid_ids:
        raise ValueError(f"Invalid reference in {location}: {value!r}")


def validate_claims(claims, ids_by_group):
    linked_evidence_ids = set()
    for claim in claims:
        location = f"Claim {claim['id']}"
        for field, options in CLAIM_OPTIONS.items():
            if claim.get(field) not in options:
                raise ValueError(f"{location} has an invalid {field}: {claim.get(field)!r}")

        check_reference(claim.get("disease_id"), ids_by_group["diseases"], f"{location} disease_id")
        check_reference(claim.get("drug_id"), ids_by_group["drugs"], f"{location} drug_id")

        kind = claim["kind"]
        if kind == "CONTRAINDICATION":
            require_text(claim, "condition_code", location)
        elif "condition_code" in claim:
            raise ValueError(f"{location} may only use condition_code for a contraindication.")

        if "prior_drug_id" in claim:
            if kind != "RESISTANCE":
                raise ValueError(f"{location} may only use prior_drug_id for resistance.")
            check_reference(claim["prior_drug_id"], ids_by_group["drugs"], f"{location} prior_drug_id")

        variant_ids = claim.get("variant_ids")
        minimum = 0 if kind == "CONTRAINDICATION" else 1
        if not isinstance(variant_ids, list) or not minimum <= len(variant_ids) <= 2:
            raise ValueError(f"{location} must have a variant_ids list with {minimum} to 2 entries.")
        for variant_id in variant_ids:
            check_reference(variant_id, ids_by_group["variants"], f"{location} variant_ids")
        if len(variant_ids) != len(set(variant_ids)):
            raise ValueError(f"{location} repeats a variant ID.")

        evidence_ids = claim.get("evidence_ids")
        if not isinstance(evidence_ids, list) or not evidence_ids:
            raise ValueError(f"{location} must have a non-empty evidence_ids list.")
        for evidence_id in evidence_ids:
            check_reference(evidence_id, ids_by_group["evidence"], f"{location} evidence_ids")
            if evidence_id in linked_evidence_ids:
                raise ValueError(f"Evidence {evidence_id} is linked more than once.")
            linked_evidence_ids.add(evidence_id)

    unlinked_evidence = ids_by_group["evidence"] - linked_evidence_ids
    if unlinked_evidence:
        raise ValueError(f"Evidence without a claim: {', '.join(sorted(unlinked_evidence))}")


def validate_demo_seed(seed):
    if not isinstance(seed, dict):
        raise ValueError("The seed must be a JSON object.")
    manifest = seed.get("manifest")
    if not isinstance(manifest, dict) or manifest.get("mode") != "DEMO":
        raise ValueError("Expected a DEMO manifest.")
    if manifest.get("schema_version") != "0.1":
        raise ValueError("Expected schema version 0.1.")
    require_text(manifest, "snapshot_id", "Manifest")

    ids_by_group = index_node_ids(seed)
    for variant in seed["variants"]:
        check_reference(variant.get("gene_id"), ids_by_group["genes"], f"Variant {variant['id']} gene_id")

    validate_claims(seed["claims"], ids_by_group)


def main():
    parser = argparse.ArgumentParser(description="Validate an OncoKG v0.1 demo seed.")
    parser.add_argument(
        "seed_path",
        nargs="?",
        type=Path,
        default=Path(__file__).with_name("seed.json"),
    )
    args = parser.parse_args()

    try:
        with args.seed_path.open(encoding="utf-8") as file:
            seed = json.load(file)
        validate_demo_seed(seed)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Validation failed: {error}\n")

    print(f"Loaded {len(seed['claims'])} claims.")
    print("All demo seed checks passed.")


if __name__ == "__main__":
    main()