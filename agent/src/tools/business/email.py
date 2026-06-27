from __future__ import annotations

import json
import os
import smtplib
import sys
from email.mime.text import MIMEText


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


def send_email_unified(to: str, subject: str, body: str) -> str:
    """Prefer Outlook on Windows, fallback to SMTP."""
    if sys.platform == "win32":
        from tools.business.outlook_adapter import outlook_available, send_outlook_email

        if outlook_available():
            ok, msg = send_outlook_email(to, subject, body)
            if ok:
                return msg

    smtp_result = send_smtp_email(to, subject, body)
    if "not configured" not in smtp_result.lower():
        return smtp_result
    return (
        f"邮件发送失败。Outlook: 不可用或未安装；SMTP: {smtp_result}"
    )


def read_email_unified(
    folder: str = "inbox",
    limit: int = 10,
    unread_only: bool = False,
) -> str:
    """Read recent emails from Outlook inbox (Windows only)."""
    if sys.platform != "win32":
        return "read_email 当前仅支持 Windows + Outlook 桌面客户端。"

    from tools.business.outlook_adapter import outlook_available, read_outlook_inbox

    if not outlook_available():
        return "Outlook COM 不可用，请安装: pip install -e \"./agent[outlook]\""

    messages, err = read_outlook_inbox(folder, limit, unread_only)
    if err:
        return f"读取邮件失败: {err}"
    if not messages:
        label = "未读" if unread_only else "最近"
        return f"Outlook {folder} 中没有{label}邮件。"
    return json.dumps(messages, ensure_ascii=False, indent=2)


def create_email_tools():
    from langchain_core.tools import tool

    @tool
    def read_email(
        folder: str = "inbox",
        limit: int = 10,
        unread_only: bool = False,
    ) -> str:
        """Read recent emails from local Outlook (inbox/sent/drafts). Windows only."""
        return read_email_unified(folder, limit, unread_only)

    @tool
    def send_email(to: str, subject: str, body: str) -> str:
        """Send an email via Outlook (Windows) or SMTP. Requires user confirmation."""
        return send_email_unified(to, subject, body)

    return [read_email, send_email]
