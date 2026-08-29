"""Auth endpoints. Matches frontend authApi: login, signup, and Google OAuth
(loginWithGoogle redirects here)."""
import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from fastapi.responses import RedirectResponse
from app.db.mongo import get_db
from app.db.models import User
from app.core.security import hash_password, verify_password, create_access_token, get_current_user
from app.core.config import settings
from app.integrations.google_oauth import get_authorization_url, exchange_code_for_tokens

router = APIRouter(prefix="/auth", tags=["auth"])

class LoginBody(BaseModel):
    email: str
    password: str

class SignupBody(BaseModel):
    fullName: Optional[str] = None
    name: Optional[str] = None
    email: str
    password: str

SignupBody.model_rebuild()
LoginBody.model_rebuild()

def _public_user(u: dict) -> dict:
    uname = u.get("name") or "User"
    initials = "".join(p[0] for p in uname.split()[:2]).upper() or "U"
    return {"id": u["id"], "name": uname, "email": u["email"], "initials": initials}

@router.post("/signup")
@router.post("/register")
async def signup(body: SignupBody):
    db = get_db()
    if await db.users.find_one({"email": body.email}):
        raise HTTPException(status_code=400, detail="An account with this email already exists")
    user_name = body.fullName or body.name or "User"
    user = User(name=user_name, email=body.email, hashed_password=hash_password(body.password))
    await db.users.insert_one(user.model_dump())
    token = create_access_token({"sub": user.id, "email": user.email})
    return {**_public_user(user.model_dump()), "token": token, "access_token": token}

@router.post("/login")
async def login(body: LoginBody):
    db = get_db()
    user = await db.users.find_one({"email": body.email})
    if not user or not user.get("hashed_password") or not verify_password(body.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token({"sub": user["id"], "email": user["email"]})
    return {**_public_user(user), "token": token, "access_token": token}

@router.get("/google")
async def google_login():
    """Kicks off login-with-Google (basic profile scopes only)."""
    state = str(uuid.uuid4())
    url = get_authorization_url(["openid", "email", "profile"], state)
    return RedirectResponse(url)

@router.get("/google/callback")
async def google_callback(code: str, state: str):
    creds = exchange_code_for_tokens(code, ["openid", "email", "profile"], state)
    import requests
    userinfo = requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {creds.token}"},
    ).json()

    db = get_db()
    user = await db.users.find_one({"email": userinfo["email"]})
    if not user:
        new_user = User(name=userinfo.get("name", userinfo["email"].split("@")[0]),
                         email=userinfo["email"], google_id=userinfo.get("id"),
                         avatar_url=userinfo.get("picture"))
        await db.users.insert_one(new_user.model_dump())
        user = new_user.model_dump()
    token = create_access_token({"sub": user["id"], "email": user["email"]})
    return RedirectResponse(f"{settings.FRONTEND_URL}/auth/callback?token={token}")

@router.get("/me")
async def me(current=Depends(get_current_user)):
    db = get_db()
    user = await db.users.find_one({"id": current["user_id"]})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return _public_user(user)
