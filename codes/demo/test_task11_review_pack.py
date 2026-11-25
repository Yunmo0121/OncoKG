import csv
import hashlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from condition_retrieval import CASES_FILE
from task11_review_pack import CASE_FIELDS, REVIEW_CASES, export_review_packet, read_review_cases


class ReviewPacketTests(unittest.TestCase):
    def test_renamed_development_case_is_rejected(self):
        development = json.loads(CASES_FILE.read_text())["cases"][0]
        candidate = {field: development.get(field) for field in CASE_FIELDS}
        candidate["case_id"] = "SYN-REVIEW-DUPLICATE"
        with TemporaryDirectory() as directory:
            path = Path(directory) / "cases.json"
            path.write_text(json.dumps({"review_set_id": "test", "cases": [candidate]}))
            with self.assertRaisesRegex(ValueError, "previously used case"):
                read_review_cases(path)

    def test_rejects_labels_inside_case_data(self):
        payload = json.loads(REVIEW_CASES.read_text())
        payload["cases"][0]["label"] = "hidden answer"
        with TemporaryDirectory() as directory:
            path = Path(directory) / "cases.json"
            path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "contain no labels"):
                read_review_cases(path)

    def test_export_has_complete_blank_template_and_matching_hashes(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "review"
            manifest = export_review_packet(path)
            with (path / "annotation.csv").open(newline="") as source:
                rows = list(csv.DictReader(source))
            self.assertEqual(len(rows), 60)
            self.assertEqual(len({(r["case_id"], r["claim_id"]) for r in rows}), 60)
            self.assertTrue(all(not any(r[key] for key in ("label", "reason", "source_location"))
                                for r in rows))
            for filename, digest in manifest["files_sha256"].items():
                self.assertEqual(hashlib.sha256((path / filename).read_bytes()).hexdigest(), digest)


if __name__ == "__main__":
    unittest.main()
