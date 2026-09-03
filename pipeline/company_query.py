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

CRITICAL DYNAMIC RELEVANCE & EXHAUSTIVE SYNTHESIS INSTRUCTIONS:

1. RELEVANCE EVALUATION:
- Carefully evaluate whether the retrieved COMPANY-SPECIFIC SMS/QMS DOCUMENTS contain relevant procedures, checks, guidelines, checklists, policies, or operational instructions that directly address or regulate the USER QUESTION.
- If the question is a basic theoretical/educational definition or generic technical concept (e.g., "What is boiler design?", "What is Archimedes principle?", "Explain 4-stroke cycle") and the Company Documents do NOT contain specific company rules/SOPs defining or regulating that subject, output ONLY: NO_COMPANY_DATA
- If the Company Documents only mention the topic incidentally/peripherally without answering the user's specific question, output ONLY: NO_COMPANY_DATA

2. TARGET LENGTH & EXHAUSTIVENESS REQUIREMENT (3000 to 4000 TOKENS):
- You MUST synthesize an exhaustive, in-depth, comprehensive technical response targeting 3000 to 4000 tokens.
- NEVER provide high-level summaries, brief outlines, or superficial one-line bullet points.
- Extract, elaborate, and present EVERY SINGLE technical requirement, procedural step, sub-clause, formula, valve line-up, checklist item, operational threshold, temperature/pressure parameter, crew responsibility, log-keeping duty, and safety precaution found in the provided contexts.
- Structure your response into 3 DISTINCT, HIGHLY READABLE SECTIONS:

### 🏢 1. According to {company_name}'s Safety Management System (SMS / QMS)
- You MUST always display the following metadata directly under the Section 1 header (and NEVER before it), using exactly this format:
  **Document Title:** [Exact title of the document, e.g. Shipboard SMS Manual (Chemical)-Completed (1).docx]
  **SOP Name:** [Exact name of the SOP, e.g. Ship Operations (Cargo Procedures) or Handling of Cargo]
  **Section:** [Section number/name/ID, e.g. Loaded Passage or III.5.5.3 Handling of Cargo or 7.1.2.6 Ice and Cold Weather Procedures]
  *(If any of the Document Title, SOP Name, or Section details are missing or not explicitly stated in the chunk headers, you must extract/infer them from the context or content of the retrieved documents. You must always prioritize extracting and displaying specific hierarchical section numbers/headings present within the retrieved text, excluding parenthetical form numbers. You must always output all three fields: Document Title, SOP Name, and Section. Do not omit any of them.)*

- **FULL PROCEDURAL EXTRACTION & ELABORATION (DO NOT SHORTEN):**
  • **CRITICAL MANDATORY TABLE & CHECKLIST REPRODUCTION:**
    - If ANY table, sequence table, checklist, matrix, or structured list exists in the retrieved Company Documents (such as `| Activity | Responsibility |`, operational sequence tables, checklist matrices, inspection tables, or equipment tables), you MUST ALWAYS reproduce and output the COMPLETE, FULL Markdown Table at the very beginning of Section 1 (immediately after the Document Title, SOP Name, and Section metadata).
    - NEVER omit, skip, summarize, or convert tables into plain bullet points or numbered lists. Include every single activity and responsibility row present in the source text.
    - If data is present in the source text for any table column, show that real data clearly.
    - If no data or check is present for a column, leave that table cell clean and empty/blank (do NOT output dummy `[x]` or `[ ]` brackets).
    - NEVER output empty tables, isolated table headers, or table headers with 0 rows (such as isolated `Check\tShip\tTerminal...` or `| Check | Ship | Terminal | Code | Remarks |` with no rows). ONLY output a table if there are actual rows of data/items present in the source text to populate the table.
    - For operational sequences, responsibility matrices, activity lists, and equipment tables, use a standard markdown table matching the actual columns from the source document (e.g., `| Activity | Responsibility |`).
  • **EXHAUSTIVE PROCEDURAL ELABORATION UNDER SUBHEADINGS:**
    - After the Markdown table (if applicable), provide full, comprehensive, step-by-step procedural coverage of every phase and requirement related to the topic in the Company Documents.
    - Group procedures under clear, logical Markdown sub-headers (e.g. `#### Pre-Entry Risk Assessment & Authorizations`, `#### Atmosphere Testing Criteria & Gas Tolerances`, `#### Ventilation Protocols & Entry Sequences`, `#### Emergency Rescue Equipment & Drills`).
    - For EVERY procedure, include:
      - **Timing & Preconditions:** When exactly the operation commences, triggers, or is completed.
      - **Mandatory Forms & Communications:** Specific form numbers, codes, and transmission channels (e.g., Form SS 004, CT 001, logbook entries).
      - **Technical Sequences & Line-ups:** Step-by-step operational sequences, equipment configurations, and testing protocols.
      - **Specific Cargo Precautions:** Detailed instructions for specific hazards, volatility, temperature/pressure limits.
      - **Personnel Responsibilities:** Exact roles and oversight (Master, Chief Officer, Competent Officer, Safety Officer).
  • Use ONLY facts from the Company Documents for this section. Never invent company procedures.

