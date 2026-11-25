"""Task07A tests: use local curated synthetic records; no model/API/DB writes."""
import copy
import unittest

from benchmark_task07 import read_expectations, DEFAULT_EXPECTATIONS, compare, run_benchmark
from condition_retrieval import load_sources, offline_claims


class Task07BenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.expectations = read_expectations(DEFAULT_EXPECTATIONS)
        base, t790m, _ = load_sources()
        cls.rows = offline_claims(base, t790m)

    def test_expected_inventory(self):
        self.assertEqual(len(self.expectations["cases"]), 4)
        self.assertEqual(len(self.expectations["claims_order"]), 5)

    def test_scoring_expected_pipeline(self):
        report = run_benchmark(self.rows, self.expectations, "offline_curated_json")
        self.assertEqual(report["metrics"]["claim_comparisons"], 20)
        self.assertEqual(report["metrics"]["research_flag_comparisons"], 12)
        self.assertEqual(report["metrics"]["engineering_status_agreement"], 1.0)
        self.assertEqual(report["metrics"]["engineering_flag_agreement"], 1.0)
        self.assertIsNone(report["metrics"]["clinical_accuracy_estimate"])

    def test_metric_detects_status_mismatch(self):
        report = run_benchmark(self.rows, self.expectations, "offline_curated_json")
        altered = copy.deepcopy(report["predictions"])
        altered[0]["status_by_claim"][self.expectations["claims_order"][0]] = "NEEDS_INFORMATION"
        _statuses, _flags, metrics = compare(altered, self.expectations)
        self.assertLess(metrics["engineering_status_agreement"], 1.0)

    def test_rejects_unsafe_auto_action(self):
        report = run_benchmark(self.rows, self.expectations, "offline_curated_json")
        altered = copy.deepcopy(report["predictions"])
        altered[0]["unsafe_auto_actions"] = 1
        with self.assertRaises(ValueError):
            compare(altered, self.expectations)

    def test_rejects_missing_case(self):
        report = run_benchmark(self.rows, self.expectations, "offline_curated_json")
        with self.assertRaises(ValueError):
            compare(report["predictions"][:-1], self.expectations)

    def test_unknown_case_never_becomes_not_matched_by_default(self):
        report = run_benchmark(self.rows, self.expectations, "offline_curated_json")
        p = next(x for x in report["predictions"] if x["case_id"] == "SYN-T790M-UNKNOWN-003")
        self.assertEqual(p["status_by_claim"]["FDA-TAGRISSO-EGFR-T790M-POST-TKI"], "NEEDS_INFORMATION")
        self.assertEqual(p["flags_by_drug"]["gefitinib"], "RESISTANCE_CONTEXT_INCOMPLETE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
