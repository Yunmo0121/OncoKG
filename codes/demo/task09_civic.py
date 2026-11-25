"""Stage four CIViC records as research-only candidates against the v0.2 graph."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from collections import defaultdict
from pathlib import Path

from condition_retrieval import load_sources

RELEASE = "01-Nov-2026"
DOWNLOAD_ROOT = f"https://civicdb.org/downloads/{RELEASE}"
SNAPSHOTS = {
    "ClinicalEvidenceSummaries": "cd0a120b3d1e31bc2237733efa0cb58c4bb9302c34817f926b2caf595aeb615c",
    "MolecularProfileSummaries": "8487655f3cad586e8de0cc127d01648c7f4b136566cbf389f6d9c122ad041e95",
    "VariantSummaries": "5b52465b9f6b4c4bc2083f03ed606319e0c1e0bb67cc93383627f6598c76051c",
}
EVIDENCE_IDS = {"963", "1867", "2158", "4294"}
VARIANTS = {"33": "L858R", "34": "T790M"}
DRUGS = {"erlotinib": "DRUG:ERLOTINIB", "gefitinib": "DRUG:GEFITINIB",
         "osimertinib": "DRUG:OSIMERTINIB"}


def snapshot_name(table: str) -> str:
    return f"{RELEASE}-{table}.tsv"


def read_selected_rows(directory: Path, table: str, id_column: str, ids: set[str]) -> dict:
    filename = snapshot_name(table)
    content = (directory / filename).read_bytes()
    if hashlib.sha256(content).hexdigest() != SNAPSHOTS[table]:
        raise ValueError(f"Unexpected SHA-256 for {filename}. Use the reviewed snapshot.")
    rows = {}
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")), delimiter="\t",
                            quoting=csv.QUOTE_NONE)
    for row in reader:
        row_id = row[id_column]
        if row_id in ids:
            if row_id in rows or None in row or None in row.values():
                raise ValueError(f"Duplicate or malformed row {row_id} in {filename}.")
            rows[row_id] = row
    if rows.keys() != ids:
        raise ValueError(f"Selected IDs missing from {filename}: {sorted(ids - rows.keys())}")
    return rows


def normalize_candidate(row: dict, profile: dict, variant: dict, claim_ids_by_pmid: dict) -> dict:
    evidence_id = row["evidence_id"]
    if (row["doid"] != "3908" or row["evidence_type"] != "Predictive"
            or row["evidence_status"] != "accepted" or row["is_flagged"] != "false"
            or row["source_type"] != "PubMed" or not row["citation_id"].isdigit()):
        raise ValueError(f"CIViC evidence {evidence_id} is outside the pilot scope.")

    profile_id = row["molecular_profile_id"]
    variant_id = variant["variant_id"]
    protein = VARIANTS.get(variant_id)
    if (protein is None or profile["variant_ids"] != variant_id
            or variant["feature_type"] != "Gene" or variant["feature_name"] != "EGFR"
            or variant["entrez_id"] != "1956" or variant["variant"] != protein
            or profile["molecular_profile_id"] != profile_id
            or variant["single_variant_molecular_profile_id"] != profile_id
            or row["molecular_profile"] != profile["name"]
            or profile["is_flagged"] != "false" or variant["is_flagged"] != "false"):
        raise ValueError(f"CIViC evidence {evidence_id} has no verified single-variant EGFR mapping.")

    therapies = [name.strip() for name in row["therapies"].split(",")]
    if not all(name.casefold() in DRUGS for name in therapies):
        raise ValueError(f"Unmapped therapy in CIViC evidence {evidence_id}.")
    if row["evidence_civic_url"] != f"https://civicdb.org/links/evidence_items/{evidence_id}":
        raise ValueError(f"Unexpected source URL for CIViC evidence {evidence_id}.")
    pmid = row["citation_id"]

    return {
        "candidate_id": f"CIViC:EID{evidence_id}",
        "review_status": "PENDING_ONCOKG_REVIEW",
        "mapping": {
            "gene_id": "GENE:EGFR", "hgnc_id": "HGNC:3236",
            "variant_id": f"VARIANT:EGFR:{protein}", "disease_id": "DISEASE:NSCLC",
            "disease_ontology_id": "DOID:3908",
            "drug_ids": sorted({DRUGS[name.casefold()] for name in therapies}),
        },
        "source": {
            "civic_url": row["evidence_civic_url"], "civic_evidence_id": evidence_id,
            "civic_molecular_profile_id": profile_id, "civic_variant_id": variant_id,
            **{field: row[field] for field in (
                "molecular_profile", "disease", "therapies", "therapy_interaction_type",
                "evidence_type", "evidence_level", "evidence_direction", "significance",
                "variant_origin", "evidence_status", "is_flagged", "last_review_date",
            )},
        },
        "publication": {
            "pmid": pmid, "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            "citation": row["citation"],
            "same_pmid_oncokg_claim_ids": sorted(claim_ids_by_pmid.get(pmid, [])),
        },
    }


def build_report(directory: Path) -> dict:
    base, incremental, anchor_hashes = load_sources()
    claim_ids_by_pmid = defaultdict(list)
    for dataset in (base, incremental):
        for claim in dataset["claims"]:
            citation = claim.get("source") or claim["evidence"]
            if citation.get("pmid"):
                claim_ids_by_pmid[str(citation["pmid"])].append(claim["id"])

    evidence = read_selected_rows(directory, "ClinicalEvidenceSummaries", "evidence_id", EVIDENCE_IDS)
    profiles = read_selected_rows(directory, "MolecularProfileSummaries", "molecular_profile_id",
                                 {row["molecular_profile_id"] for row in evidence.values()})
    variants = read_selected_rows(directory, "VariantSummaries", "variant_id", set(VARIANTS))
    candidates = []
    by_pmid = defaultdict(list)
    for eid in sorted(evidence, key=int):
        row = evidence[eid]
        profile = profiles[row["molecular_profile_id"]]
        if eid not in {value.strip() for value in profile["evidence_item_ids"].split(",")}:
            raise ValueError(f"CIViC molecular profile does not link to evidence {eid}.")
        variant = variants.get(profile["variant_ids"])
        if variant is None:
            raise ValueError(f"CIViC evidence {eid} has no verified single-variant EGFR mapping.")
        candidate = normalize_candidate(row, profile, variant, claim_ids_by_pmid)
        candidates.append(candidate)
        by_pmid[candidate["publication"]["pmid"]].append(candidate["candidate_id"])

    return {
        "research_only": True, "release": RELEASE,
        "input_files": {table: {"url": f"{DOWNLOAD_ROOT}/{snapshot_name(table)}", "sha256": digest}
                        for table, digest in SNAPSHOTS.items()},
        "oncokg_dataset_sha256": anchor_hashes,
        "candidates": candidates,
        "shared_pmid_between_candidates": {pmid: ids for pmid, ids in by_pmid.items() if len(ids) > 1},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True,
                        help="Directory containing the three pinned CIViC TSV files.")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = json.dumps(build_report(args.input_dir), indent=2, sort_keys=True)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as output:
                output.write(result + "\n")
        else:
            print(result)
    except (OSError, ValueError, KeyError, csv.Error) as error:
        parser.exit(1, f"STOP: {error}\n")


if __name__ == "__main__":
    main()
