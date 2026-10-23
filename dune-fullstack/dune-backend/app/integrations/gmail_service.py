"""
Real Gmail API Integration for DUNE.
Interacts directly with Gmail REST API v1 using OAuth 2.0 access tokens.
Supports reading inbox emails, counting unread messages, searching by query, sending emails,
and integrating with DUNE's MCP AI agent with automatic token refresh.
"""
import base64
from email.mime.text import MIMEText
from typing import List, Dict, Any, Optional
import requests
from app.integrations.google_oauth import get_valid_google_token

GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"


def _headers(access_token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }


def list_messages(access_token: str, query: str = "", max_results: int = 10) -> List[Dict[str, Any]]:
    """Lists message summaries from the student's Gmail account."""
    url = f"{GMAIL_API_BASE}/messages?maxResults={max_results}"
    if query:
        url += f"&q={requests.utils.quote(query)}"
    try:
        resp = requests.get(url, headers=_headers(access_token), timeout=15)
        if resp.status_code == 200:
            return resp.json().get("messages", [])
        print(f"[Gmail API] list_messages returned {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        print(f"[Gmail API] list_messages error: {e}")
    return []


def get_message_detail(access_token: str, message_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves full details for a message (headers, snippet, date, unread status)."""
    url = f"{GMAIL_API_BASE}/messages/{message_id}?format=full"
    try:
        resp = requests.get(url, headers=_headers(access_token), timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            payload = data.get("payload", {})
            headers = payload.get("headers", [])
            header_map = {h.get("name", "").lower(): h.get("value", "") for h in headers}

            subject = header_map.get("subject", "(No Subject)")
            from_field = header_map.get("from", "Unknown Sender")
            date_field = header_map.get("date", "")
            snippet = data.get("snippet", "")
            label_ids = data.get("labelIds", [])
            is_unread = "UNREAD" in label_ids

            return {
                "id": message_id,
                "thread_id": data.get("threadId"),
                "from": from_field,
                "subject": subject,
                "date": date_field,
                "snippet": snippet,
                "unread": is_unread,
                "labels": label_ids
            }
        print(f"[Gmail API] get_message_detail {message_id} returned {resp.status_code}")
    except Exception as e:
        print(f"[Gmail API] get_message_detail error: {e}")
    return None


def get_unread_count(access_token: str) -> int:
    """Gets the count of unread messages in the inbox."""
    url = f"{GMAIL_API_BASE}/messages?q=is:unread&maxResults=50"
    try:
        resp = requests.get(url, headers=_headers(access_token), timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("resultSizeEstimate", len(data.get("messages", [])))
    except Exception as e:
        print(f"[Gmail API] get_unread_count error: {e}")
    return 0


def send_email(access_token: str, to: str, subject: str, body_text: str) -> Dict[str, Any]:
    """Sends an email message via Gmail API."""
    url = f"{GMAIL_API_BASE}/messages/send"
    try:
        message = MIMEText(body_text)
        message["to"] = to
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        resp = requests.post(url, headers=_headers(access_token), json={"raw": raw}, timeout=15)
        if resp.status_code in (200, 201):
            return {"sent": True, "id": resp.json().get("id"), "to": to, "subject": subject}
        return {"sent": False, "error": resp.text}
    except Exception as e:
        return {"sent": False, "error": str(e)}


async def get_gmail_overview(db, user_id: str, query: str = "", max_results: int = 5) -> Dict[str, Any]:
    """
    Retrieves parsed emails from Gmail with automatic token refresh.
    """
    token = await get_valid_google_token(db, user_id, service="gmail")
    if not token:
        return {
            "connected": False,
            "message": "Gmail is not connected or authorization expired.",
            "emails": [],
            "total": 0,
            "unread": 0
        }

    raw_msgs = list_messages(token, query=query, max_results=max_results)
    emails = []
    unread_count = 0

    for m in raw_msgs:
        detail = get_message_detail(token, m["id"])
        if detail:
            emails.append(detail)
            if detail.get("unread"):
                unread_count += 1

    total_unread = get_unread_count(token)

    return {
        "connected": True,
        "emails": emails,
        "total": len(emails),
        "unread": total_unread if total_unread > 0 else unread_count
    }


async def get_gmail_mcp_context(db, user_id: str, query: str = "") -> Dict[str, Any]:
    """
    Prepares live Gmail Model Context Protocol (MCP) data for DUNE's LLM agent.
    If connected, delivers real inbox emails, unread counts, and search results.
    If not connected, returns clear connection instructions.
    """
    overview = await get_gmail_overview(db, user_id, query=query, max_results=5)

    if not overview["connected"]:
        return {
            "tool": "gmail.list_recent_emails()",
            "service": "Gmail MCP",
            "summary": "Gmail is not connected.",
            "data": (
                "Gmail status: Not Connected.\n"
                "The student has not linked their Gmail account yet.\n"
                "To read recent emails, professor announcements, or assignment notifications, the student can connect Gmail "
                "via the 'MCP Connections' studio in the sidebar by clicking 'Connect' -> 'Authorize with Google'."
            )
        }

    emails = overview.get("emails", [])
    total_unread = overview.get("unread", 0)

    lines = [
        f"Status: Connected & Synchronized (Live Gmail API v1)",
        f"Total Unread Messages: {total_unread}",
        "",
        "RECENT INBOX EMAILS:"
    ]

    for idx, em in enumerate(emails, 1):
        status = "Unread" if em.get("unread") else "Read"
        lines.append(
            f"{idx}. From: {em.get('from')}\n"
            f"   Subject: {em.get('subject')}\n"
            f"   Date: {em.get('date')}\n"
            f"   Status: {status}\n"
            f"   Snippet: {em.get('snippet')}"
        )

    summary = f"{len(emails)} emails retrieved • {total_unread} unread in inbox"

    return {
        "tool": "gmail.list_recent_emails()",
        "service": "Gmail MCP",
        "summary": summary,
        "data": "\n".join(lines).strip()
    }
