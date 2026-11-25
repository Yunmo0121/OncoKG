import unittest

from task08_multihop import enrich_paths, summarize_paths, select_cases


class MultihopTests(unittest.TestCase):
    def setUp(self):
        self.context = {
            "direct": {"status": "NEEDS_INFORMATION", "checks": ["MISSING: test"],
                       "source_urls": ["https://example.org/direct"], "warning": "Research only"},
            "background": {"status": "NOT_EVALUATED", "checks": [],
                           "source_urls": ["https://example.org/background"], "warning": "Research only"},
        }
        self.direct = {"claim_id": "direct", "scope": "DIRECT_VARIANT", "hops": 2,
                       "source": {"url": "https://example.org/direct"}}
        self.background = {"claim_id": "background", "scope": "DISEASE_BACKGROUND", "hops": 4,
                           "source": {"url": "https://example.org/background"}}

    def test_carries_forward_context_without_promoting_reachability(self):
        rows = enrich_paths([self.direct, self.background], self.context)
        self.assertEqual(rows[0]["missing_context"], ["MISSING: test"])
        self.assertEqual(rows[1]["context_status"], "NOT_EVALUATED")

    def test_rejects_unverified_provenance(self):
        path = dict(self.direct, source={"url": "https://example.org/unrelated"})
        with self.assertRaisesRegex(ValueError, "provenance"):
            enrich_paths([path], self.context)

    def test_summary_counts_paths_and_unique_claims_separately(self):
        rows = enrich_paths([self.direct, self.direct, self.background], self.context)
        summary = summarize_paths(rows)
        self.assertEqual(summary["path_count"], 3)
        self.assertEqual(summary["claim_ids"], ["background", "direct"])
        self.assertEqual(summary["matched_claim_ids"], [])

    def test_case_selection_reports_unknown_ids(self):
        with self.assertRaisesRegex(ValueError, "Unknown synthetic case"):
            select_cases("no-such-case")

    def test_aura3_has_two_entry_points_and_one_claim_and_publication(self):
        claim_id = "AURA3-2017-T790M-OVERALL-PFS"
        pubmed_url = "https://pubmed.ncbi.nlm.nih.gov/27959700/"
        path = dict(self.direct, claim_id=claim_id, source={"url": pubmed_url, "pmid": "27959700"})
        context = {claim_id: dict(self.context["direct"], source_urls=[pubmed_url])}
        rows = enrich_paths([path], context)
        self.assertEqual([link["url"] for link in rows[0]["source_links"]], [
            pubmed_url, "https://civicdb.org/links/evidence_items/1867",
        ])
        self.assertEqual(rows[0]["source_links"][1]["review_status"], "PENDING_ONCOKG_REVIEW")
        self.assertEqual(summarize_paths(rows)["path_count"], 1)
        self.assertEqual(summarize_paths(rows)["claim_ids"], [claim_id])
        self.assertEqual(summarize_paths(rows + rows)["publication_pmids"], ["27959700"])

    def test_civic_link_requires_the_verified_aura3_pmid(self):
        claim_id = "AURA3-2017-T790M-OVERALL-PFS"
        path = dict(self.direct, claim_id=claim_id)
        context = {claim_id: self.context["direct"]}
        with self.assertRaisesRegex(ValueError, "AURA3 publication"):
            enrich_paths([path], context)


if __name__ == "__main__":
    unittest.main()
