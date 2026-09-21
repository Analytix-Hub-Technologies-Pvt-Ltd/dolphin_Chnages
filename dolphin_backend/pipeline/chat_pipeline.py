# pipeline/chat_pipeline.py

class ChatPipeline:

    def __init__(self, nodes: dict):
        self.nodes = nodes

    async def run(self, state):

        # -----------------------------
        # STEP 1: ROUTER
        # -----------------------------
        state = await self.nodes["router"](state)

        node_type = state.get("router_decision", {}).get("node_type", "fallback")

        # -----------------------------
        # STEP 2: ROUTING LOGIC
        # -----------------------------
        if node_type == "query":
            state = await self.nodes["retrieval"](state)
            state = await self.nodes["query"](state)

        elif node_type == "summary":
            state = await self.nodes["summary"](state)

        elif node_type == "quiz":
            state = await self.nodes["retrieval"](state)
            state = await self.nodes["quiz"](state)

        elif node_type == "greeting":
            state = await self.nodes["greeting"](state)

        elif node_type == "goodbye":
            state = await self.nodes["goodbye"](state)

        elif node_type == "thank":
            state = await self.nodes["thank"](state)

        elif node_type == "well_wish":
            state = await self.nodes["well_wish"](state)

        elif node_type == "threadning":
            state = await self.nodes["threadning"](state)

        elif node_type == "negative":
            state = await self.nodes["negative"](state)

        else:
            state = await self.nodes["fallback"](state)

        return state