import os
from typing import Dict, Any, List, Optional

from pypdf import PdfReader
from docx import Document
from pptx import Presentation
from openpyxl import load_workbook

from ocr_service import (
    detect_pdf_text_quality,
    perform_pdf_ocr,
    is_ocr_available,
    OCR_ENABLED,
)


def extract_document_content(file_path: str) -> Dict[str, Any]:
    """
    Unified production text extraction pipeline supporting:
    - PDF (Smart Native Text extraction + Automated Local OCR fallback for scanned pages)
    - DOCX (Paragraphs & Tables)
    - PPTX (Slide shapes & notes)
    - TXT (UTF-8 with encoding fallback)
    - XLSX (Worksheet rows & cells)

    Returns structured payload containing text, page-level breakdowns, and extraction metadata.
    """
    extension = os.path.splitext(file_path)[1].lower()
    doc_name = os.path.basename(file_path)

    print("=" * 60)
    print("DOCUMENT TEXT EXTRACTION")
    print("File:", doc_name)
    print("Extension:", extension)
    print("=" * 60)

    pages: List[Dict[str, Any]] = []
    full_text = ""
    extraction_method = "native"
    ocr_used = False
    page_count = 0
    ocr_page_count = 0

    try:
        # --------------------------------------------------
        # 1. PDF Documents (Native + Smart OCR)
        # --------------------------------------------------
        if extension == ".pdf":
            quality_info = detect_pdf_text_quality(file_path)
            total_pages = quality_info.get("total_pages", 0)
            page_count = total_pages
            needs_ocr = quality_info.get("needs_ocr", False)
            native_pages = quality_info.get("native_pages", [])

            print(f"📊 [PDF QUALITY] Pages: {total_pages} | Chars: {quality_info.get('total_chars')} | Meaningful Pages: {quality_info.get('meaningful_pages')}/{total_pages} | Needs OCR: {needs_ocr}")

            if not needs_ocr and native_pages:
                pages = native_pages
                full_text = "\n\n".join(p["text"] for p in pages if p["text"].strip())
                extraction_method = "native"
                ocr_used = False
                print("✅ [EXTRACTION] Native PDF text quality sufficient. Using native extraction.")
            else:
                print("⚡ [EXTRACTION] Native text quality insufficient. Triggering Local OCR...")
                try:
                    ocr_pages = perform_pdf_ocr(file_path)
                    pages = ocr_pages
                    full_text = "\n\n".join(p["text"] for p in pages if p["text"].strip())
                    extraction_method = "ocr"
                    ocr_used = True
                    ocr_page_count = len(ocr_pages)
                    print(f"✅ [EXTRACTION] Local OCR completed successfully ({len(ocr_pages)} pages).")
                except Exception as ocr_err:
                    print(f"⚠️ [OCR ERROR] Local OCR failed or unavailable: {ocr_err}")
                    if native_pages:
                        pages = native_pages
                        full_text = "\n\n".join(p["text"] for p in pages if p["text"].strip())
                        extraction_method = "native"
                        ocr_used = False
                        print("ℹ️ Falling back to available native text.")
                    else:
                        raise

        # --------------------------------------------------
        # 2. DOCX Documents
        # --------------------------------------------------
        elif extension == ".docx":
            document = Document(file_path)
            text_lines = []

            for paragraph in document.paragraphs:
                if paragraph.text.strip():
                    text_lines.append(paragraph.text.strip())

            for table in document.tables:
                for row in table.rows:
                    row_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if row_text:
                        text_lines.append(" | ".join(row_text))

            full_text = "\n".join(text_lines)
            pages = [{"page_number": 1, "text": full_text, "char_count": len(full_text), "extraction_method": "native"}]
            page_count = 1

        # --------------------------------------------------
        # 3. PPTX Documents
        # --------------------------------------------------
        elif extension == ".pptx":
            presentation = Presentation(file_path)
            slide_pages = []

            for slide_number, slide in enumerate(presentation.slides, start=1):
                slide_lines = []
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        shape_text = shape.text.strip()
                        if shape_text:
                            slide_lines.append(shape_text)

                slide_content = f"Slide {slide_number}\n" + "\n".join(slide_lines) if slide_lines else ""
                if slide_content.strip():
                    slide_pages.append({
                        "page_number": slide_number,
                        "text": slide_content,
                        "char_count": len(slide_content),
                        "extraction_method": "native",
                    })

            pages = slide_pages
            full_text = "\n\n".join(p["text"] for p in pages)
            page_count = len(presentation.slides)

        # --------------------------------------------------
        # 4. TXT Documents
        # --------------------------------------------------
        elif extension == ".txt":
            with open(file_path, "r", encoding="utf-8", errors="ignore") as file:
                full_text = file.read()
            pages = [{"page_number": 1, "text": full_text, "char_count": len(full_text), "extraction_method": "native"}]
            page_count = 1

        # --------------------------------------------------
        # 5. XLSX Documents
        # --------------------------------------------------
        elif extension == ".xlsx":
            workbook = load_workbook(file_path, read_only=True, data_only=True)
            sheet_pages = []

            for s_idx, worksheet in enumerate(workbook.worksheets, start=1):
                raw_rows = []
                for row in worksheet.iter_rows(values_only=True):
                    if any(v is not None for v in row):
                        raw_rows.append(list(row))

                if raw_rows:
                    from services.table_extractor import TableAwareExtractor
                    chunks = TableAwareExtractor.serialize_spreadsheet_sheet(
                        sheet_name=worksheet.title,
                        sheet_data=raw_rows,
                        filename=doc_name,
                    )
                    if chunks:
                        sheet_text = "\n\n".join(c["text"] for c in chunks)
                    else:
                        sheet_lines = [f"Sheet: {worksheet.title}"]
                        for r in raw_rows:
                            vals = [str(v) for v in r if v is not None]
                            if vals:
                                sheet_lines.append(" | ".join(vals))
                        sheet_text = "\n".join(sheet_lines)
                else:
                    sheet_text = f"Sheet: {worksheet.title}\n(Empty sheet)"

                sheet_pages.append({
                    "page_number": s_idx,
                    "text": sheet_text,
                    "char_count": len(sheet_text),
                    "extraction_method": "table_extractor",
                })

            workbook.close()
            pages = sheet_pages
            full_text = "\n\n".join(p["text"] for p in pages)
            page_count = len(pages)

        # --------------------------------------------------
        # 6. Unsupported
        # --------------------------------------------------
        else:
            full_text = ""
            pages = []
            page_count = 0

        char_count = len(full_text)
        print(f"📄 Extracted text length: {char_count} chars across {page_count} pages (Method: {extraction_method})")
        if char_count > 0:
            print("✅ Text extraction successful")
        else:
            print("❌ No text extracted")

        return {
            "text": full_text,
            "pages": pages,
            "extraction_method": extraction_method,
            "ocr_used": ocr_used,
            "page_count": page_count,
            "ocr_page_count": ocr_page_count,
            "char_count": char_count,
        }

    except Exception as e:
        print("❌ Text extraction error:", str(e))
        return {
            "text": "",
            "pages": [],
            "extraction_method": "error",
            "ocr_used": False,
            "page_count": 0,
            "ocr_page_count": 0,
            "char_count": 0,
            "error": str(e),
        }


def extract_text(file_path: str) -> str:
    """
    Backwards-compatible wrapper returning full document string.
    """
    content = extract_document_content(file_path)
    return content.get("text", "")
