import os
import sys
import json
import hashlib

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

from retriever import retrieve_context
from advanced_rag import NexusAdvancedRAG
from privacy_scanner import PrivacyScanner, OutputPrivacyGuard
from rag_evaluation import (
    SourceCitationManager,
    DeterministicGroundingEvaluator,
    RAGEvaluator,
)
from model_provider import get_model_provider, GeminiModelProvider, LocalQwenModelProvider
from vector_store import delete_document_from_vector_store
from chatbot import (
    ask_gemini,
    ask_gemini_general,
    ask_gemini_stream,
    ask_gemini_general_stream,
)
from document_summary import explain_document
from local_llm import (
    ask_local,
    stream_local,
    warmup_local_model,
)

from fastapi import (
    FastAPI,
    UploadFile,
    File,
    Query,
    BackgroundTasks,
)

from fastapi.responses import (
    FileResponse,
    StreamingResponse,
)

from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from auth import (
    create_user,
    authenticate_user,
    create_access_token,
    get_user_by_email,
    update_password,
    decode_access_token,
    AUTH_DB,
    create_conversation,
    get_user_conversations,
    get_conversation,
    update_conversation_title,
    delete_conversation,
    save_message,
    touch_conversation,
    set_conversation_documents,
    generate_conversation_title,
    record_ai_metric,
    get_user_analytics_summary,
    get_user_latency_series,
    get_user_rag_distribution,
    get_user_model_stats,
    save_message_feedback,
    get_conversation_feedback,
    compute_document_fingerprint,
    compute_cache_key,
    get_cached_response,
    set_cached_response,
    invalidate_document_cache,
    clear_user_response_cache,
)

import shutil
import os
import sqlite3
import time
import threading
import io
import zipfile
import uuid

from utils import extract_text
from vector_store import create_vector_store


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="NexusAI Backend",
    description="AI Powered Document Intelligence Assistant",
    version="1.1.0",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,

    allow_origins=[
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],
)


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")

MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "100"))
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True,
)

print("=" * 70)
print("🚀 NexusAI Backend Starting...")
print("📂 Base Directory :", BASE_DIR)
print("📂 Upload Folder  :", UPLOAD_FOLDER)
print(f"📦 Max Upload Size: {MAX_UPLOAD_SIZE_MB} MB ({MAX_UPLOAD_SIZE_BYTES} bytes)")
print("=" * 70)


# ============================================================
# JWT AUTHENTICATION
# ============================================================

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    token = credentials.credentials

    user = decode_access_token(token)

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token.",
        )

    return user


# ============================================================
# HOME
# ============================================================

@app.get("/")
def home():
    return {
        "message": "Welcome to NexusAI Backend 🚀",
        "status": "running",
    }


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "NexusAI Backend",
        "max_upload_size_mb": MAX_UPLOAD_SIZE_MB,
        "active_gemini_model": os.getenv("GEMINI_MODEL", "gemini-3.6-flash"),
        "base_dir": BASE_DIR,
    }


@app.get("/api/test-gemini")
def api_test_gemini():
    from gemini_service import test_direct_gemini, CURRENT_MODEL, CANDIDATE_MODELS, SDK_AVAILABLE
    success, result = test_direct_gemini()
    return {
        "gemini_configured": bool(os.getenv("GEMINI_API_KEY")),
        "sdk": "google-genai",
        "sdk_available": SDK_AVAILABLE,
        "active_model": CURRENT_MODEL,
        "candidate_models": CANDIDATE_MODELS,
        "direct_gemini_test": "PASS" if success else "FAIL",
        "response_sample": result,
    }


@app.get("/api/run-comprehensive-audit")
def api_run_comprehensive_audit():
    import comprehensive_audit
    results = comprehensive_audit.run_all_audits()
    passed = sum(1 for k, v in results.items() if v["status"] == "PASS")
    return {
        "total_checks": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "all_passed": passed == len(results),
        "details": results,
    }



@app.get("/api/package-project")
def package_project():
    """Package canonical NexusAI source code cleanly into NexusAI-FINAL-WORKING.zip"""
    target_zip = os.path.abspath(os.path.join(BASE_DIR, "..", "NexusAI-FINAL-WORKING.zip"))
    
    excluded_dirs = {
        "node_modules", "venv", ".venv", "__pycache__", ".git", "dist",
        "chroma_db", "uploads", "logs", ".idea", ".vscode"
    }
    excluded_extensions = {".pyc", ".db", ".sqlite", ".sqlite3", ".log", ".tmp"}
    excluded_filenames = {".env", "text_diagnostic.txt", "upload_debug.txt", "test_file.txt"}

    packaged_files = []

    with zipfile.ZipFile(target_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(BASE_DIR):
            # Prune excluded directories
            dirs[:] = [d for d in dirs if d not in excluded_dirs and not d.startswith(".")]

            for file in files:
                if file in excluded_filenames:
                    continue
                ext = os.path.splitext(file)[1].lower()
                if ext in excluded_extensions:
                    continue
                
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, BASE_DIR)
                
                # Double check no secret in file name
                if ".env" in rel_path and not rel_path.endswith(".env.example"):
                    continue

                zf.write(full_path, os.path.join("NexusAI", rel_path))
                packaged_files.append(rel_path)

    zip_size_bytes = os.path.getsize(target_zip)
    return {
        "status": "success",
        "zip_path": target_zip,
        "zip_size_mb": round(zip_size_bytes / (1024 * 1024), 2),
        "total_files": len(packaged_files),
        "sample_files": packaged_files[:20],
    }


# ============================================================
# AUTHENTICATION
# ============================================================

class RegisterRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


@app.post("/register")
def register(request: RegisterRequest):
    email = request.email.strip().lower()
    password = request.password

    if not email:
        raise HTTPException(
            status_code=400,
            detail="Email is required.",
        )

    if not password:
        raise HTTPException(
            status_code=400,
            detail="Password is required.",
        )

    if len(password) < 6:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 6 characters.",
        )

    try:
        user = create_user(
            email,
            password,
        )

        token = create_access_token(
            user["id"],
            user["email"],
        )

        return {
            "message": "Registration successful",
            "token": token,
            "user": {
                "id": user["id"],
                "email": user["email"],
            },
        }

    except Exception as e:

        if isinstance(e, HTTPException):

            raise
        if "UNIQUE constraint failed" in str(e):
            raise HTTPException(
                status_code=409,
                detail="An account with this email already exists.",
            )

        print("âŒ Registration Error:", str(e))

        raise HTTPException(
            status_code=500,
            detail="Registration failed.",
        )


LOGIN_MAX_FAILED_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 10 * 60

_login_attempts = {}
_login_attempts_lock = threading.Lock()


def _login_key(email: str) -> str:
    return email.strip().lower()


def reset_login_attempts(email: str) -> None:
    key = _login_key(email)
    with _login_attempts_lock:
        _login_attempts.pop(key, None)


def check_login_rate_limit(email: str) -> None:
    key = _login_key(email)
    now = time.time()

    with _login_attempts_lock:
        record = _login_attempts.get(key)

        if record is None:
            return

        failed_attempts, first_failed_at = record

        if now - first_failed_at >= LOGIN_LOCKOUT_SECONDS:
            _login_attempts.pop(key, None)
            return

        if failed_attempts >= LOGIN_MAX_FAILED_ATTEMPTS:
            raise HTTPException(
                status_code=429,
                detail="Too many failed login attempts. Please try again later.",
            )


