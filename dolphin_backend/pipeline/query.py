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

0. BALANCED & COURTEOUS COURSE GROUNDING (TOP PRIORITY):
- When the CURRENT USER QUESTION specifically asks about a named course (e.g., "In course MSSV-2217...", "In course MSSV-2213...", "According to course X..."):
  * Look at the content belonging to that specific course in COURSE CONTEXT.
  * If the specific technical topic, protocol, or parameters asked are NOT found in that course's materials in COURSE CONTEXT:
    - Structure your response educationally and politely in two clear parts:
      1. General Topic Overview: Provide a concise, high-level educational explanation of the general subject in standard maritime practice (1-2 clear, informative paragraphs explaining the concept).
      2. Course Scope Notice: Conclude with a clear, polite notice: "Please note that the specific parameters and detailed procedures for this topic are not available in the curriculum of course [Course Name/Code]."
    - STRICT RULE: Do not invent or attribute specific numbers, limits, or proprietary procedures to that course.
    - NO MEDIA: Do NOT recommend, reference, or attach any diagrams, images, or videos when the topic is not covered in the course.
  * If the topic IS present in that course's materials in COURSE CONTEXT:
    - Answer fully, richly, and authoritatively using the course materials as instructed in Section 1.

1. RESPONSE DEPTH BY QUERY TYPE:

