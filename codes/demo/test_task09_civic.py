import unittest

from task09_civic import normalize_candidate


class CivicAlignmentTests(unittest.TestCase):
    def setUp(self):
        self.row = {
            "evidence_id": "123", "evidence_civic_url": "https://civicdb.org/links/evidence_items/123",
            "molecular_profile_id": "34", "molecular_profile": "EGFR T790M", "doid": "3908",
            "disease": "Lung Non-small Cell Carcinoma", "therapies": "Gefitinib,Erlotinib",
            "therapy_interaction_type": "Substitutes", "source_type": "PubMed", "citation_id": "42",
            "citation": "Example citation", "last_review_date": "", "evidence_type": "Predictive",
            "evidence_direction": "Supports", "evidence_level": "C", "significance": "Resistance",
            "variant_origin": "Somatic", "evidence_status": "accepted", "is_flagged": "false",
        }
        self.profile = {
            "name": "EGFR T790M", "molecular_profile_id": "34", "variant_ids": "34", "is_flagged": "false",
        }
        self.variant = {
            "variant_id": "34", "variant": "T790M", "feature_name": "EGFR", "feature_type": "Gene",
            "entrez_id": "1956", "single_variant_molecular_profile_id": "34", "is_flagged": "false",
        }

    def normalize(self):
        return normalize_candidate(self.row, self.profile, self.variant, {"42": ["local-claim"]})

    def test_shared_publication_stays_distinct_and_therapy_group_is_retained(self):
        candidate = self.normalize()
        self.assertEqual(candidate["candidate_id"], "CIViC:EID123")
        self.assertEqual(candidate["publication"]["same_pmid_oncokg_claim_ids"], ["local-claim"])
        self.assertEqual(candidate["mapping"]["variant_id"], "VARIANT:EGFR:T790M")
        self.assertEqual(candidate["source"]["therapy_interaction_type"], "Substitutes")
        self.assertEqual(candidate["mapping"]["drug_ids"], ["DRUG:ERLOTINIB", "DRUG:GEFITINIB"])
        self.assertEqual(candidate["review_status"], "PENDING_ONCOKG_REVIEW")

    def test_does_not_flatten_complex_profiles(self):
        self.profile["variant_ids"] = "33,34"
        with self.assertRaisesRegex(ValueError, "single-variant"):
            self.normalize()

    def test_other_disease_and_flagged_records_are_rejected(self):
        for field, value in (("doid", "3910"), ("is_flagged", "true")):
            with self.subTest(field=field):
                original = self.row[field]
                self.row[field] = value
                with self.assertRaisesRegex(ValueError, "pilot scope"):
                    self.normalize()
                self.row[field] = original

    def test_rejects_unmapped_drug(self):
        self.row["therapies"] = "Unknown"
        with self.assertRaisesRegex(ValueError, "Unmapped therapy"):
            self.normalize()


if __name__ == "__main__":
    unittest.main()
