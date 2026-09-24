import os
import zipfile
import hashlib
import time
import sqlite3
import json
from fastapi import HTTPException
from auth import AUTH_DB, invalidate_document_cache
from vector_store import create_vector_store, delete_document_from_vector_store
from privacy_scanner import PrivacyScanner

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "100"))
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024

ALLOWED_UPLOAD_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".pptx",
    ".txt",
    ".xlsx",
}


def validate_uploaded_content(file_path: str, filename: str) -> None:
    """Validate that uploaded file matches the declared supported document type."""
    extension = os.path.splitext(filename)[1].lower()

    if extension == ".txt":
        return

    if extension == ".pdf":
        with open(file_path, "rb") as f:
            header = f.read(1024)
        if not header.startswith(b"%PDF-"):
            try:
                os.remove(file_path)
            except Exception:
                pass
            raise HTTPException(
                status_code=415,
                detail="Invalid PDF file content.",
            )
        return

    if extension in {".docx", ".pptx", ".xlsx"}:
        if not zipfile.is_zipfile(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
            raise HTTPException(
                status_code=415,
                detail=f"Invalid {extension[1:].upper()} file content.",
            )
        return

    try:
        os.remove(file_path)
    except Exception:
        pass
    raise HTTPException(
        status_code=415,
        detail="Unsupported file type.",
    )


def validate_upload_filename(filename: str) -> str:
    if not filename:
        raise HTTPException(status_code=400, detail="A filename is required.")

    filename = filename.strip()
    normalized = filename.replace("\\", "/")
    safe_filename = os.path.basename(normalized)

    if (
        not safe_filename
        or safe_filename in {".", ".."}
        or safe_filename != normalized
        or "\x00" in safe_filename
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid filename. Please upload a file with a simple filename only.",
        )

    extension = os.path.splitext(safe_filename)[1].lower()
    if extension not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Allowed file types: PDF, DOCX, PPTX, TXT, XLSX.",
        )

    return safe_filename


def get_safe_document_path(filename: str) -> str:
    """Return a document path guaranteed to remain inside UPLOAD_FOLDER or fallback uploads."""
    safe_filename = validate_upload_filename(filename)
    upload_root = os.path.abspath(UPLOAD_FOLDER)
    file_path = os.path.abspath(os.path.join(upload_root, safe_filename))

    if os.path.isfile(file_path):
        return file_path

    # Check sibling directory uploads fallback
    for alt_parent in ["backend", "NexusAI-GitHub"]:
        alt_root = os.path.abspath(os.path.join(BASE_DIR, "..", alt_parent, "uploads"))
        alt_path = os.path.abspath(os.path.join(alt_root, safe_filename))
        if os.path.isfile(alt_path):
            return alt_path

    if os.path.commonpath([upload_root, file_path]) != upload_root:
        raise HTTPException(status_code=400, detail="Invalid document path.")

    return file_path