- BROAD OVERVIEW & ACRONYM INQUIRIES (e.g., single acronyms, broad topic titles, or general introductory definitions like "ECDIS", "What is ECDIS?", "Electronic Chart Display and Information System", "EGCS", "Exhaust Gas Cleaning Systems", "PSC", "What is PSC?", "OMM", "SOLAS", "BWMS", "OWS"):
  * Provide an in-depth, rich, and comprehensive foundational explanation drawing from all available details across the COURSE CONTEXT.
  * Do NOT artificially compress, truncate, or summarize into just a few brief bullet points.
  * Structure the explanation thoroughly into rich thematic sections using clear markdown headings (###):
    - Fundamental Definition & Operating Principle: Explain what the system, regulation, or technology is and its underlying working principles in clear, fluid prose. STRICT RULE: DO NOT output robotic textbook labels or headings such as "Core Definition & Principle:" or "Definition & Principle:". Simply state the explanation directly and fluidly.
    - System Architectures & Classifications: Detail the main types, variants, or designs (e.g., for EGCS: open-loop, closed-loop, and hybrid scrubbers; for ECDIS: vector ENCs vs raster RNCs; for OWS: gravity separation, coalescers, filtration). Explain how each variant operates.
    - Key Components & Operational Workflow: Detail the primary components, sensors, and functional flow from preparation to discharge/operation.
    - Statutory Compliance & International Regulations: Detail applicable IMO conventions, MARPOL/SOLAS regulations, approval schemes (e.g., Scheme A and Scheme B), documentation (e.g., EGC Record Book, logbooks), and flag/port state survey requirements.
  * Synthesize both the operational "How" and the underlying "Why" from the COURSE CONTEXT to provide deep educational value.

- SPECIFIC TECHNICAL INQUIRIES & DETAILED TOPICS (e.g., specific procedures, calibration intervals, display modes, sensor integration, emergency actions, troubleshooting, specific convention rules):
  * Provide a comprehensive, in-depth, and elaborate explanation drawing from all available details in the COURSE CONTEXT.
  * Do NOT artificially compress, truncate, or summarize into just a few brief bullet points if rich content exists. Expand fully on:
    - In-depth working principles, architectural descriptions, and technical specifications.
    - Comprehensive step-by-step operational procedures (preparation, execution, monitoring, post-checks).
    - Operating parameters, thresholds, limits, pressures, temperatures, and alarm setpoints.
    - Safety precautions, risk mitigations, hazard controls, and required Personal Protective Equipment (PPE).
    - Applicable conventions, failure modes, alarms, troubleshooting steps, and contingency plans.
    - Maintenance routines, testing protocols, inspections, and documentation/logbook requirements.
  * Explain both the operational "How" and the underlying "Why" to provide deep educational value.

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
  * NEVER claim that legitimate general maritime, safety, navigation, engineering, or vessel operation topics fall outside the marine training curriculum (unless the query asks about a specific named course whose curriculum does not cover that topic, as governed by Rule 0).

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

- SPECIFIC COURSE INQUIRIES & BALANCED COURSE GROUNDING:
  * When the user's question specifically names, inquires about, or targets a particular course (e.g., 'In course MSSV-2213...', 'In course MSSV-2217...', 'According to course X...'):
    - If the requested topic, protocol, procedure, or parameter is NOT present in that specific course's materials in COURSE CONTEXT:
      1. Provide a concise, high-level educational explanation of the general subject in standard maritime practice (1-2 clear, informative paragraphs explaining the concept).
      2. Conclude with a clear, polite notice: "Please note that the specific parameters and detailed procedures for this topic are not available in the curriculum of course [Course Name/Code]."
      3. Never invent or attribute specific numbers, limits, or proprietary procedures to that course.
      4. NO MEDIA: Do NOT recommend, reference, or attach any diagrams, images, or videos when the topic is not covered in the course.
    - If the requested topic IS present in that course's materials in COURSE CONTEXT:
      * Provide the full, rich, detailed, role-adapted explanation as instructed in Section 1.

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
- TOPIC OVERVIEW vs SPECIFIC QUESTION MANDATE:
  * SCENARIO 1: TOPIC OVERVIEWS & DEFINITIONS (STANDALONE ABBREVIATIONS, FULL NAMES, OR "WHAT IS" QUESTIONS):
    → When the user asks ONLY an abbreviation/acronym (e.g., "ECDIS", "EGCS", "OMM", "SEEMP", "OWS", "EEBD"), OR the full technical name / expansion (e.g., "Electronic Chart Display and Information System", "Exhaust Gas Cleaning Systems", "Onboard Monitoring Manual"), OR a broad introductory question (e.g., "What is ECDIS?", "Explain EGCS", "Overview of OMM"):
      - The FIRST section MUST be an Overview / Introduction to that system or statutory document (e.g., "Overview of ECDIS", "Overview of Exhaust Gas Cleaning Systems (EGCS)", "Overview of Onboard Monitoring Manual (OMM)"), thoroughly explaining its definition, core purpose, operating principles, and maritime importance.
  * SCENARIO 2: SPECIFIC QUESTIONS / SUB-ASPECTS / PROCEDURES / PARAMETERS (DO NOT SHOW GENERIC OVERVIEW):
    → When the user asks a specific question about a component, procedure, parameter, alarm, limit, or regulatory requirement within a topic (e.g., "What is the safety depth contour in ECDIS?", "How to calibrate sensors in OMM?", "What is the pH limit for washwater discharge?", "How to test steering gear alarms?", "What are Scheme A approval requirements?"):
      - Do NOT start with or include a generic "Overview of [Parent System]" or basic introductory definition of the equipment.
      - Directly anchor the response on the specific question asked.
      - Title the first section directly with the specific concept or procedure (e.g., "### Safety Depth Contour in ECDIS" or "### Washwater Discharge pH Limits").
      - Answer the question immediately, thoroughly, and comprehensively using the specific details from the retrieved COURSE CONTEXT.
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
# SUBTOPIC FORMATTERS (STRICTLY NO SYMBOLS / EMOJIS)
# =============================
def clean_subtopic_target_name(target_name: str, query: str = "") -> str:
    """
    Sanitize and format topic name for exploration header.
    Removes leading/trailing bullets (•, -, *), colons, numbers, newlines, and normalizes acronyms.
    E.g. '• Egcs:' -> 'EGCS', 'Overview of EGCS' -> 'EGCS'
    """
    raw = (target_name or "").strip()
    if not raw and query:
        from services.maritime_acronyms import find_acronyms_in_query
        acrs = find_acronyms_in_query(query)
        if acrs:
            return acrs[0].upper()

    if not raw:
        return ""

    # Replace newlines/tabs with space
    t = re.sub(r'[\r\n\t]+', ' ', raw)
    # Remove markdown formatting characters
    t = re.sub(r'[*_`#]', '', t)
    # Strip leading bullets (unicode bullets •, ◦, ‣, ⁃), numbers, dashes, colons
    t = re.sub(r'^[\s\u2022\u2023\u25cf\u25cb\u25e6\-\.\d:;,]+', '', t)
    # Strip trailing colons, punctuation, bullets
    t = re.sub(r'[\s\u2022\u2023\u25cf\u25cb\u25e6\-\.\d:;,?]+$', '', t)
    # Strip common prefixes
    t = re.sub(r'^(?:what\s+is|overview\s+of|introduction\s+to|about|explain)\s+', '', t, flags=re.IGNORECASE).strip()

    if not t:
        return ""

    from services.maritime_acronyms import is_known_maritime_acronym, find_acronyms_in_query
    if is_known_maritime_acronym(t.upper()):
        return t.upper()

    # If the topic contains an acronym in parentheses, prefer it for a crisp, catchy title (e.g. (EGCS) -> EGCS)
    m_paren = re.search(r'\(([A-Za-z0-9]{2,8})\)', raw)
    if m_paren and is_known_maritime_acronym(m_paren.group(1).upper()):
        return m_paren.group(1).upper()

    acrs = find_acronyms_in_query(raw)
    if acrs:
        return acrs[0].upper()

    # Acronym normalization within words (e.g. 'Egcs' -> 'EGCS', '(egcs)' -> '(EGCS)')
    words = t.split()
    fixed_words = []
    for w in words:
        clean_w = re.sub(r'[^\w]', '', w)
        if is_known_maritime_acronym(clean_w.upper()):
            fixed_words.append(w.replace(clean_w, clean_w.upper()))
        else:
            fixed_words.append(w)

    clean_res = " ".join(fixed_words).strip()
    if len(clean_res) > 35:
        return clean_res[:32].rsplit(' ', 1)[0]

    return clean_res


def generate_subtopic_header(target_name: str, query: str = "") -> str:
    """
    Generate dynamic, catchy exploration header tailored to the topic and inquiry.
    STRICT CONSTRAINT: Pure text only. Absolutely NO emojis, arrows, or unicode symbols.
    Format: **Which aspect of {Topic} would you like to explore?**
    """
    t_clean = clean_subtopic_target_name(target_name, query)
    if t_clean:
        return f"**Which aspect of {t_clean} would you like to explore?**"
    return "**Which aspect would you like to explore?**"



def generate_subtopic_metadata(title: str, raw_content: str = "", parent_topic: str = "") -> dict:
    """
    Synthesize an easy-to-read, 3 to 4 line substantive explanation for a subtopic.
    STRICT CONSTRAINTS:
    - Pure text only. Absolutely NO emojis, arrows, or unicode symbols.
    - DO NOT include 'Description:' or 'Question:' prefixes.
    - Thoroughly clean out database artifacts (Topic Name:, Topic Content:, etc.).
    """
    clean_title = re.sub(r'^\s*[\d\.\-\s]+', '', title).strip()

    # 1. Thoroughly clean raw_content of all database artifacts
    text = raw_content or ""
    text = re.sub(r'Topic\s*Name\s*:\s*[^\n\r]+', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'Topic\s*Code\s*:\s*[^\n\r]+', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'Topic\s*Content\s*:\s*', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'Learning\s*objectives?\s*:?\s*(?:On\s+completion\s+and\s+understanding[^\.\:\n]+)?', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'Specific\s*Learning\s*Objectives?\s*:?', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'Introduction\s*:?\s*(?:This\s+section\s+provides[^\.\:\n]+)?', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'#{1,6}\s*[^\n\r]+', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()

    while text.lower().startswith(clean_title.lower()):
        text = text[len(clean_title):].strip()
        text = text.lstrip(" -–:.")

    t_lower = clean_title.lower()

    # Domain-aware 3-4 line explanations (NO 'Description:', NO 'Question:', NO symbols)
    if "comparison of ecdis" in t_lower or ("ecdis" in t_lower and "paper" in t_lower):
        explanation = (
            "Compares electronic chart display systems against traditional paper charts across chart selection, updating procedures, and voyage planning workflows. "
            "It details how electronic charts eliminate manual catalogue searching while highlighting required backup arrangements under SOLAS carriage regulations. "
            "This helps officers understand when paperless navigation is legally permissible and how to maintain statutory compliance during bridge watches."
        )
    elif "difference between ecs" in t_lower or ("ecs" in t_lower and "ecdis" in t_lower):
        explanation = (
            "Explains the critical legal and operational distinctions between an Electronic Chart System (ECS) and a type-approved ECDIS. "
            "While both display digital navigational data, only an IMO-compliant ECDIS with official ENCs meets statutory SOLAS chart carriage requirements. "
            "This guides navigators on equipment limitations, situational awareness, and when paper chart backups remain mandatory."
        )
    elif "safety of navigation" in t_lower or ("safety" in t_lower and "navigation" in t_lower):
        explanation = (
            "Details operational bridge procedures, safety contour configurations, and anti-grounding alarms required to maintain navigational safety. "
            "It covers watchkeeping cross-checks between visual bearings, radar overlays, and electronic charts to avoid over-reliance on automated systems. "
            "Following these principles ensures safe passage execution and compliance with COLREGs and international bridge standards."
        )
    elif any(k in t_lower for k in ["audit", "inspection", "inspector"]):
        explanation = (
            f"Focuses on inspection walkthroughs, audit preparations, and compliance verification for {clean_title}. "
            f"It details statutory certificates, safety equipment checks, and crew operational competencies verified during official audits. "
            f"Following these procedures ensures the vessel rectifies potential non-conformities early and avoids detention or operational delays."
        )
    elif any(k in t_lower for k in ["mou", "memorand"]):
        explanation = (
            "Covers regional agreements like Paris MoU and Tokyo MoU coordinating harmonized ship inspection standards worldwide. "
            "It explains how regional authorities calculate ship risk profiles, targeting factors, and inspection priority bands. "
            "Officers learn how compliance history influences inspection frequency and how to prepare the vessel for regional scrutiny."
        )
    elif any(k in t_lower for k in ["verification", "certificate", "certification", "statutory"]):
        explanation = (
            f"Details statutory certificates, logbook entries, and crew operational competencies verified during {clean_title}. "
            f"It highlights mandatory documentation required under SOLAS, MARPOL, and STCW conventions during flag and port state controls. "
            f"This clarifies valid certificate validity periods, survey endorsements, and onboard record-keeping procedures."
        )
    elif "scheme a" in t_lower:
        explanation = (
            "Covers Scheme A certification, certified emission limits, and manufacturer documentation approval under MARPOL Annex VI regulations. "
            "It explains how continuous parameter monitoring demonstrates compliance without continuous gas analyzer dependency. "
            "Chief engineers can verify parameter check routines and ensure exhaust gas cleaning record books are properly maintained."
        )
    elif "scheme b" in t_lower:
        explanation = (
            "Covers Scheme B continuous emission monitoring (CEMS), daily parameter logging, and sensor validation procedures. "
            "It details continuous measurement of SO2 and CO2 ratios, data recording intervals, and washwater discharge limits. "
            "Crew members learn how to demonstrate compliance using continuous monitoring records during port and flag state inspections."
        )
    elif any(k in t_lower for k in ["calibration", "sensor", "span", "zero"]):
        explanation = (
            f"Outlines zero and span calibration gas procedures, sensor limits, and maintenance intervals for {clean_title}. "
            f"It defines allowable drift tolerances, calibration gas bottle certification requirements, and routine testing sequences. "
            f"Technical personnel learn how to execute calibration checks safely and ensure continuous analyzer accuracy onboard."
        )
    elif any(k in t_lower for k in ["alarm", "limit", "setpoint", "threshold"]):
        explanation = (
            f"Defines operational setpoints, threshold limits, and emergency alarm trigger conditions for {clean_title}. "
            f"It explains automated safety cut-offs, sensor failure warnings, and corrective actions required by watchkeeping personnel. "
            f"Operators learn how to respond swiftly to alarm conditions and maintain safe, uninterrupted system performance."
        )
    elif any(k in t_lower for k in ["troubleshoot", "maintenance", "overhaul", "repair"]):
        explanation = (
            f"Provides step-by-step troubleshooting routines, periodic maintenance checks, and safety precautions for {clean_title}. "
            f"It details common fault indicators, diagnostic procedures, and required personal protective equipment before opening machinery. "
            f"Engineers can reference this material to resolve technical issues promptly and avoid machinery breakdowns at sea."
        )
    elif any(k in t_lower for k in ["checklist", "check list", "procedure", "pre-departure"]):
        explanation = (
            f"Outlines mandatory operational verifications, pre-departure checks, and safety controls for {clean_title}. "
            f"It ensures that all critical valves, interlocks, and emergency controls are correctly aligned before initiating operations. "
            f"Adhering to these verifications minimizes human error and guarantees adherence to safety management system guidelines."
        )
    elif any(k in t_lower for k in ["enclosed space", "entry permit"]):
        explanation = (
            "Details atmospheric testing, ventilation standards, and rescue preparedness required before entering enclosed spaces. "
            "It outlines permissible oxygen levels, flammable vapor thresholds, and multi-gas detector testing protocols. "
            "Crew members understand permit-to-work authorizations, standby duties, and emergency extraction procedures."
        )
    elif any(k in t_lower for k in ["hot work"]):
        explanation = (
            "Details fire watch requirements, adjacent compartment checks, and gas monitoring during hot work operations. "
            "It covers removal of combustible materials, boundary cooling preparations, and firefighting equipment readiness. "
            "This ensures full adherence to safety management system protocols and eliminates onboard fire hazards."
        )
    elif any(k in t_lower for k in ["bunker", "fuel oil", "marpol annex vi"]):
        explanation = (
            f"Covers bunker delivery notes, statutory sulfur limits, and representative fuel sampling procedures under {clean_title}. "
            f"It outlines sampling bottle seal verifications, bunker manifold monitoring, and record retention periods for official verification. "
            f"This ensures the engineering team maintains full compliance and documentation during fuel receiving operations."
        )
    elif any(k in t_lower for k in ["bilge", "separator", "ows", "15 ppm"]):
        explanation = (
            f"Outlines oily water separator operations, 15 ppm bilge alarm verifications, and mandatory Oil Record Book documentation for {clean_title}. "
            f"It covers automatic stopping device testing, filter maintenance, and strict overboard discharge restrictions under MARPOL Annex I. "
            f"Engineering officers learn how to verify system readiness and prevent accidental environmental non-compliance."
        )
    else:
        sentences = [
            s.strip() for s in re.split(r'[.!?]\s+', text)
            if len(s.strip()) > 35 and not s.isupper() and not any(k in s.lower() for k in [
                "learning objective", "click here", "figure ", "table ", "no activity", "selection of charts",
                "topic name", "topic content", "topic code"
            ])
        ]
        if len(sentences) >= 2:
            combined = " ".join(sentences[:3]).strip()
            if len(combined) > 360:
                combined = combined[:357].rsplit(" ", 1)[0] + "..."
            explanation = (
                f"{combined.rstrip('.')}."
                f" This section outlines key regulatory guidelines, practical precautions, and step-by-step procedures to maintain operational safety and compliance onboard."
            )
        elif sentences:
            s_first = sentences[0].rstrip('.')
            explanation = (
                f"{s_first}. "
                f"Provides standard operating procedures, technical precautions, and statutory background for {clean_title}. "
                f"Officers and crew can reference this guidance to understand daily responsibilities, verify equipment readiness, and ensure full compliance with international maritime conventions."
            )
        else:
            explanation = (
                f"Provides comprehensive technical guidance and operational procedures for {clean_title}. "
                f"Covers statutory standards, equipment checks, and safety precautions required under international maritime regulations. "
                f"Personnel can review this section to understand practical implementation steps and verify onboard operational readiness."
            )

    return {
        "title": clean_title,
        "explanation": explanation
    }


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
        from services.maritime_acronyms import get_strict_acronym_expansions
        q_expansions = [exp.upper() for exp in get_strict_acronym_expansions(q)]
        def _match_chunk(c):
            haystack = (str(c.get("content") or "") + " " + str(c.get("topic_content") or "") + " " + str(c.get("topic_name") or "")).upper()
            return q in haystack or any(exp in haystack for exp in q_expansions)
        return [c for c in chunks if _match_chunk(c)] or chunks

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
        for s in sections:
            if isinstance(s, dict) and "content" in s and isinstance(s["content"], str):
                s["content"] = re.sub(
                    r'(?im)^(?:\s*[-*#]+\s*)?(?:\*\*)?Core\s+Definition\s*(?:&|and)\s*Principle:?(?:\*\*)?:?\s*\n*',
                    '',
                    s["content"]
                )
                s["content"] = re.sub(
                    r'(?i)(?:\*\*)?Core\s+Definition\s*(?:&|and)\s*Principle:?(?:\*\*)?:?\s*',
                    '',
                    s["content"]
                ).strip()

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

        # Strip robotic "Core Definition & Principle" / "Core Definition and Principle" labels
        c = re.sub(
            r'(?im)^(?:\s*[-*#]+\s*)?(?:\*\*)?Core\s+Definition\s*(?:&|and)\s*Principle:?(?:\*\*)?:?\s*\n*',
            '',
            c
        )
        c = re.sub(
            r'(?i)(?:\*\*)?Core\s+Definition\s*(?:&|and)\s*Principle:?(?:\*\*)?:?\s*',
            '',
            c
        ).strip()

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
            raw_c = str(chk.get("content") or chk.get("topic_content") or "").strip()
            valid, clean_t = is_valid_subtopic(tname)
            if valid:
                norm = re.sub(r'[^\w\s]', '', clean_t.lower()).strip()
                seen_topics.add(norm)
                distinct_course_chapters.append((clean_t, raw_c))
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
                raw_c = str(m.get("content") or m.get("topic_content") or "").strip()
                tl = tname.lower()
                def _matches_term(term, text):
                    if len(term) <= 4:
                        return bool(re.search(rf'\b{re.escape(term)}\b', text))
                    return term in text
                if not any(_matches_term(st, tl) for st in search_terms):
                    continue
                valid, clean_t = is_valid_subtopic(tname)
                if valid:
                    norm = re.sub(r'[^\w\s]', '', clean_t.lower()).strip()
                    seen_topics.add(norm)
                    distinct_course_chapters.append((clean_t, raw_c))
                    if len(distinct_course_chapters) >= 4:
                        break

    if distinct_course_chapters:
        import urllib.parse
        target_name = ""
        acrs = find_acronyms_in_query(query)
        if acrs:
            target_name = acrs[0]
        else:
            primary_topic_name = str(chunks[0].get("topic_name") or chunks[0].get("title") or "").strip()
            topic_acrs = find_acronyms_in_query(primary_topic_name)
            if topic_acrs:
                target_name = topic_acrs[0]
            elif primary_clean and len(primary_clean) <= 35:
                target_name = primary_clean
            elif len(query.split()) <= 4:
                target_name = query.strip()

        header_text = generate_subtopic_header(target_name, query)

        formatted_items = []
        for clean_t, raw_c in distinct_course_chapters:
            meta = generate_subtopic_metadata(clean_t, raw_c, parent_topic=target_name)
            formatted_items.append(meta)
            if meta["title"] not in suggestions:
                suggestions.append(meta["title"])

        # Clean markdown list with 3-4 line explanation - strictly zero emojis, arrows, or unicode symbols (NO 'Description:', NO 'Question:')
        list_lines = []
        for item in formatted_items:
            encoded_title = urllib.parse.quote(item["title"])
            list_lines.append(f"- **[{item['title']}](#ask:{encoded_title})**\n  {item['explanation']}")

        chapter_block = f"{header_text}\n\n" + "\n\n".join(list_lines)
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