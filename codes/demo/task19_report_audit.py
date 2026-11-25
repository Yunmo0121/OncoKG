"""Replay and audit a saved Task 18 report, with an optional case comparison."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from benchmark_task07 import sha256_file
from condition_retrieval import ALLOWED_CLAIMS, load_sources, offline_claims
from task07_retrieval_pilot import PILOT, read_cases
from task17_report_context import run_experiment

DEMO_METHODS = ("lexical_bm25", "kg_context_2hop")


def check_fields(actual: dict, expected: dict, location: str) -> None:
    if actual.keys() != expected.keys():
        raise ValueError(f"Field set mismatch at {location}.")
    for field, value in expected.items():
        if json.dumps(actual[field], sort_keys=True) != json.dumps(value, sort_keys=True):
            raise ValueError(f"Replay mismatch at {location}.{field}.")


def verify_report(actual: dict, expected: dict) -> int:
    check_fields({k: v for k, v in actual.items() if k != "methods"},
                 {k: v for k, v in expected.items() if k != "methods"}, "report")
    if actual["methods"].keys() != expected["methods"].keys():
        raise ValueError("Method set mismatch.")
    checked = 0
    for method, batch in expected["methods"].items():
        submitted = actual["methods"][method]
        check_fields({k: v for k, v in submitted.items() if k != "reports"},
                     {k: v for k, v in batch.items() if k != "reports"}, method)
        rows = submitted["reports"]
        if [row["case_id"] for row in rows] != [row["case_id"] for row in batch["reports"]]:
            raise ValueError(f"Case list or order mismatch for {method}.")
        for row, reference in zip(rows, batch["reports"]):
            check_fields(row, reference, f"{method}/{reference['case_id']}")
            checked += 1
    return checked


def render_case(report: dict, case_id: str) -> str:
    lines = [
        f"# OncoKG retrieval report comparison — {case_id}", "",
        f"Synthetic development case. Evidence limit: {report['k']}.", "",
        "Context statuses and flags below are prototype outputs for research review.", "",
    ]
    for name, method in zip(("BM25", "KG context ranking (2 hops)"), DEMO_METHODS):
        row = next((r for r in report["methods"][method]["reports"] if r["case_id"] == case_id), None)
        if row is None:
            raise ValueError(f"Unknown development case: {case_id}.")
        lines.extend([f"## {name}", "", "| Rank | Evidence claim | Context status | Sources |",
                      "| ---: | --- | --- | --- |"])
        for position, item in enumerate(row["evidence"], 1):
            links = [f"[Primary {i}]({url})" for i, url in enumerate(item["source_urls"], 1)]
            links.extend(f"[CIViC supplement, PFS only, pending review]({link['url']})"
                         for link in item["supplemental_source_links"])
            lines.append(f"| {position} | `{item['claim_id']}` | `{item['context_status']}` | {', '.join(links)} |")
        if not row["evidence"]:
            lines.extend(["", "No evidence was retrieved."])
        lines.extend(["", "### Research review flags", ""])
        lines.extend([
            f"- `{flag['flag']}` for {flag['drug_mentioned_not_recommended']} "
            f"(support: {', '.join(flag['supporting_claim_ids'])})."
            for flag in row["research_review_flags"]
        ] or ["No research review flag is supported by this report's retrieved evidence."])
        lines.extend(["", "### Missing fields", ""])
        lines.extend([f"- `{item['claim_id']}` · {item['check']}" for item in row["missing_information"]]
                     or ["No missing-field check was displayed within the retrieved evidence."])
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rankings", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--demo-output", type=Path)
    parser.add_argument("--case-id", default="SYN-PILOT-03")
    args = parser.parse_args()
    try:
        raw = args.rankings.read_bytes()
        actual = json.loads(args.report.read_bytes())
        k = actual["k"]
        if type(k) is not int or not 1 <= k <= len(ALLOWED_CLAIMS):
            raise ValueError("Evidence limit is outside the claim inventory.")
        base, t790m, hashes = load_sources()
        expected = run_experiment(json.loads(raw), read_cases(), offline_claims(base, t790m),
                                  hashes, sha256_file(PILOT), k, include_review_details=True)
        expected["task15_report_sha256"] = hashlib.sha256(raw).hexdigest()
        checked = verify_report(actual, expected)
        if args.demo_output:
            rendered = render_case(expected, args.case_id)
            args.demo_output.parent.mkdir(parents=True, exist_ok=True)
            with args.demo_output.open("x", encoding="utf-8") as output:
                output.write(rendered)
        print(f"Report replay passed: {checked} case-method reports.")
    except (OSError, KeyError, TypeError, ValueError, AttributeError) as error:
        parser.exit(1, f"STOP: {error}\n")


if __name__ == "__main__":
    main()
