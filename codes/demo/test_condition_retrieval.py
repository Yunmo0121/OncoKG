"""Offline unit tests for Task 04. No Neo4j connection or patient data."""
import json
import unittest
from pathlib import Path

from condition_retrieval import (
    CASES_FILE, ALLOWED_CLAIMS, evaluate, load_sources,
    match_claim, offline_claims, read_db_tx, validate_case, verify_records, verify_against_curated,
)


class ConditionRetrievalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        baseline, t790m, _ = load_sources()
        cls.rows = offline_claims(baseline, t790m)
        cls.by_id = {r["id"]: r for r in cls.rows}
        cls.cases = {c["case_id"]: c for c in json.loads(CASES_FILE.read_text())["cases"]}

    def test_inventory(self):
        self.assertEqual(set(self.by_id), ALLOWED_CLAIMS)
        self.assertTrue(verify_records(self.rows))

    def test_flaura_not_evaluated_and_not_l858r_specific(self):
        row = self.by_id["FLAURA-2018-EGFR-MUTATED-OVERALL-PFS"]
        self.assertEqual(row["variants"], [])
        self.assertEqual(match_claim(self.cases["SYN-L858R-002"], row)[0], "NOT_EVALUATED")

    def test_t790m_all_three_match_when_context_explicit(self):
        case = self.cases["SYN-T790M-001"]
        report = evaluate(case, self.rows, "unit_fixture")
        by_id = {r["claim_id"]: r for r in report["results"]}
        for cid in ["FDA-TAGRISSO-EGFR-T790M-POST-TKI", "AURA3-2017-T790M-OVERALL-PFS",
                    "PAO-2005-T790M-GEFITINIB-ERLOTINIB-RESISTANCE"]:
            self.assertEqual(by_id[cid]["status"], "CONTEXT_MATCHED")
        self.assertEqual(by_id["FDA-TAGRISSO-2026-1.3-EGFR-L858R"]["status"], "NOT_MATCHED")
        self.assertIn("NOT a contraindication", by_id["PAO-2005-T790M-GEFITINIB-ERLOTINIB-RESISTANCE"]["warning"])

    def test_l858r_first_line(self):
        case = self.cases["SYN-L858R-002"]
        self.assertEqual(match_claim(case, self.by_id["FDA-TAGRISSO-2026-1.3-EGFR-L858R"])[0],
                         "CONTEXT_MATCHED")
        self.assertEqual(match_claim(case, self.by_id["FDA-TAGRISSO-EGFR-T790M-POST-TKI"])[0],
                         "NOT_MATCHED")

    def test_missing_information_is_not_positive(self):
        case = self.cases["SYN-T790M-UNKNOWN-003"]
        for cid in ["FDA-TAGRISSO-EGFR-T790M-POST-TKI", "AURA3-2017-T790M-OVERALL-PFS",
                    "PAO-2005-T790M-GEFITINIB-ERLOTINIB-RESISTANCE"]:
            self.assertEqual(match_claim(case, self.by_id[cid])[0], "NEEDS_INFORMATION")

    def test_explicit_no_prior_tki_is_mismatch(self):
        case = self.cases["SYN-T790M-NO-PRIOR-004"]
        self.assertEqual(match_claim(case, self.by_id["FDA-TAGRISSO-EGFR-T790M-POST-TKI"])[0],
                         "NOT_MATCHED")
        self.assertEqual(match_claim(case, self.by_id["AURA3-2017-T790M-OVERALL-PFS"])[0],
                         "NOT_MATCHED")

    def test_no_gefitinib_does_not_assert_all_egfr_tki_resistance(self):
        case = dict(self.cases["SYN-T790M-001"])
        case["prior_drugs"] = ["osimertinib"]
        self.assertEqual(match_claim(case, self.by_id["PAO-2005-T790M-GEFITINIB-ERLOTINIB-RESISTANCE"])[0],
                         "NOT_MATCHED")

    def test_source_link_is_required(self):
        copy = [dict(r) for r in self.rows]
        copy[0]["evidence_urls"] = []
        with self.assertRaises(ValueError):
            verify_records(copy)

    def test_source_context_mismatch_rejected(self):
        actual = [dict(row) for row in self.rows]
        actual[0]["context_json"] = json.dumps({"treatment_line": "later_line"})
        with self.assertRaisesRegex(ValueError, "context mismatch"):
            verify_against_curated(actual, self.rows)

    def test_refuse_non_synthetic_case(self):
        case = dict(self.cases["SYN-T790M-001"])
        case["synthetic"] = False
        with self.assertRaises(ValueError):
            validate_case(case)

    def test_boolean_null_distinction(self):
        case = dict(self.cases["SYN-T790M-001"])
        case["prior_egfr_tki"] = "false"
        with self.assertRaises(ValueError):
            validate_case(case)

    def test_readonly_query_guards_against_wrong_database(self):
        # A tiny fake transaction to verify the guard checks counts first.
        class FakeResult:
            def __init__(self, data): self.data_ = data
            def single(self, strict=False): return self.data_
        class FakeTx:
            def __init__(self): self.calls = []
            def run(self, query, **kwargs):
                self.calls.append(query)
                return FakeResult({"n": 14} if "AS n" in query else {"r": 19})
        tx = FakeTx()
        with self.assertRaisesRegex(ValueError, "not expected v0.2"):
            read_db_tx(tx, {"x": "y"})
        self.assertTrue(all("CREATE" not in q and "MERGE" not in q and "DELETE" not in q
                            for q in tx.calls))


if __name__ == "__main__":
    unittest.main(verbosity=2)
