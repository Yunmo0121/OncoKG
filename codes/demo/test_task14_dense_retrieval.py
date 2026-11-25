import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from condition_retrieval import ALLOWED_CLAIMS
from task14_dense_retrieval import MiniLMEncoder, build_rankings


class FixtureEncoder:
    def encode(self, texts):
        self.texts = texts
        return [[0.0, 1.0]] * 4 + [[1.0, 0.0], [1.0, 0.0]]


class DenseRetrievalTests(unittest.TestCase):
    def setUp(self):
        self.case = {"case_id": "TEST", "synthetic": True, "cancer_type": "NSCLC",
                     "gene": "EGFR", "variants": ["T790M"], "prior_egfr_tki": False}
        self.claims = sorted(ALLOWED_CLAIMS)
        self.documents = {claim_id: ["neutral term"] for claim_id in self.claims}

    def test_dense_uses_similarity_and_deterministic_ties(self):
        encoder = FixtureEncoder()
        rankings = build_rankings([self.case], self.documents, "dense_minilm", encoder)
        self.assertEqual(rankings[0]["claim_ids"], self.claims[-1:] + self.claims[:-1])
        self.assertEqual(len(encoder.texts), 6)
        query = json.loads(encoder.texts[-1])
        self.assertNotIn("case_id", query)
        self.assertNotIn("synthetic", query)
        self.assertIs(query["prior_egfr_tki"], False)

    def test_ranking_rejects_reference_fields(self):
        case = dict(self.case, matched_claim_ids=[self.claims[0]])
        with self.assertRaisesRegex(ValueError, "case input fields only"):
            build_rankings([case], self.documents, "lexical_bm25")

    def test_model_fingerprint_rejected_without_loading_optional_dependencies(self):
        with TemporaryDirectory() as temp:
            path = Path(temp)
            (path / "tokenizer.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "fingerprint mismatch"):
                MiniLMEncoder(path)


if __name__ == "__main__":
    unittest.main()
