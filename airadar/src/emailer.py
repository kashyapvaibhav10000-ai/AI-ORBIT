import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def send_digest(recipient_name: str, recipient_email: str, subject: str, html_body: str) -> bool:
    """Send HTML email via Gmail SMTP. Returns True on success."""
    gmail_user = os.environ.get("GMAIL_USER", "").strip()
    gmail_password = os.environ.get("GMAIL_APP_PASSWORD", "").strip()

    if not gmail_user or not gmail_password:
        logger.error("GMAIL_USER or GMAIL_APP_PASSWORD env var not set")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"AIRadar <{gmail_user}>"
    msg["To"] = recipient_email

    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(gmail_user, gmail_password)
            server.sendmail(gmail_user, [recipient_email], msg.as_string())
        logger.info("Email sent to %s (%s)", recipient_name, recipient_email)
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error("Gmail auth failed — check GMAIL_APP_PASSWORD is a valid App Password, not account password")
        return False
    except smtplib.SMTPException as e:
        logger.error("SMTP error sending to %s: %s", recipient_email, e)
        return False
    except Exception as e:
        logger.error("Unexpected error sending to %s: %s", recipient_email, e)
        return False
