# Task 28 · Eligibility promotion ablation

Compare the Task 27 ranking with an experimental single swap at Top 3.
Promote the highest ranked out-of-cutoff criterion linked to a displayed outcome by a sourced conflict, replacing the last selected resistance association if available.

| Synthetic condition | Sourced conflict checks, baseline → promotion | Review flags, baseline → promotion |
| --- | --- | --- |
| Same population, excluded exposure present | 0 → 2 | 1 → 0 |
| Different population, unknown population, missing exposure, or nonconflicting exposure | 0 → 0 | 1 → 1 in each case |

The two checks cite one criterion. Missing source is covered by a separate regression subcase. This demonstration leaves the Task 26 pipeline intact.

```sh
python codes/demo/task28_applicability_promotion.py
python -m unittest discover -s codes/demo -q
```
