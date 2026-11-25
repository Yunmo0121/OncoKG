import copy
import unittest

from task19_report_audit import verify_report


class ReportAuditTests(unittest.TestCase):
    def setUp(self):
        self.report = {"k": 2, "methods": {"example": {"retrieved_claim_slots": 2, "reports": [{
            "case_id": "SYN-TEST", "llm_api_called": False,
            "evidence": [{"claim_id": "A", "source_urls": ["https://example.org/a"]},
                         {"claim_id": "B", "source_urls": ["https://example.org/b"]}],
            "research_review_flags": [{"flag": "REVIEW", "supporting_claim_ids": ["A"]}],
        }]}}}

    def test_exact_replay(self):
        self.assertEqual(verify_report(copy.deepcopy(self.report), self.report), 1)

    def test_rejects_edited_sources_order_and_review_support(self):
        for change, field in (
            (lambda row: row["evidence"][0]["source_urls"].append("https://example.org/changed"), "evidence"),
            (lambda row: row["evidence"].reverse(), "evidence"),
            (lambda row: row["research_review_flags"][0]["supporting_claim_ids"].append("C"),
             "research_review_flags"),
        ):
            with self.subTest(field=field):
                actual = copy.deepcopy(self.report)
                change(actual["methods"]["example"]["reports"][0])
                with self.assertRaisesRegex(ValueError, field):
                    verify_report(actual, self.report)

    def test_rejects_duplicate_cases_and_type_changes(self):
        actual = copy.deepcopy(self.report)
        rows = actual["methods"]["example"]["reports"]
        rows.append(rows[0])
        with self.assertRaisesRegex(ValueError, "Case list"):
            verify_report(actual, self.report)
        rows.pop()
        rows[0]["llm_api_called"] = 0
        with self.assertRaisesRegex(ValueError, "llm_api_called"):
            verify_report(actual, self.report)


if __name__ == "__main__":
    unittest.main()
