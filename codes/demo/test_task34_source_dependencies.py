import unittest

from task25_trial_applicability import CONFLICT
from task34_source_dependencies import compare


class SourceDependencyTests(unittest.TestCase):
    def test_joint_review_requires_both_sources_and_four_slots(self):
        (baseline, _), (selected, report) = compare("joint_review", 3)
        self.assertEqual(selected, baseline)
        self.assertEqual(report["research_review_flags"], [])
        _, (selected, report) = compare("joint_review", 4)
        self.assertEqual(selected, ["outcome_a", "review", "review_extra", "eligibility"])
        self.assertEqual(len(report["research_review_flags"]), 1)
        self.assertEqual([item["status"] for item in report["applicability_checks"]], [CONFLICT])

    def test_cross_trial_and_additional_criterion(self):
        _, (_, report) = compare("two_trials", 4)
        self.assertEqual({item["outcome_id"] for item in report["applicability_checks"]}, {"outcome_a"})
        _, (_, report) = compare("two_criteria", 5)
        self.assertEqual({item["criterion_id"] for item in report["applicability_checks"]},
                         {"eligibility", "eligibility_extra"})

    def test_no_conflict_keeps_baseline(self):
        for budget in (3, 4, 5):
            baseline, selected = compare("no_conflict", budget)
            self.assertEqual(selected, baseline)
