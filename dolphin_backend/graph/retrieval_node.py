# graph/retrieval_node.py
from __future__ import annotations

import re
import json
from typing import Any, Dict, List, Optional

from loguru import logger

from graph.base_node import BaseNode
from config import settings
from models.database import get_pool
from retrieval.faiss_store import DEFAULT_TOP_K
from retrieval.postgres_loader import PostgresLoader
from services.query_expansion_service import QueryExpansionService

QUIZ_CONFIDENCE_THRESHOLD = 1.2
GENERIC_QUIZ_KEYWORDS = [
    "quiz", "quizz", "qusiz", "mcq", "test", "practice test",
    "give me a quiz", "generate quiz", "create quiz",
    "question paper", "mock test", "assessment",
    "quiz me", "test me", "make a quiz", "can you quiz me"
]


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


class RetrievalNode(BaseNode):
    """Retrieves contextual chunks and suggested videos for downstream nodes."""

    def __init__(
        self, 
        vector_store,
        query_expansion_service: Optional[QueryExpansionService] = None
    ) -> None:
        super().__init__("retrieval")
        self.vector_store = vector_store
        self.query_expansion_service = query_expansion_service
        logger.info(f"RetrievalNode initialized with query_expansion={'enabled' if query_expansion_service else 'disabled'}")

    def _resolve_quiz_topic(
        self, query: str, previous_successful_questions: List[str], last_user_query: str
    ) -> str:
        normalized = (query or "").strip()

        if not normalized:
            return last_user_query or (
                previous_successful_questions[-1] if previous_successful_questions else ""
            )

        # Detect references to previous context
        if re.search(r"\b(previous|above|before|last topic)\b", normalized, re.IGNORECASE):
            if previous_successful_questions:
                return previous_successful_questions[-1]
            return last_user_query or normalized

        direct_patterns = [
            r"quiz for\s+(.+)$",
            r"quiz on\s+(.+)$",
            r"generate quiz on\s+(.+)$",
            r"create quiz for\s+(.+)$",
            r"make mcq for\s+(.+)$",
            r"mcq on\s+(.+)$",
        ]

        for pattern in direct_patterns:
            match = re.search(pattern, normalized, re.IGNORECASE)
            if match:
                topic = match.group(1).strip()
                if topic:
                    return topic

        return normalized

    def _coerce_media(self, value: Any) -> List[Dict[str, Any]]:
        """Ensure media payloads are always returned as lists of dicts.
        
        Improved JSON parsing with comprehensive error handling for topic_video fields.
        Handles various formats: JSON strings, lists, dicts, and malformed data.
        """
        if value is None:
            logger.debug("[VIDEO] _coerce_media: value is None, returning empty list")
            return []
        
        value_type = type(value).__name__
        logger.debug(f"[VIDEO] _coerce_media: received value type={value_type}, value_preview={str(value)[:100] if not isinstance(value, (list, dict)) else f'{len(value) if isinstance(value, list) else 1} items'}")
        
        # Already a list - validate and return
        if isinstance(value, list):
            # Validate list items are dicts
            validated = []
            for item in value:
                if isinstance(item, dict):
                    validated.append(item)
                elif isinstance(item, str):
                    # Try to parse string items as JSON
                    try:
                        parsed = json.loads(item)
                        if isinstance(parsed, dict):
                            validated.append(parsed)
                    except (json.JSONDecodeError, TypeError):
                        logger.debug(f"Failed to parse list item as JSON: {item[:50]}")
            logger.debug(f"[VIDEO] _coerce_media: parsed list, returning {len(validated)} items")
            return validated
        
        # String or bytes - try JSON parsing
        if isinstance(value, (str, bytes)):
            try:
                # Handle bytes
                if isinstance(value, bytes):
                    value = value.decode('utf-8')
                
                # Try parsing as JSON
                parsed = json.loads(value)
                
                # Handle different JSON structures
                if isinstance(parsed, list):
                    result = [item for item in parsed if isinstance(item, dict)]
                    logger.debug(f"[VIDEO] _coerce_media: parsed JSON list, returning {len(result)} items")
                    return result
                elif isinstance(parsed, dict):
                    # Single video object - wrap in list
                    logger.debug(f"[VIDEO] _coerce_media: parsed single JSON dict, wrapping in list")
                    return [parsed]
                else:
                    logger.warning(f"Unexpected JSON structure for media: {type(parsed)}")
                    return []
                    
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse media JSON: {e}. Value: {str(value)[:100]}")
                return []
            except (UnicodeDecodeError, TypeError) as e:
                logger.warning(f"Failed to decode media value: {e}")
                return []
        
        # Dict - wrap in list
        if isinstance(value, dict):
            logger.debug(f"[VIDEO] _coerce_media: received dict, wrapping in list")
            return [value]
        
        # Unknown type
        logger.debug(f"Unknown media type: {type(value)}")
        return []

    def _extract_and_filter_videos(
        self, 
        chunks: List[Dict[str, Any]], 
        existing_videos: List[Dict[str, Any]],
        max_videos: int = 15,
        score_threshold: float = 3.5  # For content filtering (not used for video extraction)
    ) -> List[Dict[str, Any]]:
        """Extract videos from chunks and return top N most relevant videos.
        
        Videos are sorted by chunk relevance score (lower = better) and limited to max_videos count.
        NO additional score-based filtering is applied - chunks are already filtered by score_threshold.
        
        Args:
            chunks: List of chunks with videos and _score fields
            existing_videos: Existing videos to merge with
            max_videos: Maximum number of videos to return (default: 15)
            score_threshold: Not used for video extraction (kept for API compatibility)
        
        Returns:
            List of top N most relevant videos, sorted by chunk relevance
        """
        video_candidates: List[Dict[str, Any]] = []
        seen_urls: set[str] = set()
        seen_video_ids: set[str] = set()
        seen_titles: set[str] = set()  # Add title-based deduplication
        
        # Note: Chunks are already filtered by score_threshold (3.5) before reaching this method.
        # We trust that filtering and only limit by count (max_videos).
        
        # Extract videos from ALL chunks (already relevance-filtered at chunk level)
        logger.debug(f"[VIDEO] Extracting videos from {len(chunks)} chunks")
        for chunk in chunks:
            if not isinstance(chunk, dict):
                continue
            
            chunk_score = chunk.get("_score")
            chunk_rank = chunk.get("_rank")
            topic_name = chunk.get("topic_name", "Unknown")
            
            videos = chunk.get("videos", [])
            if not isinstance(videos, list):
                logger.debug(f"[VIDEO] Chunk '{topic_name}' has no videos (type: {type(videos)})")
                continue
            
            if len(videos) == 0:
                logger.debug(f"[VIDEO] Chunk '{topic_name}' has empty videos list")
                continue
            
            logger.debug(f"[VIDEO] Chunk '{topic_name}' has {len(videos)} video(s), score={chunk_score}, rank={chunk_rank}")
            
            for video in videos:
                if not isinstance(video, dict):
                    continue
                
                # Extract video URL and ID for deduplication
                extract = lambda keys, d: next((d[k] for k in keys if k in d), "")
                raw_url = str(extract(["url", "videourl", "Url", "videolink", "Link"], video)).strip()
                vid_id = str(extract(["video_id", "Id", "id"], video)).strip()
                title = str(extract(["title", "Title", "About"], video)).strip()
                
                # Normalize URL for consistent deduplication
                normalized_url = normalize_video_url(raw_url)
                
                # Normalize title for deduplication (lowercase, strip whitespace)
                normalized_title = title.lower().strip() if title else ""
                
                # Check for duplicates using URL, video_id, and title (in order of priority)
                is_duplicate = False
                if normalized_url and normalized_url in seen_urls:
                    is_duplicate = True
                elif vid_id and vid_id.lower() in seen_video_ids:
                    is_duplicate = True
                elif normalized_title and normalized_title in seen_titles:
                    # Fallback: check by title if URL/ID don't match
                    is_duplicate = True
                elif not normalized_url and not vid_id and not normalized_title:
                    # Skip videos with no URL, ID, or title (can't deduplicate)
                    logger.debug(f"[VIDEO] Skipping video with no URL/ID/title: {video}")
                    continue
                
                if is_duplicate:
                    continue
                
                # Mark as seen
                if normalized_url:
                    seen_urls.add(normalized_url)
                if vid_id:
                    seen_video_ids.add(vid_id.lower())
                if normalized_title:
                    seen_titles.add(normalized_title)
                
                # Normalize video structure
                thumb = str(extract(["thumbnail", "Thumbnail"], video)).strip()
                
                # Preserve existing relevance info if present, otherwise use chunk's
                existing_score = video.get("_chunk_score", chunk_score)
                existing_rank = video.get("_chunk_rank", chunk_rank)
                
                # Check if chunk has topic match (from re-ranking)
                has_topic_match = chunk.get("_has_topic_match", False)
                
                # Use original URL for display, normalized URL for deduplication
                display_url = raw_url if raw_url else normalized_url
                
                # Create normalized video dict with relevance info
                normalized_video = {
                    "title": title if title else "Course video",
                    "url": display_url,
                    "videourl": display_url,
                    "thumbnail": thumb,
                    "video_id": vid_id,
                    "_chunk_score": existing_score,
                    "_chunk_rank": existing_rank,
                    "_has_topic_match": has_topic_match,  # Pass through topic match flag
                }
                
                video_candidates.append(normalized_video)
        
        # Add existing videos (without duplicates)
        for video in existing_videos:
            if not isinstance(video, dict):
                continue
            
            extract = lambda keys, d: next((d[k] for k in keys if k in d), "")
            raw_url = str(extract(["url", "videourl", "Url", "videolink", "Link"], video)).strip()
            vid_id = str(extract(["video_id", "Id", "id"], video)).strip()
            title = str(extract(["title", "Title", "About"], video)).strip()
            
            # Normalize URL for deduplication
            normalized_url = normalize_video_url(raw_url)
            
            # Normalize title for deduplication
            normalized_title = title.lower().strip() if title else ""
            
            # Check for duplicates using URL, video_id, and title
            is_duplicate = False
            if normalized_url and normalized_url in seen_urls:
                is_duplicate = True
            elif vid_id and vid_id.lower() in seen_video_ids:
                is_duplicate = True
            elif normalized_title and normalized_title in seen_titles:
                # Fallback: check by title if URL/ID don't match
                is_duplicate = True
            elif not normalized_url and not vid_id and not normalized_title:
                continue  # Skip videos with no URL, ID, or title
            
            if is_duplicate:
                continue
            
            # Mark as seen
            if normalized_url:
                seen_urls.add(normalized_url)
            if vid_id:
                seen_video_ids.add(vid_id.lower())
            if normalized_title:
                seen_titles.add(normalized_title)
            
            # Preserve existing video structure, add default relevance if missing
            if "_chunk_score" not in video:
                video["_chunk_score"] = None
                video["_chunk_rank"] = None
            video_candidates.append(video)
        
        # Sort by relevance: lower score = higher relevance, then by rank
        def get_sort_key(video: Dict[str, Any]) -> tuple:
            score = video.get("_chunk_score")
            rank = video.get("_chunk_rank")
            
            # Convert score to float, use high value if None (sort to end)
            score_val = float(score) if score is not None else 999.0
            rank_val = int(rank) if rank is not None else 999
            
            return (score_val, rank_val)
        
        video_candidates.sort(key=get_sort_key)
        
        # Filter videos ONLY by max count (not by score)
        # Rationale: Chunks are already filtered by score_threshold (3.5) before video extraction.
        # Videos inherit relevance approval from their parent chunks - no need for additional score filtering.
        # This prevents losing relevant videos from moderately-scored but semantically correct chunks.
        filtered_videos = video_candidates[:max_videos]
        
        logger.info(
            f"✅ Extracted {len(filtered_videos)} videos from {len(chunks)} chunks "
            f"(sorted from {len(video_candidates)} candidates)"
        )
        
        # Log details about filtered videos for debugging
        if filtered_videos:
            logger.info(f"[VIDEO] Final filtered videos ({len(filtered_videos)} total):")
            for idx, video in enumerate(filtered_videos[:5], 1):  # Log first 5
                logger.info(f"[VIDEO]   [{idx}] Title='{video.get('title', 'N/A')[:50]}', URL={'YES' if video.get('url') else 'EMPTY'}, Score={video.get('_chunk_score', 'N/A')}")
        else:
            logger.warning(
                f"[VIDEO] ⚠️ No videos returned after filtering! "
                f"Had {len(video_candidates)} candidates from {len(chunks)} chunks. "
                f"Chunks with videos: {sum(1 for c in chunks if isinstance(c.get('videos'), list) and len(c.get('videos', [])) > 0)}"
            )
        
        return filtered_videos

    def _is_acronym_match(self, term: str, topic_name: str) -> bool:
        """
        Check if a term is an acronym that matches the topic name.
        
        Examples:
            "FPFF" matches "FirePreventionAndFirefighting"
            "FPFF" matches "Fire Prevention And Firefighting"  
            "PPE" matches "PersonalProtectiveEquipment"
            "EEDI" matches "EnergyEfficiencyDesignIndex"
        
        Args:
            term: Potential acronym (e.g., "FPFF", "ppe")
            topic_name: Topic name to match against (preserves original casing)
        
        Returns:
            True if term matches the first letters of words in topic_name
        """
        if not term or not topic_name or len(term) < 2:
            return False
        
        term_upper = term.upper()
        
        # Extract words from topic name (handle CamelCase and spaces)
        # Split by uppercase letters for CamelCase (e.g., "FirePrevention" -> ["Fire", "Prevention"])
        # Split by spaces/underscores for regular names
        words = []
        
        # First, split by spaces, underscores, hyphens
        parts = re.split(r'[\s_\-]+', topic_name)
        
        for part in parts:
            # Further split CamelCase words
            # Insert space before uppercase letters (including consecutive ones)
            # e.g., "Firefighting" -> "Fire fighting", "PPE" stays as "PPE"
            camel_split = re.sub(r'([a-z])([A-Z])', r'\1 \2', part)
            # Also handle cases like "FireFighting" where both words start with capital
            camel_split = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', camel_split)
            words.extend(camel_split.split())
        
        # Filter out empty strings and common connector words that are typically not part of acronyms
        # (e.g., "Fire Prevention And Firefighting" → "FPFF" not "FPAF")
        connector_words = {'and', 'of', 'the', 'for', 'with', 'in', 'on', 'at', 'to', 'or'}
        words = [w for w in words if len(w) > 0 and w.lower() not in connector_words]
        
        if not words:
            return False
        
        # Get first letter of each word
        first_letters = ''.join(w[0].upper() for w in words if w)
        
        # Allow partial match (e.g., "FP" matches "FirePrevention")
        if first_letters.startswith(term_upper) or term_upper in first_letters:
            return True
        
        # Additional fuzzy match: Check if most letters match (for minor variations)
        # e.g., "FPFF" vs "FPF" - 3 out of 4 letters match
        if len(term_upper) >= 3 and len(first_letters) >= 3:
            common_prefix_len = 0
            for i in range(min(len(term_upper), len(first_letters))):
                if term_upper[i] == first_letters[i]:
                    common_prefix_len += 1
                else:
                    break
            
            # If at least 75% of the term matches the prefix, consider it a match
            if common_prefix_len >= len(term_upper) * 0.75 and common_prefix_len >= 3:
                return True
        
        return False
    
    def _is_fuzzy_match(self, term: str, topic_name: str, similarity_threshold: float = 0.85) -> bool:
        """
        Check if a term fuzzy-matches any word in the topic name (handles typos).
        
        Uses character-level similarity to catch typos like:
        - "psycological" → "psychological" (one char missing)
        - "confict" → "conflict" (one char missing)
        - "managment" → "management" (one char missing)
        
        Args:
            term: Query term (potentially misspelled)
            topic_name: Topic name to search in (lowercase)
            similarity_threshold: Minimum similarity ratio (0.0-1.0)
        
        Returns:
            True if term fuzzy-matches any word in topic_name
        """
        if len(term) < 4:  # Too short for meaningful fuzzy matching
            return False
        
        # Split topic name into words (handle CamelCase)
        # e.g., "PsychologicalToolsForConflictManagement" → ["psychological", "tools", "for", "conflict", "management"]
        words = []
        parts = re.split(r'[\s_\-]+', topic_name)
        for part in parts:
            # Split CamelCase
            camel_split = re.sub(r'([a-z])([A-Z])', r'\1 \2', part)
            camel_split = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', camel_split)
            words.extend(w.lower() for w in camel_split.split() if len(w) >= 4)
        
        # Check similarity with each word
        from difflib import SequenceMatcher
        for word in words:
            if len(word) < 4:  # Skip short words
                continue
            
            # Calculate similarity ratio
            similarity = SequenceMatcher(None, term, word).ratio()
            
            if similarity >= similarity_threshold:
                return True
        
        return False
    
    def _rerank_by_topic_match(self, original_query: str, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Re-rank chunks by boosting those where topic_name contains query terms.
        This helps short queries like "Cargo Sampling" match "CargoSamplingProcedures" 
        better than generic topics like "BunkeringAndOilTransfer".
        
        Also handles queries like "Explain cargo sampling" by extracting key terms
        and matching them against topic names.
        
        Args:
            original_query: The original user query (before expansion)
            chunks: List of chunks from FAISS search
            
        Returns:
            Re-ranked list of chunks
        """
        if not chunks or not original_query:
            return chunks
        
        # Extract key terms from original query (normalize and split)
        # Remove common stop words but keep important terms
        query_lower = original_query.lower().strip()
        
        # Remove common conversational words that don't help with matching
        stop_words = {'explain', 'explan', 'tell', 'describe', 'show', 'what', 'whats', 'how', 'about', 'the', 'a', 'an', 'is', 'are', 'be'}
        query_terms = [
            t.lower().strip() 
            for t in re.split(r'[\s\-_]+', query_lower) 
            if t and t.lower() not in stop_words and len(t) >= 2  # Allow 2-char terms for acronyms
        ]
        
        # If we filtered out too much, use all terms (except very short ones and common words)
        if not query_terms:
            query_terms = [t.lower().strip() for t in re.split(r'[\s\-_]+', query_lower) if t and len(t) >= 2 and t not in stop_words]
        
        if not query_terms:
            return chunks
        
        # Score each chunk based on topic name matches
        scored_chunks = []
        for chunk in chunks:
            topic_name = str(chunk.get("topic_name", "")).lower()
            topic_name_original = str(chunk.get("topic_name", ""))
            original_score = chunk.get("_score", 0.0)
            
            # Calculate boost based on topic name matches
            boost = 0.0
            matched_terms = 0
            fuzzy_matched_terms = 0
            
            for term in query_terms:
                if len(term) >= 2:  # Match terms with 2+ characters (for acronyms like "AI")
                    # Check for exact word match (case-insensitive)
                    pattern = r'\b' + re.escape(term) + r'\b'
                    if re.search(pattern, topic_name):
                        boost += 0.3  # Strong boost for exact word match
                        matched_terms += 1
                    # Check for acronym match (e.g., "FPFF" matches "FirePreventionAndFirefighting")
                    elif self._is_acronym_match(term, topic_name_original):
                        boost += 0.4  # Even stronger boost for acronym match
                        matched_terms += 1
                    # Check for fuzzy match (handles typos like "psycological" vs "psychological")
                    elif self._is_fuzzy_match(term, topic_name, similarity_threshold=0.85):
                        boost += 0.25  # Good boost for fuzzy match (typo tolerance)
                        fuzzy_matched_terms += 1
                        matched_terms += 1
                    # Check for partial match (substring)
                    elif term in topic_name:
                        boost += 0.1  # Smaller boost for partial match
                        matched_terms += 1
            
            # Bonus: If most/all query terms matched (including fuzzy), give extra boost
            match_ratio = matched_terms / len(query_terms) if len(query_terms) > 0 else 0
            if match_ratio >= 0.75:  # 75%+ of terms matched
                boost += 0.2
            
            # Additional bonus for multi-word phrase coherence
            # If query has 3+ words and all are found in topic (even fuzzy), it's very relevant
            if len(query_terms) >= 3 and match_ratio >= 0.8:
                boost += 0.15  # Extra boost for phrase match
            
            # Apply boost: lower score is better (FAISS distance), so subtract boost
            # Ensure score doesn't go negative (FAISS distances are always positive)
            new_score = max(0.0, original_score - boost)
            chunk_copy = dict(chunk)
            chunk_copy["_score"] = new_score
            chunk_copy["_original_score"] = original_score
            chunk_copy["_topic_match_boost"] = boost
            chunk_copy["_fuzzy_match_count"] = fuzzy_matched_terms
            # Mark chunks with topic matches for special video handling
            if matched_terms > 0:
                chunk_copy["_has_topic_match"] = True
            scored_chunks.append(chunk_copy)
        
        # Sort by new score (lower is better)
        scored_chunks.sort(key=lambda x: x.get("_score", float('inf')))
        
        # Update ranks
        for rank, chunk in enumerate(scored_chunks):
            chunk["_rank"] = rank
        
        # Log re-ranking if it changed order
        if scored_chunks and scored_chunks[0].get("_topic_match_boost", 0) > 0:
            fuzzy_info = f", fuzzy_matches={scored_chunks[0].get('_fuzzy_match_count', 0)}" if scored_chunks[0].get('_fuzzy_match_count', 0) > 0 else ""
            logger.info(
                f"[RERANK] Query '{original_query}': Boosted topic '{scored_chunks[0].get('topic_name')}' "
                f"(boost={scored_chunks[0].get('_topic_match_boost', 0):.2f}{fuzzy_info})"
            )
        
        return scored_chunks

    def _normalize_chunk(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize chunk data and extract media with score preservation."""
        extract = lambda keys, d: next((d[k] for k in keys if k in d), "")
        
        topic_name = str(extract(["topic_name", "title", "topic"], raw))
        topic_content = str(extract(["topic_content", "content", "text"], raw))

        combined_content = f"Topic Name: {topic_name}\n\nTopic Content:\n{topic_content}" if topic_name or topic_content else ""

        # Extract score for relevance filtering (FAISS distance - lower is better)
        chunk_score = raw.get("_score")
        chunk_rank = raw.get("_rank")
        
        # Extract videos and attach chunk relevance info
        videos = self._coerce_media(raw.get("topic_video") or raw.get("videos"))
        # Preserve topic match flag from re-ranking
        has_topic_match = raw.get("_has_topic_match", False)
        
        # Attach chunk score, rank, and topic match flag to each video for later filtering
        for video in videos:
            if isinstance(video, dict):
                video["_chunk_score"] = chunk_score
                video["_chunk_rank"] = chunk_rank
                video["_has_topic_match"] = has_topic_match

        return {
            "content_id": raw.get("content_id") or raw.get("id"),
            "topic_name": topic_name,
            "topic_content": topic_content,
            "content": combined_content,
            "videos": videos,
            "images": self._coerce_media(raw.get("topic_image") or raw.get("images")),
            "pdfs": self._coerce_media(raw.get("topic_pdf") or raw.get("pdfs")),
            "_rank": chunk_rank,
            "_score": chunk_score,
            "_faiss_index": raw.get("_faiss_index"),
            "_has_topic_match": has_topic_match,  # Preserve topic match flag
        }

    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        # FIXED: Handle both dict and GraphState properly
        query: str = str(safe_get(state, "current_query", "") or "")
        decision: Dict[str, Any] = safe_get(state, "router_decision", {}) or {}
        node_type = (decision.get("node_type") or "query").lower()

        # Safe way to log state keys for debugging
        try:
            if hasattr(state, "__dict__"):
                state_keys = list(state.__dict__.keys())
            elif isinstance(state, dict):
                state_keys = list(state.keys())
            else:
                state_keys = [type(state).__name__]
        except Exception:
            logger.exception("Failed to introspect state keys in RetrievalNode")
            state_keys = ["unknown_state_type"]

        existing_chunks_len = 0
        if isinstance(state, dict):
            existing_chunks_len = len(state.get("chunks", []) or [])
        else:
            try:
                existing_chunks_len = len(getattr(state, "chunks", []) or [])
            except Exception:
                existing_chunks_len = 0

        logger.error("💥 DEBUG — RetrievalNode input keys: {}", state_keys)
        logger.error("💥 DEBUG — state['current_query'] = {}", query)
        logger.error(
            "💥 DEBUG — BEFORE retrieval, existing chunks = {}",
            existing_chunks_len,
        )

        existing_chunks: List[Dict[str, Any]] = list(
            safe_get(state, "retrieval_chunks", []) or []
        )
        raw_existing_videos = list(safe_get(state, "video_suggestions", []) or [])

        existing_videos: List[Dict[str, Any]] = []
        seen: set[str] = set()
        
        for video in raw_existing_videos:
            data = {}
            if isinstance(video, dict):
                data = video
            else:
                # Pydantic or other object
                for field in ["title", "url", "videourl", "thumbnail", "video_id", "id", "Title", "Url", "videolink"]:
                    val = getattr(video, field, None)
                    if val is not None:
                        data[field] = val
            
            if not data:
                continue
                
            extract = lambda keys, d: next((d[k] for k in keys if k in d), "")
            
            url = str(extract(["url", "videourl", "Url", "videolink", "Link"], data)).strip()
            if not url or url in seen:
                continue
            
            seen.add(url)
            
            title = str(extract(["title", "Title", "About"], data)).strip()
            vid = str(extract(["video_id", "Id", "id"], data)).strip()
            thumb = str(extract(["thumbnail", "Thumbnail"], data)).strip()
            
            existing_videos.append({
                "title": title if title else "Course video",
                "url": url,
                "videourl": url,
                "thumbnail": thumb,
                "video_id": vid,
            })

        if node_type == "summary":
            return {
                "retrieval_chunks": existing_chunks,
                "video_suggestions": existing_videos,
                "meaningful_messages": list(safe_get(state, "meaningful_messages", []) or []),
                "meaningful_history": list(safe_get(state, "meaningful_history", []) or []),
                "standalone_query": decision.get("standalone_query") or query,
            }

        resolved_quiz_topic = ""
        previous_successful_questions = list(
            safe_get(state, "previous_successful_questions", []) or []
        )
        last_user_query = str(safe_get(state, "last_user_query", "") or "")
        standalone_query = decision.get("standalone_query") or query
        search_query = standalone_query

        # ⚡ OPTIMIZATION: Skip duplicate retrieval if chat_service already fetched chunks
        # chat_service._retrieve_chunks() already does embed + FAISS + DB before the graph runs.
        # Reuse those chunks instead of searching again (~2-4s saved).
        if existing_chunks and len(existing_chunks) > 0 and node_type != "quiz":
            logger.info(
                f"⚡ [RETRIEVAL] Reusing {len(existing_chunks)} pre-fetched chunks from chat_service "
                f"(skipping duplicate FAISS search)"
            )
            final_chunks = existing_chunks
            video_suggestions = self._extract_and_filter_videos(final_chunks, existing_videos)
            meaningful_messages = list(safe_get(state, "meaningful_messages", []) or [])
            meaningful_history = list(safe_get(state, "meaningful_history", []) or [])

            return {
                "retrieval_chunks": final_chunks,
                "video_suggestions": video_suggestions,
                "meaningful_messages": meaningful_messages,
                "meaningful_history": meaningful_history,
                "resolved_quiz_topic": resolved_quiz_topic,
                "standalone_query": standalone_query,
            }

        if node_type == "quiz":
            # Check if this is a generic quiz request
            query_lower = query.lower().strip()
            is_generic = query_lower in GENERIC_QUIZ_KEYWORDS
            
            if is_generic and not re.search(r"\b(previous|above|before|last topic)\b", query_lower):
                logger.info("[RETRIEVAL] Generic quiz request detected. Skipping FAISS retrieval.")
                return {
                    "retrieval_chunks": existing_chunks or [],
                    "video_suggestions": existing_videos,
                    "meaningful_messages": list(safe_get(state, "meaningful_messages", []) or []),
                    "meaningful_history": list(safe_get(state, "meaningful_history", []) or []),
                    "resolved_quiz_topic": "",
                    "standalone_query": standalone_query,
                }

            resolved_quiz_topic = self._resolve_quiz_topic(
                query, previous_successful_questions, last_user_query
            )
            search_query = resolved_quiz_topic or standalone_query

        retrieved_chunks: List[Dict[str, Any]] = []

        if self.vector_store:
            try:
                # Validate query before retrieval
                if not search_query or not isinstance(search_query, str) or not search_query.strip():
                    logger.error(
                        f"❌ Invalid query for retrieval: {type(search_query)} - '{search_query}'"
                    )
                    retrieved_chunks = self._get_fallback_content()
                else:
                    # ========== QUERY EXPANSION ==========
                    # Expand the query with maritime context before search
                    expanded_query = search_query
                    if self.query_expansion_service:
                        try:
                            # Get chat history for context
                            chat_history = []
                            messages = safe_get(state, "messages", [])
                            if messages:
                                # Get last few messages for context
                                for msg in messages[-6:]:  # Last 3 exchanges (user + AI)
                                    if isinstance(msg, dict):
                                        chat_history.append(msg)
                            
                            # ⚡ OPTIMIZATION: Use config setting for LLM expansion
                            # LLM expansion adds ~3-5s; rule-based is instant
                            # Control via QUERY_EXPANSION_USE_LLM env var (default: True)
                            expanded_query = await self.query_expansion_service.expand_query(
                                search_query,
                                chat_history=chat_history,
                                use_llm=settings.query_expansion_use_llm,
                            )
                            
                            if expanded_query != search_query:
                                logger.info(
                                    f"[RETRIEVAL] Query expanded:\n"
                                    f"  Original: '{search_query}'\n"
                                    f"  Expanded: '{expanded_query}'"
                                )
                        except Exception as exp_error:
                            logger.warning(f"[RETRIEVAL] Query expansion failed: {exp_error}, using original query")
                            expanded_query = search_query
                    # ========================================
                    
                    retrieved_chunks = await self.vector_store.search_with_embeddings(
                        expanded_query, k=DEFAULT_TOP_K
                    )
                    
                    # Re-rank results: Boost chunks where topic_name contains query terms
                    # Use original query (before extraction) for better topic name matching
                    # This ensures "Explain cargo sampling" and "Cargo Sampling" both match "CargoSamplingProcedures"
                    retrieved_chunks = self._rerank_by_topic_match(query, retrieved_chunks)
                    
                    logger.error("🔍 FAISS RAW RESULTS (count={})", len(retrieved_chunks))
                    for r in retrieved_chunks:
                        logger.error(
                            "🔹 FAISS RESULT rank={} | faiss_index={} | score={:.4f} | topic='{}'\ncontent='{}...'",
                            r.get("_rank"),
                            r.get("_faiss_index"),
                            r.get("_score"),
                            r.get("topic_name"),
                            str(r.get("content", ""))[:150].replace("\n", " "),
                        )

            except Exception as e:
                logger.exception(f"❌ Retrieval failed: {e}")
                retrieved_chunks = self._get_fallback_content()
        else:
            logger.error("❌ Vector store is None")
            retrieved_chunks = self._get_fallback_content()

        content_ids: List[int] = []
        for ch in retrieved_chunks:
            if ch.get("content_id"):
                try:
                    content_ids.append(int(ch.get("content_id")))
                except (TypeError, ValueError):
                    pass

        fetched_rows: Dict[int, Dict[str, Any]] = {}
        if content_ids:
            try:
                pool = await get_pool()
                loader = PostgresLoader(pool)
                fetched_rows = await loader.fetch_course_content_by_ids(content_ids)
            except Exception as exc:
                logger.exception(f"❌ Failed to fetch course_content rows: {exc}")

        normalized_chunks: List[Dict[str, Any]] = []
        for raw in retrieved_chunks:
            # Apply confidence threshold for quiz node to prevent irrelevant content
            if node_type == "quiz":
                score = raw.get("_score")
                if score is not None:
                    try:
                        if float(score) > QUIZ_CONFIDENCE_THRESHOLD:
                            logger.info(f"[RETRIEVAL] Skipping chunk with low confidence for quiz: {score}")
                            continue
                    except (TypeError, ValueError):
                        pass

            content_id = raw.get("content_id")
            record = None
            if content_id is not None:
                try:
                    record = fetched_rows.get(int(content_id))
                except (TypeError, ValueError):
                    record = None

            if record:
                # Preserve re-ranking metadata when merging with database record
                rerank_metadata = {
                    k: raw.get(k) 
                    for k in ["_score", "_rank", "_faiss_index", "_has_topic_match", "_topic_match_boost", "_original_score"]
                    if raw.get(k) is not None
                }
                merged = {**raw, **record, **rerank_metadata, "content_id": int(record.get("content_id", content_id or 0))}
                normalized_chunks.append(self._normalize_chunk(merged))
            else:
                normalized_chunks.append(self._normalize_chunk(raw))

        final_chunks = normalized_chunks or existing_chunks

        logger.info(f"✅ Final chunks count: {len(final_chunks)}")

        # Extract and filter videos from chunks based on relevance
        video_suggestions = self._extract_and_filter_videos(final_chunks, existing_videos)

        meaningful_messages = list(safe_get(state, "meaningful_messages", []) or [])
        meaningful_history = list(safe_get(state, "meaningful_history", []) or [])

        return {
            "retrieval_chunks": final_chunks,
            "video_suggestions": video_suggestions,
            "meaningful_messages": meaningful_messages,
            "meaningful_history": meaningful_history,
            "resolved_quiz_topic": resolved_quiz_topic,
            "standalone_query": standalone_query,
        }

    def _get_fallback_content(self) -> List[Dict[str, Any]]:
        """Provide fallback marine content when retrieval fails"""
        return [
            {
                "content_id": None,
                "topic_name": "Marine Knowledge Base",
                "topic_content": (
                    "I can help with marine topics including ship stability, safety procedures, "
                    "propulsion systems, and heavy lift operations. Please ask your specific marine question."
                ),
                "content": (
                    "Topic Name: Marine Knowledge Base\n\nTopic Content:\n"
                    "I can help with marine topics including ship stability, safety procedures, "
                    "propulsion systems, and heavy lift operations. Please ask your specific marine question."
                ),
                "videos": [],
                "images": [],
                "pdfs": [],
            }
        ]
