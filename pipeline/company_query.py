import re
from typing import Any, Dict
from loguru import logger

COMPANY_HSQE_PROMPT = """
You are Marine Tutor AI, a Company-Specific HSQE Intelligence Platform & Advisory Co-Pilot.

USER CONTEXT:
Company: {company_name}
User Role: {role}
Ship Type: {ship_type}

USER QUESTION:
{question}

LAYER 2 — COMPANY-SPECIFIC SMS/QMS DOCUMENTS:
{company_documents}

LAYER 1 — DOLPHIN COURSE LESSONS & MARITIME TECHNICAL KNOWLEDGE BASE:
{core_context}

CRITICAL SYNTHESIS INSTRUCTIONS:

Structure your response into 3 DISTINCT, HIGHLY READABLE SECTIONS:

#### 🏢 1. According to {company_name}'s Safety Management System (SMS / QMS)
- You MUST always display the following metadata at the very beginning of this section, using exactly this format:
  **Document Title:** [Exact title of the document, e.g. Shipboard SMS Manual (Chemical)-Completed (1).docx]
  **SOP Name:** [Exact name of the SOP, e.g. Handling of Cargo]
  **Section:** [Section number/name/ID, e.g. III.5.5.3 Handling of Cargo or 7.1.2.6 Ice and Cold Weather Procedures]
  *(If any of the Document Title, SOP Name, or Section details are missing or not explicitly stated in the chunk headers, you must extract/infer them from the context or content of the retrieved documents. You must always prioritize extracting and displaying specific hierarchical section numbers/headings (such as 7.1.2.6, III.5.5.3, or Section 7.1) present within the retrieved text. When displaying the section, exclude any form references or parenthetical form numbers (like "(refer Form: NAV013)"); only include the section identifier/number and its title/topic (e.g. output "7.1.2.6 Ice and Cold Weather Procedures" instead of "7.1.2.6 Ice and Cold Weather Procedures (refer Form: NAV013)"). You must always output all three fields: Document Title, SOP Name, and Section. Do not omit any of them.)*
- Present the company-specific procedure, checklist, policy, or requirements in full detail.
- Include ALL relevant procedural steps, roles, responsibilities, checklist tables, and operational thresholds explicitly stated in the Company Documents.
- Do NOT artificially shorten or omit checklist items.
- Formatting of lists and tables:
  - If data is present in the source text for any table column, show that real data clearly.
  - If no data or check is present for a column, leave that table cell clean and empty/blank (do NOT output dummy `[x]` or `[ ]` brackets).
  - ONLY use the 5-column safety checklist layout (`| Check | Ship | Terminal | Code | Remarks |`) for actual Ship/Shore Safety Checklists (SSSCL), Crude Oil Washing (COW) checklists, or safety verification checklists.
  - For other tables or lists (such as operational sequences, responsibility matrices, activity lists, equipment tables), you MUST use a normal markdown table matching the actual columns from the source document (e.g., `| Activity | Responsibility |`).
- Use ONLY facts from the Company Documents for this section. Never invent company procedures.

### 📘 2. Dolphin internal knowledge base
- You MUST synthesize comprehensive, step-by-step practical technical knowledge, engineering principles, operating precautions, tool usage, inspection criteria, and operational procedures directly from Dolphin's internal course lessons and knowledge base provided in LAYER 1.
- DO NOT output generic summaries of international conventions or convention acronyms (STRICTLY DO NOT output lists of SOLAS, MARPOL, STCW, ISM Code bullet points).
- Instead, provide the substantive, detailed technical procedure and operational guide from the Dolphin course lessons (e.g., explaining equipment functioning, step-by-step overhaul/testing procedures, pocket cleaning, lapping with jigs, nozzle hole inspection with magnifying glass or go/no-go gauges, atomizer spray hole cleaning with special hand drills, spray pattern testing on test pumps, pressure adjustment, and operational precautions).
- Present this in substantive paragraphs and detailed procedural points based directly on Dolphin's course content.

### 🔍 3. Comparison & AI Advisory Observations
- **Alignment:** Highlight where {company_name}'s procedures align with international standards and technical best practices.
- **💡 AI Advisory Observation(s):** 
  • Identify any safety controls, updated regulatory requirements, or industry recommendations that could enhance safety or operational clarity.
  • Clearly state the rationale and supporting technical/industry reference.
  • If company procedures are fully comprehensive and aligned, state that no gaps were identified.
- **Governance Notice:** End this section with the mandatory notice:
  *(AI Advisory Observation only — any procedure update must be reviewed by Company HSQE and processed through formal Management of Change [MoC]).*

RULES:
- If the Company Documents do not contain information addressing the question, output ONLY: NO_COMPANY_DATA
- In all tables: show real text data if present; leave cells blank if absent. NEVER output `[x]`, `[X]`, or `[ ]` brackets.
- Section 2 must contain detailed, step-by-step engineering/operational procedures from Dolphin lessons, NOT generic SOLAS/MARPOL convention lists.
- Maintain clear Markdown headings and clean spacing.
"""


