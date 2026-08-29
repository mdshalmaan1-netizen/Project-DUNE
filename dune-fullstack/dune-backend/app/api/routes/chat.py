"""Matches frontend chatApi: sendMessage, confirmAction."""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from app.core.security import get_current_user
from app.db.mongo import get_db
from app.db.models import ChatMessage
from app.agent.agent import process_message, confirm_action

router = APIRouter(prefix="/chat", tags=["chat"])

class SendMessageBody(BaseModel):
    text: str
    conversation_id: Optional[str] = None
    history: Optional[List[dict]] = None
    apiKey: Optional[str] = None
    gemini_api_key: Optional[str] = None

class ConfirmActionBody(BaseModel):
    actionId: str

@router.post("")
async def send_message(body: SendMessageBody, current=Depends(get_current_user)):
    db = get_db()
    user_id = current["user_id"]
    conversation_id = body.conversation_id or str(uuid.uuid4())
    api_key = body.gemini_api_key or body.apiKey

    user_msg = ChatMessage(user_id=user_id, conversation_id=conversation_id, role="user", text=body.text)
    await db.chat_history.insert_one(user_msg.model_dump())

    result = await process_message(user_id, conversation_id, body.text, body.history, api_key=api_key)

    assistant_msg = ChatMessage(
        user_id=user_id, conversation_id=conversation_id, role="assistant",
        text=result["text"], trace=result["trace"], citations=result["citations"],
        pending_action=result["pending_action"],
    )
    await db.chat_history.insert_one(assistant_msg.model_dump())

    return {
        "id": assistant_msg.id, "role": "assistant", "text": result["text"],
        "trace": result["trace"], "citations": result["citations"],
        "pendingAction": result["pending_action"], "conversationId": conversation_id,
    }

@router.post("/confirm-action")
async def confirm(body: ConfirmActionBody, current=Depends(get_current_user)):
    try:
        result = await confirm_action(current["user_id"], body.actionId)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute action: {e}")

@router.get("/history/{conversation_id}")
async def get_history(conversation_id: str, current=Depends(get_current_user)):
    db = get_db()
    msgs = await db.chat_history.find(
        {"user_id": current["user_id"], "conversation_id": conversation_id}
    ).sort("created_at", 1).to_list(length=500)
    for m in msgs:
        m.pop("_id", None)
    return msgs
