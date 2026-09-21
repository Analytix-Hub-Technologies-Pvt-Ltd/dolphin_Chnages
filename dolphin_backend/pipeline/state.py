# pipeline/state.py

from typing import Dict, Any, List


def create_initial_state(
    user_query: str,
    messages: List[Dict[str, Any]] | None = None,
    session_messages: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:

    return {
        "messages": messages or [],
        "session_messages": session_messages or [],
        "user_id": "",
        "category": "",
        "current_query": user_query,
        "previous_questions": [],
        "meaningful_messages": [],
        "meaningful_history": [],
        "retrieval_chunks": [],
        "video_suggestions": [],

        # tracking
        "previous_successful_questions": [],
        "previous_successful_chunks": [],
        "last_query_chunks": [],
        "last_quiz_chunks": [],
        "last_user_query": "",
        "last_user_category": "",
        "topic_history": [],

        # router + response
        "router_decision": {},
        "node_response": {},
    }