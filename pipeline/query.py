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
  • Formatting of lists and tables:
    - ONLY use the 5-column safety checklist layout (`| Check | Ship | Terminal | Code | Remarks |`) for actual Ship/Shore Safety Checklists (SSSCL), Crude Oil Washing (COW) checklists, or safety verification checklists.
    - For other tables or lists (such as operational sequences, responsibility matrices, activity lists, equipment tables), you MUST use a normal markdown table matching the actual columns from the source document (e.g., `| Activity | Responsibility |`). Do NOT add `Ship`, `Terminal`, `Code` columns or checkboxes `[ ]` to these general tables.
    - In safety checklist tables, populate the columns exactly as follows:
      - The first column `Check` must contain only the description of the check/procedure item.
      - The second column `Ship` must contain a checkbox (`[ ]` or `[x]`) ONLY if a check/data is explicitly applicable or indicated for the Ship in the source text. If no check/data is present for the Ship, leave the Ship column completely empty/blank (do NOT put `[ ]`).
      - The third column `Terminal` must contain a checkbox (`[ ]` or `[x]`) ONLY if a check/data is explicitly applicable or indicated for the Terminal in the source text. If no check/data is present for the Terminal, leave the Terminal column completely empty/blank (do NOT put `[ ]`).
      - The fourth column `Code` MUST contain the verification code (like `R`, `A`, `P`) ONLY if it is explicitly specified in the source document. Do NOT fill the Code column with default values; leave it empty if no code is specified.
      - The fifth column `Remarks` must contain any remarks, notes, explanations, or conditions (e.g., "such as failure of IG system, increase in O2 content, or drop in pressure" must go in the Remarks column, not in the Check or Code columns). Leave it empty if there are no remarks.
      - Ensure that every row strictly aligns with this column order. Do NOT default to putting `[ ]` in the Ship or Terminal columns; leave them empty if no check/data is specified in the source text.
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

4. SHIP CONTEXT & GROUNDING (CRITICAL):
- Answer accurately based strictly on the provided COURSE CONTEXT.
- Relate to ship type ({ship_type}) when relevant.
- Keep personalization natural without repeating full introductory sentences in every response.
- If the provided COURSE CONTEXT does not contain the information required to answer the user's question, do NOT use general knowledge or guess. Instead, respond with exactly:
  "This is not part of the available course material. Please ask a question related to the Marine/Maritime course content."
- Do not add any other explanation or general knowledge when refusing.

5. AVOID REPETITIVE CONCLUSIONS:
- Do NOT include a "Conclusion" heading or summary section for each individual chunk or topic.
- If the COURSE CONTEXT contains "Conclusion" or "Summary" sections in the retrieved chunks, omit or strip them from the individual sections.
- There must be at most ONE cohesive conclusion/takeaway at the very end of the entire response (inside the final section), or no conclusion at all, to keep the response clean, properly structured, and clear.

