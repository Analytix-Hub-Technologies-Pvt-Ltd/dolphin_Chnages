# services/query_service.py

class QueryService:
    def __init__(self, chat_service):
        self.chat_service = chat_service
        self.analyzer = chat_service.analyzer

    async def process(self, current_query, previous_questions, last_answer):
        # Rewrite
        standalone_query = await self.chat_service.rewrite_query(
            current_query,
            previous_questions,
            last_answer
        )

        # Intent classify
        decision = await self.analyzer.classify_for_router(
            standalone_query,
            previous_questions
        )

        return {
            "standalone_query": standalone_query,
            "node_type": decision.get("node_type"),
            "category": decision.get("category"),
            "router_decision": decision
        }