# Task 23 · Review evidence under a three-row budget

Can a bounded research report retain more evidence supporting contextual
resistance review while preserving directly matched evidence and
missing-information checks?

## Design

Replay the saved Task 15 rankings for eight synthetic development cases at
exactly one budget, at most three report rows. Compare two-hop context ranking,
four-hop context ranking, Task 22 vacancy-based backfill, and the following
conservative rule.

1. Start with the first three two-hop claims. Inspect the four-hop candidates
   in their existing order. Consider sourced resistance-association claims
   whose context is matched or whose context requires more information.
2. Keep candidates already shown in place. For eligible candidates outside
   the report, use an open slot if available. Otherwise replace the last
   `NOT_MATCHED` or `NOT_EVALUATED` row. Preserve every `CONTEXT_MATCHED` and
   `NEEDS_INFORMATION` row. Keep the list when all slots are protected.
3. Measure evidence retention with the standard mock reports. Count
   case-level support for `RESISTANCE_ASSOCIATION_REVIEW` or
   `RESISTANCE_CONTEXT_INCOMPLETE` items. Identical flags supported by the
   same claim set count once per case across drug mentions. The score also
   tracks context-matched claims, missing checks, and supplemental links.

The selector receives only claim attributes for the candidates in the
two-hop/four-hop rankings, with the two-hop set verified as a subset. The
full-snapshot report provides denominators for the audit after selection.
The run uses no independent labels, live Neo4j queries, or LLM calls.

## Observed pilot

| Top 3 method | Targeted review support | Context-matched claims | Missing checks | Supplemental links |
| --- | ---: | ---: | ---: | ---: |
| Two-hop context | 3/3 | 7/7 | 16/19 | 6/8 |
| Four-hop context | 3/3 | 7/7 | 11/19 | 4/8 |
| Two-hop then vacancy-based backfill | 3/3 | 7/7 | 16/19 | 6/8 |
| Two-hop with targeted support selection | 3/3 | 7/7 | 16/19 | 6/8 |

The targeted selector changed **0/8** case rankings. SYN-PILOT-03,
SYN-PILOT-04 and SYN-PILOT-07 already retained their review support in the
two-hop prefix. The remaining five cases yielded no qualifying support
candidate in the expanded ranking. Purpose-built unit fixtures exercise the
swap, open slot, protected list, and provenance conditions separately.

## Why the selector cannot change a v0.2 ranking

- The context matcher requires a case variant that the claim explicitly
  requires before it can assign either eligible status. The current sole
  resistance-association claim has a verified direct path from that same
  variant to its source. It therefore enters the two-hop pool whenever it
  qualifies under the current case and path rules. A four-hop path through
  a different variant cannot satisfy that match.
- The two-hop baseline already ranks both protected statuses above both
  replaceable statuses. If a qualifying claim in that pool falls below
  position three, all three displayed positions are protected.

Together, these properties make the selector a no-op under the current
path, context and ranking definitions. Testing a benefit from extra hops
requires a genuine typed path that adds eligible support absent from the
direct pool. Record this condition before measuring any gain.

## Fixed-pool comparison

To test evidence allocation separately, use the same five-claim BM25 pool
for three arms. Compare the original BM25 order, a stable sort by context
status with BM25 breaking ties, and targeted support selection applied to
the original BM25 order. Each arm uses the same three-row budget.

| Top 3 method | Targeted review support | Context-matched claims | Missing checks | Supplemental links |
| --- | ---: | ---: | ---: | ---: |
| BM25 | 0/3 | 5/7 | 12/19 | 8/8 |
| BM25 with context priority | 3/3 | 7/7 | 11/19 | 4/8 |
| BM25 with targeted support selection | 3/3 | 7/7 | 13/19 | 8/8 |

Both context-based arms recover the same review support. Targeted selection
makes three replacements and leaves five cases unchanged. It retains more
missing checks and supplemental links than context priority on these cases.
All three replacements involve the same incoming and outgoing claims.
The pilot therefore shows one repeated evidence-ranking pattern across
three cases. A follow-up should cover varied support sources and situations
where every slot is protected, then evaluate on independently annotated
synthetic cases.

These fractions measure report retention against the existing research
rules and snapshot. The pilot leaves generalization unresolved.

## Reproduce

From the repository root, use the local curated evidence files and the
saved Task 15 comparison. Choose a fresh output filename.

```bash
python codes/demo/task23_review_support.py \
  --rankings docs/results/task15-retrieval-comparison.json \
  --output docs/results/task23-review-support-v1.json
python -m unittest discover -s codes/demo -q
```

The JSON includes input hashes, each selection decision, the selected
claims for every arm, and case-level audit counts.
