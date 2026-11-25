import unittest

from task33_budget_comparison import SCENARIOS, compare


class BudgetComparisonTests(unittest.TestCase):
    def test_priority_swaps_only_in_two_confirmed_conflict_pairs(self):
        for scenario in SCENARIOS:
            for budget in (2, 3, 4):
                name, _, _, primary = scenario
                with self.subTest(case=name, budget=budget):
                    baseline, selected = compare(scenario, budget)
                    if name in {"primary_a", "primary_b"} and budget == 3:
                        self.assertEqual(selected["selected"], [primary, "review", "eligibility"])
                        self.assertEqual(selected["omitted"], [
                            "outcome_b" if primary == "outcome_a" else "outcome_a"
                        ])
                        self.assertEqual((baseline["conflicts"], selected["conflicts"]), (0, 1))
                        self.assertEqual((baseline["review_flags"], selected["review_flags"]), (1, 1))
                    else:
                        self.assertEqual(baseline, selected)
