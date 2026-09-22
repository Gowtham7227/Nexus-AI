"""
NexusAI Comprehensive Security & Functionality Audit Suite (25 Checkpoints)
===========================================================================
Checkpoints:
 1. Health endpoint (/)
 2. User registration (/register)
 3. User login (/login)
 4. Wrong password rejected (401)
 5. Missing JWT rejected on protected endpoints (401)
 6. Invalid JWT rejected (401)
 7. Tampered JWT rejected (401)
 8. alg:none JWT attack rejected (401)
 9. Expired JWT token rejected (401)
 10. Authenticated document upload (200)
 11. Unauthenticated document upload rejected (401)
 12. Path traversal filename rejected (400/415)
 13. Encoded path traversal blocked (%2e%2e)
 14. Fake PDF file signature rejected (415)
 15. Invalid executable file rejected (415)
 16. Oversized upload rejected (413 with clear error)
 17. Document ownership & metadata stored in DB
 18. Unauthorized cross-user document access blocked (403/404)
 19. Cross-user document deletion blocked (403/404)
 20. CORS trusted origin permitted (http://localhost:5173)
 21. CORS untrusted origin rejected
 22. Unsupported HTTP method rejected (405)
 23. Weak password rejected during registration (400)
 24. OTP abuse & rate limiting enforced (429)
 25. Error responses hide internal tracebacks/secrets
"""

import base64
import json
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from jose import jwt
import requests

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE = os.getenv("NEXUS_BASE_URL", "http://127.0.0.1:8001").rstrip("/")
TIMEOUT = 20
results = []
session = requests.Session()


def req(method, path, **kwargs):
    kwargs.setdefault("timeout", TIMEOUT)
    return session.request(method, BASE + path, **kwargs)


