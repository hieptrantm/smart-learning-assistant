"""
email_service.py -- SMTP email sending for study-planner-api.
"""

import logging
import random
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import (
    SMTP_FROM_NAME,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USER,
    QUIZ_EMAIL_BODY_FAILED,
    QUIZ_EMAIL_BODY_PASSED,
    QUIZ_EMAIL_SUBJECT_FAILED,
    QUIZ_EMAIL_SUBJECT_PASSED,
    QUIZ_FAILED_MOTIVATIONS,
    QUIZ_PASSED_MOTIVATIONS,
)

logger = logging.getLogger(__name__)


def send_email(to_email: str, subject: str, html_content: str) -> bool:
    """Send an HTML email via SMTP. Returns True on success."""
    if not SMTP_USER or not SMTP_PASSWORD:
        logger.warning("SMTP credentials not configured, skipping email")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_USER}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)

        logger.info(f"Email sent to {to_email}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False


def send_quiz_result_email(
    to_email: str,
    username: str,
    subject_name: str,
    score: float,
    target_grade: float,
    passed: bool,
) -> bool:
    """Send a quiz result notification email to the user."""
    target_score = int(target_grade * 10)
    score_int = int(score)

    if passed:
        motivation = random.choice(QUIZ_PASSED_MOTIVATIONS)
        email_subject = QUIZ_EMAIL_SUBJECT_PASSED.format(subject_name=subject_name)
        html_content = QUIZ_EMAIL_BODY_PASSED.format(
            username=username,
            subject_name=subject_name,
            score=score_int,
            target_score=target_score,
            motivation=motivation,
        )
    else:
        motivation = random.choice(QUIZ_FAILED_MOTIVATIONS)
        email_subject = QUIZ_EMAIL_SUBJECT_FAILED.format(subject_name=subject_name)
        html_content = QUIZ_EMAIL_BODY_FAILED.format(
            username=username,
            subject_name=subject_name,
            score=score_int,
            target_score=target_score,
            motivation=motivation,
        )

    return send_email(to_email, email_subject, html_content)
