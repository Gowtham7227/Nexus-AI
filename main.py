from retriever import retrieve_context
from chatbot import ask_gemini
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
)

import shutil
import os
import sqlite3
import time
import threading
import io
import zipfile

from utils import extract_text
from vector_store import create_vector_store


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="NexusAI Backend",
    description="AI Powered Document Intelligence Assistant",
    version="1.0.0",
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


# ============================================================
# UPLOAD FOLDER
# ============================================================

UPLOAD_FOLDER = "uploads"

# Maximum size for a single uploaded document.
MAX_UPLOAD_SIZE_BYTES = 15 * 1024 * 1024

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True,
)


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
        "message":
            "Welcome to NexusAI Backend 🚀",

        "status":
            "running",
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

        print("❌ Registration Error:", str(e))

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

from otp import generate_otp, verify_otp
from email_service import send_otp_email


OTP_MAX_FAILED_ATTEMPTS = 5
OTP_LOCKOUT_SECONDS = 10 * 60

_otp_attempts = {}
_otp_attempts_lock = threading.Lock()


def _otp_key(email: str) -> str:
    return email.strip().lower()


def reset_otp_attempts(email: str) -> None:
    key = _otp_key(email)
    with _otp_attempts_lock:
        _otp_attempts.pop(key, None)


def check_otp_rate_limit(email: str) -> None:
    key = _otp_key(email)
    now = time.time()

    with _otp_attempts_lock:
        record = _otp_attempts.get(key)

        if record is None:
            return

        failed_attempts, first_failed_at = record

        if now - first_failed_at >= OTP_LOCKOUT_SECONDS:
            _otp_attempts.pop(key, None)
            return

        if failed_attempts >= OTP_MAX_FAILED_ATTEMPTS:
            raise HTTPException(
                status_code=429,
                detail="Too many invalid OTP attempts. Please request a new OTP and try again later.",
            )


def record_failed_otp_attempt(email: str) -> None:
    key = _otp_key(email)
    now = time.time()

    with _otp_attempts_lock:
        record = _otp_attempts.get(key)

        if record is None or now - record[1] >= OTP_LOCKOUT_SECONDS:
            _otp_attempts[key] = (1, now)
        else:
            _otp_attempts[key] = (record[0] + 1, record[1])


class ForgotPasswordRequest(BaseModel):
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

    # Do not reveal whether an account exists.
    if user is not None:
        otp = generate_otp(email)
        reset_otp_attempts(email)

        try:
            send_otp_email(email, otp)
        except Exception as e:
            if isinstance(e, HTTPException):
                print("❌ OTP Email Error:", str(e))
            else:
                print("❌ OTP Email Error:", str(e))

            # Do not reveal whether the email belongs to an account.
            # Return the same generic response as the non-existent-account case.

    return {
        "message": "If an account exists for this email, an OTP has been sent."
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

    check_otp_rate_limit(email)

    if not verify_otp(email, otp):
        record_failed_otp_attempt(email)
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired OTP.",
        )

    reset_otp_attempts(email)

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

    check_otp_rate_limit(email)

    if not verify_otp(email, otp):
        record_failed_otp_attempt(email)
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired OTP.",
        )

    reset_otp_attempts(email)

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


def validate_uploaded_content(filename: str, content: bytes) -> None:
    """Validate that uploaded bytes match the declared supported document type."""
    extension = os.path.splitext(filename)[1].lower()

    if extension == ".txt":
        return

    if extension == ".pdf":
        if not content.startswith(b"%PDF-"):
            raise HTTPException(
                status_code=415,
                detail="Invalid PDF file content.",
            )
        return

    if extension in {".docx", ".pptx", ".xlsx"}:
        if not zipfile.is_zipfile(io.BytesIO(content)):
            raise HTTPException(
                status_code=415,
                detail=f"Invalid {extension[1:].upper()} file content.",
            )
        return

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
    """Return a document path guaranteed to remain inside UPLOAD_FOLDER."""
    safe_filename = validate_upload_filename(filename)
    upload_root = os.path.abspath(UPLOAD_FOLDER)
    file_path = os.path.abspath(os.path.join(upload_root, safe_filename))

    if os.path.commonpath([upload_root, file_path]) != upload_root:
        raise HTTPException(status_code=400, detail="Invalid document path.")

    return file_path


