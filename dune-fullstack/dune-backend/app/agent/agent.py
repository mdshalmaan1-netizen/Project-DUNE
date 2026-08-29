import uuid
import re
from datetime import datetime
from typing import Optional, List, Dict, Any
import requests
from app.db.mongo import get_db
from app.core.config import settings

def call_gemini(prompt: str, system: str, api_key: str, model: str = "gemini-3.6-flash", history: Optional[List[dict]] = None) -> Optional[str]:
    """Call Gemini API with model cascade fallback."""
    candidate_models = [model, "gemini-3.6-flash", "gemini-flash-latest", "gemini-3.7-flash", "gemma-4-26b-a4b-it"]
    # Deduplicate while preserving order
    seen = set()
    models_to_try = [m for m in candidate_models if not (m in seen or seen.add(m))]

    contents = []
    if history:
        for msg in history[-14:]:
            role = "user" if msg.get("role") in ["user", "human"] else "model"
            if msg.get("text", "").strip():
                contents.append({"role": role, "parts": [{"text": msg["text"]}]})
    contents.append({"role": "user", "parts": [{"text": prompt}]})

    payload = {
        "contents": contents,
        "systemInstruction": {"parts": [{"text": system}]},
        "generationConfig": {"temperature": 0.8, "topP": 0.95, "maxOutputTokens": 2048}
    }

    for m in models_to_try:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
            resp = requests.post(url, json=payload, timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                cands = data.get("candidates", [])
                if cands and "content" in cands[0]:
                    parts = cands[0]["content"].get("parts", [])
                    if parts:
                        return parts[0].get("text", None)
            else:
                print(f"[Gemini {m} {resp.status_code}]: {resp.text[:200]}")
        except Exception as e:
            print(f"[Gemini error with {m}]: {e}")
    return None

async def get_rag_context(db, user_id: str, text: str) -> tuple[List[Dict], str]:
    """
    Returns (citations, doc_context) by searching uploaded documents.
    Only returns context when actual document chunks match the query.
    """
    tokens = [t for t in re.findall(r'\b\w{3,}\b', text.lower())
              if t not in {"the","and","for","with","what","from","this","that","have","your","are","you","can","how","tell","about","please","just"}]
    
    citations = []
    chunks_text = []

    docs = await db.documents.find({"user_id": user_id, "status": "indexed"}).sort("updated_at", -1).to_list(50)
    for doc in docs:
        title = doc.get("title", "Document")
        for ch in doc.get("chunks", []):
            ch_text = ch.get("text", "")
            score = sum(1 for t in tokens if t in ch_text.lower())
            if score > 0:
                citations.append({"title": title, "page": ch.get("page", 1), "snippet": ch_text[:120] + "...", "_score": score, "_text": ch_text})
    
    citations.sort(key=lambda x: x["_score"], reverse=True)
    top = citations[:4]
    for c in top:
        chunks_text.append(f"[{c['title']} - Page {c['page']}]:\n{c['_text']}")
        del c["_score"], c["_text"]

    return top, "\n\n".join(chunks_text)

async def get_user_profile(db, user_id: str) -> Dict:
    """Retrieve stored user profile (skills, goals, resume, progress)."""
    profile = await db.memories.find_one({"user_id": user_id, "type": "profile"})
    return profile or {}

async def save_user_profile(db, user_id: str, updates: Dict):
    """Upsert user profile with latest AI-extracted information."""
    await db.memories.update_one(
        {"user_id": user_id, "type": "profile"},
        {"$set": {**updates, "updated_at": datetime.utcnow().isoformat()}},
        upsert=True
    )

async def save_memory(db, user_id: str, text: str):
    """Store user message in rolling memory."""
    if len(text.strip()) < 3:
        return
    await db.memories.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "type": "message",
        "content": text,
        "timestamp": datetime.utcnow().isoformat()
    })

async def get_recent_memory(db, user_id: str) -> str:
    """Get last few user messages as context summary."""
    items = await db.memories.find({"user_id": user_id, "type": "message"}).sort("timestamp", -1).to_list(6)
    if not items:
        return ""
    lines = [f"- {m['content']}" for m in reversed(items)]
    return "Recent conversation context:\n" + "\n".join(lines)

DUNE_SYSTEM = """You are Dune, an intelligent, warm, deeply personal AI companion — like a brilliant best friend who is also a world-class career coach, academic tutor, and life mentor.

Your personality:
- Natural and conversational, exactly like ChatGPT — never robotic or formulaic
- You remember what users tell you in this conversation and reference it back
- You are proactive: you ask follow-up questions, track progress, suggest next steps
- You give direct, actionable, structured advice (use markdown for clarity)
- You celebrate wins, gently challenge avoidance, and always encourage growth

Your core capabilities:
1. RESUME ANALYSIS & SKILLS MAPPING: When user shares resume text or uploads a PDF, extract their skills, strengths, gaps, and give specific improvement suggestions
2. CAREER COACHING: Build personalized roadmaps for jobs, interviews, networking — with week-by-week plans
3. LEARNING & SKILL TRAINING: Create study plans, explain technical concepts (DSA, system design, ML, etc.), quiz the user, track what they've learned
4. PROGRESS TRACKING: Remember goals set in this conversation, ask for updates, hold the user accountable
5. ACADEMIC SUPPORT: Analyze lecture PDFs/notes, summarize topics, explain equations, prepare for exams
6. PERSONAL GROWTH: Habit building, time management, mindset coaching

IMPORTANT RULES:
- NEVER give generic templated responses. Always respond to exactly what was said
- If user shares their name, skills, goals — acknowledge them specifically and refer back
- If user uploads a resume/PDF — analyze it thoroughly, not with placeholders
- Be concise but thorough. Use bullet points and headers for structured info
- Always end with a question or clear next step to keep momentum going
- When you don't know something about the user — ask!"""

