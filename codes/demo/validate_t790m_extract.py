"""Validate the EGFR T790M v0.2 research extraction; does NOT access Neo4j."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'data' / 'curated' / 'egfr_t790m_evidence_extraction_v0_2.json'


def main():
    data = json.loads(DATA.read_text(encoding='utf-8'))
    assert data['dataset_id'] == 'ONCOKG-NSCLC-EGFR-T790M-EXTRACTION-V0.2'
    assert data['research_only'] is True
    claims = data['claims']
    assert len(claims) == 3
    assert len({c['id'] for c in claims}) == 3
    assert {c['kind'] for c in claims} == {'APPROVED_INDICATION', 'TRIAL_OUTCOME', 'RESISTANCE_ASSOCIATION'}
    for c in claims:
        assert c['variant']['protein_label'] == 'T790M'
        assert c['source']['url'].startswith('https://')
        assert c['curation_status'] == 'source_checked_needs_independent_review'
    reg = next(c for c in claims if c['kind'] == 'APPROVED_INDICATION')
    assert reg['clinical_context']['progression_condition'] == 'on_or_after_prior_egfr_tki'
    outcome = next(c for c in claims if c['kind'] == 'TRIAL_OUTCOME')
    assert outcome['outcome']['is_l858r_only_result'] is False
    assert outcome['outcome']['osimertinib'] == 10.1
    assert outcome['outcome']['platinum_pemetrexed'] == 4.4
    resistance = next(c for c in claims if c['kind'] == 'RESISTANCE_ASSOCIATION')
    assert set(resistance['drugs']) == {'gefitinib','erlotinib'}
    print('PASS: 3 research evidence claims; no Neo4j writes performed.')

if __name__ == '__main__':
    main()
