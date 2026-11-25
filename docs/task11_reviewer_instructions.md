# OncoKG · Synthetic evidence-context review

The packet asks whether the stated facts of an invented NSCLC/EGFR
case align with a specific evidence claim. It is a research annotation
exercise. Statements about treatment choice, effectiveness for an individual,
contraindications, and clinical eligibility are outside the exercise.

## Files

| File | Contents |
| --- | --- |
| cases.csv | Twelve synthetic scenarios. `unknown` means information is absent. `false` records a negative observation. `[]` records an empty drug list. A test-confirmation field describes evidence of confirmation by the specified test, separately from whether the scenario lists the variant. |
| sources.csv | The five existing evidence claims with the primary source, its location, and claim type. Evaluate the specified source section or endpoint. |
| annotation.csv | One row per case and claim, with empty fields for the label, reason, and exact source location used. |
| manifest.json | Dataset identity, input fingerprints, and file checksums for reproducibility. |

## Labels

| Label | When to use it |
| --- | --- |
| CONTEXT_MATCHED | The recorded facts fit the scope of the stated claim. |
| NOT_MATCHED | At least one recorded fact puts the case outside that claim's scope. |
| NEEDS_INFORMATION | A decision within the claim's scope depends on case information that is unavailable. |
| NOT_EVALUATED | The source or claim provides no basis for the requested case-level judgment, or you cannot resolve its scope from the listed materials. State the reason. |

Review the primary source and the claim's specified scope. For trial outcomes,
distinguish population-level results from subgroup claims. Evidence of a
historical resistance association stays within that study's context. If a
source cannot be accessed or a field is ambiguous, record the problem in the
reason and source-location columns.

## Review and adjudication

1. Give both reviewers separate copies of the blank template and keep
   the system's outputs and the other reviewer's answers out of each review.
2. Save both original annotations. Compare labels by case and claim ID and
   record agreement, disagreements, and missing annotations.
3. Have disagreements adjudicated against the primary sources. Record the final
   label and reason separately. Preserve the two original answers. Allow a
   documented unresolved label when the evidence scope stays ambiguous.
4. Freeze the adjudicated reference before running the systems on these cases.
   Record the manifest and report dataset size and class counts. The cases were
   authored by the development team for a bounded evaluation of one graph
   snapshot, with deliberate variation in context and missing information.
