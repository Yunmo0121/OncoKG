import unittest

from task07_retrieval_pilot import (
    bm25_scores, rank_claims, read_cases, score_ranking, summarize_rankings,
)


class RetrievalPilotTests(unittest.TestCase):
    def test_lexical_baseline_uses_text_and_deterministic_ties(self):
        scores = bm25_scores(["EGFR", "T790M"], {
            "b": ["egfr", "t790m"], "a": ["egfr", "t790m"], "c": ["egfr", "l858r"],
        })
        self.assertEqual(rank_claims(scores), ["a", "b", "c"])

    def test_context_reranking_preserves_lexical_order_within_status(self):
        scores = {"a": 3.0, "b": 2.0, "c": 1.0, "d": 0.0}
        statuses = {"a": "NOT_MATCHED", "b": "NEEDS_INFORMATION",
                    "c": "CONTEXT_MATCHED", "d": "NEEDS_INFORMATION"}
        self.assertEqual(rank_claims(scores, statuses), ["c", "b", "d", "a"])

    def test_ranking_metrics_keep_no_positive_cases_separate(self):
        positive = score_ranking(["c", "a", "b", "d"], {"a", "b"}, 2)
        negative = score_ranking(["c", "a", "b", "d"], set(), 2)
        self.assertEqual(positive, {"hits": 1, "retrieved": 2, "precision": 0.5,
                                    "recall": 0.5, "reciprocal_rank": 0.5})
        self.assertIsNone(negative["recall"])
        self.assertIsNone(negative["reciprocal_rank"])
        summary = summarize_rankings([positive, negative])
        self.assertEqual(summary["positive_cases"], 1)
        self.assertEqual(summary["no_positive_cases"], 1)
        self.assertEqual(summary["macro_precision_all_cases"], 0.25)
        self.assertEqual(summary["mrr_positive_cases"], 0.5)

    def test_pilot_has_distinct_cases_and_explicit_negative_references(self):
        cases = read_cases()
        self.assertEqual(len(cases), len({row["case"]["case_id"] for row in cases}))
        self.assertTrue(any(not row["matched_claim_ids"] for row in cases))
        self.assertTrue(any(row["needs_information_claim_ids"] for row in cases))
        self.assertTrue(any(row["resistance_review"] for row in cases))


if __name__ == "__main__":
    unittest.main()
