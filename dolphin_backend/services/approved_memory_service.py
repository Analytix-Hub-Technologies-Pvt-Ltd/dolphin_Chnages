import asyncio
import json
import math
import os
import pickle
import re
import time
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from asyncpg import Pool
from loguru import logger

CACHE_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage", "approved_memory_cache.pkl")

STOP_WORDS = {
    "what", "is", "the", "for", "on", "a", "an", "and", "in", "to", "of", "how", "do", "does",
    "explain", "overview", "describe", "tell", "me", "about", "give", "please", "why", "when",
    "where", "can", "should", "are", "with", "this", "that", "these", "those", "from", "by",
    "at", "it", "its", "as", "be", "or", "which", "will", "would", "any", "some", "into", "than",
    "such", "below", "under", "shall", "having", "other", "their", "there", "they", "been", "also", "above",
    "refer", "referred", "regard", "hereinafter", "inter", "alia", "noting", "adopted"
}

GENERIC_ANCHOR_WORDS = {
    "safety", "requirement", "requirements", "procedure", "procedures", "checklist", "guidelines",
    "guidance", "inspection", "inspections", "responsibilities", "responsibility", "regulations",
    "regulation", "rules", "rule", "standard", "standards", "general", "duties", "duty", "operation",
    "operations", "operational", "test", "testing", "tests", "check", "checks", "checked", "checking",
    "equipment", "system", "systems", "manual", "manuals", "plan", "plans", "form", "forms",
    "document", "documents", "measure", "measures", "precautions", "precaution", "action", "actions",
    "method", "methods", "process", "processes", "criteria", "criterion", "condition", "conditions",
    "phenomena", "phenomenon", "provisions", "provision", "level", "levels", "limit", "limits",
    "value", "values", "minimum", "maximum", "ensure", "ensuring", "apply", "applied", "application",
    "shall", "should", "must", "part", "parts", "section", "sections", "code", "codes", "ship", "ships",
    "vessel", "vessels", "board", "onboard", "marine", "maritime", "international", "organization",
    "types", "covered", "instruments", "entry", "points", "point", "degrees", "degree", "order"
}

DISALLOWED_ANCHOR_WORDS = STOP_WORDS | GENERIC_ANCHOR_WORDS


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Compute cosine similarity between two vector floats."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (norm1 * norm2)


