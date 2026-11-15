"""OncoKG Task 03 — safe, research-only T790M incremental import.

Reads the *existing* T790M evidence-extraction v0.2 JSON and *existing* v0.1
JSON without changing them. --dry-run does not connect to Neo4j.
--check-db reads only; --apply requires an explicit confirmation string.

Usage from OncoKG project root:
  codes/demo/.venv/bin/python codes/demo/import_t790m_incremental.py --dry-run
  codes/demo/.venv/bin/python codes/demo/import_t790m_incremental.py --check-db
  codes/demo/.venv/bin/python codes/demo/import_t790m_incremental.py --apply

This is a research demonstration, NOT clinical decision support.
"""
import argparse
import hashlib
import json
from getpass import getpass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_NEW = ROOT / 'data' / 'curated' / 'egfr_t790m_evidence_extraction_v0_2.json'
DEFAULT_BASE = ROOT / 'data' / 'curated' / 'egfr_l858r_evidence_v0_1.json'
BASE_ID = 'ONCOKG-NSCLC-EGFR-REAL-EVIDENCE-V0.1'
NEW_ID = 'ONCOKG-NSCLC-EGFR-T790M-EXTRACTION-V0.2'
BASE_NODES = 9
BASE_LINKS = 10


def load(path):
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def validate_input(data, baseline):
    if baseline.get('dataset_id') != BASE_ID or len(baseline.get('claims', [])) != 2:
        raise ValueError('The baseline JSON is not the previously imported v0.1 dataset.')
    if data.get('dataset_id') != NEW_ID or data.get('research_only') is not True:
        raise ValueError('Unexpected T790M dataset or missing research_only flag.')
    claims = data.get('claims', [])
    if len(claims) != 3 or len({c.get('id') for c in claims}) != 3:
        raise ValueError('Expected exactly 3 distinct T790M claims.')
    by_kind = {c['kind']: c for c in claims}
    if set(by_kind) != {'APPROVED_INDICATION', 'TRIAL_OUTCOME', 'RESISTANCE_ASSOCIATION'}:
        raise ValueError('Expected regulatory, trial and resistance claim types.')
    for claim in claims:
        if claim['variant']['protein_label'] != 'T790M' or claim['variant']['hgvs_p'] != 'p.Thr790Met':
            raise ValueError('All T790M records must identify EGFR p.Thr790Met.')
        if claim['variant'].get('hgvs_c') is not None:
            raise ValueError('hgvs_c must remain null until a reference transcript is verified.')
        if claim.get('curation_status') != 'source_checked_needs_independent_review':
            raise ValueError('Unexpected medical review status.')
        if not claim['source']['url'].startswith('https://'):
            raise ValueError('Missing HTTPS evidence URL.')
    fda = by_kind['APPROVED_INDICATION']
    if (fda['drug'] != 'osimertinib' or fda['clinical_context']['progression_condition']
            != 'on_or_after_prior_egfr_tki'):
        raise ValueError('FDA T790M treatment-context mapping is unexpected.')
    if fda['clinical_context']['treatment_line'] != 'previously_treated_not_necessarily_second_line':
        raise ValueError('T790M FDA claim must not assert exactly second-line treatment.')
    aura = by_kind['TRIAL_OUTCOME']
    if (aura['drug'] != 'osimertinib' or aura['clinical_context']['randomized_n'] != 419
            or aura['outcome']['osimertinib'] != 10.1 or aura['outcome']['platinum_pemetrexed'] != 4.4
            or aura['outcome']['is_l858r_only_result'] is not False):
        raise ValueError('AURA3 context/outcome does not match reviewed extraction.')
    resistance = by_kind['RESISTANCE_ASSOCIATION']
    if set(resistance['drugs']) != {'gefitinib', 'erlotinib'}:
        raise ValueError('Resistance claim may concern only gefitinib and erlotinib here.')
    if len({c['source']['url'] for c in claims}) != 3:
        raise ValueError('Expected three independently traceable sources.')
    return by_kind


