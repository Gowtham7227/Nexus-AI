import os
from fastapi import APIRouter, HTTPException
from schemas.auth_schemas import (
    RegisterRequest,
    LoginRequest,
    ForgotPasswordRequest,
    ResendOTPRequest,
    VerifyOTPRequest,
    ResetPasswordRequest,
)
from dependencies.auth_deps import (
    check_login_rate_limit,
    record_failed_login_attempt,
    reset_login_attempts,
)
from auth import (
    create_user,
    authenticate_user,
    create_access_token,
    get_user_by_email,
    update_password,
)
from otp import (
    generate_or_resend_otp,
    validate_otp,
    consume_and_verify_otp,
    clear_otp,
)
from email_service import send_otp_email

router = APIRouter(tags=["auth"])


@router.post("/register")
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


@router.post("/login")
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


@router.post("/forgot-password")
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


@router.post("/resend-otp")
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


@router.post("/verify-otp")
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


@router.post("/reset-password")
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
