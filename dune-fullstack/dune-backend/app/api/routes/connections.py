"""
Connections router: list / connect / disconnect services.
Handles Google OAuth 2.0 initiation and code exchange callback for Gmail, Google Classroom,
Google Drive, and Google Calendar, persisting tokens into MongoDB.
"""
import uuid
import os
import time
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Optional
from app.core.security import get_current_user
from app.core.config import settings
from app.db.mongo import get_db
from app.services.connection_service import list_connections, disconnect_service, SERVICE_SCOPES
from app.integrations.google_oauth import get_authorization_url, exchange_code_for_tokens, store_google_connection, get_user_info
from app.services.folder_watcher import start_watching
from app.core.redis_client import cache_set, cache_get

router = APIRouter(prefix="/connections", tags=["connections"])

GOOGLE_SERVICES = {"gmail", "google_classroom", "google_drive", "drive", "calendar", "google_calendar", "google"}

class LocalFolderBody(BaseModel):
    folder_path: str

@router.get("")
async def list_all(current=Depends(get_current_user)):
    return await list_connections(current["user_id"])


@router.post("/{key}/connect")
async def connect(
    key: str,
    prompt: Optional[str] = Query(None),
    redirect_uri: Optional[str] = Query(None),
    current=Depends(get_current_user)
):
    user_id = current["user_id"]
    scopes = SERVICE_SCOPES.get(key, [])

    # If service is a Google-based service
    if key in GOOGLE_SERVICES:
        if settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_ID.strip():
            state = f"{key}:{uuid.uuid4()}"
            r_uri = (redirect_uri or settings.GOOGLE_REDIRECT_URI).strip()
            chosen_prompt = prompt or "select_account consent"
            await cache_set(
                f"oauth_state:{state}",
                {"user_id": user_id, "service": key, "redirect_uri": r_uri},
                ttl_seconds=600
            )
            url = get_authorization_url(scopes, state=state, redirect_uri=r_uri, prompt=chosen_prompt)
            return {"authorization_url": url, "service": key, "oauth": True}
        else:
            # Client ID not yet set in .env
            return {
                "key": key,
                "connected": False,
                "requires_setup": True,
                "message": "Google Client ID is not configured in .env. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET or provide an OAuth Access Token."
            }

    # Otherwise (files, lms, etc.), connect directly in DB
    db = get_db()
    await db.connections.update_one(
        {"user_id": user_id, "service": key},
        {"$set": {
            "user_id": user_id, "service": key, "connected": True,
            "status": "active",
            "scopes": scopes,
            "connected_at": datetime.utcnow().isoformat(),
        }},
        upsert=True,
    )
    return {"key": key, "connected": True, "status": "active"}


import logging

logger = logging.getLogger("connections")

@router.get("/oauth/callback")
@router.get("/oauth/callback/")
async def oauth_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None
):
    if error:
        logger.warning(f"[OAuth Callback] OAuth error received from Google: {error}")
        return RedirectResponse(f"{settings.FRONTEND_URL}/?oauth_error={error}")

    if not code or not state:
        logger.error(f"[OAuth Callback] Missing code or state parameter (code_present={bool(code)}, state_present={bool(state)})")
        raise HTTPException(status_code=400, detail="Missing code or state parameter")

    state_data = await cache_get(f"oauth_state:{state}")
    if not state_data:
        # Fallback parsing service from state if state was formatted as service:uuid or direct service
        if ":" in state:
            service_fallback = state.split(":")[0]
        else:
            service_fallback = state if state in GOOGLE_SERVICES else "google"
        user_id = "default-student-1"
        service = service_fallback
        redirect_uri_used = settings.GOOGLE_REDIRECT_URI
        logger.info(f"[OAuth Callback] Cached state not found; using fallback service='{service}'")
    else:
        user_id = state_data["user_id"]
        service = state_data["service"]
        redirect_uri_used = state_data.get("redirect_uri") or settings.GOOGLE_REDIRECT_URI
        logger.info(f"[OAuth Callback] Cached state resolved: user_id='{user_id}', service='{service}', redirect_uri='{redirect_uri_used}'")

    scopes = SERVICE_SCOPES.get(service, [])
    creds = exchange_code_for_tokens(code, scopes=scopes, state=state, redirect_uri=redirect_uri_used)

    if not creds or not creds.access_token:
        logger.error(f"[OAuth Callback] Failed to exchange authorization code for Google access token. service='{service}'")
        return RedirectResponse(f"{settings.FRONTEND_URL}/?oauth_error=token_exchange_failed")

    db = get_db()
    user_info = get_user_info(creds.access_token) or {}
    meta = {
        "email": user_info.get("email", ""),
        "name": user_info.get("name", ""),
        "picture": user_info.get("picture", ""),
    }
    if not meta.get("email") and creds.id_token:
        try:
            import json, base64
            parts = creds.id_token.split(".")
            if len(parts) >= 2:
                payload_str = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
                id_data = json.loads(base64.urlsafe_b64decode(payload_str.encode("utf-8")).decode("utf-8"))
                if "email" in id_data:
                    meta["email"] = id_data["email"]
                if "name" in id_data and not meta.get("name"):
                    meta["name"] = id_data["name"]
                if "picture" in id_data and not meta.get("picture"):
                    meta["picture"] = id_data["picture"]
        except Exception:
            pass

    await store_google_connection(db, user_id, service, creds, metadata=meta)

    # Also mark related Google services active if comprehensive scopes were granted
    if service in ["google", "google_classroom", "gmail", "google_drive", "drive"]:
        await db.connections.update_many(
            {"user_id": user_id, "service": {"$in": ["google", "google_classroom", "gmail", "google_drive", "drive"]}},
            {"$set": {
                "connected": True,
                "status": "active",
                "access_token": creds.access_token,
                "refresh_token": creds.refresh_token,
                "expires_at": creds.expires_at,
                "metadata": meta,
                "updated_at": datetime.utcnow().isoformat()
            }}
        )

    logger.info(f"[OAuth Callback] Successfully connected Google service '{service}' for user '{user_id}'. Redirecting to frontend.")
    return RedirectResponse(f"{settings.FRONTEND_URL}/?connected={service}&status=success")


@router.post("/local_folder")
async def connect_local_folder(body: LocalFolderBody, current=Depends(get_current_user)):
    if not os.path.isdir(body.folder_path):
        raise HTTPException(status_code=400, detail="Folder does not exist on the server")
    db = get_db()
    await db.connections.update_one(
        {"user_id": current["user_id"], "service": "local_folder"},
        {"$set": {
            "user_id": current["user_id"], "service": "local_folder", "connected": True,
            "metadata": {"folder_path": body.folder_path}, "connected_at": datetime.utcnow().isoformat(),
        }}, upsert=True,
    )
    start_watching(current["user_id"], body.folder_path)
    return {"key": "local_folder", "connected": True, "folder_path": body.folder_path}


@router.post("/{key}/disconnect")
async def disconnect(key: str, current=Depends(get_current_user)):
    await disconnect_service(current["user_id"], key)
    return {"key": key, "connected": False}
