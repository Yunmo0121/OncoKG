# Task 25 · Link trial evidence to its analysis population

Task 24 preserved sourced eligibility notes with hand-authored links to
displayed outcomes. Task 25 derives those links from structured metadata in
five synthetic cases using the same candidate order and three-row budget.

## Scope and report behavior

- The demo matches a sourced exclusion to an outcome only when both have
  the same explicit trial and analysis population identifiers. It checks a
  single categorical exclusion against the synthetic case.
- A matching exclusion or missing case value protects an already selected
  eligibility note and qualifies its displayed outcomes. If a criterion
  source is outside the report, an uncertainty notice appears without
  citing it or claiming an established conflict.
- Different known populations establish no link. A missing population
  identifier in the same trial yields a request to verify the population
  mapping, with no confirmed link to the outcome.
- Task 25 changes the displayed context status and explanation for affected
  outcomes. The input matcher result stays available for comparison.
  Resistance review still requires its own supporting evidence within the
  three rows.

## Controlled comparison

The first two slots always hold the same two trial outcomes. Task 24 provides
the hand-authored links as a selection reference. Each retained eligibility
note can support two outcomes, so two protected links can share one source.

| Synthetic scenario | Task 23, slot 3 | Task 24 manual, slot 3 | Task 25, slot 3 | Task 25 outcome wording |
| --- | --- | --- | --- | --- |
| Same population, excluded exposure present | Review source | Eligibility source | Eligibility source | Direct applicability limited |
| Same trial, different population | Review source | Review source | Review source | Original context status |
| Same population, exposure unknown | Review source | Eligibility source | Eligibility source | Verify missing exposure |
| Trial matches, population unknown | Review source | Review source | Review source | Verify population mapping |
| Same population, known exposure differs | Review source | Review source | Review source | Original context status |

Task 25 matched the manual selection on all five cases, retained all four
expected outcome–criterion links and added zero extra links. Task 23 missed
all four. Task 25 retained the review source in three cases and reserved the
third slot for the eligibility source in two. These counts describe designed
engineering fixtures; they cannot estimate performance on unseen evidence.
The demonstration uses prestructured metadata and placeholder provenance.
Extraction from trial documents, graph integration and validation against
real inclusion/exclusion rules remain open.

## Reproduce

From the repository root, choose a fresh output path.

```bash
python codes/demo/task25_trial_applicability.py --output docs/results/task25-demo.json
PYTHONPATH=codes/demo python -m unittest test_task25_trial_applicability -v
```

The JSON contains all three policies' reports, retained and displaced evidence,
missed and extra links, and review support decisions for every case. The demo
runs offline without Neo4j, curated trial files, or an LLM API.
