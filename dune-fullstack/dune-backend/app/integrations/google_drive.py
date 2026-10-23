"""
Real Google Drive API Integration for DUNE.
Interacts directly with Google Drive REST API v3 using OAuth 2.0 access tokens.
Supports searching and listing lecture notes, PDFs, slide decks, and coursework files.
"""
from typing import List, Dict, Any, Optional
import requests
from app.integrations.google_oauth import get_valid_google_token

DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"


def _headers(access_token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }


def list_files(access_token: str, query: str = "", page_size: int = 10) -> List[Dict[str, Any]]:
    """Lists files from Google Drive."""
    q_filter = "trashed = false"
    if query:
        q_filter += f" and (name contains '{query}' or fullText contains '{query}')"

    url = f"{DRIVE_API_BASE}/files?pageSize={page_size}&fields=files(id,name,mimeType,modifiedTime,size,webViewLink)&q={requests.utils.quote(q_filter)}"
    try:
        resp = requests.get(url, headers=_headers(access_token), timeout=15)
        if resp.status_code == 200:
            return resp.json().get("files", [])
        print(f"[Drive API] list_files returned {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        print(f"[Drive API] list_files error: {e}")
    return []


async def get_drive_overview(db, user_id: str, query: str = "", page_size: int = 10) -> Dict[str, Any]:
    token = await get_valid_google_token(db, user_id, service="google_drive")
    if not token:
        return {"connected": False, "files": [], "total": 0, "message": "Google Drive not connected."}

    files = list_files(token, query=query, page_size=page_size)
    return {"connected": True, "files": files, "total": len(files)}


async def get_drive_mcp_context(db, user_id: str, query: str = "") -> Dict[str, Any]:
    overview = await get_drive_overview(db, user_id, query=query, page_size=5)
    if not overview["connected"]:
        return {
            "tool": "drive.search_files()",
            "service": "Google Drive MCP",
            "summary": "Google Drive is not connected.",
            "data": (
                "Google Drive status: Not Connected.\n"
                "The student has not linked their Google Drive account yet.\n"
                "To search slide decks, PDFs, or lecture notes, the student can connect Google Drive "
                "via the 'MCP Connections' studio in the sidebar by clicking 'Connect' -> 'Authorize with Google'."
            )
        }

    files = overview.get("files", [])
    lines = ["Status: Connected & Synchronized (Live Google Drive API v3)", "", "RECENT GOOGLE DRIVE FILES:"]
    for f in files:
        lines.append(f"• {f.get('name')} (Modified: {f.get('modifiedTime', '')[:10]} • Link: {f.get('webViewLink', 'N/A')})")

    return {
        "tool": "drive.search_files()",
        "service": "Google Drive MCP",
        "summary": f"{len(files)} Drive files retrieved",
        "data": "\n".join(lines).strip()
    }
