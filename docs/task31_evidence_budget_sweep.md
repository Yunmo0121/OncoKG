# EXP-T31-01 · Evidence budget sweep

## Hypothesis

With one slot per candidate, preserving one outcome and both sources
requires at least three slots. Preserving both outcomes and both sources
requires four. Compare against truncation of the original ranking at each
budget. The candidate set and synthetic exposure remain fixed.

## Reproduce

```sh
PYTHONPATH=codes/demo python - <<'PY'
from itertools import combinations

from task25_trial_applicability import demo_input, find_applicability_checks, CONFLICT

_, rows, _ = demo_input("SYN-31", "A")
ranking = ("outcome_a", "outcome_b", "review", "eligibility")
checks = find_applicability_checks({"synthetic": True, "prior_exposure": "X"}, rows)
for k in (2, 3, 4):
    feasible = []
    for selected in combinations(ranking, k):
        outcomes = sum(rows[row]["claim_type"] == "TRIAL_OUTCOME" for row in selected)
        cited = sum(check["status"] == CONFLICT and check["outcome_id"] in selected
                    and check["criterion_id"] in selected for check in checks)
        review = int("review" in selected)
        print(k, selected, outcomes, cited, review)
        if outcomes and cited and review:
            feasible.append(selected)
    assert len(feasible) == {2: 0, 3: 2, 4: 1}[k]
PY
```

This enumerates candidate subsets, counts sourced applicability checks
with the existing matcher, and checks retention of the single review
source. It does not render four-row reports.
