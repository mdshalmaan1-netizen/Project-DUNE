import os
import re
import uuid
import requests
from typing import List, Dict, Any, Optional
try:
    import chromadb
    from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    Documents = Any
    EmbeddingFunction = object
    Embeddings = Any

from app.core.config import settings

CHROMA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "chroma_storage"))

class GeminiEmbeddingFunction(EmbeddingFunction):
    """Generates high-dimensional semantic embeddings via Google Gemini Embedding API."""
    def __init__(self, api_key: str):
        self.api_key = api_key

    def __call__(self, input: Documents) -> Embeddings:
        embeddings = []
        key = self.api_key or settings.GEMINI_API_KEY
        for text in input:
            cleaned = text.strip()[:2048]
            if not cleaned:
                embeddings.append([0.0] * 3072)
                continue
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key={key}"
                resp = requests.post(url, json={"content": {"parts": [{"text": cleaned}]}}, timeout=12)
                if resp.status_code == 200:
                    val = resp.json().get("embedding", {}).get("values", [])
                    if val:
                        embeddings.append(val)
                    else:
                        embeddings.append([0.0] * 3072)
                else:
                    embeddings.append([0.0] * 3072)
            except Exception as e:
                print(f"[GeminiEmbedding Error]: {e}")
                embeddings.append([0.0] * 3072)
        return embeddings

_chroma_client = None

def get_chroma_client():
    global _chroma_client
    if not CHROMA_AVAILABLE:
        return None
    if _chroma_client is None:
        os.makedirs(CHROMA_DIR, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
    return _chroma_client

def get_collection(api_key: Optional[str] = None):
    if not CHROMA_AVAILABLE:
        return None
    client = get_chroma_client()
    if not client:
        return None
    key = api_key or settings.GEMINI_API_KEY
    fn = GeminiEmbeddingFunction(key)
    return client.get_or_create_collection(name="dune_academic_docs", embedding_function=fn)

def index_chunks_in_chroma(
    user_id: str,
    file_id: str,
    file_name: str,
    chunks: List[Dict[str, Any]],
    api_key: Optional[str] = None
):
    """
    Stores structured chunks in ChromaDB with strict user_id scoping and rich metadata.
    """
    if not CHROMA_AVAILABLE or not chunks:
        return
    col = get_collection(api_key)
    if not col:
        return

    docs = []
    ids = []
    metadatas = []

    for c in chunks:
        chunk_text = c.get("text", "").strip()
        if not chunk_text:
            continue
        c_id = c.get("chunk_id") or str(uuid.uuid4())
        docs.append(chunk_text)
        ids.append(f"{file_id}_{c_id}")
        metadatas.append({
            "user_id": str(user_id),
            "file_id": str(file_id),
            "file_name": str(file_name),
            "page_number": int(c.get("page", 1)),
            "section": str(c.get("section", "")),
            "heading": str(c.get("heading", "")),
            "is_table": str(c.get("is_table", False)),
            "document_type": str(c.get("document_type", "document"))
        })

    if docs:
        col.upsert(documents=docs, ids=ids, metadatas=metadatas)

def delete_user_file_from_chroma(user_id: str, file_id: str, api_key: Optional[str] = None):
    """Deletes all chunks belonging to a specific file for an authenticated user."""
    try:
        col = get_collection(api_key)
        col.delete(where={"$and": [{"user_id": {"$eq": str(user_id)}}, {"file_id": {"$eq": str(file_id)}}]})
    except Exception as e:
        print(f"[Chroma Delete Error]: {e}")

def hybrid_chroma_retrieval(
    user_id: str,
    query: str,
    top_k: int = 8,
    file_filter: Optional[str] = None,
    api_key: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Hybrid semantic + exact keyword retrieval strictly isolated to user_id.
    Handles exact names, dates, numbers, marks, schedules, and definitions.
    """
    if not CHROMA_AVAILABLE:
        return []
    col = get_collection(api_key)
    if not col:
        return []
    where_filter: Dict[str, Any] = {"user_id": {"$eq": str(user_id)}}
    if file_filter:
        where_filter = {"$and": [{"user_id": {"$eq": str(user_id)}}, {"file_id": {"$eq": str(file_filter)}}]}

    results = []
    try:
        vector_res = col.query(
            query_texts=[query],
            n_results=min(top_k * 2, 25),
            where=where_filter
        )
    except Exception as e:
        print(f"[Chroma Query Error]: {e}")
        return []

    docs = vector_res.get("documents", [[]])[0]
    metas = vector_res.get("metadatas", [[]])[0]
    dists = vector_res.get("distances", [[]])[0] if vector_res.get("distances") else [0.0] * len(docs)

    # Keyword / exact tokens for hybrid reranking
    lowered_q = query.lower()
    raw_tokens = [t for t in re.findall(r'\b\w{2,}\b', lowered_q)
                  if t not in {"the","and","for","with","what","from","this","that","have","your","are","you","can","how","tell","about","please","just"}]
    # Also extract potential numbers, dates, codes (e.g. "95", "unit 3", "october 15")
    numbers_dates = re.findall(r'\b(?:\d+|october|november|december|january|february|march|april|may|june|july|august|september|unit|chapter|grade|marks?|deadline)\b', lowered_q)

    scored_chunks = []
    for i, doc in enumerate(docs):
        meta = metas[i] if i < len(metas) else {}
        doc_lower = doc.lower()
        title_lower = meta.get("file_name", "").lower()
        heading_lower = meta.get("heading", "").lower()

        # Vector score component
        dist = dists[i] if i < len(dists) else 1.0
        vec_score = 1.0 / (1.0 + max(0.0, dist))

        # Lexical score component
        exact_hits = sum(1 for t in raw_tokens if t in doc_lower)
        num_hits = sum(2 for nd in numbers_dates if nd in doc_lower)
        title_hits = sum(3 for t in raw_tokens if t in title_lower)
        heading_hits = sum(2 for t in raw_tokens if t in heading_lower)

        lex_score = (exact_hits + num_hits + title_hits + heading_hits)

        # Check table priority for data queries
        if meta.get("is_table") == "True" and any(k in lowered_q for k in ["table", "mark", "grade", "score", "schedule", "timetable", "who", "compare"]):
            lex_score += 4

        # Reciprocal Rank / Combined Score
        total_score = (vec_score * 5.0) + lex_score
        scored_chunks.append({
            "text": doc,
            "title": meta.get("file_name", "Document"),
            "file_id": meta.get("file_id", ""),
            "page": meta.get("page_number", 1),
            "section": meta.get("section", ""),
            "heading": meta.get("heading", ""),
            "is_table": meta.get("is_table") == "True",
            "score": total_score
        })

    scored_chunks.sort(key=lambda x: x["score"], reverse=True)
    return scored_chunks[:top_k]