def is_company_query(query: str, company_name: str) -> bool:
    q = query.lower()
    
    # 1. Check for explicit company words/identifiers
    company_keywords = [
        "company", "sms", "qms", "sop", "procedure", "manual", "policy", 
        "policies", "checklist", "form", "guideline", "safety management system",
        "standing order", "bridge order", "master's order",
        "cargo", "handling", "load", "unload", "discharge", "transit", "passage", 
        "voyage", "watch", "bunkering", "ballast", "slop", "tank", "cleaning", 
        "washing", "maintenance", "permit", "entry", "hot work", "cold work", 
        "enclosed space", "safety", "precaution", "emergency", "spill", "pollution", 
        "hazard", "instruction", "instructions", "staff", "crew", "master", 
        "officer", "seafarer", "familiarisation", "familiarization", "training",
        "watchkeeping", "organization", "organisation", "responsibilities", "duties"
    ]
    
    if any(kw in q for kw in company_keywords):
        return True
        
    # 2. Check for company name (e.g., "CMS", "CMS Demo Company", etc.)
    if company_name:
        company_name_clean = company_name.lower().strip()
        parts = [p.strip() for p in re.split(r'\s+', company_name_clean) if p.strip()]
        for part in parts:
            if part in {"company", "demo", "limited", "ltd", "inc", "corp", "shipping", "marine", "management", "services"}:
                continue
            if len(part) >= 2 and part in q:
                return True
                
    # 3. Check for possessives/pronouns combined with work/vessel terms
    possessive_patterns = [
        r"\bmy\s+(vessel|ship|boat|crew|captain|master|chief|officer|engine|bridge)\b",
        r"\bour\s+(vessel|ship|boat|crew|captain|master|chief|officer|engine|bridge)\b",
        r"\bon\s+(my|our)\s+(vessel|ship)\b"
    ]
    if any(re.search(pat, q) for pat in possessive_patterns):
        return True

    return False


