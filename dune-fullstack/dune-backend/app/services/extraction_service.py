import os
import re
import uuid
import base64
import io
from typing import List, Dict, Any, Tuple
import requests
from app.core.config import settings

def extract_image_via_gemini_vision(image_bytes: bytes, mime_type: str = "image/jpeg", api_key: str = "") -> str:
    """
    Uses Gemini Vision to perform high-accuracy OCR, table structure recognition,
    and diagram transcription on visual document pages and uploaded images.
    """
    key = api_key or settings.GEMINI_API_KEY
    if not key:
        return ""
    try:
        b64_data = base64.b64encode(image_bytes).decode("utf-8")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={key}"
        payload = {
            "contents": [{
                "parts": [
                    {
                        "text": (
                            "You are an expert document parser and OCR engine. Transcribe ALL information from this document page or image accurately:\n"
                            "1. Preserve all headings, section titles, paragraphs, and lists.\n"
                            "2. Preserve all tables in clean GitHub Markdown table format (| col1 | col2 |).\n"
                            "3. Transcribe all mathematical formulas, numbers, dates, marks, and names verbatim.\n"
                            "4. Describe key diagrams, charts, or visual figures in concise brackets e.g. [Diagram: Flowchart of RAG pipeline].\n"
                            "Do not include conversational banter, output only the transcribed, structured document content."
                        )
                    },
                    {
                        "inlineData": {
                            "mimeType": mime_type,
                            "data": b64_data
                        }
                    }
                ]
            }],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 4096}
        }
        resp = requests.post(url, json=payload, timeout=25)
        if resp.status_code == 200:
            cands = resp.json().get("candidates", [])
            if cands and "content" in cands[0]:
                parts = cands[0]["content"].get("parts", [])
                if parts:
                    return parts[0].get("text", "").strip()
        else:
            print(f"[Gemini Vision OCR Error {resp.status_code}]: {resp.text[:200]}")
    except Exception as e:
        print(f"[Gemini Vision OCR Exception]: {e}")
    return ""

def format_text_tables(raw_text: str) -> str:
    """
    Detects tab-separated or column-aligned text and converts it into structured Markdown tables.
    Preserves row-column relationships so tables are never flattened into meaningless text.
    """
    lines = raw_text.splitlines()
    formatted_lines = []
    table_buffer = []

    def flush_table(buf: List[str]) -> List[str]:
        if not buf:
            return []
        rows = []
        for line in buf:
            # Split by 2 or more spaces or tab or pipe
            if "\t" in line:
                cells = [c.strip() for c in line.split("\t") if c.strip()]
            elif "|" in line:
                cells = [c.strip() for c in line.split("|") if c.strip()]
            else:
                cells = [c.strip() for c in re.split(r'\s{2,}', line) if c.strip()]
            if cells:
                rows.append(cells)

        if len(rows) >= 2 and all(len(r) >= 2 for r in rows):
            max_cols = max(len(r) for r in rows)
            padded_rows = [r + [""] * (max_cols - len(r)) for r in rows]
            md_lines = []
            md_lines.append("| " + " | ".join(padded_rows[0]) + " |")
            md_lines.append("| " + " | ".join(["---"] * max_cols) + " |")
            for r in padded_rows[1:]:
                md_lines.append("| " + " | ".join(r) + " |")
            return md_lines
        else:
            return buf

    for line in lines:
        stripped = line.strip()
        # Heuristic for table row: contains multiple tabs or multiple double-spaces or existing pipes
        is_table_row = ("\t" in line and len(line.split("\t")) >= 2) or \
                       ("|" in line and len(line.split("|")) >= 3) or \
                       (len(re.split(r'\s{2,}', stripped)) >= 2 and len(stripped) > 10 and not stripped.startswith(('#', '*', '-', '>')))

        if is_table_row:
            table_buffer.append(line)
        else:
            if table_buffer:
                formatted_lines.extend(flush_table(table_buffer))
                table_buffer = []
            formatted_lines.append(line)

    if table_buffer:
        formatted_lines.extend(flush_table(table_buffer))

    return "\n".join(formatted_lines)

def semantic_structure_chunking(
    page_text: str,
    page_num: int,
    file_name: str,
    doc_type: str = "document"
) -> List[Dict[str, Any]]:
    """
    Performs structure-aware semantic chunking.
    Avoids cutting sentences, paragraphs, or tables in half.
    Attaches page_number, heading, section, is_table, and chunk_id metadata to every chunk.
    """
    chunks = []
    # Identify headings e.g. # Heading, Unit 1, Chapter 2, Section 3
    blocks = re.split(r'\n{2,}', page_text)
    current_heading = ""
    current_section = f"Page {page_num}"

    current_chunk_text = []
    current_chunk_len = 0
    max_chunk_chars = 900
    overlap_chars = 150

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        # Check if block is a heading
        heading_match = re.match(r'^(?:#{1,4}\s+|chapter\s+\d+|unit\s+\d+|section\s+\d+|module\s+\d+)(.+)', block, re.IGNORECASE)
        if heading_match:
            current_heading = block.strip("#").strip()
            current_section = current_heading

        is_table_block = "|" in block and "\n|" in block

        # If it's a table block, keep the entire table intact as a single dedicated chunk
        if is_table_block:
            if current_chunk_text:
                chunks.append({
                    "chunk_id": str(uuid.uuid4()),
                    "page": page_num,
                    "heading": current_heading,
                    "section": current_section,
                    "text": "\n\n".join(current_chunk_text),
                    "is_table": False,
                    "document_type": doc_type
                })
                current_chunk_text = []
                current_chunk_len = 0

            chunks.append({
                "chunk_id": str(uuid.uuid4()),
                "page": page_num,
                "heading": current_heading,
                "section": current_section,
                "text": block,
                "is_table": True,
                "document_type": doc_type
            })
            continue

        block_len = len(block)
        if current_chunk_len + block_len > max_chunk_chars:
            if current_chunk_text:
                chunks.append({
                    "chunk_id": str(uuid.uuid4()),
                    "page": page_num,
                    "heading": current_heading,
                    "section": current_section,
                    "text": "\n\n".join(current_chunk_text),
                    "is_table": False,
                    "document_type": doc_type
                })
                # Create overlap from last block if suitable
                last_block = current_chunk_text[-1]
                if len(last_block) < overlap_chars:
                    current_chunk_text = [last_block, block]
                    current_chunk_len = len(last_block) + block_len
                else:
                    current_chunk_text = [block]
                    current_chunk_len = block_len
            else:
                chunks.append({
                    "chunk_id": str(uuid.uuid4()),
                    "page": page_num,
                    "heading": current_heading,
                    "section": current_section,
                    "text": block,
                    "is_table": False,
                    "document_type": doc_type
                })
                current_chunk_text = []
                current_chunk_len = 0
        else:
            current_chunk_text.append(block)
            current_chunk_len += block_len

    if current_chunk_text:
        chunks.append({
            "chunk_id": str(uuid.uuid4()),
            "page": page_num,
            "heading": current_heading,
            "section": current_section,
            "text": "\n\n".join(current_chunk_text),
            "is_table": False,
            "document_type": doc_type
        })

    return chunks

