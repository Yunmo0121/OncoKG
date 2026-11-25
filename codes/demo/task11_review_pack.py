"""Export a review packet with synthetic cases, evidence citations and blank labels."""
from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path

from benchmark_task07 import sha256_file
from condition_retrieval import ALLOWED_CLAIMS, CASES_FILE, ROOT, load_sources, validate_case
from task07_retrieval_pilot import PILOT, case_fingerprint

REVIEW_CASES = ROOT / "data/benchmarks/task11_synthetic_review_v0_1.json"
INSTRUCTIONS = ROOT / "docs/task11_reviewer_instructions.md"
CASE_FIELDS = (
    "case_id", "synthetic", "cancer_type", "gene", "variants", "age_group", "disease_stage",
    "histology", "treatment_line", "prior_egfr_tki", "prior_treatment_line", "prior_drugs",
    "progression_on_or_after_egfr_tki", "progression_during_first_line_egfr_tki",
    "progression_after_prior_drug", "fda_approved_egfr_test", "fda_approved_t790m_test",
)
ANNOTATION_FIELDS = ("case_id", "claim_id", "label", "reason", "source_location")
TRIAL_LOCATORS = {
    "AURA3-2017-T790M-OVERALL-PFS": "Methods and Results; investigator-assessed PFS",
    "PAO-2005-T790M-GEFITINIB-ERLOTINIB-RESISTANCE": "Results and Table 1; case observations",
}


def read_review_cases(path: Path = REVIEW_CASES) -> tuple[str, list[dict]]:
    payload = json.loads(path.read_text())
    development = json.loads(CASES_FILE.read_text())["cases"]
    pilot = [item["case"] for item in json.loads(PILOT.read_text())["cases"]]
    seen_ids = {case["case_id"] for case in development + pilot}
    seen_contexts = {case_fingerprint(case) for case in development + pilot}
    cases = payload["cases"]
    if not cases:
        raise ValueError("The review set must contain synthetic cases.")
    for case in cases:
        if set(case) != set(CASE_FIELDS):
            raise ValueError("Review cases must use the declared fields and contain no labels.")
        validate_case(case)
        fingerprint = case_fingerprint(case)
        if case["case_id"] in seen_ids or fingerprint in seen_contexts:
            raise ValueError(f"Duplicate or previously used case: {case['case_id']}")
        seen_ids.add(case["case_id"])
        seen_contexts.add(fingerprint)
    return payload["review_set_id"], cases


def source_rows(datasets: tuple[dict, dict]) -> list[dict]:
    rows = []
    for dataset in datasets:
        for claim in dataset["claims"]:
            source = claim.get("source") or claim["evidence"]
            claim_id = claim["id"]
            locator = source.get("locator") or source.get("section") or TRIAL_LOCATORS.get(claim_id)
            if not locator:
                raise ValueError(f"Missing source locator for {claim_id}")
            rows.append({
                "claim_id": claim_id, "claim_type": claim["kind"], "source_title": source["title"],
                "source_url": source.get("url") or source["source_url"], "source_locator": locator,
                "pmid": source.get("pmid", ""), "doi": source.get("doi", ""),
            })
    if len(rows) != len(ALLOWED_CLAIMS) or {row["claim_id"] for row in rows} != ALLOWED_CLAIMS:
        raise ValueError("Unexpected claim inventory.")
    return sorted(rows, key=lambda row: row["claim_id"])


def csv_value(value):
    if value is None:
        return "unknown"
    return value if isinstance(value, str) else json.dumps(value)


def write_csv(path: Path, fields: tuple[str, ...], rows) -> None:
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def export_review_packet(destination: Path) -> dict:
    review_id, cases = read_review_cases()
    base, t790m, hashes = load_sources()
    sources = source_rows((base, t790m))
    destination.mkdir(parents=True, exist_ok=False)
    write_csv(destination / "cases.csv", CASE_FIELDS,
              ({field: csv_value(case[field]) for field in CASE_FIELDS} for case in cases))
    write_csv(destination / "sources.csv", tuple(sources[0]), sources)
    write_csv(destination / "annotation.csv", ANNOTATION_FIELDS,
              ({"case_id": case["case_id"], "claim_id": source["claim_id"]}
               for case in cases for source in sources))
    shutil.copyfile(INSTRUCTIONS, destination / "README.md")
    manifest = {
        "review_set_id": review_id,
        "reference_status": "AWAITING_INDEPENDENT_ANNOTATION",
        "case_count": len(cases), "claim_count": len(sources),
        "annotation_rows": len(cases) * len(sources),
        "oncokg_dataset_sha256": hashes,
        "case_fixture_sha256": sha256_file(REVIEW_CASES),
        "files_sha256": {path.name: sha256_file(path) for path in sorted(destination.iterdir())},
    }
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        manifest = export_review_packet(args.output_dir)
        print(f"Wrote {manifest['annotation_rows']} blank annotation rows to {args.output_dir}.")
    except (KeyError, OSError, TypeError, ValueError) as error:
        parser.exit(1, f"STOP: {error}\n")


if __name__ == "__main__":
    main()
