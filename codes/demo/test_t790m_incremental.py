"""Offline invariants for the T790M incremental-import plan (no Neo4j access)."""
import unittest
from import_t790m_incremental import (
    DEFAULT_NEW, DEFAULT_BASE, NEW_ID, load, validate_input, graph_plan
)


class T790MImportPlanTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data, digest = load(DEFAULT_NEW)
        base, _ = load(DEFAULT_BASE)
        cls.plan = graph_plan(data, digest, validate_input(data, base))
        cls.data = data

    def test_three_distinct_claims(self):
        self.assertEqual({c['kind'] for c in self.data['claims']},
                         {'APPROVED_INDICATION', 'TRIAL_OUTCOME', 'RESISTANCE_ASSOCIATION'})

    def test_safe_scope_not_block(self):
        nodes, links = self.plan
        rels = [rel for _, _, rel, _, _ in links]
        self.assertNotIn('CONTRAINDICATED_IN', rels)
        self.assertNotIn('RESISTANT_TO', rels)
        resistance = next(n for label, n, _ in nodes
                          if label == 'Claim' and n['kind'] == 'RESISTANCE_ASSOCIATION')
        self.assertIs(resistance['hard_contraindication'], False)

    def test_context_is_explicit(self):
        _, links = self.plan
        self.assertEqual(sum(r == 'REQUIRES_PRIOR_TREATMENT_CLASS'
                             for _, _, r, _, _ in links), 2)
        self.assertEqual(sum(r == 'HAS_PROGRESSION_CONTEXT'
                             for _, _, r, _, _ in links), 3)
        self.assertEqual(sum(r == 'REQUIRES_VARIANT'
                             for _, _, r, _, _ in links), 3)

    def test_no_false_l858r_subgroup(self):
        nodes, _ = self.plan
        aura = next(n for label, n, _ in nodes
                    if label == 'Claim' and n['kind'] == 'TRIAL_OUTCOME')
        self.assertIs(aura['is_l858r_only_result'], False)

    def test_reuses_existing_nodes(self):
        nodes, _ = self.plan
        shared = {props['id'] for _, props, is_shared in nodes if is_shared}
        self.assertEqual(shared, {'GENE:EGFR', 'DISEASE:NSCLC', 'DRUG:OSIMERTINIB'})
        dataset_ids = [props['id'] for label, props, _ in nodes if label == 'Dataset']
        self.assertEqual(dataset_ids, [NEW_ID])


if __name__ == '__main__':
    unittest.main(verbosity=2)
