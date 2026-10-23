from typing import List, Dict, Any
from app.db.mongo import get_db

SERVICE_SCOPES: Dict[str, List[str]] = {
    "gmail": [
        "openid",
        "email",
        "profile",
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send"
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
    "calendar": ["openid", "email", "profile", "https://www.googleapis.com/auth/calendar"],
    "google_calendar": ["openid", "email", "profile", "https://www.googleapis.com/auth/calendar"],
    "drive": ["openid", "email", "profile", "https://www.googleapis.com/auth/drive.readonly"],
    "google_drive": ["openid", "email", "profile", "https://www.googleapis.com/auth/drive.readonly"],
    "google": [
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
    ],
    "lms": ["lms.assignments.read", "lms.grades.read"],
    "local_folder": ["filesystem.read"]
}

async def list_connections(user_id: str) -> List[Dict[str, Any]]:
    db = get_db()
    cursor = db.connections.find({"user_id": user_id})
    conns = await cursor.to_list(length=50)
    for c in conns:
        c.pop("_id", None)
    
    # Ensure default catalog exists (Google Classroom, Gmail, Google Drive)
    keys_present = {c["service"] for c in conns}
    catalog = [
        {"service": "google_classroom", "name": "Google Classroom", "description": "Sync assignments, announcements, coursework & grades", "connected": False},
        {"service": "gmail", "name": "Gmail", "description": "Parse professor announcements & campus alerts", "connected": False},
        {"service": "google_drive", "name": "Google Drive", "description": "Sync lecture notes, PDFs, and slide decks", "connected": False},
        {"service": "calendar", "name": "Google Calendar", "description": "Auto-schedule study sessions & track exams", "connected": False},
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
