from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, Field


class VideoSuggestion(BaseModel):
    """Represents a clickable video recommendation for the UI."""

    title: str = ""
    url: str = ""
    thumbnail: str = ""
    video_id: Optional[str] = None


# class NodeResponse(BaseModel):
#     type: str
#     content: Any
#     chunks_used: List[dict]
#     video_suggestions: List[Any] = Field(default_factory=list)
#     videos: List[dict] = Field(default_factory=list)
#     images: List[dict] = Field(default_factory=list)
#     pdfs: List[dict] = Field(default_factory=list)
#     question_suggestions: List[str]
#     timestamp: datetime = Field(default_factory=datetime.utcnow)
#     metadata: dict[str, Any]

class NodeResponse(BaseModel):

    type: str
    content: str
    sections: List[dict] = Field(default_factory=list)
    chunks_used: List[dict]
    video_suggestions: List[Any] = Field(default_factory=list)
    videos: List[dict] = Field(default_factory=list)
    images: List[dict] = Field(default_factory=list)
    pdfs: List[dict] = Field(default_factory=list)
    question_suggestions: List[str]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)