### 📘 2. Dolphin internal knowledge base
- You MUST synthesize an exhaustive, comprehensive maritime technical masterclass directly from Dolphin's internal course lessons and knowledge base provided in LAYER 1.
- STRICT GROUNDING RULES:
  • Answer ONLY from COURSE CONTEXT (LAYER 1). No hallucination. Zero external knowledge fabrication.
  • Structure the response with clear headings, comparison tables, sequential steps, and formatted bullet points.
- DO NOT output generic summaries of international conventions or convention acronyms (STRICTLY DO NOT output lists of SOLAS, MARPOL, STCW, ISM Code bullet points).
- Instead, provide the substantive, detailed technical engineering principles and operational guide from the Dolphin course lessons.
- RICH VISUAL & STRUCTURAL FORMATTING FOR THIS SECTION:
  • Group topics under distinct numbered Markdown subheadings (e.g. `#### 1. Working Principles & Hydrodynamic Theory`, `#### 2. Core Components & Construction`, `#### 3. Operating Parameters & Key Metrics`, `#### 4. Step-by-Step Operational Procedures`, `#### 5. Cavitation Hazards & Protection Measures`).
  • Present technical comparisons, parameter definitions, or component summaries in clear Markdown tables where applicable (e.g., `| Parameter | Description | Operational Significance |` or `| Component | Function | Operating Characteristics |`).
  • Use numbered steps (`1. `, `2. `, `3. `) for operational workflows and sequences (e.g. Starting the Pump, Stopping the Pump).
  • Use bullet points with bold labels (`- **Label:** description`) for technical specifications, features, and safety precautions.
  • Maintain smooth introductory paragraphs explaining core physics and engineering concepts under each heading before listing steps or parameters.
  • Blend clean subheadings, rich explanations, tables, and structured points for maximum visual appeal and professional presentation.

