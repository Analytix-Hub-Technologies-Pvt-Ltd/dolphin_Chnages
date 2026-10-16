import re
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger


def is_doc_compatible_with_vessel(doc_title: str, user_ship_type: str) -> bool:
    """
    Check if a company document is relevant to the user's vessel type.
    Universal permits and general manuals are accepted for all.
    Specific manuals (OSV, Chemical, Oil Tanker, Container) match their respective type.
    """
    if not doc_title or not user_ship_type:
        return True

    t_lower = (doc_title or "").lower()
    s_lower = (user_ship_type or "").lower()

    # Universal documents (apply to all ship types)
    is_universal = any(u in t_lower for u in ["permit", "general", "policy", "contingency", "emergency", "checklist"])
    if not is_universal and bool(re.search(r'\bvol\.?\s*(?:i|1)\b', t_lower)) and not bool(re.search(r'\bvol\.?\s*(?:ii|2)\b', t_lower)):
        is_universal = True

    if is_universal:
        if "except for osv" in t_lower and ("osv" in s_lower or "offshore" in s_lower):
            return False
        return True

    # Vessel specific checks:
    # 1. OSV / Offshore
    if "osv" in t_lower or "offshore" in t_lower:
        return "osv" in s_lower or "offshore" in s_lower

    # 2. Chemical Tanker
    if "chemical" in t_lower:
        return "chemical" in s_lower

    # 3. Oil Tanker
    if "oil tanker" in t_lower or "oil" in t_lower:
        return "oil" in s_lower and "tanker" in s_lower

    # 4. Container
    if "container" in t_lower:
        return "container" in s_lower

    return True


