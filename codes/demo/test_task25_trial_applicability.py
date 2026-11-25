import unittest

from task25_trial_applicability import (
    CONFLICT, MISSING, UNRESOLVED, build_applicability_report, demo_input,
    find_applicability_checks, protection_map, run_demo,
)


class TrialApplicabilityTests(unittest.TestCase):
    def test_fixed_budget_comparison(self):
        results = run_demo()
        expected = {
            "SYN-25-CONFLICT": (CONFLICT, "eligibility"),
            "SYN-25-OTHER-POPULATION": ("CONTEXT_MATCHED", "review"),
            "SYN-25-MISSING-EXPOSURE": (MISSING, "eligibility"),
            "SYN-25-UNKNOWN-POPULATION": (UNRESOLVED, "review"),
            "SYN-25-NO-CONFLICT": ("CONTEXT_MATCHED", "review"),
        }
        self.assertEqual({case["case_id"] for case in results["cases"]}, expected.keys())
        for case in results["cases"]:
            with self.subTest(case=case["case_id"]):
                status, last = expected[case["case_id"]]
                baseline, manual, detected = (case["methods"][method]
                                              for method in ("task23", "task24_manual", "task25"))
                self.assertEqual(baseline["selected"][-1], "review")
                self.assertEqual(len(baseline["missed_limit_links"]), 2 if last == "eligibility" else 0)
                self.assertEqual(manual["selected"], detected["selected"])
                self.assertEqual(detected["selected"], ["outcome_a", "outcome_b", last])
                self.assertEqual(detected["displaced"], ["eligibility"] if last == "review" else [])
                self.assertEqual(detected["missed_limit_links"], [])
                self.assertEqual(detected["extra_limit_links"], [])
                self.assertEqual(detected["review_support_retained"], last == "review")
                report = detected["report"]
                self.assertEqual([row["context_status"] for row in report["evidence"][:2]], [status, status])
                self.assertEqual(len(report["applicability_checks"]), 0 if status == "CONTEXT_MATCHED" else 2)
                if last == "eligibility":
                    self.assertEqual(report["applicability_checks"][0]["source_urls"],
                                     ["https://example.org/eligibility"])
                if status == MISSING:
                    self.assertIn("missing case field prior_exposure", report["summary_lines"][0])
                if status == UNRESOLVED:
                    self.assertIn("outcome-to-population mapping", report["summary_lines"][0])
                    self.assertNotIn("criterion_id", report["applicability_checks"][0])

    def test_never_matches_a_different_study_or_unsourced_criterion(self):
        case = {"synthetic": True, "prior_exposure": "X"}
        _, rows, _ = demo_input("test", "A")
        rows["eligibility"]["trial_id"] = "OTHER-STUDY"
        self.assertEqual(find_applicability_checks(case, rows), [])
        rows["eligibility"].update(trial_id="SYN-TRIAL", source_urls=[])
        self.assertEqual(find_applicability_checks(case, rows), [])

    def test_missing_outcome_population_stays_unresolved(self):
        _, rows, _ = demo_input("test", "A")
        del rows["outcome_a"]["population_id"]
        checks = find_applicability_checks({"synthetic": True, "prior_exposure": "X"}, rows)
        self.assertEqual(protection_map(checks), {"eligibility": {"outcome_b"}})
        self.assertEqual(checks[0]["status"], UNRESOLVED)

    def test_outside_budget_criterion_yields_uncertainty_without_citation(self):
        _, rows, trusted = demo_input("test", "A")
        rows["outcome_a"]["status_explanation"] = "The context matches all checked fields."
        checks = find_applicability_checks({"synthetic": True, "prior_exposure": "X"}, rows)
        report = build_applicability_report(trusted, ["outcome_a", "outcome_b", "review"], checks)
        self.assertEqual(report["applicability_checks"][0], {
            "outcome_id": "outcome_a", "status": "LIMIT_SOURCE_OUTSIDE_REPORT",
        })
        self.assertIn("eligibility source is outside this report", report["summary_lines"][0])
        self.assertNotIn("context matches", report["summary_lines"][0])
        self.assertNotIn("https://example.org/eligibility", str(report))
        self.assertEqual(rows["outcome_a"]["context_status"], "CONTEXT_MATCHED")

    def test_requires_explicit_synthetic_input(self):
        _, rows, _ = demo_input("test", "A")
        with self.assertRaisesRegex(ValueError, "synthetic"):
            find_applicability_checks({"prior_exposure": "X"}, rows)


if __name__ == "__main__":
    unittest.main()
