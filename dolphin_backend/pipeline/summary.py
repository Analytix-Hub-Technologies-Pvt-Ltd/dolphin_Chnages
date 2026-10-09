# pipeline/summary.py

from typing import Any, Dict, List, Tuple
from loguru import logger

# 👉 import ALL helpers (reuse your existing logic)
from pipeline.history_utils import extract_clean_history

SUMMARY_PROMPT = """
You are Marine Tutor AI creating a PROFESSIONAL SESSION SUMMARY.

CURRENT SESSION DATA:
{topics_block}

OUTPUT:

[ANSWER SECTION]
## Session Summary

**Session Metrics:**
- Topics Covered: {topic_count}
- Learning Areas: {learning_areas}

### Key Learning Outcomes
- Summarize key learning points clearly

### Topics Covered
Provide structured explanation for each topic.

### Topic Connections
Explain relationships between topics.

### Recommended Next Steps
Suggest next learning steps.

[SUGGESTIONS SECTION]
1. Ask a follow-up question?
2. Ask practical usage?
3. Ask real-world scenario?
4. Ask advanced concept?
5. Ask safety/regulation question?
"""


# -----------------------------
# SAFE GET
# -----------------------------
def safe_get(state: Any, key: str, default=None):
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


# -----------------------------
# SUGGESTION PATTERN FILTER
# -----------------------------
def is_suggestion_pattern(user_query: str) -> bool:
    if not user_query or not isinstance(user_query, str):
        return False

    query_lower = user_query.strip().lower()

    suggestion_endings = [
        "aid navigation",
        "safe at sea",
        "vital onboard",
        "used afloat",
        "underway"
    ]

    for ending in suggestion_endings:
        if query_lower.endswith(ending + "?") or query_lower.endswith(ending):
            return True

    return False


# -----------------------------
# CHECK VALID CONTENT
# -----------------------------
def has_substantial_chunks(chunks):
    if not chunks:
        return False

    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue

        for key in ["content", "topic_content", "summary", "text"]:
            content = chunk.get(key, "")
            if isinstance(content, str) and len(content.strip()) > 50:
                return True

    return False


# -----------------------------
# VALIDATE COURSE CONTENT
# -----------------------------
def is_from_course_content(chunks, user_query):
    if not has_substantial_chunks(chunks):
        return False

    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue

        for key in ["content", "topic_content", "summary", "text"]:
            content = chunk.get(key, "")
            if isinstance(content, str) and len(content.strip()) > 50:
                if not content.startswith(("http://", "https://")):
                    return True

    return False


# -----------------------------
# 🔥 KEEP ALL YOUR UTIL FUNCTIONS (UNCHANGED)
# -----------------------------
# 👉 COPY THESE FROM YOUR ORIGINAL FILE (NO CHANGE):
# - normalize_video_url
# - is_suggestion_pattern
# - has_substantial_chunks
# - is_from_course_content

# (I am not repeating them here to keep answer readable — but KEEP THEM)

