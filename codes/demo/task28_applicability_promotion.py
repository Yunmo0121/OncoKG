"""Experimental comparison of promoting conflicting eligibility evidence."""
from task25_trial_applicability import (
    CONFLICT, build_applicability_report, demo_input, find_applicability_checks,
)
from task23_review_support import K


def promote_conflicting_criterion(ranking, candidates, checks):
    selected = ranking[:K]
    visible = set(selected)
    eligible = {
        check["criterion_id"] for check in checks
        if check["status"] == CONFLICT and check["outcome_id"] in visible
        and check["criterion_id"] not in visible
    }
    incoming = next((claim for claim in ranking[K:] if claim in eligible), None)
    outgoing = next((claim for claim in reversed(selected)
                     if candidates[claim]["claim_type"] == "RESISTANCE_ASSOCIATION"), None)
    if incoming is not None and outgoing is not None:
        selected[selected.index(outgoing)] = incoming
    return selected


if __name__ == "__main__":
    print("population | exposure | baseline third / conflicts / review flags | promotion third / conflicts / review flags")
    for population, exposure in (("A", "X"), ("B", "X"), (None, "X"), ("A", None), ("A", "Y")):
        _, rows, trusted = demo_input("SYN-28", population)
        ranking = ["outcome_a", "outcome_b", "review", "eligibility"]
        checks = find_applicability_checks({"synthetic": True, "prior_exposure": exposure}, rows)
        promoted = promote_conflicting_criterion(ranking, rows, checks)
        cells = []
        for chosen in (ranking[:K], promoted):
            report = build_applicability_report(trusted, chosen, checks)
            conflicts = sum(check["status"] == CONFLICT for check in report["applicability_checks"])
            cells.append(f"{chosen[2]} / {conflicts} / {len(report['research_review_flags'])}")
        print(population, exposure, *cells, sep=" | ")
