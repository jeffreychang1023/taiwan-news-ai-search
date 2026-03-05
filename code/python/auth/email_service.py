"""
Email service for auth system.

Dev mode: logs verification/reset/invitation URLs to console.
Production: sends via Resend API when RESEND_API_KEY is set.
"""

import os
from misc.logger.logging_config_helper import get_configured_logger

logger = get_configured_logger("email_service")

RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
RESEND_FROM_EMAIL = os.environ.get('RESEND_FROM_EMAIL', 'noreply@localhost')
BASE_URL = os.environ.get('BASE_URL', 'http://localhost:8000')


def _send_via_resend(to: str, subject: str, html: str):
    """Send email via Resend API."""
    try:
        import resend
        resend.api_key = RESEND_API_KEY
        resend.Emails.send({
            "from": RESEND_FROM_EMAIL,
            "to": to,
            "subject": subject,
            "html": html,
        })
        logger.info(f"Email sent via Resend to: {to}")
    except Exception as e:
        logger.error(f"Failed to send email via Resend to {to}: {e}", exc_info=True)
        raise


def send_verification_email(email: str, token: str, name: str):
    """Send email verification link."""
    url = f"{BASE_URL}/api/auth/verify-email?token={token}"

    if RESEND_API_KEY:
        _send_via_resend(
            to=email,
            subject="Verify your email",
            html=f"<p>Hi {name},</p>"
                 f"<p>Please verify your email by clicking the link below:</p>"
                 f'<p><a href="{url}">{url}</a></p>'
        )
    else:
        print(f"[DEV EMAIL] Verification email for {email}")
        print(f"[DEV EMAIL] Verification URL: {url}", flush=True)


def send_password_reset_email(email: str, token: str, name: str):
    """Send password reset link."""
    url = f"{BASE_URL}/api/auth/reset-password?token={token}"

    if RESEND_API_KEY:
        _send_via_resend(
            to=email,
            subject="Reset your password",
            html=f"<p>Hi {name},</p>"
                 f"<p>Click the link below to reset your password (valid for 1 hour):</p>"
                 f'<p><a href="{url}">{url}</a></p>'
        )
    else:
        print(f"[DEV EMAIL] Password reset email for {email}")
        print(f"[DEV EMAIL] Reset URL: {url}", flush=True)


def send_invitation_email(email: str, org_name: str, inviter_name: str, token: str):
    """Send organization invitation link."""
    url = f"{BASE_URL}/?invite={token}"

    if RESEND_API_KEY:
        _send_via_resend(
            to=email,
            subject=f"You're invited to join {org_name}",
            html=f"<p>Hi,</p>"
                 f"<p>{inviter_name} has invited you to join <strong>{org_name}</strong>.</p>"
                 f'<p><a href="{url}">Accept Invitation</a></p>'
        )
    else:
        print(f"[DEV EMAIL] Invitation email for {email} to join {org_name}")
        print(f"[DEV EMAIL] Invitation URL: {url}", flush=True)


def send_lockout_notification(email: str, ip: str):
    """Notify user that their account has been temporarily locked due to failed login attempts."""
    masked_ip = ip[:ip.rfind('.')] + '.***' if '.' in ip else ip[:len(ip)//2] + '***'

    if RESEND_API_KEY:
        _send_via_resend(
            to=email,
            subject="Security alert: your account has been temporarily locked",
            html=(
                f"<p>We detected multiple failed login attempts for your account.</p>"
                f"<p>Your account has been temporarily locked for 15 minutes.</p>"
                f"<p>Login attempt origin: <code>{masked_ip}</code></p>"
                f"<p>If this wasn't you, we recommend resetting your password after the lock period.</p>"
            )
        )
    else:
        print(f"[DEV EMAIL] Lockout notification for {email} (IP: {masked_ip})", flush=True)
