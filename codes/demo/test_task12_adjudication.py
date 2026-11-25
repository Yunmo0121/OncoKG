import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from task11_review_pack import ANNOTATION_FIELDS, write_csv
from task12_adjudication import compare_annotations, read_annotations


class AdjudicationTests(unittest.TestCase):
    def setUp(self):
        self.ids = [(f"case-{n}", "claim") for n in range(5)]
        self.first = {"label": "NEEDS_INFORMATION", "reason": "First reason", "source_location": "Methods"}
        self.second = {"label": "NOT_MATCHED", "reason": "Other reason", "source_location": "Results"}

    def test_agreement_denominator_excludes_unpaired_labels(self):
        a, b, c, d, e = self.ids
        left = {a: self.first, b: self.first, c: self.first}
        right = {a: self.first, b: self.second, d: self.second}
        summary, rows = compare_annotations(self.ids, left, right)
        self.assertEqual(summary["paired_label_count"], 2)
        self.assertEqual(summary["exact_agreement"], 0.5)
        self.assertEqual([row["status"] for row in rows], [
            "AGREE", "DISAGREE", "MISSING_B", "MISSING_A", "MISSING_BOTH",
        ])
        self.assertEqual(rows[1]["a_reason"], self.first["reason"])
        self.assertEqual(rows[1]["b_source_location"], self.second["source_location"])
        self.assertEqual(rows[0]["final_label"], "")

    def test_unpaired_reviews_do_not_report_agreement(self):
        summary, _ = compare_annotations(self.ids, {}, {})
        self.assertIsNone(summary["exact_agreement"])

    def test_reader_rejects_duplicate_unexpected_and_unsupported_rows(self):
        case_id, claim_id = self.ids[0]
        row = {"case_id": case_id, "claim_id": claim_id, **self.first}
        variants = [
            ([row, row], "Duplicate"),
            ([dict(row, case_id="outside")], "Unknown"),
            ([dict(row, label="TREATMENT_RECOMMENDED")], "Invalid label"),
            ([dict(row, reason="")], "requires a reason"),
        ]
        with TemporaryDirectory() as directory:
            path = Path(directory) / "annotations.csv"
            for values, message in variants:
                with self.subTest(message=message):
                    write_csv(path, ANNOTATION_FIELDS, values)
                    with self.assertRaisesRegex(ValueError, message):
                        read_annotations(path, set(self.ids))

    def test_reader_preserves_original_reason_and_locator(self):
        case_id, claim_id = self.ids[0]
        with TemporaryDirectory() as directory:
            path = Path(directory) / "annotations.csv"
            row = {"case_id": case_id, "claim_id": claim_id, **self.first,
                   "reason": " Background, with a newline\n ",
                   "source_location": " Table 1 "}
            write_csv(path, ANNOTATION_FIELDS, [row])
            result = read_annotations(path, set(self.ids))
            self.assertEqual(result[self.ids[0]]["reason"], row["reason"])
            self.assertEqual(result[self.ids[0]]["source_location"], row["source_location"])


if __name__ == "__main__":
    unittest.main()
