# # pipeline/query.py
import re
from typing import Any, Dict, List
from loguru import logger

from pipeline.history_utils import extract_clean_history
from services.fuzzy_search_service import FuzzySearchService
from services.acronym_disambiguation_service import AcronymDisambiguationService
from services.conversation_context_service import ConversationContextService




QUERY_PROMPT = """
You are Marine Tutor AI, an expert maritime education assistant.

USER PROFILE:
Name: {name}
Role: {role}
Ship: {ship}
Ship_type: {ship_type}
Company: {company}

CURRENT USER QUESTION:
{user_query}

COURSE CONTEXT:
{chunks_content}

CRITICAL FORMATTING & SYNTHESIS INSTRUCTIONS:

1. STRUCTURED & PROFESSIONAL MARITIME PRESENTATION:
- Begin with a clear, natural conversational overview introducing the subject, its operational importance, and safety objectives.
- Provide smooth narrative transitions between sections so the response flows logically rather than abruptly presenting raw tables.
- Format the response using clean, expressive Markdown:
  • Clear Headings: `### Main Topic / Section`
  • Subheadings: `#### Sub-Phase or Verification Category`
  • Bold key terms, limits, and safety-critical numbers (e.g., `**O₂ content ≤ 8%**`, `**Positive pressure**`, `**Safe access**`)
  • Numbered lists (`1. `, `2. `) for sequential procedures
  • Bullet points (`- `) for safety checks, equipment lists, and precautions
  • Double line breaks between paragraphs and sections for clear readability

2. CHECKLISTS, FORMS & MARITIME PROCEDURES (FLOW & READABILITY):
- When presenting a checklist, form, or procedure:
  • Start with an introductory summary explaining the purpose and operational scope (e.g. pre-arrival exchange between ship and terminal).
  • If the checklist uses verification codes, include a brief code key upfront:
    - **`R` (Re-check):** Must be re-verified at agreed regular intervals (e.g., each watch).
    - **`A` (Agreement):** Requires mutual formal agreement between Ship & Terminal.
    - **`P` (Permission):** Requires formal written permit/permission before starting.
  • Include the form header information (Ship’s Name, Berth, Port, Date & Time of Arrival).
  • Organize checks into logical, well-structured verification tables:
    `| Check | Ship | Terminal | Code | Remarks |`
  • Include narrative context before specialized operations (e.g., explaining why COW checks or Tank Cleaning operations are required).
  • Conclude with practical operational takeaways or next steps.

3. ROLE-BASED RESPONSE STYLE:
- If Role contains "Captain" / "Management":
  → Focus on safety overview, go/no-go decisions, compliance, and risk controls.
- If Role contains "Chief Officer" / "OOW" / "2/O" / "3/O":
  → Focus on operational execution, step-by-step guidance, preparation, and deck safety.
- If Role contains "Engineer":
  → Focus on technical systems, pressure/temperature parameters, alarms, and troubleshooting.
- If Role contains "Crew", "AB", "OS":
  → Keep instructions simple, direct, and actionable with do/don't safety checklists.
- For all other roles, provide clear, practical explanations.

4. SHIP CONTEXT & GROUNDING:
- Answer accurately based strictly on the provided COURSE CONTEXT.
- Relate to ship type ({ship_type}) when relevant.
- Keep personalization natural without repeating full introductory sentences in every response.

RESPONSE FORMAT:
Return ONLY valid JSON (without surrounding code fences if possible):

{{
  "sections": [
    {{
      "topic_code": "<topic_code from COURSE CONTEXT>",
      "topic_name": "<topic_name from COURSE CONTEXT>",
      "content": "<clean markdown content with headings, bullet points, tables, and clear formatting>"
    }}
  ],
  "suggestions": [
    "<follow-up question 1>",
    "<follow-up question 2>",
    "<follow-up question 3>"
  ]
}}

RULES:
- Return ONLY the JSON object. Do not include text outside the JSON.
- Every section's "content" must be well-formatted Markdown with bullet points, numbered lists, tables where helpful, and bold headings.
"""

# =============================
# SAFE GET
# =============================
def safe_get(state: Any, key: str, default=None):
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