def extract_and_structure_file(file_path: str, filename: str, api_key: str = "") -> Tuple[str, List[Dict[str, Any]]]:
    """
    Comprehensive document ingestion pipeline:
    Handles text PDFs, scanned PDFs (with OCR), images (PNG/JPG/WEBP), Markdown, CSV, TXT, code files.
    Preserves tables, page numbers, headings, and metadata.
    """
    ext = os.path.splitext(filename)[1].lower()
    full_text_parts = []
    all_chunks = []
    doc_type = "resume" if any(k in filename.lower() for k in ["resume", "cv", "biodata"]) else \
               "syllabus" if any(k in filename.lower() for k in ["syllabus", "curriculum", "course"]) else \
               "exam_schedule" if any(k in filename.lower() for k in ["exam", "schedule", "timetable", "date"]) else "academic_document"

    try:
        # 1. Image Files (PNG, JPG, JPEG, WEBP)
        if ext in [".png", ".jpg", ".jpeg", ".webp"]:
            with open(file_path, "rb") as f:
                img_bytes = f.read()
            mime = "image/png" if ext == ".png" else "image/webp" if ext == ".webp" else "image/jpeg"
            ocr_text = extract_image_via_gemini_vision(img_bytes, mime, api_key)
            if not ocr_text:
                ocr_text = f"[Image Document: {filename} uploaded by student]"

            formatted = format_text_tables(ocr_text)
            full_text_parts.append(formatted)
            chunks = semantic_structure_chunking(formatted, 1, filename, doc_type)
            all_chunks.extend(chunks)

        # 2. PDF Documents
        elif ext == ".pdf":
            import pypdf
            reader = pypdf.PdfReader(file_path)
            total_pages = len(reader.pages)
            print(f"[PDF Extraction] Parsing {filename} ({total_pages} pages)")

            for page_idx, page in enumerate(reader.pages):
                page_num = page_idx + 1
                page_text = page.extract_text() or ""
                page_text = page_text.strip()

                # Check if page is scanned or image-based (less than 40 chars extracted)
                if len(page_text) < 40 and hasattr(page, "images") and len(page.images) > 0:
                    print(f"[PDF Extraction] Page {page_num} appears scanned/visual. Performing Gemini OCR...")
                    try:
                        first_img = page.images[0]
                        img_bytes = first_img.data
                        mime = "image/png" if first_img.name.lower().endswith(".png") else "image/jpeg"
                        ocr_res = extract_image_via_gemini_vision(img_bytes, mime, api_key)
                        if ocr_res:
                            page_text = ocr_res
                    except Exception as err:
                        print(f"[Page OCR Error on page {page_num}]: {err}")

                if not page_text:
                    page_text = f"[Page {page_num} of {filename}]"

                formatted_page = format_text_tables(page_text)
                full_text_parts.append(f"\n--- Page {page_num} ---\n" + formatted_page)

                page_chunks = semantic_structure_chunking(formatted_page, page_num, filename, doc_type)
                all_chunks.extend(page_chunks)

        # 3. Text, Markdown, CSV, JSON, Code
        else:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            if ext == ".csv":
                doc_type = "table_data"
                # Format CSV cleanly into Markdown table
                lines = [l.strip() for l in content.splitlines() if l.strip()]
                if lines:
                    header = [c.strip() for c in lines[0].split(",")]
                    md_table = ["| " + " | ".join(header) + " |", "| " + " | ".join(["---"] * len(header)) + " |"]
                    for row in lines[1:]:
                        cells = [c.strip() for c in row.split(",")]
                        md_table.append("| " + " | ".join(cells) + " |")
                    content = "\n".join(md_table)

            formatted = format_text_tables(content)
            full_text_parts.append(formatted)
            chunks = semantic_structure_chunking(formatted, 1, filename, doc_type)
            all_chunks.extend(chunks)

    except Exception as e:
        print(f"[Document Processing Error for {filename}]: {e}")
        fallback_text = f"Content from {filename}"
        full_text_parts.append(fallback_text)
        all_chunks.append({
            "chunk_id": str(uuid.uuid4()),
            "page": 1,
            "heading": "",
            "section": "Page 1",
            "text": fallback_text,
            "is_table": False,
            "document_type": doc_type
        })

    full_text = "\n\n".join(full_text_parts)
    return full_text, all_chunks
