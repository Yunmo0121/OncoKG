import io
import json
import unittest
from zipfile import ZipFile

from task26_applicability_demo import build_entries, verify_bundle


class ApplicabilityBundleTests(unittest.TestCase):
    def test_bundle_replays_inputs_reports_and_summary_counts(self):
        entries = build_entries()
        self.assertEqual(entries, build_entries())
        manifest = json.loads(entries["manifest.json"])
        reports = json.loads(entries["reports.json"])
        self.assertEqual((manifest["cases"], manifest["reports"], manifest["k"]), (5, 15, 3))
        self.assertTrue(all(len(case["inputs"]["candidates"]) == 4 for case in reports["cases"]))
        summary = entries["comparison.md"].decode("utf-8")
        self.assertIn("| Task 23 原规则 | 4 | 0 | 5/5 |", summary)
        self.assertIn("| Task 25 自动识别 | 0 | 0 | 3/5 |", summary)
        buffer = io.BytesIO()
        with ZipFile(buffer, "w") as archive:
            for name, data in entries.items():
                archive.writestr(name, data)
        with ZipFile(buffer) as archive:
            verify_bundle(archive, entries)

    def test_rejects_modified_report_even_when_archive_is_readable(self):
        entries = build_entries()
        buffer = io.BytesIO()
        with ZipFile(buffer, "w") as archive:
            for name, data in entries.items():
                archive.writestr(name, b"{}" if name == "reports.json" else data)
        with ZipFile(buffer) as archive:
            with self.assertRaisesRegex(ValueError, "reports.json"):
                verify_bundle(archive, entries)


if __name__ == "__main__":
    unittest.main()
