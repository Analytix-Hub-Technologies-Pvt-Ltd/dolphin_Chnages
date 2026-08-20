from __future__ import annotations

from pydantic import BaseModel


class RouterDecision(BaseModel):
    node_type: str
    short_topic: str
    reason: str
    category: str
