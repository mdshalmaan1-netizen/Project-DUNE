import os
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from app.db.mongo import get_db
from app.services.extraction_service import extract_and_structure_file
from app.services.chroma_service import index_chunks_in_chroma

def extract_text_from_file(file_path: str, original_filename: str, api_key: str = "") -> tuple[str, List[Dict[str, Any]]]:
    """
    Extracts text, preserves Markdown tables, applies Gemini Vision OCR for images/scanned pages,
    and returns structure-aware semantic chunks with page numbers and headings.
    """
    return extract_and_structure_file(file_path, original_filename, api_key=api_key)

async def index_file(user_id: str, file_path: str, filename: str, source: str = "upload", api_key: Optional[str] = None) -> dict:
    """
    Parses, vectors, and indexes a real document into ChromaDB (vector store)
    and MongoDB (document metadata) for accurate hybrid RAG retrieval.
    """
    db = get_db()
    full_text, chunks = extract_and_structure_file(file_path, filename, api_key=api_key or "")
    doc_id = str(uuid.uuid4())

    # 1. Index into ChromaDB with user_id isolation and rich metadata
    try:
        index_chunks_in_chroma(
            user_id=user_id,
            file_id=doc_id,
            file_name=filename,
            chunks=chunks,
            api_key=api_key
        )
    except Exception as e:
        print(f"[ChromaDB Indexing Warning for {filename}]: {e}")

    # 2. Persist document metadata in MongoDB
    doc_item = {
        "id": doc_id,
        "user_id": user_id,
        "title": filename,
        "file_path": file_path,
        "source": source,
        "status": "indexed",
        "chunk_count": len(chunks),
        "full_text_preview": full_text[:4000],
        "chunks": chunks,
        "full_text": full_text,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }

    await db.documents.insert_one(doc_item)
    doc_copy = dict(doc_item)
    doc_copy.pop("_id", None)
    return doc_copy
