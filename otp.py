import secrets
from datetime import datetime, timedelta, timezone


OTP_EXPIRY_MINUTES = 10


_otp_store = {}


def generate_otp(email: str) -> str:
    email = email.strip().lower()

    otp = f"{secrets.randbelow(1_000_000):06d}"

    _otp_store[email] = {
        "otp": otp,
        "expires_at": datetime.now(timezone.utc)
        + timedelta(minutes=OTP_EXPIRY_MINUTES),
    }

    return otp


def verify_otp(email: str, otp: str) -> bool:
    email = email.strip().lower()

    record = _otp_store.get(email)

    if not record:
        return False

    if datetime.now(timezone.utc) > record["expires_at"]:
        _otp_store.pop(email, None)
        return False

    if not secrets.compare_digest(record["otp"], otp.strip()):
        return False

    _otp_store.pop(email, None)

    return True


def clear_otp(email: str):
    email = email.strip().lower()
    _otp_store.pop(email, None)