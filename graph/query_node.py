from __future__ import annotations

import asyncio
import re
from typing import Any, Dict, List, Tuple
from loguru import logger
from graph.base_node import BaseNode
from graph.history_utils import extract_clean_history
from services.openai_service import OpenAIService
from services.suggestion_service import SuggestionService
from services.fuzzy_search_service import FuzzySearchService
from services.acronym_disambiguation_service import AcronymDisambiguationService
from services.conversation_context_service import ConversationContextService


def safe_get(state: Any, key: str, default=None):
    """Allow dict or GraphState safely."""
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


QUERY_PROMPT = """
You are Marine Tutor AI answering marine education questions. You are an Internal Course Assistant. Your sole knowledge source is the provided "COURSE CONTEXT" below. You are PROHIBITED from using external knowledge or the internet.

CURRENT USER QUESTION:
{user_query}

COURSE CONTEXT:
{chunks_content}

CRITICAL GROUNDING RULES:
1. **STRICT GROUNDING - ZERO HALLUCINATION**: Answer ONLY using information explicitly present in the "COURSE CONTEXT" above.
   - Every fact, detail, and explanation MUST come from the provided course content.
   - If information is not in the COURSE CONTEXT, it does not exist for you.
   - DO NOT use any knowledge from training data, general knowledge, or external sources.
   - DO NOT infer, assume, or make up information even if it seems logical or common knowledge.
   - For conversational queries (e.g., "Hey, I need advice about..."), extract the core topic and answer ONLY from COURSE CONTEXT.

2. **EMPTY CONTEXT HANDLING**: 
   - If the "COURSE CONTEXT" section is empty or contains no relevant information, you MUST refuse to answer.
   - Politely explain that this specific topic isn't covered in the course material.
   - Suggest they explore related maritime topics or ask about content that IS in the course.
   - Be warm, helpful, and encouraging (not robotic or repetitive).
   - VARY your response each time - don't use the same phrasing repeatedly.
   - NEVER make up procedures, protocols, or advice that isn't in the COURSE CONTEXT.

3. **PARTIAL CONTEXT HANDLING**:
   - If the COURSE CONTEXT contains some information but not enough to fully answer the question, state what you can answer from the context and explicitly note what information is missing.
   - DO NOT fill gaps with assumptions or general knowledge.
   - DO NOT provide generic advice or standard procedures unless they are explicitly in the COURSE CONTEXT.

4. **COMPREHENSIVE ANSWER** (when context is sufficient):
   - Provide a detailed markdown explanation (50–60 lines) using ONLY information from the COURSE CONTEXT.
   - Use headings, bold, italics for structure.
   - Cite specific details from the context to support your answer.

5. **MEDIA-ONLY TOPICS**:
   - If the COURSE CONTEXT contains minimal text BUT media (videos/images/PDFs) are provided:
     * Acknowledge the topic exists in the course
     * Explain it's primarily covered through visual/video content
     * Direct attention to the media below with enthusiasm
     * Example: "This topic is thoroughly covered through our multimedia resources! Please watch the videos and review the images below for comprehensive information on [topic name]. The visual content provides detailed demonstrations and explanations."
   - DO NOT say "content not provided" when media exists
   - DO NOT generate definitions from outside knowledge

6. **SUGGESTIONS**: Generate 3-5 relevant follow-up questions based on the COURSE CONTEXT provided above.
   - Focus on concepts, principles, and topics that ARE mentioned in the COURSE CONTEXT
   - Ask about details, applications, or examples that are discussed in the content
   - If context is limited, suggest questions about what IS covered rather than what's missing
   - Prioritize depth over breadth - dig deeper into topics that are present in the context
   - Example: If context covers "fire prevention procedures", suggest "What are the key steps in fire prevention?" rather than "What marine species are resilient?"

RESPONSE FORMAT:
Your response MUST be structured as follows:

[ANSWER SECTION]
<Your detailed answer here in markdown format, using ONLY information from COURSE CONTEXT>

[SUGGESTIONS SECTION]
1. First follow-up question exploring concepts mentioned in the content above?
2. Second follow-up question about applications discussed in the content?
3. Third question about practical aspects covered in the context?
4. Fourth question diving deeper into topics from the content?
5. Fifth question about related concepts that were introduced above?

Note: Base your suggestions on topics and information present in the COURSE CONTEXT above.

ABSOLUTE PROHIBITIONS:
- NEVER mention that you are an AI.
- NEVER use external knowledge, training data, or general knowledge.
- DO NOT hallucinate, invent, or assume information not in COURSE CONTEXT.
- DO NOT make up facts, figures, or details.
- DO NOT provide generic advice, standard procedures, or common knowledge unless explicitly in COURSE CONTEXT.
- DO NOT infer or extrapolate beyond what is explicitly stated in COURSE CONTEXT.
- For workplace safety queries (harassment, bullying, intoxication), answer ONLY if relevant content exists in COURSE CONTEXT.
- If the context is irrelevant to the question, REFUSE to answer.
- If you cannot answer from the context, explicitly state so and suggest related topics that ARE in the course.

Generate your response using ONLY the COURSE CONTEXT provided above:
"""


RELEVANCE_CLASSIFIER_PROMPT = """
Classify the following user query into one of these categories:

Categories:
- IN_SCOPE: Query is about marine/maritime education, ship operations, navigation, safety, regulations, etc.
- PERSONAL_INFO: User is introducing themselves (name, role, ship, experience)
- MEMORY_RECALL: User is asking what you know/remember about them
- TANGENTIALLY_RELATED: Query is loosely related to maritime but not covered in course material
- UNRELATED: Query is completely off-topic (weather, sports, general chitchat, etc.)

User Query: "{user_query}"

Respond with ONLY: CLASSIFICATION | brief reason

Examples:
"What are the main navigation systems?" → IN_SCOPE | maritime navigation topic
"SEEMP" → IN_SCOPE | maritime acronym/topic
"MARPOL" → IN_SCOPE | maritime regulation
"SOLAS" → IN_SCOPE | maritime safety convention
"ISM Code" → IN_SCOPE | maritime management system
"COLREG" → IN_SCOPE | maritime regulation
"STCW" → IN_SCOPE | maritime training standards
"My name is John" → PERSONAL_INFO | user introduction
"What do you know about me?" → MEMORY_RECALL | asking for stored info
"What's the weather today?" → UNRELATED | general question
"Tell me about thermal emissions" → TANGENTIALLY_RELATED | maritime adjacent

Note: Single-word maritime acronyms and technical terms should be classified as IN_SCOPE.
"""


