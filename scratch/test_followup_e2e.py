import asyncio
import sys
from loguru import logger

from services.followup_resolver import (
    is_followup_query,
    extract_topic_from_query,
    resolve_followup_retrieval_query,
)
from services.chat_service import ChatService
from unittest.mock import AsyncMock, MagicMock

async def simulate_conversation_flow():
    # Setup mock OpenAI service with a proper chat response
    mock_openai = MagicMock()
    mock_openai.chat = AsyncMock(return_value="Rewritten Query from LLM")

    mock_embedder = MagicMock()
    mock_store = MagicMock()

    chat_service = ChatService(
        openai_service=mock_openai,
        embedder=mock_embedder,
        store=mock_store,
    )

    conversation_history = []
    current_topic = ""

    turns = [
        ("Procedures for Enclosed Space Entry", "Standalone Question 1"),
        ("tell me indepth", "Follow-up Depth 1"),
        ("what are the specific checklists for this?", "Follow-up Checklists 1"),
        ("Now explain cargo loading sequence", "Topic Switch Question 2"),
        ("give more details", "Follow-up Depth 2"),
    ]

    print("=" * 70)
    print("SIMULATING MULTI-TURN CONVERSATIONAL SESSION")
    print("=" * 70)

    for i, (user_msg, label) in enumerate(turns, 1):
        print(f"\n--- Turn {i}: [{label}] ---")
        print(f"User Input: '{user_msg}'")
        print(f"Active Topic Before: '{current_topic}'")

        is_followup = is_followup_query(
            current_query=user_msg,
            previous_questions=conversation_history,
            conversation_topic=current_topic,
        )
        print(f"Is Follow-up Query: {is_followup}")

        # Update topic or preserve
        if not is_followup:
            current_topic = extract_topic_from_query(user_msg)
            print(f"-> Topic Extracted/Updated: '{current_topic}'")
        else:
            print(f"-> Topic Preserved: '{current_topic}'")

        # Resolve retrieval query
        rewritten = await chat_service.rewrite_query(
            current_query=user_msg,
            previous_questions=conversation_history,
            last_answer=None,
            conversation_topic=current_topic,
        )
        print(f"-> Internal Retrieval Query: '{rewritten}'")

        # Append to history
        conversation_history.append(user_msg)

    print("\n" + "=" * 70)
    print("VERIFICATION CHECKS:")
    print("=" * 70)

    # Assertions
    assert current_topic == "Cargo Loading Sequence"
    print("[SUCCESS] Multi-turn conversational flow passed all assertions flawlessly!")

if __name__ == "__main__":
    asyncio.run(simulate_conversation_flow())