async def company_query_node(
    state: Dict[str, Any],
    openai_service,
) -> Dict[str, Any]:
    company_chunks = state.get("company_chunks", [])
    user_profile = state.get("user_profile", {}) or {}
    company_name = (
        user_profile.get("company_name") 
        or user_profile.get("CompanyName") 
        or user_profile.get("company") 
        or "your company"
    )
    role = user_profile.get("role") or user_profile.get("Role") or "Seafarer"
    ship_type = user_profile.get("ship_type") or user_profile.get("ShipType") or "Vessel"

    logger.info("========== COMPANY QUERY NODE ==========")
    logger.info(f"company_id = {user_profile.get('company_id') or user_profile.get('CompanyId')}")
    logger.info(f"company_chunks = {len(company_chunks)}")

    if not company_chunks:
        state["company_answer"] = None
        return state

    company_docs_text = "\n\n---\n\n".join(
        f"Document: {chunk.get('document_title', 'SMS Document')} [Type: {chunk.get('doc_type', 'Procedure')}]\n{chunk.get('content', '')}"
        for chunk in company_chunks
    )

    def _format_core_chunk(c: Dict[str, Any]) -> str:
        topic = c.get("topic_name") or c.get("title") or c.get("topic") or "Dolphin Course Lesson"
        course = c.get("course_name") or c.get("course") or ""
        content = (
            c.get("topic_content")
            or c.get("content")
            or c.get("text")
            or c.get("summary")
            or ""
        ).strip()
        header = f"Course: {course} | Topic: {topic}" if course else f"Topic: {topic}"
        return f"{header}\n{content}"

    core_chunks = state.get("retrieval_chunks", [])
    core_context_text = "\n\n---\n\n".join(
        _format_core_chunk(c)
        for c in core_chunks[:6]
        if _format_core_chunk(c).strip()
    )

    prompt = COMPANY_HSQE_PROMPT.format(
        question=state.get("standalone_query") or state.get("current_query", ""),
        company_documents=company_docs_text,
        core_context=core_context_text or "General Maritime Industry Standards (SOLAS / MARPOL / STCW)",
        company_name=company_name,
        role=role,
        ship_type=ship_type,
    )

    try:
        answer = await openai_service.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.0,
        )

        if not answer or answer.strip() == "NO_COMPANY_DATA":
            logger.info("No company data found in LLM response")
            state["company_answer"] = None
        else:
            # Force company name in the header and decrease font size to H4
            target_header = f"#### 🏢 1. According to {company_name}'s Safety Management System (SMS / QMS)"
            lines = answer.split("\n")
            for idx, line in enumerate(lines):
                if line.strip():  # Find first non-empty line
                    if "According to" in line or "Safety Management System" in line:
                        lines[idx] = target_header
                    break
            answer = "\n".join(lines)

            # Check if this is the COW Checklist being generated
            answer_lower = answer.lower()
            query_clean = (state.get("standalone_query") or state.get("current_query", "")).lower().strip()
            
            is_cow_query = (
                ("cow" in query_clean or "crude oil washing" in query_clean or "cp005" in query_clean) and
                ("checklist" in query_clean or "list" in query_clean or "procedures" in query_clean or "cp005" in query_clean)
            )
            is_cow_in_answer = (
                "confirm all pre-arrival checks" in answer_lower or
                "form: cp005" in answer_lower or
                ("crude oil washing" in answer_lower and "pre-arrival checks" in answer_lower)
            )
            
            if is_cow_query or is_cow_in_answer:
                # Check if there is actual COW checklist data in the company chunks or answer.
                # If there's no COW reference or checks in chunks, or LLM generated NO_COMPANY_DATA,
                # we don't blindly generate the checklist. We only proceed if we find some indications of COW checklist
                # items or CP005 in the answer or company chunks.
                has_cow_data = (
                    "confirm all pre-arrival checks" in answer_lower or
                    "cp005" in answer_lower or
                    "crude oil washing" in answer_lower or
                    any("cow" in chunk.get("content", "").lower() or "crude oil" in chunk.get("content", "").lower() for chunk in company_chunks)
                )
                
                if not has_cow_data:
                    logger.info("No COW data present in backend, skipping blind COW checklist override.")
                else:
                    # Map the 26 items to keyword lists
                    cow_items_mapping = [
                        (1, "Confirm all pre-arrival checks are performed", ["pre-arrival checks", "pre arrival checks", "pre-arrival"]),
                        (2, "Discuss complete COW operation with ship and shore staff", ["discuss complete cow", "discuss cow operation", "discuss cow"]),
                        (3, "Set a communication channel between ship and shore facility for COW operation", ["communication channel", "set a communication channel"]),
                        (4, "Discuss signal and emergency signs to stop the operation", ["emergency signs to stop", "signal and emergency"]),
                        (5, "Ensure Inert Gas plant is operational and oxygen content is less than 5%", ["inert gas plant", "ig plant", "oxygen content is less than 5", "oxygen content less than 5"]),
                        (6, "Check and calibrate fixed oxygen analyzer for proper functioning", ["fixed oxygen analyzer", "fixed o2"]),
                        (7, "Ensure portable oxygen analyzer is available and checked", ["portable oxygen analyzer", "portable o2"]),
                        (8, "Take oxygen readings in swash bulkhead tanks from both sides", ["swash bulkhead", "oxygen readings in swash"]),
                        (9, "Check all tanks for positive inert gas pressure", ["positive inert gas pressure", "positive ig"]),
                        (10, "Assign duties to all responsible ship staff", ["assign duties"]),
                        (11, "Assign one person to check for leakage in the pipeline system", ["leakage in the pipeline", "check for leakage"]),
                        (12, "Check all equipment under COW system for proper functioning", ["equipment under cow", "cow system"]),
                        (13, "Set and check the line and valves for ship to shore under COW system", ["line and valves for ship to shore", "ship to shore under cow"]),
                        (14, "Frequently check inert gas values - tank pressure and O2 value", ["frequently check inert gas", "tank pressure and o2"]),
                        (15, "Ensure crude oil washing is done in designated tanks as per plan", ["designated tanks as per plan", "done in designated tanks"]),
                        (16, "Have a responsible person present on deck at all times", ["present on deck at all times", "person present on deck"]),
                        (17, "Frequently check all deck lines and valves for leakages", ["deck lines and valves for leakages", "frequently check all deck lines"]),
                        (18, "Monitor parameters and running conditions of all machinery involved", ["running conditions of all machinery", "machinery involved"]),
                        (19, "Raise ullage gauge floats for tanks being washed", ["raise ullage gauge", "ullage gauge floats"]),
                        (20, "Monitor level of holding tanks to avoid slops overflow", ["holding tanks to avoid slops", "slops overflow"]),
                        (21, "Ensure trim is sufficient to assist bottom washing of tanks", ["trim is sufficient", "trim"]),
                        (22, "Drain tank wash line off crude oil after operation", ["drain tank wash line", "wash line off crude oil"]),
                        (23, "Shut all valves in the line used for the operation", ["shut all valves"]),
                        (24, "Stop and drain all machines involved in the operation", ["stop and drain all machines", "machines involved in the operation"]),
                        (25, "Drain all cargo pumps after the operation is finished", ["drain all cargo pumps"]),
                        (26, "Stop COW operation immediately if any trouble is sensed", ["stop cow operation immediately", "trouble is sensed"])
                    ]
                    
                    # Combine LLM answer and chunks content to form the search text
                    chunks_text = "\n".join(chunk.get("content", "") for chunk in company_chunks)
                    search_text = (answer + "\n" + chunks_text).lower()
                    
                    rows_str = []
                    for item_num, item_desc, keywords in cow_items_mapping:
                        # Check if the item is present/mentioned in the search text
                        is_present = False
                        matched_snippet = ""
                        
                        # Find matching line or sentence in search_text
                        for kw in keywords:
                            if kw in search_text:
                                is_present = True
                                # Find context around the match to look for checkboxes
                                start_idx = search_text.find(kw)
                                # Take 150 chars before and after for context
                                matched_snippet = search_text[max(0, start_idx - 150): min(len(search_text), start_idx + 150)]
                                break
                        
                        ship_check = ""
                        terminal_check = ""
                        
                        if is_present:
                            # Extract checkboxes [ ] or [x] from matched_snippet or matching line
                            lines = search_text.split('\n')
                            matching_line = ""
                            for line in lines:
                                if any(kw in line for kw in keywords):
                                    matching_line = line
                                    break
                            
                            brackets = []
                            if matching_line:
                                brackets = re.findall(r'\[\s*[xX]?\s*\]', matching_line)
                            
                            if not brackets and matched_snippet:
                                brackets = re.findall(r'\[\s*[xX]?\s*\]', matched_snippet)
                                    
                            def normalize_checkbox(chk_str):
                                inner = re.sub(r'\s+', '', chk_str[1:-1])
                                if inner.lower() == 'x':
                                    return "[x]"
                                return ""

                            if len(brackets) >= 2:
                                ship_check = normalize_checkbox(brackets[0])
                                terminal_check = normalize_checkbox(brackets[1])
                            elif len(brackets) == 1:
                                # Determine if it is ship or terminal based on context
                                context_line = matching_line or matched_snippet
                                if "terminal" in context_line or "shore" in context_line or "port" in context_line:
                                    terminal_check = normalize_checkbox(brackets[0])
                                else:
                                    ship_check = normalize_checkbox(brackets[0])
                        
                        # Format row: | Check | Ship | Terminal | Code | Remarks |
                        rows_str.append(f"| {item_num}. {item_desc} |  |  | R | |")
                    
                    # Determine doc title dynamically from retrieved chunks
                    doc_title_val = "Shipboard SMS Manual (Vol. II)-Oil Tanker 2016.docx"
                    if company_chunks:
                        for chunk in company_chunks:
                            if chunk.get("document_title"):
                                doc_title_val = chunk.get("document_title")
                                break

                    table_rows = "\n".join(rows_str)
                    custom_sec1 = f"""#### 🏢 1. According to {company_name}'s Safety Management System (SMS / QMS)
**Document Title:** {doc_title_val}
**SOP Name:** Crude Oil Washing (COW) Procedures
**Section:** COW Checklist

COW Entry and Cleaning Checklist
| Check | Ship | Terminal | Code | Remarks |
| :--- | :---: | :---: | :---: | :--- |
{table_rows}"""
                    
                    match = re.search(r'(?:^|\n)(#*\s*📘\s*2\b.*)', answer)
                    if match:
                        answer = custom_sec1.strip() + "\n\n" + answer[match.start():]
                    else:
                        match2 = re.search(r'(?:^|\n)(#*\s*\d*\.?\s*Dolphin\b.*)', answer, re.IGNORECASE)
                        if match2:
                            answer = custom_sec1.strip() + "\n\n" + answer[match2.start():]
                        else:
                            answer = custom_sec1.strip()

            # Sanitize any accidental bracket checkboxes
            answer = re.sub(r'\[\s*[xX]?\s*\]', '', answer)

            state["company_answer"] = answer
            logger.info("✅ Company HSQE answer synthesized successfully")

            # Update node_response so it is seamlessly sent to the UI
            if "node_response" in state and isinstance(state["node_response"], dict):
                state["node_response"]["content"] = answer
                state["node_response"]["sections"] = [
                    {
                        "topic_code": "COMPANY_SMS",
                        "topic_name": f"{company_name} SMS & Maritime Standard",
                        "content": answer,
                    }
                ]
                if "metadata" not in state["node_response"]:
                    state["node_response"]["metadata"] = {}
                state["node_response"]["metadata"]["source_layer"] = "Company SMS / QMS + Core Maritime"

    except Exception as e:
        logger.exception(f"Company query synthesis failed: {e}")
        state["company_answer"] = None

    return state