# ============================================================
# UPLOAD DOCUMENT
# ============================================================

@app.post("/upload")
def upload_file(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
):

    try:

        # ----------------------------------------------------
        # Save uploaded file
        # ----------------------------------------------------

        original_filename = file.filename or ""
        safe_filename = validate_upload_filename(
            original_filename
        )
        file_path = get_safe_document_path(
            safe_filename
        )

        # Read at most the configured maximum into memory so size and content
        # validation happen before anything is written to disk.
        uploaded_content = file.file.read(MAX_UPLOAD_SIZE_BYTES + 1)
        if len(uploaded_content) > MAX_UPLOAD_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail="File too large. Maximum allowed upload size is 15 MB.",
            )

        validate_uploaded_content(
            safe_filename,
            uploaded_content,
        )

        # The current vector store is keyed by filename. Do not allow two
        # different users to use the same filename and collide physically.
        conn = sqlite3.connect("auth.db")
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
        # Save validated upload content
        # ----------------------------------------------------

        # The content was already read above for size and signature validation.
        # Write those exact validated bytes instead of reading file.file again,
        # because the upload stream is now at EOF.
        with open(
            file_path,
            "wb",
        ) as buffer:
            buffer.write(uploaded_content)

        # ----------------------------------------------------
        # Save document ownership
        # ----------------------------------------------------

        conn = sqlite3.connect("auth.db")

        existing = conn.execute(
            """
            SELECT id
            FROM documents
            WHERE user_id = ? AND filename = ?
            LIMIT 1
            """,
            (
                current_user["user_id"],
                safe_filename,
            ),
        ).fetchone()

        if existing is None:
            conn.execute(
                """
                INSERT INTO documents (
                    user_id,
                    filename,
                    created_at
                )
                VALUES (?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    current_user["user_id"],
                    safe_filename,
                ),
            )
        else:
            conn.execute(
                """
                UPDATE documents
                SET created_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (existing[0],),
            )

        conn.commit()
        conn.close()


        # ----------------------------------------------------
        # Extract text
        # ----------------------------------------------------

        extracted_text = extract_text(
            file_path
        )


        print("=" * 70)

        print(
            "📄 DOCUMENT UPLOADED:",
            safe_filename,
        )

        print(
            "📦 FILE SIZE:",
            round(
                os.path.getsize(
                    file_path
                ) / (1024 * 1024),
                2,
            ),
            "MB",
        )

        print(
            "📝 EXTRACTED TEXT LENGTH:",
            len(extracted_text),
        )

        print("=" * 70)


        # ----------------------------------------------------
        # Create vector store
        # ----------------------------------------------------

        if extracted_text.strip():

            try:

                create_vector_store(
                    extracted_text,
                    safe_filename,
                )


                print(
                    "✅ ChromaDB created successfully"
                )


            except Exception as e:


                if isinstance(e, HTTPException):


                    raise
                print(
                    "❌ Vector Store Error:",
                    str(e),
                )


                return {
                    "message":
                        "File uploaded, but document processing failed.",

                    "filename":
                        safe_filename,
                }


        else:

            print(
                "⚠️ No text extracted from document"
            )


            return {
                "message":
                    "File uploaded, but no readable text was found.",

                "filename":
                    safe_filename,
            }


        # ----------------------------------------------------
        # Success
        # ----------------------------------------------------

        return {

            "message":
                "File uploaded successfully",

            "filename":
                safe_filename,

            "text":
                extracted_text[:1000],
        }


    except Exception as e:


        if isinstance(e, HTTPException):


            raise
        print(
            "❌ Upload Error:",
            str(e),
        )


        return {

            "message":
                "File upload failed.",
        }


