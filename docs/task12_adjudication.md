# Task 12 · Independent review comparison

After both independent reviewers return their CSVs, compare them against the
unpacked original Task 11 packet. Keep the blank `annotation.csv` from the
packet and ask reviewers to fill separate copies. Each completed label
requires a reason and a source location.

```bash
python codes/demo/task12_adjudication.py \
  --packet-dir docs/results/task11-review-packet \
  --reviewer-a /path/to/reviewer-a.csv \
  --reviewer-b /path/to/reviewer-b.csv \
  --output-dir docs/results/task12-comparison
```

The input CSVs may be sorted differently. Rows are joined by the original
case and claim IDs. The program checks the packet file hashes and rejects
duplicate or unknown pairs, malformed rows and unsupported labels. Choose a
new output directory on reruns.

| Output | Contents |
| --- | --- |
| `agreement.json` | Input hashes, paired-label count, exact agreement and counts for each comparison status. |
| `adjudication.csv` | A row for every expected case/claim pair, each reviewer's original label, reason and locator, and blank fields for adjudication. |

Exact agreement is the number of equal labels divided by the number of
pairs completed by both reviewers. It is undefined when no pair has two
labels. Missing annotations have explicit statuses (`MISSING_A`,
`MISSING_B` and `MISSING_BOTH`). A filled `NOT_EVALUATED` label counts as
a reviewer decision. The comparison measures agreement between annotations.

For disagreements or missing entries, return to the primary sources and
record the adjudicated decision, its reason and its location. Leave both
reviewer columns intact. An unresolved decision can be documented separately.
All final fields in the export are blank, including those for agreements.
The output stays `PENDING_ADJUDICATION`. A signed-off reference and formal
system scoring are separate steps.
