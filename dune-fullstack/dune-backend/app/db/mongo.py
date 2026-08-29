import copy
from typing import Dict, List, Any, Optional

class MockCollection:
    def __init__(self, name: str):
        self.name = name
        self.data: List[Dict[str, Any]] = []

    async def insert_one(self, doc: Dict[str, Any]):
        doc_copy = copy.deepcopy(doc)
        if "_id" not in doc_copy:
            doc_copy["_id"] = doc_copy.get("id") or str(len(self.data) + 1)
        self.data.append(doc_copy)
        return doc_copy

    async def find_one(self, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        for item in self.data:
            match = True
            for k, v in query.items():
                if item.get(k) != v:
                    match = False
                    break
            if match:
                return copy.deepcopy(item)
        return None

    def find(self, query: Optional[Dict[str, Any]] = None):
        return MockCursor(self.data, query or {})

    async def update_one(self, query: Dict[str, Any], update: Dict[str, Any], upsert: bool = False):
        set_vals = update.get("$set", {})
        for item in self.data:
            match = True
            for k, v in query.items():
                if item.get(k) != v:
                    match = False
                    break
            if match:
                item.update(set_vals)
                return item
        if upsert:
            new_item = {**query, **set_vals}
            if "_id" not in new_item:
                new_item["_id"] = str(len(self.data) + 1)
            self.data.append(new_item)
            return new_item
        return None

    async def count_documents(self, query: Dict[str, Any]) -> int:
        count = 0
        for item in self.data:
            match = True
            for k, v in query.items():
                if k == "status" and isinstance(v, dict) and "$ne" in v:
                    if item.get(k) == v["$ne"]:
                        match = False
                        break
                elif item.get(k) != v:
                    match = False
                    break
            if match:
                count += 1
        return count

class MockCursor:
    def __init__(self, data: List[Dict[str, Any]], query: Dict[str, Any]):
        self.results = []
        for item in data:
            match = True
            for k, v in query.items():
                if isinstance(v, dict) and "$ne" in v:
                    if item.get(k) == v["$ne"]:
                        match = False
                        break
                elif item.get(k) != v:
                    match = False
                    break
            if match:
                self.results.append(copy.deepcopy(item))

    def sort(self, key: str, direction: int = 1):
        try:
            self.results.sort(key=lambda x: str(x.get(key, "")), reverse=(direction == -1))
        except Exception:
            pass
        return self

    async def to_list(self, length: int = 100) -> List[Dict[str, Any]]:
        return self.results[:length]

class MockDatabase:
    def __init__(self):
        self.users = MockCollection("users")
        self.chat_history = MockCollection("chat_history")
        self.actions = MockCollection("actions")
        self.documents = MockCollection("documents")
        self.notifications = MockCollection("notifications")
        self.connections = MockCollection("connections")
        self.memories = MockCollection("memories")
        self._seed_initial_data()

    def _seed_initial_data(self):
        # Prepopulate demo data for instant out-of-the-box readiness
        self.notifications.data.extend([
            {
                "id": "notif-1",
                "user_id": "default-student-1",
                "title": "Machine Learning Assignment 3 Due",
                "message": "Neural Network optimization problem set is due in 48 hours.",
                "type": "assignment",
                "read": False,
                "created_at": "2026-08-28T18:00:00Z"
            },
            {
                "id": "notif-2",
                "user_id": "default-student-1",
                "title": "Autonomous Systems Exam Scheduled",
                "message": "Midterm examination scheduled on Friday, Room 402.",
                "type": "exam",
                "read": False,
                "created_at": "2026-08-28T14:30:00Z"
            }
        ])
        self.documents.data.extend([
            {
                "id": "doc-1",
                "user_id": "default-student-1",
                "title": "Syllabus_Advanced_Robotics.pdf",
                "source": "Google Drive",
                "status": "indexed",
                "chunk_count": 24,
                "updated_at": "2026-08-28T12:00:00Z"
            },
            {
                "id": "doc-2",
                "user_id": "default-student-1",
                "title": "Lecture_04_State_Estimation.pdf",
                "source": "Local Upload",
                "status": "indexed",
                "chunk_count": 48,
                "updated_at": "2026-08-28T15:20:00Z"
            }
        ])
        self.connections.data.extend([
            {"user_id": "default-student-1", "service": "google_drive", "connected": True, "status": "active"},
            {"user_id": "default-student-1", "service": "calendar", "connected": True, "status": "active"},
            {"user_id": "default-student-1", "service": "gmail", "connected": False, "status": "disconnected"},
            {"user_id": "default-student-1", "service": "lms", "connected": True, "status": "active"},
        ])

_db_instance = MockDatabase()

def get_db() -> MockDatabase:
    return _db_instance
