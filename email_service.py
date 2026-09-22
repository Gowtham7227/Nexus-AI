import os
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
dotenv_file = os.path.join(BASE_DIR, ".env")
if os.path.exists(dotenv_file):
    load_dotenv(dotenv_path=dotenv_file)
else:
    load_dotenv()

EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "gmail").strip().lower()

# SMTP Configuration (Gmail)
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip().replace(" ", "")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", f"NexusAI <{SMTP_USERNAME}>" if SMTP_USERNAME else "NexusAI <noreply@example.com>").strip()

# Resend Configuration (Fallback / Alternative)
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "NexusAI <onboarding@resend.dev>")

if RESEND_API_KEY:
    try:
        import resend
        resend.api_key = RESEND_API_KEY
    except ImportError:
        resend = None
else:
    resend = None


def _mask_email(email: str) -> str:
    if not email or "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    masked_local = local[0] + "***" if len(local) > 1 else "*"
    return f"{masked_local}@{domain}"


def _send_via_smtp(clean_email: str, otp: str) -> Dict[str, Any]:
    masked = _mask_email(clean_email)
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        print(f"⚠️ SMTP dispatch failed: SMTP_USERNAME or SMTP_PASSWORD is not configured in .env.")
        raise RuntimeError("SMTP email service is not configured. Please set SMTP_USERNAME and SMTP_PASSWORD (Google App Password).")

    try:
        print(f"📧 Sending OTP email to {masked} via Gmail SMTP ({SMTP_HOST}:{SMTP_PORT})...")

        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Your NexusAI Password Reset OTP"
        msg["From"] = SMTP_FROM_EMAIL
        msg["To"] = clean_email

        plain_text = f"Your NexusAI password reset OTP is: {otp}\nThis OTP is valid for 10 minutes.\nIf you did not request a password reset, you can safely ignore this email."
        html_content = f"""
        <div style="font-family: Arial, sans-serif; line-height: 1.6; max-width: 500px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 12px; background-color: #ffffff;">
            <h2 style="color: #1e3a8a; margin-top: 0;">NexusAI Password Reset</h2>
            <p style="color: #334155; font-size: 15px;">You requested a one-time passcode (OTP) to reset your NexusAI workspace password.</p>
            <div style="
                font-size: 32px;
                font-weight: bold;
                letter-spacing: 8px;
                color: #2563eb;
                background: #eff6ff;
                padding: 15px 20px;
                text-align: center;
                border-radius: 8px;
                margin: 25px 0;
                border: 1px solid #bfdbfe;
            ">
                {otp}
            </div>
            <p style="color: #64748b; font-size: 14px;">This OTP is valid for <strong>10 minutes</strong>.</p>
            <p style="color: #94a3b8; font-size: 12px; margin-top: 25px; border-top: 1px solid #f1f5f9; padding-top: 15px;">If you did not request a password reset, you can safely ignore this email.</p>
        </div>
        """

        part1 = MIMEText(plain_text, "plain", "utf-8")
        part2 = MIMEText(html_content, "html", "utf-8")
        msg.attach(part1)
        msg.attach(part2)

        if SMTP_PORT == 465:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=5) as server:
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.sendmail(SMTP_USERNAME, [clean_email], msg.as_string())
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=5) as server:
                server.starttls()
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.sendmail(SMTP_USERNAME, [clean_email], msg.as_string())

        print(f"✅ OTP email delivered successfully via Gmail SMTP to {masked}")
        return {"status": "success", "provider": "gmail_smtp", "recipient": masked}

    except smtplib.SMTPAuthenticationError as auth_err:
        print(f"❌ Gmail SMTP Authentication Error: {auth_err}")
        raise RuntimeError("Gmail SMTP Authentication failed. Please check your Google App Password.")
    except Exception as e:
        print(f"❌ Failed to deliver OTP email via SMTP to {masked}: {type(e).__name__} - {str(e)}")
        raise RuntimeError(f"Email delivery error: {str(e)}")


def _send_via_resend(clean_email: str, otp: str) -> Dict[str, Any]:
    masked = _mask_email(clean_email)
    if not RESEND_API_KEY or not resend:
        print(f"⚠️ Resend dispatch skipped: RESEND_API_KEY is not configured.")
        raise RuntimeError("Resend service is not configured. Please check RESEND_API_KEY.")

    try:
        print(f"📧 Sending OTP email to {masked} via Resend (From: {RESEND_FROM_EMAIL})...")
        response = resend.Emails.send(
            {
                "from": RESEND_FROM_EMAIL,
                "to": [clean_email],
                "subject": "Your NexusAI Password Reset OTP",
                "html": f"""
                    <div style="font-family: Arial, sans-serif; line-height: 1.6; max-width: 500px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 12px;">
                        <h2 style="color: #1e3a8a; margin-top: 0;">NexusAI Password Reset</h2>
                        <p>You requested a one-time passcode (OTP) to reset your NexusAI workspace password.</p>
                        <div style="
                            font-size: 32px;
                            font-weight: bold;
                            letter-spacing: 8px;
                            color: #2563eb;
                            background: #eff6ff;
                            padding: 15px 20px;
                            text-align: center;
                            border-radius: 8px;
                            margin: 25px 0;
                        ">
                            {otp}
                        </div>
                        <p style="color: #64748b; font-size: 14px;">This OTP is valid for 10 minutes.</p>
                        <p style="color: #94a3b8; font-size: 12px; margin-top: 25px; border-top: 1px solid #f1f5f9; padding-top: 15px;">If you did not request a password reset, you can safely ignore this email.</p>
                    </div>
                """,
            }
        )

        if isinstance(response, dict) and "error" in response and response["error"]:
            err_detail = response["error"].get("message", "Email provider rejected request")
            print(f"❌ Resend API returned error: {err_detail}")
            raise RuntimeError(f"Email delivery error: {err_detail}")

        email_id = response.get("id") if isinstance(response, dict) else getattr(response, "id", "success")
        print(f"✅ OTP email accepted by Resend for {masked} (Message ID: {email_id})")
        return response

    except Exception as e:
        print(f"❌ Failed to deliver OTP email to {masked}: {type(e).__name__} - {str(e)}")
        raise


def send_otp_email(email: str, otp: str) -> Dict[str, Any]:
    """
    Dispatches OTP email to the requested recipient using the configured provider.
    """
    clean_email = email.strip().lower()
    
    if EMAIL_PROVIDER == "resend":
        return _send_via_resend(clean_email, otp)
    else:
        return _send_via_smtp(clean_email, otp)

