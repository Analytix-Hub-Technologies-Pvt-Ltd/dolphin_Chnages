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

- MARITIME STATUTORY, REGULATORY, & ACRONYM QUERIES (CRITICAL IN-SCOPE MANDATE):
  * Inquiries regarding maritime statutory legislation, maritime security, administrations, or conventions (e.g., MSA - Merchant Shipping Act / Maritime Safety Administration / Maritime Security Awareness, IMO conventions, SOLAS, MARPOL, MLC 2006, STCW, ISPS Code, Port State Control, MEPC amendments) are STRICTLY MARITIME IN-SCOPE.
  * You are STRICTLY PROHIBITED from claiming that legitimate maritime statutory acts, administrations, or regulations are outside the maritime curriculum.
  * Thoroughly synthesize the regulatory requirements, safety standards, security measures, and compliance frameworks from the COURSE CONTEXT.
  * NO KNOWLEDGE CUTOFF OR ROBOTIC AI APOLOGY (STRICT MANDATORY RULE):
    - NEVER state "as of my knowledge cutoff in October 2023", "I do not have real-time information", or generic AI limitation excuses.
    - When a user asks about prospective, recent, or future maritime regulatory years (e.g., 2024, 2025, 2026):
      → Directly synthesize the latest IMO / SOLAS / MARPOL amendments, decarbonization targets (EEXI, CII, GHG Strategy), SEEMP Part II updates, and upcoming conventions from the COURSE CONTEXT.
      → Instruct the seafarer to verify with the latest IMO circulars and Flag State marine notices for official implementation circulars.
  * REGULATORY OVERVIEW SECTION TITLE RULE:
    - If the user query specifically asks about a regulation, amendment, or year-specific mandate (e.g. "regulation on X effective Y", "changes in marine 2025"):
      → Section 1 must focus directly on the Regulatory Overview & Requirements of that mandate, integrating the specific timeline into the section title (e.g., "Overview of Upcoming Regulations on Gas Meters Effective January 2026" or "Overview of Changes in Marine Regulations for 2025"), rather than falling back to a generic operational equipment manual.

- ZERO HALLUCINATION & NO FALSE ASSOCIATIONS (CRITICAL MANDATORY RULE):
  * NEVER fabricate, stretch, or assume connections between everyday consumer tech (e.g., iPhone, Android, smartphones, consumer electronics, laptops, gaming) and shipboard internal equipment.
  * Specifically, if the user asks about an everyday gadget or consumer product (such as 'what is iphone?'), DO NOT answer with internal vessel communication systems, PA systems, or sound-powered phones! An iPhone is a consumer smartphone from Apple, NOT a shipboard internal phone system!
  * If the question is about non-marine technology, everyday gadgets, or general world trivia, you MUST return the OUT-OF-SCOPE response immediately, even if COURSE CONTEXT contains superficially matching words like 'phone' or 'communication'.

