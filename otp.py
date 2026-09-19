import os
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from fastapi import HTTPException

OTP_EXPIRY_MINUTES = 10
RESEND_COOLDOWN_SECONDS = 30
MAX_FAILED_VERIFICATIONS = 5

_otp_lock = threading.Lock()
_otp_store = {}


def _clean_email(email: str) -> str:
    return email.strip().lower() if email else ""


def get_resend_cooldown_remaining(email: str) -> int:
    """Return remaining cooldown seconds before a new OTP can be requested."""
    clean = _clean_email(email)
    if not clean:
        return 0

    with _otp_lock:
        record = _otp_store.get(clean)
        if not record:
            return 0
        last_sent = record.get("last_sent_at", 0)
        elapsed = time.time() - last_sent
        remaining = int(RESEND_COOLDOWN_SECONDS - elapsed)
        return max(0, remaining)


def generate_or_resend_otp(email: str, is_resend: bool = False) -> str:
    """
    Generate a fresh 6-digit OTP for the given email with cooldown enforcement.
    Invalidates any previous OTP for this email.
    """
    clean = _clean_email(email)
    if not clean:
        raise HTTPException(status_code=400, detail="Email is required.")

    now_ts = time.time()
    now_dt = datetime.now(timezone.utc)

    with _otp_lock:
        record = _otp_store.get(clean)
        if record:
            last_sent = record.get("last_sent_at", 0)
            elapsed = now_ts - last_sent
            if elapsed < RESEND_COOLDOWN_SECONDS:
                remaining = int(RESEND_COOLDOWN_SECONDS - elapsed)
                raise HTTPException(
                    status_code=429,
                    detail=f"Please wait {remaining} seconds before requesting another OTP.",
                )

        # Generate fresh cryptographically secure 6-digit numeric OTP
        otp_code = f"{secrets.randbelow(1_000_000):06d}"

        _otp_store[clean] = {
            "otp": otp_code,
            "created_at": now_ts,
            "last_sent_at": now_ts,
            "expires_at": now_dt + timedelta(minutes=OTP_EXPIRY_MINUTES),
            "failed_attempts": 0,
            "verified": False,
        }

    return otp_code


def validate_otp(email: str, otp: str) -> bool:
    """
    Validate OTP without deleting it (used by intermediate validation endpoints).
    Enforces expiration, attempt limits, and constant-time string comparison.
    """
    clean = _clean_email(email)
    otp_clean = otp.strip() if otp else ""

    if not clean or not otp_clean:
        return False

    with _otp_lock:
        record = _otp_store.get(clean)
        if not record:
            return False

        # Expiration check
        if datetime.now(timezone.utc) > record["expires_at"]:
            _otp_store.pop(clean, None)
            return False

        # Attempt rate limit check
        if record["failed_attempts"] >= MAX_FAILED_VERIFICATIONS:
            _otp_store.pop(clean, None)
            raise HTTPException(
                status_code=429,
                detail="Too many failed OTP attempts. Please request a new OTP.",
            )

        # Constant-time comparison
        is_valid = secrets.compare_digest(record["otp"], otp_clean)
        if not is_valid:
            record["failed_attempts"] += 1
            return False

        record["verified"] = True
        return True


def consume_and_verify_otp(email: str, otp: str) -> bool:
    """
    Validate and permanently consume (delete) the OTP during password reset.
    """
    clean = _clean_email(email)
    otp_clean = otp.strip() if otp else ""

    if not clean or not otp_clean:
        return False

    with _otp_lock:
        record = _otp_store.get(clean)
        if not record:
            return False

        if datetime.now(timezone.utc) > record["expires_at"]:
            _otp_store.pop(clean, None)
            return False

        if record["failed_attempts"] >= MAX_FAILED_VERIFICATIONS:
            _otp_store.pop(clean, None)
            raise HTTPException(
                status_code=429,
                detail="Too many failed OTP attempts. Please request a new OTP.",
            )

        is_valid = secrets.compare_digest(record["otp"], otp_clean)
        if not is_valid:
            record["failed_attempts"] += 1
            return False

        # Consume / delete the OTP
        _otp_store.pop(clean, None)
        return True


def clear_otp(email: str) -> None:
    """Clear OTP state for an email."""
    clean = _clean_email(email)
    if clean:
        with _otp_lock:
            _otp_store.pop(clean, None)