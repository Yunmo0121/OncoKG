# Task 15 · Lexical, dense, fusion and graph retrieval

The experiment ranks the same five evidence claims for eight Task 07
development cases. Neo4j supplies typed 2-hop and 4-hop evidence paths from
the verified v0.2 snapshot. We compare seven ranking methods and audit the
top-three changes by case.

| Method | Ranking rule |
| --- | --- |
| BM25 | Rank all claims by lexical score. |
| MiniLM | Rank all claims by local embedding cosine similarity. |
| BM25 + MiniLM (RRF) | Give both rankings equal weight. Sum `1 / (60 + rank)` across both lists and break ties by Claim ID. |
| KG paths · 2 or 4 hops | Rank only claims reached by the corresponding Neo4j query. Use the shortest path first and break ties by BM25 rank. |
| KG paths + context · 2 or 4 hops | Use the same graph candidates. Rank by context status, then shortest path, then BM25 rank. |

All methods return unique Claim IDs. The graph arms keep short lists if the
path query finds fewer than three claims. Precision uses a fixed denominator
k as in Task 13. Recall and MRR are averaged over the five cases that have a
developer-labelled relevant claim. MRR uses the full list.

## Observed development result

| Method | Precision@3 | Recall@3 | MRR |
| --- | ---: | ---: | ---: |
| BM25 | 20.8% | 73.3% | 0.750 |
| MiniLM | 20.8% | 73.3% | 0.740 |
| BM25 + MiniLM (RRF) | 20.8% | 73.3% | 0.840 |
| KG paths · 2 hops | 25.0% | 93.3% | 0.767 |
| KG paths · 4 hops | 25.0% | 93.3% | 0.767 |
| KG paths + context · 2 hops | 29.2% | 100.0% | 1.000 |
| KG paths + context · 4 hops | 29.2% | 100.0% | 1.000 |

### Case-level audit

| Case | Observable difference |
| --- | --- |
| SYN-PILOT-03 | Both graph path arms place the Pao evidence claim in the top three, where BM25 and RRF miss it. RRF moves it from fourth to fifth. |
| SYN-PILOT-04 | RRF moves the first relevant claim, AURA3, from second to first. No new relevant claim enters the top three. |
| SYN-PILOT-07 | Context ranking moves the Pao claim into the top three for both hop budgets. With graph paths and the BM25 tie-break alone, two of the three reference matches are returned in the top three. |
| SYN-PILOT-05 and SYN-PILOT-08 | Expanding the hop budget fills two additional positions per case. Neither case has a developer-labelled relevant claim, so the added positions earn zero hits. |

The JSON report includes each ranking, every top-k addition and removal
relative to BM25, gained/lost relevant IDs and underlying Neo4j paths.
The change from paths alone to context ranking retained one additional
expected claim in the top three on this development set. Increasing the
hop budget changed some displayed candidates but did not change the number
of relevant hits. Development labels reflect human-authored pilot
expectations and overlap with the rules under test. Eight cases and five
claims do not establish performance on a wider corpus. The Task 11 cases
remain held back. No language-model generation was evaluated.

## Reproduce

Use the [Task 14 setup](task14_dense_retrieval.md) for MiniLM and the
[Task 08 setup](task08_multihop.md) for Neo4j, its driver, the local curated
JSON files and the verified graph. The measured run used Neo4j Community
5.26.0 and ONNX Runtime 1.21.1 on Linux CPU.

```bash
python codes/demo/task15_retrieval_comparison.py pilot \
  --model-dir data/raw/minilm-task14 \
  --uri bolt://localhost:7687 --database neo4j --k 3 \
  --output docs/results/task15-retrieval-comparison.json
```

When independent labels are frozen, use a case-only JSON file and pass
the reference file's digest to the ranker. Use the same case input and
snapshot for all arms. Rank export writes seven Task 13-compatible JSON
files in a new directory. The scorer can check the evidence fingerprint
when both the reference and the prediction supply it.

```bash
reference_sha=$(shasum -a 256 /path/to/frozen-reference.json | cut -d' ' -f1)
python codes/demo/task15_retrieval_comparison.py rank \
  --model-dir data/raw/minilm-task14 --uri bolt://localhost:7687 \
  --cases /path/to/case-only.json --reference-sha256 "$reference_sha" \
  --output-dir docs/results/task15-ranks
```

Follow the [Task 13 scoring command](task13_evaluation.md) for each rank list.
The development smoke test exported all seven lists, passed them through the
Task 13 CLI and reproduced the corresponding metrics. BM25 and MiniLM
rankings also matched Task 14.
