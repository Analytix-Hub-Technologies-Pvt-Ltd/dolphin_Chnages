# # pipeline/query.py
import json
import re
from typing import Any, Dict, List, Optional
from loguru import logger

from pipeline.history_utils import extract_clean_history
from services.fuzzy_search_service import FuzzySearchService
from services.acronym_disambiguation_service import AcronymDisambiguationService
from services.conversation_context_service import ConversationContextService
from services.pdf_service import pdf_service
from services.off_topic_detector import is_off_topic_query




QUERY_PROMPT = """
You are Marine Tutor AI answering marine education questions.

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

CRITICAL INSTRUCTIONS:

1. COMPREHENSIVE, ELABORATE & IN-DEPTH EXPLANATION (MANDATORY):
- When the question covers a topic, procedure, system, rule, or piece of equipment, provide an in-depth, thorough, and elaborate explanation drawing from all available details in the COURSE CONTEXT.
- Do NOT artificially compress, truncate, or summarize into just a few brief bullet points if rich content exists.
- If the question contains extensive content in the COURSE CONTEXT, expand and elaborate fully on all relevant aspects:
  * In-depth working principles, architectural overviews, and system descriptions.
  * Comprehensive step-by-step operational procedures (preparation, execution, monitoring, and post-operation checks).
  * Technical specifications, operating parameters, thresholds, limits, pressures, temperatures, and alarm setpoints mentioned in the context.
  * Safety precautions, risk mitigations, hazard controls, and required Personal Protective Equipment (PPE).
  * Applicable maritime conventions, codes, and regulations (e.g., SOLAS, MARPOL, STCW, COLREGS, ISM, ISPS) where present in the context.
  * Emergency actions, failure modes, alarms, troubleshooting steps, and contingency plans.
  * Maintenance routines, testing protocols, inspections, and documentation/logbook requirements.
- Explain both the operational "How" and the underlying "Why" to provide deep educational value.
- If multiple retrieved topics or subtopics in the COURSE CONTEXT contain relevant information, synthesize ALL available details across comprehensive sections rather than stopping after a single summary point.
- The response should be as rich, extensive, and complete as the available COURSE CONTEXT supports.

2. ROLE-BASED RESPONSE STYLE:

- If Role contains "Captain":
  → Give high-level, decision-focused explanation
  → Emphasize safety, critical risks, and management impact
  → Include go/no-go thinking where relevant

- If Role contains "Chief Officer":
  → Focus on planning, supervision, and execution
  → Include step-by-step operational guidance
  → Highlight safety controls and preparation

- If Role contains "2/O" or "3/O" or "OOW":
  → Give practical, onboard operational explanation
  → Include procedures, monitoring, and communication
  → Focus on what to do during the task

- If Role contains "Engineer":
  → Focus on technical systems and working principles
  → Include parameters (pressure, temperature, alarms)
  → Explain cause, effect, and preventive actions

- If Role contains "Crew", "AB", or "OS":
  → Provide clear, practical onboard instructions
  → Use checklist-style instructions and clear procedural points
  → Focus on do/don’t actions, safety, and operational precautions

- If Role contains "HSQE" or "Management":
  → Focus on compliance, procedures, and audits
  → Include risks, controls, and documentation

- If Role contains "Auditor" or "Inspector":
  → Focus on verification and compliance gaps
  → Provide checklist-style evaluation points
  → Highlight common deficiencies  

- If Role contains "Cook" or non-technical role:
  → Explain clearly with foundational safety awareness
  → Focus on safety, hygiene, and emergency awareness

- For any other roles, define similar rules following the same pattern.

3. SHIP CONTEXT:
- If relevant, relate answer to ship and ship type (e.g., ship name and Chemical Carrier)

4. STRICT DOMAIN RESTRICTIONS & MARITIME GROUNDING:
- DOMAIN RESTRICTION: You are strictly Marine Tutor AI. You assist with maritime education, navigation, marine engineering, cargo operations, seamanship, nautical science, shipboard safety, risk assessment, enclosed spaces, hot work, COLREGS, SOLAS, MARPOL, STCW, and ship operations.
- HIGH-PRIORITY SME VERIFIED GUIDANCE: If COURSE CONTEXT contains "[OFFICIAL SME-VERIFIED GUIDANCE - HIGH PRIORITY OVERRIDE]", this is an approved, human-in-the-loop validated procedural standard. You MUST strictly prioritize and adhere to this verified guidance as the authoritative truth in your response sections.
- FOR ALL MARITIME, SHIPBOARD, SAFETY, AND ENGINEERING QUESTIONS (e.g., enclosed space entry, risk assessments, hazard identification, permit-to-work, atmospheric testing, navigation, firefighting, ship machinery, cargo operations, seamanship):
  * You MUST ALWAYS provide a comprehensive, educational, and professionally structured response.
  * Base your answer on the provided COURSE CONTEXT, thoroughly extracting and organizing all relevant procedures, safety precautions, hazard controls, equipment requirements, and steps.
  * Synthesize standard maritime safety principles (e.g., Hazard Identification, Risk Analysis & Evaluation, Control Measures, Permit-to-Work, Atmospheric Monitoring, Ventilation, PPE, Emergency Rescue Preparedness, and IMO / SOLAS / ISM Code guidelines) to comprehensively answer operational safety questions.
  * NEVER claim that legitimate maritime, safety, navigation, engineering, or vessel operation topics fall outside the marine training curriculum.

- ZERO HALLUCINATION & NO FALSE ASSOCIATIONS (CRITICAL MANDATORY RULE):
  * NEVER fabricate, stretch, or assume connections between everyday consumer tech (e.g., iPhone, Android, smartphones, consumer electronics, laptops, gaming) and shipboard internal equipment.
  * Specifically, if the user asks about an everyday gadget or consumer product (such as 'what is iphone?'), DO NOT answer with internal vessel communication systems, PA systems, or sound-powered phones! An iPhone is a consumer smartphone from Apple, NOT a shipboard internal phone system!
  * If the question is about non-marine technology, everyday gadgets, or general world trivia, you MUST return the OUT-OF-SCOPE response immediately, even if COURSE CONTEXT contains superficially matching words like 'phone' or 'communication'.

- OUT-OF-SCOPE NON-MARITIME QUESTIONS ONLY (MANDATORY):
  If the user's question is entirely UNRELATED to maritime, shipping, seafaring, or ship operations (such as smartphones/iPhone/Android, consumer electronics, computer programming/coding, movies/cinema, sports, recipes/cooking, politics, non-marine general trivia):
  → You MUST NOT attempt to answer non-marine topics.
  → You MUST return exactly ONE section formatted as:
    {{
      "sections": [
        {{
          "topic_code": "",
          "topic_name": "",
          "content": "I am Marine Tutor AI, specialized exclusively in maritime education, navigation, marine engineering, ship operations, safety regulations, and seafarer training.\\n\\nThis topic is outside the marine training curriculum. Please ask questions related to maritime and shipboard operations (e.g., COLREGS, marine diesel engines, firefighting, navigation, or port state control)."
        }}
      ],
      "suggestions": [
        "What is anchor watch procedure?",
        "How does COLREG Rule 15 handle a crossing situation?",
        "What are the checks for marine auxiliary boiler?"
      ]
    }}

5. PERSONALIZATION CONTROL:
- Directly and comprehensively answer the maritime query using the course content.
- Do NOT generate generic welcome greetings or system introductions (e.g., "Welcome to Dolphin AI...", "Answers to your questions will be based on...").
- Tailor technical depth and operational context naturally to the user's role and vessel type without formulaic preambles.

RESPONSE FORMAT:

Return ONLY valid JSON.

{{
  "sections": [
    {{
      "topic_code": "",
      "topic_name": "",
      "content": ""
    }}
  ],
  "suggestions": [
    "Relevant follow-up question 1?",
    "Relevant follow-up question 2?",
    "Relevant follow-up question 3?"
  ]
}}

SUGGESTIONS RULES:
- "suggestions" MUST be exactly 3 concise, relevant maritime follow-up questions that the user might want to ask next.
- Each suggestion MUST be phrased as a question and end with a question mark '?'.
- Do NOT write advice or imperatives (e.g., do NOT say "Review the procedures...", "Practice...", "Familiarize...").

FORMATTING & STRUCTURE RULES:
- Structure the text inside each section's "content" using clean, professional, and detailed Markdown.
- If introducing topics, distinct procedures, or concepts, use clear markdown headings (e.g., "### Procedure Name" or "### Section Title") for titles.
- Organize explanations into well-formed paragraphs separated by double newlines.
- Use numbered lists (1. 2. 3.) for step-by-step procedures, sequential operations, or numbered regulations.
- Use bullet points (- ) for checklists, precautions, equipment, or key points.
- Use bold (**term**) for important terminology, warnings, limits, or parameters.
- Never run multiple distinct titles and paragraphs together without headings and paragraph breaks.
- Every section MUST correspond to the retrieved topic from COURSE CONTEXT.
- If multiple topics or extensive details are in COURSE CONTEXT, include multiple comprehensive sections to cover everything thoroughly.
- Use the exact topic_code from COURSE CONTEXT.
- Return ONLY valid JSON with no text or markdown outside the JSON structure.
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

    # 🚫 ZERO HALLUCINATION GUARD: Instant check if query is off-topic
    if is_off_topic_query(query) or is_off_topic_query(standalone_query):
        logger.info(f"🚫 [QUERY_NODE] Off-topic query detected: '{standalone_query}' (query='{query}')")
        out_of_scope_text = (
            "I am Marine Tutor AI, specialized exclusively in maritime education, navigation, "
            "marine engineering, ship operations, safety regulations, and seafarer training.\n\n"
            "This topic is outside the marine training curriculum. Please ask questions related to "
            "maritime and shipboard operations (e.g., COLREGS, marine diesel engines, firefighting, navigation, or port state control)."
        )
        response = {
            "type": "query",
            "content": out_of_scope_text,
            "sections": [
                {
                    "topic_code": "",
                    "topic_name": "",
                    "content": out_of_scope_text,
                }
            ],
            "chunks_used": [],
            "videos": [],
            "images": [],
            "pdfs": [],
            "question_suggestions": [
                "What is anchor watch procedure?",
                "How does COLREG Rule 15 handle a crossing situation?",
                "What are the checks for marine auxiliary boiler?"
            ],
            "metadata": {
                "short_topic": "marine",
                "routing_reason": "off_topic",
                "out_of_scope": True,
            }
        }
        state["retrieval_chunks"] = []
        state["video_suggestions"] = []
        state["company_answer"] = None
        state["node_response"] = response
        return state

    # ACRONYM FILTER
  
    def filter_chunks(query, chunks):
        q = query.strip().upper()
        if not (2 <= len(q) <= 6 and q.isalpha()):
            return chunks
        return [c for c in chunks if q in (c.get("content","") + c.get("topic_name","")).upper()] or chunks

    chunks = filter_chunks(standalone_query, chunks)

    if not chunks:

        out_of_scope_text = (
            "I am Marine Tutor AI, specialized exclusively in maritime education, navigation, "
            "marine engineering, ship operations, safety regulations, and seafarer training.\n\n"
            "This topic is outside the marine training curriculum. Please ask questions related to "
            "maritime and shipboard operations (e.g., COLREGS, marine diesel engines, firefighting, navigation, or port state control)."
        )

        response = {
            "type": "query",
            "content": out_of_scope_text,
            "sections": [
                {
                    "topic_code": "",
                    "topic_name": "",
                    "content": out_of_scope_text,
                }
            ],
            "chunks_used": [],
            "videos": [],
            "images": [],
            "pdfs": [],
            "question_suggestions": [
                "What is anchor watch procedure?",
                "How does COLREG Rule 15 handle a crossing situation?",
                "What are the checks for marine auxiliary boiler?"
            ],
            "metadata": {
                "short_topic": "marine",
                "routing_reason": "off_topic",
                "out_of_scope": True,
            }
        }

        state["retrieval_chunks"] = []
        state["video_suggestions"] = []
        state["company_answer"] = None
        state["node_response"] = response
        return state

    # 🌟 IMMEDIATE DIRECT SME-APPROVED GUIDANCE HANDLER
    sme_chunk = next((c for c in chunks if c.get("_is_sme_approved")), None)
    if sme_chunk:
        sme_resp = (
            sme_chunk.get("_sme_preferred_response")
            or sme_chunk.get("topic_content")
            or sme_chunk.get("content")
            or ""
        )
        logger.info(f"🌟 Direct SME Approved Guidance match found! Serving verified response directly (len={len(sme_resp)})")
        clean_sme_resp = re.sub(
            r"^SME Approved Guidance\s*\n*\[OFFICIAL SME-VERIFIED GUIDANCE - HIGH PRIORITY OVERRIDE\]:\s*\n*",
            "",
            sme_resp,
            flags=re.IGNORECASE
        ).strip()

        primary_title = "SME Approved Guidance"
        for c in chunks:
            if not c.get("_is_sme_approved") and c.get("topic_name"):
                primary_title = c.get("topic_name")
                break

        sections = [{
            "topic_code": "SME-OFFICIAL-GUIDANCE",
            "topic_name": primary_title,
            "content": clean_sme_resp
        }]
        suggestions = [
            f"What are the key safety precautions for {primary_title}?",
            f"What checklist items are required before starting {primary_title}?",
            f"What emergency procedures apply to {primary_title}?"
        ]

        videos, images, pdfs = [], [], []
        for c in chunks:
            if not c.get("_is_sme_approved"):
                videos += c.get("videos", [])
                images += c.get("images", [])
                pdfs += c.get("pdfs", [])

        response = {
            "type": "query",
            "content": clean_sme_resp,
            "sections": sections,
            "chunks_used": chunks,
            "videos": videos[:10],
            "images": images[:5],
            "pdfs": pdfs[:5],
            "question_suggestions": suggestions,
            "metadata": {
                "short_topic": "marine",
                "routing_reason": "sme_approved_override",
                "out_of_scope": False,
                "is_sme_approved": True,
                "feedback_id": sme_chunk.get("_sme_feedback_id"),
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

        stream_callback = safe_get(state, "stream_callback")
        if stream_callback:
            try:
                await stream_callback({
                    "type": "source_topic",
                    "topic_code": "SME-OFFICIAL-GUIDANCE",
                    "topic_name": primary_title,
                })
                tokens = re.findall(r'\S+\s*|\n+', clean_sme_resp)
                for tok in tokens:
                    await stream_callback({
                        "type": "content",
                        "token": tok,
                    })
                state["_streamed_live"] = True
            except Exception as e:
                logger.warning(f"Failed streaming SME guidance: {e}")

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

    for c in chunks:

        chunk_blocks.append(
            f"""
    TOPIC CODE:
    {c.get("topic_code","")}

    TOPIC NAME:
    {c.get("topic_name","")}

    CONTENT:
    {format_chunk(c)}
    """
        )

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

    # LLM CALL (JSON Mode + max_tokens for high-speed response with Real-Time Streaming)
    stream_callback = safe_get(state, "stream_callback")
    streamed_live = False

    if stream_callback:
        from services.stream_extractor import StreamJsonExtractor
        extractor = StreamJsonExtractor()
        raw_chunks = []

        # Emit initial source topic so UI can display topic pill immediately
        if source_topic_code or source_topic_name:
            try:
                await stream_callback({
                    "type": "source_topic",
                    "topic_code": source_topic_code,
                    "topic_name": source_topic_name,
                })
            except Exception as e:
                logger.warning(f"Failed to stream initial source topic: {e}")

        try:
            async for chunk in openai_service.stream_chat(
                [{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=2500,
                response_format={"type": "json_object"},
            ):
                raw_chunks.append(chunk)
                events = extractor.feed(chunk)
                for ev in events:
                    if ev[0] == 'token':
                        await stream_callback({
                            "type": "content",
                            "token": ev[1],
                        })
                        streamed_live = True
                    elif ev[0] == 'topic':
                        code, name, count = ev[1], ev[2], ev[3]
                        if count > 1:
                            await stream_callback({"type": "content", "token": "\n\n"})
                            await stream_callback({
                                "type": "source_topic",
                                "topic_code": code or source_topic_code,
                                "topic_name": name or source_topic_name,
                            })
        except Exception as e:
            logger.error(f"❌ Real-time token streaming failed: {e}")

        llm_response = "".join(raw_chunks)
        if not llm_response:
            llm_response = await openai_service.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.0,
                category="QUERY",
                max_tokens=2500,
                response_format={"type": "json_object"},
            )
    else:
        llm_response = await openai_service.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.0,
            category="QUERY",
            max_tokens=2500,
            response_format={"type": "json_object"},
        )

    state["_streamed_live"] = streamed_live

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

    def _parse_llm_json(raw_text: str) -> Optional[Dict[str, Any]]:
        if not raw_text or not isinstance(raw_text, str):
            return None
        cleaned = raw_text.strip()
        
        # 1. If wrapped in markdown code block, extract candidate
        block_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
        candidate_json = block_match.group(1).strip() if block_match else cleaned

        # 2. Try direct parse with strict=False
        try:
            return json.loads(candidate_json, strict=False)
        except Exception:
            pass

        # 3. Find outermost matching { and }
        first_brace = candidate_json.find("{")
        last_brace = candidate_json.rfind("}")
        if first_brace != -1 and last_brace > first_brace:
            try:
                return json.loads(candidate_json[first_brace:last_brace + 1], strict=False)
            except Exception:
                pass

        # 4. Regex fallback: extract sections and suggestions even if json is slightly malformed
        try:
            sections = []
            section_matches = re.findall(
                r'\{\s*"topic_code"\s*:\s*"(?P<code>.*?)"\s*,\s*"topic_name"\s*:\s*"(?P<name>.*?)"\s*,\s*"content"\s*:\s*"(?P<content>.*?)(?<!\\)"\s*\}',
                candidate_json,
                re.DOTALL
            )
            for code, name, content in section_matches:
                c_clean = content.encode().decode('unicode_escape', errors='ignore') if '\\n' in content else content
                sections.append({
                    "topic_code": code.strip(),
                    "topic_name": name.strip(),
                    "content": c_clean.strip()
                })

            suggestions = []
            sugg_match = re.search(r'"suggestions"\s*:\s*\[(.*?)\]', candidate_json, re.DOTALL)
            if sugg_match:
                raw_suggs = re.findall(r'"([^"\n\r]+?\?)"', sugg_match.group(1))
                suggestions = [s.strip() for s in raw_suggs if s.strip()]

            if sections:
                return {
                    "sections": sections,
                    "suggestions": suggestions
                }
        except Exception as e:
            logger.warning(f"Regex JSON fallback parse failed: {e}")

        return None

    logger.info(f"QUERY_NODE RAW LLM RESPONSE: {repr(llm_response)}")
    parsed = _parse_llm_json(llm_response)
    logger.info(f"QUERY_NODE PARSED: {parsed}")

    if parsed and isinstance(parsed, dict):
        sections = parsed.get("sections", [])
        if not isinstance(sections, list):
            sections = []

        raw_suggestions = parsed.get("suggestions", [])
        cleaned_suggs = []
        for s in (raw_suggestions or []):
            if isinstance(s, str) and s.strip():
                st = s.strip()
                if not st.endswith("?"):
                    st = st.rstrip(".!") + "?"
                cleaned_suggs.append(st)
        if not cleaned_suggs and sections:
            top_name = sections[0].get("topic_name") or "this topic"
            cleaned_suggs = [
                f"What are the key rules for {top_name}?",
                f"What are the safety precautions for {top_name}?",
                f"How is {top_name} verified during inspections?",
            ]
        suggestions = cleaned_suggs[:3]
    else:
        # Fallback if model output is free-form text: strip any stray markdown codeblock wrappers
        clean_content = re.sub(r"```(?:json)?\s*\{.*?\}\s*```", "", llm_response, flags=re.DOTALL).strip()
        clean_content = re.sub(r'^\s*\{\s*"sections"\s*:\s*\[\s*', '', clean_content)
        if not clean_content:
            clean_content = llm_response

        primary_title = primary_chunk.get("topic_name") or "Maritime Guidance"
        sections = [{
            "topic_code": source_topic_code,
            "topic_name": primary_title,
            "content": clean_content
        }]
        suggestions = [
            f"What are the key principles of {primary_title}?",
            f"What safety precautions apply to {primary_title}?",
            f"How is {primary_title} inspected on board?",
        ]

    # Inject understanding section
    # if understanding_summary and understanding_summary != "EMPTY":
    #     answer = f"""
    #     ### 
    #     {understanding_summary}

    #     {answer}
    #     """.strip()


    # MEDIA
    is_out_of_scope = any(
        (
            s.get("topic_name", "").strip().lower() in ("out of scope", "off topic", "unrelated")
            or "outside the marine training curriculum" in s.get("content", "").lower()
            or "outside the maritime curriculum" in s.get("content", "").lower()
            or "specialized exclusively in maritime" in s.get("content", "").lower()
            or ("marine tutor ai" in s.get("content", "").lower() and "outside" in s.get("content", "").lower())
        )
        for s in sections
    )

    if is_out_of_scope:
        state["retrieval_chunks"] = []
        state["video_suggestions"] = []
        state["company_answer"] = None

    videos, images, pdfs = [], [], []

    if not is_out_of_scope:
        for c in chunks:
            c_tc = c.get("topic_code")
            c_tn = c.get("topic_name")
            for v in c.get("videos", []):
                if isinstance(v, dict):
                    v_copy = dict(v)
                    v_copy.setdefault("topic_code", c_tc)
                    v_copy.setdefault("topic_name", c_tn)
                    videos.append(v_copy)
            for img in c.get("images", []):
                if isinstance(img, dict):
                    img_copy = dict(img)
                    img_copy.setdefault("topic_code", c_tc)
                    img_copy.setdefault("topic_name", c_tn)
                    images.append(img_copy)
            for p in c.get("pdfs", []):
                if isinstance(p, dict):
                    p_copy = pdf_service.resolve_pdf(p, chunk_topic_name=c_tn)
                    if p_copy and p_copy.get("link") and (p_copy.get("title") or "").strip():
                        p_title = (p_copy.get("title") or "").strip()
                        GENERIC_TITLES = {
                            "reference document", "document", "course document", "untitled",
                            "exam guide", "introduction", "overview", "references", "table of contents",
                            "contents", "none", "null", "image", "figure", "pdf", "index"
                        }
                        if p_title.lower() in GENERIC_TITLES or len(p_title) < 3:
                            continue

                        from services.maritime_acronyms import (
                            has_conflicting_acronym,
                            find_acronyms_in_query,
                            get_acronym_expansion,
                        )
                        curr_q = (state.get("current_query") or state.get("standalone_query") or "").strip()
                        if has_conflicting_acronym(curr_q, f"{p_title} {p.get('About', '')} {c_tn}"):
                            continue

                        q_acrs = find_acronyms_in_query(curr_q)
                        if q_acrs:
                            has_acr = False
                            t_and_top = f"{p_title} {c_tn}".lower()
                            for acr in q_acrs:
                                if re.search(rf'\b{re.escape(acr.lower())}\b', t_and_top):
                                    has_acr = True
                                    break
                                for exp in get_acronym_expansion(acr):
                                    if exp.lower() in t_and_top:
                                        has_acr = True
                                        break
                                if has_acr:
                                    break
                            if not has_acr:
                                continue

                        if len(p_title.split()) == 1 and p_title.lower() in ("chemicals", "difficulties", "necessary", "operation", "issues"):
                            if p_title.lower() not in curr_q.lower():
                                continue

                        p_copy.setdefault("topic_code", c_tc)
                        p_copy.setdefault("topic_name", c_tn)
                        pdfs.append(p_copy)

    pdfs = pdf_service.deduplicate_titles(pdfs)[:3]

    # RESPONSE
    full_content_parts = []
    for section in sections:
        c = (section.get("content") or "").strip()
        topic_name = (section.get("topic_name") or "").strip()

        # Clean any extra newlines
        c = re.sub(r'\n{3,}', '\n\n', c)

        # Ensure markdown headings have blank lines before and after
        c = re.sub(r'([^\n#\s])\s*\n*(#{1,6}\s+[^\n]+)', r'\1\n\n\2\n\n', c)

        if is_out_of_scope or topic_name.lower() in ("out of scope", "off topic", "unrelated"):
            topic_name = ""
            section["topic_name"] = ""
            c = re.sub(r'^(?:#{1,6}\s*|\*{2})?(?:Out of Scope|Off Topic)(?:\*{2})?[:\s]*\n*', '', c, flags=re.IGNORECASE).strip()

        if topic_name and not c.startswith("#") and not c.startswith(f"**{topic_name}"):
            if c.lower().startswith(topic_name.lower()):
                remainder = c[len(topic_name):].lstrip(" :\n-–")
                c = f"### {topic_name}\n\n{remainder}"
            else:
                c = f"### {topic_name}\n\n{c}"

        c = re.sub(r'\n{3,}', '\n\n', c).strip()
        section["content"] = c
        if c:
            full_content_parts.append(c)

    full_content = "\n\n".join(full_content_parts)

    response = {
        "type": "query",
        "content": full_content,
        "sections": sections,
        "chunks_used": [] if is_out_of_scope else chunks,
        "videos": [] if is_out_of_scope else videos[:10],
        "images": [] if is_out_of_scope else images[:5],
        "pdfs": [] if is_out_of_scope else pdfs[:5],
        "question_suggestions": suggestions,
        "metadata": {
            "short_topic": "marine" if is_out_of_scope else decision.get("short_topic", "marine"),
            "routing_reason": "off_topic" if is_out_of_scope else decision.get("reason", "query"),
            "out_of_scope": is_out_of_scope,
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