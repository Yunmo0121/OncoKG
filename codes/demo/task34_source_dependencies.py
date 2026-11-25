"""Test full-source retention on small synthetic rankings."""
from itertools import combinations

from task25_trial_applicability import (
    CONFLICT, build_applicability_report, demo_input, find_applicability_checks,
)

SCENARIOS = ("single", "two_trials", "two_criteria", "joint_review", "no_conflict")


def fixture(name):
    _, rows, trusted = demo_input(name, "A")
    if name == "two_trials":
        rows["outcome_b"]["trial_id"] = "SYN-OTHER-TRIAL"
    ranking = ["outcome_a", "outcome_b", "review", "eligibility"]
    if name == "two_criteria":
        extra = dict(rows["eligibility"], claim_id="eligibility_extra",
                     source_urls=["https://example.org/eligibility-extra"],
                     case_field="secondary_exposure")
        ranking.append("eligibility_extra")
        rows[extra["claim_id"]] = extra
    if name == "joint_review":
        extra = dict(rows["review"], claim_id="review_extra", source_urls=["https://example.org/review-extra"])
        ranking.insert(3, "review_extra")
        rows[extra["claim_id"]] = extra
        trusted["safety_evidence_flags"][0]["supporting_claim_ids"].append(extra["claim_id"])
    trusted["evidence_claims"] = list(rows.values())
    exposure = "Y" if name == "no_conflict" else "X"
    checks = find_applicability_checks(
        {"synthetic": True, "prior_exposure": exposure, "secondary_exposure": "X"}, rows,
    )
    return ranking, trusted, checks


def select_complete_bundle(ranking, budget, primary, trusted, checks):
    """Use baseline when no combination retains the full requested bundle."""
    baseline = ranking[:budget]
    criteria = {item["criterion_id"] for item in checks
                if item["outcome_id"] == primary and item["status"] == CONFLICT}
    sources = [set(flag["supporting_claim_ids"]) for flag in trusted["safety_evidence_flags"]
               if flag["supporting_claim_ids"]]
    outcomes = {row["claim_id"] for row in trusted["evidence_claims"]
                if row["claim_type"] == "TRIAL_OUTCOME"}
    best = baseline
    best_score = None
    for selection in combinations(ranking, len(baseline)):
        visible = set(selection)
        retained_flags = sum(group <= visible for group in sources)
        retained_criteria = len(criteria & visible)
        if primary not in visible or not retained_flags or not retained_criteria:
            continue
        score = (len(visible & outcomes), retained_flags, retained_criteria)
        if best_score is None or score > best_score:
            best = list(selection)
            best_score = score
    return best


def compare(name, budget):
    ranking, trusted, checks = fixture(name)
    baseline = ranking[:budget]
    selected = select_complete_bundle(ranking, budget, "outcome_a", trusted, checks)
    return [
        (chosen, build_applicability_report(trusted, chosen, checks, budget=budget))
        for chosen in (baseline, selected)
    ]


if __name__ == "__main__":
    for name in SCENARIOS:
        for budget in (3, 4, 5):
            cells = []
            for chosen, report in compare(name, budget):
                primary_conflicts = sum(item["status"] == CONFLICT and item["outcome_id"] == "outcome_a"
                                        for item in report["applicability_checks"])
                cells.append((chosen, primary_conflicts, len(report["research_review_flags"])))
            print(name, budget, *cells, sep=" | ")
