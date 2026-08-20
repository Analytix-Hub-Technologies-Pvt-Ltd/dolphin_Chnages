from __future__ import annotations

from typing import Any, Dict, List, Tuple
from loguru import logger

from graph.base_node import BaseNode
from services.openai_service import OpenAIService
from services.suggestion_service import SuggestionService


# ---------------------------------------------------------------------
# SAFE ACCESSOR
# ---------------------------------------------------------------------
def safe_get(state: Any, key: str, default=None):
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


def normalize_video_url(url: str) -> str:
    """
    Normalize video URL for consistent deduplication.
    
    - Converts to lowercase
    - Removes trailing slashes
    - Normalizes http/https (keeps https)
    - Removes common query parameters that don't affect video identity
    - Strips whitespace
    
    Args:
        url: Raw video URL string
        
    Returns:
        Normalized URL string for deduplication
    """
    if not url or not isinstance(url, str):
        return ""
    
    # Strip whitespace
    normalized = url.strip()
    
    if not normalized:
        return ""
    
    # Convert to lowercase
    normalized = normalized.lower()
    
    # Normalize http/https - prefer https
    if normalized.startswith("http://"):
        normalized = normalized.replace("http://", "https://", 1)
    elif not normalized.startswith("https://") and not normalized.startswith("//"):
        # Add https:// if no protocol
        if normalized.startswith("//"):
            normalized = "https:" + normalized
        elif "://" not in normalized:
            normalized = "https://" + normalized
    
    # Remove trailing slash
    normalized = normalized.rstrip("/")
    
    # Remove common query parameters that don't affect video identity
    # Keep video_id, id, v parameters as they might be important
    if "?" in normalized:
        base_url, query = normalized.split("?", 1)
        # Keep only important query params (video_id, id, v)
        important_params = []
        for param in query.split("&"):
            if param.split("=")[0].lower() in ["v", "id", "video_id", "videoid"]:
                important_params.append(param)
        if important_params:
            normalized = base_url + "?" + "&".join(important_params)
        else:
            normalized = base_url
    
    return normalized


# ---------------------------------------------------------------------
# ENTERPRISE-LEVEL SUMMARY PROMPT
# ---------------------------------------------------------------------
SUMMARY_PROMPT = """
You are Marine Tutor AI creating a PROFESSIONAL SESSION SUMMARY for a marine education platform.

**CRITICAL GROUNDING RULE:**
- You MUST ONLY summarize topics explicitly provided in the "CURRENT SESSION DATA" below
- DO NOT add topics, concepts, or information that are not in the session data
- DO NOT make assumptions or fill gaps with general knowledge
- Every topic, detail, and learning outcome MUST come directly from the session data provided

Your task is to produce a comprehensive, well-structured summary that would be suitable for:
- Corporate training records
- Progress tracking systems
- Knowledge base documentation
- Professional development portfolios


CURRENT SESSION DATA:
{topics_block}


OUTPUT REQUIREMENTS:


[ANSWER SECTION]
## Session Summary


**Session Metrics:**
- Topics Covered: {topic_count}
- Learning Areas: {learning_areas}


---


### Key Learning Outcomes


<List 3-5 specific skills or knowledge points the learner gained from this session>


---


### Topics Covered


#### 1. <Concise Topic Title (3-5 words)>
**Focus Area:** <One-line description>


<Detailed explanation of what was discussed, key points covered, and practical applications. 5-7 lines that synthesize the learning content.>


**Key Takeaways:**
- <Specific insight 1>
- <Specific insight 2>
- <Specific insight 3>


---


#### 2. <Concise Topic Title (3-5 words)>
**Focus Area:** <One-line description>


<Detailed explanation...>


**Key Takeaways:**
- <Specific insight 1>
- <Specific insight 2>
- <Specific insight 3>


---


### Topic Connections


<Brief paragraph explaining how the topics covered relate to each other and to broader marine operations concepts>


---


### Recommended Next Steps


<2-3 sentences suggesting logical next topics to explore based on what was learned>


[End of answer]


[SUGGESTIONS SECTION]
1. <Specific follow-up question directly referencing a topic from this session>?
2. <Question exploring practical application of concepts learned>?
3. <Question connecting topics to real-world maritime operations>?
4. <Question about advanced concepts related to session topics>?
5. <Question about regulatory/safety aspects of covered topics>?


FORMATTING RULES:
- Use professional, clear language
- Include specific details from the session
- Make it scannable with clear headings
- Provide actionable takeaways
- Connect topics to practical maritime operations
"""


