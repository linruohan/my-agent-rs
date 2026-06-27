from __future__ import annotations

import os
import smtplib
from email.mime.text import MIMEText
from typing import Any


def send_smtp_email(to: str, subject: str, body: str) -> str:
    host = os.environ.get("SMTP_HOST", "")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER", "")
    password = os.environ.get("SMTP_PASSWORD", "")
    from_addr = os.environ.get("SMTP_FROM", user)

    if not all([host, user, password, from_addr]):
        return (
            "SMTP not configured. Set SMTP_HOST, SMTP_PORT, SMTP_USER, "
            "SMTP_PASSWORD, SMTP_FROM environment variables."
        )

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to

    try:
        with smtplib.SMTP(host, port, timeout=30) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(from_addr, [to], msg.as_string())
        return f"Email sent to {to}: {subject}"
    except Exception as e:
        return f"Failed to send email: {e}"


def create_email_tools():
    from langchain_core.tools import tool

    @tool
    def send_email(to: str, subject: str, body: str) -> str:
        """Send an email. Requires user confirmation before sending."""
        return send_smtp_email(to, subject, body)

    return [send_email]