def record_failed_login_attempt(email: str) -> None:
    key = _login_key(email)
    now = time.time()

    with _login_attempts_lock:
        record = _login_attempts.get(key)

        if record is None or now - record[1] >= LOGIN_LOCKOUT_SECONDS:
            _login_attempts[key] = (1, now)
        else:
            _login_attempts[key] = (record[0] + 1, record[1])


@app.post("/login")
def login(request: LoginRequest):
    email = request.email.strip().lower()
    password = request.password

    if not email or not password:
        raise HTTPException(
            status_code=400,
            detail="Email and password are required.",
        )

    check_login_rate_limit(email)

    user = authenticate_user(
        email,
        password,
    )

    if user is None:
        record_failed_login_attempt(email)
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password.",
        )

    reset_login_attempts(email)

    token = create_access_token(
        user["id"],
        user["email"],
    )

    return {
        "message": "Login successful",
        "token": token,
        "user": {
            "id": user["id"],
            "email": user["email"],
        },
    }


# ============================================================
# PASSWORD RESET / OTP
# ============================================================

from otp import (
    generate_or_resend_otp,
    validate_otp,
    consume_and_verify_otp,
    clear_otp,
    get_resend_cooldown_remaining,
)
from email_service import send_otp_email


class ForgotPasswordRequest(BaseModel):
    email: str


class ResendOTPRequest(BaseModel):
    email: str


class VerifyOTPRequest(BaseModel):
    email: str
    otp: str


class ResetPasswordRequest(BaseModel):
    email: str
    otp: str
    new_password: str


@app.post("/forgot-password")
def forgot_password(request: ForgotPasswordRequest):
    email = request.email.strip().lower()

    if not email:
        raise HTTPException(
            status_code=400,
            detail="Email is required.",
        )

    user = get_user_by_email(email)

    # If user exists, generate OTP and dispatch email
    if user is not None:
        try:
            otp = generate_or_resend_otp(email, is_resend=False)
        except HTTPException:
            raise
        except Exception as e:
            print("❌ Failed to generate OTP:", str(e))
            raise HTTPException(
                status_code=500,
                detail="Unable to generate OTP. Please try again.",
            )

        try:
            send_otp_email(email, otp)
        except Exception as e:
            if os.getenv("ENVIRONMENT", "development") == "development" or not (os.getenv("SMTP_USERNAME") and os.getenv("SMTP_PASSWORD")):
                print(f"⚠️ [DEV MODE] OTP generated for {email} ({otp}), email dispatch error: {e}")
            else:
                clear_otp(email)
                print("❌ OTP Email Dispatch Failed:", str(e))
                raise HTTPException(
                    status_code=503,
                    detail="Unable to send OTP email right now. Please try again.",
                )

    return {
        "message": "If an account exists for this email, an OTP has been sent."
    }


@app.post("/resend-otp")
def resend_otp_endpoint(request: ResendOTPRequest):
    email = request.email.strip().lower()

    if not email:
        raise HTTPException(
            status_code=400,
            detail="Email is required.",
        )

    user = get_user_by_email(email)

    if user is not None:
        try:
            otp = generate_or_resend_otp(email, is_resend=True)
        except HTTPException:
            raise
        except Exception as e:
            print("❌ Failed to resend OTP:", str(e))
            raise HTTPException(
                status_code=500,
                detail="Unable to generate new OTP. Please try again.",
            )

        try:
            send_otp_email(email, otp)
        except Exception as e:
            if os.getenv("ENVIRONMENT", "development") == "development" or not (os.getenv("SMTP_USERNAME") and os.getenv("SMTP_PASSWORD")):
                print(f"⚠️ [DEV MODE] Resend OTP generated for {email} ({otp}), email dispatch error: {e}")
            else:
                clear_otp(email)
                print("❌ Resend OTP Email Dispatch Failed:", str(e))
                raise HTTPException(
                    status_code=503,
                    detail="Unable to send OTP email right now. Please try again.",
                )

    return {
        "message": "A new OTP has been sent to your email."
    }


@app.post("/verify-otp")
def verify_otp_endpoint(request: VerifyOTPRequest):
    email = request.email.strip().lower()
    otp = request.otp.strip()

    if not email or not otp:
        raise HTTPException(
            status_code=400,
            detail="Email and OTP are required.",
        )

    try:
        is_valid = validate_otp(email, otp)
    except HTTPException:
        raise
    except Exception as e:
        print("❌ OTP Validation Error:", str(e))
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired OTP.",
        )

    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired OTP.",
        )

    return {
        "message": "OTP verified successfully.",
    }


@app.post("/reset-password")
def reset_password(request: ResetPasswordRequest):
    email = request.email.strip().lower()
    otp = request.otp.strip()
    new_password = request.new_password

    if not email or not otp or not new_password:
        raise HTTPException(
            status_code=400,
            detail="Email, OTP, and new password are required.",
        )

    if len(new_password) < 6:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 6 characters.",
        )

    try:
        is_valid = consume_and_verify_otp(email, otp)
    except HTTPException:
        raise
    except Exception as e:
        print("❌ OTP Consumption Error:", str(e))
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired OTP.",
        )

    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired OTP.",
        )

    user = get_user_by_email(email)

    if user is None:
        raise HTTPException(
            status_code=400,
            detail="Unable to reset password.",
        )

    try:
        updated = update_password(
            email,
            new_password,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )

    if not updated:
        raise HTTPException(
            status_code=400,
            detail="Unable to reset password.",
        )

    token = create_access_token(
        user["id"],
        user["email"],
    )

    return {
        "message": "Password reset successful.",
        "token": token,
        "user": {
            "id": user["id"],
            "email": user["email"],
        },
    }


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


# ============================================================
# BACKGROUND DOCUMENT PROCESSING WORKER
# ============================================================

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
                import json
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


# ============================================================
# UPLOAD DOCUMENT
# ============================================================

@app.post("/upload")
def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
):
    try:
        t_upload_start = time.time()

        # ----------------------------------------------------
        # Validate Filename & Path
        # ----------------------------------------------------
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

        # ----------------------------------------------------
        # Stream file to disk with 100 MB size enforcement & SHA256 content hashing
        # ----------------------------------------------------
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

        # ----------------------------------------------------
        # Security Content Validation
        # ----------------------------------------------------
        validate_uploaded_content(file_path, safe_filename)

        file_size_bytes = os.path.getsize(file_path)
        file_extension = os.path.splitext(safe_filename)[1].lower()

        # ----------------------------------------------------
        # Initialize Document Metadata with status 'processing'
        # ----------------------------------------------------
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

        # ----------------------------------------------------
        # Dispatch Asynchronous Background Indexing
        # ----------------------------------------------------
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


# ============================================================
# CONVERSATION MODELS & CHAT REQUEST
# ============================================================

class CreateConversationRequest(BaseModel):
    title: str | None = "New Conversation"


class UpdateConversationRequest(BaseModel):
    title: str


class ChatRequest(BaseModel):
    question: str
    filenames: list[str] | None = None
    filename: str | None = None
    conversation_id: int | None = None


class FeedbackRequest(BaseModel):
    conversation_id: int
    rating: Any
    message_id: int | None = None
    reason: str | None = None
    feedback_reason: str | None = None
    feedback_text: str | None = None
    note: str | None = None
    latency_perceived: str | None = None
    request_id: str | None = None


CACHE_ENABLED = os.getenv("CACHE_ENABLED", "true").lower() in ("true", "1", "yes")
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "86400"))


# ============================================================
# GET SELECTED FILENAMES
# ============================================================