# =============================
# MAIN FUNCTION
# =============================
async def query_node(state, openai_service, suggestion_service, vector_store=None):

    # Init services
    fuzzy_search = FuzzySearchService(vector_store=vector_store)
    acronym_disambiguator = AcronymDisambiguationService(vector_store=vector_store)
    conversation_context = ConversationContextService(similarity_threshold=0.65)

    # State
    decision = safe_get(state, "router_decision", {}) or {}
    chunks = safe_get(state, "retrieval_chunks", [])
    query = safe_get(state, "current_query", "")
    standalone_query = safe_get(state, "standalone_query", query)

    primary_chunk = chunks[0] if chunks else {}

    source_topic_code = primary_chunk.get("topic_code", "")
    source_topic_name = primary_chunk.get("topic_name", "")

    understanding_summary = safe_get(state, "understanding_summary", "")
    is_user_greeting = safe_get(state, "is_user_greeting", False)

    if is_user_greeting:
        understanding_summary = ""

    existing_history = list(safe_get(state, "meaningful_history", []) or [])
    existing_messages = list(safe_get(state, "meaningful_messages", []) or [])

    # =============================
    # USER PROFILE FIX (ONLY CHANGE)
    # =============================
    user_profile = (
        safe_get(state, "user_profile") or
        safe_get(state, "user") or   # fallback support
        {}
    )

    logger.info(f"USER PROFILE RECEIVED: {user_profile}")

    user_memory = safe_get(state, "user_memory", {}) or {}

    # ACRONYM FILTER
  
    def filter_chunks(query, chunks):
        q = query.strip().upper()
        if not (2 <= len(q) <= 6 and q.isalpha()):
            return chunks
        return [c for c in chunks if q in (c.get("content","") + c.get("topic_name","")).upper()] or chunks

    chunks = filter_chunks(standalone_query, chunks)

    if not chunks:

        response = {
            "type": "query",
            "content": (
                "I am Marine Tutor AI. "
                "I can only answer maritime, navigation, cargo, "
                "marine engineering, safety, COLREGS, ship operations, "
                "and maritime training questions."
            ),
            "sections": [],
            "chunks_used": [],
            "videos": [],
            "images": [],
            "pdfs": [],
            "question_suggestions": [
                "What is anchor watch?",
                "Explain COLREG Rule 15",
                "What is boiler design?"
            ],
            "metadata": {
                "short_topic": "marine",
                "routing_reason": "off_topic"
            }
        }

        state["node_response"] = response
        return state


    # FORMAT CHUNKS

    def format_chunk(c):
        for field in ["content", "topic_content", "summary", "text"]:
            val = c.get(field)
            if val:
                return val[:8000]
        return ""

    # chunks_text = "\n\n---\n\n".join(
    #     [format_chunk(c) for c in chunks if format_chunk(c)]
    # )

    chunk_blocks = []
    seen_chunk_texts = set()

    for c in chunks:
        formatted = format_chunk(c).strip()
        if not formatted:
            continue
        sig = formatted[:150].lower()
        if sig in seen_chunk_texts:
            continue
        seen_chunk_texts.add(sig)

        chunk_blocks.append(
            f"""
    TOPIC CODE:
    {c.get("topic_code","")}

    TOPIC NAME:
    {c.get("topic_name","")}

    CONTENT:
    {formatted}
    """
        )
        if len(chunk_blocks) >= 5:
            break

    chunks_text = "\n\n---\n\n".join(chunk_blocks)

    # MAIN PROMPT (NOW FILLED)

    prompt = QUERY_PROMPT.format(
        # user_query=query,
        user_query=standalone_query,
        chunks_content=chunks_text,
        name=user_profile.get("name", ""),
        role=user_profile.get("role", ""),
        ship=user_profile.get("ship_name", ""),
        company=user_profile.get("company_name", ""),
        ship_type=user_profile.get("ship_type", ""),
        company_id=user_profile.get("company_id", "")
    )

    # LLM CALL

    llm_response = await openai_service.chat(
        [{"role": "user", "content": prompt}],
        temperature=0.0,
        category="QUERY"
    )

    # EXTRACT ANSWER + SUGGESTIONS

    def extract(text):
        answer = text
        suggestions = []

        if "[SUGGESTIONS SECTION]" in text:
            parts = text.split("[SUGGESTIONS SECTION]")
            answer = parts[0].replace("[ANSWER SECTION]", "").strip()

            for line in parts[1].split("\n"):
                line = re.sub(r"^\d+[\.\)]\s*", "", line.strip())
                if line.endswith("?"):
                    suggestions.append(line)

        if not suggestions:
            suggestions = [
                "What are the key concepts?",
                "How is this applied?",
                "What safety considerations exist?"
            ]

        return answer, suggestions[:5]

    # answer, suggestions = extract(llm_response)

    import json

    raw_response = (llm_response or "").strip()
    # Strip markdown code fences if present (e.g. ```json ... ```)
    if raw_response.startswith("```"):
        raw_response = re.sub(r"^```(?:json)?\s*", "", raw_response)
        raw_response = re.sub(r"\s*```$", "", raw_response).strip()

    sections = []
    suggestions = []

    try:
        parsed = json.loads(raw_response)
        sections = parsed.get("sections", [])
        suggestions = parsed.get("suggestions", [])

        if not isinstance(sections, list):
            sections = [{
                "topic_code": source_topic_code,
                "topic_name": source_topic_name,
                "content": str(sections)
            }]

    except Exception as e:
        logger.warning(f"Failed to parse LLM JSON response directly: {e}. Attempting regex recovery.")
        json_match = re.search(r"\{[\s\S]*\}", raw_response)
        parsed_ok = False
        if json_match:
            try:
                recovered = json.loads(json_match.group(0))
                sections = recovered.get("sections", [])
                suggestions = recovered.get("suggestions", [])
                if isinstance(sections, list) and sections:
                    parsed_ok = True
            except Exception:
                pass

        if not parsed_ok or not sections:
            sections = [{
                "topic_code": source_topic_code,
                "topic_name": source_topic_name,
                "content": raw_response
            }]
            suggestions = [
                "What are the key safety precautions?",
                "Can you explain the step-by-step procedure?",
                "What are the emergency response protocols?"
            ]

    # Inject understanding section
    # if understanding_summary and understanding_summary != "EMPTY":
    #     answer = f"""
    #     ### 
    #     {understanding_summary}

    #     {answer}
    #     """.strip()


    # MEDIA (Deduplicated across chunks)

    videos, images, pdfs = [], [], []
    seen_videos = set()
    seen_images = set()
    seen_pdfs = set()

    for c in chunks:
        for v in c.get("videos", []):
            if isinstance(v, dict):
                v_key = (
                    v.get("url")
                    or v.get("Url")
                    or v.get("videourl")
                    or v.get("id")
                    or v.get("Id")
                    or v.get("title")
                    or v.get("Title")
                )
                if v_key and v_key not in seen_videos:
                    seen_videos.add(v_key)
                    videos.append(v)

        for img in c.get("images", []):
            if isinstance(img, dict):
                img_key = (
                    img.get("url")
                    or img.get("Url")
                    or img.get("id")
                    or img.get("Id")
                    or img.get("base64")
                )
                if img_key and img_key not in seen_images:
                    seen_images.add(img_key)
                    images.append(img)

        for pdf in c.get("pdfs", []):
            if isinstance(pdf, dict):
                pdf_key = (
                    pdf.get("url")
                    or pdf.get("Url")
                    or pdf.get("id")
                    or pdf.get("Id")
                    or pdf.get("title")
                    or pdf.get("Title")
                )
                if pdf_key and pdf_key not in seen_pdfs:
                    seen_pdfs.add(pdf_key)
                    pdfs.append(pdf)

    # RESPONSE

    full_content = "\n\n".join(
        section.get("content", "")
        for section in sections
    )

    response = {
        "type": "query",
        "content": full_content,
        "sections": sections,
        "chunks_used": chunks,
        "videos": videos[:10],
        "video_suggestions": videos[:10],
        "images": images[:5],
        "pdfs": pdfs[:5],
        "question_suggestions": suggestions,
        "metadata": {
            "short_topic": decision.get("short_topic", "marine"),
            "routing_reason": decision.get("reason", "query")
        }
    }

    history_entry = {
        "node_type": "query",
        "content": sections,
        "user_query": query,
        "category": "QUERY"
    }

    state["node_response"] = response
    state["meaningful_history"] = existing_history + [history_entry]
    state["meaningful_messages"] = existing_messages + [history_entry]
    state["user_memory"] = user_memory

    return state