def graph_plan(data, digest, by_kind):
    """Construct new graph elements only; reuse existing EGFR/NSCLC/osimertinib."""
    nodes = []  # (label, props, shared_with_v01)
    links = []  # (source_label, source_id, type, destination_label, destination_id)

    def add_node(label, shared=False, **props):
        nodes.append((label, props, shared))

    def add_link(a_label, a_id, rel, b_label, b_id):
        links.append((a_label, a_id, rel, b_label, b_id))

    add_node('Gene', True, id='GENE:EGFR', symbol='EGFR')
    add_node('Disease', True, id='DISEASE:NSCLC', code='NSCLC', name='non-small-cell lung cancer')
    add_node('Drug', True, id='DRUG:OSIMERTINIB', name='osimertinib')
    add_node('Dataset', id=NEW_ID, source_sha256=digest, research_only=True,
             schema_model='OncoKG-Schema-v0.2',
             source_schema_version=data['schema_version'],
             curated_on=data['curated_on'])
    add_node('Variant', id='VARIANT:EGFR:T790M', gene_symbol='EGFR',
             protein_label='T790M', hgvs_p='p.Thr790Met', transcript_unresolved=True)
    add_node('Drug', id='DRUG:GEFITINIB', name='gefitinib')
    add_node('Drug', id='DRUG:ERLOTINIB', name='erlotinib')
    add_node('TreatmentClass', id='TREATMENT_CLASS:EGFR_TKI',
             name='EGFR tyrosine kinase inhibitor')

    # Three distinct contexts: regulatory, trial and small early resistance study.
    contexts = {
        'APPROVED_INDICATION': ('PROGRESSION:ON_OR_AFTER_EGFR_TKI',
                                'Progression on or after an EGFR TKI'),
        'TRIAL_OUTCOME': ('PROGRESSION:DURING_FIRST_LINE_EGFR_TKI',
                          'Progression during first-line EGFR TKI in AURA3'),
        'RESISTANCE_ASSOCIATION': ('PROGRESSION:AFTER_GEFITINIB_OR_ERLOTINIB',
                                   'Acquired resistance after gefitinib or erlotinib in Pao 2005'),
    }
    for cid, description in contexts.values():
        add_node('ProgressionContext', id=cid, description=description)
    add_link('Variant', 'VARIANT:EGFR:T790M', 'IN_GENE', 'Gene', 'GENE:EGFR')

    for kind, claim in by_kind.items():
        claim_id = claim['id']
        ctx = claim['clinical_context']
        props = dict(id=claim_id, kind=kind,
                     research_only=True, curation_status=claim['curation_status'],
                     evidence_scope=claim['evidence_scope'],
                     clinical_context_json=json.dumps(ctx, sort_keys=True, ensure_ascii=False))
        if kind == 'APPROVED_INDICATION':
            props.update(population=ctx['population'], disease_stage=ctx['disease_stage'],
                         treatment_line=ctx['treatment_line'],
                         test_requirement=ctx['test_requirement'])
        elif kind == 'TRIAL_OUTCOME':
            props.update(analysis_population=ctx['analysis_population'],
                         trial_id=ctx['trial_id'],
                         outcome_json=json.dumps(claim['outcome'], sort_keys=True, ensure_ascii=False),
                         is_l858r_only_result=False)
        else:
            props.update(resistance_type=ctx['resistance_type'],
                         warning_only=True, hard_contraindication=False)
        add_node('Claim', **props)
        src = claim['source']
        ev_id = 'EVID:' + claim_id
        ev_props = dict(id=ev_id, source_type=src['type'],
                        title=src['title'], url=src['url'],
                        accessed_at=src['accessed_at'])
        for field in ('pmid', 'doi', 'journal', 'published_year', 'section'):
            if field in src:
                ev_props[field] = src[field]
        add_node('Evidence', **ev_props)
        add_link('Dataset', NEW_ID, 'CONTAINS_CLAIM', 'Claim', claim_id)
        add_link('Claim', claim_id, 'IN_DISEASE', 'Disease', 'DISEASE:NSCLC')
        add_link('Claim', claim_id, 'REQUIRES_VARIANT', 'Variant', 'VARIANT:EGFR:T790M')
        add_link('Claim', claim_id, 'HAS_EVIDENCE', 'Evidence', ev_id)
        progression_id, _ = contexts[kind]
        add_link('Claim', claim_id, 'HAS_PROGRESSION_CONTEXT', 'ProgressionContext', progression_id)
        if kind in ('APPROVED_INDICATION', 'TRIAL_OUTCOME'):
            add_link('Claim', claim_id, 'ABOUT_DRUG', 'Drug', 'DRUG:OSIMERTINIB')
            add_link('Claim', claim_id, 'REQUIRES_PRIOR_TREATMENT_CLASS',
                     'TreatmentClass', 'TREATMENT_CLASS:EGFR_TKI')
        else:
            # Claim-scoped association, NOT an absolute contraindication edge.
            for name in claim['drugs']:
                add_link('Claim', claim_id, 'ABOUT_DRUG', 'Drug', 'DRUG:' + name.upper())

    ids = [(label, props['id']) for label, props, _ in nodes]
    if len(ids) != len(set(ids)) or len(links) != len(set(links)):
        raise ValueError('Duplicate node IDs or relationships in plan.')
    assert all(rel not in {'CONTRAINDICATED_IN', 'BLOCKED', 'RESISTANT_TO'} for _, _, rel, _, _ in links)
    return nodes, links


