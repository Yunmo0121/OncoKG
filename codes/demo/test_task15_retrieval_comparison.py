import unittest

from task13_evaluation import FROZEN_STATUS, evaluate_rankings
from task15_retrieval_comparison import (
    BASELINE, DENSE, FUSED, assemble_rankings, compare_pilot, graph_ranking, reciprocal_rank_fusion,
)


class RetrievalComparisonTests(unittest.TestCase):
    def test_rejects_a_rank_export_from_a_different_evidence_snapshot(self):
        reference = {"reference_status": FROZEN_STATUS, "oncokg_dataset_sha256": {"dataset": "expected"}}
        predictions = {"reference_sha256": "reference", "oncokg_dataset_sha256": {"dataset": "other"}}
        with self.assertRaisesRegex(ValueError, "different evidence snapshot"):
            evaluate_rankings(reference, predictions, "reference", 3)

    def test_fusion_uses_both_ranks_and_breaks_ties_by_claim_id(self):
        self.assertEqual(reciprocal_rank_fusion(["b", "a", "c"], ["a", "b", "c"]),
                         ["a", "b", "c"])

    def test_context_and_depth_are_separate_and_paths_are_deduplicated(self):
        paths = [
            dict(claim_id="direct", hops=2, context_status="NOT_MATCHED"),
            dict(claim_id="direct", hops=4, context_status="NOT_MATCHED"),
            dict(claim_id="related", hops=4, context_status="CONTEXT_MATCHED"),
        ]
        self.assertEqual(graph_ranking(paths, ["related", "direct", "unused"], contextual=False),
                         ["direct", "related"])
        self.assertEqual(graph_ranking(paths, ["related", "direct", "unused"], contextual=True),
                         ["related", "direct"])

    def test_graph_arms_do_not_backfill_unreachable_claims(self):
        lexical = [dict(case_id="example", claim_ids=["a", "b"])]
        dense = [dict(case_id="example", claim_ids=["b", "a"])]
        paths = [dict(claim_id="b", hops=2, context_status="NEEDS_INFORMATION")]
        graph = {"cases": [{"case_id": "example", "budgets": {
            "2": {"paths": paths}, "4": {"paths": paths},
        }}]}
        results = assemble_rankings(lexical, dense, graph)
        self.assertEqual(len(results), 7)
        self.assertEqual(results[FUSED][0]["claim_ids"], ["a", "b"])
        self.assertEqual(results["kg_path_2hop"][0]["claim_ids"], ["b"])

    def test_diagnostics_audit_changes_in_relevant_claims_and_fixed_denominator(self):
        rankings = {
            BASELINE: [dict(case_id="example", claim_ids=["miss", "second_hit", "first_hit"])],
            DENSE: [dict(case_id="example", claim_ids=["first_hit"])],
        }
        known = [{"case": {"case_id": "example"}, "matched_claim_ids": ["first_hit", "second_hit"]}]
        result = compare_pilot(rankings, known, 2)
        row = result["diagnostics"][DENSE][0]
        self.assertEqual(row["gained_reference_claim_ids"], ["first_hit"])
        self.assertEqual(row["lost_reference_claim_ids"], ["second_hit"])
        self.assertEqual(row["precision"], 0.5)
        self.assertEqual(row["recall"], 0.5)


if __name__ == "__main__":
    unittest.main()