def get_selected_filenames(
    request: ChatRequest,
) -> list[str]:

    filenames = []


    # --------------------------------------------------------
    # New frontend format
    # --------------------------------------------------------

    if request.filenames:

        for filename in request.filenames:

            if filename and filename.strip():

                clean_filename = (
                    filename.strip()
                )


                if (
                    clean_filename
                    not in filenames
                ):

                    filenames.append(
                        clean_filename
                    )


    # --------------------------------------------------------
    # Old frontend format
    # --------------------------------------------------------

    if (
        request.filename
        and request.filename.strip()
    ):

        clean_filename = (
            request.filename.strip()
        )


        if (
            clean_filename
            not in filenames
        ):

            filenames.append(
                clean_filename
            )


    return filenames


# ============================================================
# RETRIEVE CONTEXT FROM DOCUMENTS
# ============================================================

def retrieve_multi_document_context(
    question: str,
    filenames: list[str],
) -> str:

    if not filenames:

        return ""


    all_contexts = []


    print("=" * 70)

    print(
        "ðŸ”Ž MULTI-DOCUMENT RETRIEVAL"
    )

    print(
        "Question:",
        question,
    )

    print(
        "Documents:",
        filenames,
    )

    print("=" * 70)


    # --------------------------------------------------------
    # Retrieve each document separately
    # --------------------------------------------------------

    for index, filename in enumerate(
        filenames,
        start=1,
    ):

        try:

            print(
                f"ðŸ” Retrieving document {index}/{len(filenames)}:"
            )

            print(
                filename
            )


            context = retrieve_context(
                question,
                filename,
            )


            if context and context.strip():

                document_context = (
                    "\n"
                    + "=" * 60
                    + "\n"
                    + f"DOCUMENT {index}: {filename}"
                    + "\n"
                    + "=" * 60
                    + "\n"
                    + context.strip()
                    + "\n"
                )


                all_contexts.append(
                    document_context
                )


                print(
                    f"âœ… Context retrieved from: {filename}"
                )

                print(
                    "Context length:",
                    len(context),
                )


            else:

                print(
                    f"âš ï¸ No relevant context found in: {filename}"
                )


        except Exception as e:


            if isinstance(e, HTTPException):


                raise
            print(
                f"âŒ Retrieval failed for {filename}:",
                str(e),
            )


    # --------------------------------------------------------
    # Combine all document contexts
    # --------------------------------------------------------

    combined_context = "\n".join(
        all_contexts
    )


    print("=" * 70)

    print(
        "ðŸ“š COMBINED CONTEXT LENGTH:",
        len(combined_context),
    )

    print(
        "ðŸ“„ DOCUMENT COUNT:",
        len(filenames),
    )

    print("=" * 70)


    return combined_context


# ============================================================
# DOCUMENT-WIDE EXPLANATION
# ============================================================

@app.post("/document-summary")
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
                "answer": "ðŸ“„ Please select a document."
            }

        filenames = validate_user_documents(
            filenames,
            current_user["user_id"],
        )

        filename = filenames[0]
        print("=" * 70)
        print("ðŸ“„ DOCUMENT SUMMARY REQUEST")
        print("Filename:", filename)
        print("=" * 70)

        file_path = get_safe_document_path(filename)

        if not os.path.isfile(file_path):
            return {
                "filename": filename,
                "mode": "cloud",
                "answer": "ðŸ“„ Document not found."
            }

        print("ðŸ“– Extracting complete document text...")
        extracted_text = extract_text(file_path)

        if not extracted_text or not extracted_text.strip():
            return {
                "filename": filename,
                "mode": "cloud",
                "answer": "I couldn't find readable content in the uploaded document."
            }

        print("ðŸ“ Extracted text length:", len(extracted_text))

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


# ============================================================
# CONVERSATIONS REST API
# ============================================================

@app.post("/conversations")
def create_new_conversation(
    request: CreateConversationRequest = None,
    current_user=Depends(get_current_user),
):
    user_id = current_user["user_id"]
    title = request.title if (request and request.title) else "New Conversation"
    conv = create_conversation(user_id, title)
    return conv


@app.get("/conversations")
def list_conversations(
    current_user=Depends(get_current_user),
):
    user_id = current_user["user_id"]
    conversations = get_user_conversations(user_id)
    return conversations


@app.get("/conversations/{conversation_id}")
def get_single_conversation(
    conversation_id: int,
    current_user=Depends(get_current_user),
):
    user_id = current_user["user_id"]
    conv = get_conversation(conversation_id, user_id)
    if conv is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found.",
        )
    return conv


@app.patch("/conversations/{conversation_id}")
def rename_conversation(
    conversation_id: int,
    request: UpdateConversationRequest,
    current_user=Depends(get_current_user),
):
    user_id = current_user["user_id"]
    if not request.title or not request.title.strip():
        raise HTTPException(
            status_code=400,
            detail="Conversation title cannot be empty.",
        )
    success = update_conversation_title(conversation_id, user_id, request.title.strip())
    if not success:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found.",
        )
    return {
        "message": "Conversation renamed successfully.",
        "id": conversation_id,
        "title": request.title.strip(),
    }


@app.delete("/conversations/{conversation_id}")
def remove_conversation(
    conversation_id: int,
    current_user=Depends(get_current_user),
):
    user_id = current_user["user_id"]
    success = delete_conversation(conversation_id, user_id)
    if not success:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found.",
        )
    return {
        "message": "Conversation deleted successfully.",
        "id": conversation_id,
    }


def resolve_or_create_conversation(user_id: int, conv_id: int | None, question: str, filenames: list[str]) -> tuple[int, str]:
    if conv_id:
        conv = get_conversation(conv_id, user_id)
        if conv is None:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found.",
            )
        conv_title = conv.get("title", "Conversation")
    else:
        conv_title = generate_conversation_title(question)
        conv = create_conversation(user_id, conv_title)
        conv_id = conv["id"]

    # Save user message
    save_message(conv_id, "user", question)

    # Persist document selection for this conversation
    if filenames:
        set_conversation_documents(conv_id, user_id, filenames)
    else:
        set_conversation_documents(conv_id, user_id, [])

    return conv_id, conv_title


# ============================================================
# CLOUD AI - GEMINI
# ============================================================

