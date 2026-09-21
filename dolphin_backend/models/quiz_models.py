from __future__ import annotations

from typing import Dict, List
from pydantic import BaseModel, Field


class QuizQuestion(BaseModel):
    id: str
    question: str
    options: List[str]


class QuizItem(BaseModel):
    question: str
    options: List[str]
    correct_index: int


class QuizGenerateRequest(BaseModel):
    topic: str = Field(..., description="Topic for the generated quiz")


class QuizGenerateResponse(BaseModel):
    quiz_id: str
    questions: List[QuizQuestion]


class QuizSubmitRequest(BaseModel):
    quiz_id: str
    answers: Dict[str, str]


class QuizResultDetail(BaseModel):
    id: str
    selected: str
    correct: str
    is_correct: bool


class QuizSubmitResponse(BaseModel):
    score: int
    total: int
    percentage: float
    detailed: List[QuizResultDetail]


class QuizGradeRequest(BaseModel):
    quiz_items: List[QuizItem]
    user_answers: List[int]


class QuizCorrection(BaseModel):
    question: str
    correct_answer: str
    user_answer: str


class QuizGradeResponse(BaseModel):
    score_percent: float
    correct_count: int
    total: int
    corrections: List[QuizCorrection] = Field(default_factory=list)
