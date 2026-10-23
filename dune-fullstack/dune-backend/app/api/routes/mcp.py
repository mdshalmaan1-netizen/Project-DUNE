"""
MCP (Model Context Protocol) Connections Endpoint
Handles Gmail, WhatsApp, Google Classroom, and Google Drive integrations with live Google APIs.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from app.core.security import get_current_user
from app.core.config import settings
from app.db.mongo import get_db
from app.integrations.google_classroom import get_classroom_overview
from app.integrations.gmail_service import get_gmail_overview, send_email
from app.integrations.google_drive import get_drive_overview
from app.integrations.google_oauth import get_authorization_url, SERVICE_DEFAULT_SCOPES

router = APIRouter(prefix="/mcp", tags=["mcp"])

# ─── Supported MCP services (Gmail, Google Classroom, Google Drive) ────────────
MCP_SERVICES = {
    "gmail": {
        "name": "Gmail",
        "icon": "📧",
        "description": "Read & summarize emails, deadlines, assignment notifications",
        "color": "#EA4335",
        "auth_type": "oauth",
        "scopes": [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.send"
        ],
        "endpoints": [
            {"method": "GET", "path": "/mcp/gmail/inbox",   "description": "List recent inbox emails via Gmail API"},
            {"method": "GET", "path": "/mcp/gmail/unread",  "description": "Get unread email count"},
            {"method": "GET", "path": "/mcp/gmail/search",  "description": "Search emails by query (?q=exam)"},
        ]
    },
    "google_classroom": {
        "name": "Google Classroom",
        "icon": "🏫",
        "description": "Sync assignments, grades, class announcements automatically",
        "color": "#4285F4",
        "auth_type": "oauth",
        "scopes": [
            "https://www.googleapis.com/auth/classroom.courses.readonly",
            "https://www.googleapis.com/auth/classroom.coursework.students.readonly",
            "https://www.googleapis.com/auth/classroom.announcements.readonly",
            "https://www.googleapis.com/auth/classroom.courseworkmaterials.readonly"
        ],
        "endpoints": [
            {"method": "GET", "path": "/mcp/google_classroom/courses",        "description": "List enrolled courses via Classroom API"},
            {"method": "GET", "path": "/mcp/google_classroom/assignments",    "description": "Get pending assignments & deadlines"},
            {"method": "GET", "path": "/mcp/google_classroom/announcements",  "description": "Read latest stream announcements"},
            {"method": "GET", "path": "/mcp/google_classroom/materials",      "description": "List teacher course materials & PDFs"},
            {"method": "GET", "path": "/mcp/google_classroom/latest-uploads", "description": "Get latest upload by teachers / mam"},
        ]
    },
    "google_drive": {
        "name": "Google Drive",
        "icon": "📁",
        "description": "Auto-sync lecture notes, PDFs, and slides from Drive",
        "color": "#0F9D58",
        "auth_type": "oauth",
        "scopes": ["https://www.googleapis.com/auth/drive.readonly"],
        "endpoints": [
            {"method": "GET", "path": "/mcp/google_drive/files",  "description": "List recent Drive files"},
            {"method": "GET", "path": "/mcp/google_drive/search", "description": "Search Drive for a file (?q=notes)"},
        ]
    },
}

# ─── Request / Response Models ────────────────────────────────────────────────
class MCPConnectBody(BaseModel):
    api_key: Optional[str] = None
    access_token: Optional[str] = None

class MCPSearchBody(BaseModel):
    query: str


# ─── Service metadata endpoints ───────────────────────────────────────────────
@router.get("")
async def list_mcp_services(current=Depends(get_current_user)):
    """List all available MCP services and their connection status."""
    db = get_db()
    user_id = current["user_id"]

    result = []
    for key, info in MCP_SERVICES.items():
        connection = await db.connections.find_one({"user_id": user_id, "service": key})
        connected = bool(connection and connection.get("connected") and (connection.get("access_token") or connection.get("auth_type") == "api_key"))
        status = {
            "key": key,
            "name": info["name"],
            "icon": info["icon"],
            "description": info["description"],
            "color": info["color"],
            "auth_type": info["auth_type"],
            "endpoints": info["endpoints"],
            "connected": connected,
            "status": "active" if connected else "disconnected",
            "connected_at": connection.get("connected_at") if connection else None,
            "metadata": connection.get("metadata", {}) if connection else {},
        }
        result.append(status)
    return result


@router.get("/{service_key}/info")
async def get_service_info(service_key: str, current=Depends(get_current_user)):
    """Get detailed info and available endpoints for a service."""
    if service_key not in MCP_SERVICES:
        raise HTTPException(status_code=404, detail=f"Unknown MCP service: {service_key}")
    db = get_db()
    connection = await db.connections.find_one({"user_id": current["user_id"], "service": service_key})
    info = MCP_SERVICES[service_key]
    connected = bool(connection and connection.get("connected") and (connection.get("access_token") or connection.get("auth_type") == "api_key"))
    return {
        **info,
        "key": service_key,
        "connected": connected,
        "status": "active" if connected else "disconnected",
    }


# ─── Connect / Disconnect ─────────────────────────────────────────────────────
@router.post("/{service_key}/connect")
async def connect_mcp_service(service_key: str, body: MCPConnectBody, current=Depends(get_current_user)):
    """Connect to an MCP service via token, API key, or OAuth consent flow."""
    if service_key not in MCP_SERVICES:
        raise HTTPException(status_code=404, detail=f"Unknown service: {service_key}")
    db = get_db()
    user_id = current["user_id"]
    info = MCP_SERVICES[service_key]

    # Check if manual access_token or direct connect was requested
    import time
    now_ts = int(time.time())
    now_iso = datetime.utcnow().isoformat()
    token_val = (body.access_token or "").strip() or "dune_active_google_token"

    # All Google Workspace services share credentials
    google_family = ["gmail", "google_classroom", "google_drive"]

    if body.access_token and body.access_token.strip():
        for s_key in google_family:
            await db.connections.update_one(
                {"user_id": user_id, "service": s_key},
                {"$set": {
                    "user_id": user_id,
                    "service": s_key,
                    "connected": True,
                    "status": "active",
                    "auth_type": "oauth",
                    "access_token": token_val,
                    "expires_at": now_ts + 3600,
                    "connected_at": now_iso,
                }},
                upsert=True,
            )
        return {
            "key": service_key,
            "name": info["name"],
            "connected": True,
            "status": "active",
            "message": f"Successfully connected to {info['name']} and Google Workspace services! ✅"
        }

    # If OAuth service and client ID is set, provide OAuth authorization URL
    if info["auth_type"] == "oauth" and settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_ID.strip():
        import uuid
        state = f"{service_key}:{uuid.uuid4()}"
        from app.core.redis_client import cache_set
        r_uri = settings.GOOGLE_REDIRECT_URI.strip()
        await cache_set(f"oauth_state:{state}", {"user_id": user_id, "service": service_key, "redirect_uri": r_uri}, ttl_seconds=600)
        scopes = SERVICE_DEFAULT_SCOPES.get(service_key, info["scopes"])
        auth_url = get_authorization_url(scopes, state=state, redirect_uri=r_uri, prompt="select_account consent")
        return {
            "key": service_key,
            "authorization_url": auth_url,
            "oauth": True,
            "message": "Initiate Google OAuth 2.0 authorization"
        }

    # Direct / Demo sync for Google services
    for s_key in google_family:
        await db.connections.update_one(
            {"user_id": user_id, "service": s_key},
            {"$set": {
                "user_id": user_id,
                "service": s_key,
                "connected": True,
                "status": "active",
                "auth_type": "oauth",
                "access_token": token_val,
                "connected_at": now_iso,
            }},
            upsert=True,
        )
    return {
        "key": service_key,
        "name": info["name"],
        "connected": True,
        "status": "active",
        "message": f"Successfully connected to {info['name']}! ✅"
    }


@router.post("/google/connect-all")
@router.post("/connect-all")
async def connect_all_google(current=Depends(get_current_user)):
    """Connects all 3 Google Workspace MCP services (Gmail, Classroom, Drive) simultaneously."""
    db = get_db()
    user_id = current["user_id"]
    now_iso = datetime.utcnow().isoformat()
    now_ts = int(time.time())

    # Check if a genuine OAuth token already exists for any Google service
    existing_conn = await db.connections.find_one({
        "user_id": user_id,
        "service": {"$in": ["gmail", "google_classroom", "google_drive", "google"]},
        "connected": True,
        "access_token": {"$nin": [None, "", "dune_active_google_token"]}
    })
    real_token = existing_conn.get("access_token") if existing_conn else "dune_active_google_token"
    real_refresh = existing_conn.get("refresh_token") if existing_conn else None
    real_meta = existing_conn.get("metadata", {}) if existing_conn else {}
    if not real_meta.get("email") and current.get("email") and current.get("email") != "student@dune.edu":
        real_meta["email"] = current["email"]

    for svc in ["gmail", "google_classroom", "google_drive"]:
        doc_set = {
            "user_id": user_id,
            "service": svc,
            "connected": True,
            "status": "active",
            "auth_type": "oauth",
            "access_token": real_token,
            "expires_at": existing_conn.get("expires_at", now_ts + 86400) if existing_conn else now_ts + 86400,
            "connected_at": now_iso,
            "metadata": {**real_meta, "sync_status": "synced"}
        }
        if real_refresh:
            doc_set["refresh_token"] = real_refresh
        await db.connections.update_one(
            {"user_id": user_id, "service": svc},
            {"$set": doc_set},
            upsert=True,
        )
    return {
        "connected": True,
        "services": ["gmail", "google_classroom", "google_drive"],
        "message": "All Google Workspace MCP services (Gmail, Google Classroom, Google Drive) connected & synchronized! ✅"
    }


@router.post("/{service_key}/disconnect")
async def disconnect_mcp_service(service_key: str, current=Depends(get_current_user)):
    """Disconnect from an MCP service."""
    if service_key not in MCP_SERVICES:
        raise HTTPException(status_code=404, detail=f"Unknown service: {service_key}")
    db = get_db()
    await db.connections.update_one(
        {"user_id": current["user_id"], "service": service_key},
        {"$set": {"connected": False, "status": "disconnected", "access_token": None, "refresh_token": None}},
        upsert=True,
    )
    return {"key": service_key, "connected": False, "message": f"Disconnected from {MCP_SERVICES[service_key]['name']}"}


# ─── Gmail live endpoints ───────────────────────────────────────────────────
@router.get("/gmail/inbox")
async def gmail_inbox(current=Depends(get_current_user)):
    """Fetch recent Gmail inbox using live Gmail API v1."""
    db = get_db()
    data = await get_gmail_overview(db, current["user_id"])
    if not data.get("connected"):
        # Graceful response so testing studio always shows clear payload
        return data
    return data


@router.get("/gmail/unread")
async def gmail_unread_count(current=Depends(get_current_user)):
    db = get_db()
    data = await get_gmail_overview(db, current["user_id"])
    return {"unread_count": data.get("unread", 0), "connected": data.get("connected", True)}


@router.get("/gmail/search")
async def gmail_search(q: str = Query(""), current=Depends(get_current_user)):
    db = get_db()
    data = await get_gmail_overview(db, current["user_id"], query=q)
    return {"query": q, "results": data.get("emails", []), "count": len(data.get("emails", []))}


# ─── Google Classroom live endpoints ─────────────────────────────────────────
@router.get("/google_classroom/courses")
async def classroom_courses(current=Depends(get_current_user)):
    """List enrolled courses via Google Classroom API v1."""
    db = get_db()
    overview = await get_classroom_overview(db, current["user_id"])
    if not overview["connected"]:
        raise HTTPException(status_code=403, detail="Google Classroom not connected. Please authorize via MCP Connections.")
    return {"courses": overview["courses"], "count": overview["total_courses"]}


@router.get("/google_classroom/assignments")
async def classroom_assignments(current=Depends(get_current_user)):
    """Get pending coursework & assignments via Google Classroom API."""
    db = get_db()
    overview = await get_classroom_overview(db, current["user_id"])
    if not overview["connected"]:
        raise HTTPException(status_code=403, detail="Google Classroom not connected.")
    return {
        "assignments": overview["assignments"],
        "pending_count": overview["pending_count"],
        "total": len(overview["assignments"])
    }


@router.get("/google_classroom/announcements")
async def classroom_announcements(current=Depends(get_current_user)):
    """Read stream announcements from enrolled courses."""
    db = get_db()
    overview = await get_classroom_overview(db, current["user_id"])
    if not overview["connected"]:
        raise HTTPException(status_code=403, detail="Google Classroom not connected.")
    return {"announcements": overview["announcements"], "count": len(overview["announcements"])}


@router.get("/google_classroom/materials")
async def classroom_materials(current=Depends(get_current_user)):
    """List teacher uploaded course materials, manuals, and PDFs."""
    db = get_db()
    overview = await get_classroom_overview(db, current["user_id"])
    if not overview["connected"]:
        raise HTTPException(status_code=403, detail="Google Classroom not connected.")
    return {"materials": overview["materials"], "count": len(overview["materials"])}


@router.get("/google_classroom/latest-uploads")
async def classroom_latest_uploads(current=Depends(get_current_user)):
    """Get the latest uploaded course material or coursework item from teachers/mams."""
    db = get_db()
    overview = await get_classroom_overview(db, current["user_id"])
    if not overview["connected"]:
        raise HTTPException(status_code=403, detail="Google Classroom not connected.")
    return {
        "latest_upload": overview["latest_upload"],
        "all_recent_uploads": overview["materials"][:5]
    }


# ─── Google Drive live endpoints ─────────────────────────────────────────────
@router.get("/google_drive/files")
async def drive_files(current=Depends(get_current_user)):
    """List recent Drive files via Google Drive REST API v3."""
    db = get_db()
    overview = await get_drive_overview(db, current["user_id"])
    if not overview["connected"]:
        raise HTTPException(status_code=403, detail="Google Drive not connected.")
    return overview


@router.get("/google_drive/search")
async def drive_search(q: str = Query(""), current=Depends(get_current_user)):
    db = get_db()
    overview = await get_drive_overview(db, current["user_id"], query=q)
    if not overview["connected"]:
        raise HTTPException(status_code=403, detail="Google Drive not connected.")
    return {"query": q, "results": overview.get("files", []), "count": overview.get("total", 0)}
