import unittest

from task21_report_coverage import coverage_rows, summarize


class ReportCoverageTests(unittest.TestCase):
    def test_lists_exact_omissions_and_counts_unavailable_categories(self):
        reference = {"missing_checks": {("A", "missing test"), ("A", "missing stage")},
                     "review_flags": set()}
        observed = {"missing_checks": {("A", "missing test")}, "review_flags": set()}
        coverage = coverage_rows(reference, observed)
        self.assertEqual(coverage["missing_checks"]["omitted"], [("A", "missing stage")])
        result = summarize([{"coverage": coverage}])
        self.assertEqual(result["missing_checks"]["retained_fraction"], 0.5)
        self.assertEqual(result["missing_checks"]["cases_with_omissions"], 1)
        self.assertIsNone(result["review_flags"]["retained_fraction"])

    def test_rejects_a_ranked_item_absent_from_the_snapshot(self):
        with self.assertRaisesRegex(ValueError, "outside the full snapshot"):
            coverage_rows({"missing_checks": set()}, {"missing_checks": {("B", "not recorded")}})


if __name__ == "__main__":
    unittest.main()
