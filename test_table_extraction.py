"""
NexusAI v1.4 - Table-Aware Extraction Test Suite
================================================
Tests structured tabular chunking, markdown table parsing, spreadsheet row
serialization, header/column preservation, and fallback on malformed tables.
"""

import unittest
from services.table_extractor import TableAwareExtractor


class TestTableExtraction(unittest.TestCase):

    def test_01_headers_preserved_in_markdown_table(self):
        """1. Verify table headers are accurately extracted and preserved."""
        md = """
| Product | Q1 Revenue | Q2 Revenue |
| :--- | :--- | :--- |
| Alpha | $10M | $12M |
| Beta | $20M | $25M |
"""
        chunks = TableAwareExtractor.extract_markdown_tables(md, filename="sales.md", page_number=1)
        self.assertEqual(len(chunks), 1)
        chunk = chunks[0]
        self.assertIn("Headers: Product, Q1 Revenue, Q2 Revenue", chunk["text"])
        self.assertEqual(chunk["metadata"]["headers"], ["Product", "Q1 Revenue", "Q2 Revenue"])

    def test_02_rows_preserved(self):
        """2. Verify each table row is converted into relational text."""
        md = """
| Department | Headcount | Budget |
| :--- | :--- | :--- |
| Engineering | 120 | $5M |
| Marketing | 45 | $2M |
"""
        chunks = TableAwareExtractor.extract_markdown_tables(md, filename="dept.md", page_number=1)
        chunk = chunks[0]
        self.assertIn("Row 1 (Engineering) -> Department: Engineering | Headcount: 120 | Budget: $5M", chunk["text"])
        self.assertIn("Row 2 (Marketing) -> Department: Marketing | Headcount: 45 | Budget: $2M", chunk["text"])

    def test_03_columns_preserved(self):
        """3. Verify column count and identities are preserved in metadata."""
        md = """
| A | B | C | D |
| --- | --- | --- | --- |
| 1 | 2 | 3 | 4 |
"""
        chunks = TableAwareExtractor.extract_markdown_tables(md, filename="matrix.md")
        self.assertEqual(chunks[0]["metadata"]["col_count"], 4)

    def test_04_row_column_relationships_preserved(self):
        """4. Verify each cell value is explicitly paired with its column header."""
        md = """
| Country | Metric | 2025 | 2026 |
| --- | --- | --- | --- |
| Canada | GDP Growth | 2.1% | 2.4% |
"""
        chunks = TableAwareExtractor.extract_markdown_tables(md, filename="econ.md")
        text = chunks[0]["text"]
        self.assertIn("Country: Canada", text)
        self.assertIn("Metric: GDP Growth", text)
        self.assertIn("2025: 2.1%", text)
        self.assertIn("2026: 2.4%", text)

    def test_05_pdf_table_markdown_structure(self):
        """5. Verify table on page 3 of PDF preserves page_number=3."""
        md = """
| Asset | Value |
| --- | --- |
| Gold | $2,000 |
"""
        chunks = TableAwareExtractor.extract_markdown_tables(md, filename="report.pdf", page_number=3)
        self.assertEqual(chunks[0]["metadata"]["page_number"], 3)
        self.assertIn("Page: 3", chunks[0]["text"])

    def test_06_spreadsheet_table_serialization(self):
        """6. Verify openpyxl 2D raw rows are serialized into structured chunks."""
        sheet_data = [
            ["Metric", "Target", "Actual"],
            ["Uptime", "99.9%", "99.95%"],
            ["Latency", "50ms", "42ms"],
        ]
        chunks = TableAwareExtractor.serialize_spreadsheet_sheet(
            sheet_name="SLA_Metrics",
            sheet_data=sheet_data,
            filename="sla.xlsx",
        )
        self.assertTrue(len(chunks) >= 1)
        chunk_text = chunks[0]["text"]
        self.assertIn("[Spreadsheet Sheet: SLA_Metrics", chunk_text)
        self.assertIn("Columns: Metric, Target, Actual", chunk_text)
        self.assertIn("Metric: Uptime | Target: 99.9% | Actual: 99.95%", chunk_text)

    def test_07_page_and_sheet_metadata(self):
        """7. Verify spreadsheet metadata records sheet_name and filename."""
        sheet_data = [
            ["Item", "Price"],
            ["Widget", "10.00"],
        ]
        chunks = TableAwareExtractor.serialize_spreadsheet_sheet("Inventory", sheet_data, "inv.xlsx")
        self.assertEqual(chunks[0]["metadata"]["sheet_name"], "Inventory")
        self.assertEqual(chunks[0]["metadata"]["filename"], "inv.xlsx")

    def test_08_ownership_metadata_preservation(self):
        """8. Verify extraction chunks adhere to vector store chunk format."""
        md = """
| Col1 | Col2 |
| --- | --- |
| Val1 | Val2 |
"""
        chunks = TableAwareExtractor.extract_markdown_tables(md, filename="doc.txt")
        self.assertIn("metadata", chunks[0])
        self.assertIn("extraction_method", chunks[0]["metadata"])
        self.assertEqual(chunks[0]["metadata"]["extraction_method"], "table_extractor")

    def test_09_normal_text_unaffected(self):
        """9. Verify non-tabular plain prose returns empty list from table extractor."""
        prose = "This is a normal paragraph discussing economic policy without any tables or pipes."
        chunks = TableAwareExtractor.extract_markdown_tables(prose, filename="prose.txt")
        self.assertEqual(chunks, [], "Prose text must not generate false table chunks")

    def test_10_malformed_table_fallback(self):
        """10. Verify malformed table (unbalanced pipes or single row) is handled gracefully without crash."""
        malformed = "| Col1 | Col2\nNot a table divider\nJust some random lines"
        chunks = TableAwareExtractor.extract_markdown_tables(malformed, filename="bad.txt")
        self.assertIsInstance(chunks, list)


if __name__ == "__main__":
    unittest.main()
