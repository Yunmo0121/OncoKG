"""Replay evidence selection with a declared primary synthetic outcome."""
from task23_review_support import K
from task25_trial_applicability import build_applicability_report, demo_input, find_applicability_checks


def run_case(primary_outcome):
    _, candidates, trusted = demo_input("SYN-30", "A")
    ranking = ["outcome_a", "outcome_b", "review", "eligibility"]
    checks = find_applicability_checks({"synthetic": True, "prior_exposure": "X"}, candidates)
    baseline = ranking[:K]
    outcomes = [row for row in baseline if candidates[row]["claim_type"] == "TRIAL_OUTCOME"]
    if primary_outcome is not None and primary_outcome not in outcomes:
        raise ValueError("The declared primary outcome must be a displayed trial outcome.")
    selected = baseline
    decision = "OUTCOME_PRIORITY_UNSPECIFIED"
    if primary_outcome is not None:
        selected = [row for row in ranking if row == primary_outcome or row not in outcomes]
        decision = "DECLARED_PRIORITY_APPLIED"
    return {
        "decision": decision,
        "omitted": [row for row in ranking if row not in selected],
        "report": build_applicability_report(trusted, selected, checks),
    }


if __name__ == "__main__":
    for primary in ("outcome_a", "outcome_b", None):
        result = run_case(primary)
        report = result["report"]
        print(primary, result["decision"], [r["claim_id"] for r in report["evidence"]],
              result["omitted"], len(report["applicability_checks"]), len(report["research_review_flags"]))
