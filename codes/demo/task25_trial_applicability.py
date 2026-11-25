"""Compare trial applicability policies on a fixed synthetic report budget."""
from __future__ import annotations

import argparse
from pathlib import Path

from task13_evaluation import write_json
from task17_report_context import build_ranked_report
from task23_review_support import K, select_with_review_support

CONFLICT = "ELIGIBILITY_CONFLICT"
MISSING = "CASE_INFORMATION_MISSING"
UNRESOLVED = "POPULATION_UNRESOLVED"
OUTSIDE_REPORT = "LIMIT_SOURCE_OUTSIDE_REPORT"
LINKED_STATUSES = {CONFLICT, MISSING}
STATUS_PRIORITY = (CONFLICT, MISSING, UNRESOLVED, OUTSIDE_REPORT)


def find_applicability_checks(case: dict, candidates: dict[str, dict]) -> list[dict]:
    """Join structured trial metadata and evaluate a categorical exclusion."""
    if case.get("synthetic") is not True:
        raise ValueError("Expected an explicitly synthetic case.")
    outcomes = [row for row in candidates.values() if row["claim_type"] == "TRIAL_OUTCOME"]
    checks = []
    for criterion in candidates.values():
        if (criterion["claim_type"] != "TRIAL_EXCLUSION"
                or not criterion.get("trial_id") or not criterion.get("case_field")
                or not criterion.get("excluded_value")
                or not any(url.startswith("https://") for url in criterion.get("source_urls", []))):
            continue
        for outcome in outcomes:
            if outcome.get("trial_id") != criterion["trial_id"]:
                continue
            criterion_population = criterion.get("population_id")
            outcome_population = outcome.get("population_id")
            field = criterion["case_field"]
            value = case.get(field)
            if not criterion_population or not outcome_population:
                status = UNRESOLVED
            elif criterion_population != outcome_population:
                continue
            elif value is None:
                status = MISSING
            elif value == criterion["excluded_value"]:
                status = CONFLICT
            else:
                continue
            checks.append({
                "outcome_id": outcome["claim_id"], "criterion_id": criterion["claim_id"],
                "status": status, "case_field": field,
            })
    return checks


def protection_map(checks: list[dict]) -> dict[str, set[str]]:
    protected = {}
    for check in checks:
        if check["status"] in LINKED_STATUSES:
            protected.setdefault(check["criterion_id"], set()).add(check["outcome_id"])
    return protected


def qualification(check: dict) -> str:
    status = check["status"]
    if status == CONFLICT:
        return (f"The sourced trial exclusion for {check['case_field']} limits direct applicability "
                "to this synthetic case.")
    if status == MISSING:
        return f"Trial applicability is unresolved. Verify the missing case field {check['case_field']}."
    if status == UNRESOLVED:
        return "Trial applicability is unresolved. Verify the outcome-to-population mapping."
    return "Trial applicability is unresolved. The eligibility source is outside this report."


def build_applicability_report(
    trusted: dict, selected: list[str], checks: list[dict], *, budget: int = K,
) -> dict:
    """Qualify visible outcomes and cite only sources in the bounded report."""
    if type(budget) is not int or budget < 1:
        raise ValueError("Evidence budget must be a positive integer.")
    rows = {row["claim_id"]: row for row in trusted["evidence_claims"]}
    visible = set(selected[:budget])
    visible_checks = {}
    for check in checks:
        if check["outcome_id"] not in visible:
            continue
        item = check.copy()
        if check["criterion_id"] in visible:
            item["source_urls"] = rows[check["criterion_id"]]["source_urls"]
        else:
            item.pop("criterion_id")
            item.pop("case_field")
            if check["status"] in LINKED_STATUSES:
                item["status"] = OUTSIDE_REPORT
        if item["status"] == UNRESOLVED:
            item.pop("case_field", None)
        visible_checks.setdefault(item["outcome_id"], []).append(item)

    projected = []
    for row in rows.values():
        notes = visible_checks.get(row["claim_id"], [])
        if notes:
            messages = [qualification(note) for note in notes]
            status = min((note["status"] for note in notes), key=STATUS_PRIORITY.index)
            # Qualify the rendered outcome while preserving the input matcher result.
            row = dict(row, context_status=status,
                       status_explanation=" ".join(dict.fromkeys(messages)))
        projected.append(row)
    report = build_ranked_report(dict(trusted, evidence_claims=projected), selected, budget,
                                 include_review_details=True)
    report["applicability_checks"] = [item for items in visible_checks.values() for item in items]
    return report


