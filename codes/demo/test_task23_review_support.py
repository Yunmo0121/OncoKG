import unittest

from task23_review_support import audit_items, select_with_review_support


class ReviewSupportTests(unittest.TestCase):
    def setUp(self):
        self.candidates = {
            "matched": {"claim_type": "OTHER", "context_status": "CONTEXT_MATCHED"},
            "incomplete": {"claim_type": "OTHER", "context_status": "NEEDS_INFORMATION"},
            "background": {"claim_type": "OTHER", "context_status": "NOT_EVALUATED"},
            "mismatch": {"claim_type": "OTHER", "context_status": "NOT_MATCHED"},
            "support": {"claim_type": "RESISTANCE_ASSOCIATION", "context_status": "NEEDS_INFORMATION",
                        "source_urls": ["https://example.org/source"]},
        }

    def test_replaces_only_the_last_unprotected_row(self):
        primary = ["matched", "background", "mismatch"]
        selected, decisions = select_with_review_support(primary, [*primary, "support"], self.candidates)
        self.assertEqual(selected, ["matched", "background", "support"])
        self.assertEqual(decisions, [{
            "claim_id": "support", "context_status": "NEEDS_INFORMATION",
            "action": "REPLACE", "replaced_claim_id": "mismatch",
        }])
        self.assertEqual(primary, ["matched", "background", "mismatch"])

    def test_protects_context_matches_and_missing_information(self):
        self.candidates["matched_2"] = self.candidates["matched"].copy()
        primary = ["matched", "incomplete", "matched_2"]
        selected, decisions = select_with_review_support(primary, [*primary, "support"], self.candidates)
        self.assertEqual(selected, primary)
        self.assertEqual(decisions[0]["action"], "NO_REPLACEABLE_SLOT")

    def test_fills_open_slot_without_reordering(self):
        primary = ["matched", "background"]
        selected, decisions = select_with_review_support(primary, [*primary, "support"], self.candidates)
        self.assertEqual(selected, [*primary, "support"])
        self.assertEqual(decisions[0]["action"], "APPEND")

    def test_leaves_visible_support_in_place(self):
        primary = ["background", "support", "matched"]
        selected, decisions = select_with_review_support(primary, primary, self.candidates)
        self.assertEqual(selected, primary)
        self.assertEqual(decisions[0]["action"], "ALREADY_VISIBLE")

    def test_skips_mismatched_or_unsourced_support(self):
        primary = ["matched", "background", "mismatch"]
        support = self.candidates["support"]
        support["context_status"] = "NOT_MATCHED"
        self.assertEqual(select_with_review_support(primary, [*primary, "support"], self.candidates),
                         (primary, []))
        support.update(context_status="CONTEXT_MATCHED", source_urls=[])
        selected, decisions = select_with_review_support(primary, [*primary, "support"], self.candidates)
        self.assertEqual(selected, primary)
        self.assertEqual(decisions[0]["action"], "MISSING_SOURCE")

    def test_counts_shared_support_once_and_excludes_generic_flags(self):
        report = {
            "evidence": [], "missing_information": [],
            "research_review_flags": [
                {"drug_mentioned_not_recommended": "one", "flag": "RESISTANCE_CONTEXT_INCOMPLETE",
                 "supporting_claim_ids": ["support"]},
                {"drug_mentioned_not_recommended": "two", "flag": "RESISTANCE_CONTEXT_INCOMPLETE",
                 "supporting_claim_ids": ["support"]},
                {"drug_mentioned_not_recommended": "three", "flag": "SAFETY_NOT_ASSESSED",
                 "supporting_claim_ids": ["other"]},
            ],
        }
        self.assertEqual(audit_items(report)["targeted_review_support"],
                         {("RESISTANCE_CONTEXT_INCOMPLETE", ("support",))})


if __name__ == "__main__":
    unittest.main()
