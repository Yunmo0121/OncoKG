"""Offline-only Task06B unit tests; they NEVER contact an LLM or Neo4j."""
from __future__ import annotations
import copy
import unittest
from unittest.mock import patch
from llm_report import (
    minimal_llm_input, messages_for, validate_model_response, wrap_result,
    call_api, PROVIDERS, trusted_mock_report,
)


class LLMReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = trusted_mock_report("SYN-T790M-001", False, "", "", "")
        cls.ids = [c["claim_id"] for c in cls.report["evidence_claims"]]
        cls.good = {
            "notes": [{"claim_id": cid, "text": "The recorded research context was inspected."} for cid in cls.ids],
            "limitations_note": "Independent review and comprehensive screening remain incomplete.",
        }

    def test_preview_payload_is_synthetic(self):
        p = minimal_llm_input(self.report)
        self.assertTrue(p["synthetic"])
        self.assertEqual(len(p["claims"]), 5)
        self.assertNotIn("prior_drugs", str(p))

    def test_prompt_instructs_json(self):
        self.assertIn("JSON", messages_for(minimal_llm_input(self.report))[0]["content"])

    def test_exact_claim_ids(self):
        self.assertEqual(len(validate_model_response(self.good, self.report)["notes"]), 5)

    def test_missing_claim_rejected(self):
        bad = copy.deepcopy(self.good); bad["notes"].pop()
        with self.assertRaises(ValueError): validate_model_response(bad, self.report)

    def test_unknown_claim_rejected(self):
        bad = copy.deepcopy(self.good); bad["notes"][0]["claim_id"] = "FAKE-CLAIM"
        with self.assertRaises(ValueError): validate_model_response(bad, self.report)

    def test_duplicate_claim_rejected(self):
        bad = copy.deepcopy(self.good); bad["notes"][1]["claim_id"] = self.ids[0]
        with self.assertRaises(ValueError): validate_model_response(bad, self.report)

    def test_extra_key_rejected(self):
        bad = copy.deepcopy(self.good); bad["dose"] = "abc"
        with self.assertRaises(ValueError): validate_model_response(bad, self.report)

    def test_extra_note_key_rejected(self):
        bad = copy.deepcopy(self.good); bad["notes"][0]["source_url"] = "https://fake.example"
        with self.assertRaises(ValueError): validate_model_response(bad, self.report)

    def test_dose_rejected(self):
        bad = copy.deepcopy(self.good); bad["notes"][0]["text"] = "Give 80 mg daily"
        with self.assertRaises(ValueError): validate_model_response(bad, self.report)

    def test_recommendation_rejected(self):
        bad = copy.deepcopy(self.good); bad["notes"][0]["text"] = "You should start treatment"
        with self.assertRaises(ValueError): validate_model_response(bad, self.report)

    def test_unsafe_chinese_rejected(self):
        bad = copy.deepcopy(self.good); bad["notes"][0]["text"] = "建议用药"
        with self.assertRaises(ValueError): validate_model_response(bad, self.report)

    def test_link_rejected(self):
        bad = copy.deepcopy(self.good); bad["notes"][0]["text"] = "See https://fake.example"
        with self.assertRaises(ValueError): validate_model_response(bad, self.report)

    def test_long_text_rejected(self):
        bad = copy.deepcopy(self.good); bad["notes"][0]["text"] = "X" * 181
        with self.assertRaises(ValueError): validate_model_response(bad, self.report)

    def test_untrusted_note_not_authoritative(self):
        wrap = wrap_result(self.report, validate_model_response(self.good, self.report), "glm", "example-model")
        self.assertEqual(wrap["treatment_recommendations"], [])
        self.assertEqual(wrap["automatic_exclusions"], [])
        self.assertEqual(wrap["safety_clearances"], [])
        self.assertTrue(wrap["requires_human_review"])
        self.assertEqual(wrap["claims_authoritative_from_task06a"], self.report["evidence_claims"])

    def test_no_network_in_unit_tests(self):
        with patch("llm_report.urllib.request.urlopen", side_effect=AssertionError("network call")):
            minimal_llm_input(self.report)
            validate_model_response(self.good, self.report)

    def test_api_requires_key(self):
        with self.assertRaises(ValueError):
            call_api(provider="glm", model="x", api_key="", messages=[])

    def test_provider_urls_are_https(self):
        self.assertTrue(all(u.startswith("https://") for u in PROVIDERS.values()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
