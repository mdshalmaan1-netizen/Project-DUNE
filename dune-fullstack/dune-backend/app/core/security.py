import hashlib
import hmac
import time
import json
import base64
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings

security_scheme = HTTPBearer(auto_error=False)

def hash_password(password: str) -> str:
    salt = "dune_salt_"
    return hashlib.sha256((salt + password).encode()).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return hash_password(plain_password) == hashed_password

def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode('utf-8').rstrip('=')

def _base64url_decode(data: str) -> bytes:
    rem = len(data) % 4
    if rem > 0:
        data += '=' * (4 - rem)
    return base64.urlsafe_b64decode(data.encode('utf-8'))

def create_access_token(payload: dict) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    full_payload = {
        **payload,
        "exp": now + (settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60),
        "iat": now,
    }
    
    header_b64 = _base64url_encode(json.dumps(header).encode('utf-8'))
    payload_b64 = _base64url_encode(json.dumps(full_payload).encode('utf-8'))
    
    message = f"{header_b64}.{payload_b64}".encode('utf-8')
    signature = hmac.new(settings.SECRET_KEY.encode('utf-8'), message, hashlib.sha256).digest()
    signature_b64 = _base64url_encode(signature)
    
    return f"{header_b64}.{payload_b64}.{signature_b64}"

def decode_access_token(token: str) -> Optional[dict]:
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
        header_b64, payload_b64, signature_b64 = parts
        message = f"{header_b64}.{payload_b64}".encode('utf-8')
        expected_sig = hmac.new(settings.SECRET_KEY.encode('utf-8'), message, hashlib.sha256).digest()
        actual_sig = _base64url_decode(signature_b64)
        
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None
            
        payload = json.loads(_base64url_decode(payload_b64).decode('utf-8'))
        if payload.get("exp", 0) < int(time.time()):
            return None
        return payload
    except Exception:
        return None

async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)) -> Dict[str, Any]:
    # Allow mock / dev fallback user if no auth header passed in development
    if not credentials:
        return {"user_id": "default-student-1", "email": "student@dune.edu", "name": "Paul Atreides"}
    
    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload:
        # Fallback to dev user if token is invalid or dummy
        return {"user_id": "default-student-1", "email": "student@dune.edu", "name": "Paul Atreides"}
    
    user_id = payload.get("sub") or payload.get("user_id") or "default-student-1"
    return {"user_id": user_id, "email": payload.get("email", "student@dune.edu")}
