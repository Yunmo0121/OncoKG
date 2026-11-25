# Task 17 · Ranked evidence in a local report

Task 17 takes the saved Task 15 ranking output and produces one deterministic
research report per method and case. It checks the evidence and development
fixture fingerprints and uses the existing context matcher and mock report
builder to obtain claim status, primary source URLs and missing-field checks.
Each method receives the same top-k budget. Graph methods may provide fewer
items when the ranking is shorter. Each report preserves ranking order.

The report lists only checks attached to the retrieved claims. A missing field
for an omitted claim is outside that report's coverage. The output uses
primary source URLs from the curated inventory. Task 10's supplemental CIViC
link and Task 05's full-corpus triage flags are outside this report projection.

## Development results at k=3

| Method | Cases with at least one context match | Cases with a missing-field check | Evidence rows |
| --- | ---: | ---: | ---: |
| BM25 | 4/8 | 5/8 | 24 |
| MiniLM | 4/8 | 5/8 | 24 |
| Rank fusion | 4/8 | 5/8 | 24 |
| KG paths, 2 hops | 5/8 | 6/8 | 20 |
| KG paths, 4 hops | 5/8 | 6/8 | 24 |
| KG paths + context, 2 hops | 5/8 | 5/8 | 20 |
| KG paths + context, 4 hops | 5/8 | 5/8 | 24 |

Every one of the 160 reported evidence rows carries its source URL.
SYN-PILOT-03 illustrates the additional context-match coverage. The graph
rankings include the Pao claim, which the text-only top-three lists omit.
On SYN-PILOT-07, context reranking promotes that claim into the top three.
It displaces the L858R claim and the missing-test check attached to it.
Thus a report with fewer missing-field notes may reflect retrieval coverage.
It does not establish that the input case was more complete.

The counts describe prototype rule states and report content. Task 11 remains
reserved for independent review. No LLM was called. The report carries empty
treatment recommendation, automatic exclusion and safety clearance lists.

## Reproduce

Use a matching [Task 15 report](task15_retrieval_comparison.md) and both curated
JSON inputs. The reporting step runs locally with the standard library and
uses the saved rankings. Choose a fresh output filename for a rerun.

```bash
python codes/demo/task17_report_context.py \
  --report docs/results/task15-retrieval-comparison.json \
  --output docs/results/task17-reports.json --k 3
```
