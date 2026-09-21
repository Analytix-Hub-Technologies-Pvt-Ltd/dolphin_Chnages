from typing import Any, Dict

DOLPHIN_STATUS_MESSAGES: Dict[str, str] = {
    "understanding": "Dolphin is thinking...",
    "searching": "Dolphin is searching the relevant information...",
    "company_search": "Dolphin is searching company documents...",
    "course_search": "Dolphin is searching course materials...",
    "analyzing": "Dolphin is analyzing the retrieved information...",
    "preparing": "Dolphin is preparing your answer...",
    "generating": "Dolphin is generating your response...",
    "completed": "completed",
}


def get_status_event(status_key: str, fallback_message: str = None) -> Dict[str, Any]:
    """
    Return a standardized, sanitized status event dictionary.
    Guarantees that no internal prompts, tokens, reasoning, or private data are leaked.
    """
    message = fallback_message or DOLPHIN_STATUS_MESSAGES.get(
        status_key, "Dolphin is thinking..."
    )
    return {
        "type": "status",
        "status": status_key,
        "message": message,
    }
