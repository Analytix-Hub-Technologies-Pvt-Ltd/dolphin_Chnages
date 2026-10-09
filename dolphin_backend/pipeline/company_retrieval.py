from typing import Any

from loguru import logger


async def company_retrieval_node(
    state: dict,
    company_vector_store,
) -> dict:
    """Retrieve relevant company-specific document chunks."""

    company_id = (
        state.get("user_profile", {})
        .get("company_id")
    )

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

    # Retrieve more company chunks so the LLM has enough
    # information to generate a detailed answer.
    k = 10

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

        logger.info(
            f"Chunk {i}: "
            f"company_id={chunk_company_id} "
            f"({type(chunk_company_id)}) | "
            f"user_company_id={company_id} "
            f"({type(company_id)})"
        )

        if str(chunk_company_id) == str(company_id):
            logger.info(
                f"✅ Company matched for chunk {i}"
            )
            company_chunks.append(chunk)
        else:
            logger.info(
                f"❌ Company mismatch for chunk {i}"
            )

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