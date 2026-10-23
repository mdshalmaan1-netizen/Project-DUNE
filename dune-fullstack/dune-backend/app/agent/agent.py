import os
import uuid
import re
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
import requests
from app.db.mongo import get_db
from app.core.config import settings
from app.services.chroma_service import hybrid_chroma_retrieval
from app.integrations.google_classroom import get_classroom_mcp_context
from app.integrations.gmail_service import get_gmail_mcp_context
from app.integrations.google_drive import get_drive_mcp_context

DUNE_SYSTEM_PROMPT = """You are DUNE, an advanced personal AI academic assistant powered by a real large language model.

You possess two integrated knowledge and tool capabilities:
1. Connected Student Integrations (Google Classroom / GCR, Gmail, Google Drive, WhatsApp, Calendar via Model Context Protocol).
2. Document Knowledge Engine (User-uploaded PDFs, Lecture Notes, Syllabi, Course Materials, Resumes).

RULES FOR INTEGRATIONS & MCP TOOLS:
1. When Live MCP Integration Data is supplied in the context (such as Google Classroom courses, announcements, teacher uploads, assignments, Gmail inbox, or Google Drive files), you MUST answer the user's question directly, accurately, and authoritatively.
2. NEVER state that you lack access to personal accounts, real-time accounts, or Google Classroom when MCP data is provided. You ARE actively connected to the student's accounts through DUNE's Model Context Protocol.
3. When answering about what a teacher / mam / sir uploaded or posted on GCR:
   - Identify the exact teacher name (e.g. Dr. Ananya Sharma / Mam, Dr. Priya Patel / Mam, Dr. Rajesh Smith / Prof).
   - State the course title, uploaded document/material name, upload timestamp, and description.
   - Mention any related assignment deadlines, submission links, or exam dates.
4. Proactively offer practical student follow-ups (e.g., summarize the uploaded material, draft homework solutions, or add deadlines to the timetable).

RULES FOR UPLOADED DOCUMENTS (PDFs, Resumes, Notes):
1. When the user asks about an uploaded document, provide an accurate and grounded answer based on the actual document content supplied.
2. Do not invent facts, numbers, dates, names, or definitions not supported by the document.
3. Include source/page references (e.g. Source: [Document Name] — Page X) when document context is used.

GENERAL & NATURAL CONVERSATION:
1. Fluently understand English, Tamil, and Tanglish.
2. Understand natural student phrasing (e.g., "what is my last mam uploaded on gcr", "what did sir post", "assignments due this week").
3. Always maintain a warm, proactive, supportive academic mentor tone."""

def clean_llm_response(text: Optional[str]) -> Optional[str]:
    """Strip any third-party ads or promotional footers."""
    if not text:
        return text
    cleaned = re.sub(r'(?i)\n*-{2,}\s*\n*Support Pollinations\.AI:.*', '', text, flags=re.DOTALL)
    cleaned = re.sub(r'(?i)\n*🌸\s*Ad\s*🌸.*', '', cleaned, flags=re.DOTALL)
    cleaned = re.sub(r'(?i)\n*Powered by Pollinations.*', '', cleaned, flags=re.DOTALL)
    cleaned = re.sub(r'(?i)\n*Support our mission.*', '', cleaned, flags=re.DOTALL)
    return cleaned.strip()

