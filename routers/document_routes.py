import os
import time
import sqlite3
import hashlib
from fastapi import (
    APIRouter,
    UploadFile,
    File,
    Query,
    BackgroundTasks,
    Depends,
    HTTPException,
)
from fastapi.responses import FileResponse
from dependencies.auth_deps import get_current_user
from schemas.chat_schemas import ChatRequest
from auth import (
    AUTH_DB,
    save_message,
    touch_conversation,
    invalidate_document_cache,
)
from services.document_service import (
    validate_upload_filename,
    validate_uploaded_content,
    get_safe_document_path,
    process_document_indexing_background,
    document_belongs_to_user,
    validate_user_documents,
    MAX_UPLOAD_SIZE_BYTES,
    MAX_UPLOAD_SIZE_MB,
)
from services.chat_service import (
    get_selected_filenames,
    resolve_or_create_conversation,
)
from utils import extract_text
from document_summary import explain_document
from vector_store import delete_document_from_vector_store

router = APIRouter(tags=["documents"])


@router.post("/upload")
def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
):
    try:
        t_upload_start = time.time()

        # Validate Filename & Path
        original_filename = file.filename or ""
        safe_filename = validate_upload_filename(original_filename)
        file_path = get_safe_document_path(safe_filename)

        # Collision prevention across different users
        conn = sqlite3.connect(AUTH_DB)
        try:
            filename_in_use = conn.execute(
                """
                SELECT 1
                FROM documents
                WHERE filename = ?
                LIMIT 1
                """,
                (safe_filename,),
            ).fetchone()
        finally:
            conn.close()

        if filename_in_use is not None and not document_belongs_to_user(
            safe_filename,
            current_user["user_id"],
        ):
            raise HTTPException(
                status_code=409,
                detail="A document with this filename already exists. Please rename the file and upload again.",
            )

        # Stream file to disk with 100 MB size enforcement & SHA256 content hashing
        total_bytes = 0
        chunk_size = 1024 * 1024  # 1 MB chunk buffer
        hasher = hashlib.sha256()
        with open(file_path, "wb") as buffer:
            while True:
                chunk = file.file.read(chunk_size)
                if not chunk:
                    break
                hasher.update(chunk)
                total_bytes += len(chunk)
                if total_bytes > MAX_UPLOAD_SIZE_BYTES:
                    buffer.close()
                    try:
                        os.remove(file_path)
                    except Exception:
                        pass
                    raise HTTPException(
                        status_code=413,
                        detail=f"File is too large. Maximum allowed size is {MAX_UPLOAD_SIZE_MB} MB.",
                    )
                buffer.write(chunk)

        content_hash = hasher.hexdigest()

        # Security Content Validation
        validate_uploaded_content(file_path, safe_filename)

        file_size_bytes = os.path.getsize(file_path)
        file_extension = os.path.splitext(safe_filename)[1].lower()

        # Initialize Document Metadata with status 'processing'
        conn = sqlite3.connect(AUTH_DB)
        try:
            existing = conn.execute(
                """
                SELECT id
                FROM documents
                WHERE user_id = ? AND filename = ?
                LIMIT 1
                """,
                (current_user["user_id"], safe_filename),
            ).fetchone()

            if existing is None:
                conn.execute(
                    """
                    INSERT INTO documents (
                        user_id,
                        filename,
                        original_filename,
                        file_size,
                        file_type,
                        content_hash,
                        created_at,
                        processing_status,
                        processing_error,
                        vector_status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 'processing', NULL, 'indexing')
                    """,
                    (
                        current_user["user_id"],
                        safe_filename,
                        original_filename,
                        file_size_bytes,
                        file_extension,
                        content_hash,
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE documents
                    SET original_filename = ?,
                        file_size = ?,
                        file_type = ?,
                        content_hash = ?,
                        created_at = CURRENT_TIMESTAMP,
                        processing_status = 'processing',
                        processing_error = NULL,
                        vector_status = 'indexing'
                    WHERE id = ?
                    """,
                    (
                        original_filename,
                        file_size_bytes,
                        file_extension,
                        content_hash,
                        existing[0],
                    ),
                )
            conn.commit()
        finally:
            conn.close()

        # Dispatch Asynchronous Background Indexing
        background_tasks.add_task(
            process_document_indexing_background,
            safe_filename,
            current_user["user_id"],
        )

        upload_response_time = time.time() - t_upload_start
        print(f"🚀 [UPLOAD FAST-PATH RESPONSE] File: {safe_filename} ({file_size_bytes/(1024*1024):.2f} MB) in {upload_response_time*1000:.2f} ms")

        return {
            "message": "File uploaded successfully. Document indexing is in progress.",
            "filename": safe_filename,
            "status": "processing",
            "processing_status": "processing",
            "size": file_size_bytes,
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print("❌ Upload Error (Internal):", str(e))
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail="Document upload failed. Please try again.",
        )


@router.post("/document-summary")
def document_summary(
    request: ChatRequest,
    current_user=Depends(get_current_user),
):
    try:
        filenames = get_selected_filenames(request)

        if not filenames:
            return {
                "question": request.question,
                "mode": "cloud",
                "answer": "📄 Please select a document."
            }

        filenames = validate_user_documents(
            filenames,
            current_user["user_id"],
        )

        filename = filenames[0]
        print("=" * 70)
        print("📄 DOCUMENT SUMMARY REQUEST")
        print("Filename:", filename)
        print("=" * 70)

        file_path = get_safe_document_path(filename)

        if not os.path.isfile(file_path):
            return {
                "filename": filename,
                "mode": "cloud",
                "answer": "📄 Document not found."
            }

        print("📖 Extracting complete document text...")
        extracted_text = extract_text(file_path)

        if not extracted_text or not extracted_text.strip():
            return {
                "filename": filename,
                "mode": "cloud",
                "answer": "I couldn't find readable content in the uploaded document."
            }

        print("📏 Extracted text length:", len(extracted_text))

        answer = explain_document(extracted_text, filename)

        # Persist conversation & messages in SQLite
        conv_id = request.conversation_id
        user_prompt = request.question.strip() if request.question else f"Explain document: {filename}"

        conv_id, conv_title = resolve_or_create_conversation(
            current_user["user_id"],
            conv_id,
            user_prompt,
            [filename],
        )
        save_message(conv_id, "assistant", answer)
        touch_conversation(conv_id, current_user["user_id"])

        print("=" * 70)
        print("🤖 DOCUMENT EXPLANATION")
        print(answer)
        print(f"Conversation ID: {conv_id} | Title: {conv_title}")
        print("=" * 70)

        return {
            "question": user_prompt,
            "filename": filename,
            "filenames": [filename],
            "mode": "cloud",
            "answer": answer,
            "conversation_id": conv_id,
            "conversation_title": conv_title,
        }

    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        print("❌ Document Summary Error:", str(e))
        return {"error": "Document summary failed."}


@router.get("/documents")
def get_documents(
    current_user=Depends(get_current_user),
):
    try:
        conn = sqlite3.connect(AUTH_DB)
        rows = conn.execute(
            """
            SELECT filename, file_size, processing_status, processing_error, vector_status, created_at, privacy_risk, privacy_details,
                   COALESCE(extraction_method, 'native'), COALESCE(ocr_used, 0), COALESCE(ocr_page_count, 0), COALESCE(page_count, 1)
            FROM documents
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (current_user["user_id"],),
        ).fetchall()
        conn.close()

        files = []

        for filename, file_size, proc_status, proc_error, vec_status, created_at, priv_risk, priv_details, ext_method, ocr_u, ocr_p, p_count in rows:
            file_path = get_safe_document_path(filename)
            actual_size = file_size if (file_size and file_size > 0) else (os.path.getsize(file_path) if os.path.isfile(file_path) else 0)

            status_val = proc_status or "ready"
            if status_val == "completed":
                status_val = "ready"

            files.append({
                "filename": filename,
                "size": actual_size,
                "status": status_val,
                "processing_status": status_val,
                "error": proc_error,
                "processing_error": proc_error,
                "vector_status": vec_status or "indexed",
                "created_at": created_at,
                "privacy_risk": priv_risk or "LOW",
                "privacy_details": priv_details,
                "extraction_method": ext_method,
                "ocr_used": bool(ocr_u),
                "ocr_page_count": ocr_p,
                "page_count": p_count,
            })

        return {
            "count": len(files),
            "documents": files,
        }

    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        print("❌ Documents Error:", str(e))
        return {
            "count": 0,
            "documents": [],
            "error": "Unable to retrieve documents.",
        }


@router.delete("/documents/{filename}")
def delete_document(
    filename: str,
    current_user=Depends(get_current_user),
):
    try:
        if not document_belongs_to_user(
            filename,
            current_user["user_id"],
        ):
            raise HTTPException(
                status_code=403,
                detail="You do not have access to this document.",
            )

        file_path = get_safe_document_path(filename)

        if not os.path.isfile(file_path):
            return {
                "message": "Document not found",
                "filename": filename,
            }

        os.remove(file_path)

        # Delete from Chroma vector store and invalidate BM25 index
        delete_document_from_vector_store(filename)

        # Invalidate response cache for this document
        invalidate_document_cache(current_user["user_id"], filename)

        conn = sqlite3.connect(AUTH_DB)
        conn.execute(
            """
            DELETE FROM documents
            WHERE user_id = ? AND filename = ?
            """,
            (
                current_user["user_id"],
                filename,
            ),
        )
        conn.commit()
        conn.close()

        print("🗑️ Document deleted:", filename)

        return {
            "message": "Document deleted successfully",
            "filename": filename,
        }

    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        return {
            "message": "Failed to delete document",
            "filename": filename,
            "error": "Failed to delete document.",
        }


@router.get("/documents/{filename}/file")
def get_document_file(
    filename: str,
    download: bool = Query(False),
    current_user=Depends(get_current_user),
):
    filename = filename.strip()

    if not document_belongs_to_user(
        filename,
        current_user["user_id"],
    ):
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this document.",
        )

    file_path = get_safe_document_path(filename)

    if not os.path.isfile(file_path):
        return {
            "message": "Document not found",
            "filename": filename,
        }

    extension = os.path.splitext(filename)[1].lower()

    media_types = {
        ".pdf": "application/pdf",
        ".txt": "text/plain",
        ".doc": "application/msword",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".ppt": "application/vnd.ms-powerpoint",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".xls": "application/vnd.ms-excel",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }

    media_type = media_types.get(
        extension,
        "application/octet-stream",
    )

    if download:
        return FileResponse(
            path=file_path,
            media_type=media_type,
            filename=filename,
        )

    return FileResponse(
        path=file_path,
        media_type=media_type,
        headers={
            "Content-Disposition": "inline",
        },
    )
