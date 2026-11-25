import unittest

from task25_trial_applicability import (
    CONFLICT, OUTSIDE_REPORT, build_applicability_report, demo_input, find_applicability_checks,
)


class ReportBudgetTests(unittest.TestCase):
    def test_citations_and_flags_follow_visible_evidence(self):
        _, rows, trusted = demo_input("SYN-32", "A")
        ranking = ["outcome_a", "outcome_b", "review", "eligibility"]
        checks = find_applicability_checks({"synthetic": True, "prior_exposure": "X"}, rows)
        for budget, status, flags in ((2, OUTSIDE_REPORT, 0), (3, OUTSIDE_REPORT, 1),
                                      (4, CONFLICT, 1)):
            with self.subTest(budget=budget):
                report = build_applicability_report(trusted, ranking, checks, budget=budget)
                self.assertEqual([row["claim_id"] for row in report["evidence"]], ranking[:budget])
                self.assertEqual(len(report["research_review_flags"]), flags)
                self.assertEqual([item["status"] for item in report["applicability_checks"]], [status] * 2)
                for item in report["applicability_checks"]:
                    self.assertEqual(item.get("source_urls"), rows["eligibility"]["source_urls"]
                                     if budget == 4 else None)
        self.assertEqual(build_applicability_report(trusted, ranking, checks),
                         build_applicability_report(trusted, ranking, checks, budget=3))

    def test_invalid_budgets_are_rejected(self):
        for budget in (0, -1, True, 2.5):
            with self.subTest(budget=budget), self.assertRaises(ValueError):
                build_applicability_report({}, [], [], budget=budget)
