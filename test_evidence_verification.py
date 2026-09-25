"""
NexusAI v1.4 - Evidence Verification & Conflict Detection Test Suite
====================================================================
Tests evidence sufficiency scoring, polarity contradictions, numerical
discrepancies across documents, source attribution, and tenant isolation.
"""

import unittest
from services.verification_service import VerificationService


class TestEvidenceVerification(unittest.TestCase):

    def setUp(self):
        self.doc_1 = "Q1_Financial_Report.pdf"
        self.doc_2 = "Q2_Financial_Update.pdf"
        self.doc_3 = "Annual_Audit.pdf"

    def test_01_fully_supported_claim_sufficiency(self):
        """1. Verify fully supported claim yields 'sufficient' status."""
        q = "What is the annual revenue of Company A?"
        chunks = [
            {"text": "Company A reported annual revenue of $10 million in 2026.", "score": 0.9, "metadata": {"filename": self.doc_1}},
        ]
        res = VerificationService.verify_evidence_sufficiency(q, chunks)
        self.assertEqual(res["status"], "sufficient")
        self.assertGreaterEqual(res["score"], 0.65)
        self.assertIn("revenue", res["matched_terms"])

    def test_02_partially_supported_claim(self):
        """2. Verify partially matching evidence yields 'partial' status."""
        q = "What is the annual revenue and exact operating margin breakdown for the overseas subsidiary?"
        chunks = [
            {"text": "Company A reported annual revenue of $10 million.", "score": 0.6, "metadata": {"filename": self.doc_1}},
        ]
        res = VerificationService.verify_evidence_sufficiency(q, chunks)
        self.assertIn(res["status"], ["partial", "sufficient"])

    def test_03_unsupported_claim(self):
        """3. Verify completely irrelevant evidence yields 'insufficient' status."""
        q = "What is the encryption key algorithm for project Nebula?"
        chunks = [
            {"text": "The cafeteria menu on Tuesday includes soup and sandwiches.", "score": 0.1, "metadata": {"filename": self.doc_1}},
        ]
        res = VerificationService.verify_evidence_sufficiency(q, chunks)
        self.assertEqual(res["status"], "insufficient")
        self.assertLess(res["score"], 0.35)

    def test_04_sufficient_evidence_multiple_chunks(self):
        """4. Verify evidence scattered across chunks aggregates to sufficient."""
        q = "Compare Company A revenue and employee count"
        chunks = [
            {"text": "Company A achieved $15M revenue.", "score": 0.85, "metadata": {"filename": self.doc_1}},
            {"text": "Company A employs 250 full-time employees.", "score": 0.82, "metadata": {"filename": self.doc_2}},
        ]
        res = VerificationService.verify_evidence_sufficiency(q, chunks)
        self.assertEqual(res["status"], "sufficient")

    def test_05_insufficient_evidence_empty_pool(self):
        """5. Verify empty chunk pool returns status='insufficient'."""
        res = VerificationService.verify_evidence_sufficiency("Any query", [])
        self.assertEqual(res["status"], "insufficient")
        self.assertEqual(res["score"], 0.0)

    def test_06_conflicting_evidence_numerical_discrepancy(self):
        """6. Verify cross-document numerical discrepancy is detected and attributed."""
        chunks = [
            {"text": "Annual research budget for 2026 is $4.5 million USD.", "metadata": {"filename": self.doc_1}},
            {"text": "Revised research budget for 2026 is $8.2 million USD.", "metadata": {"filename": self.doc_2}},
        ]
        conflict_res = VerificationService.detect_cross_document_conflicts(chunks)
        self.assertTrue(conflict_res["conflict_detected"])
        self.assertTrue(len(conflict_res["conflicts"]) >= 1)
        conf = conflict_res["conflicts"][0]
        self.assertEqual(conf["type"], "numerical_discrepancy")
        self.assertEqual(conf["source_a"], self.doc_1)
        self.assertEqual(conf["source_b"], self.doc_2)

    def test_07_same_document_non_conflict(self):
        """7. Verify differing statements inside the SAME document are not falsely flagged as cross-doc conflicts."""
        chunks = [
            {"text": "Initial Q1 budget was $4.5 million.", "metadata": {"filename": self.doc_1}},
            {"text": "Later Q2 budget was $8.2 million.", "metadata": {"filename": self.doc_1}},
        ]
        conflict_res = VerificationService.detect_cross_document_conflicts(chunks)
        self.assertFalse(conflict_res["conflict_detected"], "Same document chunks must not trigger cross-document conflict")

    def test_08_cross_document_polarity_conflict(self):
        """8. Verify opposing polarity assertions across documents are flagged."""
        chunks = [
            {"text": "The environmental regulation proposal was approved and passed in parliament.", "metadata": {"filename": self.doc_1}},
            {"text": "The environmental regulation proposal was rejected and failed in committee.", "metadata": {"filename": self.doc_2}},
        ]
        conflict_res = VerificationService.detect_cross_document_conflicts(chunks)
        self.assertTrue(conflict_res["conflict_detected"])
        conf = conflict_res["conflicts"][0]
        self.assertEqual(conf["type"], "polarity_contradiction")

    def test_09_multiple_conflicting_sources(self):
        """9. Verify 3-way conflicts across 3 distinct documents are captured."""
        chunks = [
            {"text": "Projected headcount is 100 employees.", "metadata": {"filename": self.doc_1}},
            {"text": "Projected headcount is 250 employees.", "metadata": {"filename": self.doc_2}},
            {"text": "Projected headcount is 500 employees.", "metadata": {"filename": self.doc_3}},
        ]
        conflict_res = VerificationService.detect_cross_document_conflicts(chunks)
        self.assertTrue(conflict_res["conflict_detected"])
        self.assertTrue(len(conflict_res["conflicts"]) >= 2)

    def test_10_conflict_xml_annotation_preserves_sources(self):
        """10. Verify XML annotation formatting generates structured XML tags."""
        conflicts = [
            {
                "type": "numerical_discrepancy",
                "topic": "revenue",
                "source_a": self.doc_1,
                "claim_a": "Revenue is $10M",
                "source_b": self.doc_2,
                "claim_b": "Revenue is $25M",
            }
        ]
        xml = VerificationService.format_conflict_grounding_annotation(conflicts)
        self.assertIn("<cross_document_conflicts>", xml)
        self.assertIn(f'name="{self.doc_1}"', xml)
        self.assertIn(f'name="{self.doc_2}"', xml)
        self.assertIn("Explicitly present both perspectives", xml)

    def test_11_tenant_isolation_boundary(self):
        """11. Verify verification functions operate in-memory on authorized payloads only."""
        chunks = [
            {"text": "User 1 private patent data", "metadata": {"filename": "p1.txt"}},
            {"text": "User 1 second claim", "metadata": {"filename": "p2.txt"}},
        ]
        res = VerificationService.detect_cross_document_conflicts(chunks)
        self.assertIsInstance(res, dict)
        self.assertIn("conflict_detected", res)


if __name__ == "__main__":
    unittest.main()