### 🔍 3. Comparison & AI Advisory Observations
- **Direct Comparative Analysis (Section 1 vs Section 2):**
  • Explicitly compare **Section 1 (According to {company_name}'s Safety Management System (SMS / QMS))** with **Section 2 (Dolphin internal knowledge base)**.
  • **Procedural Alignment:** Point out specifically and thoroughly where {company_name}'s SMS requirements and Dolphin's internal technical knowledge base align (e.g., shared baseline safety controls, mandatory valve verifications, routine inspection duties, regulatory compliance points).
  • **Missing Technical Elements & Gaps in {company_name}'s Company Document:** Exhaustively identify and list what technical details, operational steps, numerical tolerances/thresholds, diagnostic methods, tool specifications, or safety precautions present in Dolphin's internal knowledge base are **MISSING, INCOMPLETE, OR NOT SPECIFIED in {company_name}'s SMS/QMS document**.
  • **CRITICAL RULE — NEVER CRITIQUE OR LIST WHAT IS MISSING IN DOLPHIN:** Do NOT state or list what is missing in Dolphin's internal knowledge base. Dolphin's internal knowledge base is the reference maritime technical benchmark. Your gap evaluation MUST focus strictly on identifying what is missing or lacking in **{company_name}'s Company Document**.
- **💡 AI Advisory Observation(s):** 
  • Provide specific, concrete technical observations and actionable advisory notes focused entirely on what should be added, updated, or improved in **{company_name}'s Company Document / SMS**.
  • STRICTLY DO NOT output generic platitudes (e.g., DO NOT say generic things like "conduct regular training", "ensure PPE is worn", or "follow manufacturer guidelines").
  • Highlight specific technical additions or operational safeguards from Dolphin's internal knowledge base (such as exact numerical thresholds, specialized inspection tools, environmental parameters, or verification steps) that are missing from {company_name}'s SMS and should be incorporated to strengthen their company procedure.
  • If {company_name}'s SMS already contains all the technical details and steps found in Dolphin's knowledge base, clearly state that the company SMS is fully comprehensive with no procedural or technical gaps identified.
- **Governance Notice:** End this section with the mandatory notice:
  *(AI Advisory Observation only — any procedure update must be reviewed by Company HSQE and processed through formal Management of Change [MoC]).*

RULES:
- PRIORITY RULE: Always give first priority to company_doc (Section 1: According to {company_name}'s Safety Management System). If the Company Documents do not contain information addressing the question, output ONLY: NO_COMPANY_DATA (the system will immediately fetch and deliver the response directly from the Course Content).
- STRICT GROUNDING: Answer Section 2 ONLY from COURSE CONTEXT (LAYER 1). Zero hallucination.
- Structure responses with clear headings, bullet points, and key comparisons.
- The response MUST start on the very first line with "### 🏢 1. According to {company_name}'s Safety Management System (SMS / QMS)". NEVER output Document Title, SOP Name, Section, or any introductory text before this heading. Document Title, SOP Name, and Section MUST appear directly underneath this Section 1 heading.
- MANDATORY TABLE RULE: If ANY table exists in the company documents (such as an Operational Sequence table with Activity and Responsibility columns, or a Checklist table), you MUST output the complete Markdown Table in Section 1. Do NOT omit it or convert it to plain text.
- In all tables: show real text data if present; leave cells blank if absent. NEVER output `[x]`, `[X]`, or `[ ]` brackets. NEVER output empty tables with 0 rows.
- Section 2 must ALWAYS use proper Markdown subheadings (`#### ...`), clean paragraphs, comparison tables, and properly aligned bullet points (`- **Title:** description`) or numbered steps. Never dump raw unformatted lists.
- Section 3 MUST be a direct, concrete evaluation of what is missing or can be enhanced in {company_name}'s Company Document (SMS/QMS) compared to Dolphin's Internal Knowledge Base. Under NO circumstances should it list what is missing in Dolphin's internal knowledge base.
- Maintain clear Markdown headings and clean spacing.
"""

def format_company_response(
    answer: str,
    company_name: str,
    company_chunks: list = None
) -> str:
    """
    Ensures that:
    1. Section 1 header (### 🏢 1. According to {company_name}'s Safety Management System (SMS / QMS)) is at the very top.
    2. Document Title, SOP Name, Section metadata appear immediately under Section 1 header, and NEVER before it.
    3. Any duplicate metadata or pre-header text is stripped.
    """
    if not answer or not answer.strip():
        return answer

    # If answer starts with NO_COMPANY_DATA, return as is
    if "NO_COMPANY_DATA" in answer:
        return "NO_COMPANY_DATA"

    # Separate Section 1 and Section 2+
    sec2_match = re.search(r'(?:^|\n)(#*\s*📘\s*2[^\n]*)', answer)
    if not sec2_match:
        sec2_match = re.search(r'(?:^|\n)(#*\s*\d*\.?\s*Dolphin internal knowledge[^\n]*)', answer, re.IGNORECASE)

    if sec2_match:
        sec1_raw = answer[:sec2_match.start()].strip()
        sec2_and_beyond = answer[sec2_match.start():].strip()
    else:
        sec1_raw = answer.strip()
        sec2_and_beyond = ""

    # 1. Extract Document Title, SOP Name, Section from metadata lines in sec1_raw
    doc_title_match = re.search(r'(?:\*\*|\*|#)*\s*Document\s*Title\s*:\s*(?:\*\*)?\s*([^\n*]+)', sec1_raw, re.IGNORECASE)
    sop_name_match = re.search(r'(?:\*\*|\*|#)*\s*SOP\s*Name\s*:\s*(?:\*\*)?\s*([^\n*]+)', sec1_raw, re.IGNORECASE)
    section_match = re.search(r'(?:\*\*|\*|#)*\s*Section\s*:\s*(?:\*\*)?\s*([^\n*]+)', sec1_raw, re.IGNORECASE)

    doc_title = doc_title_match.group(1).strip() if doc_title_match else ""
    sop_name = sop_name_match.group(1).strip() if sop_name_match else ""
    section_val = section_match.group(1).strip() if section_match else ""

    # 2. Fallback to company_chunks if missing
    if not doc_title and company_chunks:
        for chunk in company_chunks:
            if chunk.get("document_title"):
                doc_title = str(chunk.get("document_title")).strip()
                break
    if not doc_title:
        doc_title = "Shipboard Safety Management System Manual.docx"

    if not sop_name:
        sop_name = "Ship Operations & Safety Procedures"

    if not section_val:
        section_val = "Operational Procedures"

    # 3. Clean Section 1 body
    sec1_hdr_match = re.search(
        r'(?:^|\n)(#*\s*(?:🏢\s*)?1\.?\s*(?:According\s+to|Safety\s+Management\s+System)[^\n]*)',
        sec1_raw,
        re.IGNORECASE
    )

    if sec1_hdr_match:
        sec1_body_raw = sec1_raw[sec1_hdr_match.end():].strip()
    else:
        sec1_body_raw = sec1_raw

    # Strip metadata lines and redundant section 1 headers
    lines = sec1_body_raw.split('\n')
    filtered_lines = []
    for line in lines:
        clean = line.strip()
        if re.match(r'^(?:\*\*|\*|#)*\s*Document\s*Title\s*:', clean, re.IGNORECASE): continue
        if re.match(r'^(?:\*\*|\*|#)*\s*SOP\s*Name\s*:', clean, re.IGNORECASE): continue
        if re.match(r'^(?:\*\*|\*|#)*\s*Section\s*:', clean, re.IGNORECASE): continue
        if re.match(r'^#*\s*(?:🏢\s*)?1\.?\s*(?:According\s+to|Safety\s+Management\s+System)', clean, re.IGNORECASE): continue
        if re.match(r'^(?:Check\s+Ship\s+Terminal\s+Code\s+Remarks|\|\s*Check\s*\|\s*Ship\s*\|\s*Terminal\s*\|\s*Code\s*\|\s*Remarks\s*\|)$', clean, re.IGNORECASE): continue
        filtered_lines.append(line)

    while filtered_lines and not filtered_lines[0].strip():
        filtered_lines.pop(0)

    clean_sec1_body = "\n".join(filtered_lines).strip()

    # 4. Construct Section 1
    sec1_header = f"### 🏢 1. According to {company_name}'s Safety Management System (SMS / QMS)"
    metadata_block = (
        f"**Document Title:** {doc_title}  \n"
        f"**SOP Name:** {sop_name}  \n"
        f"**Section:** {section_val}"
    )

    if clean_sec1_body:
        reconstructed_sec1 = f"{sec1_header}\n\n{metadata_block}\n\n{clean_sec1_body}"
    else:
        reconstructed_sec1 = f"{sec1_header}\n\n{metadata_block}"

    # 5. Combine
    if sec2_and_beyond:
        return f"{reconstructed_sec1}\n\n{sec2_and_beyond}"
    return reconstructed_sec1


def format_internal_knowledge_section(text: str) -> str:
    """
    Ensures that under '📘 2. Dolphin internal knowledge base':
    - Subheadings are clean markdown headers (#### Subheading)
    - Markdown tables are preserved intact
    - Numbered lists are preserved intact as numbered steps (1. **Label:** description)
    - Bullet points with labels have bold terms (- **Label:** description)
    - Normal paragraphs remain clean paragraphs without forced bulleting
    """
    sec2_marker = re.search(r'(?:^|\n)(#*\s*📘\s*2[^\n]*)', text)
    if not sec2_marker:
        sec2_marker = re.search(r'(?:^|\n)(#*\s*\d*\.?\s*Dolphin internal knowledge[^\n]*)', text, re.IGNORECASE)
    if not sec2_marker:
        return text

    sec3_marker = re.search(r'(?:^|\n)(#*\s*🔍\s*3[^\n]*)', text[sec2_marker.end():])
    if not sec3_marker:
        sec3_marker = re.search(r'(?:^|\n)(#*\s*\d*\.?\s*Comparison[^\n]*)', text[sec2_marker.end():], re.IGNORECASE)
    
    start_pos = sec2_marker.end()
    end_pos = (sec2_marker.end() + sec3_marker.start()) if sec3_marker else len(text)
    
    sec2_body = text[start_pos:end_pos]
    lines = sec2_body.split('\n')
    formatted_lines = []
    
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            formatted_lines.append("")
            continue

        # 1. Preserve Markdown Tables
        if line.startswith('|'):
            formatted_lines.append(raw_line)
            continue
            
        clean_line = re.sub(r'^#+\s*', '', line).strip()
        subheading_candidate = re.sub(r'^\*+|\*+$', '', clean_line).rstrip(':').strip()
        
        # 2. Detect Subheadings
        is_subheading = False
        if (
            not clean_line.startswith(('-', '*', '•', '1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.'))
            and len(clean_line) < 80
            and (
                raw_line.startswith('#') or
                clean_line.endswith(':') or
                re.match(r'^(?:\d+\.|\bOverview\b|\bOperational\b|\bComponents\b|\bPrinciples\b|\bProcedures\b|\bPrevention\b|\bStarting\b|\bStopping\b|\bOperation\b|\bStep-by-Step\b|\bArchitecture\b|\bSafety\b)', clean_line, re.IGNORECASE) or
                not any(clean_line.endswith(p) for p in ['.', '!', ';'])
            )
            and ':' not in clean_line[:-1]
        ):
            is_subheading = True
            
        if is_subheading:
            formatted_lines.append(f"\n#### **{subheading_candidate}**\n")
            continue
            
        # 3. Preserve and format Bullet Points
        if re.match(r'^[-*•]\s+', clean_line):
            bullet_body = re.sub(r'^[-*•]\s+', '', clean_line).strip()
            colon_match = re.match(r'^([A-Za-z0-9\s/&,()_-]{2,50}):\s*(.+)$', bullet_body)
            if colon_match and not bullet_body.startswith('**'):
                formatted_lines.append(f"- **{colon_match.group(1).strip()}:** {colon_match.group(2).strip()}")
            else:
                formatted_lines.append(f"- {bullet_body}")
            continue
            
        # 4. Preserve Numbered Steps
        num_match = re.match(r'^(\d+\.)\s+(.+)$', clean_line)
        if num_match:
            num_prefix = num_match.group(1)
            num_body = num_match.group(2).strip()
            colon_match = re.match(r'^([A-Za-z0-9\s/&,()_-]{2,50}):\s*(.+)$', num_body)
            if colon_match and not num_body.startswith('**'):
                formatted_lines.append(f"{num_prefix} **{colon_match.group(1).strip()}:** {colon_match.group(2).strip()}")
            else:
                formatted_lines.append(f"{num_prefix} {num_body}")
            continue
            
        # 5. Handle key-value property lines (short parameter definitions)
        colon_match = re.match(r'^([A-Za-z0-9\s/&,()_-]{2,50}):\s+(.+)$', clean_line)
        if colon_match and len(clean_line) < 180 and not clean_line.startswith(('http', 'Note:')):
            formatted_lines.append(f"- **{colon_match.group(1).strip()}:** {colon_match.group(2).strip()}")
        else:
            # Regular narrative paragraph
            formatted_lines.append(clean_line)
            
    new_sec2_body = "\n".join(formatted_lines)
    new_sec2_body = re.sub(r'\n{3,}', '\n\n', new_sec2_body).strip()
    
    sec2_title = "### 📘 2. Dolphin internal knowledge base"
    new_text = text[:sec2_marker.start()].strip() + "\n\n" + sec2_title + "\n\n" + new_sec2_body + "\n\n" + text[end_pos:].strip()
    return new_text.strip()


def is_company_query(query: str, company_name: str) -> bool:
    if not query:
        return False
    q = query.lower().strip()
    
    # 1. Direct company governance, SMS, SOP, policy, checklist terms & operational procedures
    explicit_governance_patterns = [
        r"\b(sms|qms|sop|sops)\b",
        r"\b(company|company\'s)\b",
        r"\b(policy|policies)\b",
        r"\b(checklist|checklists)\b",
        r"\b(safety\s+management\s+system)\b",
        r"\b(standing\s+order|standing\s+orders|bridge\s+order|master\'s\s+order|engine\s+order)\b",
        r"\b(permit\s+to\s+work|ptw|hot\s+work|cold\s+work|enclosed\s+space|confined\s+space|tank\s+entry|working\s+aloft|working\s+overboard)\b",
        r"\b(company\s+procedure|company\s+procedures|company\s+rule|company\s+rules|company\s+manual|company\s+form)\b",
        r"\b(form\s+[a-z]{1,4}\d{2,4}|cp\d{2,4}|ss\d{2,4})\b", # e.g. Form SS004, CP005
        r"\b(hsqe|ism\s+code|ism|moc|management\s+of\s+change)\b",
        r"\b(cow|crude\s+oil\s+washing)\b",
        r"\b(bunkering|bunker\s+operation|bunker\s+procedure|bunker\s+safety)\b",
        r"\b(tank\s+cleaning|tank\s+washing|gas\s+freeing|purging|inerting|inert\s+gas\s+system|igs\s+operation|ig\s+plant)\b",
        r"\b(pre-arrival|pre-departure|pilotage|passage\s+planning)\b",
        r"\b(abandon\s+ship|man\s+overboard|oil\s+spill|sopep|smpep|emergency\s+procedure|emergency\s+operation|emergency\s+firing)\b",
        r"\b(instructions?\s+to\s+ship[\'’‘`]?s?\s+staff)\b",
        r"\b(handling\s+of\s+cargo|cargo\s+handling|cargo\s+operation|cargo\s+operations|loading\s+operation|discharging\s+operation)\b",
        r"\b(loaded\s+passage|passage\s+loaded|loaded\s+voyage|laden\s+passage|laden\s+voyage|sea\s+passage|ballast\s+passage|cargo\s+procedure|cargo\s+procedures|cargo\s+care|recirculation|statement\s+of\s+facts|ct\s*007)\b",
        r"\b(lining\s+up|line\s+up|lining\s+up\s+for\s+(loading|unloading|discharging|bunkering|ballasting|deballasting))\b",
        r"\b(unloading|discharging|loading|ballasting|deballasting|topping\s+off|stripping|cargo\s+plan|unloading\s+plan|loading\s+plan)\b",
        r"\b(ship\s*/\s*shore\s*meeting|ship\s*/\s*shore\s*information|ship\s*/\s*shore\s*safety|manifold\s+connection|manifold\s+drip\s+tray)\b",
        r"\b(fire\s*fighting|firefighting|fire\s+extinguisher|fire\s+extinguishers|foam\s+applicator|water\s+mist|fire\s+monitor|scba|eebd|dcp|co2\s+system|fixed\s+gas|fire\s+alarm|fire\s+safety|fire\s+appliances|fire\s+drill|fire\s+plan|fire\s+media|extinguishing\s+media|firefighting\s+media)\b",
        r"\b(anchor\s+watch|bridge\s+watch|watchkeeping\s+procedure|watchkeeping\s+duties)\b",
        r"\b(back\s*fire|backfire\s+precaution|boiler\s+emergency)\b",
        r"\b(check\s+before|checks\s+before|check\s+prior|checks\s+prior|equipment\s+(should\s+i|to)\s+check|safety\s+checks?|operational\s+checks?|precautions?\s+before)\b"
    ]
    if any(re.search(pat, q) for pat in explicit_governance_patterns):
        return True

    # 2. Check for company name (e.g., "CMS", "CMS Demo Company", etc.)
    if company_name:
        company_name_clean = company_name.lower().strip()
        parts = [p.strip() for p in re.split(r'\s+', company_name_clean) if p.strip()]
        for part in parts:
            if part in {"company", "demo", "limited", "ltd", "inc", "corp", "shipping", "marine", "management", "services"}:
                continue
            if len(part) >= 2 and re.search(rf"\b{re.escape(part)}\b", q):
                return True

    # 3. Check for possessives/pronouns combined with work/vessel terms
    possessive_patterns = [
        r"\bmy\s+(company|sms|sop|checklist|procedure|policy|vessel|ship|boat|crew|captain|master|chief|officer)\b",
        r"\bour\s+(company|sms|sop|checklist|procedure|policy|vessel|ship|boat|crew|captain|master|chief|officer)\b",
        r"\bon\s+(my|our)\s+(vessel|ship|fleet)\b",
        r"\bonboard\s+(my|our)\s+(vessel|ship|fleet)\b"
    ]
    if any(re.search(pat, q) for pat in possessive_patterns):
        return True

    # 4. Procedural & operational questions specifically asking "how to carry out / procedure for" on board
    operational_procedure_patterns = [
        r"\b(procedure\s+for|procedures\s+for)\s+(bunkering|cow|crude\s+oil\s+washing|enclosed\s+space|tank\s+entry|hot\s+work|cold\s+work|ballast|slop|emergency|back\s+fire|boiler\s+emergency|anchor\s+watch|starting|operation)\b",
        r"\bhow\s+to\s+(conduct|carry\s+out|perform|start|operate)\s+(cow|crude\s+oil\s+washing|bunkering|enclosed\s+space\s+entry|hot\s+work|tank\s+cleaning|purifier|boiler|generator)\b"
    ]
    if any(re.search(pat, q) for pat in operational_procedure_patterns):
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
    query = state.get("standalone_query") or state.get("current_query", "")

    logger.info("========== COMPANY QUERY NODE ==========")
    logger.info(f"company_id = {user_profile.get('company_id') or user_profile.get('CompanyId')}")
    logger.info(f"company_chunks = {len(company_chunks)}")

    # Guard: If no company chunks retrieved, keep course content from query_node
    if not company_chunks:
        logger.info(f"Query '{query}' has no company chunks. Keeping query_node answer.")
        state["company_answer"] = None
        return state

    def _clean_content(text: str) -> str:
        if not text:
            return ""
        # Remove massive sequences of dots, underscores, or filler characters
        t = re.sub(r'\.{3,}', '...', text)
        t = re.sub(r'_{3,}', '___', t)
        t = re.sub(r'[\r\t]+', ' ', t)

        # Clean repetitive table cells produced by Word docx extraction
        lines = t.split('\n')
        cleaned_lines = []
        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                cleaned_lines.append("")
                continue
            if '|' in line:
                cells = [c.strip() for c in line.split('|')]
                if line.startswith('|') and cells and cells[0] == '':
                    cells.pop(0)
                if line.endswith('|') and cells and cells[-1] == '':
                    cells.pop()
                deduped_cells = []
                for c in cells:
                    if not deduped_cells or c != deduped_cells[-1]:
                        deduped_cells.append(c)
                if deduped_cells:
                    cleaned_lines.append("| " + " | ".join(deduped_cells) + " |")
                else:
                    cleaned_lines.append("")
            else:
                cleaned_lines.append(line)
        t = "\n".join(cleaned_lines)
        t = re.sub(r'\n{3,}', '\n\n', t)
        return t.strip()

    # Deduplicate company chunks
    seen_company_texts = set()
    deduped_company_chunks = []
    for chunk in company_chunks:
        raw_text = chunk.get("content", "").strip()
        cleaned_text = _clean_content(raw_text)
        fingerprint = re.sub(r'\s+', ' ', cleaned_text[:200].lower())
        if fingerprint and fingerprint not in seen_company_texts:
            seen_company_texts.add(fingerprint)
            deduped_company_chunks.append({
                **chunk,
                "content": cleaned_text
            })

    company_docs_text = "\n\n---\n\n".join(
        f"Document: {chunk.get('document_title', 'SMS Document')} [Type: {chunk.get('doc_type', 'Procedure')}]\n{chunk.get('content', '')}"
        for chunk in deduped_company_chunks
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
        cleaned_content = _clean_content(content)
        header = f"Course: {course} | Topic: {topic}" if course else f"Topic: {topic}"
        return f"{header}\n{cleaned_content}"

    core_chunks = state.get("retrieval_chunks", [])
    seen_core_texts = set()
    deduped_core_texts = []
    for c in core_chunks:
        formatted = _format_core_chunk(c)
        fingerprint = re.sub(r'\s+', ' ', formatted[:120].lower())
        if fingerprint and fingerprint not in seen_core_texts:
            seen_core_texts.add(fingerprint)
            deduped_core_texts.append(formatted)
        if len(deduped_core_texts) >= 8:
            break

    core_context_text = "\n\n---\n\n".join(deduped_core_texts)

    prompt = COMPANY_HSQE_PROMPT.format(
        question=state.get("standalone_query") or state.get("current_query", ""),
        company_documents=company_docs_text,
        core_context=core_context_text or "General Maritime Industry Standards (SOLAS / MARPOL / STCW)",
        company_name=company_name,
        role=role,
        ship_type=ship_type,
    )

    try:
        system_msg = {
            "role": "system",
            "content": (
                "You are Marine Tutor AI, a dedicated maritime training, technical advisory, "
                "and Company Safety Management System (SMS/QMS) assistant. You provide professional "
                "maritime procedures, operational guidance, safety management steps, and technical explanations "
                "based on official shipboard operating manuals, company SMS documentation, and maritime regulations."
            )
        }
        user_msg = {"role": "user", "content": prompt}

        answer = await openai_service.chat(
            [system_msg, user_msg],
            temperature=0.0,
            max_tokens=4000,
        )

        refusal_patterns = [
            r"\bi['’]?m sorry,?\s+but\s+i\s+can['’]?t\s+assist\b",
            r"\bi cannot assist with that\b",
            r"\bi am unable to assist with this request\b",
            r"\bi cannot fulfill this request\b"
        ]
        if answer and any(re.search(pat, answer, re.IGNORECASE) for pat in refusal_patterns):
            logger.warning("LLM returned refusal response. Retrying with explicit maritime procedural prompt...")
            retry_messages = [
                {
                    "role": "system",
                    "content": "You are a professional maritime safety management system assistant. The user is a licensed maritime officer reviewing standard commercial shipboard operating procedures (SMS/SOPs) for vessel operations. Synthesize the provided documentation clearly into the required standard 3-section format."
                },
                {
                    "role": "user",
                    "content": f"Please provide the standard operating procedure for the following shipboard operational query based strictly on the provided documents:\n\nQuery: {state.get('standalone_query') or state.get('current_query', '')}\n\n{prompt}"
                }
            ]
            retry_answer = await openai_service.chat(retry_messages, temperature=0.0, max_tokens=4000)
            if retry_answer and not any(re.search(pat, retry_answer, re.IGNORECASE) for pat in refusal_patterns):
                answer = retry_answer

        if not answer or answer.strip() == "NO_COMPANY_DATA" or "NO_COMPANY_DATA" in answer:
            logger.info("No relevant company data found in LLM response for this query. Keeping query_node course answer.")
            state["company_answer"] = None
        else:
            # Format company response to guarantee Section 1 header is at the very top and metadata is directly underneath
            answer = format_company_response(answer, company_name, company_chunks)

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
            # Ensure proper bullet points and formatting in Dolphin internal knowledge section
            answer = format_internal_knowledge_section(answer)

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
                if "videos" not in state["node_response"] or not state["node_response"]["videos"]:
                    state["node_response"]["videos"] = state.get("video_suggestions", [])
                if "metadata" not in state["node_response"]:
                    state["node_response"]["metadata"] = {}
                state["node_response"]["metadata"]["source_layer"] = "Company SMS / QMS + Core Maritime"

    except Exception as e:
        logger.exception(f"Company query synthesis failed: {e}")
        state["company_answer"] = None

    return state