async def summary_node(
    state: Dict[str, Any],
    openai_service,
    suggestion_service,
) -> Dict[str, Any]:

    logger.info("=" * 80)
    logger.info("[SUMMARY] FUNCTION START")
    logger.info("=" * 80)

    decision = safe_get(state, "router_decision", {}) or {}
    full_history = safe_get(state, "meaningful_history", []) or []
    current_query = safe_get(state, "current_query", "") or ""

    logger.info(f"[SUMMARY] History count: {len(full_history)}")

    # -----------------------------
    # BUILD CONTEXTS (RELAXED)
    # -----------------------------
    contexts = []

    for i, entry in enumerate(full_history):
        if not isinstance(entry, dict):
            continue

        node_type = str(entry.get("node_type", "")).lower()
        if node_type not in {"query", "quiz"}:
            continue

        logger.info(f"[SUMMARY] Processing entry {i}")

        contexts.append({
            "user_query": entry.get("user_query", ""),
            "content": entry.get("content", ""),
            "chunks": entry.get("chunks", []),
            "short_topic": entry.get("short_topic", ""),
        })

    logger.info(f"[SUMMARY] contexts built: {len(contexts)}")

    if not contexts:
        logger.warning("[SUMMARY] No contexts → fallback")

        return {
            "node_response": {
                "type": "summary",
                "content": "No topics available yet.",
                "question_suggestions": [
                    "What topic would you like to learn?",
                    "Ask about marine navigation",
                    "Explain ship safety systems"
                ],
            },
            "meaningful_history": full_history,
        }

    # -----------------------------
    # BUILD TOPICS BLOCK
    # -----------------------------
    topics_block = ""

    for i, ctx in enumerate(contexts, 1):
        topics_block += f"""
Topic {i}: {ctx.get("short_topic") or ctx.get("user_query")}
Notes: {ctx.get("content")[:300]}
"""

    # -----------------------------
    # ENTERPRISE PROMPT (SAME AS GRAPH)
    # -----------------------------
    prompt = SUMMARY_PROMPT.format(
        topics_block=topics_block,
        topic_count=len(contexts),
        learning_areas=", ".join(
            list(set([c.get("short_topic", "") for c in contexts if c.get("short_topic")]))
        ),
    )

    logger.info("[SUMMARY] Calling LLM...")

    # -----------------------------
    # LLM CALL
    # -----------------------------
    llm_response = await openai_service.chat(
        [{"role": "user", "content": prompt}],
        temperature=0,
        category="SUMMARY",
    )

    logger.info(f"[SUMMARY] LLM RESPONSE:\n{llm_response}")

    # -----------------------------
    # 🔥 SAME EXTRACTION AS GRAPH
    # -----------------------------
    def extract_answer_and_suggestions(text: str):
        answer = text
        suggestions = []

        if "[SUGGESTIONS SECTION]" in text:
            parts = text.split("[SUGGESTIONS SECTION]")

            answer_part = parts[0]
            suggestions_part = parts[1]

            if "[ANSWER SECTION]" in answer_part:
                answer = answer_part.split("[ANSWER SECTION]")[1].strip()

            for line in suggestions_part.split("\n"):
                line = line.strip()

                if line and line[0].isdigit():
                    suggestions.append(line[2:].strip())

        # fallback extract
        if not suggestions:
            suggestions = [
                l.strip() for l in text.split("\n")
                if l.strip().endswith("?")
            ]

        # final fallback
        if not suggestions:
            suggestions = [
                "Which topic would you like to explore more?",
                "How does this apply in real marine operations?",
                "What safety aspects should be considered?",
                "Can we go deeper into this topic?",
                "What should I learn next?"
            ]

        return answer, suggestions[:5]

    answer, suggestions = extract_answer_and_suggestions(llm_response)

    logger.info(f"[SUMMARY] Extracted suggestions: {len(suggestions)}")

    # -----------------------------
    # RESPONSE
    # -----------------------------
    state["node_response"] = {
        "type": "summary",
        "content": answer,
        "question_suggestions": suggestions,
        "chunks_used": [],
        "videos": [],
        "images": [],
        "pdfs": [],
        "metadata": {
            "short_topic": decision.get("short_topic", "summary"),
            "routing_reason": "summary",
        },
    }

    logger.info("[SUMMARY] FUNCTION DONE")

    return state














# # -----------------------------
# # MAIN FUNCTION (REPLACES CLASS)
# # -----------------------------
# async def summary_node(
#     state: Dict[str, Any],
#     openai_service,
#     suggestion_service,
# ) -> Dict[str, Any]:

#     logger.info("=" * 80)
#     logger.info("[SUMMARY] Starting summary generation")
#     logger.info("=" * 80)

#     decision = safe_get(state, "router_decision", {}) or {}
#     full_history = safe_get(state, "meaningful_history", []) or []
#     current_query = safe_get(state, "current_query", "") or ""

#     # -----------------------------
#     # 🔥 TOPIC COUNT EXTRACTION
#     # -----------------------------
#     def extract_topic_count(query: str) -> int:
#         import re

