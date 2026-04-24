"""
email_tool.py -- MCP tool for sending HTML email via SMTP.
Singleton pattern.
"""

import json
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Annotated

from pydantic import Field

import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SendEmailTool:
    """SMTP email sending tool (singleton)."""

    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.__class__._initialized = True
            logger.info("Initialized SendEmailTool")

    async def send_email(
        self,
        to_email: Annotated[str, Field(description="Recipient email address")],
        subject: Annotated[str, Field(description="Email subject line")],
        html_content: Annotated[str, Field(description="Email body in HTML format")],
    ) -> str:
        """Send an HTML email to the specified recipient. Returns success/error JSON."""
        try:
            if not config.SMTP_USER or not config.SMTP_PASSWORD:
                return json.dumps({
                    "success": False,
                    "content": "",
                    "error": "SMTP credentials not configured (SMTP_USER, SMTP_PASSWORD)",
                })

            msg = MIMEMultipart("alternative")
            msg["From"] = f"{config.SMTP_FROM_NAME} <{config.SMTP_USER}>"
            msg["To"] = to_email
            msg["Subject"] = subject
            msg.attach(MIMEText(html_content, "html", "utf-8"))

            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
                server.starttls()
                server.login(config.SMTP_USER, config.SMTP_PASSWORD)
                server.send_message(msg)

            logger.info(f"Email sent to {to_email}")
            return json.dumps({
                "success": True,
                "content": f"Email sent to {to_email}",
                "error": None,
            })

        except Exception as e:
            logger.error(f"send_email error: {e}")
            return json.dumps({
                "success": False,
                "content": "",
                "error": str(e),
            })

# script test
if __name__ == "__main__":
    import asyncio

    tool = SendEmailTool()
    result = asyncio.run(tool.send_email(
        to_email="hiepchip318@gmail.com",
        subject="Test Email from MCP Server",
        html_content="<h1>Hello from MCP Server!</h1><p>This is a test email sent using the SendEmailTool.</p>",
    ))