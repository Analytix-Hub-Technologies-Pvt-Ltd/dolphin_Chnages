# chat_pipeline.py

from typing import Dict, Any, Tuple, List


class ChatPipeline:

    def __init__(
        self,
        analyzer,
        retrieval_node,
        query_node,
        summary_node,
        quiz_node,
        greeting_node,
        fallback_node,
        goodbye_node,
        thank_node,
        well_wish_node,
        threadning_node,
        negative_node,
    ):
        self.analyzer = analyzer
        self.retrieval_node = retrieval_node
        self.query_node = query_node
        self.summary_node = summary_node
        self.quiz_node = quiz_node
        self.greeting_node = greeting_node
        self.fallback_node = fallback_node
        self.goodbye_node = goodbye_node
        self.thank_node = thank_node
        self.well_wish_node = well_wish_node
        self.threadning_node = threadning_node
        self.negative_node = negative_node

    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:

        # 🔹 Step 1: Router
        decision = state.get("router_decision", {})
        node_type = decision.get("node_type", "fallback")

        # 🔹 Step 2: Route manually

        if node_type == "query":
            state = await self.retrieval_node.run(state)
            state = await self.query_node.run(state)
            return state

        elif node_type == "summary":
            return await self.summary_node.run(state)

        elif node_type == "quiz":
            state = await self.retrieval_node.run(state)
            return await self.quiz_node.run(state)

        elif node_type == "greeting":
            return await self.greeting_node.run(state)

        elif node_type == "goodbye":
            return await self.goodbye_node.run(state)

        elif node_type == "thank":
            return await self.thank_node.run(state)

        elif node_type == "well_wish":
            return await self.well_wish_node.run(state)

        elif node_type == "threadning":
            return await self.threadning_node.run(state)

        elif node_type == "negative":
            return await self.negative_node.run(state)

        else:
            return await self.fallback_node.run(state)