- OUT-OF-SCOPE NON-MARITIME QUESTIONS ONLY (MANDATORY):
  ONLY if the user's question is completely NON-MARITIME and has ZERO relation to ships, seafaring, navigation, marine engineering, or maritime regulations (such as smartphones/iPhone/Android, consumer electronics, computer programming/coding, movies/cinema, sports, recipes/cooking, politics, non-marine general trivia):
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
  → CRITICAL: NEVER return this out-of-scope refusal for maritime regulations, statutory acts (like MSA), ship machinery, or nautical procedures!

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
- ADAPTIVE HIERARCHICAL STRUCTURE (PROPORTIONAL TO TOPIC DEPTH):
  * For comprehensive, rich, or multi-faceted topics (e.g. international regulations, complex systems, multi-aspect operations):
    → Dynamically organize explanations into logical thematic subheadings using markdown headings (### Subheading Title) reflecting the natural facets in COURSE CONTEXT (e.g., key requirements, measurement methods, compliance timelines/pathways, operational impact, conclusion).
    → Use bullet points (- ) with bold lead-ins (- **Facet / Concept:** Details) and indented sub-bullets for classifications (e.g., consumer types, equipment groups).
    → Use numbered lists (1. 2. 3.) ONLY for strict chronological sequences or step-by-step procedures that must be executed in order. Do NOT compress multiple distinct themes into a single flat numbered list.
  * For concise or small topics (e.g., definitions, single-concept facts):
    → Keep the structure direct, clean, and proportional to the available content without inventing unnecessary subheadings or padding.
- Organize explanations into well-formed paragraphs separated by double newlines.
- Use bold (**term**) for important terminology, conventions, warnings, limits, or parameters.
- Never run multiple distinct titles and paragraphs together without headings and paragraph breaks.
- TOPIC-LEVEL QUESTIONS & OVERVIEW MANDATE:
  * When the user's question asks about a general equipment or machinery system (e.g., "ECDIS", "EGCS", "Boiler", "Inert Gas System", "Oily Water Separator", "Pilot Ladder"):
    → The FIRST section MUST be an Overview / Introduction to that system (e.g., "Overview of ECDIS" or "Overview of Exhaust Gas Cleaning Systems (EGCS)"), explaining what it is, its core purpose, operating principles, and importance.
  * When the user's question specifically asks about a statutory manual, plan, certificate, or document (e.g., "Onboard Monitoring Manual", "SEEMP", "SOPEP", "Garbage Management Plan"):
    → The response MUST focus directly on that specific manual, plan, or document (e.g., "Overview of Onboard Monitoring Manual (OMM)"), detailing its purpose, regulatory basis, required contents, and approval requirements, while identifying which system it governs.
- REGULATORY MANDATES & UPCOMING AMENDMENTS:
  * When the user's question asks about regulations, rules, amendments, or compliance effective on a specific date or year (e.g., "regulation on gas meters effective jan 2026", "amendments to SEEMP/DCS for 2026"):
    → Focus the response directly on the regulatory requirements, compliance deadlines, MARPOL/IMO resolutions, and instrumentation/reporting standards from COURSE CONTEXT.
    → Do NOT substitute or lead with a basic introductory description of unrelated safety gear (such as enclosed space portable gas detectors) when the question specifically asks for regulations and compliance effective in a given year.
    → Select the topic_code and topic_name corresponding to the regulatory compliance topic from COURSE CONTEXT.
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
    category = safe_get(state, "category", "") or decision.get("category", "")
    from services.maritime_acronyms import find_acronyms_in_query
    from services.off_topic_detector import is_marine_domain_query, has_strong_marine_signal
    is_marine = (
        is_marine_domain_query(query)
        or is_marine_domain_query(standalone_query)
        or bool(find_acronyms_in_query(query))
        or bool(find_acronyms_in_query(standalone_query))
        or has_strong_marine_signal(query)
        or has_strong_marine_signal(standalone_query)
    )
    if not is_marine:
        try:
            from services.dynamic_acronym_service import dynamic_acronym_service
            for t in (query + " " + standalone_query).upper().split():
                clean_t = re.sub(r'[^A-Z0-9]', '', t)
                if len(clean_t) >= 2 and dynamic_acronym_service.is_known_acronym(clean_t):
                    is_marine = True
                    break
        except Exception:
            pass
    if is_off_topic_query(query) or is_off_topic_query(standalone_query) or (category == "OFF_TOPIC" and not is_marine):
        logger.info(f"🚫 [QUERY_NODE] Off-topic query detected: '{standalone_query}' (query='{query}', cat='{category}')")
        from services.off_topic_detector import generate_dynamic_off_topic_response
        out_of_scope_text, dynamic_suggestions = await generate_dynamic_off_topic_response(
            standalone_query or query
        )
        stream_callback = safe_get(state, "stream_callback")
        if stream_callback:
            try:
                tokens = re.findall(r'\S+\s*|\n+', out_of_scope_text)
                for tok in tokens:
                    await stream_callback({"type": "content", "token": tok})
                state["_streamed_live"] = True
            except Exception as e:
                logger.warning(f"Failed streaming off-topic in query_node: {e}")

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
            "question_suggestions": dynamic_suggestions,
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
        from services.off_topic_detector import generate_dynamic_off_topic_response
        out_of_scope_text, dynamic_suggestions = await generate_dynamic_off_topic_response(
            standalone_query or query
        )
        stream_callback = safe_get(state, "stream_callback")
        if stream_callback:
            try:
                tokens = re.findall(r'\S+\s*|\n+', out_of_scope_text)
                for tok in tokens:
                    await stream_callback({"type": "content", "token": tok})
                state["_streamed_live"] = True
            except Exception as e:
                logger.warning(f"Failed streaming off-topic for empty chunks: {e}")

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
            "question_suggestions": dynamic_suggestions,
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
    # Enrich prompt with maritime acronym domain expansions if present
    acronym_notes = []
    try:
        from services.maritime_acronyms import find_acronyms_in_query, get_acronym_expansion
        from services.dynamic_acronym_service import dynamic_acronym_service
        found_acrs = find_acronyms_in_query(standalone_query or query)
        for acr in found_acrs:
            exps = get_acronym_expansion(acr) or dynamic_acronym_service.get_expansion_sync(acr)
            if exps:
                acronym_notes.append(f"{acr}: {', '.join(exps)}")
    except Exception as e:
        logger.debug(f"Acronym context extraction error: {e}")

    effective_query_for_prompt = standalone_query or query
    if acronym_notes:
        effective_query_for_prompt += f"\n[Maritime Acronym Context: {'; '.join(acronym_notes)}]"

    prompt = QUERY_PROMPT.format(
        user_query=effective_query_for_prompt,
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

        state["_streamed_live"] = streamed_live
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
                            get_strict_acronym_expansions,
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
                                for exp in get_strict_acronym_expansions(acr):
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

    # Multi-chapter cross-reference links (extract genuine, non-redundant course subtopics)
    distinct_course_chapters = []
    if not is_out_of_scope and chunks:
        from services.maritime_acronyms import find_acronyms_in_query, get_strict_acronym_expansions
        acrs = find_acronyms_in_query(query)
        base_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', query.lower()))
        for acr in acrs:
            base_words.add(acr.lower())
            for exp in get_strict_acronym_expansions(acr):
                base_words.update(re.findall(r'\b[a-zA-Z]{3,}\b', exp.lower()))

        noise_words = {
            "what", "is", "are", "introduction", "intro", "overview", "about",
            "definition", "general", "basic", "basics", "the", "and", "for",
            "with", "know", "your", "system", "systems"
        }

        intro_prefixes = re.compile(
            r'^(what is|introduction to|overview of|about|definition of|know your|general principles of)\b',
            re.IGNORECASE
        )
        code_pattern = re.compile(r'^[A-Z0-9]{3,8}-[\d]{3,8}', re.IGNORECASE)

        primary_topic_name = str(chunks[0].get("topic_name") or chunks[0].get("title") or "").strip()
        primary_clean = re.sub(r'^\s*[\d\.\-\s]+', '', primary_topic_name).strip()
        primary_norm = re.sub(r'[^\w\s]', '', primary_clean.lower()).strip()
        seen_topics = {primary_norm}

        def is_valid_subtopic(tname):
            clean_t = re.sub(r'^\s*[\d\.\-\s]+', '', tname).strip()
            if len(clean_t) < 5 or code_pattern.search(clean_t):
                return False, ""
            if intro_prefixes.search(clean_t):
                return False, ""

            t_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', clean_t.lower()))
            distinct_words = t_words - base_words - noise_words
            if not distinct_words:
                return False, ""

            norm = re.sub(r'[^\w\s]', '', clean_t.lower()).strip()
            if norm in seen_topics:
                return False, ""

            return True, clean_t

        # 1. Evaluate from chunks[1:]
        for chk in chunks[1:]:
            tname = str(chk.get("topic_name") or chk.get("title") or "").strip()
            valid, clean_t = is_valid_subtopic(tname)
            if valid:
                norm = re.sub(r'[^\w\s]', '', clean_t.lower()).strip()
                seen_topics.add(norm)
                distinct_course_chapters.append(clean_t)
                if len(distinct_course_chapters) >= 4:
                    break

        # 2. If fewer than 3 distinct subtopics found, pull genuine subtopics from vector_store / FAISS metadata
        if len(distinct_course_chapters) < 3 and vector_store and hasattr(vector_store, "store"):
            raw_meta = getattr(vector_store.store, "id_to_metadata", []) or []
            search_terms = [query.lower()]
            for acr in acrs:
                search_terms.append(acr.lower())
                for exp in get_strict_acronym_expansions(acr):
                    if len(exp) >= 4:
                        search_terms.append(exp.lower())

            for m in raw_meta:
                tname = m.get("topic_name", "").strip()
                tl = tname.lower()
                if not any(st in tl for st in search_terms):
                    continue
                valid, clean_t = is_valid_subtopic(tname)
                if valid:
                    norm = re.sub(r'[^\w\s]', '', clean_t.lower()).strip()
                    seen_topics.add(norm)
                    distinct_course_chapters.append(clean_t)
                    if len(distinct_course_chapters) >= 4:
                        break

    if distinct_course_chapters:
        import urllib.parse
        for dcc in distinct_course_chapters:
            if dcc not in suggestions:
                suggestions.append(dcc)

        target_name = ""
        acrs = find_acronyms_in_query(query)
        if acrs:
            target_name = acrs[0]
        elif len(query.split()) <= 4:
            target_name = query.strip()
        elif primary_clean and len(primary_clean) <= 30:
            target_name = primary_clean

        if target_name:
            header_text = f"**Which aspect of {target_name} would you like to explore?**"
        else:
            header_text = "**Which aspect would you like to explore?**"

        links_md = "\n".join([f"- **[{ch}](#ask:{urllib.parse.quote(ch)})**" for ch in distinct_course_chapters])
        chapter_block = f"{header_text}\n{links_md}"
        if chapter_block not in full_content:
            full_content = (full_content.rstrip() + "\n\n" + chapter_block).strip()
        if sections and isinstance(sections[-1], dict) and "content" in sections[-1]:
            if chapter_block not in sections[-1]["content"]:
                sections[-1]["content"] = (sections[-1]["content"].rstrip() + "\n\n" + chapter_block).strip()

        # Emit over stream_callback so live SSE stream displays the clickable subtopics
        stream_cb = safe_get(state, "stream_callback")
        if stream_cb and safe_get(state, "_streamed_live", False):
            try:
                await stream_cb({"type": "content", "token": "\n\n" + chapter_block})
            except Exception as e:
                logger.warning(f"Failed to stream subtopics block: {e}")

    typo_prompt = safe_get(state, "typo_prompt") or safe_get(state, "typo_banner")
    if typo_prompt:
        if typo_prompt.strip() not in full_content:
            full_content = (full_content.rstrip() + "\n\n" + typo_prompt.strip()).strip()
        if sections and isinstance(sections[-1], dict) and "content" in sections[-1]:
            if typo_prompt.strip() not in sections[-1]["content"]:
                sections[-1]["content"] = (sections[-1]["content"].rstrip() + "\n\n" + typo_prompt.strip()).strip()
        stream_cb = safe_get(state, "stream_callback")
        if stream_cb and safe_get(state, "_streamed_live", False):
            try:
                await stream_cb({"type": "content", "token": "\n\n" + typo_prompt.strip()})
            except Exception as e:
                logger.warning(f"Failed to stream typo prompt: {e}")

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