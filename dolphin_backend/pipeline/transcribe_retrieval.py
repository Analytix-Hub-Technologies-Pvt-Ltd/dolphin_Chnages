async def transcribe_retrieval_node(
    state,
    vector_store,
):
    query = state["standalone_query"]

    chunks = await vector_store.search_with_embeddings(
        query,
        k=3,
    )

    state["transcribe_chunks"] = chunks

    return state