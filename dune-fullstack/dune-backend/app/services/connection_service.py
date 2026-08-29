from typing import List, Dict, Any
from app.db.mongo import get_db

SERVICE_SCOPES: Dict[str, List[str]] = {
    "gmail": ["https://www.googleapis.com/auth/gmail.readonly", "https://www.googleapis.com/auth/gmail.send"],
    "calendar": ["https://www.googleapis.com/auth/calendar"],
    "google_calendar": ["https://www.googleapis.com/auth/calendar"],
    "drive": ["https://www.googleapis.com/auth/drive.readonly"],
    "google_drive": ["https://www.googleapis.com/auth/drive.readonly"],
    "lms": ["lms.assignments.read", "lms.grades.read"],
    "local_folder": ["filesystem.read"]
}

async def list_connections(user_id: str) -> List[Dict[str, Any]]:
    db = get_db()
    cursor = db.connections.find({"user_id": user_id})
    conns = await cursor.to_list(length=50)
    for c in conns:
        c.pop("_id", None)
    
    # Ensure default catalog exists
    keys_present = {c["service"] for c in conns}
    catalog = [
        {"service": "google_drive", "name": "Google Drive", "description": "Sync lecture notes, PDFs, and slide decks", "connected": False},
        {"service": "calendar", "name": "Google Calendar", "description": "Auto-schedule study sessions & track exams", "connected": False},
        {"service": "gmail", "name": "Gmail", "description": "Parse professor announcements & campus alerts", "connected": False},
        {"service": "lms", "name": "Canvas / LMS", "description": "Import syllabus, deadlines & grades", "connected": False},
        {"service": "local_folder", "name": "Local Directory", "description": "Watch local study folder on disk", "connected": False},
    ]
    
    result = []
    for item in catalog:
        matching = next((c for c in conns if c["service"] == item["service"]), None)
        if matching:
            result.append({**item, **matching})
        else:
            result.append(item)
    return result

async def disconnect_service(user_id: str, key: str):
    db = get_db()
    await db.connections.update_one(
        {"user_id": user_id, "service": key},
        {"$set": {"connected": False, "status": "disconnected"}}
    )
