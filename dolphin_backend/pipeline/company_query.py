import hashlib
import re
from typing import Any, Dict, List
from loguru import logger
from services.status_service import get_status_event
from retrieval.normalization import (
    extract_distinctive_terms,
    normalize_text_for_retrieval,
    simple_stem,
    tokenize_for_retrieval,
    is_term_or_compound_in_text,
)

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

PRIMARY MANDATE — COMPANY DOCUMENT FIRST PRIORITY:
1. Always give FIRST PRIORITY to Company SMS/QMS Documents whenever the company documentation contains policies, operational guidelines, safety precautions, hazard controls, equipment instructions, or procedures addressing the topic of the question (e.g. Snap-back zones & Mooring operations, Enclosed space entry, Emergency fire pump, Navigation, Cargo handling, Bunkering, Hot work, etc.).
2. If the company documents contain specific guidelines, safety rules, deck markings, line handling procedures, or risk assessments covering the queried subject (such as snap-back hazard controls under mooring operations), they are HIGHLY RELEVANT. You MUST generate Section 1 with full procedural completeness.
3. Fallback to NO_COMPANY_DATA ONLY when the company documents have ZERO procedural or contextual relation to the queried topic (e.g. asking about diesel engine overhaul when the only retrieved chunks are about chart corrections or medical supplies).

TARGET EXHAUSTIVENESS & DEPTH (FULL PROCEDURAL COMPLETENESS — NEVER SUMMARIZE OR TRUNCATE):
- You MUST synthesize an exhaustive, in-depth technical response with maximum procedural detail drawn from all provided company chunks.
- Extract, elaborate, and present EVERY SINGLE technical requirement, procedural step, sub-clause, checklist item, operational threshold, crew responsibility, log-keeping duty, and safety precaution found in the provided contexts.
- Structure your response into 3 DISTINCT, HIGHLY PROFESSIONAL SECTIONS:

### 🏢 1. {company_name}'s Safety Management System (SMS / QMS)
- You MUST always display the following metadata directly under the Section 1 header (and NEVER before it), using exactly this format:
  **Document Title:** [Exact title of the document, e.g. Shipboard SMS Manual (Chemical)-Completed (1).docx]
  **SOP Name:** [Exact name of the SOP, e.g. Mooring Operations or Documentation]
  **Section:** [Section number/name/ID, e.g. III.5.1.4 Mooring Operations - Guidelines]
  *(Extract/infer all three fields from the retrieved company text. Do not omit any of them.)*

- **FULL PROCEDURAL EXTRACTION & ELABORATION (DO NOT CONDENSE OR SHORTEN):**
  • **CRITICAL MANDATORY TABLE & CHECKLIST REPRODUCTION:**
    - If ANY table, responsibility matrix, or checklist exists in the retrieved Company Documents (such as `| Activity | Responsibility |` or procedural action tables), you MUST ALWAYS output the COMPLETE, FULL Markdown Table at the very beginning of Section 1.
    - Include every single activity, parameter, and responsibility row present in the source text without omitting or summarizing any row.
    - If a multi-item checklist exists, break it down into clean, structured individual rows or distinct bullet points. Never compress multiple items into one cell.
  • **EXHAUSTIVE MULTI-PROCEDURAL BREAKDOWN:**
    - Provide deep, comprehensive procedural coverage for EVERY distinct procedure and safety rule present in the Company Documents (e.g. `#### Mooring Operations & Snap-Back Zone Safety Guidelines:`, `#### Operational Controls & Winch Safety:`, etc.).
    - Detail all specific precautions, deck markings, line types and elasticity rules, winch brake inspections, figure-of-eight bollard securing, personnel positioning, and PPE requirements.
  • Base Section 1 on the retrieved Company Documents and any provided Layer 3 Admin-Approved Feedback Preference. Never invent company procedures.

