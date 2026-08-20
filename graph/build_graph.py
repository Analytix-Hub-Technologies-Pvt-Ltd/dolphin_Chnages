from langgraph.graph import END, StateGraph

from graph.fallback_node import FallbackNode
from graph.greeting_node import GreetingNode
from graph.query_node import QueryNode
from graph.quiz_node import QuizNode
from graph.retrieval_node import RetrievalNode
from graph.router_node import RouterNode
from graph.goodbye_node import GoodbyeNode
from graph.state import GraphState
from graph.summary_node import SummaryNode
from graph.thank_node import ThankYouNode
from graph.well_wish import WellWishNode
from graph.threadning import ThreadningNode
from graph.negative import NegativeNode
from services.openai_service import OpenAIService
from services.query_analyzer import EnhancedQueryAnalyzer
from services.suggestion_service import SuggestionService
from services.gpt_intent_service import GPTIntentService
from services.query_expansion_service import QueryExpansionService
from config import settings
from loguru import logger

def build_graph(openai: OpenAIService, suggestion_service: SuggestionService, vector_store):

    intent_service = GPTIntentService()
    analyzer = EnhancedQueryAnalyzer(intent_service)
    graph = StateGraph(GraphState)
    
    # -------------------------------
    # INITIALIZE QUERY EXPANSION SERVICE
    # -------------------------------
    query_expansion_service = None
    if settings.enable_query_expansion:
        logger.info("🔍 Query Expansion: ENABLED")
        query_expansion_service = QueryExpansionService(
            openai_service=openai,
            vector_store=vector_store,  # Pass vector store for generic acronym loading
            enabled=settings.enable_query_expansion
        )
    else:
        logger.info("🔍 Query Expansion: DISABLED")

    # -------------------------------
    # REGISTER NODES
    # -------------------------------
    graph.add_node("router", RouterNode(analyzer))
    graph.add_node("retrieval", RetrievalNode(vector_store, query_expansion_service))
    graph.add_node("query", QueryNode(openai, suggestion_service, vector_store))  # Pass vector_store for fuzzy search
    graph.add_node("summary", SummaryNode(openai, suggestion_service))
    graph.add_node("quiz", QuizNode(openai, suggestion_service))
    graph.add_node("greeting", GreetingNode(suggestion_service))
    graph.add_node("fallback", FallbackNode(suggestion_service, openai))  # Pass openai for dynamic messages
    graph.add_node("goodbye", GoodbyeNode(suggestion_service))
    graph.add_node("thank", ThankYouNode(suggestion_service))
    graph.add_node("well_wish", WellWishNode(suggestion_service))
    graph.add_node("threadning", ThreadningNode(suggestion_service))
    graph.add_node("negative", NegativeNode(suggestion_service))

    # -------------------------------
    # SET ENTRYPOINT
    # -------------------------------
    if hasattr(graph, "set_entrypoint"):
        graph.set_entrypoint("router")
    else:
        graph.set_entry_point("router")

    # -------------------------------
    # ROUTING LOGIC
    # -------------------------------
    graph.add_conditional_edges(
        "router",
        lambda state: state.router_decision.get("node_type", "fallback"),
        {
            "query": "retrieval",
            "summary": "summary",
            "quiz": "retrieval",
            "greeting": "greeting",
            "fallback": "fallback",
            "goodbye": "goodbye",
            "thank": "thank",
            "well_wish": "well_wish",
            "threadning": "threadning",
            "negative": "negative",
        },
    )

    graph.add_edge("retrieval", "query")

    graph.add_conditional_edges(
        "query",
        lambda state: state.router_decision.get("node_type", "query"),
        {
            "query": END,
            "summary": "summary",
            "quiz": "quiz",
            "greeting": "greeting",
            "fallback": "fallback",
            "goodbye": "goodbye",
            "thank": "thank",
            "well_wish": "well_wish",
            "threadning": "threadning",
            "negative": "negative",
        },
    )

    graph.add_edge("summary", END)
    graph.add_edge("quiz", END)
    graph.add_edge("greeting", END)
    graph.add_edge("fallback", END)
    graph.add_edge("goodbye", END)
    graph.add_edge("thank", END)
    graph.add_edge("well_wish", END)
    graph.add_edge("threadning", END)
    graph.add_edge("negative", END)

    return graph
