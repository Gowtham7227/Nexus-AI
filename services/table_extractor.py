"""
NexusAI v1.4 - Table-Aware Structural Extraction & Retrieval
============================================================
Preserves 2D row/column/header semantics during document ingestion,
enabling precise cell-level and relation-level retrieval over spreadsheets,
PDF tables, and tabular structured text.
"""

import re
from typing import List, Dict, Any, Optional, Tuple


class TableAwareExtractor:
    """
    Extracts tabular data into relationally structured chunks that preserve
    header hierarchy, row identifiers, and column attributes.
    """

    _RE_TABLE_ROW = re.compile(r"^\s*\|(.+)\|\s*$")
    _RE_TABLE_DIVIDER = re.compile(r"^\s*\|(?:\s*[-:]+\s*\|)+\s*$")
    _RE_CSV_ROW = re.compile(r"^(?:[^,\n]+,){2,}[^,\n]+$")
    _RE_TABULAR_QUERY = re.compile(
        r"\b(?:table|spreadsheet|sheet|row|column|cells?|tabular|financial\s+sheet|balance\s+sheet|quarterly|q[1-4]|yoy|metrics?\s+table)\b",
        re.IGNORECASE
    )

    @classmethod
    def is_tabular_query(cls, question: str) -> bool:
        """Deterministically detect if user query is targeting structured tabular data."""
        if not question:
            return False
        return bool(cls._RE_TABULAR_QUERY.search(question))

    @classmethod
    def extract_markdown_tables(
        cls,
        text: str,
        filename: str = "",
        page_number: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        Identify markdown-formatted tables in text and convert them into
        structured relational chunks with explicit column-header associations.
        """
        if not text or "|" not in text:
            return []

        lines = text.splitlines()
        chunks = []
        in_table = False
        headers: List[str] = []
        table_rows: List[List[str]] = []
        table_index = 1

        for line in lines:
            line_str = line.strip()
            if cls._RE_TABLE_ROW.match(line_str):
                if cls._RE_TABLE_DIVIDER.match(line_str):
                    # Divider line separating header from rows
                    in_table = True
                    continue

                cells = [c.strip() for c in line_str.strip("|").split("|")]
                if not in_table and not headers:
                    headers = cells
                else:
                    table_rows.append(cells)
            else:
                if in_table and table_rows and headers:
                    # Flush table chunk
                    chunk = cls._build_table_chunk(
                        headers=headers,
                        rows=table_rows,
                        filename=filename,
                        page_number=page_number,
                        table_index=table_index,
                    )
                    if chunk:
                        chunks.append(chunk)
                    table_index += 1
                    headers = []
                    table_rows = []
                    in_table = False

        if in_table and table_rows and headers:
            chunk = cls._build_table_chunk(
                headers=headers,
                rows=table_rows,
                filename=filename,
                page_number=page_number,
                table_index=table_index,
            )
            if chunk:
                chunks.append(chunk)

        return chunks

    @classmethod
    def _build_table_chunk(
        cls,
        headers: List[str],
        rows: List[List[str]],
        filename: str,
        page_number: int,
        table_index: int,
    ) -> Optional[Dict[str, Any]]:
        """Serialize parsed rows and headers into a rich relational text chunk."""
        if not headers or not rows:
            return None

        clean_headers = [h if h else f"Col_{idx+1}" for idx, h in enumerate(headers)]
        relational_lines = [f"[Structured Table {table_index} | Source: {filename} | Page: {page_number}]"]
        relational_lines.append(f"Headers: {', '.join(clean_headers)}")

        for row_idx, row in enumerate(rows, start=1):
            row_items = []
            row_key = row[0] if row else f"Row {row_idx}"
            for h, cell_val in zip(clean_headers, row):
                if cell_val:
                    row_items.append(f"{h}: {cell_val}")
            if row_items:
                relational_lines.append(f"Row {row_idx} ({row_key}) -> " + " | ".join(row_items))

        text_representation = "\n".join(relational_lines)
        return {
            "text": text_representation,
            "metadata": {
                "source": filename,
                "filename": filename,
                "page_number": page_number,
                "extraction_method": "table_extractor",
                "table_index": table_index,
                "row_count": len(rows),
                "col_count": len(headers),
                "headers": clean_headers,
            }
        }

    @classmethod
    def serialize_spreadsheet_sheet(
        cls,
        sheet_name: str,
        sheet_data: List[List[Any]],
        filename: str,
    ) -> List[Dict[str, Any]]:
        """
        Extract structured table rows from a 2D spreadsheet sheet (e.g. from openpyxl).
        """
        if not sheet_data or len(sheet_data) < 2:
            return []

        # First non-empty row as header
        raw_headers = sheet_data[0]
        headers = [str(h).strip() if h is not None and str(h).strip() else f"Col_{i+1}" for i, h in enumerate(raw_headers)]

        rows = []
        for raw_row in sheet_data[1:]:
            row_cells = [str(c).strip() if c is not None else "" for c in raw_row]
            if any(c for c in row_cells):
                rows.append(row_cells)

        if not rows:
            return []

        # Batch rows into manageable tabular chunks (e.g. 10 rows per chunk)
        batch_size = 10
        chunks = []
        for batch_idx in range(0, len(rows), batch_size):
            batch_rows = rows[batch_idx:batch_idx + batch_size]
            relational_lines = [f"[Spreadsheet Sheet: {sheet_name} | File: {filename} | Rows {batch_idx+1}-{batch_idx+len(batch_rows)}]"]
            relational_lines.append(f"Columns: {', '.join(headers)}")

            for idx, r in enumerate(batch_rows, start=batch_idx + 1):
                row_items = []
                row_key = r[0] if r else f"Row {idx}"
                for h, val in zip(headers, r):
                    if val:
                        row_items.append(f"{h}: {val}")
                if row_items:
                    relational_lines.append(f"Row {idx} ({row_key}) -> " + " | ".join(row_items))

            chunk_text = "\n".join(relational_lines)
            chunks.append({
                "text": chunk_text,
                "metadata": {
                    "source": filename,
                    "filename": filename,
                    "sheet_name": sheet_name,
                    "page_number": 1,
                    "extraction_method": "table_extractor",
                    "row_range": f"{batch_idx+1}-{batch_idx+len(batch_rows)}",
                }
            })

        return chunks
