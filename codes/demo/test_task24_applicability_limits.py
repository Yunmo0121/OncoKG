import unittest

from task17_report_context import build_ranked_report
from task23_review_support import K, select_with_review_support


class ApplicabilityLimitTests(unittest.TestCase):
    def setUp(self):
        self.primary = ["outcome_1", "outcome_2", "context"]
        self.candidate_order = [*self.primary, "review_source"]
        self.claims = {
            claim_id: {
                "claim_id": claim_id, "claim_type": claim_type, "context_status": status,
                "status_explanation": explanation, "review_status": "synthetic_fixture",
                "source_urls": [f"https://example.org/{claim_id}"],
            }
            for claim_id, claim_type, status, explanation in (
                ("outcome_1", "TRIAL_OUTCOME", "CONTEXT_MATCHED", "Synthetic trial outcome 1."),
                ("outcome_2", "TRIAL_OUTCOME", "CONTEXT_MATCHED", "Synthetic trial outcome 2."),
                ("context", "TRIAL_CONTEXT", "NOT_EVALUATED",
                 "This trial excluded prior exposure X, which is present in this synthetic case."),
                ("review_source", "RESISTANCE_ASSOCIATION", "CONTEXT_MATCHED",
                 "Synthetic evidence for resistance review."),
            )
        }
        self.limits = {"context": {"outcome_1", "outcome_2"}}

    def build_report(self, selected):
        flag = {"flag": "RESISTANCE_ASSOCIATION_REVIEW", "supporting_claim_ids": ["review_source"]}
        return build_ranked_report({
            "case_id": "SYN-APP-24", "limitations": [], "disclaimer": "Synthetic fixture",
            "evidence_claims": list(self.claims.values()), "missing_information": [],
            "safety_evidence_flags": [flag],
        }, selected, K, include_review_details=True)

    def test_preserves_sourced_limit_on_displayed_outcomes(self):
        baseline, _ = select_with_review_support(self.primary, self.candidate_order, self.claims)
        guarded, decisions = select_with_review_support(
            self.primary, self.candidate_order, self.claims, applicability_limits=self.limits,
        )
        self.assertEqual(baseline, ["outcome_1", "outcome_2", "review_source"])
        self.assertEqual(guarded, self.primary)
        self.assertEqual(decisions[0]["action"], "NO_REPLACEABLE_SLOT")
        self.assertEqual(decisions[0]["protected_applicability_limits"],
                         {"context": ["outcome_1", "outcome_2"]})
        baseline_report = self.build_report(baseline)
        guarded_report = self.build_report(guarded)
        self.assertEqual(len(baseline_report["research_review_flags"]), 1)
        self.assertEqual(guarded_report["research_review_flags"], [])
        self.assertIn("excluded prior exposure X", guarded_report["summary_lines"][2])
        self.assertEqual(guarded_report["evidence"][2]["source_urls"], ["https://example.org/context"])

    def test_replaces_generic_background_in_paired_control(self):
        self.claims["context"]["status_explanation"] = "General background for the synthetic trial."
        selected, decisions = select_with_review_support(
            self.primary, self.candidate_order, self.claims, applicability_limits={},
        )
        self.assertEqual(selected, ["outcome_1", "outcome_2", "review_source"])
        self.assertEqual(decisions[0]["replaced_claim_id"], "context")
        self.assertEqual(len(self.build_report(selected)["research_review_flags"]), 1)

    def test_limit_requires_a_source_and_visible_target(self):
        with self.subTest(reason="unshown target"):
            selected, _ = select_with_review_support(
                self.primary, self.candidate_order, self.claims,
                applicability_limits={"context": {"review_source", "context"}},
            )
            self.assertEqual(selected[-1], "review_source")
        with self.subTest(reason="missing source"):
            self.claims["context"]["source_urls"] = []
            selected, _ = select_with_review_support(
                self.primary, self.candidate_order, self.claims, applicability_limits=self.limits,
            )
            self.assertEqual(selected[-1], "review_source")


if __name__ == "__main__":
    unittest.main()
