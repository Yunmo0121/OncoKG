"""Offline tests; no Neo4j/database side effects or actual patient data."""
import copy
import unittest

from condition_retrieval import load_sources, offline_claims, evaluate
from safety_triage import evidence_triage, inspect_task04_report, load_case, RESISTANCE_CLAIM


class Task05SafetyTriageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base, t790m, _ = load_sources()
        cls.claims = offline_claims(base, t790m)

    def run_case(self, case_id):
        case = load_case(case_id)
        t4 = evaluate(case, self.claims, "test_offline_curated_json")
        return case, t4, evidence_triage(case, t4)

    def test_t790m_resistance_association_flagged_but_not_blocked(self):
        _, _, report = self.run_case("SYN-T790M-001")
        by_drug = {x["drug_mentioned_not_recommended"]: x for x in report["drug_mentions_for_research_review"]}
        self.assertEqual(by_drug["gefitinib"]["research_flag"], "RESISTANCE_ASSOCIATION_REVIEW")
        self.assertEqual(by_drug["erlotinib"]["research_flag"], "RESISTANCE_ASSOCIATION_REVIEW")
        self.assertTrue(by_drug["gefitinib"]["recorded_prior_exposure"])
        self.assertFalse(by_drug["erlotinib"]["recorded_prior_exposure"])
        self.assertFalse(any(x["automatic_exclusion"] for x in by_drug.values()))

    def test_osimertinib_never_cleared_or_recommended(self):
        _, _, report = self.run_case("SYN-T790M-001")
        osi = next(x for x in report["drug_mentions_for_research_review"] if x["drug_mentioned_not_recommended"] == "osimertinib")
        self.assertEqual(osi["research_flag"], "SAFETY_NOT_ASSESSED")
        self.assertFalse(osi["cleared_as_safe"])
        self.assertFalse(osi["recommended"])
        self.assertEqual(report["candidate_treatments_generated"], [])

    def test_unknown_treatment_history_does_not_mean_no_risk(self):
        _, _, report = self.run_case("SYN-T790M-UNKNOWN-003")
        for r in report["drug_mentions_for_research_review"]:
            if r["drug_mentioned_not_recommended"] in {"gefitinib", "erlotinib"}:
                self.assertEqual(r["research_flag"], "RESISTANCE_CONTEXT_INCOMPLETE")
                self.assertIsNone(r["recorded_prior_exposure"])

    def test_no_prior_exposure_does_not_result_in_safety_clearance(self):
        _, _, report = self.run_case("SYN-T790M-NO-PRIOR-004")
        for r in report["drug_mentions_for_research_review"]:
            if r["drug_mentioned_not_recommended"] in {"gefitinib", "erlotinib"}:
                self.assertEqual(r["research_flag"], "RESISTANCE_CLAIM_CONTEXT_NOT_MATCHED")
                self.assertFalse(r["cleared_as_safe"])

    def test_l858r_path_does_not_flag_t790m_historical_association(self):
        _, _, report = self.run_case("SYN-L858R-002")
        gf = next(x for x in report["drug_mentions_for_research_review"] if x["drug_mentioned_not_recommended"] == "gefitinib")
        self.assertEqual(gf["research_flag"], "RESISTANCE_CLAIM_CONTEXT_NOT_MATCHED")
        self.assertFalse(gf["automatic_exclusion"])

    def test_provenance_preserved(self):
        _, task04, report = self.run_case("SYN-T790M-001")
        self.assertEqual(report["evidence_inventory_claims"], 5)
        source_ids = {c["claim_id"] for d in report["drug_mentions_for_research_review"] for c in d["evidence_claims"]}
        self.assertEqual(source_ids, {x["claim_id"] for x in task04["results"]})
        resistance = next(c for d in report["drug_mentions_for_research_review"] for c in d["evidence_claims"] if c["claim_id"] == RESISTANCE_CLAIM)
        self.assertTrue(resistance["source_urls"][0].startswith("https://"))

    def test_no_hard_contraindication_data(self):
        _, _, report = self.run_case("SYN-T790M-001")
        self.assertEqual(report["screening_coverage"]["absolute_contraindications"], "NOT_IMPLEMENTED_NO_REVIEWED_RULES")
        self.assertEqual(report["auto_exclusions"], [])

    def test_refuse_unsafe_non_synthetic_case(self):
        case, task04, _ = self.run_case("SYN-T790M-001")
        case["synthetic"] = False
        with self.assertRaises(ValueError):
            evidence_triage(case, task04)

    def test_refuse_missing_claim(self):
        case, task04, _ = self.run_case("SYN-T790M-001")
        corrupted = copy.deepcopy(task04)
        corrupted["results"].pop()
        with self.assertRaises(ValueError):
            evidence_triage(case, corrupted)

    def test_refuse_missing_source_url(self):
        case, task04, _ = self.run_case("SYN-T790M-001")
        corrupted = copy.deepcopy(task04)
        corrupted["results"][0]["source_urls"] = []
        with self.assertRaises(ValueError):
            evidence_triage(case, corrupted)

    def test_refuse_changed_evidence_review_status(self):
        case, task04, _ = self.run_case("SYN-T790M-001")
        corrupted = copy.deepcopy(task04)
        corrupted["results"][0]["curation_status"] = "clinically_approved"
        with self.assertRaises(ValueError):
            evidence_triage(case, corrupted)

    def test_no_source_claim_mislabeled_as_hard_block(self):
        _, _, report = self.run_case("SYN-T790M-001")
        for r in report["drug_mentions_for_research_review"]:
            self.assertNotIn("BLOCK", r["research_flag"])
            self.assertFalse(r["recommended"])

    def test_all_four_synthetic_cases(self):
        for case_id in ["SYN-T790M-001", "SYN-L858R-002", "SYN-T790M-UNKNOWN-003", "SYN-T790M-NO-PRIOR-004"]:
            with self.subTest(case_id=case_id):
                _, _, report = self.run_case(case_id)
                self.assertTrue(report["synthetic"])
                self.assertEqual(len(report["drug_mentions_for_research_review"]), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
