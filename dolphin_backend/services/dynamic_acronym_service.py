"""
services/dynamic_acronym_service.py

Dynamic, self-learning maritime acronym and abbreviation service.
Provides:
1. Startup Database Harvester: Scans course_content topic titles for (ACR) and definition patterns.
2. Just-In-Time (JIT) Maritime LLM Resolver: Automatically classifies and expands unknown abbreviations
   using gpt-4o-mini with Redis & memory caching (takes ~180ms once, 0.00ms thereafter).
3. Runtime synchronization with services.maritime_acronyms.
"""

import os
from typing import Dict, List, Set, Optional, Any
import asyncio
import re
import json
from loguru import logger
from openai import AsyncOpenAI

from config import settings
from core.redis_client import redis_service

COMMON_NON_ACRONYMS: Set[str] = {
    "THE", "AND", "FOR", "NOT", "ALL", "NEW", "TOPIC", "PART", "TYPES", "TYPE",
    "BASIC", "HOW", "WHY", "WHAT", "WITH", "FROM", "INTO", "OVER", "UNDER",
    "AFTER", "BEFORE", "SOME", "MANY", "MOST", "PAGE", "UNIT", "LEVEL", "STAGE",
    "CLASS", "GRADE", "RULE", "RULES", "CASE", "CASES", "SHIP", "SHIPS", "CAN",
    "YOU", "YOUR", "OUR", "WHO", "WHOM", "WHICH", "THAT", "THIS", "THESE", "THOSE",
    "YES", "PLEASE", "TELL", "GIVE", "SHOW", "LIST", "VIEW", "TEST", "USER", "ROLE",
    "II", "III", "IV", "VI", "VII", "VIII", "IX", "XI", "XII",
    "OF", "BY", "AT", "IN", "ON", "TO", "UP", "DO", "NO", "SO", "IS", "IT", "AS", "AN", "AM", "HE", "WE", "OR", "IF", "GA",
    "PDF", "DOC", "TXT", "URL", "PPT", "HTML", "HTTP", "HTTPS",
    "MANUAL", "KEY", "STEP", "MAIN", "SAFE", "FIRE", "RISK", "LIFE", "ZERO", "GOOD",
    "BEST", "TRUE", "FREE", "CODE", "COST", "WORK", "DUTY", "REST", "TEAM", "CARE",
    "PLAN", "LOOK", "HELP", "LINE", "HOLD", "FALL", "STOP", "LEAD", "SEEN", "KEEP",
    "DONE", "SEEK", "FIND", "MAKE", "TAKE", "KNOW", "DAYS", "HOURS", "DATE", "NAME",
    "NOTE", "TERM", "GOAL", "NEED", "MUST", "HAVE", "BEEN", "WILL", "UPON", "ONLY",
    "ALSO", "EVEN", "JUST", "VERY", "MUCH", "MORE", "LESS", "SUCH", "LIKE", "SAME",
    "BOTH", "EACH", "ACT", "LAW", "WAY", "SET", "END", "TOP", "MEN", "MAN", "DAY",
    "WAR", "USE", "RUN", "OFF", "OIL", "AIR", "SEA", "GAS", "CARGO", "TANK", "WATER",
    "CREW", "PUMP", "DECK", "PORT"
}


