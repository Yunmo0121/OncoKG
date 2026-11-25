# Task 07 — Benchmark Protocol v0.1 (research design)

**Scope:** NSCLC / EGFR knowledge-graph research prototype. Synthetic cases only. **Not for patient-level decisions.**

## Separate the three evaluation layers

1. **Engineering regression (Task 07A; included now).** Four existing synthetic examples × five versioned Claim IDs = 20 context-status checks, plus 12 research-flag checks. Expected results reflect the implemented design and are **not independent medical ground truth**. These cases were used during development, so do not call the result a held-out test or an estimate of clinical accuracy. Even 100% agreement means only that this version behaves as expected.
2. **Independent evidence / label review (Task 07B; not yet done).** Before claiming clinical validity, freeze a new evaluation set with independent domain-expert labeling of evidence applicability, provenance quality, scope limitations, contradictory conditions, and when to abstain. Keep disagreement and adjudication logs, dataset version and dates. Record the exact evidence supporting every gold label. Use *synthetic cases* until authorized otherwise.
3. **Real model comparisons and ablation (Task 07C; not yet done).** Once the LLM endpoint is available, compare three implemented, genuinely distinct systems on the **same held-out cases** with a defined reference standard: LLM only; vector RAG (same accessible source corpus, embeddings and retrieval settings documented); KG-aware retrieval plus the same generator and policy layer. If a baseline has not been built, mark it **NOT RUN**, never invent a score.

## Proposed evaluation table for Task 07C

| Dimension | What to measure | Interpretation |
|---|---|---|
| Claim-level evidence-context correctness | independently reviewed per-Claim label match on a held-out set | NOT the engineering regression score |
| Insufficient-info detection | precision/recall for `NEEDS_INFORMATION`, with explicit denominators | avoid conflating missing with false |
| Unhandled-scope abstention | rate of `NOT_EVALUATED` on claims with no supported matching rule | do not score abstention automatically as a mistake |
| Provenance completeness | fraction of returned claims with a traceable source | existence alone is not citation *support* |
| Source support / faithfulness | manual review of whether a generated sentence is actually supported by its cited source | citations can exist but not support the sentence |
| Contradiction / resistance-context warnings | relevant signals captured, false alarms, explicit failure to infer hard contraindications | needs clinical review |
| Unsupported treatment instructions | manual count and types of unsafe invented directives | must not output patient-level treatment recommendations |
| Coverage, latency and cost | reported per-system with model version, inference date, token counts and request settings | do not compare different available evidence unfairly |

## Proposed synthetic-case strata for future *held-out* set

- Positive evidence-context match with all explicit conditions supplied
- A similar case with a different variant or mismatched treatment line
- Unknown prior therapy / unknown test status (nullable fields; not `false`)
- Known absence of prior exposure or progression
- Multiple changes in one case (context clashes)
- Unrepresented variants / diseases should be safely rejected or explicitly out-of-scope, never extrapolated
- Conflicting or stale evidence with provenance and updates (requires **new independently checked evidence**)

Keep train/dev cases separate from the **held-out** set. Freeze labels and prompts before system comparison. Pre-register hypotheses and metrics if the study will be reported formally.

## Important scientific limitations

- The five current Claim records are marked `source_checked_needs_independent_review`. They are **not** medically adjudicated, and safety triage does not include comprehensive contraindications/interactions.
- Retrieval correctness, citation correctness, and patient safety are different metrics; an LLM that echoes Claim IDs has not thereby demonstrated factual correctness.
- A benchmark derived from the same rules being evaluated is useful for regression, but has a high risk of circular validation. Obtain independent expert review before writing effectiveness claims.
- Do not publish datasets, claims, or screenshots to GitHub without research-lead approval. Do not store API credentials or sensitive health data in the repository.

## Literature for methodology planning

- Gallifant J et al. *The TRIPOD-LLM reporting guideline for studies using large language models.* Nature Medicine (2025). https://www.nature.com/articles/s41591-024-03425-5
- *Evaluation Methods for Inference-Time Retrieval-Augmented and Graph Retrieval-Augmented Large Language Models in Health Care: Scoping Review.* JMIR (2026). https://www.jmir.org/2026/1/e90046

