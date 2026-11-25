# Task 22 · Four-hop backfill for short report lists

Task 22 compares two-hop context ranking, four-hop context ranking, and
two-hop context ranking followed by four-hop backfill. For backfill, every
two-hop candidate retains its position. Previously unseen four-hop
candidates are appended in four-hop ranking order. The report takes a
prefix of the resulting list, so additions appear only if the two-hop list
has fewer than k candidates.

The experiment replays saved Task 15 rankings for eight synthetic
development cases and uses the Task 21 full-snapshot coverage denominator.
It validates that every two-hop candidate also appears in the four-hop
list. No retrieval timing was measured because both rankings already exist.
The comparison does not use the independent evaluation set.

## Observations

| k | Cases using backfill | Additional evidence rows |
| ---: | ---: | ---: |
| 1 | 0/8 | 0 |
| 2 | 2/8 | 2 |
| 3 | 2/8 | 4 |
| 4 | 6/8 | 10 |
| 5 | 8/8 | 18 |

At k=3, SYN-PILOT-05 and SYN-PILOT-08 each gain two evidence rows.
None of the four rows increases coverage for a context-matched claim,
missing check, research flag, or supplemental link. The approach preserves
the original top-three coverage of 7/7, 16/19, 10/24, and 6/8 respectively.

At k=4, both the two-hop and backfill configurations retain 7/7 context-matched
claims and 19/19 missing checks. Backfill raises research flag coverage from
12/24 to 14/24 and supplemental-link coverage from 6/8 to 8/8. The direct
four-hop ranking at the same cutoff retains 13/24 flags, 8/8 supplemental
links, and 16/19 missing checks.

At k=5, both backfill and four-hop context ranking retain every item in
the full-snapshot reference for these cases. Their ordering can still differ.
The comparison measures presentation coverage under prototype rules.
A displayed or omitted flag makes no determination about clinical safety.

## Reproduce

Use the two local curated evidence files and the saved Task 15 report.
Run from the repository root and choose a fresh output filename.

```bash
python codes/demo/task22_graph_backfill.py \
  --rankings docs/results/task15-retrieval-comparison.json \
  --output docs/results/task22-graph-backfill.json
```

The output records hashes, coverage for each cutoff and method, and every
case and claim used for backfill.