# ---------------------------------------------------------------------
# UTILITY: DETECT SUGGESTION PATTERNS
# ---------------------------------------------------------------------
def is_suggestion_pattern(user_query: str) -> bool:
    """Check if user_query matches common suggestion/question patterns."""
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

    if "aid navigation" in query_lower and "how does" in query_lower:
        return True
    if "safe at sea" in query_lower and "what keeps" in query_lower:
        return True
    if "vital onboard" in query_lower and "why is" in query_lower:
        return True
    if "used afloat" in query_lower and "where is" in query_lower:
        return True
    if "underway" in query_lower and ("how to handle" in query_lower or "how to" in query_lower):
        return True

    return False


# ---------------------------------------------------------------------
# UTILITY: CHECK IF CHUNKS ARE SUBSTANTIAL
# ---------------------------------------------------------------------
def has_substantial_chunks(chunks: List[Dict[str, Any]]) -> bool:
    """Check if chunks contain actual course content, not just metadata."""
    if not chunks or len(chunks) == 0:
        return False

    content_keys = ["content", "topic_content", "summary", "text"]

    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue

        for key in content_keys:
            content = chunk.get(key, "")
            if content and isinstance(content, str):
                content = content.strip()
                if len(content) > 50:
                    return True

    return False


# ---------------------------------------------------------------------
# UTILITY: VALIDATE TOPIC FROM COURSE CONTENT
# ---------------------------------------------------------------------
def is_from_course_content(chunks: List[Dict[str, Any]], user_query: str) -> bool:
    """Validate that topics come from actual course content, not metadata."""
    if not has_substantial_chunks(chunks):
        return False

    content_keys = ["content", "topic_content", "summary", "text"]

    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue

        for key in content_keys:
            content = chunk.get(key, "")
            if content and isinstance(content, str):
                content = content.strip()
                if len(content) > 50:
                    if not content.startswith(("http://", "https://", "id:", "ID:")):
                        if any(c.isalpha() for c in content):
                            return True

    return False