# ============================================================
# CHAT REQUEST MODEL
# ============================================================

class ChatRequest(BaseModel):

    question: str

    # New format
    filenames: list[str] | None = None

    # Old format - backward compatibility
    filename: str | None = None


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
        "🔎 MULTI-DOCUMENT RETRIEVAL"
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
                f"🔍 Retrieving document {index}/{len(filenames)}:"
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
                    f"✅ Context retrieved from: {filename}"
                )

                print(
                    "Context length:",
                    len(context),
                )


            else:

                print(
                    f"⚠️ No relevant context found in: {filename}"
                )


        except Exception as e:


            if isinstance(e, HTTPException):


                raise
            print(
                f"❌ Retrieval failed for {filename}:",
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
        "📚 COMBINED CONTEXT LENGTH:",
        len(combined_context),
    )

    print(
        "📄 DOCUMENT COUNT:",
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

        print("📝 Extracted text length:", len(extracted_text))

        answer = explain_document(extracted_text, filename)

        print("=" * 70)
        print("🤖 DOCUMENT EXPLANATION")
        print(answer)
        print("=" * 70)

        return {
            "question": request.question,
            "filename": filename,
            "mode": "cloud",
            "answer": answer,
        }

    except Exception as e:

        if isinstance(e, HTTPException):

            raise
        print("❌ Document Summary Error:", str(e))
        return {"error": "Document summary failed."}


# ============================================================
# CLOUD AI - GEMINI
# ============================================================

@app.post("/chat")
def chat(
    request: ChatRequest,
    current_user=Depends(get_current_user),
):

    try:

        filenames = (
            get_selected_filenames(
                request
            )
        )


        # ----------------------------------------------------
        # Validate documents
        # ----------------------------------------------------

        if not filenames:

            return {

                "question":
                    request.question,

                "mode":
                    "cloud",

                "answer":
                    "📄 Please select at least one document.",
            }


        filenames = validate_user_documents(
            filenames,
            current_user["user_id"],
        )


        print("=" * 70)

        print(
            "☁️ CLOUD CHAT REQUEST"
        )

        print(
            "Question:",
            request.question,
        )

        print(
            "Documents:",
            filenames,
        )

        print("=" * 70)


        # ----------------------------------------------------
        # Retrieve context
        # ----------------------------------------------------

        context = (
            retrieve_multi_document_context(
                request.question,
                filenames,
            )
        )


        if not context.strip():

            return {

                "question":
                    request.question,

                "filenames":
                    filenames,

                "mode":
                    "cloud",

                "answer":
                    "I couldn't find relevant information in the selected document(s).",
            }


        # ----------------------------------------------------
        # Generate Gemini answer
        # ----------------------------------------------------

        answer = ask_gemini(
            context,
            request.question,
        )


        print("=" * 70)

        print(
            "🤖 GEMINI ANSWER"
        )

        print(
            answer
        )

        print("=" * 70)


        return {

            "question":
                request.question,

            "filenames":
                filenames,

            "mode":
                "cloud",

            "answer":
                answer,
        }


    except Exception as e:


        if isinstance(e, HTTPException):


            raise
        print(
            "❌ Cloud Chat Error:",
            str(e),
        )


        return {

            "error":
                "Cloud chat failed.",
        }


# ============================================================
# LOCAL AI - QWEN NORMAL RESPONSE
# ============================================================

@app.post("/local-chat-normal")
def local_chat_normal(
    request: ChatRequest,
    current_user=Depends(get_current_user),
):

    try:

        filenames = (
            get_selected_filenames(
                request
            )
        )


        # ----------------------------------------------------
        # Validate
        # ----------------------------------------------------

        if not filenames:

            return {

                "question":
                    request.question,

                "mode":
                    "local",

                "answer":
                    "📄 Please select at least one document.",
            }


        filenames = validate_user_documents(
            filenames,
            current_user["user_id"],
        )


        print("=" * 70)

        print(
            "🖥️ LOCAL QWEN CHAT REQUEST"
        )

        print(
            "Question:",
            request.question,
        )

        print(
            "Documents:",
            filenames,
        )

        print("=" * 70)


        # ----------------------------------------------------
        # Retrieve context
        # ----------------------------------------------------

        context = (
            retrieve_multi_document_context(
                request.question,
                filenames,
            )
        )


        if not context.strip():

            return {

                "question":
                    request.question,

                "filenames":
                    filenames,

                "mode":
                    "local",

                "answer":
                    "I couldn't find relevant information in the selected document(s).",
            }


        # ----------------------------------------------------
        # Generate Qwen answer
        # ----------------------------------------------------

        answer = ask_local(
            context,
            request.question,
        )


        print("=" * 70)

        print(
            "🤖 LOCAL QWEN ANSWER"
        )

        print(
            answer
        )

        print("=" * 70)


        return {

            "question":
                request.question,

            "filenames":
                filenames,

            "mode":
                "local",

            "answer":
                answer,
        }


    except Exception as e:


        if isinstance(e, HTTPException):


            raise
        print(
            "❌ Local Chat Error:",
            str(e),
        )


        return {

            "error":
                "Local chat failed.",
        }


# ============================================================
# LOCAL AI - STREAMING QWEN
# ============================================================

@app.post("/local-chat")
def local_chat(
    request: ChatRequest,
    current_user=Depends(get_current_user),
):

    try:

        filenames = (
            get_selected_filenames(
                request
            )
        )


        # ----------------------------------------------------
        # Validate
        # ----------------------------------------------------

        if not filenames:

            return StreamingResponse(

                iter([
                    "📄 Please select at least one document."
                ]),

                media_type=
                    "text/plain; charset=utf-8",
            )


        filenames = validate_user_documents(
            filenames,
            current_user["user_id"],
        )


        print("=" * 70)

        print(
            "🖥️ LOCAL STREAMING QWEN REQUEST"
        )

        print(
            "Question:",
            request.question,
        )

        print(
            "Documents:",
            filenames,
        )

        print("=" * 70)


        # ----------------------------------------------------
        # Retrieve context
        # ----------------------------------------------------

        context = (
            retrieve_multi_document_context(
                request.question,
                filenames,
            )
        )


        if not context.strip():

            return StreamingResponse(

                iter([
                    "I couldn't find relevant information in the selected document(s)."
                ]),

                media_type=
                    "text/plain; charset=utf-8",
            )


        # ----------------------------------------------------
        # Stream Qwen response
        # ----------------------------------------------------

        return StreamingResponse(

            stream_local(
                context,
                request.question,
            ),

            media_type=
                "text/plain; charset=utf-8",

            headers={

                "Cache-Control":
                    "no-cache",

                "X-Accel-Buffering":
                    "no",

                "Connection":
                    "keep-alive",
            },
        )


    except Exception as e:


        if isinstance(e, HTTPException):


            raise
        print(
            "❌ Local Streaming Chat Error:",
            str(e),
        )


        return StreamingResponse(

            iter([
                "❌ Local AI request failed."
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
            "🔥 LOCAL AI WARM-UP REQUEST"
        )

        print("=" * 70)


        result = warmup_local_model()


        return result


    except Exception as e:


        if isinstance(e, HTTPException):


            raise
        print(
            "❌ Local Warm-up Error:",
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
    conn = sqlite3.connect("auth.db")
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

    conn = sqlite3.connect("auth.db")
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
        conn = sqlite3.connect("auth.db")
        rows = conn.execute(
            """
            SELECT filename
            FROM documents
            WHERE user_id = ?
            ORDER BY filename COLLATE NOCASE
            """,
            (current_user["user_id"],),
        ).fetchall()
        conn.close()

        files = []

        for (filename,) in rows:
            file_path = get_safe_document_path(
                filename
            )

            if os.path.isfile(file_path):
                files.append({
                    "filename": filename,
                    "size": os.path.getsize(file_path),
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

        conn = sqlite3.connect("auth.db")
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
            "🗑️ Document deleted:",
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


