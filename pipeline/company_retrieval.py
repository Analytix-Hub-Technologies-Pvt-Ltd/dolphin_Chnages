from typing import Any

from loguru import logger
from pipeline.manual_filter import is_manual_allowed_for_ship_type


async def company_retrieval_node(
    state: dict,
    company_vector_store,
) -> dict:
    """Retrieve relevant company-specific document chunks."""

    user_profile = state.get("user_profile", {}) or {}
    company_id = user_profile.get("company_id")
    ship_type = user_profile.get("ship_type") or user_profile.get("ShipType") or ""

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

    # Retrieve more company chunks so we have enough candidate chunks to filter
    k = 30

    chunks = await company_vector_store.search_with_embeddings(
        query,
        k=k,
    )

    logger.info(
        f"Company FAISS returned {len(chunks)} chunks "
        f"(requested k={k})"
    )

    company_chunks = []

    for i, chunk in enumerate(chunks):
        chunk_company_id = chunk.get("company_id")

        if str(chunk_company_id) != str(company_id):
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
        company_chunks.append(chunk)
        if len(company_chunks) >= 10:
            break

    state["company_chunks"] = company_chunks

    logger.info(
        f"✅ Final company chunks: {len(company_chunks)}"
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