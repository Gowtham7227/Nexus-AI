import os

import resend
from dotenv import load_dotenv


load_dotenv()

RESEND_API_KEY = os.getenv("RESEND_API_KEY")

if not RESEND_API_KEY:
    raise RuntimeError("RESEND_API_KEY is not configured.")

resend.api_key = RESEND_API_KEY


FROM_EMAIL = "NexusAI <onboarding@resend.dev>"


def send_otp_email(email: str, otp: str):
    response = resend.Emails.send(
        {
            "from": FROM_EMAIL,
            "to": [email],
            "subject": "Your NexusAI Password Reset OTP",
            "html": f"""
                <div style="font-family: Arial, sans-serif; line-height: 1.6;">
                    <h2>NexusAI Password Reset</h2>
                    <p>Use the following OTP to reset your NexusAI password:</p>

                    <div style="
                        font-size: 32px;
                        font-weight: bold;
                        letter-spacing: 8px;
                        margin: 20px 0;
                    ">
                        {otp}
                    </div>

                    <p>This OTP is valid for 10 minutes.</p>
                    <p>If you did not request a password reset, you can safely ignore this email.</p>
                </div>
            """,
        }
    )

    return response
