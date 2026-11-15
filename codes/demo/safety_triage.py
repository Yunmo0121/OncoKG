"""OncoKG Task 05: conservative, research-only evidence triage for SYNTHETIC cases.

Builds on Task 04's validated Claim matching. There are NO clinically
reviewed absolute-contraindication rules in the current v0.2 graph, so this
module deliberately NEVER blocks, clears, ranks or recommends any drug.

--offline: local curated JSON only; --db: Task 04's verified read-only Neo4j.
"""
from __future__ import annotations

import argparse
import json
from getpass import getpass
from pathlib import Path

from condition_retrieval import (
    ALLOWED_CLAIMS, CASES_FILE, evaluate, load_sources, offline_claims,
    read_db_tx, validate_case, verify_against_curated,
)

POLICY_ID = "ONCOKG-TASK05-RESEARCH-EVIDENCE-TRIAGE-V0.1"
RESISTANCE_CLAIM = "PAO-2005-T790M-GEFITINIB-ERLOTINIB-RESISTANCE"
EXPECTED_DRUG_MENTIONS = {"osimertinib", "gefitinib", "erlotinib"}
VALID_STATUSES = {"CONTEXT_MATCHED", "NEEDS_INFORMATION", "NOT_MATCHED", "NOT_EVALUATED"}


def load_case(case_id: str, cases_path: Path = CASES_FILE) -> dict:
    cases_json = json.loads(cases_path.read_text(encoding="utf-8"))
    cases = cases_json["cases"]
    found = [case for case in cases if case.get("case_id") == case_id]
    if len(found) != 1:
        raise ValueError(f"Expected exactly one synthetic case with ID {case_id!r}.")
    validate_case(found[0])
    return found[0]


def inspect_task04_report(case: dict, report: dict) -> None:
    """Fail closed when any upstream evidence inventory or provenance is missing."""
    validate_case(case)
    if report.get("case_id") != case["case_id"] or report.get("synthetic") is not True:
        raise ValueError("Synthetic case identity or provenance mismatch.")
    if report.get("research_only") is not True:
        raise ValueError("Task 04 report is not marked research-only.")
    rows = report.get("results")
    if not isinstance(rows, list) or len(rows) != 5:
        raise ValueError("Expected five validated Task 04 evidence Claim results.")
    ids = [x.get("claim_id") for x in rows]
    if set(ids) != ALLOWED_CLAIMS or len(set(ids)) != len(ids):
        raise ValueError("Unexpected/duplicate/missing Claim IDs: refuse safety triage.")
    for item in rows:
        if item.get("status") not in VALID_STATUSES:
            raise ValueError("Unrecognised Task 04 context status.")
        if item.get("curation_status") != "source_checked_needs_independent_review":
            raise ValueError("Unexpected evidence review status.")
        urls = item.get("source_urls")
        if not isinstance(urls, list) or len(urls) != 1 or not urls[0].startswith("https://"):
            raise ValueError("Missing or invalid evidence source URL.")
        drugs = item.get("drugs_mentioned_not_recommended")
        if not isinstance(drugs, list) or not drugs or any(d not in EXPECTED_DRUG_MENTIONS for d in drugs):
            raise ValueError("Unexpected evidence drug inventory.")
    resistance = next(x for x in rows if x["claim_id"] == RESISTANCE_CLAIM)
    if resistance["claim_type"] != "RESISTANCE_ASSOCIATION" or set(resistance["drugs_mentioned_not_recommended"]) != {"gefitinib", "erlotinib"}:
        raise ValueError("T790M association is missing/changed: refuse safety triage.")


