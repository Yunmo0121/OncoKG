import unittest

from task08_multihop import AURA3_PFS_CLAIM, AURA3_PRIMARY_URL
from task17_report_context import build_ranked_report, run_experiment


class RankedReportTests(unittest.TestCase):
    def setUp(self):
        self.trusted = {
            "case_id": "test", "limitations": [], "disclaimer": "Synthetic research",
            "evidence_claims": [
                {"claim_id": cid, "claim_type": "TRIAL_OUTCOME", "context_status": status,
                 "status_explanation": "scope only", "source_urls": [f"https://example.org/{cid}"],
                 "review_status": "pending"}
                for cid, status in (("A", "CONTEXT_MATCHED"), ("B", "NEEDS_INFORMATION"))
            ],
            "missing_information": [{"claim_id": "B", "check": "MISSING: test confirmation"}],
        }

    def test_rank_order_sources_and_missing_checks_are_preserved_under_top_k(self):
        report = build_ranked_report(self.trusted, ["B", "A"], 1)
        self.assertEqual([r["claim_id"] for r in report["evidence"]], ["B"])
        self.assertEqual(report["evidence"][0]["source_urls"], ["https://example.org/B"])
        self.assertEqual(report["missing_information"], self.trusted["missing_information"])
        self.assertNotIn("https://example.org/A", " ".join(report["summary_lines"]))
        self.assertEqual(report["treatment_recommendations"], [])
        self.assertFalse(report["llm_api_called"])

    def test_empty_and_omitted_claim_checks_are_handled(self):
        self.assertEqual(build_ranked_report(self.trusted, ["A"], 1)["missing_information"], [])
        report = build_ranked_report(self.trusted, [], 3)
        self.assertEqual(report["evidence"], [])
        self.assertIn("No evidence was retrieved", report["summary_lines"][0])

    def test_supplement_tracks_the_retrieved_claim_and_preserves_its_status(self):
        claim = self.trusted["evidence_claims"][0]
        claim.update(claim_id=AURA3_PFS_CLAIM, source_urls=[AURA3_PRIMARY_URL])
        self.trusted["safety_evidence_flags"] = []
        report = build_ranked_report(self.trusted, [AURA3_PFS_CLAIM], 1, include_review_details=True)
        row, = report["evidence"]
        self.assertEqual(row["source_urls"], [AURA3_PRIMARY_URL])
        link, = row["supplemental_source_links"]
        self.assertEqual(link["review_status"], "PENDING_ONCOKG_REVIEW")
        self.assertEqual(link["linked_scope"], "PFS_ONLY")
        self.assertEqual(row["context_status"], claim["context_status"])
        omitted = build_ranked_report(self.trusted, ["B", AURA3_PFS_CLAIM], 1, include_review_details=True)
        self.assertEqual(omitted["evidence"][0]["supplemental_source_links"], [])

    def test_review_flags_require_all_supporting_claims(self):
        flag = {"flag": "RESEARCH_REVIEW", "supporting_claim_ids": ["A", "B"]}
        self.trusted["safety_evidence_flags"] = [flag, {"flag": "UNSUPPORTED", "supporting_claim_ids": []}]
        short = build_ranked_report(self.trusted, ["A", "B"], 1, include_review_details=True)
        full = build_ranked_report(self.trusted, ["A", "B"], 2, include_review_details=True)
        self.assertEqual(short["research_review_flags"], [])
        self.assertEqual(full["research_review_flags"], [flag])
        self.assertEqual(full["safety_clearances"], [])

    def test_experiment_rejects_a_mismatched_snapshot_before_building_reports(self):
        from task07_retrieval_pilot import REFERENCE

        study = {"reference_type": REFERENCE, "official_evaluation": False, "pilot_sha256": "pilot",
                 "oncokg_dataset_sha256": {"dataset": "old"}}
        with self.assertRaisesRegex(ValueError, "evidence snapshot"):
            run_experiment(study, [], [], {"dataset": "new"}, "pilot", 3)


if __name__ == "__main__":
    unittest.main()
