"""
Real Google Classroom API Integration for DUNE.
Interacts directly with Google Classroom REST API v1 using OAuth 2.0 access tokens.
Supports courses, coursework (assignments & deadlines), announcements, and course materials.
Includes automatic token refresh via get_valid_google_token.
"""
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
import requests
from app.integrations.google_oauth import get_valid_google_token

CLASSROOM_API_BASE = "https://classroom.googleapis.com/v1"


def _headers(access_token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }


def list_courses(access_token: str, page_size: int = 20) -> List[Dict[str, Any]]:
    """Fetches active courses where the student is enrolled."""
    url = f"{CLASSROOM_API_BASE}/courses?courseStates=ACTIVE&pageSize={page_size}"
    try:
        resp = requests.get(url, headers=_headers(access_token), timeout=15)
        if resp.status_code == 200:
            return resp.json().get("courses", [])
        print(f"[Google Classroom API] list_courses returned {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        print(f"[Google Classroom API] list_courses error: {e}")
    return []


def list_course_work(access_token: str, course_id: str, page_size: int = 15) -> List[Dict[str, Any]]:
    """Fetches coursework (assignments, projects, quizzes) for a given course."""
    url = f"{CLASSROOM_API_BASE}/courses/{course_id}/courseWork?pageSize={page_size}"
    try:
        resp = requests.get(url, headers=_headers(access_token), timeout=15)
        if resp.status_code == 200:
            return resp.json().get("courseWork", [])
        print(f"[Google Classroom API] list_course_work {course_id} returned {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        print(f"[Google Classroom API] list_course_work error: {e}")
    return []


def list_announcements(access_token: str, course_id: str, page_size: int = 10) -> List[Dict[str, Any]]:
    """Fetches stream announcements for a given course."""
    url = f"{CLASSROOM_API_BASE}/courses/{course_id}/announcements?pageSize={page_size}"
    try:
        resp = requests.get(url, headers=_headers(access_token), timeout=15)
        if resp.status_code == 200:
            return resp.json().get("announcements", [])
        print(f"[Google Classroom API] list_announcements {course_id} returned {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        print(f"[Google Classroom API] list_announcements error: {e}")
    return []


def list_course_materials(access_token: str, course_id: str, page_size: int = 10) -> List[Dict[str, Any]]:
    """Fetches teacher uploaded materials, lab manuals, PDFs, and slide decks."""
    url = f"{CLASSROOM_API_BASE}/courses/{course_id}/courseWorkMaterials?pageSize={page_size}"
    try:
        resp = requests.get(url, headers=_headers(access_token), timeout=15)
        if resp.status_code == 200:
            return resp.json().get("courseWorkMaterial", [])
        print(f"[Google Classroom API] list_course_materials {course_id} returned {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        print(f"[Google Classroom API] list_course_materials error: {e}")
    return []


def list_course_teachers(access_token: str, course_id: str) -> List[Dict[str, Any]]:
    """Fetches teachers/instructors for a given course."""
    url = f"{CLASSROOM_API_BASE}/courses/{course_id}/teachers"
    try:
        resp = requests.get(url, headers=_headers(access_token), timeout=15)
        if resp.status_code == 200:
            return resp.json().get("teachers", [])
    except Exception as e:
        print(f"[Google Classroom API] list_course_teachers error: {e}")
    return []


def _format_due_date(due_date_obj: Optional[Dict], due_time_obj: Optional[Dict]) -> str:
    """Formats Google Classroom dueDate and dueTime dicts into human-readable string."""
    if not due_date_obj:
        return "No deadline specified"
    y = due_date_obj.get("year", datetime.now().year)
    m = due_date_obj.get("month", 1)
    d = due_date_obj.get("day", 1)
    date_str = f"{y:04d}-{m:02d}-{d:02d}"

    if due_time_obj:
        hh = due_time_obj.get("hours", 23)
        mm = due_time_obj.get("minutes", 59)
        time_str = f"{hh:02d}:{mm:02d}"
        return f"{date_str} {time_str}"
    return date_str


async def get_classroom_overview(db, user_id: str) -> Dict[str, Any]:
    """
    Retrieves full live Google Classroom data for user with automatic token refresh.
    Returns parsed courses, pending assignments, stream announcements, and materials.
    """
    token = await get_valid_google_token(db, user_id, service="google_classroom")
    if not token:
        return {
            "connected": False,
            "message": "Google Classroom is not connected or authorization expired.",
            "courses": [],
            "assignments": [],
            "announcements": [],
            "materials": [],
            "latest_upload": None,
            "total_courses": 0
        }

    courses_raw = list_courses(token)
    parsed_courses = []
    all_assignments = []
    all_announcements = []
    all_materials = []

    for c in courses_raw:
        c_id = c.get("id")
        c_name = c.get("name", "Untitled Course")
        section = c.get("section", "")
        room = c.get("room", "")

        # Fetch teachers
        teachers = list_course_teachers(token, c_id)
        teacher_names = []
        for t in teachers:
            profile = t.get("profile", {})
            name_obj = profile.get("name", {})
            full_name = name_obj.get("fullName") or profile.get("emailAddress", "Instructor")
            teacher_names.append(full_name)
        teacher_display = ", ".join(teacher_names) if teacher_names else "Course Instructor"

        parsed_courses.append({
            "id": c_id,
            "name": c_name,
            "section": section,
            "room": room,
            "teacher": teacher_display,
            "alternateLink": c.get("alternateLink")
        })

        # Fetch coursework (assignments)
        cw_items = list_course_work(token, c_id)
        for cw in cw_items:
            due_str = _format_due_date(cw.get("dueDate"), cw.get("dueTime"))
            all_assignments.append({
                "id": cw.get("id"),
                "course_id": c_id,
                "course": c_name,
                "title": cw.get("title", "Assignment"),
                "description": cw.get("description", ""),
                "due": due_str,
                "max_points": cw.get("maxPoints", 100),
                "state": cw.get("state", "PUBLISHED"),
                "alternateLink": cw.get("alternateLink"),
                "teacher": teacher_display,
                "creation_time": cw.get("creationTime")
            })

        # Fetch stream announcements
        ann_items = list_announcements(token, c_id)
        for ann in ann_items:
            all_announcements.append({
                "id": ann.get("id"),
                "course_id": c_id,
                "course": c_name,
                "teacher": teacher_display,
                "text": ann.get("text", ""),
                "created_at": ann.get("creationTime", ""),
                "alternateLink": ann.get("alternateLink")
            })

        # Fetch course materials (manuals, notes, PDFs)
        mat_items = list_course_materials(token, c_id)
        for mat in mat_items:
            # Extract attachments info
            attachment_names = []
            for m in mat.get("materials", []):
                if "driveFile" in m:
                    df = m["driveFile"].get("driveFile", {})
                    attachment_names.append(df.get("title", "Attached File"))
                elif "link" in m:
                    attachment_names.append(m["link"].get("title", m["link"].get("url", "Link")))

            file_desc = ", ".join(attachment_names) if attachment_names else mat.get("title", "Course Material")
            all_materials.append({
                "id": mat.get("id"),
                "course_id": c_id,
                "course": c_name,
                "teacher": teacher_display,
                "name": mat.get("title", "Course Material"),
                "description": mat.get("description", ""),
                "attachments": file_desc,
                "uploaded_at": mat.get("creationTime", ""),
                "alternateLink": mat.get("alternateLink")
            })

    # Sort assignments by due date / creation
    all_assignments.sort(key=lambda x: x.get("due", ""), reverse=False)
    # Sort announcements & materials by creation time descending
    all_announcements.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    all_materials.sort(key=lambda x: x.get("uploaded_at", ""), reverse=True)

    # Determine latest upload across coursework and materials
    latest_upload = None
    if all_materials:
        top_mat = all_materials[0]
        latest_upload = {
            "course": top_mat["course"],
            "teacher": top_mat["teacher"],
            "title": top_mat["name"],
            "uploaded_at": top_mat["uploaded_at"][:10] if top_mat["uploaded_at"] else "Recently",
            "type": "Course Material / Document",
            "description": top_mat.get("description") or top_mat.get("attachments", ""),
            "due_date": "N/A"
        }
    elif all_assignments:
        top_asg = all_assignments[0]
        latest_upload = {
            "course": top_asg["course"],
            "teacher": top_asg["teacher"],
            "title": top_asg["title"],
            "uploaded_at": top_asg.get("creation_time", "Recently")[:10],
            "type": "Assignment / Lab Work",
            "description": top_asg.get("description", ""),
            "due_date": top_asg.get("due", "N/A")
        }

    return {
        "connected": True,
        "courses": parsed_courses,
        "assignments": all_assignments,
        "announcements": all_announcements,
        "materials": all_materials,
        "latest_upload": latest_upload,
        "total_courses": len(parsed_courses),
        "pending_count": len(all_assignments),
    }


async def get_classroom_mcp_context(db, user_id: str, query: str = "") -> Dict[str, Any]:
    """
    Prepares live Google Classroom Model Context Protocol (MCP) data for DUNE's LLM agent.
    If connected, delivers genuine courses, latest teacher uploads, assignments, and announcements.
    If not connected, returns clear connection instructions.
    """
    overview = await get_classroom_overview(db, user_id)

    if not overview["connected"]:
        return {
            "tool": "classroom.get_latest_updates_and_materials()",
            "service": "Google Classroom MCP",
            "summary": "Google Classroom is not connected.",
            "data": (
                "Google Classroom status: Not Connected.\n"
                "The student has not linked their Google Classroom account yet.\n"
                "To sync live courses, assignments, and teacher uploads, the student can connect Google Classroom "
                "via the 'MCP Connections' studio in the sidebar by clicking 'Connect' -> 'Authorize with Google'."
            )
        }

    courses = overview.get("courses", [])
    assignments = overview.get("assignments", [])
    announcements = overview.get("announcements", [])
    materials = overview.get("materials", [])
    latest_upload = overview.get("latest_upload")

    lines = [
        f"Status: Connected & Synchronized (Live Google Classroom API v1)",
        f"Enrolled Courses Count: {len(courses)}",
        ""
    ]

    if courses:
        lines.append("ACTIVE ENROLLED COURSES:")
        for c in courses:
            lines.append(f"• {c['name']} | Section: {c['section'] or 'General'} | Instructor: {c['teacher']}")
        lines.append("")

    if latest_upload:
        lines.append("LATEST TEACHER UPLOAD ON GOOGLE CLASSROOM:")
        lines.append(
            f"• Course: {latest_upload['course']}\n"
            f"  Instructor / Teacher: {latest_upload['teacher']}\n"
            f"  File / Material: {latest_upload['title']}\n"
            f"  Uploaded At: {latest_upload['uploaded_at']}\n"
            f"  Type: {latest_upload['type']}\n"
            f"  Description: {latest_upload['description']}\n"
            f"  Due Date: {latest_upload['due_date']}"
        )
        lines.append("")

    if materials:
        lines.append("RECENT COURSE MATERIALS & LAB MANUALS:")
        for m in materials[:5]:
            lines.append(f"• [{m['course']}] {m['name']} — Uploaded by: {m['teacher']} ({m['uploaded_at'][:10] if m['uploaded_at'] else 'Recent'})")
        lines.append("")

    if assignments:
        lines.append("PENDING COURSEWORK & ASSIGNMENTS:")
        for idx, a in enumerate(assignments[:6], 1):
            lines.append(f"{idx}. [{a['course']}] {a['title']} — Due: {a['due']} ({a['max_points']} Points) — Teacher: {a['teacher']}")
        lines.append("")

    if announcements:
        lines.append("LATEST STREAM ANNOUNCEMENTS:")
        for ann in announcements[:4]:
            lines.append(f"• [{ann['course']}] {ann['teacher']}: \"{ann['text']}\"")
        lines.append("")

    summary = f"{len(courses)} courses active • {len(assignments)} assignments pending"
    if latest_upload:
        summary += f" • Latest: {latest_upload['title']} by {latest_upload['teacher']}"

    return {
        "tool": "classroom.get_latest_updates_and_materials()",
        "service": "Google Classroom MCP",
        "summary": summary,
        "data": "\n".join(lines).strip()
    }