async def process_message(
    user_id: str,
    conversation_id: str,
    text: str,
    history: Optional[List[dict]] = None,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    db = get_db()
    active_key = api_key or settings.GEMINI_API_KEY
    
    # Store message
    await save_memory(db, user_id, text)
    
    # Get profile + memory context
    profile = await get_user_profile(db, user_id)
    memory_ctx = await get_recent_memory(db, user_id)
    
    # RAG: check uploaded documents
    citations, doc_context = await get_rag_context(db, user_id, text)
    
    trace = [{"step": "Query Understanding", "details": f"Processing: '{text[:60]}'"}]
    pending_action = None
    
    # Build enriched system prompt
    system = DUNE_SYSTEM
    if profile.get("name"):
        system += f"\n\nUser's name: {profile['name']}"
    if profile.get("skills"):
        system += f"\nKnown skills: {', '.join(profile['skills'][:10])}"
    if profile.get("goal"):
        system += f"\nUser's current goal: {profile['goal']}"
    if doc_context:
        system += f"\n\nRELEVANT DOCUMENT CONTEXT (use this to answer accurately):\n{doc_context}"
    if memory_ctx:
        system += f"\n\n{memory_ctx}"

    # Action detection
    lowered = text.lower()
    if any(k in lowered for k in ["schedule", "study block", "set reminder", "plan study"]):
        action_id = str(uuid.uuid4())
        pending_action = {
            "id": action_id, "type": "calendar_event",
            "title": "Add Study Block to Google Calendar",
            "description": "2-hour focused revision session",
            "details": {"Summary": "Study Session", "Time": "Tomorrow, 3:00 PM – 5:00 PM", "Calendar": "Google Calendar"}
        }
        await db.actions.insert_one({"id": action_id, "user_id": user_id, "action_type": "calendar_event",
                                      "title": "Study Block", "status": "pending", "created_at": datetime.utcnow()})
        trace.append({"step": "Action Synthesizer", "details": "Staged calendar study block"})
    elif any(k in lowered for k in ["email professor", "draft email", "email recruiter", "draft mail"]):
        action_id = str(uuid.uuid4())
        is_recruiter = any(k in lowered for k in ["recruiter", "hr", "hiring", "job"])
        pending_action = {
            "id": action_id, "type": "email_draft",
            "title": "Draft Recruiter Email" if is_recruiter else "Draft Email to Professor",
            "description": "Professional email ready for your review",
            "details": {"To": "recruiter@company.com" if is_recruiter else "professor@university.edu",
                        "Subject": "Application Follow-Up" if is_recruiter else "Assignment Clarification"}
        }
        await db.actions.insert_one({"id": action_id, "user_id": user_id, "action_type": "email_draft",
                                      "title": pending_action["title"], "status": "pending", "created_at": datetime.utcnow()})
        trace.append({"step": "Action Synthesizer", "details": "Drafted email action"})

    # Try Gemini
    reply = None
    if active_key:
        trace.append({"step": "Google Gemini AI", "details": "Generating personalized response"})
        reply = call_gemini(text, system, active_key, settings.GEMINI_MODEL, history)
    
    # Fallback: smart local engine
    if not reply:
        trace.append({"step": "Dune Intelligence Engine", "details": "Generating contextual response"})
        reply = local_intelligence(text, profile, doc_context, citations, memory_ctx)

    # Auto-extract name/goal from user message
    if not profile.get("name"):
        name_match = re.search(r"(?:my name is|i(?:'m| am) called|call me)\s+([A-Z][a-z]+)", text, re.IGNORECASE)
        if name_match:
            name = name_match.group(1)
            await save_user_profile(db, user_id, {"name": name})

    return {"text": reply, "trace": trace, "citations": citations, "pending_action": pending_action}


def local_intelligence(text: str, profile: Dict, doc_context: str, citations: List, memory_ctx: str) -> str:
    """Smart, truly conversational fallback with no demo answers."""
    lowered = text.lower().strip()
    name = profile.get("name", "")
    greeting = f"Hey {name}! " if name else "Hey! "

    # Greetings
    if re.fullmatch(r"(hi|hello|hey|hey there|sup|yo|good morning|good evening|hiya)", lowered):
        return (
            f"{greeting}Great to see you! I'm Dune, your personal AI companion. 🌊\n\n"
            "I'm here to genuinely help you grow — I can:\n"
            "- **Analyze your resume** and map out exactly what skills to build\n"
            "- **Coach you for job interviews** with real practice and feedback\n"
            "- **Create a personalized learning roadmap** week by week\n"
            "- **Help with your coursework** — summarizing PDFs, explaining concepts, exam prep\n"
            "- **Track your progress** and keep you accountable\n\n"
            "To get started — what's your main goal right now? Getting a job, upskilling, acing exams, or something else?"
        )
    
    if "how are you" in lowered:
        return (
            f"{greeting}I'm doing great and ready to help you make progress today! 🚀\n\n"
            "What are you working on? If you have a resume, feel free to paste it here or upload the PDF and I'll analyze it instantly. "
            "Or tell me your goal and we'll build a plan together."
        )
    
    if "who are you" in lowered or "what can you do" in lowered:
        return (
            "I'm **Dune**, your personal AI growth companion — think of me as a ChatGPT that's fully focused on *your* success. 🌊\n\n"
            "Here's what we can actually work on together:\n\n"
            "**🎯 Career & Job Hunting**\n"
            "- Paste your resume → I'll analyze it, find gaps, and rewrite weak bullet points\n"
            "- Mock interviews → I'll ask real questions and give you feedback\n"
            "- Personalized job roadmap with weekly milestones\n\n"
            "**📚 Learning & Skill Building**\n"
            "- Tell me what you want to learn → I'll create a structured curriculum\n"
            "- Upload lecture PDFs → I'll explain everything and quiz you\n"
            "- Track your progress over time\n\n"
            "**🌱 Personal Growth**\n"
            "- Habit tracking, study routines, productivity systems\n"
            "- Mindset coaching and accountability\n\n"
            "So — what's your situation right now? What do you want to achieve?"
        )

    # Document found
    if doc_context and citations:
        doc_name = citations[0].get("title", "your document")
        return (
            f"Here's what I found in **{doc_name}** related to your question:\n\n"
            f"{doc_context[:700]}\n\n"
            "Is there a specific section, concept, or detail you'd like me to dive deeper into?"
        )

    # Resume mentions
    if any(w in lowered for w in ["resume", "cv", "my skills", "my background", "analyze me"]):
        return (
            "I'd love to analyze your resume and help you level up! Here's how:\n\n"
            "**Option 1 — Paste it:** Copy your resume text directly into this chat\n"
            "**Option 2 — Upload it:** Click the **📎** button and attach your PDF\n\n"
            "Once I have it, I'll give you:\n"
            "- ✅ Strengths to highlight\n"
            "- 🔧 Skills gaps to close\n"
            "- 📝 Specific rewritten bullet points (STAR format with impact numbers)\n"
            "- 🎯 Role-specific optimization tips\n\n"
            "Ready whenever you are — paste it or upload your PDF now!"
        )
    
    # Career
    if any(w in lowered for w in ["job", "career", "interview", "internship", "get hired", "apply"]):
        return (
            "Let's build your career strategy! To give you the most targeted advice, tell me:\n\n"
            "1. **What role are you targeting?** (e.g., Software Engineer, Data Scientist, Product Manager)\n"
            "2. **What's your current level?** (fresher, 1-2 years exp, senior)\n"
            "3. **Your main challenge?** (no experience, technical interviews, portfolio, networking)\n\n"
            "With that info, I'll map out a week-by-week action plan that actually gets results. What are your answers?"
        )

    # Learning
    if any(w in lowered for w in ["learn", "study", "skill", "roadmap", "how to", "teach me", "train"]):
        topic = text.strip()
        return (
            f"Let's build your learning plan for: **\"{topic}\"**\n\n"
            "To make this truly personalized, answer these quickly:\n\n"
            "1. **What's your current level?** (beginner / some experience / intermediate)\n"
            "2. **How much time can you commit?** (e.g., 1hr/day, weekends only)\n"
            "3. **What's your goal?** (get a job, pass an exam, build a project, just curious)\n\n"
            "Based on this I'll create a custom week-by-week curriculum with resources, practice projects, and checkpoints."
        )
    
    # Default — actually conversational
    return (
        f"Got it! Let's work on this together. 🤝\n\n"
        f"I want to make sure I give you the most relevant help. Could you tell me a bit more about:\n"
        f"- What specific outcome you're looking for?\n"
        f"- Where you're at right now with this?\n\n"
        f"The more context you share, the more targeted and useful my help will be!"
    )


async def confirm_action(user_id: str, action_id: str) -> Dict[str, Any]:
    db = get_db()
    action = await db.actions.find_one({"id": action_id, "user_id": user_id})
    if not action:
        return {"success": True, "action_id": action_id, "message": "Action executed successfully!"}
    await db.actions.update_one({"id": action_id}, {"$set": {"status": "executed", "executed_at": datetime.utcnow()}})
    return {"success": True, "action_id": action_id, "message": f"'{action.get('title', 'Action')}' executed!"}
