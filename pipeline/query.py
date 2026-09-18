# # pipeline/query.py
import re
from typing import Any, Dict, List
from loguru import logger

from pipeline.history_utils import extract_clean_history
from services.fuzzy_search_service import FuzzySearchService
from services.acronym_disambiguation_service import AcronymDisambiguationService
from services.conversation_context_service import ConversationContextService
from services.scope_messages import get_random_out_of_scope_message, normalize_markdown_tables
from pipeline.stream_utils import JsonStreamContentExtractor
from services.status_service import get_status_event


def format_structured_markdown(text: str) -> str:
    if not text:
        return ""
    lines = text.strip().split("\n")
    formatted = []

    for raw in lines:
        line = raw.strip()
        if not line:
            formatted.append("")
            continue

        if line.startswith("|"):
            formatted.append(raw)
            continue

        clean = re.sub(r"^#+\s*", "", line).strip()
        clean_no_stars = re.sub(r"^\*+|\*+$", "", clean).rstrip(":").strip()

        # Check if already a markdown header
        if line.startswith("#"):
            match = re.match(r"^#+", line)
            level = min(len(match.group(0)), 4) if match else 4
            hashes = "#" * level
            formatted.append(f"\n{hashes} **{clean_no_stars}**\n")
            continue

        # Detect Subheadings
        is_subheading = False
        if (
            not clean.startswith(("-", "*", "•", "1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9."))
            and len(clean) < 80
            and (
                line.endswith(":")
                or re.match(r"^(?:\d+\.|\bOverview\b|\bOperational\b|\bComponents\b|\bPrinciples\b|\bProcedures\b|\bPrevention\b|\bStarting\b|\bStopping\b|\bOperation\b|\bWorking\b|\bCore\b|\bKey\b|\bOperating\b|\bSafety\b|\bChecklist\b|\bStep-by-Step\b|\bArchitecture\b)", clean, re.IGNORECASE)
                or (not any(clean.endswith(p) for p in [".", "!", ";", ","]) and ":" not in clean)
            )
            and ":" not in clean[:-1]
        ):
            is_subheading = True

        if is_subheading:
            formatted.append(f"\n#### **{clean_no_stars}**\n")
            continue

        # Numbered list
        num_m = re.match(r"^(\d+\.)\s+(.+)$", clean)
        if num_m:
            prefix, body = num_m.group(1), num_m.group(2).strip()
            col_m = re.match(r"^([A-Za-z0-9\s/&,()_-]{2,50}):\s*(.+)$", body)
            if col_m and not body.startswith("**"):
                formatted.append(f"{prefix} **{col_m.group(1).strip()}:** {col_m.group(2).strip()}")
            else:
                formatted.append(f"{prefix} {body}")
            continue

        # Bullet list
        if re.match(r"^[-*•]\s+", clean):
            body = re.sub(r"^[-*•]\s+", "", clean).strip()
            col_m = re.match(r"^([A-Za-z0-9\s/&,()_-]{2,50}):\s*(.+)$", body)
            if col_m and not body.startswith("**"):
                formatted.append(f"- **{col_m.group(1).strip()}:** {col_m.group(2).strip()}")
            else:
                formatted.append(f"- {body}")
            continue

        # Key-Value property line without bullet
        col_m = re.match(r"^([A-Za-z0-9\s/&,()_-]{2,50}):\s+(.+)$", clean)
        if col_m and len(clean) < 250 and not clean.startswith(("http", "Note:")):
            formatted.append(f"- **{col_m.group(1).strip()}:** {col_m.group(2).strip()}")
            continue

        # Regular paragraph text
        formatted.append(clean)

    res = "\n".join(formatted)
    res = re.sub(r"\n{3,}", "\n\n", res)
    return normalize_markdown_tables(res.strip())


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

RELEVANCE VALIDATION — MANDATORY:
Before generating the answer, analyze the user's question and compare it with the retrieved document content.
1. Identify the exact topic and intent of the question.
2. Determine whether the retrieved content directly answers that topic.
3. Do not consider a document relevant merely because it contains matching keywords such as fuel, tank, cargo, temperature, or flash point.
4. If the retrieved content is unrelated, do not reproduce its table, procedures, responsibilities, or elaboration.
5. Retrieve or select content that directly addresses the user's question.
6. If relevant content is unavailable, clearly state that the answer cannot be verified from the available course material (e.g., "This topic is not covered in the available course material. Please ask a question related to the Marine/Maritime course content.").

Examples:
- Question: Describe low flash point fuels used onboard ships.
  Retrieved: Ship/Shore Information Exchange — Loading.
  Result: IRRELEVANT. Do not generate a cargo loading answer.
- Question: Describe low flash point fuels used onboard ships.
  Retrieved: A course section explaining marine low flash point fuels and their types.
  Result: RELEVANT. Generate the answer from that content.

STRICT RULES:
- Answer from the provided COURSE CONTEXT and any provided ADMIN-APPROVED FEEDBACK PREFERENCE.
- When an ADMIN-APPROVED FEEDBACK PREFERENCE is included, it represents the authoritative verified standard: you MUST seamlessly incorporate all its specific operational steps, parameters, checklist items, and technical points into the generated answer.
- Zero external hallucination.
- Structure the response with clear headings, structured tables, sequential steps, and formatted bullet points.

