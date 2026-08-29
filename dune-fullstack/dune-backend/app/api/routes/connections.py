"""Matches frontend connectionsApi: list / connect / disconnect.
Also exposes the OAuth callback for incremental-scope connects
(Gmail / Calendar / Drive / local folder registration)."""
import uuid, os
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from app.core.security import get_current_user
from app.core.config import settings
from app.db.mongo import get_db
from app.services.connection_service import list_connections, disconnect_service, SERVICE_SCOPES
from app.integrations.google_oauth import get_authorization_url, exchange_code_for_tokens
from app.services.folder_watcher import start_watching
from app.core.redis_client import cache_set, cache_get

router = APIRouter(prefix="/connections", tags=["connections"])

class LocalFolderBody(BaseModel):
    folder_path: str

@router.get("")
async def list_all(current=Depends(get_current_user)):
    return await list_connections(current["user_id"])

@router.post("/{key}/connect")
async def connect(key: str, current=Depends(get_current_user)):
    user_id = current["user_id"]
    scopes = SERVICE_SCOPES.get(key, [])

    # If Google OAuth client is configured and service is Google-based, trigger OAuth flow
    if settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_ID.strip() and key in ["gmail", "calendar", "google_calendar", "drive", "google_drive"]:
        state = str(uuid.uuid4())
        await cache_set(f"oauth_state:{state}", {"user_id": user_id, "service": key}, ttl_seconds=600)
        url = get_authorization_url(scopes, state)
        return {"authorization_url": url}

    # Otherwise (files, lms, or dev mode without OAuth credentials), connect directly in DB
    db = get_db()
    await db.connections.update_one(
        {"user_id": user_id, "service": key},
        {"$set": {
            "user_id": user_id, "service": key, "connected": True,
            "scopes": scopes, "access_token": "mock_token",
            "connected_at": datetime.utcnow(),
        }},
        upsert=True,
    )
    return {"key": key, "connected": True, "status": "active"}


@router.get("/oauth/callback")
async def oauth_callback(code: str, state: str):
    state_data = await cache_get(f"oauth_state:{state}")
    if not state_data:
        raise HTTPException(status_code=400, detail="OAuth state expired or invalid")
    user_id, service = state_data["user_id"], state_data["service"]
    scopes = SERVICE_SCOPES[service]
    creds = exchange_code_for_tokens(code, scopes, state)

    db = get_db()
    await db.connections.update_one(
        {"user_id": user_id, "service": service},
        {"$set": {
            "user_id": user_id, "service": service, "connected": True, "scopes": scopes,
            "access_token": creds.token, "refresh_token": creds.refresh_token,
            "connected_at": datetime.utcnow(),
        }}, upsert=True,
    )
    return RedirectResponse(f"{settings.FRONTEND_URL}/workspace?connected={service}")

@router.post("/local_folder")
async def connect_local_folder(body: LocalFolderBody, current=Depends(get_current_user)):
    if not os.path.isdir(body.folder_path):
        raise HTTPException(status_code=400, detail="Folder does not exist on the server")
    db = get_db()
    await db.connections.update_one(
        {"user_id": current["user_id"], "service": "local_folder"},
        {"$set": {
            "user_id": current["user_id"], "service": "local_folder", "connected": True,
            "metadata": {"folder_path": body.folder_path}, "connected_at": datetime.utcnow(),
        }}, upsert=True,
    )
    start_watching(current["user_id"], body.folder_path)
    return {"key": "local_folder", "connected": True, "folder_path": body.folder_path}

@router.post("/{key}/disconnect")
async def disconnect(key: str, current=Depends(get_current_user)):
    await disconnect_service(current["user_id"], key)
    return {"key": key, "connected": False}
