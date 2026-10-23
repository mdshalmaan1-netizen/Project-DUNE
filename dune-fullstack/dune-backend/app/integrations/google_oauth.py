"""
Real Google OAuth 2.0 Integration for DUNE.
Handles OAuth authorization URL generation, code-to-token exchange via Google's token endpoint,
automatic token refresh, user profile retrieval, and MongoDB token storage.
"""
import time
import urllib.parse
from typing import List, Dict, Any, Optional, Union
import requests
from app.core.config import settings

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

# Comprehensive Academic Student Scopes
DEFAULT_GOOGLE_SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.students.readonly",
    "https://www.googleapis.com/auth/classroom.announcements.readonly",
    "https://www.googleapis.com/auth/classroom.courseworkmaterials.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/calendar",
]

SERVICE_DEFAULT_SCOPES = {
    "gmail": [
        "openid",
        "email",
        "profile",
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send",
    ],
    "google_classroom": [
        "openid",
        "email",
        "profile",
        "https://www.googleapis.com/auth/classroom.courses.readonly",
        "https://www.googleapis.com/auth/classroom.coursework.students.readonly",
        "https://www.googleapis.com/auth/classroom.announcements.readonly",
        "https://www.googleapis.com/auth/classroom.courseworkmaterials.readonly",
    ],
    "google_drive": [
        "openid",
        "email",
        "profile",
        "https://www.googleapis.com/auth/drive.readonly",
    ],
    "calendar": [
        "openid",
        "email",
        "https://www.googleapis.com/auth/calendar",
    ],
    "google_calendar": [
        "openid",
        "email",
        "https://www.googleapis.com/auth/calendar",
    ],
    "google": DEFAULT_GOOGLE_SCOPES,
}


class OAuthCredentials:
    """
    Credentials container that supports both object attribute access (.token, .refresh_token)
    and dict-like access (creds['access_token']) for maximum compatibility.
    """
    def __init__(
        self,
        token: str,
        refresh_token: Optional[str] = None,
        expires_in: int = 3600,
        token_type: str = "Bearer",
        id_token: Optional[str] = None,
        scope: Optional[str] = None,
        raw: Optional[Dict[str, Any]] = None
    ):
        self.token = token
        self.access_token = token
        self.refresh_token = refresh_token
        self.expires_in = expires_in
        self.expires_at = int(time.time()) + int(expires_in)
        self.token_type = token_type
        self.id_token = id_token
        self.scope = scope
        self.raw = raw or {}

    def __getitem__(self, item: str):
        if item in ("access_token", "token"):
            return self.access_token
        if item == "refresh_token":
            return self.refresh_token
        if item == "expires_in":
            return self.expires_in
        if item == "expires_at":
            return self.expires_at
        if item in self.raw:
            return self.raw[item]
        raise KeyError(item)

    def get(self, item: str, default: Any = None):
        try:
            return self[item]
        except KeyError:
            return default

    def to_dict(self) -> Dict[str, Any]:
        return {
            "access_token": self.access_token,
            "token": self.token,
            "refresh_token": self.refresh_token,
            "expires_in": self.expires_in,
            "expires_at": self.expires_at,
            "token_type": self.token_type,
            "id_token": self.id_token,
            "scope": self.scope,
            **self.raw
        }


import logging

logger = logging.getLogger("google_oauth")

def _mask_client_id(client_id: str) -> str:
    if not client_id or len(client_id) < 12:
        return "***"
    return f"{client_id[:8]}...{client_id[-10:]}"


def get_authorization_url(
    scopes: Optional[List[str]] = None,
    state: str = "default_state",
    redirect_uri: Optional[str] = None,
    access_type: str = "offline",
    prompt: str = "select_account consent"
) -> str:
    """
    Generates the genuine Google OAuth 2.0 authorization URL.
    Includes prompt='select_account' so users can choose their intended Google account,
    while preserving 'consent' flow and offline access to ensure a refresh_token is issued.
    """
    selected_scopes = scopes or DEFAULT_GOOGLE_SCOPES
    scope_str = " ".join(selected_scopes)
    client_id = settings.GOOGLE_CLIENT_ID
    r_uri = (redirect_uri or settings.GOOGLE_REDIRECT_URI).strip()

    logger.info(
        f"[Google OAuth] Generating authorization URL: client_id={_mask_client_id(client_id)}, "
        f"redirect_uri={r_uri}, scopes_count={len(selected_scopes)}"
    )

    # Ensure select_account is present so users choose their intended Google account,
    # and consent is present when requesting offline access for refresh token issuance.
    final_prompt = prompt or "select_account consent"
    prompt_tokens = final_prompt.split()
    if "select_account" not in prompt_tokens:
        prompt_tokens.insert(0, "select_account")
    if access_type == "offline" and "consent" not in prompt_tokens:
        prompt_tokens.append("consent")
    formatted_prompt = " ".join(prompt_tokens)

    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": r_uri,
        "scope": scope_str,
        "state": state,
        "access_type": access_type,
        "prompt": formatted_prompt,
        "include_granted_scopes": "true",
    }
    return f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"