### 📘 2. Dolphin internal knowledge base
- STRICT SOURCE ISOLATION & INDEPENDENCE (ZERO COMPANY INFLUENCE):
  • Section 2 MUST BE 100% DRAWN EXCLUSIVELY FROM LAYER 1 (Dolphin course lessons & maritime technical knowledge base).
  • Section 2 MUST NEVER BE INFLUENCED, LIMITED, OR ALTERED by Section 1 or the Company SMS Documents in LAYER 2.
  • Synthesize an exhaustive, authoritative, deeply elaborate maritime technical, operational, and regulatory explanation drawn directly and comprehensively from the Dolphin course lessons provided in LAYER 1.
- DIRECT FACTUAL & REGULATORY ANSWERING:
  • You MUST DIRECTLY answer the user's specific question upfront in the opening paragraph.
  • If the question asks for dates, years, regulations, codes, historical milestones, adoption/effective dates (e.g., "When was the regulation...", "What date/year...", "Which chapter..."), explicitly provide all specific dates, years, international conventions/codes (e.g., IGC Code adopted in 1986, Chapter 13, SOLAS conventions, MARPOL Annexes, resolution numbers, entry-into-force dates) present in the course content.
  • Never omit or gloss over dates, years, or direct answers.
- TOPICAL STRUCTURING & TECHNICAL DEPTH (EXHAUSTIVE & DETAILED):
  • Organize Section 2 with clear, topic-specific Markdown subheadings tailored to the question and course material (e.g., `#### Regulation for [Topic] & Entry into Force Date`, `#### Key Points of the Regulation & Statutory Framework`, `#### Technical & Operational Requirements`, `#### Critical Safety Limits & Equipment Standards`).
  • Fully unpack all technical parameters (e.g., O₂ %, toxic gas PPM limits, sampling intervals such as 30 minutes, minimum equipment counts such as at least 2 portable sets), operational workflows, risk controls, and statutory requirements.
  • Include structured bullet points, clear bold labels, and Markdown tables where applicable from the course lessons.
  • Provide full in-depth explanations of principles, operational mechanisms, and standards from the internal course lessons.
  • Maintain 100% topic relevance strictly aligned with the user query and the retrieved course materials.

