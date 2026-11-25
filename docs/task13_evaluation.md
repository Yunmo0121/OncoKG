# Task 13 · Freeze reference labels and score ranked evidence

The final reference is prepared after a human completes the Task 12 worksheet.
Retain the original Task 11 packet and both original reviewer files. The
`freeze` command checks that the reviewer and status columns correspond to
those inputs, and that all expected rows have a final label, reason and source
location. Use `UNRESOLVED` with a reason and locator when adjudication cannot
settle a row. Keep the frozen reference separate from system inputs.

```bash
python codes/demo/task13_evaluation.py freeze \
  --packet-dir docs/results/task11-review-packet \
  --reviewer-a /path/to/reviewer-a.csv \
  --reviewer-b /path/to/reviewer-b.csv \
  --adjudication /path/to/completed-adjudication.csv \
  --output docs/results/task13-frozen-reference.json
```

The frozen JSON records the labels, reasons, source locators, class counts and
input checksums. A successful freeze validates the file lineage and required
fields. Human reviewers establish the reference and the review protocol
documents their independence. Use a versioned output path for any amendments.

## Score a ranking file

Each system returns one row for every case. A row contains a `case_id` and
an ordered `claim_ids` list; use `[]` to report no results. Include `system_id`
and the SHA-256 digest of the frozen reference as `reference_sha256` at the
top level. The scorer does not pass labels to the ranking system. Share case
inputs, evidence corpus and the reference digest with a system runner.

```json
{
  "system_id": "example-baseline-v1",
  "reference_sha256": "<digest of the frozen reference bytes>",
  "cases": [
    {"case_id": "<case ID>", "claim_ids": ["<first claim ID>", "<second claim ID>"]}
  ]
}
```

```bash
python codes/demo/task13_evaluation.py score \
  --reference docs/results/task13-frozen-reference.json \
  --predictions /path/to/ranked-claims.json \
  --k 3 \
  --output docs/results/task13-example-score.json
```

- A relevant result is a Claim ID labelled `CONTEXT_MATCHED` by adjudication.
- Precision@k divides hits by the requested k and macro-averages over scored
  cases. Short lists use the same denominator as full lists.
- Recall@k and reciprocal rank are macro-averaged over scored cases with at
  least one relevant claim. Reciprocal rank uses the entire supplied list.
- Any case with an `UNRESOLVED` reference row is excluded for every system and
  listed explicitly. The output records the resulting coverage.
- Use the same frozen reference and k across systems. The output records
  file hashes and case-level metrics. These metrics concern evidence retrieval
  on the benchmark corpus.