def process_document_indexing_background(safe_filename: str, user_id: int):
    """
    Asynchronous background worker for text extraction, OCR, chunking, and Chroma indexing.
    Updates processing_status safely without blocking upload response.
    """
    file_path = get_safe_document_path(safe_filename)
    t_start = time.time()
    print("=" * 70)
    print(f"🔄 [ASYNC INDEXING START] File: {safe_filename} | User ID: {user_id}")
    print("=" * 70)

    processing_status = "ready"
    processing_error = None
    vector_status = "indexed"
    extraction_method = "native"
    ocr_used = 0
    ocr_page_count = 0
    page_count = 0
    extracted_char_count = 0
    privacy_risk = "LOW"
    privacy_details = None

    try:
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"Uploaded file '{safe_filename}' not found on disk.")

        # Update status to extracting in DB
        try:
            conn = sqlite3.connect(AUTH_DB)
            conn.execute(
                "UPDATE documents SET processing_status = 'extracting' WHERE user_id = ? AND filename = ?",
                (user_id, safe_filename),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

        t_ext = time.time()
        from utils import extract_document_content
        extracted_data = extract_document_content(file_path)
        ext_time = time.time() - t_ext

        extracted_text = extracted_data.get("text", "")
        pages = extracted_data.get("pages", [])
        extraction_method = extracted_data.get("extraction_method", "native")
        ocr_used = 1 if extracted_data.get("ocr_used") else 0
        page_count = extracted_data.get("page_count", len(pages))
        ocr_page_count = extracted_data.get("ocr_page_count", 0)
        extracted_char_count = extracted_data.get("char_count", len(extracted_text))

        print(f"📄 [ASYNC EXTRACTION] File: {safe_filename} | Chars: {extracted_char_count} | Pages: {page_count} | Method: {extraction_method} | Time: {ext_time:.3f}s")

        if extracted_text and extracted_text.strip():
            # Run privacy scanner on extracted text
            try:
                scanner = PrivacyScanner()
                risk_level, findings = scanner.scan_document(extracted_text)
                privacy_risk = risk_level
                privacy_details = json.dumps([f.to_dict() for f in findings])
                print(f"🛡️ [PRIVACY SCAN] File: {safe_filename} | Risk: {privacy_risk} | Findings: {len(findings)}")
            except Exception as scan_err:
                print(f"⚠️ [PRIVACY SCAN ERROR] File: {safe_filename} | Error: {str(scan_err)}")

            # Update status to indexing
            try:
                conn = sqlite3.connect(AUTH_DB)
                conn.execute(
                    "UPDATE documents SET processing_status = 'indexing' WHERE user_id = ? AND filename = ?",
                    (user_id, safe_filename),
                )
                conn.commit()
                conn.close()
            except Exception:
                pass

            t_vec = time.time()
            create_vector_store(extracted_data, safe_filename, user_id=user_id)
            vec_time = time.time() - t_vec
            print(f"⚡ [ASYNC CHROMA INDEXED] File: {safe_filename} | Time: {vec_time:.3f}s")
            processing_status = "ready"
            processing_error = None
            vector_status = "indexed"
        else:
            processing_status = "ready"
            processing_error = "No extractable text found in document."
            vector_status = "none"
            print(f"⚠️ [ASYNC INDEXING] File: {safe_filename} contains no extractable text.")

    except Exception as e:
        elapsed = time.time() - t_start
        print(f"❌ [ASYNC INDEXING FAILED] File: {safe_filename} | Error: {type(e).__name__} - {str(e)} in {elapsed:.2f}s")
        processing_status = "failed"
        processing_error = "Document indexing failed. Please try again."
        vector_status = "failed"
        try:
            delete_document_from_vector_store(safe_filename)
        except Exception:
            pass

    # Persist final status to database
    try:
        conn = sqlite3.connect(AUTH_DB)
        try:
            conn.execute(
                """
                UPDATE documents
                SET processing_status = ?,
                    processing_error = ?,
                    vector_status = ?,
                    privacy_risk = COALESCE(?, privacy_risk),
                    privacy_details = COALESCE(?, privacy_details),
                    extraction_method = ?,
                    ocr_used = ?,
                    ocr_page_count = ?,
                    page_count = ?,
                    extracted_char_count = ?
                WHERE user_id = ? AND filename = ?
                """,
                (
                    processing_status,
                    processing_error,
                    vector_status,
                    privacy_risk,
                    privacy_details,
                    extraction_method,
                    ocr_used,
                    ocr_page_count,
                    page_count,
                    extracted_char_count,
                    user_id,
                    safe_filename,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        total_time = time.time() - t_start
        print(f"✅ [ASYNC INDEXING COMPLETE] File: {safe_filename} | Status: {processing_status} | Method: {extraction_method} | Total Time: {total_time:.3f}s")
        print("=" * 70)
    except Exception as db_err:
        print(f"❌ [ASYNC DB UPDATE ERROR] File: {safe_filename} | Error: {str(db_err)}")


def document_belongs_to_user(
    filename: str,
    user_id: int,
) -> bool:
    conn = sqlite3.connect(AUTH_DB)
    try:
        row = conn.execute(
            """
            SELECT 1
            FROM documents
            WHERE user_id = ? AND filename = ?
            LIMIT 1
            """,
            (user_id, filename),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def get_owned_filenames(
    filenames: list[str],
    user_id: int,
) -> list[str]:
    if not filenames:
        return []

    conn = sqlite3.connect(AUTH_DB)
    try:
        placeholders = ",".join("?" for _ in filenames)
        rows = conn.execute(
            f"""
            SELECT filename
            FROM documents
            WHERE user_id = ?
              AND filename IN ({placeholders})
            """,
            [user_id, *filenames],
        ).fetchall()
    finally:
        conn.close()

    owned = {row[0] for row in rows}
    return [filename for filename in filenames if filename in owned]


def validate_user_documents(
    filenames: list[str],
    user_id: int,
) -> list[str]:
    owned_filenames = get_owned_filenames(
        filenames,
        user_id,
    )

    if len(owned_filenames) != len(filenames):
        raise HTTPException(
            status_code=403,
            detail="You do not have access to one or more selected documents.",
        )

    return owned_filenames
