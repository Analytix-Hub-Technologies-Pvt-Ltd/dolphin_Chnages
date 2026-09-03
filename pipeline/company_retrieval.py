from typing import Any

from loguru import logger
from pipeline.manual_filter import is_manual_allowed_for_ship_type


def is_company_match(chunk_cid: Any, user_cid: Any, company_name: str = "", chunk_cname: str = "") -> bool:
    """
    Check if a chunk belongs to the user's company dynamically.
    Matches by exact ID, company name, or dynamic multi-tenant ID relationship across systems.
    """
    c_chunk = str(chunk_cid).strip() if chunk_cid is not None else ""
    c_user = str(user_cid).strip() if user_cid is not None else ""
    c_name = str(company_name).lower().strip() if company_name else ""
    c_chunk_name = str(chunk_cname).lower().strip() if chunk_cname else ""

    # 1. Direct ID match
    if c_chunk and c_user and c_chunk == c_user:
        return True

    # 2. Company name match
    if c_name and c_chunk_name and (c_name == c_chunk_name or c_name in c_chunk_name or c_chunk_name in c_name):
        return True

    # 3. Dynamic numeric/prefix relationship across multi-tenant identifier formats (e.g. user '8' with doc '824866')
    if c_chunk and c_user and (c_chunk.startswith(c_user) or c_user.startswith(c_chunk)):
        return True

    # 4. If chunk_cid matches user's company name string directly
    if c_chunk and c_name and c_chunk.lower() == c_name:
        return True

    return False


async def company_retrieval_node(
    state: dict,
    company_vector_store,
) -> dict:
    """Retrieve relevant company-specific document chunks."""

    user_profile = state.get("user_profile", {}) or {}
    company_id = user_profile.get("company_id")
    company_name = (
        user_profile.get("company_name")
        or user_profile.get("CompanyName")
        or user_profile.get("company")
        or ""
    )
    ship_type = user_profile.get("ship_type") or user_profile.get("ShipType") or ""

    if not company_id and not company_name:
        logger.warning("No company_id or company_name found in user profile")
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

    # Retrieve more company chunks so we have enough candidate chunks to filter across multi-tenant index
    k = 100

    chunks = await company_vector_store.search_with_embeddings(
        query,
        k=k,
    )

    logger.info(
        f"Company FAISS returned {len(chunks)} chunks "
        f"(requested k={k})"
    )

    matched_chunks = []
    matched_faiss_indices = []

    for i, chunk in enumerate(chunks):
        chunk_company_id = chunk.get("company_id")
        chunk_cname = chunk.get("company_name", "")

        if not is_company_match(chunk_company_id, company_id, company_name, chunk_cname):
            logger.info(
                f"❌ Company mismatch for chunk {i}: chunk={chunk_company_id}, user={company_id}"
            )
            continue

        doc_title = chunk.get("document_title", "")
        if not is_manual_allowed_for_ship_type(doc_title, ship_type):
            logger.info(
                f"🚫 Filtered out chunk {i} ('{doc_title}') for ship type '{ship_type}'"
            )
            continue

        logger.info(
            f"✅ Company and ship type matched for chunk {i} ('{doc_title}')"
        )
        matched_chunks.append(chunk)
        faiss_idx = chunk.get("_faiss_index")
        if faiss_idx is not None:
            matched_faiss_indices.append(faiss_idx)

    # Sequential neighbor expansion: add adjacent chunks (+1, -1) from the same document
    # so multi-chunk tables, operational sequences, and full procedures are preserved
    expanded_chunks = list(matched_chunks)
    seen_indices = set(matched_faiss_indices)

    if hasattr(company_vector_store, "id_to_metadata") and company_vector_store.id_to_metadata:
        for faiss_idx in matched_faiss_indices[:15]:
            for neighbor_idx in [faiss_idx - 1, faiss_idx + 1]:
                if (
                    0 <= neighbor_idx < len(company_vector_store.id_to_metadata)
                    and neighbor_idx not in seen_indices
                ):
                    neighbor_meta = dict(company_vector_store.id_to_metadata[neighbor_idx])
                    neighbor_cid = neighbor_meta.get("company_id")
                    neighbor_cname = neighbor_meta.get("company_name", "")
                    neighbor_doc = neighbor_meta.get("document_title", "")
                    if is_company_match(neighbor_cid, company_id, company_name, neighbor_cname) and is_manual_allowed_for_ship_type(neighbor_doc, ship_type):
                        neighbor_meta["_faiss_index"] = neighbor_idx
                        expanded_chunks.append(neighbor_meta)
                        seen_indices.add(neighbor_idx)

    # Sort chunks by document and original sequential index to maintain natural document order
    expanded_chunks.sort(key=lambda c: (c.get("document_title", ""), c.get("_faiss_index", 0)))

    state["company_chunks"] = expanded_chunks[:35]

    logger.info(
        f"✅ Final company chunks: {len(state['company_chunks'])}"
    )

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