### 🔍 3. Comparison & AI Advisory Observations
- **Direct Comparative Analysis (Section 1 vs Section 2):**
  • Explicitly compare **Section 1 ({company_name}'s SMS)** with **Section 2 (Dolphin internal knowledge base)**.
  • **Procedural Alignment:** Detail specifically where {company_name}'s SMS requirements and the maritime industry benchmarks align (e.g., controlled transmittals, formal receipt acknowledgments, defined DO/Group I/C roles).
  • **Missing Technical Elements & Gaps in {company_name}'s Company Document:** Exhaustively identify specific technical details, verification steps, tracking mechanisms, or regulatory controls that are **MISSING, INCOMPLETE, OR NOT SPECIFIED in {company_name}'s SMS document**.
  • **CRITICAL RULE — NEVER CRITIQUE OR LIST WHAT IS MISSING IN DOLPHIN:** Evaluate only what is lacking or missing in **{company_name}'s Company Document**.
- **💡 AI Advisory Observation(s):** 
  • Provide specific, concrete technical recommendations for what should be incorporated into **{company_name}'s Company Document / SMS** to close the identified gaps.
  • Highlight actionable improvements (e.g., digital receipt tracking, specific revision audit logs, automated acknowledgment timelines).
  • If the SMS is already fully comprehensive, state that no procedural gaps were identified.
- **Governance Notice:** End with:
  *(AI Advisory Observation only — any procedure update must be reviewed by Company HSQE and processed through formal Management of Change [MoC]).*

RULES:
- CRITICAL OVERRIDE: If the retrieved Company Documents in LAYER 2 do NOT contain relevant procedures, rules, or operational standards directly answering or regulating the USER QUESTION (e.g. general maritime concepts, EEDI/CII, engineering theory, or unrelated company procedures), output ONLY: NO_COMPANY_DATA without any markdown or greetings.
- When relevant company procedures exist: Start directly on line 1 with "### 🏢 1. {company_name}'s Safety Management System (SMS / QMS)".
- Output Document Title, SOP Name, and Section directly under the Section 1 header.
- In Section 1, reproduce the complete multi-row table and exhaustively detail all sub-procedures based strictly on Company SMS.
- MANDATORY TABLE FORMATTING: ALL tables, checklists, matrices, and tabular procedures MUST be formatted in standard GitHub Flavored Markdown (GFM) using pipe delimiters (`|`) and a mandatory header separator row (`| :--- | :--- |`). NEVER output raw tab-separated or space-separated columns without pipes.
- Section 2 is STRICTLY and INDEPENDENTLY synthesized 100% from the internal Dolphin course lessons in LAYER 1 with complete depth and detail, completely uninfluenced by company SMS documents.
- Section 3 provides the comparative gap analysis between Section 1 and Section 2.
- Maintain clean Markdown formatting, bold headings, and professional maritime structure throughout.
"""


def normalize_markdown_tables(text: str) -> str:
    """
    Ensure all tables, tabular checklists, tab-separated rows, space-separated rows,
    and pipe rows with missing separator lines are normalized to valid GFM Markdown tables.
    """
    if not text:
        return ""

    lines = text.split("\n")
    result_lines = []
    
    in_table = False
    table_cols = 0

    for i, line in enumerate(lines):
        trimmed = line.strip()

        if not trimmed:
            in_table = False
            table_cols = 0
            result_lines.append("")
            continue

        # Check if line is already a markdown pipe row
        is_pipe_row = trimmed.startswith("|") and trimmed.endswith("|") and len(trimmed) > 2
        is_pipe_separator = is_pipe_row and bool(re.match(r'^\|(?:\s*:?-+:?\s*\|)+$', trimmed))

        # Check if line is a heading, list item, or quote
        is_markdown_element = trimmed.startswith(("#", "-", "*", ">")) or bool(re.match(r'^\d+\.', trimmed))

        # Extract cells from pipe row or whitespace/tab separated row
        cells = []
        if is_pipe_row:
            if is_pipe_separator:
                result_lines.append(trimmed)
                continue
            cells = [c.strip() for c in trimmed[1:-1].split("|")]
        elif not is_markdown_element:
            if "\t" in line:
                cells = [c.strip() for c in line.split("\t")]
            elif re.search(r'\S\s{2,}\S', trimmed):
                cells = [c.strip() for c in re.split(r'\s{2,}', trimmed)]
            elif in_table:
                # Sub-heading or single cell row inside an active table (e.g. "During Maintenance")
                cells = [trimmed]

        # Determine if this should be a table row
        if len(cells) >= 2 or (in_table and len(cells) == 1):
            if not in_table:
                in_table = True
                table_cols = max(len(cells), 2)
                
                while len(cells) < table_cols:
                    cells.append("")
                md_header = f"| {' | '.join(cells)} |"
                # Check if next line is already a separator
                next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
                next_is_sep = next_line.startswith("|") and bool(re.match(r'^\|(?:\s*:?-+:?\s*\|)+$', next_line))
                
                result_lines.append(md_header)
                if not next_is_sep:
                    md_sep = f"| {' | '.join(['---'] * table_cols)} |"
                    result_lines.append(md_sep)
            else:
                while len(cells) < table_cols:
                    cells.append("")
                md_row = f"| {' | '.join(cells[:table_cols])} |"
                result_lines.append(md_row)
        else:
            in_table = False
            table_cols = 0
            result_lines.append(line)

    return "\n".join(result_lines)


def format_company_response(
    answer: str,
    company_name: str,
    company_chunks: list = None
) -> str:
    """
    Ensures that:
    1. Section 1 header (### 🏢 1. {company_name}'s Safety Management System (SMS / QMS)) is at the very top.
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
        doc_title = f"{company_name} Safety Management System (SMS) Manual"

    if not sop_name:
        sop_name = "Safety & Operational Procedures"

    if not section_val:
        section_val = "General Requirements & Guidelines"

    # 3. Clean Section 1 body
    sec1_hdr_match = re.search(
        r'(?:^|\n)(#*\s*(?:🏢\s*)?1\.?\s*(?:According\s+to\s+)?.*?(?:Safety\s+Management\s+System|SMS\s*/\s*QMS)[^\n]*)',
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
        if re.match(r'^#*\s*(?:🏢\s*)?1\.?\s*(?:According\s+to\s+)?.*?(?:Safety\s+Management\s+System|SMS\s*/\s*QMS)', clean, re.IGNORECASE): continue
        if re.match(r'^(?:According\s+to\s+.*Safety\s+Management\s+System|According\s+to\s+.*SMS)', clean, re.IGNORECASE): continue
        if re.match(r'^(?:Check\s+Ship\s+Terminal\s+Code\s+Remarks|\|\s*Check\s*\|\s*Ship\s*\|\s*Terminal\s*\|\s*Code\s*\|\s*Remarks\s*\|)$', clean, re.IGNORECASE): continue
        filtered_lines.append(line)

    while filtered_lines and not filtered_lines[0].strip():
        filtered_lines.pop(0)

    clean_sec1_body = "\n".join(filtered_lines).strip()
    clean_sec1_body = normalize_markdown_tables(clean_sec1_body)

    # 4. Construct Section 1
    sec1_header = f"### 🏢 1. {company_name}'s Safety Management System (SMS / QMS)"
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
        r"\b(mooring|unmooring|berthing|unberthing|snap\s*back|snap-back|snapback|snap\s*back\s*zone|snap\s*back\s*zones|mooring\s+operation|mooring\s+operations|mooring\s+line|mooring\s+lines|mooring\s+rope|mooring\s+ropes|mooring\s+wire|mooring\s+wires|warping\s+drum|winch|windlass|fairlead|chock|bitts?|bollard|tug\s+line|towing|towage|pilot\s+ladder|gangway|rigging)\b",
        r"\b(back\s*fire|backfire\s+precaution|boiler\s+emergency)\b",
        r"\b(check\s+before|checks\s+before|check\s+prior|checks\s+prior|equipment\s+(should\s+i|to)\s+check|safety\s+checks?|operational\s+checks?|precautions?\s+before)\b"
    ]
    if any(re.search(pat, q) for pat in explicit_governance_patterns):
        return True

    # 2. Check for company name
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


def _clean_content(text: str) -> str:
    """
    Clean text formatting artifacts while strictly preserving valid tables,
    rows, procedures, values, and whitespace structure.
    """
    if not text:
        return ""
    # Remove massive sequences of dots, underscores, or filler characters
    t = re.sub(r'\.{4,}', '...', text)
    t = re.sub(r'_{4,}', '___', t)
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
            raw_cells = [c.strip() for c in line.split('|')]
            if line.startswith('|') and raw_cells and raw_cells[0] == '':
                raw_cells.pop(0)
            if line.endswith('|') and raw_cells and raw_cells[-1] == '':
                raw_cells.pop()
            
            non_empty = [c for c in raw_cells if c]
            # If all non-empty cells in this row are identical (e.g. Table of Contents repetition)
            if len(non_empty) > 1 and len(set(non_empty)) == 1:
                cleaned_lines.append(f"| {non_empty[0]} |")
            else:
                cleaned_lines.append("| " + " | ".join(raw_cells) + " |")
        else:
            cleaned_lines.append(line)
    t = "\n".join(cleaned_lines)
    t = re.sub(r'\n{3,}', '\n\n', t)
    return t.strip()


def _compute_chunk_hash(text: str) -> str:
    norm = re.sub(r"\s+", " ", (text or "").strip().lower())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


async def company_query_node(
    state: Dict[str, Any],
    openai_service,
    suggestion_service=None,
    on_token=None,
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
    logger.info(f"ship_type = {ship_type}")
    logger.info(f"raw company_chunks received = {len(company_chunks)}")

    # Guard: If no company chunks retrieved, keep course content from query_node
    if not company_chunks:
        logger.info(f"Query '{query}' has no company chunks. Keeping query_node answer.")
        state["company_answer"] = None
        return state

    # Guard: Pre-check topical relevance of retrieved company_chunks against the query
    distinctive_terms = extract_distinctive_terms(query)
    all_chunks_text = " ".join(
        f"{c.get('topic_name', '')} {c.get('title', '')} {c.get('document_title', '')} {c.get('content', '')} {c.get('topic_content', '')}"
        for c in company_chunks
    ).lower()

    ACRONYM_MAP = {
        "cow": ["crude oil washing", "crude oil wash", "cow"],
        "igs": ["inert gas system", "inert gas", "ig plant", "igs"],
        "ptw": ["permit to work", "ptw"],
        "eebd": ["emergency escape breathing device", "eebd"],
        "scba": ["self contained breathing apparatus", "scba"],
        "igf": ["low flashpoint", "low flash point", "igf code", "igf"],
        "moc": ["management of change", "moc"],
        "hsqe": ["health safety quality environment", "hsqe"],
        "sms": ["safety management system", "sms"],
        "qms": ["quality management system", "qms"],
        "sop": ["standard operating procedure", "sop"],
    }

    if distinctive_terms:
        has_overlap = False
        for dt in distinctive_terms:
            dt_stem = simple_stem(dt)
            if is_term_or_compound_in_text(dt, all_chunks_text) or is_term_or_compound_in_text(dt_stem, all_chunks_text):
                has_overlap = True
                break
            if dt in ACRONYM_MAP and any(exp in all_chunks_text for exp in ACRONYM_MAP[dt]):
                has_overlap = True
                break
            if dt_stem in ACRONYM_MAP and any(exp in all_chunks_text for exp in ACRONYM_MAP[dt_stem]):
                has_overlap = True
                break

        if not has_overlap:
            logger.info(
                f"[Company Query] Retrieved company_chunks have NO overlap with query distinctive terms {distinctive_terms}. "
                f"Setting company_answer = None and keeping course answer."
            )
            state["company_answer"] = None
            return state

    # -------------------------------------------------------------
    # 1. Deduplicate & Assemble Company Chunks with Token Budget
    # -------------------------------------------------------------
    seen_chunk_keys = set()
    deduped_company_chunks = []
    
    # Character budget for company context (45,000 to 55,000 chars)
    MAX_COMPANY_CHARS = 55000
    current_company_chars = 0

    for chunk in company_chunks:
        raw_text = chunk.get("content", "").strip()
        cleaned_text = _clean_content(raw_text)
        if not cleaned_text:
            continue

        doc_id = chunk.get("document_id")
        chunk_idx = chunk.get("chunk_index")
        faiss_idx = chunk.get("_faiss_index")
        content_hash = _compute_chunk_hash(cleaned_text)

        if doc_id is not None and chunk_idx is not None:
            dedup_key = ("doc_chunk", doc_id, chunk_idx)
        elif faiss_idx is not None:
            dedup_key = ("faiss", faiss_idx)
        else:
            dedup_key = ("hash", content_hash)

        if dedup_key not in seen_chunk_keys:
            seen_chunk_keys.add(dedup_key)
            chunk_len = len(cleaned_text)
            if current_company_chars + chunk_len > MAX_COMPANY_CHARS and len(deduped_company_chunks) >= 15:
                logger.info(f"Reached MAX_COMPANY_CHARS budget ({current_company_chars} chars, {len(deduped_company_chunks)} chunks)")
                break

            deduped_company_chunks.append({
                **chunk,
                "content": cleaned_text
            })
            current_company_chars += chunk_len

    # -------------------------------------------------------------
    # 2. Build Structured Company Context with Document Boundaries
    # -------------------------------------------------------------
    # Group chunks by document to preserve procedural hierarchy
    docs_map: Dict[str, List[Dict[str, Any]]] = {}
    for chunk in deduped_company_chunks:
        doc_title = chunk.get("document_title", "SMS Manual")
        if doc_title not in docs_map:
            docs_map[doc_title] = []
        docs_map[doc_title].append(chunk)

    doc_blocks = []
    for doc_title, chunks_in_doc in docs_map.items():
        doc_type = chunks_in_doc[0].get("doc_type", "Procedure")
        doc_id = chunks_in_doc[0].get("document_id", "N/A")
        
        indices = [c.get("chunk_index") for c in chunks_in_doc if c.get("chunk_index") is not None]
        chunk_range_str = f"Chunks {min(indices)} to {max(indices)}" if indices else f"{len(chunks_in_doc)} chunks"

        # Combine chunks in sequence
        combined_text = "\n\n".join(c.get("content", "") for c in chunks_in_doc)

        block = (
            f"=== COMPANY DOCUMENT ===\n"
            f"Document Title: {doc_title}\n"
            f"Document Type: {doc_type}\n"
            f"Document ID: {doc_id}\n"
            f"Coverage: {chunk_range_str}\n\n"
            f"{combined_text}\n"
            f"=== END COMPANY DOCUMENT ==="
        )
        doc_blocks.append(block)

    company_docs_text = "\n\n\n".join(doc_blocks)

    # -------------------------------------------------------------
    # 3. Format Dolphin Core Course Context
    # -------------------------------------------------------------
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
    MAX_CORE_CHARS = 45000
    current_core_chars = 0

    for c in core_chunks:
        formatted = _format_core_chunk(c)
        c_hash = _compute_chunk_hash(formatted)
        if c_hash not in seen_core_texts:
            seen_core_texts.add(c_hash)
            c_len = len(formatted)
            if current_core_chars + c_len > MAX_CORE_CHARS and len(deduped_core_texts) >= 15:
                break
            deduped_core_texts.append(formatted)
            current_core_chars += c_len
        if len(deduped_core_texts) >= 20:
            break

    core_context_text = "\n\n---\n\n".join(deduped_core_texts)

    logger.info(
        f"[Company Query] Formatted Context - Deduped Company Chunks: {len(deduped_company_chunks)}, "
        f"Company Chars: {len(company_docs_text)}, Core Chunks: {len(deduped_core_texts)}, Core Chars: {len(core_context_text)}"
    )

    prompt = COMPANY_HSQE_PROMPT.format(
        question=state.get("standalone_query") or state.get("current_query", ""),
        company_documents=company_docs_text,
        core_context=core_context_text or "General Maritime Industry Standards (SOLAS / MARPOL / STCW)",
        company_name=company_name,
        role=role,
        ship_type=ship_type,
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

            from services.suggestion_service import SuggestionService
            sugg_service = suggestion_service or SuggestionService()
            dynamic_suggestions = sugg_service.generate_from_response(
                query=query,
                response_text=pref_response,
                company_name=company_name,
                chunks=company_chunks or state.get("retrieval_chunks", []),
            )

            state["company_answer"] = pref_response
            state["node_response"] = {
                "type": "query",
                "content": pref_response,
                "sections": [
                    {
                        "topic_code": "APPROVED_FEEDBACK_STANDARD",
                        "topic_name": f"{company_name or 'HSQE'} Approved Standard Response",
                        "content": pref_response,
                    }
                ],
                "chunks_used": company_chunks or [],
                "question_suggestions": dynamic_suggestions,
                "videos": state.get("video_suggestions", []),
                "images": state.get("images", []),
                "pdfs": state.get("pdfs", []),
                "metadata": {
                    "source_layer": "Approved Feedback Memory (Verified Standard)",
                    "feedback_id": feedback_pref.get("feedback_id"),
                    "approved_similarity": sim,
                }
            }
            return state

        logger.info(f"✨ [Prompt Enrichment] Including Approved Feedback Preference in company query for '{feedback_pref.get('feedback_id')}'")
        pref_block = (
            f"\n\n===================================================\n"
            f"LAYER 3 — ADMIN-APPROVED FEEDBACK PREFERENCE (Verified Standard):\n"
            f"Matching Query Pattern: {feedback_pref.get('question')}\n"
            f"Authoritative Approved Preferred Response:\n{feedback_pref.get('preferred_response')}\n\n"
            f"CRITICAL MANDATORY INSTRUCTION:\n"
            f"1. The above Approved Preferred Response represents the verified, authoritative standard approved by HSQE Fleet Management.\n"
            f"2. You MUST directly feature and integrate all specific operational steps, line-ups, technical thresholds, and checklist requirements from this approved response directly inside Section 1 and Section 3.\n"
            f"3. Replace any incomplete descriptions with the precise technical instructions from this approved response.\n"
            f"===================================================\n"
        )
        prompt += pref_block

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

        if on_token:
            await on_token(get_status_event("generating"))
            accumulated_chunks = []
            buffer_flushed = False
            BUFFER_THRESHOLD = 50

            async for chunk in openai_service.stream_chat(
                [system_msg, user_msg],
                temperature=0.0,
                max_tokens=10000,
                category="COMPANY_QUERY",
            ):
                accumulated_chunks.append(chunk)
                current_text = "".join(accumulated_chunks)
                if not buffer_flushed:
                    if "NO_COMPANY_DATA" in current_text:
                        # Suppress streaming - this will fall back to query_node
                        continue
                    if len(current_text) >= BUFFER_THRESHOLD:
                        buffer_flushed = True
                        for b_chunk in accumulated_chunks:
                            await on_token({"type": "content", "token": b_chunk})
                else:
                    await on_token({"type": "content", "token": chunk})

            answer = "".join(accumulated_chunks)
            if not buffer_flushed and answer and "NO_COMPANY_DATA" not in answer:
                for b_chunk in accumulated_chunks:
                    await on_token({"type": "content", "token": b_chunk})
        else:
            answer = await openai_service.chat(
                [system_msg, user_msg],
                temperature=0.0,
                max_tokens=10000,
                category="COMPANY_QUERY",
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
            retry_answer = await openai_service.chat(retry_messages, temperature=0.0, max_tokens=10000)
            if retry_answer and not any(re.search(pat, retry_answer, re.IGNORECASE) for pat in refusal_patterns):
                answer = retry_answer

        if not answer or answer.strip() == "NO_COMPANY_DATA" or "NO_COMPANY_DATA" in answer:
            logger.info("No relevant company data found in LLM response for this query. Keeping query_node course answer.")
            state["company_answer"] = None
        else:
            # Format company response to guarantee Section 1 header is at the very top and metadata is directly underneath
            answer = format_company_response(answer, company_name, company_chunks)

            # Sanitize any accidental bracket checkboxes
            answer = re.sub(r'\[\s*[xX]?\s*\]', '', answer)
            # Ensure proper bullet points and formatting in Dolphin internal knowledge section
            answer = format_internal_knowledge_section(answer)

            state["company_answer"] = answer
            logger.info("✅ Company HSQE answer synthesized successfully")

            # Update or construct node_response so it is seamlessly sent to the UI
            if "node_response" not in state or not isinstance(state["node_response"], dict):
                state["node_response"] = {}

            # Generate dynamic, response-related question suggestions
            from services.suggestion_service import SuggestionService
            sugg_service = suggestion_service or SuggestionService()
            dynamic_suggestions = sugg_service.generate_from_response(
                query=query,
                response_text=answer,
                company_name=company_name,
                chunks=company_chunks or state.get("retrieval_chunks", []),
            )

            state["node_response"]["type"] = state["node_response"].get("type") or "query"
            state["node_response"]["content"] = answer
            state["node_response"]["sections"] = [
                {
                    "topic_code": "COMPANY_SMS",
                    "topic_name": f"{company_name} SMS & Maritime Standard",
                    "content": answer,
                }
            ]
            state["node_response"]["chunks_used"] = state["node_response"].get("chunks_used") or company_chunks or []
            state["node_response"]["question_suggestions"] = dynamic_suggestions
            state["node_response"]["videos"] = state["node_response"].get("videos") or state.get("video_suggestions", [])
            state["node_response"]["images"] = state["node_response"].get("images") or state.get("images", [])
            state["node_response"]["pdfs"] = state["node_response"].get("pdfs") or state.get("pdfs", [])
            if "metadata" not in state["node_response"] or not isinstance(state["node_response"]["metadata"], dict):
                state["node_response"]["metadata"] = {}
            state["node_response"]["metadata"]["source_layer"] = "Company SMS / QMS + Core Maritime"

    except Exception as e:
        logger.exception(f"Company query synthesis failed: {e}")
        state["company_answer"] = None

    return state