def exchange_code_for_tokens(
    code: str,
    scopes: Optional[List[str]] = None,
    state: Optional[str] = None,
    redirect_uri: Optional[str] = None
) -> Optional[OAuthCredentials]:
    """
    Exchanges an authorization code for genuine access_token and refresh_token
    via Google's OAuth 2.0 token endpoint.
    Signature accommodates (code, redirect_uri) and (code, scopes, state, redirect_uri).
    """
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        logger.error("[Google OAuth] Error: GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET not configured in environment.")
        return None

    r_uri = (redirect_uri or settings.GOOGLE_REDIRECT_URI).strip()
    masked_cid = _mask_client_id(settings.GOOGLE_CLIENT_ID)
    logger.info(f"[Google OAuth] Initiating token exchange: client_id={masked_cid}, redirect_uri={r_uri}")

    payload = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": r_uri,
    }

    try:
        resp = requests.post(GOOGLE_TOKEN_URL, data=payload, timeout=15)
        if resp.status_code == 200:
            token_data = resp.json()
            token_type = token_data.get("token_type", "Bearer")
            expires_in = token_data.get("expires_in", 3600)
            has_refresh = bool(token_data.get("refresh_token"))
            logger.info(
                f"[Google OAuth] Token exchange successful (HTTP 200). "
                f"token_type={token_type}, expires_in={expires_in}s, has_refresh_token={has_refresh}"
            )
            creds = OAuthCredentials(
                token=token_data.get("access_token", ""),
                refresh_token=token_data.get("refresh_token"),
                expires_in=expires_in,
                token_type=token_type,
                id_token=token_data.get("id_token"),
                scope=token_data.get("scope"),
                raw=token_data
            )
            return creds
        else:
            # Parse error details safely without leaking any credentials
            err_code = "unknown_error"
            err_desc = ""
            try:
                err_json = resp.json()
                err_code = err_json.get("error", "unknown_error")
                err_desc = err_json.get("error_description", "")
            except Exception:
                err_desc = f"HTTP status {resp.status_code}"

            logger.error(
                f"[Google OAuth] Token exchange failed (HTTP {resp.status_code}): "
                f"error='{err_code}', description='{err_desc}', redirect_uri='{r_uri}'"
            )

            # If error is redirect_uri_mismatch, attempt retry with canonical variations
            # (e.g. trailing slash difference or localhost vs 127.0.0.1)
            if err_code == "redirect_uri_mismatch":
                candidate_uris = []
                if r_uri.endswith("/"):
                    candidate_uris.append(r_uri.rstrip("/"))
                else:
                    candidate_uris.append(r_uri + "/")
                if "localhost" in r_uri:
                    candidate_uris.append(r_uri.replace("localhost", "127.0.0.1"))
                elif "127.0.0.1" in r_uri:
                    candidate_uris.append(r_uri.replace("127.0.0.1", "localhost"))

                for alt_uri in candidate_uris:
                    logger.info(f"[Google OAuth] Retrying token exchange with alternative redirect_uri='{alt_uri}'")
                    retry_payload = {**payload, "redirect_uri": alt_uri}
                    try:
                        alt_resp = requests.post(GOOGLE_TOKEN_URL, data=retry_payload, timeout=15)
                        if alt_resp.status_code == 200:
                            alt_data = alt_resp.json()
                            logger.info(f"[Google OAuth] Token exchange succeeded with alternative redirect_uri='{alt_uri}'")
                            return OAuthCredentials(
                                token=alt_data.get("access_token", ""),
                                refresh_token=alt_data.get("refresh_token"),
                                expires_in=alt_data.get("expires_in", 3600),
                                token_type=alt_data.get("token_type", "Bearer"),
                                id_token=alt_data.get("id_token"),
                                scope=alt_data.get("scope"),
                                raw=alt_data
                            )
                    except Exception:
                        pass
            return None
    except requests.exceptions.RequestException as e:
        logger.error(f"[Google OAuth] Network exception during token exchange: {type(e).__name__}: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"[Google OAuth] Unexpected exception during token exchange: {type(e).__name__}: {str(e)}")
        return None
        return None


def refresh_access_token(refresh_token: str) -> Optional[Dict[str, Any]]:
    """
    Uses the long-lived refresh_token to obtain a fresh access_token from Google.
    """
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET or not refresh_token:
        logger.error("[Google OAuth] Cannot refresh token: missing client credentials or refresh_token.")
        return None

    masked_cid = _mask_client_id(settings.GOOGLE_CLIENT_ID)
    logger.info(f"[Google OAuth] Refreshing expired access token with Google. client_id={masked_cid}")

    payload = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }

    try:
        resp = requests.post(GOOGLE_TOKEN_URL, data=payload, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            expires_in = data.get("expires_in", 3600)
            logger.info(f"[Google OAuth] Access token refreshed successfully. expires_in={expires_in}s")
            return data
        else:
            err_code = "unknown_error"
            err_desc = ""
            try:
                err_json = resp.json()
                err_code = err_json.get("error", "unknown_error")
                err_desc = err_json.get("error_description", "")
            except Exception:
                err_desc = f"HTTP status {resp.status_code}"

            logger.error(f"[Google OAuth] Token refresh failed (HTTP {resp.status_code}): error='{err_code}', description='{err_desc}'")
            return None
    except Exception as e:
        logger.error(f"[Google OAuth] Token refresh exception: {type(e).__name__}: {str(e)}")
        return None


def get_user_info(access_token: str) -> Optional[Dict[str, Any]]:
    """Fetches user profile information (email, name, picture) using the access token."""
    try:
        resp = requests.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json()
        # Fallback to OpenID v3 userinfo endpoint
        resp_v3 = requests.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10
        )
        if resp_v3.status_code == 200:
            return resp_v3.json()
    except Exception as e:
        logger.warning(f"[Google OAuth] Failed to get userinfo: {e}")
    return None


