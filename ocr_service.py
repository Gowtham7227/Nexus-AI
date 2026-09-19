import os
import re
import shutil
from typing import List, Dict, Any, Optional, Tuple

import pytesseract
from PIL import Image

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None


# ============================================================
# OCR CONFIGURATION
# ============================================================

OCR_ENABLED = os.getenv("OCR_ENABLED", "true").lower() in ("true", "1", "yes")
OCR_MIN_TEXT_CHARS_PER_PAGE = int(os.getenv("OCR_MIN_TEXT_CHARS_PER_PAGE", "50"))
OCR_MIN_TEXT_PAGE_RATIO = float(os.getenv("OCR_MIN_TEXT_PAGE_RATIO", "0.30"))
OCR_DPI = int(os.getenv("OCR_DPI", "200"))
OCR_LANGUAGE = os.getenv("OCR_LANGUAGE", "eng")


# ============================================================
# TESSERACT AUTO-DISCOVERY
# ============================================================

def find_tesseract_binary() -> Optional[str]:
    """
    Search for Tesseract executable across environment variables, PATH,
    and standard Windows/Linux installation locations.
    """
    # 1. Custom ENV path
    env_cmd = os.getenv("TESSERACT_CMD")
    if env_cmd and os.path.isfile(env_cmd):
        return env_cmd

    # 2. Check system PATH
    which_path = shutil.which("tesseract")
    if which_path and os.path.isfile(which_path):
        return which_path

    # 3. Standard Windows locations
    user_home = os.path.expanduser("~")
    local_app_data = os.environ.get("LOCALAPPDATA", os.path.join(user_home, "AppData", "Local"))
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")

    candidate_paths = [
        os.path.join(program_files, "Tesseract-OCR", "tesseract.exe"),
        os.path.join(program_files_x86, "Tesseract-OCR", "tesseract.exe"),
        os.path.join(local_app_data, "Programs", "Tesseract-OCR", "tesseract.exe"),
        os.path.join(local_app_data, "Tesseract-OCR", "tesseract.exe"),
        r"C:\tools\tesseract\tesseract.exe",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools", "tesseract", "tesseract.exe"),
    ]

    for p in candidate_paths:
        if os.path.isfile(p):
            return p

    return None


_configured_tesseract: Optional[str] = None


def setup_tesseract() -> bool:
    """Configure pytesseract with discovered executable path."""
    global _configured_tesseract
    tess_path = find_tesseract_binary()
    if tess_path:
        pytesseract.pytesseract.tesseract_cmd = tess_path
        _configured_tesseract = tess_path
        return True
    return False


# Run auto-discovery once at module import
setup_tesseract()


def is_ocr_available() -> bool:
    """Return True if local OCR engine is installed and operational."""
    if not OCR_ENABLED:
        return False
    if fitz is None:
        return False
    tess_path = find_tesseract_binary()
    if not tess_path:
        return False
    return True


# ============================================================
# SMART OCR DETECTION
# ============================================================

def detect_pdf_text_quality(file_path: str) -> Dict[str, Any]:
    """
    Extract native text page-by-page from a PDF and compute text quality metrics.
    Determines whether native extraction is sufficient or if OCR is required.
    """
    if not os.path.isfile(file_path):
        return {
            "total_pages": 0,
            "total_chars": 0,
            "chars_per_page": 0.0,
            "meaningful_pages": 0,
            "meaningful_page_ratio": 0.0,
            "needs_ocr": False,
            "native_pages": [],
        }

    native_pages: List[Dict[str, Any]] = []
    total_chars = 0
    meaningful_pages = 0

    try:
        # Use PyMuPDF for fast, robust page text extraction
        if fitz is not None:
            doc = fitz.open(file_path)
            total_pages = len(doc)
            for page_idx in range(total_pages):
                page = doc[page_idx]
                p_text = page.get_text("text").strip()
                char_count = len(p_text)
                total_chars += char_count
                is_meaningful = char_count >= OCR_MIN_TEXT_CHARS_PER_PAGE
                if is_meaningful:
                    meaningful_pages += 1
                native_pages.append({
                    "page_number": page_idx + 1,
                    "text": p_text,
                    "char_count": char_count,
                    "extraction_method": "native",
                })
            doc.close()
        else:
            # Fallback to pypdf
            from pypdf import PdfReader
            reader = PdfReader(file_path)
            total_pages = len(reader.pages)
            for page_idx, page in enumerate(reader.pages):
                p_text = (page.extract_text() or "").strip()
                char_count = len(p_text)
                total_chars += char_count
                is_meaningful = char_count >= OCR_MIN_TEXT_CHARS_PER_PAGE
                if is_meaningful:
                    meaningful_pages += 1
                native_pages.append({
                    "page_number": page_idx + 1,
                    "text": p_text,
                    "char_count": char_count,
                    "extraction_method": "native",
                })

    except Exception as e:
        print(f"⚠️ [OCR DETECT] Error reading PDF pages: {e}")
        return {
            "total_pages": 0,
            "total_chars": 0,
            "chars_per_page": 0.0,
            "meaningful_pages": 0,
            "meaningful_page_ratio": 0.0,
            "needs_ocr": OCR_ENABLED,
            "native_pages": [],
        }

    chars_per_page = (total_chars / total_pages) if total_pages > 0 else 0.0
    meaningful_page_ratio = (meaningful_pages / total_pages) if total_pages > 0 else 0.0

    # Decision criteria: if either average chars/page or meaningful page ratio is below threshold, trigger OCR
    needs_ocr = (
        OCR_ENABLED
        and total_pages > 0
        and (
            chars_per_page < OCR_MIN_TEXT_CHARS_PER_PAGE
            or meaningful_page_ratio < OCR_MIN_TEXT_PAGE_RATIO
        )
    )

    return {
        "total_pages": total_pages,
        "total_chars": total_chars,
        "chars_per_page": round(chars_per_page, 2),
        "meaningful_pages": meaningful_pages,
        "meaningful_page_ratio": round(meaningful_page_ratio, 3),
        "needs_ocr": needs_ocr,
        "native_pages": native_pages,
    }


