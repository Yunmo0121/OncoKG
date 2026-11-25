# Task 33 · Paired budget comparison

```bash
python codes/demo/task33_budget_comparison.py
python -m unittest discover -s codes/demo -q
```

Seven synthetic scenarios at budgets 2, 3 and 4 yield 21 paired reports.
The script prints selected and omitted IDs, sourced conflict counts and
review flag counts for each arm. The experimental rule only swaps a row at
budget 3 when a declared primary outcome has a confirmed conflict.

Two pairs changed, one for each declared primary outcome in the same
fixture. Each adds one sourced conflict check, retains the review flag,
and omits the other outcome. The remaining 19 pairs have identical
outputs. Independent outcome annotations are outside this experiment.
