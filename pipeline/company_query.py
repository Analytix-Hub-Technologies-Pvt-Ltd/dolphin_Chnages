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

### 🏢 1. According to {company_name}'s Safety Management System (SMS / QMS)
- Present the company-specific procedure, checklist, policy, or requirements in full detail.
- Explicitly cite the document title, SOP name, or manual section (e.g. *Bridge Procedures Manual*, *Cargo Operations SOP*, *SMS Section 6*).
- Include ALL relevant procedural steps, roles, responsibilities, checklist tables, and operational thresholds explicitly stated in the Company Documents.
- Do NOT artificially shorten or omit checklist items or verification tables. Format tables clearly: `| Check | Ship | Terminal | Code | Remarks |`.
- Use ONLY facts from the Company Documents for this section. Never invent company procedures.

### 📘 2. International Maritime Standard & Industry Baseline
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
- Maintain clear Markdown headings, bullet points, and clean spacing.
"""


async def company_query_node(
    state: Dict[str, Any],
    openai_service,
) -> Dict[str, Any]:
    company_chunks = state.get("company_chunks", [])
    user_profile = state.get("user_profile", {}) or {}
    company_name = user_profile.get("company_name") or user_profile.get("company") or "your company"
    role = user_profile.get("role", "Seafarer")
    ship_type = user_profile.get("ship_type", "Vessel")

    logger.info("========== COMPANY QUERY NODE ==========")
    logger.info(f"company_id = {user_profile.get('company_id')}")
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