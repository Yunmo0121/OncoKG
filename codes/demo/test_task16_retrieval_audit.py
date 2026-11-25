import unittest

from condition_retrieval import ALLOWED_CLAIMS
from task13_evaluation import score_claim_ranking
from task07_retrieval_pilot import summarize_rankings
from task16_retrieval_audit import BASELINE, METHODS, compare_pair, index_rankings


class RetrievalAuditTests(unittest.TestCase):
    def test_rejects_duplicate_missing_or_out_of_corpus_rankings(self):
        claim = sorted(ALLOWED_CLAIMS)[0]
        valid = {"case_id": "a", "claim_ids": [claim]}
        rankings = {method: [valid] for method in METHODS}
        self.assertEqual(index_rankings(rankings, {"a"})[BASELINE], {"a": [claim]})
        for rows in ([valid, valid], [], [dict(valid, claim_ids=[claim, claim])],
                     [dict(valid, claim_ids=["outside"])]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                index_rankings({**rankings, BASELINE: rows}, {"a"})

    def test_paired_omissions_handle_missing_positive_denominator(self):
        rankings = {"left": {"a": [], "b": []}, "right": {"a": ["hit"], "b": []}}
        references = {"a": {"hit"}, "b": set()}
        scores = {method: {cid: score_claim_ranking(order, references[cid], 3)
                           for cid, order in rows.items()} for method, rows in rankings.items()}
        summary = {method: summarize_rankings(list(rows.values())) for method, rows in scores.items()}
        result = compare_pair("left", "right", rankings, scores, summary, 3)
        self.assertEqual(result["case_hit_direction"], {"improved": 1, "tied": 1, "worsened": 0})
        self.assertAlmostEqual(result["delta"]["macro_precision_all_cases"], 1 / 6)
        self.assertIsNone(result["leave_one_out_deltas"]["a"]["macro_recall_positive_cases"])
        self.assertEqual(result["leave_one_out_ranges"]["macro_recall_positive_cases"],
                         {"min": 1.0, "max": 1.0})
        self.assertEqual(result["changed_top_k"][0]["added"], ["hit"])


if __name__ == "__main__":
    unittest.main()
