"""OncoKG Task 06A: deterministic mock generation over Task 04/05 outputs.

Not a real LLM. Research-only. SYNTHETIC cases only. Read-only database mode.
No treatment recommendations, eligibility judgements, or drug safety clearance.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from safety_triage import (
    evidence_triage,
    get_report,
    inspect_task04_report,
    load_case,
)

PIPELINE_VERSION = "ONCOKG-TASK06A-MOCK-STRUCTURED-REPORT-V0.1"
STATUS_MEANINGS = {
    "CONTEXT_MATCHED": "This synthetic case matches the prototype's recorded claim context; this does not establish clinical suitability.",
    "NOT_MATCHED": "At least one stated condition in the prototype differs from this claim's context.",
    "NEEDS_INFORMATION": "One or more required data fields were not supplied or are unknown.",
    "NOT_EVALUATED": "No sufficiently specific validated matching rule is available for this claim.",
}


def build_mock_report(case: dict, task04: dict, task05: dict) -> dict:
    """Produce an auditable JSON report exclusively from verified upstream facts."""
    inspect_task04_report(case, task04)
    if task05.get("case_id") != case["case_id"] or task05.get("synthetic") is not True:
        raise ValueError("Task 05 report does not match this synthetic case.")
    if task05.get("task04_data_origin") != task04.get("data_origin"):
        raise ValueError("Mismatched Task 04/05 data origins.")
    if task05.get("policy_id") != "ONCOKG-TASK05-RESEARCH-EVIDENCE-TRIAGE-V0.1":
        raise ValueError("Unexpected Task 05 policy version.")
    if task05.get("auto_exclusions") != [] or task05.get("candidate_treatments_generated") != []:
        raise ValueError("This mock stage forbids automatic exclusions or treatment generation.")

    claims = []
    for item in sorted(task04["results"], key=lambda r: r["claim_id"]):
        if item["status"] not in STATUS_MEANINGS:
            raise ValueError("Unsupported evidence-context status.")
        claims.append({
            "claim_id": item["claim_id"],
            "claim_type": item["claim_type"],
            "context_status": item["status"],
            "status_explanation": STATUS_MEANINGS[item["status"]],
            "drugs_mentioned_not_recommended": list(item["drugs_mentioned_not_recommended"]),
            "source_urls": list(item["source_urls"]),
            "matching_checks": list(item["checks"]),
            "review_status": item["curation_status"],
        })
    flags = []
    for item in sorted(task05["drug_mentions_for_research_review"], key=lambda x: x["drug_mentioned_not_recommended"]):
        if item.get("automatic_exclusion") is not False or item.get("cleared_as_safe") is not False or item.get("recommended") is not False:
            raise ValueError("Task 05 contains an unsupported drug clearance, exclusion or recommendation.")
        flags.append({
            "drug_mentioned_not_recommended": item["drug_mentioned_not_recommended"],
            "flag": item["research_flag"],
            "explanation": item["flag_explanation"],
            "supporting_claim_ids": [x["claim_id"] for x in item["evidence_claims"]],
        })
    claim_ids = {x["claim_id"] for x in claims}
    if any(not set(f["supporting_claim_ids"]) <= claim_ids for f in flags):
        raise ValueError("A drug flag cites a claim outside the verified evidence set.")

    counts = {status: sum(x["context_status"] == status for x in claims) for status in STATUS_MEANINGS}
    missing = [
        {"claim_id": claim["claim_id"], "check": msg}
        for claim in claims
        for msg in claim["matching_checks"]
        if msg.startswith("MISSING")
    ]
    lines = [
        f"Synthetic case {case['case_id']}: {len(claims)} versioned research claims inspected.",
        ("Context status counts: " + ", ".join(f"{k}={counts[k]}" for k in STATUS_MEANINGS) + "."),
    ]
    for c in claims:
        lines.append(f"[{c['claim_id']}] {c['claim_type']}: {c['context_status']}.")
    for f in flags:
        lines.append(f"Evidence-triage flag for {f['drug_mentioned_not_recommended']}: {f['flag']} (not a treatment recommendation).")
    lines.extend([
        "No drug was recommended, automatically excluded, or cleared as safe.",
        "The evidence corpus is small and not independently clinically reviewed; contraindication and interaction checks are not implemented.",
    ])
    return {
        "pipeline_version": PIPELINE_VERSION,
        "case_id": case["case_id"],
        "synthetic": True,
        "research_only": True,
        "generation_mode": "DETERMINISTIC_MOCK_NO_LLM",
        "llm_api_called": False,
        "input_origin": task04["data_origin"],
        "evidence_claim_count": len(claims),
        "status_counts": counts,
        "evidence_claims": claims,
        "missing_information": missing,
        "safety_evidence_flags": flags,
        "screening_coverage": dict(task05["screening_coverage"]),
        "automatic_exclusions": [],
        "treatment_recommendations": [],
        "safety_clearances": [],
        "mock_summary_lines": lines,
        "limitations": list(task05["limitations"]),
        "disclaimer": "RESEARCH PROTOTYPE — SYNTHETIC DATA ONLY; NOT MEDICAL ADVICE OR A CLINICAL DECISION SUPPORT SYSTEM.",
    }


def build_future_llm_payload(report: dict) -> dict:
    """A *local artifact* for a future adapter; does not call or configure an API."""
    if report.get("generation_mode") != "DETERMINISTIC_MOCK_NO_LLM" or not report.get("synthetic"):
        raise ValueError("Only validated synthetic mock reports can be converted to a future LLM payload.")
    return {
        "schema_version": "ONCOKG-LLM-INPUT-DRAFT-V0.1",
        "send_to_external_api": False,
        "instructions": [
            "Use only the supplied claim IDs, context statuses, source URLs, and screening limitations.",
            "Never infer a patient-level treatment recommendation, eligibility, safe-drug clearance or contraindication.",
            "Distinguish matched context from clinical safety and from efficacy.",
            "Explicitly state missing information and unimplemented safety screening.",
            "If evidence is absent, say not evaluated; do not fabricate evidence or citations.",
            "Output a structured research evidence summary for a SYNTHETIC example only.",
        ],
        "case_id": report["case_id"],
        "claim_evidence": report["evidence_claims"],
        "triage_flags": report["safety_evidence_flags"],
        "missing_information": report["missing_information"],
        "limitations": report["limitations"],
    }


def format_markdown(report: dict) -> str:
    lines = [
        "# OncoKG — Mock Evidence Report (SYNTHETIC)",
        "",
        f"- Case: `{report['case_id']}`",
        f"- Source mode: `{report['input_origin']}`",
        "- Generator: **Deterministic mock (no LLM call)**",
        "- Clinical use: **Not permitted**",
        "",
        "## Context evidence",
        "",
    ]
    for c in report["evidence_claims"]:
        lines.extend([
            f"### `{c['claim_id']}`",
            f"- Claim: `{c['claim_type']}`; status: **{c['context_status']}**",
            f"- Meaning: {c['status_explanation']}",
            "- Sources: " + ", ".join(c["source_urls"]),
            "",
        ])
    lines.append("## Safety evidence flags (not prescriptions)")
    lines.append("")
    for flag in report["safety_evidence_flags"]:
        lines.append(f"- `{flag['drug_mentioned_not_recommended']}` — `{flag['flag']}`; {flag['explanation']}")
    lines.extend([
        "", "## Limitations", "",
        *(f"- {item}" for item in report["limitations"]),
        "", f"**{report['disclaimer']}**", "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Task 06A: deterministic mock of a research evidence report; synthetic cases only")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--offline", action="store_true", help="Use local curated JSON without Neo4j")
    mode.add_argument("--db", action="store_true", help="Read-only verified OncoKG-Real")
    parser.add_argument("--case-id", default="SYN-T790M-001")
    parser.add_argument("--output", type=Path, help="Optional local JSON path")
    parser.add_argument("--markdown", type=Path, help="Optional local Markdown report path")
    parser.add_argument("--prompt-json", type=Path, help="Optional future-LLM payload saved locally; does not send")
    parser.add_argument("--uri", default="bolt://localhost:7687")
    parser.add_argument("--username", default="neo4j")
    parser.add_argument("--database", default="neo4j")
    args = parser.parse_args()
    try:
        case = load_case(args.case_id)
        task04 = get_report(case, args.db, args.uri, args.username, args.database)
        task05 = evidence_triage(case, task04)
        report = build_mock_report(case, task04, task05)
        print(f"MOCK REPORT PASS: {report['case_id']}; {report['evidence_claim_count']} evidence claims; "+
              f"origin={report['input_origin']}.")
        for line in report["mock_summary_lines"]:
            print("  " + line)
        for dest, content in (
            (args.output, json.dumps(report, indent=2, ensure_ascii=False) + "\n"),
            (args.markdown, format_markdown(report)),
            (args.prompt_json, json.dumps(build_future_llm_payload(report), indent=2, ensure_ascii=False) + "\n"),
        ):
            if dest is not None:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(content, encoding="utf-8")
                print(f"Saved local artifact: {dest}")
        print("No LLM API call. No Neo4j writes. No medication recommendation or safety clearance.")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        parser.exit(1, f"STOP: {exc}\n")
    except Exception as exc:
        parser.exit(1, f"DATABASE/DRIVER ERROR: {type(exc).__name__}: {exc}\n")


if __name__ == "__main__":
    main()
