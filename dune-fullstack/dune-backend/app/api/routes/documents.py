"""Matches frontend documentsApi: list / indexStatus. Also exposes manual
upload for files not covered by a watched folder (e.g. drag-and-drop)."""
import os, shutil, uuid
from fastapi import APIRouter, Depends, UploadFile, File
from app.core.security import get_current_user
from app.db.mongo import get_db
from app.services.ingestion_service import index_file

router = APIRouter(prefix="/documents", tags=["documents"])
UPLOAD_DIR = "./student_uploads"

@router.get("")
async def list_documents(current=Depends(get_current_user)):
    db = get_db()
    docs = await db.documents.find(
        {"user_id": current["user_id"], "status": {"$ne": "deleted"}}
    ).sort("updated_at", -1).to_list(length=200)
    for d in docs:
        d.pop("_id", None)
    return docs

@router.get("/index-status")
async def index_status(current=Depends(get_current_user)):
    db = get_db()
    user_id = current["user_id"]
    doc_count = await db.documents.count_documents({"user_id": user_id, "status": "indexed"})
    pending = await db.documents.count_documents({"user_id": user_id, "status": {"$in": ["pending", "indexing"]}})
    pipeline = [{"$match": {"user_id": user_id, "status": "indexed"}},
                {"$group": {"_id": None, "total": {"$sum": "$chunk_count"}}}]
    agg = await db.documents.aggregate(pipeline).to_list(length=1)
    chunk_count = agg[0]["total"] if agg else 0
    last_doc = await db.documents.find_one({"user_id": user_id}, sort=[("updated_at", -1)])
    return {
        "docCount": doc_count, "chunkCount": chunk_count, "upToDate": pending == 0,
        "lastChangeLabel": last_doc["filename"] if last_doc else None,
    }

@router.post("/upload")
async def upload_document(file: UploadFile = File(...), current=Depends(get_current_user)):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    clean_filename = file.filename or "uploaded_document.pdf"
    dest = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}_{clean_filename}")
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    doc = await index_file(
        user_id=current["user_id"],
        file_path=dest,
        filename=clean_filename,
        source="upload"
    )
    return doc