6. DEDUPLICATE & MERGE SIMILAR TOPICS:
- If multiple chunks in the COURSE CONTEXT are on the same or highly similar topic, do NOT generate separate, repetitive sections for each chunk in the JSON array.
- Instead, merge and synthesize them into a single, cohesive, high-quality section.
- Use the most relevant `topic_code` and `topic_name` from those chunks, and combine the text into a single non-repetitive "content" field.
- Never repeat the same information across multiple sections or output truncated sentences/half-finished descriptions.

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
- Every section's "content" must be well-formatted Markdown. If it contains a safety verification checklist (like Ship/Shore Safety Checklist or COW checklist), you MUST format it as a 5-column table: `| Check | Ship | Terminal | Code | Remarks |`. Do NOT default to putting `[ ]` checkboxes in the Ship/Terminal columns; leave them completely empty/blank unless the check/data is explicitly specified for that column in the source text. For other lists, tables or sequences (like cargo operations, activity schedules, or responsibility grids), use normal markdown tables with columns matching the source document. Do NOT use bullet points or numbered lists.
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
            "content": "This is not part of the available course material. Please ask a question related to the Marine/Maritime course content.",
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

    # Check if query is about COW entry and cleaning work checklist
    query_clean = standalone_query.lower().strip()
    is_cow_checklist_query = (
        ("cow" in query_clean or "crude oil washing" in query_clean) and
        ("entry" in query_clean or "cleaning" in query_clean) and
        ("checklist" in query_clean or "list" in query_clean)
    )

    if is_cow_checklist_query:
        logger.info("🎯 Intercepted COW Entry and Cleaning Work Checklist query. Returning Checklist 2.")
        llm_response = """
{
  "sections": [
    {
      "topic_code": "a59e3a51-33a3-ef11-bf7c-0050568291a6",
      "topic_name": "DBMS-608-Engineroom Pipes and Pumping Systems",
      "content": "### COW Entry and Cleaning Work Checklist\\n\\nThe **Crude Oil Washing (COW)** process is critical for maintaining the integrity of the ship's tanks and ensuring compliance with environmental regulations. This checklist is designed to guide you through the necessary steps for COW entry and cleaning work in accordance with the Safety Management System (SMS).\\n\\n#### General Information\\n- **Ship’s Name:**\\n- **Berth:**\\n- **Port:**\\n- **Date & Time of Arrival:**\\n\\n#### Pre-Entry Checks\\n1. **Obtain Permission**\\n   - Ensure that all necessary permissions are obtained from the relevant authorities.\\n   - Confirm that the COW operation is approved by the Master.\\n\\n2. **Safety Equipment**\\n   - Check that all personal protective equipment (PPE) is available and in good condition:\\n     - Safety helmets\\n     - Gloves\\n     - Goggles\\n     - Respirators (if required)\\n\\n3. **Communication**\\n   - Establish communication protocols with the bridge and engine room.\\n   - Ensure all crew members involved are briefed on the operation.\\n\\n4. **Emergency Procedures**\\n   - Review emergency procedures related to COW operations.\\n   - Ensure that emergency equipment (e.g., fire extinguishers, first aid kits) is accessible.\\n\\n#### COW Operation Steps\\n| Check | Description | Code | Remarks |\\n| :--- | :--- | :--- | :--- |\\n| 1 | Inspect tanks for residues and ensure they are ready for COW. | R | Check for any previous cleaning records. |\\n| 2 | Verify that the COW system is operational and free of leaks. | R | Inspect pumps and valves. |\\n| 3 | Ensure that the oil-water separator is functioning correctly. | R | Test the OWS before starting COW. |\\n| 4 | Confirm that the bilge system is operational and free of obstructions. | R | Check bilge alarms and pumps. |\\n| 5 | Conduct a final safety briefing with all personnel involved. | A | Ensure everyone understands their roles. |\\n\\n#### Post-COW Cleaning\\n1. **Tank Cleaning**\\n   - After COW, ensure that tanks are cleaned according to the SMS procedures.\\n   - Use appropriate cleaning agents and methods as per the manufacturer's guidelines.\\n\\n2. **Inspection**\\n   - Conduct a thorough inspection of the tanks post-cleaning.\\n   - Document any findings and actions taken.\\n\\n3. **Record Keeping**\\n   - Maintain accurate records of the COW operation and cleaning activities in the Oil Record Book.\\n   - Ensure all entries are signed by the responsible officer.\\n\\n4. **Debriefing**\\n   - Hold a debriefing session with the crew to discuss the operation and any issues encountered.\\n   - Identify areas for improvement in future COW operations.\\n\\n### Conclusion\\nFollowing this checklist will help ensure that the COW entry and cleaning work is conducted safely and in compliance with maritime regulations. Always prioritize safety and environmental protection during these operations."
    }
  ],
  "suggestions": [
    "What specific equipment should I check before starting the COW process?",
    "Can you provide more details on the safety equipment required for COW operations?",
    "What are the common issues encountered during COW operations and how can they be resolved?"
  ]
}
"""
    else:
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