def db_counts(tx):
    n = tx.run('MATCH (n) RETURN count(n) AS n').single(strict=True)['n']
    r = tx.run('MATCH ()-[r]->() RETURN count(r) AS r').single(strict=True)['r']
    return n, r


def db_status(tx, new_nodes, new_links, digest, base_digest):
    """Read-only safety checks; returns 'fresh' or 'repeat'."""
    baseline = tx.run('MATCH (d:Dataset {id:$id}) RETURN d.source_sha256 AS sha',
                      id=BASE_ID).single()
    if baseline is None or baseline['sha'] != base_digest:
        raise ValueError('Wrong Neo4j instance, or v0.1 baseline JSON differs from imported data. STOP.')
    new_marker = tx.run('MATCH (d:Dataset {id:$id}) RETURN d.source_sha256 AS sha',
                        id=NEW_ID).single()
    if new_marker is not None and new_marker['sha'] != digest:
        raise ValueError('T790M dataset ID already exists with another SHA256. STOP; review manually.')
    state = 'repeat' if new_marker is not None else 'fresh'
    total_nodes, total_links = db_counts(tx)
    expected_added_nodes = sum(not shared for _, _, shared in new_nodes)
    expected_added_links = len(new_links)
    expected = ((BASE_NODES, BASE_LINKS) if state == 'fresh' else
                (BASE_NODES + expected_added_nodes, BASE_LINKS + expected_added_links))
    if (total_nodes, total_links) != expected:
        raise ValueError(f'Unexpected database counts {(total_nodes, total_links)}, expected {expected} for {state}. STOP.')
    for label, props, shared in new_nodes:
        result = tx.run('MATCH (n {id:$id}) RETURN labels(n) AS labels, properties(n) AS props',
                        id=props['id']).data()
        if len(result) > 1:
            raise ValueError('Duplicate ID: ' + props['id'])
        if shared or state == 'repeat':
            if len(result) != 1 or label not in result[0]['labels']:
                raise ValueError('Missing/mismatched existing node: ' + props['id'])
            if any(result[0]['props'].get(key) != value for key, value in props.items()):
                raise ValueError('Unexpected existing node properties: ' + props['id'])
        elif result:
            raise ValueError('Unexpected preexisting new node: ' + props['id'])
    if state == 'repeat':
        for sl, sid, rel, dl, did in new_links:
            found = tx.run(
                f'MATCH (a:{sl} {{id:$sid}})-[r:{rel}]->(b:{dl} {{id:$did}}) RETURN count(r) AS n',
                sid=sid, did=did).single(strict=True)['n']
            if found != 1:
                raise ValueError(f'Missing or duplicated relationship: {sid} -[{rel}]-> {did}')
    return state, expected_added_nodes, expected_added_links