These sources support rigorous transparent evaluation design, **not** the medical correctness of this project's current evidence or any benchmark result.

## Offline retrieval pilot v0.1

This separate pilot compares evidence-claim ranking on eight newly authored synthetic
contexts. The case file records developer annotations and reasons explicitly,
including cases with no context match and cases with missing context. The development
cases in Task 07A are excluded. Both the labels and the cases were designed with
knowledge of the current rules and corpus. The pilot supports engineering and
experiment-design decisions. Independent review and a locked evaluation set are pending.

### Reproduce

Use Python 3.10 or newer. Verification used Python 3.12.14. Place the two approved
local curated JSON inputs in `data/curated/` without editing them:

- `egfr_l858r_evidence_v0_1.json`
- `egfr_t790m_evidence_extraction_v0_2.json`

From the repository root:

```bash
python -m unittest discover -s codes/demo
python codes/demo/benchmark_task07.py --offline
python codes/demo/task07_retrieval_pilot.py --k 3 \
  --output docs/results/task07_retrieval_pilot_v0_1.json
```

For subsequent runs of the pilot, choose a new output filename or omit `--output`
for JSON on stdout. The pilot JSON is deterministic for the same inputs. Both
experiments preserve Claim IDs and source URLs and record input SHA-256 hashes.
The canonical facts remain in the versioned local evidence records.

The optional database regression uses Neo4j Community 5.26.0 and Python driver
5.28.2 in the verification environment. Use a dedicated v0.2 database and the same
curated JSON inputs to run the read-only comparison:

```bash
python codes/demo/benchmark_task07.py --db \
  --output-dir docs/results/task07_v0_1_db
```

### Comparison and denominators

All three modes rank the same five curated claims for each case. They use the
same tokenized case query and deterministic Claim-ID tie-break. Unknown fields are
omitted from the text query. Explicit false values remain in the query.

| Mode | Scoring |
| --- | --- |
| Lexical BM25 | Match case text against one text record per claim, using source title, claim type, disease, variant, drug mentions and curated context/scope. Fixed \(k_1=1.2\) and \(b=0.75\). |
| Variant-only rerank | Prioritize claims with a matching variant, retain unscoped claims ahead of variant mismatches, and use the BM25 order within each group. |
| Full-context rerank | Prioritize matched, needs-information, unassessed and mismatched claims in that order, then use the same BM25 order. Reuse Task 04 context rules on graph-shaped rows reconstructed offline. |

Precision@3 averages over all eight cases. Recall@3 and MRR average over the
five cases with a reference match. MRR uses the full ranked list. The three
cases without a reference match still contribute to precision and the separate
case-level check for whether a structured method incorrectly signals a match.
The ranked list can contain background evidence even when no matching evidence
is marked. Missing-context detection uses all 40 case/claim pairs. The triage
ablation measures the presence of a historical resistance-review flag per case
with triage enabled or omitted. It leaves evidence rankings fixed and measures
flag coverage only. It does not measure exclusion or treatment safety.

### Formal experiment still pending

- Freeze a synthetic evaluation set with independent reviewers, exact source
  locators for each label, disagreement resolution, and explicit labels for
  unknown and unsupported contexts. Preserve separate development and evaluation splits.
- Compare zero-shot LLM, dense text retrieval plus LLM, and graph-path retrieval
  plus the same LLM. Align data snapshots, context budgets, output schema,
  generation settings and scoring. Document each arm's evidence access.
- Implement bounded, typed path retrieval with an ordered node/edge trace and
  source joins. With retrieval and generation held fixed, test the effect of
  allowed paths, hop budget, context conditions and independently reviewed
  conflict rules individually. Add supported versus out-of-scope strata before
  running cross-cancer comparisons.
- Score claim relevance, evidence support of individual statements, abstention
  and conflict handling separately. A failure to retrieve evidence must be
  reported as a coverage gap. A historical resistance association remains a
  research review signal.
