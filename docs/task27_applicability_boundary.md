# Task 27 · Applicability evidence outside the report cutoff

## Why this case matters

Task 26 started with an eligibility note already in the first three
positions. Its selection rule protected that note when applicable.
Task 27 starts with the same two outcomes and review source in the first
three positions, with the eligibility note fourth. The candidate pool and
budget stay fixed. Only the note's analysis population changes.

| Population of the note | Third evidence row | Outcome checks |
| --- | --- | --- |
| A, matching the displayed outcomes | Review source | Two notices that the eligibility source is outside the report |
| B, another population in the same trial | Review source | None |
| Unknown | Review source | Two requests to verify the population mapping |

The report includes no citation or confirmed exclusion for the omitted
note. This regression test checks the existing behavior. It exposes the
next selection question: should an eligible note outside the cutoff be
promoted, given that doing so would displace the review source?

```sh
PYTHONPATH=codes/demo python -m unittest test_task27_applicability_boundary -v
```