def write_tx(tx, nodes, links, digest, base_digest):
    state, added_nodes, added_links = db_status(tx, nodes, links, digest, base_digest)
    if state == 'repeat':
        return state, added_nodes, added_links
    for label, props, shared in nodes:
        if shared:
            continue
        # fixed labels from hard-coded definitions, never from untrusted JSON
        tx.run(f'CREATE (n:{label}) SET n = $props', props=props).consume()
    for sl, sid, rel, dl, did in links:
        result = tx.run(
            f'MATCH (a:{sl} {{id:$sid}}) MATCH (b:{dl} {{id:$did}}) '
            f'MERGE (a)-[r:{rel}]->(b) RETURN count(r) AS n',
            sid=sid, did=did).single(strict=True)
        if result['n'] != 1:
            raise ValueError('Relationship write failed; transaction will roll back.')
    expected = BASE_NODES + added_nodes, BASE_LINKS + added_links
    if db_counts(tx) != expected:
        raise ValueError('Post-write count mismatch; transaction will roll back.')
    return state, added_nodes, added_links


def main():
    p = argparse.ArgumentParser(description='OncoKG T790M research-only v0.2 incremental import')
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument('--dry-run', action='store_true', help='Offline preview; no Neo4j access')
    group.add_argument('--check-db', action='store_true', help='Read-only check for correct Neo4j instance')
    group.add_argument('--apply', action='store_true', help='Explicitly write v0.2 in a transaction')
    p.add_argument('--input', type=Path, default=DEFAULT_NEW)
    p.add_argument('--baseline', type=Path, default=DEFAULT_BASE)
    p.add_argument('--uri', default='bolt://localhost:7687')
    p.add_argument('--username', default='neo4j')
    p.add_argument('--database', default='neo4j')
    args = p.parse_args()
    try:
        data, digest = load(args.input)
        base, base_digest = load(args.baseline)
        by_kind = validate_input(data, base)
        nodes, links = graph_plan(data, digest, by_kind)
        added = sum(not shared for _, _, shared in nodes)
        if args.dry_run:
            print(f'DRY RUN PASS: 3 claims; +{added} nodes; +{len(links)} relationships.')
            print(f'Expected OncoKG-Real after import: {BASE_NODES+added} nodes, {BASE_LINKS+len(links)} relationships.')
            print('No database connection or writes performed.')
            return
        # Deferred import: offline dry run needs no Neo4j Python package.
        from neo4j import GraphDatabase
        confirmation = None
        if args.apply:
            confirmation = input('Type APPLY-T790M-V02 to authorize writing to OncoKG-Real: ').strip()
            if confirmation != 'APPLY-T790M-V02':
                raise ValueError('Confirmation mismatch: no database writes performed.')
        pw = getpass('Password for your OncoKG-Real Neo4j instance: ')
        with GraphDatabase.driver(args.uri, auth=(args.username, pw)) as driver:
            driver.verify_connectivity()
            with driver.session(database=args.database) as session:
                if args.check_db:
                    state, _, _ = session.execute_read(db_status, nodes, links, digest, base_digest)
                    print(f'DATABASE CHECK PASS: correct v0.1 baseline, T790M state={state}. No writes performed.')
                else:
                    state, n, r = session.execute_write(write_tx, nodes, links, digest, base_digest)
                    if state == 'repeat':
                        print('IMPORT PASS (idempotent): dataset already present and verified; no changes.')
                    else:
                        print(f'IMPORT PASS: added {n} nodes and {r} relationships; original v0.1 retained.')
                        print(f'Expected total: {BASE_NODES+n} nodes, {BASE_LINKS+r} relationships.')
        print('Research-only: independent medical review still required.')
    except (OSError, TypeError, KeyError, ValueError, ImportError, RuntimeError) as err:
        p.exit(1, f'STOP: {err}\n')
    except Exception as err:
        # Errors from Neo4j are reported, not hidden, but never claim transaction success.
        p.exit(1, f'NEO4J ERROR: {type(err).__name__}: {err}\n')


if __name__ == '__main__':
    main()