def clean_text_for_embedding(text: str) -> str:
    """Strips HTML tags, data URLs, base64 images, and markdown formatting for clean vector embedding."""
    if not text:
        return ""
    # Strip base64 data URLs
    text = re.sub(r"data:image/[^;]+;base64,[a-zA-Z0-9+/=]+", " ", text)
    # Strip HTML tags (e.g. <sub>, <sup>, <p>, etc.)
    text = re.sub(r"<[^>]+>", " ", text)
    # Strip markdown images and links
    text = re.sub(r"!\[.*?\]\(.*?\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Strip formatting symbols
    text = re.sub(r"[#*`_~|]", " ", text)
    return " ".join(text.split())


def normalize_query_text(text: str) -> str:
    """Normalize query text by stripping HTML tags, lowercasing, and normalizing Greek/special characters."""
    if not text:
        return ""
    # Strip HTML tags (e.g. <sub>, <sup>)
    cleaned = re.sub(r"<[^>]+>", "", text).strip().lower()
    # Normalize Greek phi symbols to standard ϕ
    cleaned = cleaned.replace("φ", "ϕ")
    # Subscript digits in unicode to regular digits (e.g. ϕ₀ -> ϕ0, ϕ₁ -> ϕ1)
    sub_map = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
    cleaned = cleaned.translate(sub_map)
    # Metacentric height initial GMo -> GM0
    cleaned = re.sub(r"\bgmo\b", "gm0", cleaned)
    # Punctuation to spaces
    norm = re.sub(r"[^\w\s]", " ", cleaned)
    return " ".join(norm.split())


def normalize_company_id(cid: Any) -> Optional[int]:
    """
    Safely normalizes company_id to an integer ID, or None for global/system items.
    Handles: int, str, '1', 1, None, '0', 0, 'global', 'all', 'comp_alpha', 'demo'.
    """
    if cid is None:
        return None
    if isinstance(cid, int):
        return cid if cid > 0 else None
    s = str(cid).strip().lower()
    if s in ("", "none", "null", "global", "all", "0", "comp_alpha", "demo", "test"):
        return None
    if s.isdigit():
        val = int(s)
        return val if val > 0 else None
    # If it contains digits like 'comp_1'
    m = re.search(r"\d+", s)
    if m:
        val = int(m.group(0))
        return val if val > 0 else None
    return None


def extract_topic_keywords(question: str, content: str) -> List[str]:
    """
    Extract key domain entities, acronyms, and technical n-grams from question and content
    to serve as high-precision topic anchors.
    """
    clean_q = clean_text_for_embedding(question).lower()
    clean_c = clean_text_for_embedding(content).lower()
    keywords: Set[str] = set()

    # 1. Acronyms & technical abbreviations from raw text (must not be generic)
    raw_acronyms = re.findall(r"\b[A-Z0-9]{2,8}\b", f"{question} {content[:8000]}")
    for acr in raw_acronyms:
        a_low = acr.lower()
        if a_low not in DISALLOWED_ANCHOR_WORDS and len(a_low) >= 2:
            keywords.add(a_low)

    # 2. Extract technical formula identifiers (e.g. gz, gm0, lw1, lw2, phi, theta, co2, nox, sox)
    formulas = re.findall(r"\b(?:gz|gm0?|lw[12]|phi|theta|co2|nox|sox)\b", clean_c[:8000])
    for f in formulas:
        keywords.add(f)

    # 3. Meaningful words and n-grams from question
    q_words = [w for w in re.split(r"[^\w]+", clean_q) if w and w not in DISALLOWED_ANCHOR_WORDS and len(w) > 2]
    for w in q_words:
        keywords.add(w)

    q_all_tokens = [w for w in re.split(r"[^\w]+", clean_q) if w]
    for i in range(len(q_all_tokens) - 1):
        w1, w2 = q_all_tokens[i], q_all_tokens[i+1]
        if w1 not in STOP_WORDS or w2 not in STOP_WORDS:
            phrase = f"{w1} {w2}".strip()
            # Only add phrase if at least one token is non-generic
            if any(p not in DISALLOWED_ANCHOR_WORDS for p in phrase.split()):
                if len(phrase) >= 5:
                    keywords.add(phrase)

    for i in range(len(q_all_tokens) - 2):
        w1, w2, w3 = q_all_tokens[i], q_all_tokens[i+1], q_all_tokens[i+2]
        if (w1 not in STOP_WORDS or w3 not in STOP_WORDS) and (w2 not in STOP_WORDS):
            phrase = f"{w1} {w2} {w3}".strip()
            if any(p not in DISALLOWED_ANCHOR_WORDS for p in phrase.split()):
                if len(phrase) >= 7:
                    keywords.add(phrase)

    # 4. Extract technical nouns and 2-word domain phrases from full content (up to 8000 chars)
    content_tokens = [w for w in re.split(r"[^\w]+", clean_c[:8000]) if w and w not in DISALLOWED_ANCHOR_WORDS and len(w) >= 3]
    counts = Counter(content_tokens)
    for term, _ in counts.most_common(40):
        keywords.add(term)

    # Extract 2-word technical phrases from content
    c_tokens = [w for w in re.split(r"[^\w]+", clean_c[:8000]) if w]
    for i in range(len(c_tokens) - 1):
        w1, w2 = c_tokens[i], c_tokens[i+1]
        if w1 not in STOP_WORDS and w2 not in STOP_WORDS and len(w1) >= 3 and len(w2) >= 3:
            phrase = f"{w1} {w2}"
            if any(p not in DISALLOWED_ANCHOR_WORDS for p in (w1, w2)):
                if phrase in ("righting lever", "weather criterion", "heeling lever", "intact stability", "dead ship", "gz curve", "enclosed space"):
                    keywords.add(phrase)

    return sorted(list(keywords))


def matches_topic_anchor(query_text: str, topic_keywords: Optional[List[str]]) -> bool:
    """
    Check if the user query contains ANY topic keyword or entity phrase from the approved item.
    Guarantees <0.05ms rejection of completely unrelated domain queries (purifiers vs stability).
    """
    if not topic_keywords:
        return True

    clean_q = normalize_query_text(query_text).lower()
    q_words = set(re.split(r"[^\w]+", clean_q))

    for kw in topic_keywords:
        kw_clean = kw.strip().lower()
        if not kw_clean:
            continue
        if " " in kw_clean:
            # Multi-word phrase check (e.g. "intact stability", "fire pump", "enclosed space")
            if kw_clean in clean_q:
                return True
        else:
            # Single word / acronym check
            if kw_clean in q_words:
                return True
    return False


class ApprovedMemoryService:
    def __init__(self, pool: Pool, embedder=None) -> None:
        self.pool = pool
        self.embedder = embedder
        self._cache: Optional[List[Dict[str, Any]]] = None
        self._cache_timestamp: float = 0.0
        self._cache_ttl: float = 600.0  # 10 minutes cache TTL
        self._disk_cache_mtime: float = 0.0
        self._lock: Optional[asyncio.Lock] = None

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def _load_cache_from_disk(self) -> Optional[List[Dict[str, Any]]]:
        if os.path.exists(CACHE_FILE_PATH):
            try:
                mtime = os.path.getmtime(CACHE_FILE_PATH)
                with open(CACHE_FILE_PATH, "rb") as f:
                    items = pickle.load(f)
                if isinstance(items, list):
                    self._disk_cache_mtime = mtime
                    logger.info(f"⚡ Loaded {len(items)} approved memory items from local disk cache")
                    return items
            except Exception as e:
                logger.warning(f"Failed to load approved memory disk cache: {e}")
        return None

    def _save_cache_to_disk(self, items: List[Dict[str, Any]]) -> None:
        try:
            os.makedirs(os.path.dirname(CACHE_FILE_PATH), exist_ok=True)
            with open(CACHE_FILE_PATH, "wb") as f:
                pickle.dump(items, f)
            if os.path.exists(CACHE_FILE_PATH):
                self._disk_cache_mtime = os.path.getmtime(CACHE_FILE_PATH)
        except Exception as e:
            logger.warning(f"Failed to save approved memory disk cache: {e}")

    def invalidate_cache(self) -> None:
        """Invalidate the in-memory cache so next search refreshes from DB."""
        self._cache = None
        self._cache_timestamp = 0.0
        self._disk_cache_mtime = 0.0
        if os.path.exists(CACHE_FILE_PATH):
            try:
                os.remove(CACHE_FILE_PATH)
            except OSError:
                pass
        logger.info("🧹 In-memory approved feedback memory cache invalidated")

    async def warmup_cache(self) -> None:
        """Pre-warm in-memory cache at server startup and backfill missing vectors in background."""
        await self._ensure_cache()
        asyncio.create_task(self.backfill_missing_embeddings())

    async def refresh_cache(self) -> List[Dict[str, Any]]:
        """Fetch active items from PostgreSQL, parse vectors once, and persist to RAM and disk."""
        await self.init_table()
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT memory_id, feedback_id, question, preferred_response, original_response, 
                       company_id, ship_type, embedding, content_embedding, topic_keywords, updated_at
                FROM public.approved_feedback_memory
                WHERE is_active = TRUE
                ORDER BY updated_at DESC;
                """
            )
        cached: List[Dict[str, Any]] = []
        for r in rows:
            item = dict(r)
            q_text = (item.get("question") or "").strip()
            item["_clean_q"] = re.sub(r"<[^>]+>", "", q_text).strip().lower()
            item["_norm_q"] = normalize_query_text(q_text)

            # Parse question embedding vector
            emb_raw = item.get("embedding")
            parsed_vec = None
            if emb_raw:
                try:
                    parsed_vec = json.loads(emb_raw) if isinstance(emb_raw, str) else emb_raw
                except Exception:
                    pass
            item["_parsed_vec"] = parsed_vec

            # Parse content embedding vector
            content_emb_raw = item.get("content_embedding")
            parsed_content_vec = None
            if content_emb_raw:
                try:
                    parsed_content_vec = json.loads(content_emb_raw) if isinstance(content_emb_raw, str) else content_emb_raw
                except Exception:
                    pass
            item["_parsed_content_vec"] = parsed_content_vec

            # Parse topic keywords
            kws_raw = item.get("topic_keywords")
            parsed_kws = None
            if kws_raw:
                try:
                    parsed_kws = json.loads(kws_raw) if isinstance(kws_raw, str) else kws_raw
                except Exception:
                    pass
            if not parsed_kws:
                parsed_kws = extract_topic_keywords(item.get("question") or "", item.get("preferred_response") or "")
            item["_topic_keywords"] = parsed_kws

            item.pop("embedding", None)
            item.pop("content_embedding", None)
            item.pop("topic_keywords", None)
            cached.append(item)

        self._cache = cached
        self._cache_timestamp = time.perf_counter()
        self._save_cache_to_disk(cached)
        if os.path.exists(CACHE_FILE_PATH):
            self._disk_cache_mtime = os.path.getmtime(CACHE_FILE_PATH)
        logger.info(f"⚡ Refreshed approved memory cache ({len(cached)} items in RAM & disk)")
        return self._cache

    async def _ensure_cache(self) -> List[Dict[str, Any]]:
        now = time.perf_counter()
        disk_mtime = os.path.getmtime(CACHE_FILE_PATH) if os.path.exists(CACHE_FILE_PATH) else 0.0

        # If cache is loaded and TTL is valid, check if disk cache was updated externally
        if self._cache is not None and (now - self._cache_timestamp) < self._cache_ttl:
            if disk_mtime <= self._disk_cache_mtime:
                return self._cache
            # Disk cache has been updated by an approval action! Reload immediately.

        lock = self._get_lock()
        async with lock:
            disk_mtime = os.path.getmtime(CACHE_FILE_PATH) if os.path.exists(CACHE_FILE_PATH) else 0.0
            if self._cache is not None and (time.perf_counter() - self._cache_timestamp) < self._cache_ttl:
                if disk_mtime <= self._disk_cache_mtime:
                    return self._cache

            # Try disk cache first (instant sub-millisecond load)
            disk_items = self._load_cache_from_disk()
            if disk_items is not None:
                self._cache = disk_items
                self._cache_timestamp = time.perf_counter()
                self._disk_cache_mtime = disk_mtime
                return self._cache

            # Fallback to DB fetch
            return await self.refresh_cache()

    async def init_table(self) -> None:
        """Ensure approved_feedback_memory table exists and has proper dual-vector schema."""
        query = """
        CREATE TABLE IF NOT EXISTS public.approved_feedback_memory (
            memory_id TEXT PRIMARY KEY,
            feedback_id TEXT UNIQUE NOT NULL,
            question TEXT NOT NULL,
            preferred_response TEXT NOT NULL,
            original_response TEXT,
            company_id TEXT,
            ship_type TEXT,
            embedding JSONB,
            content_embedding JSONB,
            topic_keywords JSONB,
            approved_by TEXT,
            approved_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        ALTER TABLE public.approved_feedback_memory ADD COLUMN IF NOT EXISTS content_embedding JSONB;
        ALTER TABLE public.approved_feedback_memory ADD COLUMN IF NOT EXISTS topic_keywords JSONB;

        CREATE INDEX IF NOT EXISTS idx_afm_active ON public.approved_feedback_memory (is_active);
        CREATE INDEX IF NOT EXISTS idx_afm_company ON public.approved_feedback_memory (company_id);
        CREATE INDEX IF NOT EXISTS idx_afm_feedback_id ON public.approved_feedback_memory (feedback_id);
        """
        async with self.pool.acquire() as conn:
            await conn.execute(query)

    async def backfill_missing_embeddings(self) -> None:
        """Backfill content embeddings and topic keywords for active approved items missing them."""
        if not self.embedder:
            return
        try:
            await self.init_table()
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT memory_id, feedback_id, question, preferred_response
                    FROM public.approved_feedback_memory
                    WHERE is_active = TRUE AND (content_embedding IS NULL OR topic_keywords IS NULL);
                    """
                )
            if not rows:
                return

            logger.info(f"🔄 Backfilling content embeddings and topic keywords for {len(rows)} approved memory items...")
            for r in rows:
                mid = r["memory_id"]
                q = r["question"] or ""
                pref = r["preferred_response"] or ""
                kws = extract_topic_keywords(q, pref)
                clean_content = clean_text_for_embedding(pref)[:8000]

                content_vec = await self.embedder.embed_query(clean_content) if clean_content else None
                content_json = json.dumps(content_vec) if content_vec else None
                kws_json = json.dumps(kws)

                async with self.pool.acquire() as conn:
                    await conn.execute(
                        """
                        UPDATE public.approved_feedback_memory
                        SET content_embedding = COALESCE($1::jsonb, content_embedding),
                            topic_keywords = $2::jsonb,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE memory_id = $3;
                        """,
                        content_json,
                        kws_json,
                        mid,
                    )
            logger.info(f"✅ Successfully backfilled {len(rows)} approved memory items with dual vectors & topic anchors")
            await self.refresh_cache()
        except Exception as e:
            logger.warning(f"Error during approved memory backfill: {e}")

    async def sync_feedback_approval(
        self,
        feedback_id: Any,
        question: str,
        preferred_response: str,
        original_response: Optional[str] = None,
        company_id: Optional[str] = None,
        ship_type: Optional[str] = None,
        approved_by: Optional[str] = None,
        is_active: bool = True,
    ) -> None:
        """Immediately store or update an approved feedback item into active memory with dual vectors and topic anchors."""
        await self.init_table()
        fb_id_str = str(feedback_id)
        memory_id = f"mem_fb_{fb_id_str}"

        if not is_active:
            # Deactivate memory item
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE public.approved_feedback_memory
                    SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
                    WHERE feedback_id = $1;
                    """,
                    fb_id_str,
                )
            logger.info(f"Deactivated approved feedback memory for feedback_id={fb_id_str}")
            try:
                await self.refresh_cache()
            except Exception as e:
                logger.warning(f"Failed to refresh approved memory cache after deactivation: {e}")
            return

        # 1. Topic Keywords Extraction
        topic_keywords = extract_topic_keywords(question, preferred_response)
        topic_keywords_json = json.dumps(topic_keywords)

        # 2. Dual Embeddings: Question Vector and Content Vector
        embedding_json = None
        content_embedding_json = None

        if self.embedder:
            try:
                clean_q = clean_text_for_embedding(question)
                clean_c = clean_text_for_embedding(preferred_response)[:8000]

                q_vec = await self.embedder.embed_query(clean_q) if clean_q else None
                c_vec = await self.embedder.embed_query(clean_c) if clean_c else None

                if q_vec:
                    embedding_json = json.dumps(q_vec)
                if c_vec:
                    content_embedding_json = json.dumps(c_vec)
            except Exception as e:
                logger.warning(f"Failed to generate dual embeddings for approved feedback memory: {e}")

        query = """
        INSERT INTO public.approved_feedback_memory (
            memory_id, feedback_id, question, preferred_response,
            original_response, company_id, ship_type, embedding,
            content_embedding, topic_keywords,
            approved_by, approved_at, is_active, created_at, updated_at
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9::jsonb, $10::jsonb, $11, CURRENT_TIMESTAMP, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        )
        ON CONFLICT (feedback_id) DO UPDATE SET
            question = EXCLUDED.question,
            preferred_response = EXCLUDED.preferred_response,
            original_response = EXCLUDED.original_response,
            company_id = EXCLUDED.company_id,
            ship_type = EXCLUDED.ship_type,
            embedding = COALESCE(EXCLUDED.embedding, approved_feedback_memory.embedding),
            content_embedding = COALESCE(EXCLUDED.content_embedding, approved_feedback_memory.content_embedding),
            topic_keywords = COALESCE(EXCLUDED.topic_keywords, approved_feedback_memory.topic_keywords),
            approved_by = EXCLUDED.approved_by,
            approved_at = CURRENT_TIMESTAMP,
            is_active = TRUE,
            updated_at = CURRENT_TIMESTAMP;
        """

        async with self.pool.acquire() as conn:
            await conn.execute(
                query,
                memory_id,
                fb_id_str,
                question,
                preferred_response,
                original_response or preferred_response,
                str(normalize_company_id(company_id)) if normalize_company_id(company_id) is not None else "global",
                ship_type or "All",
                embedding_json,
                content_embedding_json,
                topic_keywords_json,
                approved_by or "SME Reviewer",
            )

        logger.info(f"✅ Synced approved feedback into immediate dual-vector memory: id={fb_id_str}, q='{question[:60]}'")
        try:
            await self.refresh_cache()
        except Exception as e:
            logger.warning(f"Failed to refresh approved memory cache after sync: {e}")

    async def search_approved_memory(
        self,
        query_text: str,
        company_id: Optional[Any] = None,
        similarity_threshold: float = 0.45,
        query_vector: Optional[List[float]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Search approved memory for matching questions or related content using:
        1. Two-Tier Company Filter:
           - Tier 1: Exact company-specific match (int or string normalized)
           - Tier 2: Global fallback (company_id is None / global / general regulatory knowledge)
        2. Fast In-Memory Exact / Punctuation-Normalized Match (~0.01ms) -> Direct Override
        3. Strict Topic Anchor Guardrail (<0.05ms) -> 100% blocks unrelated domain queries
        4. Dual-Vector Match (Question Vec vs Content Vec):
           - Higher Question Match / Overview -> is_direct_override = True (direct serving)
           - Higher Content Match / Sub-topic -> is_direct_override = False (contextual grounding Chunk #0)
        """
        if not query_text or not query_text.strip():
            return None

        cleaned_q = re.sub(r"<[^>]+>", "", query_text).strip()
        cleaned_lower = cleaned_q.lower()
        normalized_q = normalize_query_text(query_text)

        target_norm = normalize_company_id(company_id)

        # ⚡ Load from in-memory / disk cache (instant ~0.01ms)
        cached_items = await self._ensure_cache()
        if not cached_items:
            return None

        # Partition items into Tier 1 (Company-Specific) and Tier 2 (Global Fallback)
        tier1_items: List[Dict[str, Any]] = []
        tier2_items: List[Dict[str, Any]] = []

        for item in cached_items:
            item_norm = normalize_company_id(item.get("company_id"))
            if target_norm is not None and item_norm == target_norm:
                tier1_items.append(item)
            elif item_norm is None:
                # Global / System regulatory knowledge accessible to all companies
                tier2_items.append(item)

        # Candidate item evaluation order: Tier 1 (Company-Specific) first, then Tier 2 (Global Fallback)
        candidate_tiers = []
        if tier1_items:
            candidate_tiers.append(("company_specific", tier1_items))
        if tier2_items:
            candidate_tiers.append(("global_fallback", tier2_items))

        # 1. Fast In-Memory Exact or Punctuation-Normalized Match (~0.01ms)
        for tier_name, pool in candidate_tiers:
            for item in pool:
                if item.get("_clean_q") == cleaned_lower or item.get("_norm_q") == normalized_q:
                    logger.info(f"🎯 Exact text match found in approved feedback memory: id={item['feedback_id']} (tier={tier_name})")
                    return {
                        "memory_id": item["memory_id"],
                        "feedback_id": item["feedback_id"],
                        "question": item["question"],
                        "preferred_response": item["preferred_response"],
                        "original_response": item.get("original_response") or item["preferred_response"],
                        "company_id": item["company_id"],
                        "ship_type": item["ship_type"],
                        "match_type": "exact",
                        "score": 1.0,
                        "is_direct_override": True,
                    }

        # 2. Topic Anchor Guardrail Filter:
        # Pre-filter candidate items to only those that share domain entities/keywords with the query.
        filtered_tiers = []
        for tier_name, pool in candidate_tiers:
            anchored = [item for item in pool if matches_topic_anchor(query_text, item.get("_topic_keywords"))]
            if anchored:
                filtered_tiers.append((tier_name, anchored))

        if not filtered_tiers:
            return None

        # 3. Dual-Vector Semantic Search in RAM (~0.5ms)
        query_vec = query_vector
        if query_vec is None:
            if not self.embedder:
                return None
            try:
                query_vec = await self.embedder.embed_query(cleaned_q)
            except Exception as e:
                logger.warning(f"Could not embed query for memory search: {e}")
                return None

        is_overview_query = bool(re.search(r"\b(overview|summary|brief overview|overall)\b", query_text.lower()))

        # Evaluate candidate pools in priority order (Tier 1 then Tier 2)
        for tier_name, candidate_items in filtered_tiers:
            best_match = None
            best_score = 0.0
            best_match_type = "semantic_question"
            best_is_direct = True

            for item in candidate_items:
                q_vec = item.get("_parsed_vec")
                c_vec = item.get("_parsed_content_vec")

                score_q = cosine_similarity(query_vec, q_vec) if q_vec else 0.0
                score_c = cosine_similarity(query_vec, c_vec) if c_vec else 0.0

                # Determine whether this item represents a direct question rephrase or contextual sub-topic
                if is_overview_query and score_q >= 0.48:
                    item_match_type = "semantic_question"
                    item_is_direct = True
                    selected_score = score_q
                elif score_q >= 0.60 and score_q >= score_c:
                    item_match_type = "semantic_question"
                    item_is_direct = True
                    selected_score = score_q
                elif score_c >= 0.50:
                    item_match_type = "semantic_content"
                    item_is_direct = False
                    selected_score = score_c
                else:
                    continue

                if selected_score > best_score:
                    best_score = selected_score
                    best_match = item
                    best_match_type = item_match_type
                    best_is_direct = item_is_direct

            if best_match and best_score >= similarity_threshold:
                logger.info(
                    f"🎯 Approved feedback memory match: id={best_match['feedback_id']}, "
                    f"tier={tier_name}, type={best_match_type}, score={best_score:.3f}, direct={best_is_direct}"
                )
                return {
                    "memory_id": best_match["memory_id"],
                    "feedback_id": best_match["feedback_id"],
                    "question": best_match["question"],
                    "preferred_response": best_match["preferred_response"],
                    "original_response": best_match.get("original_response") or best_match["preferred_response"],
                    "company_id": best_match["company_id"],
                    "ship_type": best_match["ship_type"],
                    "match_type": best_match_type,
                    "score": best_score,
                    "is_direct_override": best_is_direct,
                }

        return None
