# state.py
from __future__ import annotations
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field

from models.node_response import VideoSuggestion


class GraphState(BaseModel):
    # Incoming context
    messages: List[Any] = Field(default_factory=list)
    session_messages: List[Dict[str, Any]] = Field(default_factory=list)
    user_id: str = ""
    category: str = ""
    current_query: str = ""
    previous_questions: List[str] = Field(default_factory=list)
    meaningful_messages: List[Dict[str, Any]] = Field(default_factory=list)
    meaningful_history: List[Dict[str, Any]] = Field(default_factory=list)
    retrieval_chunks: List[Dict[str, Any]] = Field(default_factory=list)
    video_suggestions: List[VideoSuggestion] = Field(default_factory=list)

    # LangGraph checkpointer fields
    previous_successful_questions: List[str] = Field(default_factory=list)
    previous_successful_chunks: List[List[Dict[str, Any]]] = Field(
        default_factory=list
    )
    last_query_chunks: List[Dict[str, Any]] = Field(default_factory=list)
    last_quiz_chunks: List[Dict[str, Any]] = Field(default_factory=list)
    last_user_query: str = ""
    last_user_category: str = ""
    topic_history: List[str] = Field(default_factory=list)

    # MUST ALWAYS BE DICT (never None)
    router_decision: Dict[str, Any] = Field(default_factory=dict)

    # Node output - Make this more flexible temporarily
    node_response: Union[Dict[str, Any], Any] = Field(default_factory=dict)