def demo_input(case_id: str, population: str | None) -> tuple[list[str], dict[str, dict], dict]:
    primary = ["outcome_a", "outcome_b", "eligibility"]
    rows = {}
    for claim_id, kind, status, explanation in (
        ("outcome_a", "TRIAL_OUTCOME", "CONTEXT_MATCHED", "First outcome from the synthetic trial."),
        ("outcome_b", "TRIAL_OUTCOME", "CONTEXT_MATCHED", "Second outcome from the synthetic trial."),
        ("eligibility", "TRIAL_EXCLUSION", "NOT_EVALUATED", "The eligibility document excludes exposure X."),
        ("review", "RESISTANCE_ASSOCIATION", "CONTEXT_MATCHED", "Synthetic review evidence."),
    ):
        rows[claim_id] = {
            "claim_id": claim_id, "claim_type": kind, "context_status": status,
            "status_explanation": explanation, "source_urls": [f"https://example.org/{claim_id}"],
            "review_status": "synthetic_fixture",
        }
    for claim_id in ("outcome_a", "outcome_b"):
        rows[claim_id].update(trial_id="SYN-TRIAL", population_id="A")
    rows["eligibility"].update(trial_id="SYN-TRIAL", population_id=population,
                               case_field="prior_exposure", excluded_value="X")
    trusted = {
        "case_id": case_id, "limitations": [], "disclaimer": "Synthetic research fixture",
        "evidence_claims": list(rows.values()), "missing_information": [],
        "safety_evidence_flags": [{"flag": "RESISTANCE_ASSOCIATION_REVIEW", "supporting_claim_ids": ["review"]}],
    }
    return primary, rows, trusted


def run_demo(*, include_inputs: bool = False) -> dict:
    fixtures = [
        ("SYN-25-CONFLICT", "A", "X", True),
        ("SYN-25-OTHER-POPULATION", "B", "X", False),
        ("SYN-25-MISSING-EXPOSURE", "A", None, True),
        ("SYN-25-UNKNOWN-POPULATION", None, "X", False),
        ("SYN-25-NO-CONFLICT", "A", "Y", False),
    ]
    cases = []
    for case_id, population, exposure, limit_expected in fixtures:
        primary, rows, trusted = demo_input(case_id, population)
        case = {"synthetic": True, "prior_exposure": exposure}
        checks = find_applicability_checks(case, rows)
        manual_links = {"eligibility": {"outcome_a", "outcome_b"}} if limit_expected else {}
        expected_links = {("eligibility", outcome) for outcome in manual_links.get("eligibility", set())}
        comparisons = {}
        for method, links in (("task23", {}), ("task24_manual", manual_links), ("task25", protection_map(checks))):
            selected, decisions = select_with_review_support(primary, list(rows), rows, applicability_limits=links)
            report = (build_applicability_report(trusted, selected, checks) if method == "task25"
                      else build_ranked_report(trusted, selected, K, include_review_details=True))
            retained_links = {(criterion, outcome) for criterion, outcomes in links.items() for outcome in outcomes
                              if criterion in selected and outcome in selected}
            comparisons[method] = {
                "selected": selected, "displaced": [claim for claim in primary if claim not in selected],
                "missed_limit_links": sorted(expected_links - retained_links),
                "extra_limit_links": sorted(retained_links - expected_links),
                "review_support_retained": bool(report["research_review_flags"]),
                "decisions": decisions, "report": report,
            }
        result = {"case_id": case_id, "methods": comparisons}
        if include_inputs:
            result["inputs"] = {"case": case, "initial_ranking": primary, "candidates": list(rows.values())}
        cases.append(result)
    return {"synthetic": True, "official_evaluation": False, "k": K, "cases": cases}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        write_json(args.output, run_demo())
    except OSError as error:
        parser.exit(1, f"STOP: {error}\n")


if __name__ == "__main__":
    main()