# async def query_node_stream(
#     state,
#     openai_service,
#     suggestion_service,
#     vector_store=None,
# ):

#     # SAME CODE FROM query_node()
#     # COPY EVERYTHING UNTIL prompt creation

#     decision = safe_get(state, "router_decision", {}) or {}
#     chunks = safe_get(state, "retrieval_chunks", [])
#     query = safe_get(state, "current_query", "")
#     standalone_query = safe_get(state, "standalone_query", query)

#     user_profile = (
#         safe_get(state, "user_profile") or {}
#     )

#     def format_chunk(c):
#         for field in ["content", "topic_content", "summary", "text"]:
#             val = c.get(field)
#             if val:
#                 return val[:8000]
#         return ""

#     chunks_text = "\n\n---\n\n".join(
#         [format_chunk(c) for c in chunks if format_chunk(c)]
#     )

#     prompt = QUERY_PROMPT.format(
#         user_query=standalone_query,
#         chunks_content=chunks_text,
#         name=user_profile.get("name", ""),
#         role=user_profile.get("role", ""),
#         ship=user_profile.get("ship_name", ""),
#         company=user_profile.get("company_name", ""),
#         ship_type=user_profile.get("ship_type", "")
#     )

#     # STREAM FROM OPENAI

#     async for token in openai_service.stream_chat(
#         [{"role": "user", "content": prompt}],
#         temperature=0.0,
#     ):
#         yield token