@app.post("/chat")
def chat(
    request: ChatRequest,
    current_user=Depends(get_current_user),
):
    t_req_start = time.perf_counter()
    request_id = str(uuid.uuid4())
    try:
        user_id = current_user.get("user_id") if isinstance(current_user, dict) else getattr(current_user, "id", "unknown")
        user_email = current_user.get("email") if isinstance(current_user, dict) else getattr(current_user, "email", "unknown")
        filenames = get_selected_filenames(request)

        # Stage [1] REQUEST PARSED
        print("=" * 70)
        print(f"🔹 [STAGE 1] REQUEST PARSED: req_id={request_id[:8]}, user_id={user_id}, question='{request.question[:60]}...', doc_count={len(filenames)}, filenames={filenames}")

        # Stage [2] AUTHENTICATION PASSED
        print(f"🔹 [STAGE 2] AUTHENTICATION PASSED: user_id={user_id}, email={user_email}")

        # Validate documents if specified
        if filenames:
            validated_filenames = validate_user_documents(
                filenames,
                current_user["user_id"],
            )
        else:
            validated_filenames = []

        # Resolve or create persistent conversation & save user message
        conv_id, conv_title = resolve_or_create_conversation(
            current_user["user_id"],
            request.conversation_id,
            request.question,
            validated_filenames,
        )

        active_model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        normalized_query = request.question.strip()
        doc_fingerprint = compute_document_fingerprint(current_user["user_id"], validated_filenames)
        cache_key = compute_cache_key(current_user["user_id"], normalized_query, doc_fingerprint, active_model)

        # ----------------------------------------------------
        # RESPONSE CACHE CHECK
        # ----------------------------------------------------
        if CACHE_ENABLED:
            cached = get_cached_response(current_user["user_id"], cache_key)
            if cached:
                total_ms = (time.perf_counter() - t_req_start) * 1000
                msg_id = save_message(conv_id, "assistant", cached["answer"])
                touch_conversation(conv_id, current_user["user_id"])
                print(f"⚡ [CACHE HIT] Query resolved in {total_ms:.2f}ms (key={cache_key[:8]}...)")

                record_ai_metric(
                    request_id=request_id,
                    user_id=current_user["user_id"],
                    conversation_id=conv_id,
                    query_type="cached",
                    optimizer_strategy="cache_hit",
                    retrieval_ms=0.0,
                    total_ms=total_ms,
                    citation_count=len(cached.get("citations", [])),
                    grounding_score=cached.get("grounding", {}).get("grounding_score", 1.0) if cached.get("grounding") else 1.0,
                    model=active_model,
                    streaming=0,
                    cache_hit=1,
                    status="success",
                )

                return {
                    "question": request.question,
                    "filenames": validated_filenames,
                    "sources": validated_filenames if validated_filenames else [],
                    "mode": "cloud",
                    "answer": cached["answer"],
                    "response": cached["answer"],
                    "citations": cached.get("citations", []),
                    "grounding": cached.get("grounding") or {
                        "grounding_score": 1.0,
                        "supported_claim_ratio": 1.0,
                        "unsupported_claim_ratio": 0.0,
                    },
                    "evidence_quality": "High",
                    "conversation_id": conv_id,
                    "conversation_title": conv_title,
                    "request_id": request_id,
                    "message_id": msg_id,
                    "cache_hit": True,
                }

        # ----------------------------------------------------
        # GENERAL AI (No document selected)
        # ----------------------------------------------------
        if not validated_filenames:
            print("🌐 Executing General AI Chat (No documents attached)...")
            t_gen_start = time.perf_counter()
            answer = ask_gemini_general(request.question)
            gen_ms = (time.perf_counter() - t_gen_start) * 1000
            total_ms = (time.perf_counter() - t_req_start) * 1000

            msg_id = save_message(conv_id, "assistant", answer)
            touch_conversation(conv_id, current_user["user_id"])

            if CACHE_ENABLED:
                set_cached_response(
                    user_id=current_user["user_id"],
                    cache_key=cache_key,
                    normalized_query=normalized_query,
                    doc_fingerprint=doc_fingerprint,
                    model=active_model,
                    answer=answer,
                    citations=[],
                    grounding={"grounding_score": 1.0, "supported_claim_ratio": 1.0, "unsupported_claim_ratio": 0.0},
                    conversation_id=conv_id,
                    ttl_seconds=CACHE_TTL_SECONDS,
                )

            record_ai_metric(
                request_id=request_id,
                user_id=current_user["user_id"],
                conversation_id=conv_id,
                query_type="general_ai",
                optimizer_strategy="direct_generation",
                retrieval_ms=0.0,
                generation_ms=gen_ms,
                total_ms=total_ms,
                output_tokens=len(answer.split()),
                citation_count=0,
                grounding_score=1.0,
                model=active_model,
                streaming=0,
                cache_hit=0,
                status="success",
            )

            print(f"✅ [STAGE 10] CHAT SUCCESS: Mode=General AI, Answer Length={len(answer)} chars, Conv ID={conv_id}")
            print("=" * 70)
            return {
                "question": request.question,
                "filenames": [],
                "sources": [],
                "mode": "cloud",
                "answer": answer,
                "response": answer,
                "citations": [],
                "grounding": {
                    "score": 1.0,
                    "grounding_score": 1.0,
                    "supported_claim_ratio": 1.0,
                    "unsupported_claim_ratio": 0.0,
                },
                "conversation_id": conv_id,
                "conversation_title": conv_title,
                "request_id": request_id,
                "message_id": msg_id,
                "cache_hit": False,
            }

        # Stage [3] DOCUMENT LOOKUP START
        print(f"🔹 [STAGE 3] DOCUMENT LOOKUP START: checking sqlite ownership for user_id={user_id}, docs={validated_filenames}")

        # Stage [4] DOCUMENT LOOKUP RESULT
        print(f"🔹 [STAGE 4] DOCUMENT LOOKUP RESULT: verified={validated_filenames}, count={len(validated_filenames)}")

        # Stage [5] ADVANCED HYBRID RETRIEVAL START
        print(f"🔹 [STAGE 5] ADVANCED HYBRID RETRIEVAL START: querying Hybrid RAG (BM25 + Chroma) for question='{request.question[:60]}...' against {validated_filenames}")

        # Retrieve hybrid context with reranking, window expansion & prompt injection shielding
        retrieval_res = NexusAdvancedRAG.retrieve_hybrid_context(
            request.question,
            validated_filenames,
            user_id=current_user["user_id"],
        )
        context = retrieval_res["formatted_context"]
        evidence_quality = retrieval_res["evidence_quality"]
        raw_citations = retrieval_res.get("citations", [])
        retrieval_timings = retrieval_res.get("timings", {})
        strategy_info = retrieval_res.get("strategy", {})

        # Stage [6] ADVANCED RETRIEVAL RESULT
        print(f"🔹 [STAGE 6] ADVANCED RETRIEVAL RESULT: retrieved context length={len(context)} chars, evidence_quality={evidence_quality}")

        if not context.strip():
            print("⚠️ No relevant context found across documents.")
            fallback_ans = "I couldn't find relevant information in the selected document(s)."
            msg_id = save_message(conv_id, "assistant", fallback_ans)
            touch_conversation(conv_id, current_user["user_id"])
            total_ms = (time.perf_counter() - t_req_start) * 1000

            record_ai_metric(
                request_id=request_id,
                user_id=current_user["user_id"],
                conversation_id=conv_id,
                query_type=strategy_info.get("query_type", "document_rag"),
                optimizer_strategy=strategy_info.get("complexity", "hybrid"),
                retrieval_ms=retrieval_timings.get("total_retrieval_ms"),
                chroma_ms=retrieval_timings.get("semantic_search_ms"),
                bm25_ms=retrieval_timings.get("bm25_ms"),
                cross_encoder_ms=retrieval_timings.get("cross_encoder_ms"),
                compression_ms=retrieval_timings.get("compression_ms"),
                generation_ms=0.0,
                total_ms=total_ms,
                citation_count=0,
                grounding_score=1.0,
                model=active_model,
                streaming=0,
                cache_hit=0,
                status="insufficient_evidence",
            )

            return {
                "question": request.question,
                "filenames": validated_filenames,
                "sources": validated_filenames if validated_filenames else [],
                "mode": "cloud",
                "answer": fallback_ans,
                "response": fallback_ans,
                "citations": [],
                "grounding": {
                    "score": 1.0,
                    "grounding_score": 1.0,
                    "supported_claim_ratio": 1.0,
                    "unsupported_claim_ratio": 0.0,
                    "is_insufficient_evidence": True,
                },
                "evidence_quality": "Low",
                "conversation_id": conv_id,
                "conversation_title": conv_title,
                "request_id": request_id,
                "message_id": msg_id,
                "cache_hit": False,
            }

        # Stage [7] GEMINI CALL START
        print(f"🔹 [STAGE 7] GEMINI CALL START: model={active_model}, context_chars={len(context)}, question='{request.question[:60]}...'")

        # Generate Gemini answer via ModelProvider with Output Privacy Guard
        t_gen_start = time.perf_counter()
        gemini_provider = GeminiModelProvider()
        answer = gemini_provider.generate_response(
            context,
            request.question,
            user_id=str(user_id),
        )
        gen_ms = (time.perf_counter() - t_gen_start) * 1000

        # Validate citations and compute grounding
        validated_answer, validated_citations = SourceCitationManager.validate_citations(
            answer, raw_citations, retrieval_res.get("top_chunks", [])
        )
        grounding_eval = DeterministicGroundingEvaluator.evaluate(
            request.question,
            retrieval_res.get("top_chunks", []),
            validated_answer,
            validated_citations,
        )

        total_ms = (time.perf_counter() - t_req_start) * 1000

        # Stage [8] GEMINI RESPONSE RECEIVED
        print(f"🔹 [STAGE 8] GEMINI RESPONSE RECEIVED: response_status=200, elapsed={gen_ms/1000:.2f}s, answer_chars={len(validated_answer) if validated_answer else 0}")

        # Stage [9] RESPONSE PARSED
        print(f"🔹 [STAGE 9] RESPONSE PARSED: parsed length={len(validated_answer) if validated_answer else 0} chars, sample='{str(validated_answer)[:80]}...'")

        # Save assistant answer to conversation
        msg_id = save_message(conv_id, "assistant", validated_answer)
        touch_conversation(conv_id, current_user["user_id"])

        # Cache response
        if CACHE_ENABLED:
            set_cached_response(
                user_id=current_user["user_id"],
                cache_key=cache_key,
                normalized_query=normalized_query,
                doc_fingerprint=doc_fingerprint,
                model=active_model,
                answer=validated_answer,
                citations=validated_citations,
                grounding=grounding_eval,
                conversation_id=conv_id,
                ttl_seconds=CACHE_TTL_SECONDS,
            )

        # Record telemetry
        record_ai_metric(
            request_id=request_id,
            user_id=current_user["user_id"],
            conversation_id=conv_id,
            query_type=strategy_info.get("query_type", "document_rag"),
            optimizer_strategy=strategy_info.get("complexity", "hybrid"),
            retrieval_ms=retrieval_timings.get("total_retrieval_ms"),
            chroma_ms=retrieval_timings.get("semantic_search_ms"),
            bm25_ms=retrieval_timings.get("bm25_ms"),
            cross_encoder_ms=retrieval_timings.get("cross_encoder_ms"),
            compression_ms=retrieval_timings.get("compression_ms"),
            generation_ms=gen_ms,
            total_ms=total_ms,
            context_tokens=len(context.split()),
            output_tokens=len(validated_answer.split()),
            citation_count=len(validated_citations),
            grounding_score=grounding_eval.get("grounding_score"),
            model=active_model,
            streaming=0,
            cache_hit=0,
            status="success",
        )

        # Stage [10] CHAT SUCCESS
        print(f"✅ [STAGE 10] CHAT SUCCESS: HTTP 200 returned for user_id={user_id}, docs={validated_filenames}, Conv ID={conv_id} in {total_ms:.1f}ms")
        print("=" * 70)

        return {
            "question": request.question,
            "filenames": validated_filenames,
            "sources": validated_filenames if validated_filenames else [],
            "mode": "cloud",
            "answer": validated_answer,
            "response": validated_answer,
            "citations": validated_citations,
            "grounding": {
                "score": grounding_eval["grounding_score"],
                "grounding_score": grounding_eval["grounding_score"],
                "supported_claim_ratio": grounding_eval["supported_claim_ratio"],
                "unsupported_claim_ratio": grounding_eval["unsupported_claim_ratio"],
            },
            "evidence_quality": evidence_quality,
            "conversation_id": conv_id,
            "conversation_title": conv_title,
            "request_id": request_id,
            "message_id": msg_id,
            "cache_hit": False,
        }

    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        print("=" * 70)
        print("[ERROR] ========== CHAT EXCEPTION ==========")
        print("Exception Type   :", type(e).__name__)
        print("Exception Message:", str(e))
        print("=" * 70)
        raise HTTPException(
            status_code=503,
            detail="Cloud AI service is temporarily unavailable. Please try again.",
        )


