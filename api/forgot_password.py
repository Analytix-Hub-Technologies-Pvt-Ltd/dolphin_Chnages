from fastapi_mail.fastmail import email_dispatched
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema
from fastapi import APIRouter, Depends, HTTPException, Response, Request
from models.user_models import ForgotPasswordRequest, ForgotPasswordResponse
import httpx
from config import settings
from loguru import logger

router = APIRouter()

conf = ConnectionConfig(
    MAIL_USERNAME=settings.mail_username,
    MAIL_PASSWORD=settings.mail_password,
    MAIL_FROM=settings.mail_from,
    MAIL_SERVER=settings.mail_server,
    MAIL_PORT=settings.mail_port,
    MAIL_SSL_TLS=settings.mail_ssl_tls,
    MAIL_STARTTLS=settings.mail_starttls,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True
)

@router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest):
    dolphin_forget_password_payload = {
        "UserName": request.email,
        "SecurityKey": "FslKviDfp2tH3qeZla00hp"
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(settings.forgot_password_api_url, json=dolphin_forget_password_payload)
        response.raise_for_status()
        data = response.json()

    logger.info(f"Forgot password API response received for {request.email}")

    # Check if user information was found in the response
    if not data or not data.get("LoginId") or not data.get("Password"):
        logger.warning(f"No user information found for email: {request.email}")
        raise HTTPException(
            status_code=404,
            detail="No account information found for the provided email address."
        )
    
    subject = "Your Password Reset Request"
    body = f"""
    Hello {data.get("FullName")},

    We received a request to reset your password.

    Your updated login details are as follows:

    LoginId: {data.get("LoginId")}
    FullName: {data.get("FullName")}
    EmailId: {data.get("EmailId")}
    Role: {data.get("Role")}
    Password: {data.get("Password")}

    Please log in using the above credentials.

    If you did not request this change, please contact our support team right away.

    Regards,
    Support Team
    """

    message = MessageSchema(
        subject=subject,
        recipients=[data.get("EmailId")],  
        body=body,  
        subtype="plain"
    )

    fm = FastMail(conf)
    try:
        await fm.send_message(message)
        logger.info(f"Password reset email sent successfully to {data.get('EmailId')}")
        return ForgotPasswordResponse(status="success", message="Mail sent successfully")
    except Exception as e:
        logger.error(f"Failed to send password reset email to {data.get('EmailId')}: {e}")
        
        raise HTTPException(
            status_code=500,
            detail="Password reset details retrieved, but failed to send the email. Please try again later."
        )