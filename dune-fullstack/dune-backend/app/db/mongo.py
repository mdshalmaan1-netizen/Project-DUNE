"""
Real MongoDB client for DUNE AI.
Connects to mongodb://localhost:27017/dune_ai
Falls back to in-memory mock if MongoDB is not available.
"""
import copy, asyncio
from typing import Dict, List, Any, Optional

# Try to import Motor (async MongoDB driver)
try:
    from motor.motor_asyncio import AsyncIOMotorClient
    MOTOR_AVAILABLE = True
except ImportError:
    MOTOR_AVAILABLE = False

from app.core.config import settings

# ─────────────────────────────────────────────────────────────
#  Real Motor-backed collection / database wrappers
# ─────────────────────────────────────────────────────────────
class MotorCollectionWrapper:
    """Thin wrapper around Motor collection that matches the MockCollection API."""
    def __init__(self, col):
        self._col = col

    async def insert_one(self, doc: Dict[str, Any]):
        result = await self._col.insert_one(doc)
        return doc

    async def find_one(self, query: Dict[str, Any], **kwargs) -> Optional[Dict[str, Any]]:
        doc = await self._col.find_one(query, **kwargs)
        if doc:
            doc.pop("_id", None)
        return doc

    def find(self, query: Optional[Dict[str, Any]] = None, **kwargs):
        return MotorCursorWrapper(self._col, query or {}, **kwargs)

    async def update_one(self, query: Dict[str, Any], update: Dict[str, Any], upsert: bool = False):
        result = await self._col.update_one(query, update, upsert=upsert)
        return result

    async def count_documents(self, query: Dict[str, Any]) -> int:
        return await self._col.count_documents(query)

    async def delete_one(self, query: Dict[str, Any]):
        return await self._col.delete_one(query)

    def aggregate(self, pipeline: List[Dict[str, Any]], **kwargs):
        return self._col.aggregate(pipeline, **kwargs)

    async def distinct(self, key: str, query: Optional[Dict[str, Any]] = None):
        return await self._col.distinct(key, query or {})

    def __getattr__(self, name: str):
        return getattr(self._col, name)


class MotorCursorWrapper:
    def __init__(self, col, query: Dict[str, Any], **kwargs):
        self._col = col
        self._query = query
        self._kwargs = kwargs
        self._sort_key = None
        self._sort_dir = 1
        self._limit = None

    def sort(self, key: str, direction: int = 1):
        self._sort_key = key
        self._sort_dir = direction
        return self

    def limit(self, count: int):
        self._limit = count
        return self

    async def to_list(self, length: int = 100) -> List[Dict[str, Any]]:
        cursor = self._col.find(self._query, **self._kwargs)
        if self._sort_key:
            cursor = cursor.sort(self._sort_key, self._sort_dir)
        actual_len = self._limit if self._limit is not None else length
        cursor = cursor.limit(actual_len)
        docs = await cursor.to_list(length=actual_len)
        for d in docs:
            d.pop("_id", None)
        return docs


class MotorDatabase:
    """Real async MongoDB database using Motor."""
    def __init__(self, motor_db, client=None):
        self._db = motor_db
        self._client = client
        self.users         = MotorCollectionWrapper(motor_db["users"])
        self.chat_history  = MotorCollectionWrapper(motor_db["chat_history"])
        self.actions       = MotorCollectionWrapper(motor_db["actions"])
        self.documents     = MotorCollectionWrapper(motor_db["documents"])
        self.notifications = MotorCollectionWrapper(motor_db["notifications"])
        self.connections   = MotorCollectionWrapper(motor_db["connections"])
        self.memories      = MotorCollectionWrapper(motor_db["memories"])

    def __getitem__(self, name: str):
        return MotorCollectionWrapper(self._db[name])


# ─────────────────────────────────────────────────────────────
#  In-memory mock (fallback when MongoDB is unavailable)
# ─────────────────────────────────────────────────────────────
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
            if all(item.get(k) == v for k, v in query.items()):
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
                        match = False; break
                elif item.get(k) != v:
                    match = False; break
            if match:
                count += 1
        return count

    async def delete_one(self, query: Dict[str, Any]):
        for i, item in enumerate(self.data):
            if all(item.get(k) == v for k, v in query.items()):
                self.data.pop(i)
                return {"deleted": 1}
        return {"deleted": 0}


