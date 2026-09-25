import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Directories & Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "100"))
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

print("=" * 70)
print("🚀 NexusAI Backend Starting (Modular Architecture)...")
print("📂 Base Directory :", BASE_DIR)
print("📂 Upload Folder  :", UPLOAD_FOLDER)
print(f"📦 Max Upload Size: {MAX_UPLOAD_SIZE_MB} MB ({MAX_UPLOAD_SIZE_BYTES} bytes)")
print("=" * 70)

# Initialize FastAPI App
app = FastAPI(
    title="NexusAI Backend",
    description="AI Powered Document Intelligence Assistant",
    version="1.4.0",
)

# CORS Configuration
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

# Import and Register APIRouters
from routers import (
    system_router,
    auth_router,
    document_router,
    conversation_router,
    chat_router,
    rag_router,
    analytics_router,
    feedback_router,
    cache_router,
)

app.include_router(system_router)
app.include_router(auth_router)
app.include_router(document_router)
app.include_router(conversation_router)
app.include_router(chat_router)
app.include_router(rag_router)
app.include_router(analytics_router)
app.include_router(feedback_router)
app.include_router(cache_router)

# Backward-Compatibility Exports
from dependencies.auth_deps import get_current_user, security
from schemas import (
    RegisterRequest,
    LoginRequest,
    ForgotPasswordRequest,
    ResendOTPRequest,
    VerifyOTPRequest,
    ResetPasswordRequest,
    CreateConversationRequest,
    UpdateConversationRequest,
    ChatRequest,
    FeedbackRequest,
)
from services.document_service import (
    validate_uploaded_content,
    validate_upload_filename,
    get_safe_document_path,
    process_document_indexing_background,
    document_belongs_to_user,
    get_owned_filenames,
    validate_user_documents,
)
from services.chat_service import (
    get_selected_filenames,
    retrieve_multi_document_context,
    resolve_or_create_conversation,
)
