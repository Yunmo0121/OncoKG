# Task 09 — CIViC evidence alignment pilot

This pilot stages four selected CIViC evidence items as candidates against the
existing NSCLC/EGFR graph. The sample was chosen to exercise both variant
mappings, publication overlap with OncoKG, and two CIViC items covering
different variants that cite the same publication. It is purposive;
counts should not be interpreted as coverage estimates.

## Release and mappings

- CIViC monthly snapshot **01-Nov-2026**. The loader checks the SHA-256 of the
  evidence, molecular profile and variant TSV files before reading them. The
  output includes each download location and hash. See the [data release
  documentation](https://docs.civicdb.org/en/latest/using/data_releases.html)
  and [CIViC licensing FAQ](https://docs.civicdb.org/en/latest/about/faq.html#how-is-civic-licensed).
- The selected evidence item must link to the profile, and the profile must
  resolve to exactly one supported EGFR variant. The mappings are CIViC variant
  33 to `VARIANT:EGFR:L858R` and 34 to `VARIANT:EGFR:T790M`.
  NCBI Gene 1956 maps to HGNC:3236 and the current `GENE:EGFR`.
  [NCBI Gene](https://www.ncbi.nlm.nih.gov/gene/1956)
- Disease mapping uses DOID:3908 for the existing `DISEASE:NSCLC`.
  [Disease Ontology](https://disease-ontology.org/term/DOID%3A3908/)
- The therapy mapping is restricted to three existing graph drug IDs. CIViC
  therapy names and interaction types are retained together on the source item.
  The mapped normalized IDs serve as entity references.
- Each record retains the CIViC evidence, molecular profile and variant IDs,
  CIViC review metadata, and the PubMed ID and URL for the cited publication.
  CIViC acceptance is separate from the local `PENDING_ONCOKG_REVIEW` status.
  The report omits free-text evidence statements, which remain accessible at
  the source.

## Observed pilot

| CIViC evidence item | Variant | PMID | Existing OncoKG publication link |
| --- | --- | --- | --- |
| [EID963](https://civicdb.org/links/evidence_items/963) | T790M | 24893891 | None |
| [EID1867](https://civicdb.org/links/evidence_items/1867) | T790M | 27959700 | AURA3-2017-T790M-OVERALL-PFS |
| [EID2158](https://civicdb.org/links/evidence_items/2158) | T790M | 15737014 | PAO-2005-T790M-GEFITINIB-ERLOTINIB-RESISTANCE |
| [EID4294](https://civicdb.org/links/evidence_items/4294) | L858R | 24893891 | None |

Four records refer to three publications. EID963 and EID4294 keep their separate
variant scopes and share the same PMID. EID1867 and EID2158 link to existing
OncoKG claims at publication level. Shared citation identity alone leaves
claim equivalence, context and independent corroboration unresolved.

All seven mapped entity IDs and two matched claim IDs were located in the
isolated Neo4j v0.2 snapshot by read-only queries. The database counts after
the check were 23 nodes and 32 relationships. The pilot output is a separate
candidate file. Research review of population, treatment line, prior exposure,
outcomes and potential overlap is pending before promotion into the corpus.

## Reproduce

Use the two local curated OncoKG source files in `data/curated/`. From the
repository root, download the three immutable-version inputs to a local directory:

```bash
release=01-Nov-2026
civic_input=data/raw/civic-task09
mkdir -p "$civic_input"
for table in ClinicalEvidenceSummaries MolecularProfileSummaries VariantSummaries; do
  file="$release-$table.tsv"
  curl -fL "https://civicdb.org/downloads/$release/$file" -o "$civic_input/$file"
done

python codes/demo/task09_civic.py --input-dir "$civic_input" \
  --output docs/results/task09-civic-candidates.json
python codes/demo/test_task09_civic.py
```

For a rerun, choose a different output filename or omit `--output` to print
deterministic JSON. The loader runs offline after the snapshots are available.