#         if not query:
#             return 0

#         q = query.lower()

#         if any(x in q for x in ["all topics", "everything", "full summary"]):
#             return 999

#         match = re.search(r'(\d+)', q)
#         if match:
#             return int(match.group(1))

#         return 0

#     requested_count = extract_topic_count(current_query)

#     # -----------------------------
#     # 🔥 FILTER CONTEXTS
#     # -----------------------------
#     contexts = []

#     for entry in full_history:
#         if not isinstance(entry, dict):
#             continue

#         node_type = str(entry.get("node_type", "")).lower()

#         if node_type not in {"query", "quiz"}:
#             continue

#         chunks = entry.get("chunks", [])
#         user_query = entry.get("user_query", "")

#         if not chunks:
#             continue

#         contexts.append({
#             "user_query": user_query,
#             "chunks": chunks,
#             "content": entry.get("content", ""),
#             "short_topic": entry.get("short_topic", ""),
#             "timestamp": entry.get("timestamp", ""),
#         })

#     # -----------------------------
#     # LIMIT
#     # -----------------------------
#     if requested_count > 0:
#         contexts = contexts[-requested_count:]
#     elif len(contexts) > 10:
#         contexts = contexts[-10:]

#     if not contexts:
#         state["node_response"] = {
#             "type": "summary",
#             "content": "No valid topics found in session.",
#             "chunks_used": [],
#             "video_suggestions": [],
#             "videos": [],
#             "images": [],
#             "pdfs": [],
#             "question_suggestions": [],
#             "metadata": {
#                 "short_topic": "summary",
#                 "routing_reason": "no_topics",
#             },
#         }
#         return state

#     # -----------------------------
#     # BUILD TOPICS BLOCK
#     # -----------------------------
#     topics_block = ""

#     for i, ctx in enumerate(contexts, 1):
#         topics_block += f"""
# Topic {i}: {ctx.get("short_topic") or ctx.get("user_query")}
# Notes: {ctx.get("content")[:300]}
# """

#     # -----------------------------
#     # PROMPT
#     # -----------------------------
#     prompt = f"""
# Summarize this session:

# {topics_block}
# """

#     # -----------------------------
#     # LLM CALL
#     # -----------------------------
#     llm_response = await openai_service.chat(
#         [{"role": "user", "content": prompt}],
#         category="SUMMARY"
#     )

#     # -----------------------------
#     # MEDIA
#     # -----------------------------
#     merged_chunks = []
#     for ctx in contexts:
#         merged_chunks.extend(ctx.get("chunks", []))

#     videos, images, pdfs = [], [], []

#     for c in merged_chunks:
#         videos.extend(c.get("videos", []))
#         images.extend(c.get("images", []))
#         pdfs.extend(c.get("pdfs", []))

#     # -----------------------------
#     # RESPONSE
#     # -----------------------------
#     state["node_response"] = {
#         "type": "summary",
#         "content": llm_response,
#         "chunks_used": merged_chunks,
#         "video_suggestions": videos[:10],
#         "videos": videos[:10],
#         "images": images[:5],
#         "pdfs": pdfs[:5],
#         "question_suggestions": suggestion_service.generate(
#             query=current_query,
#             chunks=merged_chunks,
#             history=contexts,
#             short_topic="summary",
#             category="summary",
#         ),
#         "metadata": {
#             "short_topic": decision.get("short_topic", "summary"),
#             "routing_reason": decision.get("reason", "summary"),
#         },
#     }

#     # -----------------------------
#     # UPDATE HISTORY
#     # -----------------------------
#     history_entry = {
#         "node_type": "summary",
#         "content": llm_response,
#         "user_query": current_query,
#         "chunks": merged_chunks,
#         "category": "SUMMARY",
#     }

#     state["meaningful_history"] = full_history + [history_entry]
#     # state["meaningful_messages"] = safe_get(state, "meaningful_messages", [])  + [history_entry]
#     state["meaningful_messages"] = (safe_get(state, "meaningful_messages", []) or []) + [history_entry]

#     return state