class MockCursor:
    def __init__(self, data: List[Dict[str, Any]], query: Dict[str, Any]):
        self.results = []
        for item in data:
            match = True
            for k, v in query.items():
                if isinstance(v, dict) and "$ne" in v:
                    if item.get(k) == v["$ne"]:
                        match = False; break
                elif item.get(k) != v:
                    match = False; break
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
        self.users         = MockCollection("users")
        self.chat_history  = MockCollection("chat_history")
        self.actions       = MockCollection("actions")
        self.documents     = MockCollection("documents")
        self.notifications = MockCollection("notifications")
        self.connections   = MockCollection("connections")
        self.memories      = MockCollection("memories")
        self._seed()

    def _seed(self):
        self.notifications.data.extend([
            {"id": "notif-1", "user_id": "default-student-1",
             "title": "ML Assignment Due", "message": "Neural Network problem set is due in 48 hours.",
             "type": "assignment", "read": False, "created_at": "2026-10-01T18:00:00Z"},
        ])
        self.connections.data.extend([
            {"user_id": "default-student-1", "service": "gmail",            "connected": False, "status": "disconnected"},
            {"user_id": "default-student-1", "service": "whatsapp",         "connected": False, "status": "disconnected"},
            {"user_id": "default-student-1", "service": "google_classroom",  "connected": False, "status": "disconnected"},
            {"user_id": "default-student-1", "service": "google_drive",      "connected": False, "status": "disconnected"},
        ])


# ─────────────────────────────────────────────────────────────
#  Singleton — attempt real MongoDB, fallback to mock
# ─────────────────────────────────────────────────────────────
_db_instance = None
_client_instance = None

def _init_db():
    global _db_instance, _client_instance
    if _db_instance is not None:
        return _db_instance

    if MOTOR_AVAILABLE:
        try:
            # Normalize URI to 127.0.0.1 on Windows to bypass IPv6 DNS resolution latency/issues
            uri = settings.MONGO_URI or "mongodb://127.0.0.1:27017"
            if "localhost" in uri:
                uri = uri.replace("localhost", "127.0.0.1")
            client = AsyncIOMotorClient(
                uri,
                serverSelectionTimeoutMS=2500
            )
            motor_db = client[settings.MONGO_DB_NAME]
            _client_instance = client
            _db_instance = MotorDatabase(motor_db, client=client)
            print(f"[DUNE] [OK] Connected to MongoDB at {settings.MONGO_URI} / {settings.MONGO_DB_NAME}")
        except Exception as e:
            print(f"[DUNE] [WARN] MongoDB connection error ({e}). Using in-memory fallback.")
            _db_instance = MockDatabase()
    else:
        print("[DUNE] [WARN] motor not installed. Using in-memory fallback.")
        _db_instance = MockDatabase()

    return _db_instance


def get_db():
    return _init_db()


async def check_mongo_status() -> Dict[str, Any]:
    """Test actual connectivity to MongoDB."""
    db = get_db()
    if isinstance(db, MotorDatabase) and db._client:
        try:
            # Issue a real ping command to verify live MongoDB server
            await asyncio.wait_for(db._client.admin.command('ping'), timeout=2.0)
            return {
                "connected": True,
                "status": "online",
                "uri": settings.MONGO_URI,
                "database": settings.MONGO_DB_NAME,
                "type": "MongoDB (Motor Async Driver)",
                "collections": ["users", "chat_history", "documents", "connections", "notifications", "actions", "memories"]
            }
        except Exception as e:
            return {
                "connected": False,
                "status": "unreachable",
                "error": str(e),
                "uri": settings.MONGO_URI,
                "fallback": "MockDatabase (active)"
            }
    return {
        "connected": False,
        "status": "mock",
        "uri": settings.MONGO_URI,
        "fallback": "MockDatabase (active)"
    }