# ============================================================
# CLOUD AI - GEMINI STREAMING (SSE)
# ============================================================

@app.post("/chat/stream")
def chat_stream(
    request: ChatRequest,
    current_user=Depends(get_current_user),
):
    t_req_start = time.perf_counter()
    request_id = str(uuid.uuid4())
    try:
        user_id = current_user.get("user_id") if isinstance(current_user, dict) else getattr(current_user, "id", "unknown")
        user_email = current_user.get("email") if isinstance(current_user, dict) else getattr(current_user, "email", "unknown")
        filenames = get_selected_filenames(request)

        # Validate documents if specified
        if filenames:
            validated_filenames = validate_user_documents(
                filenames,
                current_user["user_id"],
            )
        else:
            validated_filenames = []

        # Resolve or create persistent conversation & save user message
        conv_id, conv_title = resolve_or_create_conversation(
            current_user["user_id"],
            request.conversation_id,
            request.question,
            validated_filenames,
        )

        active_model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        normalized_query = request.question.strip()
        doc_fingerprint = compute_document_fingerprint(current_user["user_id"], validated_filenames)
        cache_key = compute_cache_key(current_user["user_id"], normalized_query, doc_fingerprint, active_model)

        # ----------------------------------------------------
        # STREAMING RESPONSE CACHE CHECK
        # ----------------------------------------------------
        if CACHE_ENABLED:
            cached = get_cached_response(current_user["user_id"], cache_key)
            if cached:
                def cached_event_stream():
                    # 1. Start event
                    start_payload = {
                        "conversation_id": conv_id,
                        "conversation_title": conv_title,
                        "filenames": validated_filenames,
                        "mode": "cloud",
                        "request_id": request_id,
                        "cache_hit": True,
                    }
                    yield f"event: start\ndata: {json.dumps(start_payload)}\n\n"

                    # 2. Token payload
                    yield f"event: token\ndata: {json.dumps({'text': cached['answer']})}\n\n"

                    # 3. Persist message
                    msg_id = save_message(conv_id, "assistant", cached["answer"])
                    touch_conversation(conv_id, current_user["user_id"])

                    # 4. Complete payload
                    total_ms = (time.perf_counter() - t_req_start) * 1000
                    complete_payload = {
                        "conversation_id": conv_id,
                        "conversation_title": conv_title,
                        "final_text": cached["answer"],
                        "citations": cached.get("citations", []),
                        "grounding": cached.get("grounding") or {
                            "score": 1.0,
                            "grounding_score": 1.0,
                            "supported_claim_ratio": 1.0,
                            "unsupported_claim_ratio": 0.0,
                        },
                        "status": "complete",
                        "request_id": request_id,
                        "message_id": msg_id,
                        "cache_hit": True,
                    }
                    yield f"event: complete\ndata: {json.dumps(complete_payload)}\n\n"

                    record_ai_metric(
                        request_id=request_id,
                        user_id=current_user["user_id"],
                        conversation_id=conv_id,
                        query_type="cached",
                        optimizer_strategy="cache_hit",
                        retrieval_ms=0.0,
                        ttft_ms=total_ms,
                        total_ms=total_ms,
                        citation_count=len(cached.get("citations", [])),
                        grounding_score=cached.get("grounding", {}).get("grounding_score", 1.0) if cached.get("grounding") else 1.0,
                        model=active_model,
                        streaming=1,
                        cache_hit=1,
                        status="success",
                    )

                return StreamingResponse(
                    cached_event_stream(),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "X-Accel-Buffering": "no",
                        "X-Conversation-Id": str(conv_id),
                        "X-Conversation-Title": conv_title,
                        "X-Request-Id": request_id,
                    },
                )

        # ----------------------------------------------------
        # LIVE GENERATION STREAM (Cache Miss)
        # ----------------------------------------------------
        def event_stream():
            accumulated_text = ""
            ttft_ms = None
            retrieval_timings = {}
            strategy_info = {}
            stream_started = time.perf_counter()

            try:
                # 1. Start event
                start_payload = {
                    "conversation_id": conv_id,
                    "conversation_title": conv_title,
                    "filenames": validated_filenames,
                    "mode": "cloud",
                    "request_id": request_id,
                }
                yield f"event: start\ndata: {json.dumps(start_payload)}\n\n"

                # 2. General AI (No document selected)
                if not validated_filenames:
                    print(f"🌐 [STREAM] Executing General AI Chat Stream (user_id={user_id}, conv_id={conv_id})...")
                    query_type = "general_ai"
                    optimizer_strat = "direct_generation"
                    for chunk in ask_gemini_general_stream(request.question):
                        if chunk:
                            if ttft_ms is None:
                                ttft_ms = (time.perf_counter() - t_req_start) * 1000
                            accumulated_text += chunk
                            yield f"event: token\ndata: {json.dumps({'text': chunk})}\n\n"

                # 3. Document Grounded RAG
                else:
                    print(f"📚 [STREAM] Executing Document RAG Stream (user_id={user_id}, docs={validated_filenames})...")
                    retrieval_res = NexusAdvancedRAG.retrieve_hybrid_context(
                        request.question,
                        validated_filenames,
                        user_id=current_user["user_id"],
                    )
                    context = retrieval_res["formatted_context"]
                    evidence_quality = retrieval_res["evidence_quality"]
                    retrieval_timings = retrieval_res.get("timings", {})
                    strategy_info = retrieval_res.get("strategy", {})
                    query_type = strategy_info.get("query_type", "document_rag")
                    optimizer_strat = strategy_info.get("complexity", "hybrid")

                    if not context.strip():
                        fallback_ans = "I couldn't find relevant information in the selected document(s)."
                        accumulated_text = fallback_ans
                        ttft_ms = (time.perf_counter() - t_req_start) * 1000
                        yield f"event: token\ndata: {json.dumps({'text': fallback_ans})}\n\n"
                    else:
                        for chunk in ask_gemini_stream(context, request.question):
                            if chunk:
                                if ttft_ms is None:
                                    ttft_ms = (time.perf_counter() - t_req_start) * 1000
                                accumulated_text += chunk
                                yield f"event: token\ndata: {json.dumps({'text': chunk})}\n\n"

                # 4. Output Privacy Guard sanitization & Citation validation
                safe_text, was_redacted, reason = OutputPrivacyGuard.guard(accumulated_text)
                if was_redacted:
                    print(f"🛡️ [STREAM PRIVACY] Output sanitized: {reason}")

                if validated_filenames and 'retrieval_res' in locals() and retrieval_res.get("top_chunks"):
                    raw_citations = retrieval_res.get("citations", [])
                    validated_text, validated_citations = SourceCitationManager.validate_citations(
                        safe_text, raw_citations, retrieval_res.get("top_chunks", [])
                    )
                    grounding_eval = DeterministicGroundingEvaluator.evaluate(
                        request.question,
                        retrieval_res.get("top_chunks", []),
                        validated_text,
                        validated_citations,
                    )
                else:
                    validated_text = safe_text
                    validated_citations = []
                    grounding_eval = {
                        "score": 1.0,
                        "grounding_score": 1.0,
                        "supported_claim_ratio": 1.0,
                        "unsupported_claim_ratio": 0.0,
                    }

                # 5. Persist final assistant response to SQLite
                msg_id = save_message(conv_id, "assistant", validated_text)
                touch_conversation(conv_id, current_user["user_id"])

                total_ms = (time.perf_counter() - t_req_start) * 1000
                gen_ms = total_ms - (retrieval_timings.get("total_retrieval_ms") or 0.0)

                # 6. Save in response cache (only on successful completed stream)
                if CACHE_ENABLED and validated_text.strip():
                    set_cached_response(
                        user_id=current_user["user_id"],
                        cache_key=cache_key,
                        normalized_query=normalized_query,
                        doc_fingerprint=doc_fingerprint,
                        model=active_model,
                        answer=validated_text,
                        citations=validated_citations,
                        grounding=grounding_eval,
                        conversation_id=conv_id,
                        ttl_seconds=CACHE_TTL_SECONDS,
                    )

                # 7. Record Telemetry
                record_ai_metric(
                    request_id=request_id,
                    user_id=current_user["user_id"],
                    conversation_id=conv_id,
                    query_type=query_type,
                    optimizer_strategy=optimizer_strat,
                    retrieval_ms=retrieval_timings.get("total_retrieval_ms"),
                    chroma_ms=retrieval_timings.get("semantic_search_ms"),
                    bm25_ms=retrieval_timings.get("bm25_ms"),
                    cross_encoder_ms=retrieval_timings.get("cross_encoder_ms"),
                    compression_ms=retrieval_timings.get("compression_ms"),
                    ttft_ms=ttft_ms,
                    generation_ms=gen_ms,
                    total_ms=total_ms,
                    context_tokens=len(context.split()) if ('context' in locals() and context) else 0,
                    output_tokens=len(validated_text.split()),
                    citation_count=len(validated_citations),
                    grounding_score=grounding_eval.get("grounding_score", 1.0),
                    model=active_model,
                    streaming=1,
                    cache_hit=0,
                    status="success",
                )

                # 8. Complete event
                complete_payload = {
                    "conversation_id": conv_id,
                    "conversation_title": conv_title,
                    "final_text": validated_text,
                    "citations": validated_citations,
                    "grounding": {
                        "score": grounding_eval.get("grounding_score", 1.0),
                        "grounding_score": grounding_eval.get("grounding_score", 1.0),
                        "supported_claim_ratio": grounding_eval.get("supported_claim_ratio", 1.0),
                        "unsupported_claim_ratio": grounding_eval.get("unsupported_claim_ratio", 0.0),
                    },
                    "status": "complete",
                    "request_id": request_id,
                    "message_id": msg_id,
                    "cache_hit": False,
                }
                yield f"event: complete\ndata: {json.dumps(complete_payload)}\n\n"

            except Exception as stream_err:
                print(f"❌ [STREAM ERROR] {type(stream_err).__name__}: {str(stream_err)}")
                error_msg = "Cloud AI service is temporarily unavailable. Please try again."
                if accumulated_text:
                    try:
                        safe_text, _, _ = OutputPrivacyGuard.guard(accumulated_text)
                        save_message(conv_id, "assistant", safe_text)
                        touch_conversation(conv_id, current_user["user_id"])
                    except Exception:
                        pass
                yield f"event: error\ndata: {json.dumps({'detail': error_msg})}\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "X-Conversation-Id": str(conv_id),
                "X-Conversation-Title": conv_title,
                "X-Request-Id": request_id,
            },
        )

    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        print("❌ [CHAT STREAM ROUTE ERROR]:", str(e))
        raise HTTPException(
            status_code=503,
            detail="Cloud AI streaming is temporarily unavailable. Please try again.",
        )