INTELLIGENT_FALLBACK_PROMPT = """
You are Marine Tutor AI, a helpful maritime education assistant. A user asked about a topic that wasn't found in your course material.

User Query: "{user_query}"
{user_context}

{fuzzy_match_info}

Task: Generate a UNIQUE, friendly, contextual response that:
1. Acknowledges their question warmly (VARY your opening - don't repeat the same phrase)
2. {personalized_tone}
3. If fuzzy matches were found, ask if they meant one of those topics
4. If no fuzzy matches, explain this specific topic isn't in your course material
5. Encourage them to explore maritime topics you DO cover
6. Suggest 3-5 specific, relevant maritime questions they could ask (numbered list, each ending with '?')

CRITICAL: 
- DO NOT use robotic, repetitive phrases like "I am sorry, but I cannot find..."
- VARY your language and tone each time (be creative, warm, engaging)
- Make it conversational and helpful, not formulaic
- Show genuine interest in helping them learn

Examples of GOOD varied openings:
- "Great question about {user_query}! I don't have that specific content in my course materials, but..."
- "I'd love to help with {user_query}, but that topic isn't covered in my current database. However..."
- "Thanks for asking about {user_query}! While I don't have dedicated material on that, I can help with..."
- "Interesting question! {user_query} isn't in my course content yet, but I have lots of material on..."

Keep the tone warm, professional, and VARIED. Never sound repetitive or robotic.
"""


CONVERSATIONAL_MEMORY_PROMPT = """
Extract personal information from this user message:

User Message: "{user_message}"

Extract if present:
- Name
- Role/Position (Captain, Engineer, Officer, etc.)
- Ship/Vessel name
- Experience level or years

Respond in this exact format:
NAME: [name or NONE]
ROLE: [role or NONE]  
SHIP: [ship or NONE]
EXPERIENCE: [experience or NONE]

If nothing is present, respond with all NONE values.
"""


