# retrieval/precision_scorer.py
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple
from loguru import logger

from retrieval.normalization import (
    normalize_text_for_retrieval,
    tokenize_for_retrieval,
    simple_stem,
    extract_distinctive_terms,
    generate_ngrams,
    match_phrase_flexible,
    COMMON_GENERIC_WORDS,
    QUERY_STOP_WORDS,
)


def compute_chunk_precision_score(
    chunk: Dict[str, Any],
    query: str,
    standalone_query: str = "",
    vector_weight: float = 0.5,
    bm25_weight: float = 0.5,
    exact_phrase_boost: float = 3.0,
    topic_name_boost: float = 5.0,
    max_bm25_in_batch: float = 1.0,
) -> Tuple[float, Dict[str, Any]]:
    """
    Compute a composite precision score for a single chunk candidate.
    
    Returns:
        (total_score, score_breakdown_dict)
    """
    effective_query = (standalone_query or query or "").strip()
    q_norm = normalize_text_for_retrieval(effective_query)
    q_tokens = tokenize_for_retrieval(effective_query, stem=False)
    q_stems = [simple_stem(t) for t in q_tokens if t not in QUERY_STOP_WORDS]
    distinctive_q_words = extract_distinctive_terms(effective_query)

    topic_name = str(
        chunk.get("topic_name")
        or chunk.get("title")
        or chunk.get("document_title")
        or ""
    ).strip()
    
    content = str(
        chunk.get("topic_content")
        or chunk.get("content")
        or chunk.get("text")
        or ""
    ).strip()

    t_norm = normalize_text_for_retrieval(topic_name)
    t_tokens = tokenize_for_retrieval(topic_name, stem=False)
    t_stems = [simple_stem(t) for t in t_tokens]

    # --- 1. TOPIC NAME SCORING ---
    topic_match_type = "none"
    topic_score = 0.0

    if q_norm and t_norm:
        q_stem_str = " ".join([simple_stem(t) for t in tokenize_for_retrieval(q_norm)])
        t_stem_str = " ".join(t_stems)

        # Exact match on topic name
        if q_norm == t_norm or q_stem_str == t_stem_str:
            topic_match_type = "exact_topic"
            topic_score = 10.0
        # Complete query phrase in topic name
        elif match_phrase_flexible(effective_query, topic_name):
            topic_match_type = "phrase_in_topic"
            topic_score = 7.5
        # Distinctive keyword overlap in topic name
        elif distinctive_q_words:
            matched_dist = [w for w in distinctive_q_words if simple_stem(w) in t_stems or w in t_norm]
            if len(matched_dist) == len(distinctive_q_words):
                topic_match_type = "full_distinctive_in_topic"
                topic_score = 5.5
            elif matched_dist:
                topic_match_type = "partial_distinctive_in_topic"
                topic_score = 3.0 * (len(matched_dist) / len(distinctive_q_words))
        # Generic query overlap in topic name
        elif q_stems:
            matched_q = [w for w in q_stems if w in t_stems]
            if matched_q:
                topic_match_type = "generic_in_topic"
                topic_score = 1.0 * (len(matched_q) / len(q_stems))

    # --- 2. CONTENT PHRASE & DISTINCTIVE KEYWORD SCORING ---
    content_phrase_score = 0.0
    content_dist_score = 0.0

    if effective_query and content:
        # Multi-word phrase matching
        if len(q_stems) >= 2:
            if match_phrase_flexible(effective_query, content):
                content_phrase_score = exact_phrase_boost
            else:
                # Sub-phrase matching (e.g. 2-3 word n-grams)
                ngrams = generate_ngrams(q_tokens, min_n=2, max_n=3)
                for ng in ngrams:
                    if match_phrase_flexible(ng, content):
                        content_phrase_score = max(content_phrase_score, exact_phrase_boost * 0.6)

        # Distinctive keyword matching in content
        if distinctive_q_words:
            c_norm = normalize_text_for_retrieval(content)
            c_tokens = set(tokenize_for_retrieval(content, stem=True))
            matched_c_dist = [w for w in distinctive_q_words if simple_stem(w) in c_tokens or w in c_norm]
            if matched_c_dist:
                content_dist_score = 2.0 * (len(matched_c_dist) / len(distinctive_q_words))

    # --- 3. VECTOR SIMILARITY COMPONENT ---
    # Convert FAISS L2 distance to [0, 1] similarity
    raw_vector_dist = chunk.get("_score") if chunk.get("_bm25_score") is None else chunk.get("_vector_score")
    if raw_vector_dist is None:
        raw_vector_dist = chunk.get("_score", 1.0)
    
    # If _score is already a normalized similarity (e.g. cosine/BM25) vs L2 distance
    vector_sim = 0.0
    if raw_vector_dist is not None:
        # For L2 distance: dist >= 0, smaller is better -> 1 / (1 + dist)
        # Typical OpenAI embedding L2 distance is between 0.3 and 1.8
        try:
            dist_val = float(raw_vector_dist)
            if dist_val >= 0:
                vector_sim = 1.0 / (1.0 + dist_val)
            else:
                vector_sim = max(0.0, min(1.0, dist_val))
        except (ValueError, TypeError):
            vector_sim = 0.0

    # --- 4. BM25 COMPONENT ---
    raw_bm25 = float(chunk.get("_bm25_score", 0.0) or 0.0)
    norm_bm25 = (raw_bm25 / max_bm25_in_batch) if max_bm25_in_batch > 0 else 0.0
    norm_bm25 = min(1.0, max(0.0, norm_bm25))

    # --- 5. COMPOSITE PRECISION CALCULATION ---
    # Weight topic match strongly
    topic_component = topic_score * (topic_name_boost / 5.0)
    content_component = content_phrase_score + content_dist_score
    lexical_component = norm_bm25 * bm25_weight * 2.0
    semantic_component = vector_sim * vector_weight * 2.0

    # Penalize purely generic matches if distinctive query words exist and were NOT matched
    generic_penalty = 0.0
    if distinctive_q_words and topic_match_type in ("none", "generic_in_topic") and content_dist_score == 0.0:
        generic_penalty = 2.0

    final_score = (
        topic_component
        + content_component
        + lexical_component
        + semantic_component
        - generic_penalty
    )

    breakdown = {
        "topic_name": topic_name,
        "topic_match_type": topic_match_type,
        "topic_score": topic_score,
        "topic_component": topic_component,
        "content_phrase_score": content_phrase_score,
        "content_dist_score": content_dist_score,
        "norm_bm25": norm_bm25,
        "vector_sim": vector_sim,
        "final_score": round(final_score, 4),
    }

    return final_score, breakdown


