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

LAYER 1 — CORE MARITIME STANDARD CONTEXT (SOLAS / MARPOL / IMO / STCW):
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
  - ONLY use the 5-column safety checklist layout (`| Check | Ship | Terminal | Code | Remarks |`) for actual Ship/Shore Safety Checklists (SSSCL), Crude Oil Washing (COW) checklists, or safety verification checklists.
  - For other tables or lists (such as operational sequences, responsibility matrices, activity lists, equipment tables), you MUST use a normal markdown table matching the actual columns from the source document (e.g., `| Activity | Responsibility |`). Do NOT add `Ship`, `Terminal`, `Code` columns or checkboxes `[ ]` to these general tables.
  - In safety checklist tables, populate the columns exactly as follows:
    - The first column `Check` must contain only the description of the check/procedure item.
    - The second column `Ship` must contain a checkbox (`[ ]` or `[x]`) ONLY if a check/data is explicitly applicable or indicated for the Ship in the source text. If no check/data is present for the Ship, leave the Ship column completely empty/blank (do NOT put `[ ]`).
    - The third column `Terminal` must contain a checkbox (`[ ]` or `[x]`) ONLY if a check/data is explicitly applicable or indicated for the Terminal in the source text. If no check/data is present for the Terminal, leave the Terminal column completely empty/blank (do NOT put `[ ]`).
    - The fourth column `Code` MUST contain the verification code (like `R`, `A`, `P`) ONLY if it is explicitly specified in the source document. Do NOT fill the Code column with default values; leave it empty if no code is specified.
    - The fifth column `Remarks` must contain any remarks, notes, explanations, or conditions (e.g., "such as failure of IG system, increase in O2 content, or drop in pressure" must go in the Remarks column, not in the Check or Code columns). Leave it empty if there are no remarks.
    - Ensure that every row strictly aligns with this column order. Do NOT default to putting `[ ]` in the Ship or Terminal columns; leave them empty if no check/data is specified in the source text.
- Use ONLY facts from the Company Documents for this section. Never invent company procedures.

### 📘 2. Dolphin internal knowledge base
- Provide the comparative international maritime framework (SOLAS, MARPOL, STCW, ISM Code, or IMO Resolutions).
- Summarize the global regulatory baseline and industry best practices.

### 🔍 3. Comparison & AI Advisory Observations
- **Alignment:** Highlight where {company_name}'s procedures align with international standards.
- **💡 AI Advisory Observation(s):** 
  • Identify any safety controls, updated regulatory requirements, or industry recommendations that could enhance safety or operational clarity.
  • Clearly state the rationale and supporting regulatory/industry reference.
  • If company procedures are fully comprehensive and aligned, state that no gaps were identified.
- **Governance Notice:** End this section with the mandatory notice:
  *(AI Advisory Observation only — any procedure update must be reviewed by Company HSQE and processed through formal Management of Change [MoC]).*

RULES:
- If the Company Documents do not contain information addressing the question, output ONLY: NO_COMPANY_DATA
- If the document contains a safety verification checklist (like Ship/Shore Safety Checklist or COW checklist), you MUST format it as a 5-column table: `| Check | Ship | Terminal | Code | Remarks |`. Do NOT default to putting `[ ]` checkboxes in the Ship/Terminal columns; leave them completely empty/blank unless the check/data is explicitly specified for that column in the source text. For other lists, tables or sequences (like cargo operations, activity schedules, or responsibility grids), use normal markdown tables with columns matching the source document. Do NOT use bullet points or numbered lists.
- Maintain clear Markdown headings and clean spacing.
"""


def is_company_query(query: str, company_name: str) -> bool:
    import re
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

    # Check if the query is company-related
    query = state.get("standalone_query") or state.get("current_query", "")
    if not is_company_query(query, company_name):
        logger.info(f"Query '{query}' is not classified as company-related. Skipping company query node.")
        state["company_answer"] = None
        return state

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

    core_chunks = state.get("retrieval_chunks", [])
    core_context_text = "\n\n---\n\n".join(
        f"Topic: {c.get('topic_name', 'Maritime Standard')}\n{c.get('content', '')}"
        for c in core_chunks[:4]
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
                import re
                
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
                        rows_str.append(f"| {item_num}. {item_desc} | {ship_check} | {terminal_check} | R | |")
                    
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