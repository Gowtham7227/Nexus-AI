import time
import threading
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from auth import decode_access_token

security = HTTPBearer()

LOGIN_MAX_FAILED_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 10 * 60

_login_attempts: dict[str, tuple[int, float]] = {}
_login_attempts_lock = threading.Lock()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    token = credentials.credentials
    user = decode_access_token(token)

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token.",
        )

    return user


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
