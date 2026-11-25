import unittest

from task22_graph_backfill import append_expanded_candidates


class GraphBackfillTests(unittest.TestCase):
    def test_keeps_primary_order_and_appends_only_new_candidates(self):
        order = append_expanded_candidates(["B", "A"], ["A", "C", "B", "D"])
        self.assertEqual(order, ["B", "A", "C", "D"])
        self.assertEqual(order[:1], ["B"])

    def test_rejects_inconsistent_graph_snapshot(self):
        with self.assertRaisesRegex(ValueError, "must contain"):
            append_expanded_candidates(["B"], ["A"])


if __name__ == "__main__":
    unittest.main()
