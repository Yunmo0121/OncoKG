import unittest

from task23_review_support import select_with_review_support
from task25_trial_applicability import (
    OUTSIDE_REPORT, build_applicability_report, demo_input,
    find_applicability_checks, protection_map,
)


class ApplicabilityBoundaryTests(unittest.TestCase):
    def test_criterion_outside_top_three(self):
        for population in ("A", "B", None):
            with self.subTest(population=population):
                _, rows, trusted = demo_input("SYN-27", population)
                ranking = ["outcome_a", "outcome_b", "review", "eligibility"]
                case = {"synthetic": True, "prior_exposure": "X"}
                checks = find_applicability_checks(case, rows)
                selected, _ = select_with_review_support(
                    ranking, ranking, rows, applicability_limits=protection_map(checks),
                )
                report = build_applicability_report(trusted, selected, checks)
                self.assertEqual(selected, ranking[:3])
                expected = {"A": [OUTSIDE_REPORT] * 2, "B": [],
                            None: ["POPULATION_UNRESOLVED"] * 2}
                self.assertEqual([check["status"] for check in report["applicability_checks"]],
                                 expected[population])
                for check in report["applicability_checks"]:
                    self.assertNotIn("source_urls", check)
                    self.assertNotIn("criterion_id", check)