def rank_and_filter_candidates(
    candidates: List[Dict[str, Any]],
    query: str,
    standalone_query: str = "",
    min_exact_match_score: float = 0.85,
    top_k: int = 10,
) -> Tuple[List[Dict[str, Any]], Optional[str], List[Dict[str, Any]]]:
    """
    Reranks candidate chunks with precision scoring, applies exact topic focus mode
    if detected, and groups chunks belonging to the same topic family.
    
    Returns:
        (final_selected_chunks, exact_matched_topic_name, debug_scored_list)
    """
    if not candidates:
        return [], None, []

    effective_query = (standalone_query or query or "").strip()

    # Find max BM25 score in batch for normalization
    max_bm25 = max(
        [float(c.get("_bm25_score", 0.0) or 0.0) for c in candidates] + [1.0]
    )

    scored_candidates = []
    for c in candidates:
        score, breakdown = compute_chunk_precision_score(
            chunk=c,
            query=query,
            standalone_query=standalone_query,
            max_bm25_in_batch=max_bm25,
        )
        scored_candidates.append((score, breakdown, c))

    # Sort descending by composite score
    scored_candidates.sort(key=lambda x: x[0], reverse=True)

    # Check for strong exact topic match in top candidates
    exact_topic_detected: Optional[str] = None
    exact_topic_codes: Set[str] = set()
    exact_topic_names: Set[str] = set()

    for score, breakdown, chunk in scored_candidates:
        match_type = breakdown.get("topic_match_type")
        if match_type in ("exact_topic", "phrase_in_topic"):
            t_name = chunk.get("topic_name") or chunk.get("title") or ""
            t_code = chunk.get("topic_code") or ""
            exact_topic_detected = t_name
            if t_code:
                exact_topic_codes.add(str(t_code).strip())
            if t_name:
                exact_topic_names.add(normalize_text_for_retrieval(t_name))
            break

    final_chunks: List[Dict[str, Any]] = []
    seen_content_signatures = set()

    if exact_topic_detected:
        logger.info(
            f"🎯 [PRECISION RETRIEVAL] Exact topic focus mode activated for: '{exact_topic_detected}'"
        )
        # In exact topic focus mode:
        # 1. Collect all chunks belonging to this exact topic family
        # 2. Prevent unrelated generic topics from polluting context
        for score, breakdown, chunk in scored_candidates:
            c_code = str(chunk.get("topic_code", "")).strip()
            c_name = normalize_text_for_retrieval(chunk.get("topic_name", ""))
            
            is_same_topic = (
                (c_code and c_code in exact_topic_codes)
                or (c_name and c_name in exact_topic_names)
                or breakdown.get("topic_match_type") in ("exact_topic", "phrase_in_topic")
            )

            if is_same_topic:
                raw_text = chunk.get("content") or chunk.get("topic_content") or ""
                sig = normalize_text_for_retrieval(raw_text[:150])
                if sig and sig in seen_content_signatures:
                    continue
                if sig:
                    seen_content_signatures.add(sig)
                
                chunk_copy = dict(chunk)
                chunk_copy["_precision_score"] = score
                chunk_copy["_precision_breakdown"] = breakdown
                final_chunks.append(chunk_copy)
                if len(final_chunks) >= top_k:
                    break

        # If we found chunks for the exact topic, return them focused
        if final_chunks:
            debug_info = [
                {
                    "topic_name": b["topic_name"],
                    "match_type": b["topic_match_type"],
                    "score": s,
                }
                for s, b, _ in scored_candidates
            ]
            return final_chunks, exact_topic_detected, debug_info

    # If no exact topic focus mode or fallback needed:
    # Use standard hybrid ranking
    for score, breakdown, chunk in scored_candidates:
        raw_text = chunk.get("content") or chunk.get("topic_content") or ""
        sig = normalize_text_for_retrieval(raw_text[:150])
        if sig and sig in seen_content_signatures:
            continue
        if sig:
            seen_content_signatures.add(sig)

        chunk_copy = dict(chunk)
        chunk_copy["_precision_score"] = score
        chunk_copy["_precision_breakdown"] = breakdown
        final_chunks.append(chunk_copy)

        if len(final_chunks) >= top_k:
            break

    debug_info = [
        {
            "topic_name": b["topic_name"],
            "match_type": b["topic_match_type"],
            "score": s,
        }
        for s, b, _ in scored_candidates
    ]

    return final_chunks, exact_topic_detected, debug_info