def record(name, ok, detail=""):
    results.append((name, ok, detail))
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}" + (f" - {detail}" if detail else ""))


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def main():
    print("=" * 75)
    print("      NEXUSAI 25-CHECKPOINT SECURITY & FUNCTIONALITY AUDIT SUITE")
    print("Target Backend:", BASE)
    print("=" * 75)

    # 1. Health endpoint
    r = req("GET", "/")
    record(
        "1. Health endpoint (/) -> 200",
        r.status_code == 200 and "NexusAI" in r.text,
        f"HTTP {r.status_code}",
    )

    # Setup Test Users
    uid_a = uuid.uuid4().hex[:8]
    email_a = f"user_a_{uid_a}@nexusai.test"
    pass_a = "StrongPass123!"

    uid_b = uuid.uuid4().hex[:8]
    email_b = f"user_b_{uid_b}@nexusai.test"
    pass_b = "StrongPass456!"

    # 2. Registration
    r_reg = req("POST", "/register", json={"email": email_a, "password": pass_a})
    token_a = r_reg.json().get("token") if r_reg.status_code == 200 else None
    record(
        "2. User registration (/register) -> 200",
        r_reg.status_code == 200 and bool(token_a),
        f"HTTP {r_reg.status_code}",
    )

    # Register User B for cross-tenant isolation testing
    r_reg_b = req("POST", "/register", json={"email": email_b, "password": pass_b})
    token_b = r_reg_b.json().get("token") if r_reg_b.status_code == 200 else None

    # 3. Login
    r_login = req("POST", "/login", json={"email": email_a, "password": pass_a})
    token = r_login.json().get("token") if r_login.status_code == 200 else token_a
    record(
        "3. User login (/login) -> 200",
        r_login.status_code == 200 and bool(token),
        f"HTTP {r_login.status_code}",
    )

    if not token:
        print("❌ Cannot proceed with security audit: Login/Register failed.")
        return summary()

    # 4. Wrong password
    r_wrong = req("POST", "/login", json={"email": email_a, "password": "WrongPassword999!"})
    record(
        "4. Wrong password rejected -> 401",
        r_wrong.status_code == 401,
        f"HTTP {r_wrong.status_code}",
    )

    # 5. Missing JWT
    r_no_jwt = req("GET", "/documents")
    record(
        "5. Missing JWT rejected on protected route -> 401",
        r_no_jwt.status_code == 401,
        f"HTTP {r_no_jwt.status_code}",
    )

    # 6. Invalid JWT
    r_bad_jwt = req("GET", "/documents", headers=auth_header("invalid.jwt.token"))
    record(
        "6. Invalid JWT token rejected -> 401",
        r_bad_jwt.status_code == 401,
        f"HTTP {r_bad_jwt.status_code}",
    )

    # 7. Tampered JWT
    parts = token.split(".")
    if len(parts) == 3:
        try:
            pad = "=" * (-len(parts[1]) % 4)
            payload_data = json.loads(base64.urlsafe_b64decode(parts[1] + pad))
            payload_data["sub"] = "999999"
            fake_payload = base64.urlsafe_b64encode(json.dumps(payload_data).encode()).decode().rstrip("=")
            r_tamper = req("GET", "/documents", headers=auth_header(f"{parts[0]}.{fake_payload}.{parts[2]}"))
            record(
                "7. Tampered JWT payload rejected -> 401",
                r_tamper.status_code == 401,
                f"HTTP {r_tamper.status_code}",
            )
        except Exception as e:
            record("7. Tampered JWT payload rejected -> 401", False, str(e))
    else:
        record("7. Tampered JWT payload rejected -> 401", False, "Invalid token format")

    # 8. alg:none JWT attack
    fake_header = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).decode().rstrip("=")
    r_none = req("GET", "/documents", headers=auth_header(f"{fake_header}.{parts[1]}."))
    record(
        "8. alg:none JWT attack rejected -> 401",
        r_none.status_code == 401,
        f"HTTP {r_none.status_code}",
    )

    # 9. Expired JWT
    try:
        secret = os.getenv("JWT_SECRET_KEY", "nexus_ai_secure_super_secret_key_change_in_production_2026!")
        expired_payload = {
            "sub": "1",
            "email": email_a,
            "exp": datetime.now(timezone.utc) - timedelta(hours=2),
        }
        expired_jwt = jwt.encode(expired_payload, secret, algorithm="HS256")
        r_exp = req("GET", "/documents", headers=auth_header(expired_jwt))
        record(
            "9. Expired JWT token rejected -> 401",
            r_exp.status_code == 401,
            f"HTTP {r_exp.status_code}",
        )
    except Exception as exc:
        record("9. Expired JWT token rejected -> 401", False, str(exc))

    # 10. Authenticated document upload
    doc_a = f"test_doc_a_{uuid.uuid4().hex[:6]}.txt"
    doc_a_content = (
        "NexusAI Document Content\n"
        "Project: NexusAI\n"
        "Secret Code: 4729\n"
    ).encode("utf-8")
    r_up = req("POST", "/upload", headers=auth_header(token), files={"file": (doc_a, doc_a_content, "text/plain")})
    record(
        "10. Authenticated document upload -> 200",
        r_up.status_code == 200,
        f"HTTP {r_up.status_code}",
    )

    # 11. Unauthenticated document upload
    r_unauth_up = req("POST", "/upload", files={"file": ("unauth.txt", b"secret", "text/plain")})
    record(
        "11. Unauthenticated upload rejected -> 401",
        r_unauth_up.status_code == 401,
        f"HTTP {r_unauth_up.status_code}",
    )

    # 12. Path traversal upload
    r_trav = req("POST", "/upload", headers=auth_header(token), files={"file": ("../../escape.txt", b"escape", "text/plain")})
    record(
        "12. Path traversal upload rejected -> 400/415",
        r_trav.status_code in (400, 415),
        f"HTTP {r_trav.status_code}",
    )

    # 13. Encoded path traversal in access
    r_enc = req("GET", "/documents/%2e%2e%2fauth.db/file", headers=auth_header(token))
    record(
        "13. Encoded path traversal blocked",
        r_enc.status_code != 200,
        f"HTTP {r_enc.status_code}",
    )

    # 14. Fake PDF file signature
    r_fake_pdf = req("POST", "/upload", headers=auth_header(token), files={"file": ("fake.pdf", b"NOT-A-REAL-PDF", "application/pdf")})
    record(
        "14. Fake PDF signature rejected -> 415",
        r_fake_pdf.status_code == 415,
        f"HTTP {r_fake_pdf.status_code}",
    )

    # 15. Invalid executable upload
    r_exe = req("POST", "/upload", headers=auth_header(token), files={"file": ("program.exe", b"MZexecutable", "application/octet-stream")})
    record(
        "15. Invalid executable upload rejected -> 415",
        r_exe.status_code == 415,
        f"HTTP {r_exe.status_code}",
    )

    # 16. Upload size limit enforcement (100 MB limit and oversized 413 rejection)
    # 16a: Valid large file (within 100 MB limit) -> 200
    valid_large_name = f"valid_large_{uuid.uuid4().hex[:6]}.txt"
    valid_large_content = ("NexusAI Document Content.\n" * 10000).encode("utf-8")
    r_valid_large = req("POST", "/upload", headers=auth_header(token), files={"file": (valid_large_name, valid_large_content, "text/plain")})
    
    # 16b: Oversized file exceeding 100 MB limit -> 413
    oversized_bytes = b"0" * (100 * 1024 * 1024 + 1024)
    r_oversized = req("POST", "/upload", headers=auth_header(token), files={"file": ("oversized_100mb.txt", oversized_bytes, "text/plain")}, timeout=60)
    has_100mb_msg = "100" in r_oversized.text or "too large" in r_oversized.text.lower()
    
    record(
        "16. Upload size limit (100 MB) enforced -> 413 on oversize & 200 on valid",
        r_valid_large.status_code == 200 and r_oversized.status_code == 413 and has_100mb_msg,
        f"Valid HTTP {r_valid_large.status_code}, Oversize HTTP {r_oversized.status_code}",
    )

    # 17. Document ownership & metadata stored in DB
    r_docs = req("GET", "/documents", headers=auth_header(token))
    doc_list = r_docs.json().get("documents", []) if r_docs.status_code == 200 else []
    found_doc = any(d.get("filename") == doc_a for d in doc_list)
    record(
        "17. Document metadata stored in DB & listed -> 200",
        r_docs.status_code == 200 and found_doc,
        f"Found doc_a in list: {found_doc}",
    )

    # 18. Unauthorized cross-user document access
    if token_b:
        r_cross = req("GET", f"/documents/{doc_a}/file", headers=auth_header(token_b))
        record(
            "18. Cross-user document read blocked -> 403/404",
            r_cross.status_code in (403, 404),
            f"HTTP {r_cross.status_code}",
        )
    else:
        record("18. Cross-user document read blocked", False, "User B token missing")

    # 19. Cross-user document deletion
    if token_b:
        r_cross_del = req("DELETE", f"/documents/{doc_a}", headers=auth_header(token_b))
        record(
            "19. Cross-user document delete blocked -> 403/404",
            r_cross_del.status_code in (403, 404),
            f"HTTP {r_cross_del.status_code}",
        )
    else:
        record("19. Cross-user document delete blocked", False, "User B token missing")

    # 20. CORS trusted origin
    r_cors_ok = req("OPTIONS", "/documents", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    allowed_cors = r_cors_ok.status_code == 200 and r_cors_ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    record(
        "20. CORS trusted origin permitted",
        allowed_cors,
        f"HTTP {r_cors_ok.status_code}",
    )

    # 21. CORS untrusted origin
    r_cors_bad = req("OPTIONS", "/documents", headers={"Origin": "http://malicious-site.example", "Access-Control-Request-Method": "GET"})
    blocked_cors = r_cors_bad.headers.get("access-control-allow-origin") != "http://malicious-site.example"
    record(
        "21. CORS untrusted origin rejected",
        blocked_cors,
        f"HTTP {r_cors_bad.status_code}",
    )

    # 22. Unsupported HTTP method
    r_method = req("POST", "/documents", headers=auth_header(token))
    record(
        "22. Unsupported HTTP method rejected -> 405",
        r_method.status_code == 405,
        f"HTTP {r_method.status_code}",
    )

    # 23. Weak password rejected
    r_weak = req("POST", "/register", json={"email": f"weak_{uuid.uuid4().hex[:6]}@nexusai.test", "password": "123"})
    record(
        "23. Weak password rejected during registration -> 400",
        r_weak.status_code == 400,
        f"HTTP {r_weak.status_code}",
    )

    # 24. OTP abuse & rate limiting
    otp_email = f"otp_{uuid.uuid4().hex[:6]}@nexusai.test"
    req("POST", "/register", json={"email": otp_email, "password": "StrongPassword123!"})
    req("POST", "/forgot-password", json={"email": otp_email})
    rate_limited = False
    for _ in range(7):
        r_otp = req("POST", "/verify-otp", json={"email": otp_email, "otp": "000000"})
        if r_otp.status_code == 429:
            rate_limited = True
            break
    record(
        "24. OTP abuse & rate limiting enforced -> 429",
        rate_limited,
        f"Last HTTP {r_otp.status_code}",
    )

    # 25. Error responses hide internal tracebacks/secrets
    bad_patterns = ["traceback (most recent call last)", "sqlite3.operationalerror", "sqlalchemy", "filenotfounderror:"]
    r_err = req("POST", "/chat", headers=auth_header(token), json={"question": "test", "filenames": ["ghost_doc.txt"]})
    clean_err = not any(p in r_err.text.lower() for p in bad_patterns)
    record(
        "25. Error responses hide internal tracebacks & secrets",
        clean_err,
        f"HTTP {r_err.status_code}",
    )

    # Cleanup test document
    try:
        req("DELETE", f"/documents/{doc_a}", headers=auth_header(token))
    except Exception:
        pass

    return summary()


def summary():
    passed = sum(1 for _, ok, _ in results if ok)
    failed = len(results) - passed
    print("\n" + "=" * 75)
    print(f"AUDIT SUMMARY: Total {len(results)} | Passed: {passed} | Failed: {failed}")
    if failed:
        print("\nFAILED CHECKS:")
        for name, ok, detail in results:
            if not ok:
                print(f" ❌ {name} ({detail})")
    print("=" * 75)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