def evidence_triage(case: dict, context_report: dict) -> dict:
    """Describe evidence signals, not drug safety or clinical eligibility."""
    inspect_task04_report(case, context_report)
    statuses = {r["claim_id"]: r for r in context_report["results"]}
    resistance = statuses[RESISTANCE_CLAIM]
    prior = case.get("prior_drugs")
    prior_normalized = None if prior is None else {d.strip().lower() for d in prior}

    rows = []
    for drug in sorted(EXPECTED_DRUG_MENTIONS):
        relevant = [r for r in context_report["results"] if drug in r["drugs_mentioned_not_recommended"]]
        if drug in {"gefitinib", "erlotinib"}:
            if resistance["status"] == "CONTEXT_MATCHED":
                flag = "RESISTANCE_ASSOCIATION_REVIEW"
                meaning = "Historical resistance association applies to the modelled case context; request expert review. Not an absolute contraindication."
            elif resistance["status"] == "NEEDS_INFORMATION":
                flag = "RESISTANCE_CONTEXT_INCOMPLETE"
                meaning = "Missing information prevents evaluation of the historical resistance association; not evidence of safety."
            elif resistance["status"] == "NOT_MATCHED":
                flag = "RESISTANCE_CLAIM_CONTEXT_NOT_MATCHED"
                meaning = "This particular historical association's prototype conditions do not match; other resistance risks were not assessed."
            else:
                flag = "RESISTANCE_NOT_EVALUATED"
                meaning = "No validated case-specific resistance interpretation was established."
        else:
            flag = "SAFETY_NOT_ASSESSED"
            meaning = "There is contextual FDA/trial evidence, but this prototype contains no comprehensive safety screen or contraindication rules."

        rows.append({
            "drug_mentioned_not_recommended": drug,
            "research_flag": flag,
            "flag_explanation": meaning,
            "recorded_prior_exposure": (None if prior_normalized is None else drug in prior_normalized),
            "evidence_claims": [
                {"claim_id": r["claim_id"], "claim_type": r["claim_type"],
                 "context_status": r["status"], "source_urls": list(r["source_urls"])}
                for r in sorted(relevant, key=lambda x: x["claim_id"])
            ],
            "automatic_exclusion": False,
            "cleared_as_safe": False,
            "recommended": False,
        })

    return {
        "policy_id": POLICY_ID,
        "case_id": case["case_id"],
        "synthetic": True,
        "research_only": True,
        "task04_data_origin": context_report["data_origin"],
        "evidence_inventory_claims": len(statuses),
        "screening_coverage": {
            "resistance_association": "LIMITED_HISTORICAL_CLAIM_GEFITINIB_ERLOTINIB_ONLY",
            "absolute_contraindications": "NOT_IMPLEMENTED_NO_REVIEWED_RULES",
            "drug_drug_interactions": "NOT_IMPLEMENTED_NO_REVIEWED_RULES",
            "organ_function_and_comorbidities": "NOT_IMPLEMENTED",
            "current_guideline_reconciliation": "NOT_IMPLEMENTED",
        },
        "auto_exclusions": [],
        "candidate_treatments_generated": [],
        "drug_mentions_for_research_review": rows,
        "limitations": [
            "Only five source-checked-but-not-independently-reviewed claims are available.",
            "No reviewed absolute contraindication or drug interaction dataset has been integrated.",
            "Matched evidence context is not individual eligibility, safety clearance or a recommendation.",
            "T790M does not establish resistance to every EGFR-targeting drug.",
        ],
        "disclaimer": "SYNTHETIC RESEARCH CASE ONLY. NOT medical advice, prescription, CDSS or patient-level drug selection.",
    }


def get_report(case: dict, use_db: bool, uri: str, username: str, database: str) -> dict:
    base, t790m, hashes = load_sources()
    preview = offline_claims(base, t790m)
    if not use_db:
        records = preview
        origin = "offline_curated_json_preview_NO_NEO4J_QUERY"
    else:
        # This uses Task 04's checks for SHA256, counts and exact Claim inventory.
        # The query is read-only. No Neo4j CREATE/SET/MERGE/DELETE is executed.
        from neo4j import GraphDatabase
        with GraphDatabase.driver(uri, auth=(username, getpass("Password for OncoKG-Real: "))) as driver:
            driver.verify_connectivity()
            with driver.session(database=database) as session:
                records = session.execute_read(read_db_tx, hashes)
        verify_against_curated(records, preview)
        origin = "verified_neo4j_oncokg_real_read_only"
    return evaluate(case, records, origin)


def main() -> None:
    parser = argparse.ArgumentParser(description="Research-only evidence triage on synthetic NSCLC cases")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--offline", action="store_true", help="Local curated data only")
    mode.add_argument("--db", action="store_true", help="Read-only verified OncoKG-Real query")
    parser.add_argument("--case-id", default="SYN-T790M-001")
    parser.add_argument("--cases", type=Path, default=CASES_FILE)
    parser.add_argument("--output", type=Path, help="Optional locally saved JSON report")
    parser.add_argument("--uri", default="bolt://localhost:7687")
    parser.add_argument("--username", default="neo4j")
    parser.add_argument("--database", default="neo4j")
    args = parser.parse_args()
    try:
        case = load_case(args.case_id, args.cases)
        task04 = get_report(case, args.db, args.uri, args.username, args.database)
        report = evidence_triage(case, task04)
        print(f"PASS: Task 05 evidence triage for {case['case_id']} ({report['task04_data_origin']}).")
        print(f"Claims checked: {report['evidence_inventory_claims']}; automatic exclusions: 0 (no reviewed contraindication rules).")
        for item in report["drug_mentions_for_research_review"]:
            print(f"  {item['drug_mentioned_not_recommended']:<15} {item['research_flag']}")
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"Local report saved: {args.output}")
        print("No Neo4j writes. NO drug was deemed safe, recommended or automatically excluded.")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        parser.exit(1, f"STOP: {exc}\n")
    except Exception as exc:
        parser.exit(1, f"DATABASE/DRIVER ERROR: {type(exc).__name__}: {exc}\n")


if __name__ == "__main__":
    main()
