# services/answer_service.py

class AnswerService:
    def __init__(self, chat_service, openai_service, suggestion_service):
        self.chat_service = chat_service
        self.openai_service = openai_service
        self.suggestion_service = suggestion_service

    async def generate(self, query_data, state):
        query = query_data["standalone_query"]
        node_type = query_data["node_type"]

        # Retrieval
        if node_type in {"query", "quiz", "summary"}:
            chunks, video_suggestions = await self.chat_service._retrieve_chunks(query)
        else:
            chunks, video_suggestions = [], []

        # Inject into state
        state["current_query"] = query
        state["standalone_query"] = query
        state["retrieval_chunks"] = chunks
        state["video_suggestions"] = video_suggestions
        state["router_decision"] = query_data["router_decision"]

        # Call your existing pipeline
        if node_type == "query":
            from pipeline.query import query_node
            state = await query_node(
                state,
                self.openai_service,
                self.suggestion_service,
                self.chat_service.vector_store
            )

        return state