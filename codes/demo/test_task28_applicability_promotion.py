import unittest

from task25_trial_applicability import demo_input, find_applicability_checks
from task28_applicability_promotion import promote_conflicting_criterion


class ApplicabilityPromotionTests(unittest.TestCase):
    def test_only_sourced_conflict_can_displace_review(self):
        ranking = ["outcome_a", "outcome_b", "review", "eligibility"]
        for population, exposure, sourced, third in (
            ("A", "X", True, "eligibility"), ("B", "X", True, "review"),
            (None, "X", True, "review"), ("A", None, True, "review"),
            ("A", "Y", True, "review"), ("A", "X", False, "review"),
        ):
            with self.subTest(population=population, exposure=exposure, sourced=sourced):
                _, rows, _ = demo_input("SYN-28", population)
                if not sourced:
                    rows["eligibility"]["source_urls"] = []
                checks = find_applicability_checks({"synthetic": True, "prior_exposure": exposure}, rows)
                self.assertEqual(promote_conflicting_criterion(ranking, rows, checks),
                                 ["outcome_a", "outcome_b", third])
                self.assertEqual(ranking[2], "review")
