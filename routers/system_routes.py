import os
import zipfile
from fastapi import APIRouter

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "100"))

router = APIRouter(tags=["system"])


@router.get("/")
def home():
    return {
        "message": "Welcome to NexusAI Backend 🚀",
        "status": "running",
    }


@router.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "NexusAI Backend",
        "max_upload_size_mb": MAX_UPLOAD_SIZE_MB,
        "active_gemini_model": os.getenv("GEMINI_MODEL", "gemini-3.6-flash"),
        "base_dir": BASE_DIR,
    }


@router.get("/api/test-gemini")
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


@router.get("/api/run-comprehensive-audit")
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


@router.get("/api/package-project")
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