async def get_company_template_catalog(
    pool,
    company_id: str,
    ship_type: str = "",
) -> List[Tuple[str, str]]:
    """
    Returns a deduplicated list of available (clean_title, doc_id_or_code)
    templates and permits for the user's company and vessel type.
    """
    if not pool or not company_id:
        return []

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT document_id, document_title
                FROM public.company_documents
                WHERE (company_id = $1 OR company_id LIKE $1 || '%') AND is_active = TRUE
                ORDER BY document_id
                """,
                str(company_id).strip(),
            )
            if not rows:
                rows = await conn.fetch(
                    """
                    SELECT document_id, document_title
                    FROM public.company_documents
                    WHERE is_active = TRUE
                    ORDER BY document_id
                    """
                )

        templates: List[Tuple[str, str]] = []
        seen = set()

        for r in rows:
            title = r["document_title"] or ""
            if not is_doc_compatible_with_vessel(title, ship_type):
                continue

            # Standalone permits / checklists / forms
            if any(w in title.upper() for w in ["PERMIT", "CHECKLIST", "FORM", "CRANE", "PTW", "FORMAT"]):
                clean = re.sub(r"\.docx?$", "", title, flags=re.IGNORECASE).strip()
                clean = re.sub(r"\s+", " ", clean).title()
                if "crane" in clean.lower() and "permit" not in clean.lower():
                    clean = f"{clean} Permit"
                if clean.lower() not in seen:
                    seen.add(clean.lower())
                    templates.append((clean, str(r["document_id"])))

        # Also add well-known standard SMS forms present in shipboard SMS manuals
        manual_forms = [
            ("Hot Work Permit (SS 001)", "SS 001"),
            ("Enclosed Space Entry Permit (SS 004)", "SS 004"),
            ("Cold Work Permit (SS 002)", "SS 002"),
            ("Electrical Work Permit / EIC (SS 003)", "SS 003"),
            ("Bunkering Safety Checklist (E05-A)", "E05-A"),
            ("Safety Familiarisation Checklist (SS 006)", "SS 006"),
            ("Risk Assessment Format (RA 001)", "RA 001"),
        ]
        for name, code in manual_forms:
            base = name.split("(")[0].strip().lower()
            if not any(base in s for s in seen):
                seen.add(base)
                templates.append((name, code))

        return templates
    except Exception as exc:
        logger.warning(f"Error fetching template catalog: {exc}")
        return []


async def fetch_template_document_data(
    pool,
    company_id: str,
    ship_type: str,
    template_target: str,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Retrieves the document content and title for a specific template.
    1. Searches standalone permit documents for this company.
    2. If not standalone, extracts the relevant section from the compatible vessel manual.
    """
    if not pool or not company_id or not template_target:
        return None, None

    target_clean = (template_target or "").strip()
    target_lower = target_clean.lower()

    # Determine optimal search keywords based on template target
    search_terms: List[str] = []
    if "enclosed" in target_lower or "confined" in target_lower or "ss 004" in target_lower:
        search_terms = ["enclosed", "confined", "ss 004", "ss004"]
    elif "cold" in target_lower or "ss 002" in target_lower:
        search_terms = ["cold work", "cold", "ss 002", "ss002"]
    elif "hot" in target_lower or "ss 001" in target_lower:
        search_terms = ["hot work", "hot", "ss 001", "ss001"]
    elif "electrical" in target_lower or "ss 003" in target_lower:
        search_terms = ["electrical", "ss 003", "ss003"]
    elif "familiar" in target_lower or "ss 006" in target_lower:
        search_terms = ["familiaris", "familiariz", "ss 006", "ss006"]
    elif "bunker" in target_lower or "e05" in target_lower:
        search_terms = ["bunkering", "e05"]
    elif "risk" in target_lower or "ra 001" in target_lower:
        search_terms = ["risk assessment", "ra 001", "ra001"]
    elif "crane" in target_lower or "personnel" in target_lower:
        search_terms = ["crane", "personnel transfer"]
    elif "height" in target_lower or "overside" in target_lower:
        search_terms = ["height", "overside"]
    elif "underwater" in target_lower:
        search_terms = ["underwater"]
    elif "high voltage" in target_lower:
        search_terms = ["high voltage"]
    elif "weather" in target_lower or "deck" in target_lower:
        search_terms = ["adverse weather", "deck"]
    elif "lift" in target_lower:
        search_terms = ["passenger lift", "lift"]
    elif "pipeline" in target_lower:
        search_terms = ["pressurised pipeline", "pipeline"]
    # Dynamic significant word extraction from target title (e.g. "Scaffolding Safety Checklist" -> ["scaffolding", "safety"])
    significant_words = [
        w.lower() for w in re.findall(r'\b\w+\b', target_clean)
        if w.lower() not in {"permit", "checklist", "form", "template", "format", "ptw", "the", "and", "for", "of", "work"}
        and len(w) >= 3
    ]
    for sw in significant_words:
        if sw not in search_terms:
            search_terms.append(sw)

    if not search_terms:
        first_term = target_clean.split()[0] if target_clean.split() else target_clean
        search_terms = [first_term.lower()]

    try:
        async with pool.acquire() as conn:
            # 1. Standalone permit doc search for this company
            for st in search_terms:
                row = await conn.fetchrow(
                    """
                    SELECT document_id, document_title, document_content
                    FROM public.company_documents
                    WHERE is_active = TRUE
                      AND (company_id = $1 OR company_id LIKE $1 || '%')
                      AND document_title ILIKE $2
                    LIMIT 1
                    """,
                    str(company_id).strip(),
                    f"%{st}%",
                )
                if row and row["document_content"]:
                    return row["document_title"], row["document_content"]

            # Fallback across all active company docs for standalone permits
            for st in search_terms:
                row = await conn.fetchrow(
                    """
                    SELECT document_id, document_title, document_content
                    FROM public.company_documents
                    WHERE is_active = TRUE AND document_title ILIKE $1
                    LIMIT 1
                    """,
                    f"%{st}%",
                )
                if row and row["document_content"]:
                    return row["document_title"], row["document_content"]

            # 2. Search inside the vessel-compatible SMS manual
            manual_rows = await conn.fetch(
                """
                SELECT document_id, document_title, document_content
                FROM public.company_documents
                WHERE is_active = TRUE
                  AND (company_id = $1 OR company_id LIKE $1 || '%')
                  AND document_title ILIKE '%Manual%'
                ORDER BY document_id
                """,
                str(company_id).strip(),
            )
            if not manual_rows:
                manual_rows = await conn.fetch(
                    """
                    SELECT document_id, document_title, document_content
                    FROM public.company_documents
                    WHERE is_active = TRUE AND document_title ILIKE '%Manual%'
                    ORDER BY document_id
                    """
                )

            # First pass: try compatible vessel manuals
            for m in manual_rows:
                title = m["document_title"] or ""
                if not is_doc_compatible_with_vessel(title, ship_type):
                    continue
                content = m["document_content"] or ""
                content_lower = content.lower()
                for st in search_terms:
                    idx = content_lower.find(st)
                    if idx != -1:
                        # Extract ~8,000 characters around the form / checklist section
                        start = max(0, idx - 400)
                        end = min(len(content), idx + 8000)
                        return title, content[start:end]

            # Second pass: if vessel manual only references the form code, check any manual that has the full form
            for m in manual_rows:
                content = m["document_content"] or ""
                content_lower = content.lower()
                for st in search_terms:
                    idx = content_lower.find(st)
                    if idx != -1:
                        start = max(0, idx - 400)
                        end = min(len(content), idx + 8000)
                        return m["document_title"], content[start:end]

        return None, None
    except Exception as exc:
        logger.warning(f"Error retrieving specific template document: {exc}")
        return None, None


