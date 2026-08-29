"""Notifications: assignment/exam/placement alerts surfaced to the student."""
from fastapi import APIRouter, Depends
from app.core.security import get_current_user
from app.db.mongo import get_db

router = APIRouter(prefix="/notifications", tags=["notifications"])

@router.get("")
async def list_notifications(current=Depends(get_current_user)):
    db = get_db()
    items = await db.notifications.find(
        {"user_id": current["user_id"]}
    ).sort("created_at", -1).to_list(length=100)
    for n in items:
        n.pop("_id", None)
    return items

@router.post("/{notification_id}/read")
async def mark_read(notification_id: str, current=Depends(get_current_user)):
    db = get_db()
    await db.notifications.update_one(
        {"id": notification_id, "user_id": current["user_id"]}, {"$set": {"read": True}}
    )
    return {"id": notification_id, "read": True}
