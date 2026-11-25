# Task 29 · Trade-offs under a three-source budget

Using the Task 28 same-population conflict fixture, enumerate the distinct
three-source subsets. Each source consumes one slot.

| Evidence retained | Outcomes | Sourced conflict checks | Review flags |
| --- | ---: | ---: | ---: |
| Both outcomes and review source | 2 | 0 | 1 |
| Both outcomes and eligibility source | 2 | 2 | 0 |
| Outcome A, eligibility and review | 1 | 1 | 1 |
| Outcome B, eligibility and review | 1 | 1 | 1 |

Both mixed selections have the same counts. The fixture has no outcome
priority labels. Two conflict checks in one report can share one source.

## Reproduce from the repository root

```sh
PYTHONPATH=codes/demo python - <<'PY'
from itertools import combinations

from task25_trial_applicability import (
    CONFLICT, build_applicability_report, demo_input, find_applicability_checks,
)

_, rows, trusted = demo_input("SYN-29", "A")
ranking = ["outcome_a", "outcome_b", "review", "eligibility"]
checks = find_applicability_checks({"synthetic": True, "prior_exposure": "X"}, rows)
for selection in combinations(ranking, 3):
    report = build_applicability_report(trusted, list(selection), checks)
    conflicts = sum(item["status"] == CONFLICT for item in report["applicability_checks"])
    print(selection, conflicts, len(report["research_review_flags"]))
PY
```
