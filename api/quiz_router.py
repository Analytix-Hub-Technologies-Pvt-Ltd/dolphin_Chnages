from __future__ import annotations

from typing import Dict, List
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from models.quiz_models import (
    QuizGenerateRequest,
    QuizGenerateResponse,
    QuizGradeRequest,
    QuizGradeResponse,
    QuizItem,
    QuizQuestion,
    QuizResultDetail,
    QuizSubmitRequest,
    QuizSubmitResponse,
)

router = APIRouter(prefix="/quiz", tags=["quiz"])

QUIZ_STORE: Dict[str, Dict[str, object]] = {}


def _question_bank(topic: str) -> List[Dict[str, object]]:
    base_questions = [
        {
            "question": "What is the primary function of a marine diesel engine turbocharger?",
            "options": [
                "To reduce exhaust noise",
                "To increase airflow and improve combustion",
                "To cool the engine block",
                "To filter incoming fuel",
            ],
            "correct": "To increase airflow and improve combustion",
        },
        {
            "question": "Which component mixes fuel with high-pressure air in a common rail system?",
            "options": [
                "Injector",
                "Exhaust manifold",
                "Sea water pump",
                "Turbocharger diffuser",
            ],
            "correct": "Injector",
        },
        {
            "question": "Why is lube oil analysis critical for marine engines?",
            "options": [
                "It measures the exhaust gas temperature",
                "It confirms the color of the oil",
                "It detects wear particles and contamination",
                "It calculates propeller thrust",
            ],
            "correct": "It detects wear particles and contamination",
        },
        {
            "question": "What does the jacket water system primarily control?",
            "options": [
                "Fuel viscosity",
                "Cylinder liner temperature",
                "Propeller speed",
                "Sea chest pressure",
            ],
            "correct": "Cylinder liner temperature",
        },
        {
            "question": "During a start failure, which check is most important before attempting a restart?",
            "options": [
                "If the navigation lights are on",
                "Whether the engine room is painted",
                "If starting air pressure is within range",
                "How many crew are on deck",
            ],
            "correct": "If starting air pressure is within range",
        },
    ]

    if topic:
        emphasized_questions = []
        for q in base_questions:
            emphasized_questions.append(
                {
                    **q,
                    "question": f"[{topic}] {q['question']}",
                }
            )
        return emphasized_questions

    return base_questions


@router.post("/generate", response_model=QuizGenerateResponse)
def generate_quiz(payload: QuizGenerateRequest) -> QuizGenerateResponse:
    quiz_id = str(uuid4())
    question_bank = _question_bank(payload.topic)

    questions: List[QuizQuestion] = []
    answers: Dict[str, str] = {}

    for idx, question in enumerate(question_bank, start=1):
        question_id = f"q{idx}"
        questions.append(
            QuizQuestion(
                id=question_id,
                question=question["question"],
                options=question["options"],
            )
        )
        answers[question_id] = question["correct"]

    QUIZ_STORE[quiz_id] = {"questions": questions, "answers": answers}

    return QuizGenerateResponse(quiz_id=quiz_id, questions=questions)


@router.post("/submit", response_model=QuizSubmitResponse)
def submit_quiz(payload: QuizSubmitRequest) -> QuizSubmitResponse:
    quiz = QUIZ_STORE.get(payload.quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    answers: Dict[str, str] = quiz["answers"]  # type: ignore[assignment]
    questions: List[QuizQuestion] = quiz["questions"]  # type: ignore[assignment]

    detailed_results: List[QuizResultDetail] = []
    score = 0

    for question in questions:
        selected_answer = payload.answers.get(question.id, "")
        correct_answer = answers.get(question.id, "")
        is_correct = selected_answer == correct_answer
        if is_correct:
            score += 1

        detailed_results.append(
            QuizResultDetail(
                id=question.id,
                selected=selected_answer,
                correct=correct_answer,
                is_correct=is_correct,
            )
        )

    total_questions = len(questions)
    percentage = round((score / total_questions) * 100, 2) if total_questions else 0

    return QuizSubmitResponse(
        score=score,
        total=total_questions,
        percentage=percentage,
        detailed=detailed_results,
    )


@router.post("/grade", response_model=QuizGradeResponse)
def grade_quiz(payload: QuizGradeRequest) -> QuizGradeResponse:
    quiz_items: List[QuizItem] = payload.quiz_items
    user_answers: List[int] = payload.user_answers

    total = len(quiz_items)
    correct = 0
    corrections: List[QuizResultDetail] = []

    for idx, item in enumerate(quiz_items):
        try:
            user_choice = user_answers[idx]
        except IndexError:
            user_choice = -1
        if user_choice == item.correct_index:
            correct += 1

        correct_answer_text = ""
        user_answer_text = ""

        if isinstance(item.options, list):
            if 0 <= item.correct_index < len(item.options):
                correct_answer_text = item.options[item.correct_index]
            if 0 <= user_choice < len(item.options):
                user_answer_text = item.options[user_choice]

        corrections.append(
            QuizResultDetail(
                id=str(idx),
                selected=user_answer_text,
                correct=correct_answer_text,
                is_correct=user_choice == item.correct_index,
            )
        )

    score_percent = round((correct / total) * 100, 2) if total else 0

    return QuizGradeResponse(
        score_percent=score_percent,
        correct_count=correct,
        total=total,
        corrections=[
            {
                "question": quiz_items[idx].question,
                "correct_answer": corr.correct,
                "user_answer": corr.selected,
            }
            for idx, corr in enumerate(corrections)
        ],
    )