# ============================================================
# LOCAL AI - QWEN NORMAL RESPONSE
# ============================================================

@app.post("/local-chat-normal")
def local_chat_normal(
    request: ChatRequest,
    current_user=Depends(get_current_user),
):
    try:
        filenames = get_selected_filenames(request)

        if filenames:
            validated_filenames = validate_user_documents(
                filenames,
                current_user["user_id"],
            )
        else:
            validated_filenames = []

        conv_id, conv_title = resolve_or_create_conversation(
            current_user["user_id"],
            request.conversation_id,
            request.question,
            validated_filenames,
        )

        if not validated_filenames:
            answer = ask_local("", request.question)
            save_message(conv_id, "assistant", answer)
            touch_conversation(conv_id, current_user["user_id"])
            return {
                "question": request.question,
                "filenames": [],
                "mode": "local",
                "answer": answer,
                "conversation_id": conv_id,
                "conversation_title": conv_title,
            }

        retrieval_res = NexusAdvancedRAG.retrieve_hybrid_context(
            request.question,
            validated_filenames,
            user_id=current_user["user_id"],
        )
        context = retrieval_res["formatted_context"]
        evidence_quality = retrieval_res["evidence_quality"]

        if not context.strip():
            fallback_ans = "I couldn't find relevant information in the selected document(s)."
            save_message(conv_id, "assistant", fallback_ans)
            touch_conversation(conv_id, current_user["user_id"])
            return {
                "question": request.question,
                "filenames": validated_filenames,
                "mode": "local",
                "answer": fallback_ans,
                "evidence_quality": "Low",
                "conversation_id": conv_id,
                "conversation_title": conv_title,
            }

        local_provider = LocalQwenModelProvider()
        answer = local_provider.generate_response(
            context,
            request.question,
            user_id=str(current_user["user_id"]),
        )

        save_message(conv_id, "assistant", answer)
        touch_conversation(conv_id, current_user["user_id"])

        return {
            "question": request.question,
            "filenames": validated_filenames,
            "sources": validated_filenames if validated_filenames else [],
            "mode": "local",
            "answer": answer,
            "conversation_id": conv_id,
            "conversation_title": conv_title,
        }

    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        print("❌ Local Chat Error:", str(e))
        raise HTTPException(
            status_code=500,
            detail="Local chat failed.",
        )