async def get_valid_google_token(db, user_id: str, service: Optional[str] = None) -> Optional[str]:
    """
    Retrieves a valid Google access token for the user.
    If the access token is close to expiry or expired, it automatically refreshes it
    using the stored refresh_token and persists the new token in MongoDB.
    """
    conn = None
    if service:
        conn = await db.connections.find_one({"user_id": user_id, "service": service, "connected": True})

    if not conn:
        # Check general Google connection or family services
        for svc_name in ["google", "google_classroom", "gmail", "google_drive", "calendar", "google_calendar"]:
            conn = await db.connections.find_one({"user_id": user_id, "service": svc_name, "connected": True})
            if conn and conn.get("access_token"):
                break

    if not conn or not conn.get("connected"):
        return None

    access_token = conn.get("access_token")
    expires_at = conn.get("expires_at", 0)
    refresh_token = conn.get("refresh_token")

    now = int(time.time())
    # If token expires within 3 minutes and refresh_token exists, refresh it automatically
    if refresh_token and (not expires_at or expires_at - now < 180):
        fresh = refresh_access_token(refresh_token)
        if fresh and "access_token" in fresh:
            new_access_token = fresh["access_token"]
            new_expires_in = fresh.get("expires_in", 3600)
            new_expires_at = now + new_expires_in

            await db.connections.update_many(
                {
                    "user_id": user_id,
                    "service": {"$in": ["google", "google_classroom", "gmail", "google_drive", "calendar", "google_calendar"]}
                },
                {"$set": {
                    "access_token": new_access_token,
                    "expires_at": new_expires_at,
                    "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                }}
            )
            return new_access_token

    return access_token


async def store_google_connection(
    db,
    user_id: str,
    service: str,
    creds: OAuthCredentials,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Stores genuine OAuth credentials in MongoDB for the given user and service.
    Propagates tokens across related Google family services if granted comprehensive scopes.
    """
    meta = metadata or {}
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # Try to enrich with user info if not present
    if "email" not in meta and creds.access_token:
        info = get_user_info(creds.access_token)
        if info:
            meta["email"] = info.get("email")
            meta["name"] = info.get("name")
            meta["picture"] = info.get("picture")

    # If email still not found in meta, inspect id_token payload
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

    doc = {
        "user_id": user_id,
        "service": service,
        "connected": True,
        "status": "active",
        "auth_type": "oauth",
        "access_token": creds.access_token,
        "refresh_token": creds.refresh_token,
        "expires_at": creds.expires_at,
        "scopes": creds.scope.split(" ") if creds.scope else DEFAULT_GOOGLE_SCOPES,
        "metadata": meta,
        "connected_at": now_iso,
        "updated_at": now_iso,
    }

    await db.connections.update_one(
        {"user_id": user_id, "service": service},
        {"$set": doc},
        upsert=True
    )
    return doc