1. STRUCTURED & VISUALLY STUNNING MARITIME PRESENTATION:
- Begin with a clear, professional technical overview introducing the subject and its operational/engineering significance.
- Provide smooth narrative transitions between sections.
- Format the response using clean, expressive Markdown:
  • Clear Headings: `### Main Topic / Concept`
  • Subheadings: `#### Sub-Phase or Technical Category`
  • Comparison & Parameter Tables: Use clean Markdown tables to summarize component functions, operational parameters, pressure/flow limits, or comparison matrices where applicable.
  • Numbered sequential steps (`1. `, `2. `, `3. `) for operational workflows (e.g. Starting, Running, Stopping, Testing).
  • Bullet points (`- `) with bold labels for key parameters, formulas, and safety rules (`- **Parameter:** description`).
  • Bold critical engineering thresholds (e.g. `**O₂ content ≤ 8%**`, `**NPSH Margin ≥ 0.5m**`, `**Positive Suction Head**`).
  • Maintain clean paragraph explanations under each subheading instead of dumping flat unformatted lists.
  • Double line breaks between paragraphs and sections for clear readability.

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
- If the provided COURSE CONTEXT does not contain the information required to answer the user's question, do NOT use general knowledge or guess. Instead, respond with one of the following exact messages:
  "This topic is not covered in the available course material. Please ask a question related to the Marine/Maritime course content."
  "This question falls outside the available course material. Please ask something related to the Marine/Maritime course topics."
  "The requested information is not included in the current course content. Please ask a question relevant to the Marine/Maritime curriculum."
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
async def query_node(state, openai_service, suggestion_service, vector_store=None, on_token=None):

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
            "content": get_random_out_of_scope_message(),
            "sections": [],
            "chunks_used": [],
            "videos": [],
            "images": [],
            "pdfs": [],
            "question_suggestions": suggestion_service.generate_from_response(
                query=standalone_query,
                response_text="",
                chunks=[],
            ),
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
                return val[:3500]
        return ""

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
        if len(chunk_blocks) >= 4:
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

    feedback_pref = state.get("approved_feedback_preference")
    if feedback_pref and isinstance(feedback_pref, dict) and feedback_pref.get("preferred_response"):
        pref_response = feedback_pref.get("preferred_response", "").strip()
        eff_sim = float(feedback_pref.get("effective_similarity", 0.0) or 0.0)
        sim = float(feedback_pref.get("similarity", 0.0) or 0.0)

        # If high-confidence match (direct match to approved ticket), deliver the approved response directly!
        if (eff_sim >= 0.75 or sim >= 0.72) and pref_response:
            logger.success(
                f"🎯 [Direct Approved Response Delivery] Returning verified approved feedback response for '{feedback_pref.get('feedback_id')}' "
                f"(Similarity: {sim}, Effective: {eff_sim})"
            )
            if on_token:
                await on_token(get_status_event("generating"))
                tokens = re.findall(r'\s+|\S+', pref_response)
                for t in tokens:
                    await on_token({"type": "content", "token": t})

            suggestions = suggestion_service.generate_from_response(
                query=standalone_query,
                response_text=pref_response,
                topic_name=source_topic_name,
                chunks=chunks,
            )

            state["node_response"] = {
                "type": "query",
                "content": pref_response,
                "sections": [
                    {
                        "topic_code": source_topic_code or "APPROVED_STANDARD",
                        "topic_name": source_topic_name or "Approved Standard Response",
                        "content": pref_response,
                    }
                ],
                "chunks_used": chunks or [],
                "question_suggestions": suggestions,
                "videos": [],
                "images": [],
                "pdfs": [],
                "metadata": {
                    "source_layer": "Approved Feedback Memory (Verified Standard)",
                    "feedback_id": feedback_pref.get("feedback_id"),
                    "approved_similarity": sim,
                }
            }
            return state

        logger.info(f"✨ [Prompt Enrichment] Including Approved Feedback Preference in general query for '{feedback_pref.get('feedback_id')}'")
        pref_block = (
            f"\n\n===================================================\n"
            f"ADMIN-APPROVED FEEDBACK PREFERENCE (MANDATORY STANDARD CORRECTION):\n"
            f"Matching Query Pattern: {feedback_pref.get('question')}\n"
            f"Authoritative Approved Preferred Response:\n{feedback_pref.get('preferred_response')}\n\n"
            f"CRITICAL MANDATORY INSTRUCTION:\n"
            f"1. The above Approved Preferred Response represents the authoritative verified standard approved by HSQE administrators.\n"
            f"2. You MUST seamlessly integrate and feature all specific operational actions, valve line-ups, priming steps, and technical parameters (e.g. pressure thresholds, gas limits) from this approved response directly inside the primary operational workflow section (such as 'Starting Procedure' or 'Operational Steps') as distinct, numbered steps and bold bullet points.\n"
            f"3. Replace any generic or vague steps with the exact technical actions specified in the approved response above.\n"
            f"===================================================\n"
        )
        prompt += pref_block

    if on_token:
        await on_token(get_status_event("generating"))
        extractor = JsonStreamContentExtractor()
        accumulated_chunks = []
        async for chunk in openai_service.stream_chat(
            [{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=7000,
            category="QUERY",
        ):
            accumulated_chunks.append(chunk)
            deltas = extractor.process_chunk(chunk)
            for delta in deltas:
                await on_token({"type": "content", "token": delta})
        llm_response = "".join(accumulated_chunks)
    else:
        llm_response = await openai_service.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=7000,
            category="QUERY"
        )

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
            suggestions = suggestion_service.generate_from_response(
                query=standalone_query,
                response_text=raw_response,
                topic_name=source_topic_name,
                chunks=chunks,
            )

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
    for section in sections:
        if isinstance(section, dict) and "content" in section:
            section["content"] = format_structured_markdown(section["content"])

    full_content = "\n\n".join(
        section.get("content", "")
        for section in sections
    )

    if not suggestions:
        suggestions = suggestion_service.generate_from_response(
            query=standalone_query,
            response_text=full_content,
            topic_name=source_topic_name,
            chunks=chunks,
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