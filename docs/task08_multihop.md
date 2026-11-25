# Task 08 — Bounded evidence paths

The experiment asks whether a four-hop search adds context-matched evidence to
a two-hop search on the existing NSCLC/EGFR research snapshot. It uses the
four synthetic cases from `data/samples/synthetic_nsclc_cases_v0_1.json`, the
same five-claim graph, the same case-context rules, and the same provenance
checks at both hop budgets.

## Path definitions

A hop crosses one relationship. The Cypher query uses three explicit templates.
Paths are ordered from the case variant to the evidence source. A relationship's
stored direction may point opposite the direction of traversal.

| Hops | Scope | Ordered nodes |
| ---: | --- | --- |
| 2 | Direct variant | Variant → Claim → Evidence |
| 4 | Other variant of the same gene | Variant → Gene → Other variant → Claim → Evidence |
| 4 | Disease background | Variant → Bridge claim → Disease → Variant-unscoped claim → Evidence |

The candidate claim must belong to a verified dataset and have an
`IN_DISEASE` edge for the case disease. The bridge claim must also belong to
a verified dataset. Each result records the anchor, scope, ordered node IDs
and labels, stored relationship endpoints and types, dataset and claim IDs,
and evidence identity and URL. The output includes the source locator,
PMID and DOI when available.

Task 04 evaluates the whole case once. Every occurrence of a claim inherits
that result and any missing-context checks. Multiple paths to the same claim
are counted separately as paths and once in the distinct-claim metrics.
Reachability through a shared gene or disease only identifies a candidate;
context rules determine its status. Historical resistance remains a research
review signal.

## Run

The verification used Neo4j Community 5.26.0 and Neo4j Python driver 5.28.2.
Use the existing v0.2 database (23 nodes, 32 relationships) and the local
curated JSON files. The script verifies both dataset hashes and the curated
claim inventory before reading the paths.

Run from the repository root with your Neo4j instance running:

```bash
python codes/demo/task08_multihop.py \
  --uri bolt://localhost:7687 \
  --database neo4j \
  --output docs/results/task08-comparison.json
python codes/demo/test_task08_multihop.py
```

Use a new output filename on reruns, or omit `--output` to print the report.
Use `--case-id SYN-T790M-001` for a single-case demonstration. Database
access is read-only and the password is requested interactively. The
experiment uses neither a model API nor any external evidence service.

## Observed results on the v0.2 snapshot

| Synthetic case | Paths, 2 → 4 | Distinct claims, 2 → 4 | Context-matched claims, 2 → 4 |
| --- | ---: | ---: | ---: |
| SYN-T790M-001 | 3 → 7 | 3 → 5 | 3 → 3 |
| SYN-L858R-002 | 1 → 5 | 1 → 5 | 1 → 1 |
| SYN-T790M-UNKNOWN-003 | 3 → 7 | 3 → 5 | 0 → 0 |
| SYN-T790M-NO-PRIOR-004 | 3 → 7 | 3 → 5 | 0 → 0 |

For example, the T790M query reaches the disease-level FLAURA outcome
through three distinct bridge claims. Those are three graph paths to one
background claim. The other additional claim in the T790M cases is scoped
to the L858R variant and is reported as `NOT_MATCHED`. The disease-level
outcome remains `NOT_EVALUATED` by the variant-specific rules. The L858R
case similarly reaches three claims for T790M and one disease-level claim.

All two-hop paths were present in the four-hop runs. The extra traversals
increased discoverable context but added zero context-matched claims in
these four cases. These are prototype path and rule-status counts. The
small snapshot and its existing synthetic cases do not support a
general claim about the value of four-hop retrieval on a larger graph.

## Task 10 — AURA3 provenance pilot

The report includes `source_links` alongside each path's original graph
`source` object. AURA3's existing PFS Claim carries two entry points:
the original publication via PubMed (PMID 27959700) and the CIViC
curator summary EID1867 from the 01-Nov-2026 release. The supplemental link
is marked `PFS_ONLY` and `PENDING_ONCOKG_REVIEW`. It is annotated at report
time after the graph source has passed the existing verification and the
AURA3 PMID and URL match the reviewed source.

Use `claim_ids` for distinct claims and `publication_pmids` for distinct
PubMed-identified publications within a case and hop budget. Count graph
paths separately. The number of source links expresses available entry
points, so two links for AURA3 still yield one Claim ID and one PMID.
Publication counts from this field exclude graph sources without a PMID.

This pilot surfaces one candidate provenance link for review. It does not
create a second trial finding or import the other outcomes in EID1867.

References: [AURA3 publication](https://pubmed.ncbi.nlm.nih.gov/27959700/),
[CIViC EID1867](https://civicdb.org/links/evidence_items/1867).
