# Task 18 · Supplemental provenance and scoped research flags

Task 18 adds an optional projection to the Task 17 report. The default
Task 17 output is preserved. The new projection uses the same pinned
development rankings, case fixture and curated evidence snapshot.

- Each retrieved AURA3 PFS claim includes the supplemental CIViC EID1867
  link beside its unchanged primary URL. The link retains its PFS-only
  scope and pending review status. It does not add another claim or
  change the matching state.
- A research flag is displayed only if its supporting claim list is
  nonempty and every supporting claim appears in the report's top-k
  evidence. The flag preserves its original explanation and supporting
  IDs. An absent flag does not indicate a negative full-corpus finding
  or safety clearance.
- This is deterministic output for synthetic research cases. The report
  still has empty treatment recommendations, exclusions and safety
  clearances.

## Results at k=3

| Method | Reports with a supplemental link | Reports with a research flag |
| --- | ---: | ---: |
| BM25 | 8/8 | 0/8 |
| MiniLM | 8/8 | 0/8 |
| Rank fusion | 8/8 | 0/8 |
| KG paths, 2 hops | 6/8 | 4/8 |
| KG paths, 4 hops | 8/8 | 4/8 |
| KG paths + context, 2 hops | 6/8 | 5/8 |
| KG paths + context, 4 hops | 4/8 | 3/8 |

Across 56 reports the projection adds 48 supplemental-link occurrences
and shows research flags in 16 reports. These are occurrences across
methods and cases. The 48 links all point to the same supplemental
record. The difference in flag counts reflects the evidence in the
top three, and includes mismatch and missing-context flags.

## Reproduce

Run from the repository root with the two curated JSON inputs and the
saved Task 15 development report. Choose a fresh output filename.

```bash
python codes/demo/task17_report_context.py \
  --report docs/results/task15-retrieval-comparison.json \
  --output docs/results/task18-reports.json --k 3 --include-review-details
```

Independent Task 11 evaluations and live language-model calls are outside
this experiment.

## Task 19 replay and case demonstration

Rebuild the expected Task 18 report from its original development rankings,
curated inputs and the current generator. The audit checks metadata,
methods and case order, then compares every report field for exact
agreement. It detects changes to saved outputs relative to this replay.
The ranking file is an input to the audit. The audit does not rerun retrieval,
establish input authenticity, or independently validate clinical evidence.

```bash
python codes/demo/task19_report_audit.py \
  --rankings docs/results/task15-retrieval-comparison.json \
  --report docs/results/task18-reports.json \
  --demo-output docs/results/task19-case-demo.md
```

The optional Markdown output is written only after validation, to a new file.
[Example: compare BM25 and 2-hop KG context ranking](task19_case_demo.md).
Use `--case-id` to select another development case.
