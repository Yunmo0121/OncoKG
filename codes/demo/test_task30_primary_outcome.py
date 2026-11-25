import unittest

from task25_trial_applicability import CONFLICT
from task30_primary_outcome import run_case


class PrimaryOutcomeDemoTests(unittest.TestCase):
    def test_priority_changes_only_the_outcome_slot(self):
        for primary, omitted in (("outcome_a", "outcome_b"), ("outcome_b", "outcome_a")):
            with self.subTest(primary=primary):
                result = run_case(primary)
                report = result["report"]
                self.assertEqual([r["claim_id"] for r in report["evidence"]],
                                 [primary, "review", "eligibility"])
                self.assertEqual(result["omitted"], [omitted])
                self.assertEqual(report["applicability_checks"][0]["status"], CONFLICT)
                self.assertEqual(len(report["applicability_checks"]), 1)
                self.assertEqual(len(report["research_review_flags"]), 1)

    def test_unspecified_priority_preserves_baseline(self):
        result = run_case(None)
        self.assertEqual(result["decision"], "OUTCOME_PRIORITY_UNSPECIFIED")
        self.assertEqual(result["omitted"], ["eligibility"])
        with self.assertRaises(ValueError):
            run_case("review")
