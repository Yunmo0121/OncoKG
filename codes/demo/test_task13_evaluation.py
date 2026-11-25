import tempfile
import unittest
from pathlib import Path

from task11_review_pack import ANNOTATION_FIELDS, export_review_packet, write_csv
from task12_adjudication import OUTPUT_FIELDS, compare_annotations, read_packet
from task13_evaluation import FROZEN_STATUS, evaluate_rankings, freeze_reference


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.reference = {
            "review_set_id": "TEST",
            "reference_status": FROZEN_STATUS,
            "annotations": [
                {"case_id": case, "claim_id": claim, "label": label}
                for case, labels in (
                    ("hits", ["CONTEXT_MATCHED", "NOT_MATCHED"]),
                    ("abstains", ["CONTEXT_MATCHED", "NOT_EVALUATED"]),
                    ("unresolved", ["UNRESOLVED", "NOT_MATCHED"]),
                )
                for claim, label in zip(("one", "two"), labels)
            ],
        }
        self.predictions = {"system_id": "TEST-SYSTEM", "reference_sha256": "fixture",
                            "cases": [{"case_id": "hits", "claim_ids": ["one"]},
                                      {"case_id": "abstains", "claim_ids": []},
                                      {"case_id": "unresolved", "claim_ids": ["two"]}]}

    def test_scoring_uses_fixed_k_and_excludes_unresolved_cases(self):
        result = evaluate_rankings(self.reference, self.predictions, "fixture", 2)
        self.assertEqual(result["excluded_unresolved_case_ids"], ["unresolved"])
        self.assertEqual(result["scored_cases"], 2)
        self.assertEqual(result["metrics"]["macro_precision_all_cases"], 0.25)
        self.assertEqual(result["metrics"]["macro_recall_positive_cases"], 0.5)
        self.assertEqual(result["metrics"]["mrr_positive_cases"], 0.5)

    def test_rejects_wrong_reference_hash_and_missing_or_duplicate_rankings(self):
        with self.assertRaisesRegex(ValueError, "different reference"):
            evaluate_rankings(self.reference, self.predictions, "other", 2)
        self.predictions["cases"].pop()
        with self.assertRaisesRegex(ValueError, "include every case"):
            evaluate_rankings(self.reference, self.predictions, "fixture", 2)
        self.predictions["cases"].append(self.predictions["cases"][0])
        with self.assertRaisesRegex(ValueError, "duplicate prediction"):
            evaluate_rankings(self.reference, self.predictions, "fixture", 2)

    def test_freeze_preserves_provenance_and_rejects_unfinished_or_edited_review(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packet = root / "packet"
            export_review_packet(packet)
            _, keys = read_packet(packet)
            left, right, adjudication = (root / name for name in ("a.csv", "b.csv", "adjudication.csv"))
            completed = {"label": "NOT_EVALUATED", "reason": "Fixture only", "source_location": "Test"}
            first_case, first_claim = keys[0]
            reviewer_row = {"case_id": first_case, "claim_id": first_claim, **completed}
            write_csv(left, ANNOTATION_FIELDS, [reviewer_row])
            write_csv(right, ANNOTATION_FIELDS, [reviewer_row])
            _, rows = compare_annotations(keys, {keys[0]: completed}, {keys[0]: completed})
            write_csv(adjudication, OUTPUT_FIELDS, rows)
            with self.assertRaisesRegex(ValueError, "Complete the final label"):
                freeze_reference(packet, left, right, adjudication)

            for row in rows:
                row.update(final_label="NOT_EVALUATED", final_reason="Fixture only",
                           final_source_location="Test")
            write_csv(adjudication, OUTPUT_FIELDS, rows)
            frozen = freeze_reference(packet, left, right, adjudication)
            self.assertEqual(frozen["reference_status"], FROZEN_STATUS)
            self.assertEqual(frozen["label_counts"], {"NOT_EVALUATED": len(keys)})
            self.assertEqual(len(frozen["adjudication_csv_sha256"]), 64)

            rows[0]["a_reason"] = "Edited original"
            write_csv(adjudication, OUTPUT_FIELDS, rows)
            with self.assertRaisesRegex(ValueError, "was edited"):
                freeze_reference(packet, left, right, adjudication)


if __name__ == "__main__":
    unittest.main()