# ---------------------------------------------------------------------
# SUMMARY NODE
# ---------------------------------------------------------------------
class SummaryNode(BaseNode):
    def __init__(self, openai_service: OpenAIService, suggestion_service: SuggestionService) -> None:
        super().__init__("summary")
        self.openai_service = openai_service
        self.suggestion_service = suggestion_service

    def _extract_chunk_titles(self, chunks: List[Dict[str, Any]]) -> List[str]:
        """Extract potential topic titles from chunks with multiple fallbacks."""
        titles: List[str] = []

        for chunk in chunks:
            for key in ("topic", "title", "section", "heading", "topic_name", "name"):
                val = (chunk.get(key) or "").strip()
                if val:
                    clean_val = val.replace("Topic Name:", "").replace("Topic:", "").strip()
                    titles.append(clean_val)
                    break

            if not titles or not titles[-1]:
                content = chunk.get("content", "") or chunk.get("topic_content", "") or ""
                if content:
                    first_line = content.split('\n')[0].strip()
                    if len(first_line) < 100:
                        titles.append(first_line)

        return titles

    def _topic_source_text(self, chunks: List[Dict[str, Any]], assistant_content: str, user_query: str) -> str:
        """Construct source text for a topic with better content extraction."""
        notes: List[str] = []

        if user_query and user_query.strip():
            notes.append(f"User Question: {user_query.strip()}")

        if assistant_content and isinstance(assistant_content, str) and assistant_content.strip():
            truncated_content = assistant_content[:500] + "..." if len(assistant_content) > 500 else assistant_content
            notes.append(f"AI Answer: {truncated_content.strip()}")

        for i, chunk in enumerate(chunks[:2]):
            content_keys = ["content", "topic_content", "summary", "text"]
            for key in content_keys:
                content = chunk.get(key, "")
                if content and isinstance(content, str) and content.strip():
                    clean_content = content.strip()
                    if len(clean_content) > 200:
                        clean_content = clean_content[:200] + "..."
                    notes.append(f"Background {i + 1}: {clean_content}")
                    break

        return "\n".join(notes)[:1200]

    def _build_topics(self, contexts: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Build topics from history contexts."""
        topics: List[Dict[str, str]] = []

        for idx, ctx in enumerate(contexts):
            chunks = ctx.get("chunks", [])
            user_query = ctx.get("user_query", "").strip()
            short_topic = ctx.get("short_topic", "").strip()

            logger.info(
                f"[SUMMARY] Building topic {idx + 1}: query='{user_query}', short_topic='{short_topic}', chunks={len(chunks)}")

            chunk_titles = self._extract_chunk_titles(chunks)

            raw_title = "Unknown Topic"

            if chunk_titles:
                raw_title = chunk_titles[0]
            elif short_topic:
                raw_title = short_topic
            elif user_query:
                raw_title = user_query
                question_words = ["what", "how", "why", "when", "where", "who", "which", "can", "could", "would",
                                  "should", "list", "tell", "explain", "describe"]
                words = raw_title.lower().split()
                if words and words[0] in question_words:
                    raw_title = ' '.join(words[1:]).capitalize()
                raw_title = raw_title.strip().rstrip("?.")

            raw_title = raw_title.strip().rstrip(".?")

            source = self._topic_source_text(
                chunks=chunks,
                assistant_content=ctx.get("content", ""),
                user_query=user_query,
            )

            topics.append({"title": raw_title, "source": source})

        return topics

    def _build_topics_with_metadata(self, contexts: List[Dict[str, Any]]) -> Tuple[
        List[Dict[str, str]], Dict[str, Any]]:
        """Build topics and extract session metadata."""
        topics = self._build_topics(contexts)

        metadata = {
            "topic_count": len(topics),
            "learning_areas": set(),
            "questions_asked": [],
            "timestamp_first": None,
            "timestamp_last": None,
        }

        for ctx in contexts:
            short_topic = ctx.get("short_topic", "")
            if short_topic:
                metadata["learning_areas"].add(short_topic)

            user_query = ctx.get("user_query", "")
            if user_query:
                metadata["questions_asked"].append(user_query)

            timestamp = ctx.get("timestamp", "")
            if timestamp:
                if not metadata["timestamp_first"]:
                    metadata["timestamp_first"] = timestamp
                metadata["timestamp_last"] = timestamp

        metadata["learning_areas"] = ", ".join(sorted(metadata["learning_areas"]))

        return topics, metadata

    def _dedupe_topics(self, topics: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Remove duplicate topics."""
        seen = set()
        unique: List[Dict[str, str]] = []
        for t in topics:
            key = t["title"].lower()
            if key not in seen:
                seen.add(key)
                unique.append(t)
                if len(unique) == 8:
                    break
        return unique

    def _build_topics_block(self, topics: List[Dict[str, str]]) -> str:
        """Build the topics block for LLM prompt."""
        if not topics:
            return "No prior marine topics were captured."

        parts: List[str] = []
        for idx, t in enumerate(topics, start=1):
            parts.append(f"Topic {idx}: {t['title']}\nNotes: {t['source']}")
        return "\n\n".join(parts)

    def _aggregate_media(
        self, 
        chunks: List[Dict[str, Any]], 
        score_threshold: float = 3.5,  # Increased from 2.0 to be more lenient with relevance filtering
        max_images: int = 8,
        max_pdfs: int = 5
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Aggregate and deduplicate media from chunks with relevance filtering and limits."""

        def is_junk_media(item: Dict[str, Any]) -> bool:
            """Identify likely junk media (icons, placeholders, etc.)."""
            title = str(item.get("title", item.get("Title", ""))).lower()
            url = str(item.get("url", item.get("videourl", item.get("Url", "")))).lower()
            
            junk_keywords = ["icon", "logo", "placeholder", "bullet", "marker", "arrow", "checkbox"]
            return any(kw in title or kw in url for kw in junk_keywords)

        def dedupe_and_limit(items: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
            seen_ids: set[str] = set()
            seen_urls: set[str] = set()
            output: List[Dict[str, Any]] = []
            
            # Sort by relevance first (lower score is better)
            sorted_items = sorted(
                items, 
                key=lambda x: float(x.get("_chunk_score", 999.0))
            )

            for item in sorted_items:
                if not isinstance(item, dict):
                    continue

                if is_junk_media(item):
                    continue

                # Check ID (case-insensitive)
                identifier = None
                for key in ("Id", "id", "ID", "video_id"):
                    if key in item and item[key] is not None:
                        identifier = str(item[key]).strip().lower()
                        break

                # Check URL and normalize
                raw_url = None
                for key in ("url", "videourl", "Url", "Link", "link", "href"):
                    if key in item and item[key]:
                        raw_url = str(item[key]).strip()
                        break
                
                normalized_url = normalize_video_url(raw_url) if raw_url else None

                # Check for duplicates using both ID and normalized URL
                if identifier and identifier in seen_ids:
                    continue
                if normalized_url and normalized_url in seen_urls:
                    continue
                
                # Skip items with no identifier or URL
                if not identifier and not normalized_url:
                    continue

                if identifier:
                    seen_ids.add(identifier)
                if normalized_url:
                    seen_urls.add(normalized_url)
                    
                output.append(item)
                if len(output) >= limit:
                    break

            return output

        all_videos: List[Dict[str, Any]] = []
        all_images: List[Dict[str, Any]] = []
        all_pdfs: List[Dict[str, Any]] = []

        for chunk in chunks:
            if not isinstance(chunk, dict):
                continue

            chunk_score = chunk.get("_score")
            # Skip chunks with low relevance
            if chunk_score is not None:
                try:
                    if float(chunk_score) > score_threshold:
                        continue
                except (TypeError, ValueError):
                    pass

            def attach_score(media_list):
                if not isinstance(media_list, list):
                    return []
                results = []
                for m in media_list:
                    if isinstance(m, dict):
                        m["_chunk_score"] = chunk_score
                        results.append(m)
                return results

            all_videos.extend(attach_score(chunk.get("videos", [])))
            all_images.extend(attach_score(chunk.get("images", [])))
            all_pdfs.extend(attach_score(chunk.get("pdfs", [])))

        return {
            "videos": dedupe_and_limit(all_videos, 15),
            "images": dedupe_and_limit(all_images, max_images),
            "pdfs": dedupe_and_limit(all_pdfs, max_pdfs),
        }

    def _format_video_suggestions_for_response(self, videos: List[Dict[str, Any]]) -> str:
        """Format video suggestions professionally for the response."""
        if not videos:
            return ""

        video_section = "\n\n### Recommended Video Resources\n\n"

        for i, video in enumerate(videos[:5], 1):
            title = video.get("title", video.get("Title", f"Course Video {i}"))
            url = video.get("url") or video.get("videourl") or video.get("Url", "#")

            video_section += f"**{i}. {title}**\n"
            video_section += f"   Related to topics covered in this session\n"
            video_section += f"   [Watch Video]({url})\n\n"

        return video_section

    def _extract_answer_and_suggestions(self, llm_response: str) -> Tuple[str, List[str]]:
        """Parse the LLM response into answer text and a list of suggestions."""
        answer_text = llm_response
        suggestions: List[str] = []

        suggestions_marker = "[SUGGESTIONS SECTION]"
        answer_marker = "[ANSWER SECTION]"

        if suggestions_marker in llm_response:
            parts = llm_response.split(suggestions_marker)
            if len(parts) == 2:
                suggestions_text = parts[1].strip()
                answer_part = parts[0]
                if answer_marker in answer_part:
                    answer_text = answer_part.split(answer_marker, 1)[1].strip()
                else:
                    answer_text = answer_part.strip()
                lines = suggestions_text.split("\n")
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    if line[0].isdigit() and len(line) > 2 and line[1] in ". )":
                        line = line[2:].strip()
                    elif line.startswith("- ") or line.startswith("* ") or line.startswith("• "):
                        line = line[2:].strip()
                    line = line.strip('"\'').strip()
                    if line and (line.endswith("?") or len(line.split()) >= 3):
                        suggestions.append(line)

        if not suggestions:
            fallback = [ln.strip() for ln in llm_response.split("\n") if ln.strip().endswith("?")]
            suggestions.extend(fallback)

        if not suggestions:
            suggestions = [
                "Which of these summary topics would you like to explore in more detail?",
                "How does effective communication on the bridge improve overall ship safety?",
                "What specific aspect of bridge resource management should we study next?",
            ]

        suggestions = suggestions[:5]
        logger.info(f"[SUMMARY] Extracted {len(suggestions)} suggestions from LLM response")
        return answer_text, suggestions

    def _generate_default_summary(self) -> str:
        """Generate a professional default summary when no topics found."""
        return """
## Session Summary


**Session Status:** No learning topics recorded yet


---


### Getting Started


This session is just beginning! I'm ready to help you learn about:


- **Navigation Systems:** RADAR, GPS, ECDIS, and chart work
- **Ship Handling:** Maneuvering, anchoring, and berthing operations  
- **Safety Management:** BRM, emergency procedures, and safety systems
- **Marine Engineering:** Propulsion, auxiliary systems, and maintenance
- **Cargo Operations:** Loading, securing, and dangerous goods handling
- **Maritime Regulations:** SOLAS, MARPOL, and port state control


---


### How to Use This Session


1. Ask specific questions about marine topics
2. Request explanations of concepts or procedures
3. Explore practical applications and real-world scenarios
4. Review safety protocols and regulatory requirements


When you're ready for a summary, I'll provide a comprehensive overview of everything we've covered!


---


### Recommended Starting Topics


- **For Navigation Officers:** Start with RADAR principles and collision avoidance
- **For Engineering Officers:** Explore propulsion systems and maintenance procedures
- **For Deck Officers:** Learn about cargo operations and securing techniques
- **For Safety Officers:** Review BRM principles and emergency response
"""

    def _extract_topic_count_from_query(self, query: str) -> int:
        """
        Extract the number of topics requested from user query.
        
        SMART DEFAULTS:
        - If user specifies a number: use that
        - If query says "all": return 999 (effectively unlimited)
        - If query says "recent/last": return 10
        - Default: return 0 (meaning "auto-detect based on session")
        
        Examples:
        - "summarize last 2 topics" -> 2
        - "give me summary of last 3" -> 3
        - "summary of all topics" -> 999
        - "summary" -> 0 (auto-detect)
        """
        import re
        
        if not query:
            return 0  # Auto-detect
        
        query_lower = query.lower()
        
        # Check for "all" keywords
        if any(keyword in query_lower for keyword in ["all topics", "all my", "everything", "entire session", "full summary"]):
            return 999  # Effectively unlimited
        
        # Patterns to match: "last N topics", "last N", "N topics", etc.
        patterns = [
            r'last\s+(\d+)\s+topics?',
            r'last\s+(\d+)',
            r'recent\s+(\d+)\s+topics?',
            r'previous\s+(\d+)\s+topics?',
            r'(\d+)\s+topics?',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query_lower)
            if match:
                try:
                    count = int(match.group(1))
                    if 1 <= count <= 50:  # Reasonable range (increased max)
                        logger.info(f"[SUMMARY] User requested last {count} topics")
                        return count
                except (ValueError, IndexError):
                    continue
        
        # Default: 0 means auto-detect based on session duration
        return 0

    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Main execution method for summary node - CORRECT SIGNATURE."""

        logger.info("=" * 80)
        logger.info("[SUMMARY] Starting enterprise-level summary generation")
        logger.info("=" * 80)

        decision = safe_get(state, "router_decision", {})
        full_history = safe_get(state, "meaningful_history", [])
        current_query = safe_get(state, "current_query", "")

        logger.info(f"[SUMMARY] Total history entries: {len(full_history)}")

        # ============================================================
        # INTELLIGENT TOPIC SELECTION: Auto-adapt based on context
        # ============================================================
        requested_topic_count = self._extract_topic_count_from_query(current_query)
        
        if requested_topic_count == 0:
            # AUTO-DETECT MODE: Smart defaults based on session characteristics
            # Count how many valid query/quiz entries exist in history
            potential_topics = sum(
                1 for entry in full_history 
                if isinstance(entry, dict) and 
                str(entry.get("node_type", "")).lower() in {"query", "quiz"}
            )
            
            # Adaptive logic:
            if potential_topics <= 5:
                # Short session: include everything
                MAX_TOPICS_IN_SUMMARY = 999
                logger.info(f"[SUMMARY] AUTO-DETECT: Short session ({potential_topics} topics), including ALL")
            elif potential_topics <= 15:
                # Medium session: include last 10
                MAX_TOPICS_IN_SUMMARY = 10
                logger.info(f"[SUMMARY] AUTO-DETECT: Medium session ({potential_topics} topics), limiting to last 10")
            else:
                # Long session: include last 15 (focus on recent learning)
                MAX_TOPICS_IN_SUMMARY = 15
                logger.info(f"[SUMMARY] AUTO-DETECT: Long session ({potential_topics} topics), limiting to last 15")
        else:
            # User explicitly requested a specific number
            MAX_TOPICS_IN_SUMMARY = requested_topic_count
            logger.info(f"[SUMMARY] USER REQUESTED: {MAX_TOPICS_IN_SUMMARY} topics")

        # Collect ONLY VALID query/quiz nodes with course content
        contexts: List[Dict[str, Any]] = []
        filtered_stats = {
            "suggestion": 0, 
            "no_chunks": 0, 
            "not_course": 0, 
            "fallback": 0,
            "error_response": 0
        }

        for entry in full_history:
            if not isinstance(entry, dict):
                continue

            node_type = str(entry.get("node_type") or entry.get("category") or "").lower()

            if node_type not in {"query", "quiz"}:
                continue

            user_query = entry.get("user_query", "").strip()
            chunks = entry.get("chunks", [])
            metadata = entry.get("metadata", {})

            # CRITICAL FILTER 1: Exclude fallback/error responses
            routing_reason = metadata.get("routing_reason", "")
            if routing_reason in [
                "no_retrieval", 
                "empty_chunks_content", 
                "no_retrieval_intelligent_fallback",
                "fallback"
            ]:
                filtered_stats["fallback"] += 1
                logger.info(f"[SUMMARY] FILTERED fallback response: '{user_query}' (reason: {routing_reason})")
                continue

            # CRITICAL FILTER 2: Check if content indicates error/fallback
            content = entry.get("content", "")
            if content and isinstance(content, str):
                error_indicators = [
                    "I am sorry, but I cannot find information",
                    "cannot find information regarding this specific topic",
                    "Please check if your query is related to the marine course material",
                    "outside your course content scope"
                ]
                if any(indicator in content for indicator in error_indicators):
                    filtered_stats["error_response"] += 1
                    logger.info(f"[SUMMARY] FILTERED error response: '{user_query}'")
                    continue

            # FILTER 3: Exclude suggestion patterns
            if is_suggestion_pattern(user_query):
                filtered_stats["suggestion"] += 1
                continue

            # FILTER 4: Require substantial chunks
            if not has_substantial_chunks(chunks):
                filtered_stats["no_chunks"] += 1
                logger.info(f"[SUMMARY] FILTERED no chunks: '{user_query}'")
                continue

            # FILTER 5: Validate course content
            if not is_from_course_content(chunks, user_query):
                filtered_stats["not_course"] += 1
                logger.info(f"[SUMMARY] FILTERED not from course: '{user_query}'")
                continue

            # ✅ Valid topic - add to contexts
            contexts.append({
                "node_type": node_type,
                "user_query": user_query,
                "short_topic": entry.get("short_topic", ""),
                "content": entry.get("content", ""),
                "chunks": chunks,
                "videos": entry.get("videos", []),
                "timestamp": entry.get("timestamp", ""),
            })

        # CRITICAL: Limit to last N topics only (most recent learning)
        total_valid_topics_found = len(contexts)  # Track total before limiting
        if len(contexts) > MAX_TOPICS_IN_SUMMARY:
            logger.info(f"[SUMMARY] Limiting from {len(contexts)} to last {MAX_TOPICS_IN_SUMMARY} topics")
            contexts = contexts[-MAX_TOPICS_IN_SUMMARY:]

        logger.info(f"[SUMMARY] Valid contexts: {len(contexts)}, Filtered: {filtered_stats}")

        # Handle no valid contexts
        if not contexts:
            # Check if we had history but it was all filtered
            had_queries = any(
                entry.get("node_type") in {"query", "quiz"} 
                for entry in full_history 
                if isinstance(entry, dict)
            )
            
            if had_queries:
                logger.warning(f"[SUMMARY] All {len(full_history)} queries filtered - no valid course content")
                default_summary = """## Session Summary

**Session Status:** No valid course topics found

---

### What Happened?

While you've been active in this session, the queries didn't retrieve valid course content that can be summarized. This can happen when:

- Questions were outside the course scope
- Queries didn't match available course materials
- Topics were suggestions rather than actual learning content

---

### Let's Get Back on Track!

I'm ready to help you learn about marine topics covered in our course:

- **Navigation Systems:** RADAR, GPS, ECDIS, and chart work
- **Ship Handling:** Maneuvering, anchoring, and berthing operations
- **Safety Management:** BRM, emergency procedures, and safety systems
- **Marine Engineering:** Propulsion, auxiliary systems, and maintenance
- **Cargo Operations:** Loading, securing, and dangerous goods handling
- **Maritime Regulations:** SOLAS, MARPOL, and port state control

Try asking specific questions about these topics to build a meaningful summary!
"""
            else:
                logger.warning("[SUMMARY] No queries in history - new session")
                default_summary = self._generate_default_summary()

            return {
                "router_decision": decision,
                "node_response": self._response_to_dict(self._build_response(
                    content=default_summary,
                    chunks_used=[],
                    video_suggestions=[],
                    question_suggestions=[
                        "What marine navigation topics would you like to explore?",
                        "Can you explain RADAR collision avoidance techniques?",
                        "What are the key principles of bridge resource management?",
                    ],
                    short_topic="Session Summary",
                    routing_reason="No valid topics found",
                    media={"videos": [], "images": [], "pdfs": []},
                )),
                "meaningful_history": full_history,
                "meaningful_messages": safe_get(state, "meaningful_messages", []),
                "last_user_category": "SUMMARY",
            }

        # Build topics with metadata
        topics, session_metadata = self._build_topics_with_metadata(contexts)
        topics = self._dedupe_topics(topics)

        logger.info(f"[SUMMARY] Final topics: {len(topics)}")

        # Merge all chunks
        merged_chunks = []
        for ctx in contexts:
            merged_chunks.extend(ctx.get("chunks", []))

        # Build topics block
        topics_block = self._build_topics_block(topics)

        # Format prompt with metadata
        prompt = SUMMARY_PROMPT.format(
            topics_block=topics_block,
            topic_count=session_metadata["topic_count"],
            learning_areas=session_metadata["learning_areas"],
        )

        logger.info("[SUMMARY] Calling LLM...")

        # Call LLM
        llm_response = await self.openai_service.chat(
            [{"role": "user", "content": prompt}],
            temperature=0,
            category="SUMMARY",
        )

        # Extract answer and suggestions
        answer, dynamic_suggestions = self._extract_answer_and_suggestions(llm_response)
        

        # Add note if user requested specific number and we limited the summary
        if total_valid_topics_found > len(contexts):
            topic_note = f"\n\n---\n\n**Note:** This summary focuses on your **{len(contexts)} most recent topics** as requested. ({total_valid_topics_found} total topics were discussed in this session.)\n"
            answer = answer + topic_note

        # Aggregate media
        media_bundle = self._aggregate_media(merged_chunks)
        video_suggestions = media_bundle.get("videos", [])

        # Format video section professionally
        video_section = self._format_video_suggestions_for_response(video_suggestions)

        # Append video section to answer
        if video_section:
            answer = answer + video_section

        # Build response
        response = self._build_response(
            content=answer,
            chunks_used=merged_chunks,
            video_suggestions=video_suggestions,
            question_suggestions=dynamic_suggestions,
            short_topic=decision.get("short_topic", "Session Summary"),
            routing_reason=decision.get("reason", "summary"),
            media=media_bundle,
        )

        response_dict = self._response_to_dict(response)

        # Create history entry
        history_entry = {
            "node_type": self.node_type,
            "content": answer,
            "short_topic": decision.get("short_topic", "Session Summary"),
            "user_query": safe_get(state, "current_query", ""),
            "chunks": merged_chunks,
            "metadata": {
                **response.get("metadata", {}),
                "session_metadata": session_metadata,
            },
            "category": decision.get("category", "summary"),
        }

        updated_history = list(full_history) + [history_entry]

        logger.info("[SUMMARY] Enterprise summary complete")
        logger.info("=" * 80)

        return {
            "router_decision": decision,
            "node_response": response_dict,
            "meaningful_history": updated_history,
            "meaningful_messages": safe_get(state, "meaningful_messages", []) + [history_entry],
            "last_user_category": "SUMMARY",
        }


