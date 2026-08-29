"""Matches frontend actionLogApi: list."""
from fastapi import APIRouter, Depends
from app.core.security import get_current_user
from app.db.mongo import get_db

router = APIRouter(prefix="/actions", tags=["actions"])

@router.get("")
async def list_actions(current=Depends(get_current_user)):
    db = get_db()
    actions = await db.actions.find(
        {"user_id": current["user_id"]}
    ).sort("created_at", -1).to_list(length=100)
    for a in actions:
        a.pop("_id", None)
    return actions