class QueryNode(BaseNode):
    def __init__(self, openai_service: OpenAIService, suggestion_service: SuggestionService, vector_store=None) -> None:
        super().__init__("query")
        self.openai_service = openai_service
        self.suggestion_service = suggestion_service
        
        # Initialize fuzzy search with vector store for generic topic matching
        self.fuzzy_search = FuzzySearchService(vector_store=vector_store)
        
        # Initialize acronym disambiguation service
        self.acronym_disambiguator = AcronymDisambiguationService(vector_store=vector_store)
        
        # Initialize conversation context service for response variation
        self.conversation_context = ConversationContextService(similarity_threshold=0.65)
        
        # Load topics from database for fuzzy matching and acronym detection
        if vector_store:
            try:
                topic_count = self.fuzzy_search.load_topics_from_database()
                acronym_count = self.acronym_disambiguator.load_acronyms_from_database()
                logger.info(
                    f"QueryNode initialized: {topic_count} topics, {acronym_count} acronyms loaded, "
                    f"conversation context enabled"
                )
            except Exception as e:
                logger.warning(f"QueryNode: Failed to load database data: {e}")
                logger.info("QueryNode initialized with services (fallback mode)")
        else:
            logger.info("QueryNode initialized with services (no vector store, fallback mode)")

    def _collect_chunk_keywords(self, chunks: List[Dict[str, Any]]) -> List[str]:
        keywords: List[str] = []
        for chunk in chunks:
            for key in ("keywords", "topic_name"):
                val = chunk.get(key)
                if isinstance(val, list):
                    keywords.extend([str(v) for v in val if str(v).strip()])
                elif val:
                    keywords.append(str(val))
        return keywords
    
    def _filter_chunks_by_acronym(self, query: str, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter chunks to ensure query acronym is actually present in content.
        
        CRITICAL FIX FOR: EEDI returning EEBD content
        
        For acronym queries (short, uppercase, single words), verify the exact
        acronym exists in the chunk content before returning it. This prevents
        vector similarity confusion between similar acronyms.
        
        Args:
            query: User's search query
            chunks: Retrieved chunks from vector search
            
        Returns:
            Filtered chunks containing the actual query term (or original if not acronym)
        """
        query_clean = query.strip().upper()
        
        # Check if query is a pure acronym (2-6 uppercase letters, no spaces)
        if not (2 <= len(query_clean) <= 6 and query_clean.isalpha() and query_clean.isupper()):
            # Not an acronym query - return all chunks as-is
            return chunks
        
        # For acronym queries, filter chunks to ensure exact match
        # PRIORITY: If acronym is in topic_name, keep the chunk (high confidence)
        filtered_chunks = []
        import re
        for chunk in chunks:
            # Check topic_name FIRST - strong signal of relevance
            topic_name = chunk.get('topic_name', '')
            if topic_name and isinstance(topic_name, str):
                pattern = r'\b' + re.escape(query_clean) + r'\b'
                if re.search(pattern, topic_name.upper()):
                    filtered_chunks.append(chunk)
                    continue  # Skip content check
            
            # Check content fields as fallback
            content_fields = [
                chunk.get('content', ''),
                chunk.get('topic_content', ''),
                chunk.get('summary', ''),
            ]
            
            # Check if acronym appears in any content field
            found = False
            for content in content_fields:
                if content and isinstance(content, str):
                    pattern = r'\b' + re.escape(query_clean) + r'\b'
                    if re.search(pattern, content.upper()):
                        found = True
                        break
            
            if found:
                filtered_chunks.append(chunk)
        
        # Log filtering results
        if len(filtered_chunks) != len(chunks):
            removed = len(chunks) - len(filtered_chunks)
            logger.info(
                f"[ACRONYM FILTER] Query '{query_clean}': {len(chunks)} → {len(filtered_chunks)} chunks "
                f"({removed} removed due to missing acronym)"
            )
            
            # Log which topics were removed
            removed_topics = [
                c.get('topic_name', 'Unknown')[:50] 
                for c in chunks 
                if c not in filtered_chunks
            ]
            if removed_topics:
                logger.info(f"[ACRONYM FILTER] Removed topics: {removed_topics}")
        
        # Only return filtered results if we found matches
        # If no matches, fall back to original (let disambiguation handle it)
        return filtered_chunks if filtered_chunks else chunks

    def _last_short_topic(self, history: List[Dict[str, Any]], decision: Dict[str, Any]) -> str:
        for entry in reversed(history):
            topic = entry.get("short_topic") or ""
            if topic:
                return topic
        return decision.get("short_topic", "marine topic")

    def _aggregate_media(
        self, 
        chunks: List[Dict[str, Any]], 
        max_videos: int = 15,
        max_images: int = 8,
        max_pdfs: int = 5,
        score_threshold: float = 3.5  # For content filtering (not used for video extraction)
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Aggregate media from chunks with relevance filtering and limits.
        
        IMPORTANT: Uses more lenient threshold (5.0) for video extraction vs content filtering (3.5).
        This ensures we don't lose relevant videos from chunks that are slightly above content threshold.
        """
        
        def is_junk_media(item: Dict[str, Any]) -> bool:
            """Identify likely junk media (icons, placeholders, etc.)."""
            title = str(item.get("title", item.get("Title", ""))).lower()
            url = str(item.get("url", item.get("videourl", item.get("Url", "")))).lower()
            
            junk_keywords = ["icon", "logo", "placeholder", "bullet", "marker", "arrow", "checkbox"]
            return any(kw in title or kw in url for kw in junk_keywords)

        def dedupe(items: List[Dict[str, Any]], limit: int = 99) -> List[Dict[str, Any]]:
                seen_ids: set[str] = set()
                seen_urls: set[str] = set()
                seen_titles: set[str] = set()  # Add title-based deduplication
                output: List[Dict[str, Any]] = []
                for item in items:
                    if not isinstance(item, dict):
                        continue

                    if is_junk_media(item):
                        continue

                    extract = lambda keys, d: next((d[k] for k in keys if k in d), "")
                    
                    # Try ID-based deduplication first (case-insensitive)
                    identifier = str(extract(["Id", "id", "ID", "video_id"], item)).strip().lower()
                    if identifier and identifier in seen_ids:
                        continue
                    
                    # Also check URL-based deduplication with normalization
                    raw_url = str(extract(["url", "videourl", "Url", "videolink", "Link"], item)).strip()
                    normalized_url = normalize_video_url(raw_url)
                    if normalized_url and normalized_url in seen_urls:
                        continue
                    
                    # Fallback: check by title (normalized, case-insensitive)
                    # Prioritize Title over About, clean HTML if About is used
                    title_raw = extract(["Title", "title"], item)
                    if not title_raw:
                        title_raw = extract(["About"], item)
                        if title_raw:
                            # Strip HTML tags from About if used as fallback
                            title_raw = re.sub(r'<[^>]+>', '', str(title_raw))
                    title = str(title_raw).strip() if title_raw else ""
                    normalized_title = title.lower().strip() if title else ""
                    if normalized_title and normalized_title in seen_titles:
                        continue
                    
                    # Skip items with no identifier, URL, or title
                    if not identifier and not normalized_url and not normalized_title:
                        continue

                    if identifier:
                        seen_ids.add(identifier)
                    if normalized_url:
                        seen_urls.add(normalized_url)
                    if normalized_title:
                        seen_titles.add(normalized_title)
                    
                    output.append(item)
                    if len(output) >= limit:
                        break

                return output

        # Chunks are already filtered by score_threshold (3.5) at retrieval stage
        # Videos inherit relevance from their parent chunks - no additional filtering needed

        all_videos: List[Dict[str, Any]] = []
        all_images: List[Dict[str, Any]] = []
        all_pdfs: List[Dict[str, Any]] = []

        # Extract media from ALL chunks (already relevance-filtered at chunk level)
        for chunk in chunks:
            if not isinstance(chunk, dict):
                continue
                
            chunk_score = chunk.get("_score")
            chunk_rank = chunk.get("_rank")
            
            videos = chunk.get("videos") or []
            images = chunk.get("images") or []
            pdfs = chunk.get("pdfs") or []

            # Extract media and attach relevance info
            if isinstance(videos, list):
                for video in videos:
                    if isinstance(video, dict):
                        video["_chunk_score"] = chunk_score
                        video["_chunk_rank"] = chunk_rank
                        all_videos.append(video)
            
            if isinstance(images, list):
                for img in images:
                    if isinstance(img, dict):
                        img["_chunk_score"] = chunk_score
                        all_images.append(img)
                        
            if isinstance(pdfs, list):
                for pdf in pdfs:
                    if isinstance(pdf, dict):
                        pdf["_chunk_score"] = chunk_score
                        all_pdfs.append(pdf)

        # Sort all media by relevance (lower score = higher relevance)
        def get_sort_key(item: Dict[str, Any]) -> float:
            score = item.get("_chunk_score")
            return float(score) if score is not None else 999.0
        
        all_videos.sort(key=get_sort_key)
        all_images.sort(key=get_sort_key)
        all_pdfs.sort(key=get_sort_key)
        
        # Apply deduplication and limit to max counts (no score-based filtering)
        filtered_videos = dedupe(all_videos, max_videos)
        filtered_images = dedupe(all_images, max_images)
        filtered_pdfs = dedupe(all_pdfs, max_pdfs)
        
        logger.info(
            f"[QUERY] Aggregated media: v={len(filtered_videos)}, i={len(filtered_images)}, p={len(filtered_pdfs)} "
            f"from {len(chunks)} chunks"
        )

        return {
            "videos": filtered_videos,
            "images": filtered_images,
            "pdfs": filtered_pdfs,
        }

    def _format_chunk_for_prompt(self, chunk: Dict[str, Any]) -> str:
        """Represent a chunk in a prompt-friendly format using text only.
        
        Extracts content from multiple possible fields to ensure course content
        reaches the LLM. Media (videos/images/pdfs) are excluded to avoid
        inflating token usage and keep reasoning text-only.
        
        Individual chunks are truncated to 8000 characters to prevent single
        massive chunks from consuming all context.
        """
        if not isinstance(chunk, dict):
            return ""
        
        # Try multiple content fields in priority order
        content_fields = [
            "content",           # Primary content field
            "topic_content",     # Topic-specific content
            "summary",           # Summary field
            "text",              # Generic text field
        ]
        
        for field in content_fields:
            content = chunk.get(field)
            if content and isinstance(content, str):
                content = content.strip()
                if content:  # Ensure non-empty
                    # Truncate very long individual chunks (8000 chars ≈ 2000 tokens)
                    if len(content) > 8000:
                        logger.warning(f"[QUERY NODE] Truncating chunk content from {len(content)} to 8000 chars")
                        content = content[:8000] + "..."
                    return content
        
        # Fallback: try to construct from topic_name if available
        topic_name = chunk.get("topic_name", "").strip()
        if topic_name:
            return f"Topic: {topic_name}"
        
        return ""

    def _extract_answer_and_suggestions(self, llm_response: str, chunks: List[Dict[str, Any]] = None) -> Tuple[str, List[str]]:
        """
        Extract answer and suggestions from a single LLM response.
        Returns: (answer_text, list_of_suggestions)
        
        Args:
            llm_response: The LLM response text
            chunks: Optional chunks to generate fallback suggestions from if LLM didn't provide any
        """
        # Initialize defaults
        answer_text = llm_response
        suggestions = []

        # Try to find the SUGGESTIONS SECTION marker
        suggestions_marker = "[SUGGESTIONS SECTION]"
        answer_marker = "[ANSWER SECTION]"

        if suggestions_marker in llm_response:
            # Split the response into answer and suggestions parts
            parts = llm_response.split(suggestions_marker)
            if len(parts) == 2:
                # Extract suggestions part
                suggestions_text = parts[1].strip()

                # The answer part might have the ANSWER SECTION marker or not
                answer_part = parts[0]
                if answer_marker in answer_part:
                    # Remove the ANSWER SECTION marker
                    answer_text = answer_part.split(answer_marker, 1)[1].strip()
                else:
                    answer_text = answer_part.strip()

                # Parse suggestions
                lines = suggestions_text.split('\n')
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue

                    # Remove numbering (1., 2., etc.) or bullets (-, *, •)
                    if line[0].isdigit() and len(line) > 2 and line[1] in '. )':
                        line = line[2:].strip()
                    elif line.startswith('- ') or line.startswith('* ') or line.startswith('• '):
                        line = line[2:].strip()

                    # Clean up the line
                    line = line.strip('"\'').strip()

                    # Only add if it looks like a question
                    if line and (line.endswith('?') or len(line.split()) >= 3):
                        suggestions.append(line)

        # If we couldn't find suggestions or they're empty, generate from chunks
        if not suggestions and chunks:
            logger.info("[QUERY] LLM didn't provide suggestions, generating from chunks")
            suggestions = self._generate_chunk_based_suggestions(chunks)
        
        # Ultimate fallback if no chunks or chunk extraction failed
        if not suggestions:
            logger.warning("[QUERY] No suggestions from LLM or chunks, using generic fallback")
            suggestions = [
                "What are the key maritime procedures covered in this topic?",
                "How does this apply to ship operations?",
                "What safety considerations are important for this?"
            ]

        # Ensure we have 3-5 suggestions
        suggestions = suggestions[:5] if len(suggestions) > 5 else suggestions[:3]

        # Log for debugging
        logger.info(f"[QUERY] Extracted {len(suggestions)} suggestions from LLM response")

        return answer_text, suggestions
    
    def _generate_chunk_based_suggestions(self, chunks: List[Dict[str, Any]]) -> List[str]:
        """
        Generate suggestions from chunk content when LLM fails to provide them.
        Extracts topic names and creates questions about them.
        """
        suggestions = []
        seen_topics = set()
        
        for chunk in chunks[:5]:  # Look at top 5 chunks
            topic_name = chunk.get("topic_name", "").strip()
            if not topic_name or topic_name.lower() in seen_topics:
                continue
            
            seen_topics.add(topic_name.lower())
            
            # Generate questions based on topic name
            # Clean CamelCase or underscore-separated names
            topic_clean = topic_name.replace("_", " ").replace("-", " ")
            # Add spaces before capitals in CamelCase
            topic_clean = re.sub(r'([a-z])([A-Z])', r'\1 \2', topic_clean)
            
            # Create varied question types
            if len(suggestions) == 0:
                suggestions.append(f"What are the key aspects of {topic_clean.lower()}?")
            elif len(suggestions) == 1:
                suggestions.append(f"How is {topic_clean.lower()} applied in maritime operations?")
            elif len(suggestions) == 2:
                suggestions.append(f"What procedures are involved in {topic_clean.lower()}?")
            
            if len(suggestions) >= 3:
                break
        
        return suggestions

    async def _classify_query_relevance(self, user_query: str) -> Tuple[str, str]:
        """Classify if query is in scope, personal info, memory recall, or unrelated."""
        prompt = RELEVANCE_CLASSIFIER_PROMPT.format(user_query=user_query)
        
        try:
            response = await self.openai_service.chat(
                [{"role": "user", "content": prompt}],
                temperature=0,
                category="CLASSIFICATION",
            )
            
            # Parse response: "CLASSIFICATION | reason"
            parts = response.strip().split("|")
            classification = parts[0].strip()
            reason = parts[1].strip() if len(parts) > 1 else "unknown"
            return classification, reason
        except Exception as e:
            logger.warning(f"[QUERY] Failed to parse relevance classification: {e}")
            return "UNRELATED", "parse error"

    async def _generate_intelligent_fallback(
        self, 
        user_query: str, 
        user_context: str = ""
    ) -> Tuple[str, List[str]]:
        """Generate contextual, helpful response for out-of-scope queries with fuzzy matching."""
        
        # Try fuzzy matching first
        fuzzy_result = self.fuzzy_search.suggest_corrections(user_query)
        
        # Build fuzzy match info for prompt
        fuzzy_match_info = ""
        if fuzzy_result["has_suggestions"]:
            suggestions_text = "\n".join([
                f"- {s['term']}: {s['description']} (confidence: {s['confidence']:.0%})"
                for s in fuzzy_result["suggestions"]
            ])
            fuzzy_match_info = f"\nFUZZY MATCH SUGGESTIONS FOUND:\n{suggestions_text}\n\nUser likely made a typo or used incomplete term. Ask if they meant one of these."
        else:
            fuzzy_match_info = "\nNo similar maritime terms found in the database."
        
        personalized_tone = "Use their name if known" if user_context else "Use general professional tone"
        
        prompt = INTELLIGENT_FALLBACK_PROMPT.format(
            user_query=user_query,
            user_context=user_context,
            fuzzy_match_info=fuzzy_match_info,
            personalized_tone=personalized_tone
        )
        
        response = await self.openai_service.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.7,
            category="FALLBACK",
        )
        
        # Extract suggestions
        suggestions = []
        for line in response.split("\n"):
            line = line.strip()
            if line.endswith("?"):
                clean_line = line
                if line and (line[0].isdigit() or line.startswith(("- ", "* ", "• "))):
                    clean_line = line.lstrip("0123456789.-*• ").strip()
                if clean_line:
                    suggestions.append(clean_line)
        
        # If fuzzy matches found, prepend them as suggestions
        if fuzzy_result["has_suggestions"]:
            fuzzy_suggestions = [
                f"Did you mean {s['term']}?" 
                for s in fuzzy_result["suggestions"][:2]
            ]
            suggestions = fuzzy_suggestions + suggestions
        
        # Fallback suggestions
        if not suggestions or len(suggestions) < 3:
            default_suggestions = [
                "What are the main navigation systems used on modern ships?",
                "Can you explain bridge resource management principles?",
                "What safety procedures are critical for cargo operations?",
            ]
            suggestions = suggestions + default_suggestions
        
        suggestions = suggestions[:5]
        
        logger.info(f"[FALLBACK] Generated intelligent response with {len(suggestions)} suggestions (fuzzy: {fuzzy_result['has_suggestions']})")
        
        return response, suggestions

    async def _extract_personal_info(self, user_message: str) -> Dict[str, str]:
        """Extract personal information from user message."""
        prompt = CONVERSATIONAL_MEMORY_PROMPT.format(user_message=user_message)
        
        try:
            response = await self.openai_service.chat(
                [{"role": "user", "content": prompt}],
                temperature=0,
                category="MEMORY_EXTRACTION",
            )
            
            info = {}
            for line in response.strip().split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip().lower()
                    value = value.strip()
                    if value and value != "NONE":
                        info[key] = value
            
            return info
        except Exception as e:
            logger.warning(f"[QUERY] Failed to extract personal info: {e}")
            return {}

    def _handle_memory_recall(self, user_memory: Dict[str, str]) -> str:
        """Generate response for memory recall queries."""
        if not user_memory:
            return "I don't have any information stored about you yet. Feel free to introduce yourself!"
        
        parts = []
        if "name" in user_memory:
            parts.append(f"your name is {user_memory['name']}")
        if "role" in user_memory:
            parts.append(f"you work as a {user_memory['role']}")
        if "ship" in user_memory:
            parts.append(f"you're on the {user_memory['ship']}")
        if "experience" in user_memory:
            parts.append(f"you have {user_memory['experience']} of experience")
        
        if parts:
            return f"Based on what you've told me, {', '.join(parts)}. How can I help you with your maritime education today?"
        else:
            return "I have some basic information about you. What would you like to know about your maritime courses?"

    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        decision = safe_get(state, "router_decision", {})
        chunks: List[Dict[str, Any]] = safe_get(state, "retrieval_chunks", [])
        
        # Get query early (needed for filtering)
        query = safe_get(state, "current_query", "")
        standalone_query = safe_get(state, "standalone_query", query) or query
        
        
        # CRITICAL FIX: Filter chunks for acronym queries (EEDI vs EEBD confusion)
        # Apply BEFORE any other processing to ensure we work with correct content
        original_chunk_count = len(chunks)
        chunks = self._filter_chunks_by_acronym(standalone_query, chunks)
        if len(chunks) != original_chunk_count:
            logger.info(f"[QUERY] Acronym filtering: {original_chunk_count} → {len(chunks)} chunks")
        
        # Get chat history from messages
        chat_history = extract_clean_history(state)

        # CRITICAL: Get existing meaningful history from state
        existing_meaningful_history: List[Dict[str, Any]] = list(safe_get(state, "meaningful_history", []))
        existing_meaningful_messages: List[Dict[str, Any]] = list(safe_get(state, "meaningful_messages", []))

        # Get or initialize user memory
        user_memory: Dict[str, str] = safe_get(state, "user_memory", {})
        if not user_memory:
            user_memory = {}
        
        # ⚡ OPTIMIZATION: Run classification and personal info extraction in PARALLEL
        # These are independent LLM calls (~3-5s each sequentially → ~3-5s in parallel)
        # Also: personal info extraction is CONDITIONAL (only on first msg or intro-like queries)
        needs_personal_info = (
            not user_memory  # First message (no memory yet)
            or any(kw in query.lower() for kw in ["my name", "i am", "i'm", "this is", "call me"])
        )
        
        if needs_personal_info:
            # Run both in parallel with asyncio.gather
            classification_task = self._classify_query_relevance(query)
            personal_info_task = self._extract_personal_info(query)
            (classification, reason), personal_info = await asyncio.gather(
                classification_task, personal_info_task
            )
            if personal_info:
                user_memory.update(personal_info)
                logger.info(f"[QUERY] Updated user memory: {user_memory}")
        else:
            # Skip personal info extraction entirely (~3-5s saved)
            classification, reason = await self._classify_query_relevance(query)
            logger.info(f"[QUERY] ⚡ Skipped personal info extraction (memory exists, no intro detected)")
        
        logger.info(f"[QUERY] Classification: {classification} | Reason: {reason}")
        
        # GENERIC FIX: Trust retrieval over classification
        # If FAISS found ANY chunks, the content exists - classification is secondary
        if len(chunks) > 0:
            # Log original classification but override if marked as unrelated
            if classification in ["UNRELATED", "TANGENTIALLY_RELATED"]:
                logger.info(
                    f"[QUERY] OVERRIDE: {len(chunks)} chunks found in database. "
                    f"Ignoring classification '{classification}' - content exists, therefore IN_SCOPE."
                )
                classification = "IN_SCOPE"
            
            # Additional check: if chunks have reasonable scores, definitely override
            confidence_threshold = 2.0  # More lenient threshold
            has_good_chunks = any(
                c.get("_score") is not None and float(c.get("_score")) < confidence_threshold 
                for c in chunks
            )
            if has_good_chunks and classification in ["UNRELATED", "TANGENTIALLY_RELATED"]:
                logger.info(f"[QUERY] High-quality chunks found (score < {confidence_threshold}). Forcing IN_SCOPE.")
                classification = "IN_SCOPE"
        
        # AMBIGUITY DETECTION: Check if query matches multiple similar acronyms
        # This prevents returning EEBD when user asks for EEDI
        is_ambiguous, possible_acronyms = self.acronym_disambiguator.is_ambiguous(
            query=standalone_query,
            chunks=chunks,
            similarity_threshold=0.7
        )
        
        if is_ambiguous and len(possible_acronyms) > 1:
            # Generate clarification request
            clarification = self.acronym_disambiguator.generate_clarification_prompt(
                query=standalone_query,
                possible_acronyms=possible_acronyms
            )
            
            # Return clarification response
            response = self._build_response(
                content=clarification,
                chunks_used=[],
                video_suggestions=[],
                question_suggestions=[
                    f"Tell me about {possible_acronyms[0]}",
                    f"What is {possible_acronyms[1] if len(possible_acronyms) > 1 else 'the correct acronym'}?",
                ],
                short_topic="clarification",
                routing_reason="ambiguous_acronym",
                media={"videos": [], "images": [], "pdfs": []},
            )
            
            history_entry = {
                "node_type": self.node_type,
                "content": clarification,
                "short_topic": "clarification",
                "user_query": query,
                "chunks": [],
                "metadata": response.get("metadata", {}),
                "category": "QUERY",
            }
            updated_meaningful_messages = existing_meaningful_messages + [history_entry]
            updated_meaningful_history = existing_meaningful_history + [history_entry]
            
            return {
                "router_decision": {**decision, "category": "QUERY"},
                "node_response": response,
                "meaningful_messages": updated_meaningful_messages,
                "meaningful_history": updated_meaningful_history,
                "user_memory": user_memory,
                "last_user_query": standalone_query,
                "last_user_category": "QUERY",
            }

        # Handle memory recall queries
        if classification == "MEMORY_RECALL":
            recall_response = self._handle_memory_recall(user_memory)
            response = self._build_response(
                content=recall_response,
                chunks_used=[],
                video_suggestions=[],
                question_suggestions=[
                    "What navigation systems are covered in the course?",
                    "Can you explain ship stability principles?",
                    "What are the main safety procedures for maritime operations?",
                ],
                short_topic="memory",
                routing_reason="memory_recall",
                media={"videos": [], "images": [], "pdfs": []},
            )
            return {
                "router_decision": {**decision, "category": "QUERY"},
                "node_response": response,
                "meaningful_messages": existing_meaningful_messages,
                "meaningful_history": existing_meaningful_history,
                "user_memory": user_memory,
                "last_user_query": standalone_query,
                "last_user_category": "QUERY",
            }
        
        # Handle personal info introduction
        if classification == "PERSONAL_INFO":
            name_part = f", {user_memory.get('name')}" if user_memory.get('name') else ""
            intro_response = f"Nice to meet you{name_part}! I'm Marine Tutor AI, here to help with your maritime education. What would you like to learn about today?"
            response = self._build_response(
                content=intro_response,
                chunks_used=[],
                video_suggestions=[],
                question_suggestions=[
                    "What navigation systems are taught in this course?",
                    "Can you explain maritime safety regulations?",
                    "What are the key principles of ship operations?",
                ],
                short_topic="introduction",
                routing_reason="personal_info",
                media={"videos": [], "images": [], "pdfs": []},
            )
            return {
                "router_decision": {**decision, "category": "QUERY"},
                "node_response": response,
                "meaningful_messages": existing_meaningful_messages,
                "meaningful_history": existing_meaningful_history,
                "user_memory": user_memory,
                "last_user_query": standalone_query,
                "last_user_category": "QUERY",
            }

        # --- 1. STRICT GUARD: CHECK FOR EMPTY CHUNKS OR OUT-OF-SCOPE ---
        if not chunks or classification in ["UNRELATED", "TANGENTIALLY_RELATED"]:
            logger.warning(f"[QUERY NODE] No chunks or out-of-scope query ({classification}). Using intelligent fallback.")
            
            # Build user context for personalization
            user_context_parts = []
            if user_memory.get("name"):
                user_context_parts.append(f"User's name: {user_memory['name']}")
            if user_memory.get("role"):
                user_context_parts.append(f"Role: {user_memory['role']}")
            user_context_str = "\n".join(user_context_parts) if user_context_parts else ""
            
            # Generate intelligent, contextual fallback
            fallback_answer, fallback_suggestions = await self._generate_intelligent_fallback(
                query, 
                user_context_str
            )

            # Construct partial response
            response = self._build_response(
                content=fallback_answer,
                chunks_used=[],
                video_suggestions=[],
                question_suggestions=fallback_suggestions,
                short_topic="general",
                routing_reason="no_retrieval" if not chunks else "out_of_scope",
                media={"videos": [], "images": [], "pdfs": []},
            )

            # Do usual state updates but skip LLM
            history_entry = {
                "node_type": self.node_type,
                "content": fallback_answer,
                "short_topic": "general",
                "user_query": query,
                "chunks": [],
                "metadata": response.get("metadata", {}),
                "category": "QUERY",
            }
            updated_meaningful_messages = existing_meaningful_messages + [history_entry]
            updated_meaningful_history = existing_meaningful_history + [history_entry]
            
            return {
                "router_decision": {**decision, "category": "QUERY"},
                "node_response": response,
                "meaningful_messages": updated_meaningful_messages,
                "meaningful_history": updated_meaningful_history,
                "user_memory": user_memory,
                "last_user_query": standalone_query,
                "last_user_category": "QUERY",
            }
        # -----------------------------------------------

        # Check if this is a "have i asked this question before" query
        is_asking_if_asked_before = False
        original_question = ""

        # Pattern to detect "have i asked this question before" type queries
        if "have i asked this question before" in query.lower() or "did i ask this before" in query.lower():
            is_asking_if_asked_before = True
            # Extract the question after the colon
            parts = query.split(":", 1)
            if len(parts) > 1:
                original_question = parts[1].strip()
            else:
                # Try to extract question from other patterns
                match = re.search(r"about\s+(.+)$", query.lower())
                if match:
                    original_question = match.group(1).strip()

        # Get previous answers from meaningful history
        previous_answers = []
        for entry in existing_meaningful_history:
            if isinstance(entry, dict) and entry.get("content") and entry.get("user_query"):
                previous_answers.append({
                    "question": entry.get("user_query", ""),
                    "answer": entry.get("content", ""),
                    "node_type": entry.get("node_type", "")
                })

        # Check if this exact question (or similar) was asked before
        question_was_asked_before = False
        previous_answer_content = ""

        if is_asking_if_asked_before and original_question:
            for answer in previous_answers:
                # Check if the questions are similar
                prev_q_lower = answer["question"].lower()
                orig_q_lower = original_question.lower()

                # Simple similarity check - check if one contains the other
                if (orig_q_lower in prev_q_lower or prev_q_lower in orig_q_lower or
                    orig_q_lower in answer["answer"].lower()):
                    question_was_asked_before = True
                    previous_answer_content = answer["answer"]
                    break

        category = (decision.get("category") or safe_get(state, "category", "QUERY") or "QUERY").upper()

        media_bundle = self._aggregate_media(chunks)
        include_media = False

        # Get last topic from existing meaningful history first
        last_topic = "marine"
        if existing_meaningful_history:
            for entry in reversed(existing_meaningful_history):
                if entry.get("short_topic"):
                    last_topic = entry.get("short_topic")
                    break

        if not last_topic or last_topic == "marine":
            last_topic = decision.get("short_topic", "marine")


        # If user is asking if they asked before AND we found a previous answer
        if is_asking_if_asked_before and question_was_asked_before and previous_answer_content:
            # Just return the previous answer with a note
            answer = f"## ✅ Yes, you have asked this question before!\n\n**Your previous question:** {original_question}\n\n**Previous answer:**\n\n{previous_answer_content}\n\n*Would you like me to elaborate on any specific part or explore related topics?*"

            # Use default suggestions
            dynamic_suggestions = [
                "What are the practical applications of compass corrections in modern navigation?",
                "How does magnetic variation differ in various parts of the world?",
                "What are the main differences between magnetic and gyro compasses?"
            ]

        else:
            # Normal query processing
            # Format chunks into text content for LLM
            chunks_text_parts = []
            total_chars = 0
            # Limit to prevent token overflow (aim for ~80K tokens max for chunks ≈ 320K chars)
            MAX_CHUNK_CHARS = 300000  # ~75K tokens, leaving room for system prompt + response
            
            for chunk in chunks:
                chunk_text = self._format_chunk_for_prompt(chunk)
                if chunk_text:  # Only add non-empty chunks
                    # Check if adding this chunk would exceed our limit
                    if total_chars + len(chunk_text) > MAX_CHUNK_CHARS:
                        logger.warning(
                            f"[QUERY NODE] Stopping chunk inclusion at {len(chunks_text_parts)} chunks "
                            f"(total: {total_chars} chars) to prevent token overflow"
                        )
                        break
                    chunks_text_parts.append(chunk_text)
                    total_chars += len(chunk_text)
            
            chunks_text = "\n\n---\n\n".join(chunks_text_parts)
            
            # CRITICAL VALIDATION: Ensure chunks_content is not empty
            if not chunks_text or not chunks_text.strip():
                logger.error(
                    "[QUERY NODE] CRITICAL: chunks_content is empty after formatting! "
                    f"Chunks count: {len(chunks)}, Chunk keys: {[list(c.keys()) if isinstance(c, dict) else 'not-dict' for c in chunks[:2]]}"
                )
                # Use intelligent fallback
                user_context_parts = []
                if user_memory.get("name"):
                    user_context_parts.append(f"User's name: {user_memory['name']}")
                if user_memory.get("role"):
                    user_context_parts.append(f"Role: {user_memory['role']}")
                user_context_str = "\n".join(user_context_parts) if user_context_parts else ""
                
                fallback_answer, fallback_suggestions = await self._generate_intelligent_fallback(
                    query, 
                    user_context_str
                )
                
                response = self._build_response(
                    content=fallback_answer,
                    chunks_used=chunks,
                    video_suggestions=[],
                    question_suggestions=fallback_suggestions,
                    short_topic=decision.get("short_topic", "general"),
                    routing_reason="empty_chunks_content",
                    media={"videos": [], "images": [], "pdfs": []},
                )
                
                history_entry = {
                    "node_type": self.node_type,
                    "content": fallback_answer,
                    "short_topic": decision.get("short_topic", "general"),
                    "user_query": query,
                    "chunks": chunks,
                    "metadata": response.get("metadata", {}),
                    "category": category,
                }
                
                updated_meaningful_messages = existing_meaningful_messages + [history_entry]
                updated_meaningful_history = existing_meaningful_history + [history_entry]
                
                return {
                    "router_decision": {**decision, "category": category},
                    "node_response": response,
                    "meaningful_messages": updated_meaningful_messages,
                    "meaningful_history": updated_meaningful_history,
                    "user_memory": user_memory,
                    "last_user_query": standalone_query,
                    "last_user_category": "QUERY",
                }
            
            # Log chunks_content for debugging (first 500 chars)
            logger.info(
                f"[QUERY NODE] Formatted chunks_content length: {len(chunks_text)} chars, "
                f"from {len(chunks_text_parts)} chunks. Preview: {chunks_text[:200]}..."
            )
            
            # ====== CONVERSATION CONTEXT AWARENESS ======
            # Check if this topic was recently covered to enable response variation
            context_info = self.conversation_context.check_recent_topic_coverage(
                session_history=existing_meaningful_history or existing_meaningful_messages,
                current_query=standalone_query,
                lookback=10
            )
            
            # Detect user intent from query phrasing
            user_intent = self.conversation_context.detect_user_intent(
                query=standalone_query,
                conversation_context=context_info
            )
            
            # Determine query style
            query_style = 'ALL_CAPS' if standalone_query.isupper() and len(standalone_query) > 5 else 'normal'
            
            # Get response strategy based on context
            response_strategy = self.conversation_context.get_response_strategy(
                times_asked=context_info['times_asked'],
                user_intent=user_intent,
                query_style=query_style
            )
            
            # Generate acknowledgment if topic was asked before
            acknowledgment_text = None
            if context_info['already_covered']:
                topic_name = decision.get("short_topic", standalone_query[:50])
                acknowledgment_text = self.conversation_context.generate_acknowledgment_text(
                    times_asked=context_info['times_asked'],
                    user_intent=user_intent,
                    topic=topic_name
                )
            
            # Generate follow-up options if frustrated repetition detected
            followup_options = None
            if context_info['times_asked'] >= 1:
                topic_name = decision.get("short_topic", standalone_query[:50])
                followup_options = self.conversation_context.generate_followup_options(
                    topic=topic_name,
                    times_asked=context_info['times_asked'],
                    previous_responses=context_info['previous_responses']
                )
            
            # Build enhanced prompt with conversation context
            context_instructions = ""
            if context_info['already_covered']:
                previous_summary = self.conversation_context.summarize_previous_coverage(
                    context_info['previous_responses'],
                    max_length=150
                )
                
                context_instructions = f"""
IMPORTANT CONVERSATION CONTEXT:
- This topic has been discussed {context_info['times_asked']} time(s) recently
- User intent detected: {user_intent}
- Response strategy: {response_strategy['approach']}
- Tone to use: {response_strategy['tone']}

PREVIOUS COVERAGE (DO NOT repeat verbatim):
{previous_summary}

VARIATION REQUIREMENTS:
1. {acknowledgment_text if acknowledgment_text else "Acknowledge you've covered this topic"}
2. VARY your response structure and content - focus on DIFFERENT aspects than before
3. Match user intent '{user_intent}':
   - If 'simplification': Use clear, accessible language
   - If 'more_detail': Provide comprehensive technical depth
   - If 'practical': Focus on step-by-step procedures
   - If 'examples': Emphasize scenarios and case studies
   - If 'frustrated_repetition': Clarify intent and offer specific options
4. Use tone: {response_strategy['tone']}
5. Each response should add NEW value not covered previously

{f"FOLLOW-UP OPTIONS TO INCLUDE:{chr(10)}{followup_options}" if followup_options else ""}
"""
            
            # Format prompt - ONLY include placeholders that exist in template
            base_prompt = QUERY_PROMPT.format(
                chunks_content=chunks_text,
                user_query=query,
            )
            
            # Append context instructions if topic was covered before
            prompt = base_prompt + (f"\n\n{context_instructions}" if context_instructions else "")
            
            # Log conversation context
            if context_info['already_covered']:
                logger.warning(
                    f"[CONTEXT] Repeated question detected! "
                    f"times_asked={context_info['times_asked']}, intent={user_intent}, "
                    f"strategy={response_strategy['approach']}"
                )
            
            # Log final prompt for debugging
            logger.debug(f"[QUERY NODE] Final prompt length: {len(prompt)} chars")

            # ====== SINGLE LLM CALL ======
            # CRITICAL: Use temperature=0 for DETERMINISTIC responses
            # Same query + same chunks MUST produce same answer for consistency
            llm_response = await self.openai_service.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.0,  # DETERMINISTIC: Ensures identical query+chunks → identical answer
                category="QUERY",
            )

            include_media = True

            # Extract both answer and suggestions from the single response
            answer, dynamic_suggestions = self._extract_answer_and_suggestions(llm_response, chunks)

            # Log the extracted suggestions for debugging
            logger.info(f"[QUERY] Generated {len(dynamic_suggestions)} suggestions from single LLM call")
            
            # IMPROVED: Detect if LLM refused to answer (varied phrasing)
            # Check for multiple refusal indicators instead of one hardcoded message
            refusal_indicators = [
                "does not contain",
                "not provided",
                "no information",
                "unable to provide",
                "cannot find",
                "not relate",
                "does not align",
                "no mention",
                "no reference",
                "not covered in the course",
                "not in the course"
            ]
            
            # Check if answer contains refusal indicators AND is relatively short (< 500 chars)
            # Short length helps distinguish refusals from legitimate answers mentioning these phrases
            answer_lower = answer.lower()
            contains_refusal = any(indicator in answer_lower for indicator in refusal_indicators)
            is_short_response = len(answer) < 500
            
            if contains_refusal and is_short_response:
                logger.warning(
                    f"[QUERY] Refusal detected in LLM response (length={len(answer)}). "
                    f"Suppressing media suggestions."
                )
                include_media = False
            # ====== END SINGLE LLM CALL ======

        media_payload = media_bundle if include_media else {"videos": [], "images": [], "pdfs": []}

        response = self._build_response(
            content=answer,
            chunks_used=chunks,
            video_suggestions=media_payload["videos"],
            question_suggestions=dynamic_suggestions,
            short_topic=decision.get("short_topic", "marine"),
            routing_reason=decision.get("reason", "query"),
            media=media_payload,
        )

        response_metadata = response.get("metadata", {})

        # Create history entry
        history_entry = {
            "node_type": self.node_type,
            "content": answer,
            "short_topic": decision.get("short_topic", "marine"),
            "user_query": query,
            "chunks": chunks,
            "metadata": response_metadata,
            "category": category,
        }

        # CRITICAL: Append to existing history, don't replace it
        updated_meaningful_messages = existing_meaningful_messages + [history_entry]
        updated_meaningful_history = existing_meaningful_history + [history_entry]

        # 🔐 LangGraph checkpointer fields
        previous_successful_questions: List[str] = list(
            safe_get(state, "previous_successful_questions", []) or []
        )
        previous_successful_chunks: List[List[Dict[str, Any]]] = list(
            safe_get(state, "previous_successful_chunks", []) or []
        )
        topic_history: List[str] = list(safe_get(state, "topic_history", []) or [])

        previous_successful_questions.append(standalone_query)
        previous_successful_chunks.append(chunks)
        if decision.get("short_topic"):
            topic_history.append(decision.get("short_topic"))

        return {
            "router_decision": {**decision, "category": category},
            "node_response": response,
            "meaningful_messages": updated_meaningful_messages,
            "meaningful_history": updated_meaningful_history,
            "previous_successful_questions": previous_successful_questions,
            "previous_successful_chunks": previous_successful_chunks,
            "last_query_chunks": chunks,
            "last_user_query": standalone_query,
            "last_user_category": "QUERY",
            "topic_history": topic_history,
            "user_memory": user_memory,
        }
