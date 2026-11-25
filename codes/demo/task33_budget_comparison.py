"""Compare budget-matched report policies on synthetic fixtures."""
from task25_trial_applicability import CONFLICT, build_applicability_report, demo_input, find_applicability_checks

SCENARIOS = (
    ("primary_a", "A", "X", "outcome_a"),
    ("primary_b", "A", "X", "outcome_b"),
    ("other_population", "B", "X", "outcome_a"),
    ("unknown_population", None, "X", "outcome_a"),
    ("unknown_exposure", "A", None, "outcome_a"),
    ("no_conflict", "A", "Y", "outcome_a"),
    ("no_priority", "A", "X", None),
)


def compare(scenario, budget):
    name, population, exposure, primary = scenario
    _, rows, trusted = demo_input(name, population)
    ranking = ["outcome_a", "outcome_b", "review", "eligibility"]
    checks = find_applicability_checks({"synthetic": True, "prior_exposure": exposure}, rows)
    baseline = ranking[:budget]
    selected = baseline
    if budget == 3 and any(
        item["status"] == CONFLICT and item["outcome_id"] == primary
        and item["criterion_id"] == "eligibility" for item in checks
    ):
        selected = [primary, "review", "eligibility"]

    def summarize(chosen):
        report = build_applicability_report(trusted, chosen, checks, budget=budget)
        return {
            "selected": chosen,
            "omitted": [claim for claim in ranking if claim not in chosen],
            "conflicts": sum(item["status"] == CONFLICT for item in report["applicability_checks"]),
            "review_flags": len(report["research_review_flags"]),
        }

    return summarize(baseline), summarize(selected)


if __name__ == "__main__":
    for scenario in SCENARIOS:
        for budget in (2, 3, 4):
            print(scenario[0], budget, *compare(scenario, budget))
