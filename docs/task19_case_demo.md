# OncoKG retrieval report comparison — SYN-PILOT-03

Synthetic development case. Evidence limit: 3.

Context statuses and flags below are prototype outputs for research review.

## BM25

| Rank | Evidence claim | Context status | Sources |
| ---: | --- | --- | --- |
| 1 | `FDA-TAGRISSO-EGFR-T790M-POST-TKI` | `NOT_MATCHED` | [Primary 1](https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=5e81b4a7-b971-45e1-9c31-29cea8c87ce7) |
| 2 | `AURA3-2017-T790M-OVERALL-PFS` | `NOT_MATCHED` | [Primary 1](https://pubmed.ncbi.nlm.nih.gov/27959700/), [CIViC supplement, PFS only, pending review](https://civicdb.org/links/evidence_items/1867) |
| 3 | `FDA-TAGRISSO-2026-1.3-EGFR-L858R` | `NOT_MATCHED` | [Primary 1](https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=5e81b4a7-b971-45e1-9c31-29cea8c87ce7) |

### Research review flags

No research review flag is supported by this report's retrieved evidence.

### Missing fields

No missing-field check was displayed within the retrieved evidence.

## KG context ranking (2 hops)

| Rank | Evidence claim | Context status | Sources |
| ---: | --- | --- | --- |
| 1 | `PAO-2005-T790M-GEFITINIB-ERLOTINIB-RESISTANCE` | `CONTEXT_MATCHED` | [Primary 1](https://pubmed.ncbi.nlm.nih.gov/15737014/) |
| 2 | `FDA-TAGRISSO-EGFR-T790M-POST-TKI` | `NOT_MATCHED` | [Primary 1](https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=5e81b4a7-b971-45e1-9c31-29cea8c87ce7) |
| 3 | `AURA3-2017-T790M-OVERALL-PFS` | `NOT_MATCHED` | [Primary 1](https://pubmed.ncbi.nlm.nih.gov/27959700/), [CIViC supplement, PFS only, pending review](https://civicdb.org/links/evidence_items/1867) |

### Research review flags

- `RESISTANCE_ASSOCIATION_REVIEW` for erlotinib (support: PAO-2005-T790M-GEFITINIB-ERLOTINIB-RESISTANCE).
- `RESISTANCE_ASSOCIATION_REVIEW` for gefitinib (support: PAO-2005-T790M-GEFITINIB-ERLOTINIB-RESISTANCE).

### Missing fields

No missing-field check was displayed within the retrieved evidence.
