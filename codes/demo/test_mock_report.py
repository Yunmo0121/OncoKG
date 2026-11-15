"""Task 06A integration tests; run from the unchanged OncoKG project root."""
from __future__ import annotations
import copy
import unittest

from mock_report import build_mock_report, build_future_llm_payload, format_markdown
from safety_triage import load_case, get_report, evidence_triage


class MockReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.case = load_case("SYN-T790M-001")
        cls.task04 = get_report(cls.case, False, "", "", "")
        cls.task05 = evidence_triage(cls.case, cls.task04)
        cls.report = build_mock_report(cls.case, cls.task04, cls.task05)

    def test_claim_inventory(self):
        self.assertEqual(self.report["evidence_claim_count"], 5)
        self.assertEqual(len(self.report["evidence_claims"]), 5)

    def test_mode_and_origin(self):
        self.assertEqual(self.report["generation_mode"], "DETERMINISTIC_MOCK_NO_LLM")
        self.assertFalse(self.report["llm_api_called"])
        self.assertTrue(self.report["input_origin"].startswith("offline_"))

    def test_flaura_is_not_evaluated(self):
        f = next(x for x in self.report["evidence_claims"] if x["claim_id"].startswith("FLAURA"))
        self.assertEqual(f["context_status"], "NOT_EVALUATED")

    def test_t790m_fda_context_matched(self):
        f = next(x for x in self.report["evidence_claims"] if x["claim_id"].startswith("FDA-TAGRISSO-EGFR-T790M"))
        self.assertEqual(f["context_status"], "CONTEXT_MATCHED")

    def test_resistance_flags_not_hard_blocks(self):
        flags = {x["drug_mentioned_not_recommended"]: x["flag"] for x in self.report["safety_evidence_flags"]}
        self.assertEqual(flags["erlotinib"], "RESISTANCE_ASSOCIATION_REVIEW")
        self.assertEqual(flags["gefitinib"], "RESISTANCE_ASSOCIATION_REVIEW")
        self.assertEqual(flags["osimertinib"], "SAFETY_NOT_ASSESSED")
        self.assertEqual(self.report["automatic_exclusions"], [])

    def test_zero_treatment_recommendations(self):
        self.assertEqual(self.report["treatment_recommendations"], [])
        self.assertEqual(self.report["safety_clearances"], [])

    def test_all_claims_have_source_and_review_status(self):
        for x in self.report["evidence_claims"]:
            self.assertTrue(all(url.startswith("https://") for url in x["source_urls"]))
            self.assertEqual(x["review_status"], "source_checked_needs_independent_review")

    def test_wrong_task05_case_rejected(self):
        bad = copy.deepcopy(self.task05)
        bad["case_id"] = "OTHER"
        with self.assertRaises(ValueError):
            build_mock_report(self.case, self.task04, bad)

    def test_nonempty_auto_exclusions_rejected(self):
        bad = copy.deepcopy(self.task05)
        bad["auto_exclusions"] = ["gefitinib"]
        with self.assertRaises(ValueError):
            build_mock_report(self.case, self.task04, bad)

    def test_spurious_recommendation_rejected(self):
        bad = copy.deepcopy(self.task05)
        bad["drug_mentions_for_research_review"][0]["recommended"] = True
        with self.assertRaises(ValueError):
            build_mock_report(self.case, self.task04, bad)

    def test_report_deterministic(self):
        self.assertEqual(self.report, build_mock_report(self.case, self.task04, self.task05))

    def test_future_payload_never_sends(self):
        payload = build_future_llm_payload(self.report)
        self.assertFalse(payload["send_to_external_api"])
        self.assertEqual(len(payload["claim_evidence"]), 5)

    def test_markdown_contains_provenance_and_warning(self):
        md = format_markdown(self.report)
        self.assertIn("pubmed.ncbi.nlm.nih.gov", md)
        self.assertIn("Not permitted", md)
        self.assertIn("no LLM call", md)

    def test_unknown_history_case_has_missing_fields(self):
        case = load_case("SYN-T790M-UNKNOWN-003")
        t04 = get_report(case, False, "", "", "")
        t05 = evidence_triage(case, t04)
        rep = build_mock_report(case, t04, t05)
        self.assertGreater(len(rep["missing_information"]), 0)
        self.assertEqual(rep["treatment_recommendations"], [])

    def test_no_prior_case_not_same_as_unknown(self):
        case = load_case("SYN-T790M-NO-PRIOR-004")
        t04 = get_report(case, False, "", "", "")
        t05 = evidence_triage(case, t04)
        rep = build_mock_report(case, t04, t05)
        fda = next(x for x in rep["evidence_claims"] if x["claim_id"].startswith("FDA-TAGRISSO-EGFR-T790M"))
        self.assertEqual(fda["context_status"], "NOT_MATCHED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
