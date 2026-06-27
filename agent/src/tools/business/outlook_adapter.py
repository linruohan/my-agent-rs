from __future__ import annotations

import sys
from datetime import datetime
from typing import Any


def outlook_available() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import win32com.client  # noqa: F401

        return True
    except ImportError:
        return False


def read_outlook_events(
    start_date: str = "",
    end_date: str = "",
) -> tuple[list[dict[str, Any]], str]:
    """Read calendar items from local Outlook. Returns (events, error)."""
    if not outlook_available():
        return [], "Outlook COM not available (Windows + pywin32 required)"

    try:
        import win32com.client

        outlook = win32com.client.Dispatch("Outlook.Application")
        namespace = outlook.GetNamespace("MAPI")
        calendar = namespace.GetDefaultFolder(9)  # olFolderCalendar
        items = calendar.Items
        items.IncludeRecurrences = True
        items.Sort("[Start]")

        start_filter = start_date or datetime.now().strftime("%Y-%m-%d")
        restriction = f"[Start] >= '{start_filter}'"
        if end_date:
            restriction += f" AND [End] <= '{end_date}'"
        try:
            filtered = items.Restrict(restriction)
        except Exception:
            filtered = items

        events: list[dict[str, Any]] = []
        for item in filtered:
            try:
                subject = str(getattr(item, "Subject", "") or "")
                if not subject:
                    continue
                start = getattr(item, "Start", None)
                end = getattr(item, "End", None)
                location = str(getattr(item, "Location", "") or "")
                events.append(
                    {
                        "id": f"outlook-{getattr(item, 'EntryID', subject)[:16]}",
                        "title": subject,
                        "start_time": str(start),
                        "end_time": str(end),
                        "location": location,
                        "description": str(getattr(item, "Body", "") or "")[:200],
                        "source": "outlook",
                    }
                )
            except Exception:
                continue
            if len(events) >= 50:
                break
        return events, ""
    except Exception as e:
        return [], str(e)


def read_outlook_inbox(
    folder: str = "inbox",
    limit: int = 10,
    unread_only: bool = False,
) -> tuple[list[dict[str, Any]], str]:
    """Read mail items from local Outlook. Returns (messages, error)."""
    if not outlook_available():
        return [], "Outlook COM not available (Windows + pywin32 required)"

    folder_map = {
        "inbox": 6,  # olFolderInbox
        "sent": 5,  # olFolderSentMail
        "drafts": 16,  # olFolderDrafts
    }
    folder_key = (folder or "inbox").strip().lower()
    folder_id = folder_map.get(folder_key)
    if folder_id is None:
        return [], f"Unsupported folder: {folder} (use inbox, sent, drafts)"

    max_items = max(1, min(int(limit or 10), 50))

    try:
        import win32com.client

        outlook = win32com.client.Dispatch("Outlook.Application")
        namespace = outlook.GetNamespace("MAPI")
        mail_folder = namespace.GetDefaultFolder(folder_id)
        items = mail_folder.Items
        items.Sort("[ReceivedTime]", True)

        messages: list[dict[str, Any]] = []
        for item in items:
            try:
                if unread_only and not bool(getattr(item, "UnRead", False)):
                    continue
                subject = str(getattr(item, "Subject", "") or "(无主题)")
                sender = str(getattr(item, "SenderName", "") or "")
                sender_email = str(getattr(item, "SenderEmailAddress", "") or "")
                received = getattr(item, "ReceivedTime", None)
                body_preview = str(getattr(item, "Body", "") or "")[:300]
                messages.append(
                    {
                        "id": f"outlook-mail-{str(getattr(item, 'EntryID', subject))[:16]}",
                        "subject": subject,
                        "from": sender,
                        "from_email": sender_email,
                        "received_time": str(received),
                        "unread": bool(getattr(item, "UnRead", False)),
                        "preview": body_preview,
                        "folder": folder_key,
                        "source": "outlook",
                    }
                )
            except Exception:
                continue
            if len(messages) >= max_items:
                break
        return messages, ""
    except Exception as e:
        return [], str(e)


def send_outlook_email(to: str, subject: str, body: str) -> tuple[bool, str]:
    """Send email via local Outlook. Returns (success, message)."""
    if not outlook_available():
        return False, "Outlook COM not available"

    try:
        import win32com.client

        outlook = win32com.client.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)  # olMailItem
        mail.To = to
        mail.Subject = subject
        mail.Body = body
        mail.Send()
        return True, f"已通过 Outlook 发送邮件至 {to}: {subject}"
    except Exception as e:
        return False, str(e)


def create_outlook_event(
    title: str,
    start_time: str,
    end_time: str,
    location: str = "",
    description: str = "",
) -> tuple[bool, str]:
    """Create calendar appointment in Outlook. Returns (success, message)."""
    if not outlook_available():
        return False, "Outlook COM not available"

    try:
        import win32com.client

        outlook = win32com.client.Dispatch("Outlook.Application")
        appt = outlook.CreateItem(1)  # olAppointmentItem
        appt.Subject = title
        appt.Start = start_time
        appt.End = end_time
        if location:
            appt.Location = location
        if description:
            appt.Body = description
        appt.Save()
        return True, (
            f"已在 Outlook 创建事件: {title} ({start_time} ~ {end_time})"
            + (f" @ {location}" if location else "")
        )
    except Exception as e:
        return False, str(e)
