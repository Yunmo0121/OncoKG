# Task 30 · Declared primary outcome under a three-source budget

This controlled replay uses the Task 29 same-population conflict fixture.
The declared primary outcome comes from the experiment input.

| Declared priority | Kept evidence | Omitted evidence | Sourced conflict checks | Review flags |
| --- | --- | --- | ---: | ---: |
| A | A, review, eligibility | B | 1 | 1 |
| B | B, review, eligibility | A | 1 | 1 |
| Unspecified | A, B, review | eligibility | 0 | 1 |

The unspecified case emits two source-outside-report notices and an
explicit priority decision. The replay exercises a fixed synthetic fixture.
It does not establish priorities for real studies.

```sh
python codes/demo/task30_primary_outcome.py
python -m unittest discover -s codes/demo -q
```