class DynamicAcronymService:
    def __init__(self) -> None:
        # In-memory mapping: UPPERCASE acronym -> list of expansions/keywords
        self._memory_map: Dict[str, List[str]] = {}
        # In-memory negative cache: words confirmed NOT to be specialized maritime acronyms
        self._rejected_set: Set[str] = set()
        # JIT learned acronyms to persist
        self._jit_learned_map: Dict[str, List[str]] = {}
        self._openai_client: Optional[AsyncOpenAI] = None
        self._initialized: bool = False
        self._lock = asyncio.Lock()
        self._local_cache_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "storage", "learned_acronyms.json"
        )
        self._load_local_cache()

    def _load_local_cache(self) -> None:
        """Load previously JIT-learned acronyms and rejections from local disk cache."""
        try:
            if os.path.exists(self._local_cache_path):
                with open(self._local_cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    learned = data.get("learned", {})
                    rejected = data.get("rejected", [])
                    for acr, exps in learned.items():
                        self._register_acronym(acr, exps)
                        self._jit_learned_map[acr.upper()] = exps
                    for rej in rejected:
                        self._rejected_set.add(rej.upper())
                    if learned:
                        logger.info(f"Loaded {len(learned)} learned acronyms from local disk cache")
        except Exception as e:
            logger.debug(f"Failed loading local acronym cache: {e}")

    def _save_local_cache(self) -> None:
        """Persist JIT-learned acronyms and rejections to local disk cache."""
        try:
            os.makedirs(os.path.dirname(self._local_cache_path), exist_ok=True)
            with open(self._local_cache_path, "w", encoding="utf-8") as f:
                json.dump({
                    "learned": self._jit_learned_map,
                    "rejected": list(self._rejected_set)[:500]
                }, f, indent=2)
        except Exception as e:
            logger.debug(f"Failed saving local acronym cache: {e}")

    def _is_valid_acr_token(self, token: str) -> bool:
        """Verify token is a valid candidate acronym and not a numeric rule or course code."""
        t = token.strip().upper()
        if len(t) < 2 or len(t) > 8:
            return False
        if not any(c.isalpha() for c in t):
            return False
        if sum(1 for c in t if c.isalpha()) < 2:
            return False
        if t in COMMON_NON_ACRONYMS:
            return False
        # Exclude numeric course codes like Q112A, 2203A, 01A
        if re.search(r'\d{2,}', t) and t not in {"MLC2006", "MARPOL7378"}:
            return False
        return True

    def _get_openai_client(self) -> AsyncOpenAI:
        if self._openai_client is None:
            self._openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
        return self._openai_client

    def _clean_expansion(self, text: str) -> str:
        """Clean symbols and extra whitespace from an expansion string."""
        t = re.sub(r'[^a-zA-Z0-9\s\-]', ' ', text).strip()
        return re.sub(r'\s+', ' ', t).lower()

    async def harvest_course_acronyms(self, pool=None) -> int:
        """
        Scans distinct course_content topic names from PostgreSQL to harvest acronyms.
        Uses clean, high-confidence regexes without noisy fragments.
        """
        if self._initialized:
            return len(self._memory_map)

        async with self._lock:
            if self._initialized:
                return len(self._memory_map)

            t0 = asyncio.get_event_loop().time()
            try:
                if pool is None:
                    from models.database import get_pool
                    pool = await get_pool()

                rows = await pool.fetch(
                    "SELECT DISTINCT topic_name FROM course_content WHERE topic_name IS NOT NULL"
                )
            except Exception as e:
                logger.warning(f"⚠️ [Dynamic Acronyms] DB harvesting skipped (DB unavailable): {e}")
                return len(self._memory_map)

            # Regex 1: Full Name (ACR) e.g. "Boil-Off Gas (BOG)", "Emergency Escape Breathing Device (EEBD)"
            p1 = re.compile(r'([A-Za-z\s\-]{3,45})\s*\(([A-Z0-9]{2,8})\)')
            # Regex 2: ACR (Full Name) e.g. "ECDIS (Electronic Chart Display...)"
            p2 = re.compile(r'\b([A-Z0-9]{2,8})\s*\(([A-Za-z\s\-]{3,45})\)')
            # Regex 3: ACR - Full Name e.g. "ALARP - As Low As Reasonably Practicable"
            p3 = re.compile(r'\b([A-Z0-9]{2,8})\s*[-:]\s*([A-Za-z\s\-]{4,45})\b')

            NOISE_EXPANSIONS = {
                "explain", "introduction", "overview", "definition", "basics", "summary",
                "test", "quiz", "general", "activity", "examples", "case study", "guidelines",
                "types", "part", "requirements", "compliance", "verification", "planning"
            }

            discovered = 0
            for r in rows:
                tname = r["topic_name"] or ""

                for m in p1.finditer(tname):
                    full, acr = self._clean_expansion(m.group(1)), m.group(2).upper()
                    if self._is_valid_acr_token(acr) and len(full) >= 4 and full not in NOISE_EXPANSIONS:
                        self._register_acronym(acr, [full])
                        discovered += 1

                for m in p2.finditer(tname):
                    acr, full = m.group(1).upper(), self._clean_expansion(m.group(2))
                    if self._is_valid_acr_token(acr) and len(full) >= 4 and full not in NOISE_EXPANSIONS:
                        self._register_acronym(acr, [full])
                        discovered += 1

                for m in p3.finditer(tname):
                    acr, full = m.group(1).upper(), self._clean_expansion(m.group(2))
                    if self._is_valid_acr_token(acr) and len(full) >= 6 and len(full.split()) >= 2 and full not in NOISE_EXPANSIONS:
                        self._register_acronym(acr, [full])
                        discovered += 1

            self._initialized = True
            dur = asyncio.get_event_loop().time() - t0
            logger.success(
                f"🚢 [Dynamic Acronyms] Harvested {len(self._memory_map)} unique course acronyms "
                f"from {len(rows)} topics in {dur:.2f}s"
            )
            return len(self._memory_map)

    def _register_acronym(self, acronym: str, expansions: List[str]) -> None:
        """Register an acronym into local memory and sync with services.maritime_acronyms."""
        acr = acronym.strip().upper()
        if not acr or acr in COMMON_NON_ACRONYMS or not any(c.isalpha() for c in acr):
            return

        clean_exps = [e.strip().lower() for e in expansions if e and len(e.strip()) >= 2]
        if not clean_exps:
            return

        if acr not in self._memory_map:
            self._memory_map[acr] = []
        for exp in clean_exps:
            if exp not in self._memory_map[acr]:
                self._memory_map[acr].append(exp)

        # Sync runtime structures in maritime_acronyms
        try:
            from services.maritime_acronyms import MARITIME_ACRONYMS_MAP, KNOWN_ACRONYMS_SET
            if acr not in MARITIME_ACRONYMS_MAP:
                MARITIME_ACRONYMS_MAP[acr] = list(self._memory_map[acr])
            else:
                for exp in self._memory_map[acr]:
                    if exp not in MARITIME_ACRONYMS_MAP[acr]:
                        MARITIME_ACRONYMS_MAP[acr].append(exp)
            KNOWN_ACRONYMS_SET.add(acr)
        except Exception:
            pass

    def get_expansion_sync(self, acronym: str) -> List[str]:
        """Synchronous 0.00ms lookup from memory."""
        if not acronym:
            return []
        return self._memory_map.get(acronym.strip().upper(), [])

    def is_known_acronym(self, token: str) -> bool:
        """Check if token is recognized as a maritime acronym in memory."""
        if not token:
            return False
        return token.strip().upper() in self._memory_map

    async def resolve_acronym(self, token: str) -> Optional[List[str]]:
        """
        Just-In-Time (JIT) resolution for an unknown candidate acronym or abbreviation.
        1. Checks memory map (0.00ms).
        2. Checks rejection set (0.00ms).
        3. Checks Redis cache (if connected).
        4. Queries gpt-4o-mini once (~180ms), caches permanently in Redis and memory.
        """
        if not token:
            return None

        token_clean = token.strip().upper()
        if len(token_clean) < 2 or len(token_clean) > 12:
            return None
        if token_clean in COMMON_NON_ACRONYMS:
            return None

        # 1. Memory check
        if token_clean in self._memory_map:
            return self._memory_map[token_clean]
        if token_clean in self._rejected_set:
            return None

        # 2. Redis check
        redis_key = f"dolphin:dynamic_acronym:{token_clean}"
        try:
            if redis_service.is_connected() and redis_service.redis:
                cached_val = await redis_service.redis.get(redis_key)
                if cached_val:
                    if cached_val == "__NOT_MARITIME__":
                        self._rejected_set.add(token_clean)
                        self._save_local_cache()
                        return None
                    try:
                        exp_list = json.loads(cached_val)
                        if isinstance(exp_list, list):
                            self._register_acronym(token_clean, exp_list)
                            self._jit_learned_map[token_clean] = exp_list
                            self._save_local_cache()
                            return exp_list
                    except Exception:
                        pass
        except Exception as e:
            logger.debug(f"Redis lookup for acronym {token_clean} failed: {e}")

        # 3. LLM JIT Resolver
        logger.info(f"🔍 [Dynamic Acronyms] Resolving unknown abbreviation '{token_clean}' via JIT LLM...")
        try:
            client = self._get_openai_client()
            system_prompt = (
                "You are an expert maritime training specialist, ship master, naval architect, and maritime legal/labour advisor.\n"
                "Determine if the given abbreviation or code is a recognized, specialized maritime, shipping, "
                "seafarer employment / MLC 2006 / crew management (e.g. CBA = Collective Bargaining Agreement, SEA = Seafarers Employment Agreement), "
                "vessel operations, port state control, cargo handling, marine safety (e.g. BBS = Behavior-Based Safety), "
                "marine engineering, bridge navigation, or IMO / ILO regulatory abbreviation or term.\n"
                "CRITICAL: Common everyday English acronyms or internet slang (e.g., ASAP, FYI, LOL, BRB, OMG, ETC) "
                "are NOT specialized maritime terms and must return is_maritime: false.\n"
                "Respond ONLY in valid JSON format:\n"
                "{\n"
                '  "is_maritime": true or false,\n'
                '  "full_name": "Full descriptive technical title",\n'
                '  "keywords": ["2-4 relevant maritime technical keywords"]\n'
                "}"
            )

            resp = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Abbreviation: {token_clean}"}
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
                max_tokens=80,
            )

            data = json.loads(resp.choices[0].message.content)
            is_maritime = bool(data.get("is_maritime"))

            if is_maritime:
                full_name = self._clean_expansion(str(data.get("full_name") or ""))
                kws = [self._clean_expansion(str(k)) for k in data.get("keywords", []) if k]
                expansions = [full_name] + [k for k in kws if k and k != full_name]
                expansions = [e for e in expansions if e]

                if expansions:
                    self._register_acronym(token_clean, expansions)
                    self._jit_learned_map[token_clean] = expansions
                    self._save_local_cache()
                    logger.success(
                        f"✨ [Dynamic Acronyms] JIT learned maritime abbreviation '{token_clean}': {expansions}"
                    )

                    # Cache in Redis for 30 days
                    try:
                        if redis_service.is_connected() and redis_service.redis:
                            await redis_service.redis.setex(
                                redis_key,
                                30 * 86400,
                                json.dumps(expansions)
                            )
                    except Exception:
                        pass

                    return expansions

            # If not maritime, cache negative result
            self._rejected_set.add(token_clean)
            self._save_local_cache()
            try:
                if redis_service.is_connected() and redis_service.redis:
                    await redis_service.redis.setex(
                        redis_key,
                        7 * 86400,
                        "__NOT_MARITIME__"
                    )
            except Exception:
                pass
            return None

        except Exception as e:
            logger.warning(f"⚠️ [Dynamic Acronyms] JIT resolution failed for '{token_clean}': {e}")
            return None


# Global singleton instance
dynamic_acronym_service = DynamicAcronymService()