# ============================================================
# LOCAL AI - STREAMING QWEN
# ============================================================

@app.post("/local-chat")
def local_chat(
    request: ChatRequest,
    current_user=Depends(get_current_user),
):
    try:
        filenames = get_selected_filenames(request)

        if filenames:
            validated_filenames = validate_user_documents(
                filenames,
                current_user["user_id"],
            )
        else:
            validated_filenames = []

        conv_id, conv_title = resolve_or_create_conversation(
            current_user["user_id"],
            request.conversation_id,
            request.question,
            validated_filenames,
        )

        if not validated_filenames:
            stream_gen = stream_local("", request.question)
        else:
            retrieval_res = NexusAdvancedRAG.retrieve_hybrid_context(
                request.question,
                validated_filenames,
                user_id=current_user["user_id"],
            )
            context = retrieval_res["formatted_context"]
            evidence_quality = retrieval_res["evidence_quality"]
            if not context.strip():
                fallback_ans = "I couldn't find relevant information in the selected document(s)."
                save_message(conv_id, "assistant", fallback_ans)
                touch_conversation(conv_id, current_user["user_id"])
                return StreamingResponse(
                    iter([fallback_ans]),
                    media_type="text/plain; charset=utf-8",
                    headers={
                        "X-Conversation-Id": str(conv_id),
                        "X-Conversation-Title": conv_title,
                        "X-Evidence-Quality": "Low",
                    },
                )
            stream_gen = stream_local(context, request.question)

        def stream_with_persistence():
            full_chunks = []
            try:
                for chunk in stream_gen:
                    full_chunks.append(chunk)
                    yield chunk
            finally:
                complete_text = "".join(full_chunks)
                if complete_text.strip():
                    try:
                        save_message(conv_id, "assistant", complete_text)
                        touch_conversation(conv_id, current_user["user_id"])
                    except Exception as persist_err:
                        print("Failed to persist streaming message:", persist_err)

        return StreamingResponse(
            stream_with_persistence(),
            media_type="text/plain; charset=utf-8",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
                "X-Conversation-Id": str(conv_id),
                "X-Conversation-Title": conv_title,
            },
        )

    except Exception as e:


        if isinstance(e, HTTPException):


            raise
        print(
            "âŒ Local Streaming Chat Error:",
            str(e),
        )


        return StreamingResponse(

            iter([
                "âŒ Local AI request failed."
            ]),

            media_type=
                "text/plain; charset=utf-8",
        )


# ============================================================
# LOCAL AI WARM-UP
# ============================================================

@app.post("/local-warmup")
def local_warmup(
    current_user=Depends(get_current_user),
):

    try:

        print("=" * 70)

        print(
            "ðŸ”¥ LOCAL AI WARM-UP REQUEST"
        )

        print("=" * 70)


        result = warmup_local_model()


        return result


    except Exception as e:


        if isinstance(e, HTTPException):


            raise
        print(
            "âŒ Local Warm-up Error:",
            str(e),
        )


        return {

            "status":
                "error",

            "error":
                "Local model warm-up failed.",
        }


# ============================================================
# DOCUMENT OWNERSHIP HELPERS
# ============================================================

def document_belongs_to_user(
    filename: str,
    user_id: int,
) -> bool:
    conn = sqlite3.connect(os.path.join(BASE_DIR, "auth.db"))
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

    conn = sqlite3.connect(os.path.join(BASE_DIR, "auth.db"))
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


# ============================================================
# DOCUMENTS API
# ============================================================

@app.get("/documents")
def get_documents(
    current_user=Depends(get_current_user),
):
    try:
        conn = sqlite3.connect(os.path.join(BASE_DIR, "auth.db"))
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


# ============================================================
# DELETE DOCUMENT
# ============================================================

@app.delete(
    "/documents/{filename}"
)
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

        file_path = get_safe_document_path(
            filename
        )


        if not os.path.isfile(
            file_path
        ):

            return {

                "message":
                    "Document not found",

                "filename":
                    filename,
            }


        os.remove(
            file_path
        )

        # Delete from Chroma vector store and invalidate BM25 index
        delete_document_from_vector_store(filename)

        # Invalidate response cache for this document
        invalidate_document_cache(current_user["user_id"], filename)

        conn = sqlite3.connect(os.path.join(BASE_DIR, "auth.db"))
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


        print(
            "ðŸ—‘ï¸ Document deleted:",
            filename,
        )


        return {

            "message":
                "Document deleted successfully",

            "filename":
                filename,
        }


    except Exception as e:


        if isinstance(e, HTTPException):


            raise
        return {

            "message":
                "Failed to delete document",

            "filename":
                filename,

            "error":
                "Failed to delete document.",
        }


# ============================================================
# VIEW / DOWNLOAD DOCUMENT
# ============================================================

