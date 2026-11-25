# Task 24 · Preserve applicability limits at Top 3

A candidate's value can depend on what else the report displays. A trial
eligibility note may carry no standalone outcome while qualifying two
already selected outcomes.

The paired fixtures hold the ranking, budget, candidate types, context
statuses and review support constant. Both outcomes match the fields
checked by a deliberately coarse synthetic matcher. In one fixture, the
third row records that the trial excluded prior exposure X, which is
present in the synthetic case. In the control, the third row is general
background. The fourth row supports a historical resistance review flag.

| Synthetic fixture | Task 23 keeps in slot 3 | With explicit applicability protection |
| --- | --- | --- |
| Eligibility limit linked to the two displayed outcomes | Review source | Eligibility limit and its source |
| General background with no such link | Review source | Review source |

The selector accepts an optional mapping from limitation claim IDs to the
IDs of claims they qualify. The mapping is supplied by the caller and is
hand-authored in these fixtures. Protection requires a source link and at
least one distinct, displayed target. The audit records the protected row
and its displayed targets. The existing report builder withholds the
review flag when its supporting claim does not fit in the report.

These are controlled engineering tests. The replay command in Task 23
continues to run without limitation annotations. The existing graph and
context matcher do not detect or verify these links. The change preserves
the limiting note alongside the outcomes and does not revise their context
status. Detecting the relation and qualifying the outcome wording remain
separate work.

Run from the repository root.

```bash
PYTHONPATH=codes/demo python -m unittest test_task24_applicability_limits -v
```