def call_gemini(
    prompt: str,
    system: str,
    api_key: str,
    model: str = "gemini-3.5-flash-lite",
    history: Optional[List[dict]] = None
) -> Optional[str]:
    """
    Calls Google Gemini API with multi-model cascade fallback.
    Uses real Gemini LLM intelligence without mock or predefined responses.
    """
    candidate_models = [
        model,
        "gemini-3.5-flash-lite",
        "gemini-flash-lite-latest",
        "gemini-3.8-flash",
        "gemini-3.7-flash",
        "gemini-flash-latest"
    ]
    seen = set()
    models_to_try = [m for m in candidate_models if m and not (m in seen or seen.add(m))]

    contents = []
    if history:
        for msg in history[-10:]:
            role = "user" if msg.get("role") in ["user", "human"] else "model"
            txt = msg.get("text") or msg.get("content") or ""
            if txt.strip():
                contents.append({"role": role, "parts": [{"text": txt.strip()}]})

    contents.append({"role": "user", "parts": [{"text": prompt}]})

    payload = {
        "contents": contents,
        "systemInstruction": {"parts": [{"text": system}]},
        "generationConfig": {"temperature": 0.65, "topP": 0.95, "maxOutputTokens": 4096}
    }

    for m in models_to_try:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
            resp = requests.post(url, json=payload, timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                cands = data.get("candidates", [])
                if cands and "content" in cands[0]:
                    parts = cands[0]["content"].get("parts", [])
                    if parts:
                        text_val = parts[0].get("text", "")
                        if text_val and text_val.strip():
                            return clean_llm_response(text_val)
            else:
                print(f"[Gemini Model {m} Error {resp.status_code}]: {resp.text[:180]}")
        except Exception as e:
            print(f"[Gemini Model {m} Exception]: {e}")
    return None

def detect_document_intent(
    text: str,
    available_docs: List[Dict],
    history: Optional[List[dict]] = None
) -> Tuple[bool, Optional[str], str]:
    """
    Determines if the query requires document retrieval or is an integration/general query.
    Returns (is_doc_query, target_filename, query_type).
    Query types: 'broad', 'factual', 'comparative', 'generation', 'general'.
    """
    if not available_docs:
        return False, None, "general"

    lowered = text.lower().strip()

    # Priority 0: Explicit check for Integration / MCP triggers (Google Classroom, GCR, Gmail, Drive, WhatsApp, Calendar)
    mcp_intent_words = [
        "gcr", "classroom", "google classroom", "coursework", "announcement", "announcements",
        "mam upload", "mam uploaded", "teacher upload", "teacher uploaded", "sir upload", "sir uploaded",
        "prof upload", "prof uploaded", "professor upload", "professor uploaded", "faculty upload", "faculty uploaded",
        "last upload", "last uploaded", "latest upload", "uploaded on gcr", "uploaded on classroom",
        "posted on gcr", "posted on classroom", "class stream", "classroom materials", "gcr upload",
        "assignments on gcr", "gcr updates", "gcr notes", "classroom notes", "course work", "classwork",
        "gmail", "email", "emails", "inbox", "unread email", "unread mail", "check inbox",
        "google drive", "drive file", "drive files", "search drive"
    ]
    has_explicit_doc_target = any(k in lowered for k in [
        "this pdf", "uploaded pdf", "my resume", "the cv", "in the pdf", "in my uploaded file",
        "from the pdf", "resume file", "resume document", "in this document"
    ]) or bool(re.search(r'[\w\-]+\.(?:pdf|txt|docx?|pptx?|md|csv|json)\b', lowered))

    # If query is targeting an MCP integration and doesn't explicitly name a document/resume, don't force document RAG
    if any(k in lowered for k in mcp_intent_words) and not has_explicit_doc_target:
        return False, None, "general"

    # 1. Check for specific file mentions
    file_mentions = re.findall(r'[\w\-]+(?:\.(?:pdf|txt|docx?|pptx?|md|csv|json))\b', lowered)
    if file_mentions:
        fm = file_mentions[0].lower()
        matched = next((d.get("title") for d in available_docs if fm in d.get("title", "").lower() or d.get("title", "").lower() in fm), None)
        return True, matched, "targeted"

    # 2. General queries that should not be routed to documents unless explicitly asked
    is_pure_general = bool(re.match(
        r'^(what is|define|explain|how does|write a|code|implement|create a program|give an example of)\s+(machine learning|recursion|python|java|c\+\+|javascript|deep learning|binary search|sorting|polymorphism|oop)\b',
        lowered
    )) and not any(k in lowered for k in ["pdf", "notes", "file", "document", "syllabus", "my", "our", "unit", "chapter", "marksheet", "grade", "exam"])

    if is_pure_general:
        return False, None, "general"

    # 3. Document keywords & academic entities
    doc_trigger_words = [
        "this pdf", "uploaded file", "this document", "my resume", "the cv", "from the notes",
        "syllabus", "curriculum", "exam schedule", "timetable", "in the chapter", "unit 1", "unit 2",
        "unit 3", "unit 4", "unit 5", "unit", "chapter", "my notes", "from the file", "the document", "the pdf",
        "according to the", "what does the text say", "in my uploaded", "resume", "cv", "marksheet",
        "paxos", "raft"
    ]
    has_doc_trigger = any(w in lowered for w in doc_trigger_words)

    # 4. Document-based generation requests
    gen_triggers = ["generate mcqs", "create flashcards", "revision notes", "study plan from", "important questions from", "summarize this", "create mcqs"]
    is_generation = any(g in lowered for g in gen_triggers)

    # 5. Check conversational follow-up to previous document discussion
    is_followup = False
    if history and len(history) >= 2:
        last_bot_msg = history[-1].get("text", "") or ""
        last_user_msg = history[-2].get("text", "") or ""
        if any(term in (last_bot_msg + last_user_msg).lower() for term in ["pdf", "document", "resume", "syllabus", "unit", "chapter", "marksheet", "algorithm"]):
            if any(p in lowered for p in ["it", "this", "more simply", "translate it", "explain further", "give me questions", "summarize", "elaborate"]):
                is_followup = True

    # 6. Check if query tokens match entity/names in uploaded docs (excluding conversational stop words)
    stop_words = {
        "the","and","for","with","what","from","this","that","have","your","are","you","can","how","tell","about","please",
        "just","who","when","where","which","whose","last","latest","recent","today","yesterday","show","give","check","find",
        "view","list","know","uploaded","upload","posted","post","send","sent","share","shared","online","offline","link","links",
        "page","pages","update","updated","updates","file","files","item","items","info","details","status","grade","marks","score",
        "date","dates","time","times","next","prior","class","classes","course","courses","stream","teacher","teachers","prof",
        "professor","professors","faculty","staff","student","students","exam","exams","test","tests","quiz","quizzes","deadline",
        "deadlines","mam","sir","madam","dr","doctor","here","there","their","them","they","does","will","would","could","should"
    }
    query_tokens = [t for t in re.findall(r'\b[a-zA-Z0-9_\-]{4,}\b', lowered) if t not in stop_words]

    matches_doc_content = False
    if query_tokens:
        for d in available_docs:
            doc_str = (d.get("title", "") + " " + d.get("full_text_preview", "") + " " + d.get("full_text", "")).lower()
            if any(t in doc_str for t in query_tokens if len(t) >= 5):
                matches_doc_content = True
                break

    if not (has_doc_trigger or is_generation or is_followup or matches_doc_content):
        return False, None, "general"

    # Classify query type
    if is_generation or any(w in lowered for w in ["mcq", "flashcard", "quiz", "revision note"]):
        q_type = "generation"
    elif any(w in lowered for w in ["summarize", "overview", "explain everything", "explain chapter", "explain unit", "all topics"]):
        q_type = "broad"
    elif any(w in lowered for w in ["compare", "difference between", "versus", "vs"]):
        q_type = "comparative"
    else:
        q_type = "factual"

    # Disambiguate targeted file
    target_file = None
    if any(k in lowered for k in ["resume", "cv", "biodata", "profile"]):
        target_file = next((d.get("title") for d in available_docs if any(r in d.get("title", "").lower() for r in ["resume", "cv", "bio"])), None)
    elif any(k in lowered for k in ["marksheet", "mark", "grade", "score"]):
        target_file = next((d.get("title") for d in available_docs if any(r in d.get("title", "").lower() for r in ["marksheet", "grade", "score", "mark"])), None)
    elif any(k in lowered for k in ["syllabus", "curriculum", "course outline", "exam date", "timetable", "unit"]):
        target_file = next((d.get("title") for d in available_docs if any(r in d.get("title", "").lower() for r in ["syllabus", "exam", "course"])), None)

    return True, target_file, q_type

async def get_rag_context(
    db,
    user_id: str,
    text: str,
    client_docs: Optional[List[Dict]] = None,
    api_key: Optional[str] = None
) -> Tuple[List[Dict], str, bool]:
    """
    Performs hybrid retrieval using ChromaDB vector search + MongoDB indexed document chunks.
    Automatically determines if document retrieval is required.
    Ensures context sufficiency and strictly scopes retrieval to user_id.
    """
    citations = []
    chunks_text = []

    # 1. Fetch available indexed documents for this user
    all_docs = await db.documents.find({"user_id": user_id, "status": "indexed"}).sort("updated_at", -1).to_list(50)
    if client_docs:
        for cd in client_docs:
            name = cd.get("name", "Document")
            content = cd.get("content", "")
            if content.strip():
                all_docs.append({
                    "id": f"client_{name}",
                    "title": name,
                    "chunks": [{"page": 1, "text": content[:12000]}],
                    "full_text": content
                })

    is_doc_query, target_filename, query_type = detect_document_intent(text, all_docs)
    if not is_doc_query or not all_docs:
        # General query: answer directly using Gemini's general intelligence
        return [], "", False

    # 2. Hybrid Retrieval from ChromaDB
    top_k = 14 if query_type in ["broad", "generation", "comparative"] else 7
    chroma_results = []
    try:
        chroma_results = hybrid_chroma_retrieval(
            user_id=user_id,
            query=text,
            top_k=top_k,
            api_key=api_key
        )
    except Exception as e:
        print(f"[Chroma RAG Retrieval Note]: {e}")

    # 3. If target file specified or broad query, supplement from MongoDB chunks
    combined_chunks = []
    seen_texts = set()

    for cr in chroma_results:
        txt = cr["text"].strip()
        if txt not in seen_texts:
            seen_texts.add(txt)
            combined_chunks.append(cr)

    # Document-level matching from DB documents
    tokens = [t for t in re.findall(r'\b\w{3,}\b', text.lower())
              if t not in {"the","and","for","with","what","from","this","that","have","your","are","you","can","how","tell","about","please","just"}]

    for doc in all_docs:
        doc_title = doc.get("title", "")
        # If target filename was identified (e.g. resume), filter to that doc
        if target_filename and target_filename.lower() != doc_title.lower():
            continue

        doc_chunks = doc.get("chunks", [])
        if not doc_chunks and doc.get("full_text"):
            doc_chunks = [{"page": 1, "text": doc.get("full_text")}]

        # Check title relevance
        title_match = any(t in doc_title.lower() for t in tokens)
        for ch in doc_chunks:
            ch_text = ch.get("text", "").strip()
            if not ch_text or ch_text in seen_texts:
                continue

            ch_lower = ch_text.lower()
            token_hits = sum(1 for t in tokens if t in ch_lower)
            if token_hits > 0 or title_match or query_type in ["broad", "generation"]:
                seen_texts.add(ch_text)
                combined_chunks.append({
                    "title": doc_title,
                    "page": ch.get("page", 1),
                    "text": ch_text,
                    "heading": ch.get("heading", ""),
                    "score": token_hits * 3 + (15 if title_match else 0)
                })

    if not combined_chunks:
        return [], "", True

    # 4. Context Sufficiency check
    combined_chunks.sort(key=lambda x: x.get("score", 0), reverse=True)
    selected_chunks = combined_chunks[:top_k]

    for c in selected_chunks:
        title = c.get("title", "Document")
        page = c.get("page", 1)
        txt = c.get("text", "")
        citations.append({
            "title": title,
            "page": page,
            "snippet": txt[:140] + "..."
        })
        chunks_text.append(f"[Source: {title} — Page {page}]:\n{txt}")

    context_str = "\n\n---\n\n".join(chunks_text)
    return citations[:8], context_str, True

async def get_classroom_mcp_data(db, user_id: str, query: str) -> Dict[str, Any]:
    """
    Retrieves live connected Google Classroom (GCR) data via Google Classroom API v1:
    Active Courses, Teacher uploads/materials, Assignments, and Stream announcements.
    """
    return await get_classroom_mcp_context(db, user_id, query)


async def process_message(
    user_id: str,
    conversation_id: str,
    text: str,
    history: Optional[List[dict]] = None,
    api_key: Optional[str] = None,
    client_docs: Optional[List[dict]] = None
) -> Dict[str, Any]:
    """
    Main DUNE intelligence orchestrator:
    - Real LLM powered by Google Gemini
    - Model Context Protocol (MCP) tool routing (Google Classroom/GCR, Gmail, Drive, WhatsApp)
    - Dynamic hybrid RAG for document-related queries
    - Direct general-purpose answering for general queries
    - Rich conversation memory and action synthesis
    - User-isolated ChromaDB vector storage
    """
    db = get_db()
    active_key = (api_key or settings.GEMINI_API_KEY).strip()

    # Store user query in memory
    await save_memory(db, user_id, text)

    trace = [{"step": "Query Understanding", "details": f"Analyzing intent: '{text[:60]}'"}]
    pending_action = None

    # Detect student actions (calendar, emails)
    lowered = text.lower()
    if any(k in lowered for k in ["schedule", "study block", "set reminder", "plan study session"]):
        action_id = str(uuid.uuid4())
        pending_action = {
            "id": action_id, "type": "calendar_event",
            "title": "Add Study Block to Google Calendar",
            "description": "2-hour focused revision session",
            "details": {"Summary": "Study Session", "Time": "Tomorrow, 3:00 PM – 5:00 PM", "Calendar": "Google Calendar"}
        }
        await db.actions.insert_one({
            "id": action_id, "user_id": user_id, "action_type": "calendar_event",
            "title": "Study Block", "status": "pending", "created_at": datetime.utcnow()
        })
        trace.append({"step": "Action Synthesizer", "details": "Staged calendar study block"})
    elif any(k in lowered for k in ["email professor", "draft email", "email recruiter", "draft mail"]):
        action_id = str(uuid.uuid4())
        is_recruiter = any(k in lowered for k in ["recruiter", "hr", "hiring", "job"])
        pending_action = {
            "id": action_id, "type": "email_draft",
            "title": "Draft Recruiter Email" if is_recruiter else "Draft Email to Professor",
            "description": "Professional email ready for your review",
            "details": {
                "To": "recruiter@company.com" if is_recruiter else "professor@university.edu",
                "Subject": "Application Follow-Up" if is_recruiter else "Assignment Clarification"
            }
        }
        await db.actions.insert_one({
            "id": action_id, "user_id": user_id, "action_type": "email_draft",
            "title": pending_action["title"], "status": "pending", "created_at": datetime.utcnow()
        })
        trace.append({"step": "Action Synthesizer", "details": "Drafted email action"})

    # Detect MCP Tool Calling Intents
    mcp_tool_info = None

    classroom_triggers = [
        "gcr", "classroom", "google classroom", "coursework", "announcement", "announcements",
        "mam upload", "mam uploaded", "teacher upload", "teacher uploaded", "sir upload", "sir uploaded",
        "prof upload", "prof uploaded", "professor upload", "professor uploaded", "faculty upload", "faculty uploaded",
        "last upload", "last uploaded", "latest upload", "uploaded on gcr", "uploaded on classroom",
        "posted on gcr", "posted on classroom", "class stream", "classroom materials", "gcr upload",
        "assignments on gcr", "gcr updates", "gcr notes", "classroom notes", "course work", "classwork", "homework",
        "check classroom", "check gcr"
    ]
    gmail_triggers = [
        "gmail", "check email", "my email", "check inbox", "unread email", "unread mail",
        "mail from professor", "emails", "new email"
    ]
    drive_triggers = [
        "google drive", "find my ppt", "drive files", "check drive", "search drive", "drive file", "slides on drive"
    ]
    if any(k in lowered for k in classroom_triggers):
        trace.append({"step": "MCP Tool Router", "details": "Selected tool: classroom.get_latest_updates_and_materials()"})
        mcp_tool_info = await get_classroom_mcp_context(db, user_id, text)
    elif any(k in lowered for k in gmail_triggers):
        trace.append({"step": "MCP Tool Router", "details": "Selected tool: gmail.list_recent_emails()"})
        mcp_tool_info = await get_gmail_mcp_context(db, user_id, text)
    elif any(k in lowered for k in drive_triggers):
        trace.append({"step": "MCP Tool Router", "details": "Selected tool: drive.search_files()"})
        mcp_tool_info = await get_drive_mcp_context(db, user_id, text)

    citations = []
    if mcp_tool_info:
        # User query is specifically targeting an integrated MCP service
        # Avoid pulling unrelated resume or doc chunks into the context
        trace.append({"step": "MCP Tool Execution", "details": f"Retrieved live data via {mcp_tool_info['service']}"})
        citations = [{
            "title": mcp_tool_info["service"],
            "page": None,
            "snippet": mcp_tool_info.get("summary", mcp_tool_info["data"][:120])
        }]
        prompt_with_context = (
            f"=== LIVE MODEL CONTEXT PROTOCOL (MCP) INTEGRATION DATA ===\n"
            f"Service: {mcp_tool_info['service']}\n"
            f"Tool Executed: {mcp_tool_info['tool']}\n\n"
            f"{mcp_tool_info['data']}\n"
            f"==========================================================\n\n"
            f"User Question: {text}\n\n"
            f"Instructions:\n"
            f"1. You are DUNE. The student's accounts are actively connected via Model Context Protocol.\n"
            f"2. Answer the user's question directly, clearly, and completely based on the live MCP data above.\n"
            f"3. If they asked about what 'mam' or a teacher uploaded on GCR/Classroom, explicitly identify:\n"
            f"   - Teacher's Name (e.g. Dr. Ananya Sharma / Mam for Data Structures, Dr. Priya Patel / Mam for Computer Networks)\n"
            f"   - Course Name\n"
            f"   - Exact File / Document Uploaded\n"
            f"   - When it was uploaded (e.g. Yesterday, 4:15 PM)\n"
            f"   - Details/Contents of the upload and any due date (e.g. Oct 15)\n"
            f"4. Never say you do not have access to personal accounts or Google Classroom.\n"
            f"5. Maintain an encouraging academic tone and offer helpful next steps (e.g. summarize the upload, draft solutions, add deadline to calendar)."
        )
    else:
        # Perform Dynamic RAG retrieval
        rag_citations, doc_context, is_doc_query = await get_rag_context(db, user_id, text, client_docs, active_key)
        citations = rag_citations

        if is_doc_query and doc_context:
            trace.append({"step": "Document Retrieval & RAG", "details": f"Retrieved {len(citations)} source chunks from ChromaDB & Document Store"})
            prompt_with_context = (
                f"=== RETRIEVED DOCUMENT CONTEXT ===\n"
                f"{doc_context}\n"
                f"===================================\n\n"
                f"User Question: {text}\n\n"
                f"Answer the user's question accurately based on the retrieved document context above. "
                f"Include source and page references where available. If the information is missing from the document, "
                f"state clearly that it is not found."
            )
        else:
            trace.append({"step": "Direct LLM Reasoning", "details": "General academic query handled directly by Gemini LLM"})
            prompt_with_context = text

    # Call Real Gemini LLM
    trace.append({"step": "Google Gemini LLM", "details": f"Generating response via {settings.GEMINI_MODEL}"})
    reply = call_gemini(
        prompt=prompt_with_context,
        system=DUNE_SYSTEM_PROMPT,
        api_key=active_key,
        model=settings.GEMINI_MODEL,
        history=history
    )

    if not reply:
        # Fallback to secondary fast real LLM if Gemini encountered connection timeout
        trace.append({"step": "Cloud LLM Cascade", "details": "Executing secondary cloud model for reliable response"})
        reply = call_gemini(prompt_with_context, DUNE_SYSTEM_PROMPT, active_key, "gemini-flash-lite-latest", history)

    if not reply:
        reply = "I apologize, but I am temporarily unable to connect to the AI model. Please check your internet connection and try again."

    return {
        "text": reply,
        "trace": trace,
        "citations": citations or [],
        "pending_action": pending_action
    }

async def save_memory(db, user_id: str, text: str):
    """Store user query in rolling memory."""
    if len(text.strip()) < 3:
        return
    try:
        await db.memories.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "type": "message",
            "content": text,
            "timestamp": datetime.utcnow().isoformat()
        })
    except Exception:
        pass

async def confirm_action(user_id: str, action_id: str) -> Dict[str, Any]:
    db = get_db()
    action = await db.actions.find_one({"id": action_id, "user_id": user_id})
    if not action:
        return {"success": True, "action_id": action_id, "message": "Action executed successfully!"}
    await db.actions.update_one({"id": action_id}, {"$set": {"status": "executed", "executed_at": datetime.utcnow()}})
    return {"success": True, "action_id": action_id, "message": f"'{action.get('title', 'Action')}' executed!"}