# ============================================================
# OCR TEXT NORMALIZATION
# ============================================================

def normalize_ocr_text(text: str) -> str:
    """
    Clean up whitespace and common OCR artifacts safely without
    altering substantive content.
    """
    if not text:
        return ""

    # 1. Normalize line endings
    t = text.replace("\r\n", "\n").replace("\r", "\n")

    # 2. Fix hyphenated word breaks at end of lines (e.g., "transfor-\nmation" -> "transformation")
    t = re.sub(r"(\b[a-zA-Z]{2,})-\n([a-zA-Z]{2,}\b)", r"\1\2", t)

    # 3. Replace multiple non-newline whitespace characters with a single space
    t = re.sub(r"[^\S\n]+", " ", t)

    # 4. Collapse 3+ consecutive newlines to 2 newlines (preserve paragraphs)
    t = re.sub(r"\n{3,}", "\n\n", t)

    return t.strip()


# ============================================================
# LOCAL PAGE-BY-PAGE OCR PROCESSOR
# ============================================================

def perform_pdf_ocr(file_path: str, dpi: Optional[int] = None, lang: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Execute 100% local page-by-page OCR on a PDF document using PyMuPDF and Tesseract.
    Returns list of page dictionaries with page numbers, OCR text, and metadata.
    """
    if fitz is None:
        raise RuntimeError("PyMuPDF (fitz) is not installed for local PDF page rendering.")

    if not setup_tesseract():
        raise RuntimeError(
            "Local OCR is unavailable. Please install Tesseract OCR and ensure it is accessible on your system."
        )

    use_dpi = dpi or OCR_DPI
    use_lang = lang or OCR_LANGUAGE

    doc_name = os.path.basename(file_path)
    print("=" * 70)
    print(f"🔍 [OCR START] Document: {doc_name} | DPI: {use_dpi} | Lang: {use_lang}")
    print("=" * 70)

    doc = fitz.open(file_path)
    total_pages = len(doc)
    ocr_pages: List[Dict[str, Any]] = []

    try:
        for page_idx in range(total_pages):
            page_num = page_idx + 1
            page = doc[page_idx]
            print(f"  [OCR] Processing page {page_num}/{total_pages}...")

            # Render page to high-resolution pixmap
            pix = page.get_pixmap(dpi=use_dpi)
            
            # Convert pixmap to PIL Image
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            # Perform local Tesseract OCR
            raw_text = pytesseract.image_to_string(img, lang=use_lang)

            # Normalize OCR text
            clean_text = normalize_ocr_text(raw_text)

            # Release memory explicitly
            del pix
            del img

            ocr_pages.append({
                "page_number": page_num,
                "text": clean_text,
                "char_count": len(clean_text),
                "extraction_method": "ocr",
            })

        total_extracted = sum(p["char_count"] for p in ocr_pages)
        print(f"✅ [OCR COMPLETE] Document: {doc_name} | Pages: {total_pages} | Total Chars: {total_extracted}")
        print("=" * 70)
        return ocr_pages

    finally:
        doc.close()
