# Task 16 · Retrieval sensitivity and paired case audit

This audit reuses the seven Task 15 rankings for eight synthetic development cases.
It checks the case-fixture fingerprint, rejects duplicate or unknown case and claim
IDs, and reproduces the original Task 15 metrics before reporting additional
cutoffs. The audit uses existing rankings without rerunning Neo4j or MiniLM.
The independent Task 11 cases are reserved for their reviewers.

## Cutoff sensitivity

Mean Recall@k across the five cases with at least one developer-labelled match:

| Method | @1 | @2 | @3 | @4 | @5 |
| --- | ---: | ---: | ---: | ---: | ---: |
| BM25 | 46.7% | 66.7% | 73.3% | 100.0% | 100.0% |
| MiniLM | 46.7% | 73.3% | 73.3% | 73.3% | 100.0% |
| BM25 + MiniLM (RRF) | 66.7% | 73.3% | 73.3% | 73.3% | 100.0% |
| KG paths (2 and 4 hops) | 46.7% | 66.7% | 93.3% | 100.0% | 100.0% |
| KG paths + context (2 and 4 hops) | 86.7% | 93.3% | 100.0% | 100.0% | 100.0% |

The machine report also includes Precision@k averaged across all eight cases.
Its per-case denominator stays fixed at k, even for short rankings. Mean
reciprocal rank (MRR) uses the full lists and therefore repeats across cutoffs.
At k=5, all methods recover every labelled match. This cutoff spans the entire
five-claim inventory and gives little information about ordering quality.

## Paired case audit

- **Context reranking over 2-hop path ranking.** At k=1 both SYN-PILOT-03
  and SYN-PILOT-04 gain one hit. At k=3 the single additional hit comes from
  SYN-PILOT-07, with the Pao claim entering the top three. Removing that
  case reduces the Recall@3 gain from 6.7 percentage points to zero.
- **2 hops to 4 hops.** Both graph comparisons have identical hit counts
  in every case at each cutoff from 1 to 5. At k=3, the 2-hop lists are
  short for SYN-PILOT-05 and SYN-PILOT-08. The 4-hop lists fill the two extra
  slots for each case. Both cases have zero developer-labelled matches.
- **Fusion over BM25.** The Recall@1 gain is 20 percentage points. At k=4,
  fusion loses the sole labelled match for SYN-PILOT-03 by moving it from
  fourth to fifth. The full-list MRR gain is 0.090. Across the eight paired
  leave-one-out runs it ranges from −0.0125 to +0.1250, so its direction
  depends on the case mix.

Leave-one-out sensitivity drops the same case from both methods and recomputes
the aggregate delta. The reported ranges are descriptive checks of case
influence. The cases and labels were authored for development and share the
scope of the rules under test. The study has no independent performance
estimate yet.

## Reproduce

Generate the results JSON using the [Task 15 pilot](task15_retrieval_comparison.md).
Run the following from repository root with a new output filename:

```bash
python codes/demo/task16_retrieval_audit.py \
  --report docs/results/task15-retrieval-comparison.json \
  --output docs/results/task16-retrieval-audit.json
```

The output includes the input report checksum, evidence snapshot hashes,
per-cutoff metrics, short-list counts, changed Top-k lists and their case-level
hit deltas, and paired leave-one-out results. Repeated runs from identical
inputs produce byte-identical JSON.