@app.get(
    "/documents/{filename}/file"
)
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


    file_path = get_safe_document_path(
        filename
    )


    if not os.path.isfile(
        file_path
    ):

        return {

            "message":
                "Document not found",

            "filename":
                filename,
        }


    extension = os.path.splitext(
        filename
    )[1].lower()


    media_types = {

        ".pdf":
            "application/pdf",

        ".txt":
            "text/plain",

        ".doc":
            "application/msword",

        ".docx":
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",

        ".ppt":
            "application/vnd.ms-powerpoint",

        ".pptx":
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",

        ".xls":
            "application/vnd.ms-excel",

        ".xlsx":
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }


    media_type = media_types.get(
        extension,
        "application/octet-stream",
    )


    # --------------------------------------------------------
    # DOWNLOAD
    # --------------------------------------------------------

    if download:

        return FileResponse(

            path=file_path,

            media_type=media_type,

            filename=filename,
        )


    # --------------------------------------------------------
    # VIEW
    # --------------------------------------------------------

    return FileResponse(

        path=file_path,

        media_type=media_type,

        headers={

            "Content-Disposition":
                "inline",
        },
    )


# ============================================================
# RAG EVALUATION & BENCHMARK API
# ============================================================

@app.post("/rag/evaluate")
def evaluate_rag(
    current_user=Depends(get_current_user),
):
    """
    Run deterministic RAG evaluation benchmark across all 10 query categories.
    JWT protected and operates strictly within authorized document isolation.
    """
    try:
        evaluator = RAGEvaluator()
        user_ctx = {
            "user_id": current_user.get("user_id") if isinstance(current_user, dict) else getattr(current_user, "id", 1),
            "email": current_user.get("email") if isinstance(current_user, dict) else getattr(current_user, "email", "eval_user"),
        }
        report = evaluator.run_evaluation(
            user_context=user_ctx,
            use_optimizer=True,
            generate_answers=False,
        )
        evaluator.save_reports(report)
        return report
    except Exception as e:
        print(f"❌ [RAG EVALUATION ERROR]: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Evaluation failed: {str(e)}",
        )


@app.get("/rag/evaluation/latest")
def get_latest_evaluation(
    current_user=Depends(get_current_user),
):
    """Retrieve the latest cached RAG evaluation report (JSON format)."""
    report_path = os.path.join(BASE_DIR, "evaluation_reports", "rag_evaluation_latest.json")
    if not os.path.exists(report_path):
        raise HTTPException(status_code=404, detail="No evaluation report found. Run POST /rag/evaluate first.")
    with open(report_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ============================================================
# v1.2.0 OBSERVABILITY & ANALYTICS APIs
# ============================================================

@app.get("/analytics/overview")
def get_analytics_overview(
    days: int = 7,
    current_user=Depends(get_current_user),
):
    """Retrieve overall system analytics for the authenticated user."""
    safe_days = max(1, min(days, 90))
    user_id = current_user.get("user_id") if isinstance(current_user, dict) else getattr(current_user, "id", 1)
    summary = get_user_analytics_summary(user_id, days=safe_days)
    return summary


@app.get("/analytics/latency")
def get_analytics_latency(
    days: int = 7,
    limit: int = 50,
    current_user=Depends(get_current_user),
):
    """Retrieve time-series latency breakdown records for charts."""
    safe_days = max(1, min(days, 90))
    safe_limit = max(1, min(limit, 200))
    user_id = current_user.get("user_id") if isinstance(current_user, dict) else getattr(current_user, "id", 1)
    data = get_user_latency_series(user_id, days=safe_days, limit=safe_limit)
    return {"latency_series": data}


@app.get("/analytics/rag")
def get_analytics_rag(
    days: int = 7,
    current_user=Depends(get_current_user),
):
    """Retrieve query type distribution and RAG optimizer strategy breakdown."""
    safe_days = max(1, min(days, 90))
    user_id = current_user.get("user_id") if isinstance(current_user, dict) else getattr(current_user, "id", 1)
    data = get_user_rag_distribution(user_id, days=safe_days)
    return data


@app.get("/analytics/models")
def get_analytics_models(
    days: int = 7,
    current_user=Depends(get_current_user),
):
    """Retrieve per-model usage and latency metrics."""
    safe_days = max(1, min(days, 90))
    user_id = current_user.get("user_id") if isinstance(current_user, dict) else getattr(current_user, "id", 1)
    data = get_user_model_stats(user_id, days=safe_days)
    return {"models": data}


# ============================================================
# v1.2.0 USER FEEDBACK APIs
# ============================================================

@app.post("/feedback")
def submit_feedback(
    payload: FeedbackRequest,
    current_user=Depends(get_current_user),
):
    """Submit user feedback (thumbs up/down, reason, notes) for a message."""
    user_id = current_user.get("user_id") if isinstance(current_user, dict) else getattr(current_user, "id", 1)

    # Verify conversation ownership
    conv = get_conversation(payload.conversation_id, user_id)
    if not conv:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found or access denied.",
        )

    # Sanitize and validate inputs
    raw_rating = payload.rating
    if raw_rating in (1, "1", "helpful"):
        norm_rating = 1
    elif raw_rating in (-1, "-1", "unhelpful"):
        norm_rating = -1
    else:
        raise HTTPException(
            status_code=400,
            detail="Rating must be 1/helpful (positive) or -1/unhelpful (negative).",
        )

    valid_reasons = {
        "accurate", "fast", "helpful", "good_citations",
        "hallucination", "missing_info", "slow", "poor_citations",
        "incorrect_facts", "refused_answer", "other",
        "incorrect_answer", "missing_information", "poor_citation", "irrelevant_sources", "too_verbose"
    }
    chosen_reason = payload.feedback_reason or payload.reason
    if chosen_reason:
        clean_reason = str(chosen_reason).strip().lower()
        if clean_reason not in valid_reasons:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid feedback reason. Allowed: {', '.join(sorted(valid_reasons))}",
            )
        chosen_reason = clean_reason

    clean_text = payload.feedback_text or payload.note
    if clean_text:
        clean_text = str(clean_text).strip()[:1000]

    feedback_id = save_message_feedback(
        user_id=user_id,
        conversation_id=payload.conversation_id,
        rating=norm_rating,
        message_id=payload.message_id,
        feedback_reason=chosen_reason,
        feedback_text=clean_text,
        latency_perceived=payload.latency_perceived,
        request_id=payload.request_id,
    )

    if not feedback_id:
        raise HTTPException(
            status_code=400,
            detail="Failed to record feedback. Invalid message or foreign message reference.",
        )

    return {
        "status": "success",
        "feedback_id": feedback_id,
        "message": "Feedback recorded successfully",
    }


@app.get("/feedback/conversation/{conversation_id}")
def get_conversation_feedback_route(
    conversation_id: int,
    current_user=Depends(get_current_user),
):
    """Get all feedback submitted for a conversation."""
    user_id = current_user.get("user_id") if isinstance(current_user, dict) else getattr(current_user, "id", 1)

    # Verify conversation ownership
    conv = get_conversation(conversation_id, user_id)
    if not conv:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found or access denied.",
        )

    feedback_list = get_conversation_feedback(conversation_id, user_id)
    return {"feedback": feedback_list}


# ============================================================
# v1.2.0 CACHE MANAGEMENT APIs
# ============================================================

@app.post("/cache/clear")
def clear_cache_route(
    current_user=Depends(get_current_user),
):
    """Clear cached AI responses for the authenticated user."""
    user_id = current_user.get("user_id") if isinstance(current_user, dict) else getattr(current_user, "id", 1)
    cleared_count = clear_user_response_cache(user_id)
    return {
        "status": "success",
        "cleared_entries": cleared_count,
        "message": f"Successfully invalidated {cleared_count} cached response(s).",
    }
