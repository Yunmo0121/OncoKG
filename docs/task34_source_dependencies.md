# EXP-T34-01 · Evidence source dependencies

## Hypothesis

A review flag supported by two distinct evidence rows increases the smallest budget
that can retain a primary outcome, a sourced conflict and the entire review flag.

## Change vs. baseline

Compare rank truncation with exhaustive subset selection at equal budgets.
A qualifying subset contains the declared primary outcome, at least one of its
sourced conflict criteria and all supporting rows for at least one review flag.
Among qualifying subsets, prefer more outcomes, then more fully supported flags,
then more sourced primary-outcome conflicts. Break ties by candidate order.
If none qualify, use rank truncation.

## Setup

Five synthetic variants at budgets 3, 4 and 5. Rankings contain four or five
candidates. All variants declare outcome A as primary. Shared sources and flags
use existing report logic. This is a bounded experiment with a combinatorial
search over small candidate pools.

## Reproduce

```bash
python codes/demo/task34_source_dependencies.py
python -m unittest discover -s codes/demo -q
```

## Results

| Scenario | Changed budgets | Effect |
| --- | --- | --- |
| Single source | 3 | One sourced primary conflict added, one secondary outcome omitted |
| Second outcome from another trial | 3 | One sourced primary conflict added, one secondary outcome omitted |
| Two conflict criteria | 3 | One sourced primary conflict added, one secondary outcome omitted |
| Review flag requires two sources | 4 | One sourced primary conflict added, one secondary outcome omitted |
| No conflict | None | Rank truncation retained |

The other 11 pairs retain the baseline output. All four changed pairs preserve
the baseline review flag count. The cross-trial check qualifies outcome A only.
With two separate criteria and five available slots, both criteria enter the
report. The suite passes 140 tests and the Task 26 replay verifies.

## Observation

Three slots cannot hold a primary outcome, an eligibility criterion and two
distinct review support rows. Four suffice in the joint-review example.

## Conclusion

The hypothesis holds on this synthetic variant. The selector favors retaining
more outcomes over adding further conflict checks after the bundle goal is met.

## Next

Evaluate the outcome-retention priority against independently labelled cases.