async def company_retrieval_node(
    state: dict,
    company_vector_store,
) -> dict:
    """Retrieve relevant company-specific document chunks filtered by vessel type."""

    user_profile = state.get("user_profile", {}) or {}
    company_id = user_profile.get("company_id")
    ship_type = (user_profile.get("ship_type") or "").strip()

    if not company_id:
        logger.warning("No company_id found in user profile")
        state["company_chunks"] = []
        return state

    query = (
        state.get("standalone_query")
        or state.get("current_query")
    )

    if not query:
        logger.warning("No query available for company retrieval")
        state["company_chunks"] = []
        return state

    # Retrieve company chunks
    k = 10
    chunks = await company_vector_store.search_with_embeddings(
        query,
        k=k,
    )

    logger.info(
        f"Company FAISS returned {len(chunks)} chunks (requested k={k}) | ship_type='{ship_type}'"
    )

    company_chunks = []
    for i, chunk in enumerate(chunks):
        chunk_company_id = chunk.get("company_id")

        if str(chunk_company_id) == str(company_id):
            doc_title = chunk.get("document_title") or ""
            # Apply vessel compatibility filter
            if ship_type and not is_doc_compatible_with_vessel(doc_title, ship_type):
                logger.info(
                    f"⏩ Vessel filter: Chunk {i} ('{doc_title}') excluded for ship_type '{ship_type}'"
                )
                continue

            logger.info(f"✅ Company & Vessel matched for chunk {i}: {doc_title}")
            company_chunks.append(chunk)

    state["company_chunks"] = company_chunks
    logger.info(f"✅ Final company chunks: {len(company_chunks)}")
    return state





# from typing import Any

# from loguru import logger

# async def company_retrieval_node(
#     state: dict,
#     company_vector_store,
# ):

#     company_id = (
#         state.get("user_profile", {})
#         .get("company_id")
#     )

#     if not company_id:
#         state["company_chunks"] = []
#         return state

#     query = state.get(
#         "standalone_query",
#         state.get("current_query")
#     )

#     chunks = await company_vector_store.search_with_embeddings(
#         query,
#         k=5
#     )

#     logger.info(f"FAISS returned {len(chunks)} chunks")

#     for i, c in enumerate(chunks):
#         logger.info(f"Chunk {i}: {c}")

#     company_chunks = []

#     for c in chunks:
#         logger.info(
#             f"Chunk company_id={c.get('company_id')} ({type(c.get('company_id'))})"
#         )
#         logger.info(
#             f"User company_id={company_id} ({type(company_id)})"
#         )

#         if str(c.get("company_id")) == str(company_id):
#             logger.info("✅ Company matched")
#             company_chunks.append(c)

#     state["company_chunks"] = company_chunks

#     return state