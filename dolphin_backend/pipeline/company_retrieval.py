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