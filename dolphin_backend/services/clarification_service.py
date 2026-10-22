"""
Clarification Service  ("Did you mean...?")

When a learner types a bare, under-specified term such as "temperature" or
"pressure", the course material can contain several unrelated meanings of it
(cargo temperature, engine cooling temperature, ...). Instead of guessing and
dumping the wrong topic, Dolphin asks which one the learner means and offers
clickable options, like ChatGPT does.

Design notes
------------
* Deterministic first: candidates come from topic names in the vector store and
  from the chunks that retrieval already returned. No extra LLM call is needed.
* Optional LLM polish: when enabled, a single small JSON call groups the
  candidates into <= N meaningful "meanings" with friendly labels. It has a
  hard timeout and silently falls back to the deterministic options.
* Stateless on the server: the pending question is stored on the assistant
  message (``clarification`` key), so a typed reply such as "2" or "cargo" can
  be resolved on the next turn without any extra session store.
* Never blocks a clear question. Only 1-2 "focus word" queries are eligible and
  quiz/summary requests, follow-ups and SME-approved answers bypass it. Bare acronyms
  (e.g. "SMS") ARE clarified: options come from the topics that mention them.
"""

from __future__ import annotations

import asyncio
import json
import random
import re
import urllib.parse
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Iterable, List, Optional, Sequence

from loguru import logger


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

# Words that carry no topic information. Stripped before deciding whether a
# query is "just a term".
_FILLER_WORDS = {
    "a", "an", "the", "of", "in", "on", "for", "to", "and", "or", "about", "regarding",
    "what", "whats", "what's", "which", "who", "when", "where", "why", "how", "is", "are",
    "was", "were", "do", "does", "did", "can", "could", "would", "should", "will",
    "tell", "me", "us", "give", "show", "explain", "describe", "define", "definition",
    "meaning", "mean", "means", "info", "information", "details", "detail", "please",
    "pls", "plz", "i", "we", "you", "want", "wanna", "need", "know", "learn", "understand",
    "understanding", "about", "some", "any", "more", "with", "by", "my", "your", "it",
    "like", "regards", "related", "topic", "topics", "concept", "term", "word",
    "lesson", "chapter", "module", "course", "overview", "intro", "introduction",
}

_ORDINALS = {
    "first": 1, "1st": 1, "one": 1, "second": 2, "2nd": 2, "two": 2,
    "third": 3, "3rd": 3, "three": 3, "fourth": 4, "4th": 4, "four": 4,
    "fifth": 5, "5th": 5, "five": 5,
}
_LAST_WORDS = {"last", "final", "latter"}
_GENERAL_WORDS = {"general", "generic", "overview", "basics", "basic", "anything", "any", "all", "everything"}
_AFFIRMATIVE_WORDS = {
    "yes", "yeah", "yep", "yup", "sure", "ok", "okay", "proceed", "confirm",
    "continue", "why not", "definitely", "correct", "tell me", "show me",
}
_NEGATIVE_WORDS = {
    "no", "nope", "nah", "never", "cancel", "dont", "don't", "stop", "skip",
    "leave it", "never mind", "not now",
}
_REPLY_FILLER = {
    "the", "a", "an", "one", "option", "number", "pick", "choose", "select",
    "i", "mean", "meant", "want", "it", "is", "this", "that", "please", "pls",
    "about", "regarding", "for", "of", "in", "on", "then",
}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", (text or "").lower())).strip()


def _stem(word: str) -> str:
    """Very small stemmer so 'temperatures' == 'temperature', 'pumping' ~ 'pump'."""
    w = word.lower()
    for suffix in ("ing", "es", "s"):
        if len(w) > len(suffix) + 3 and w.endswith(suffix):
            return w[: -len(suffix)]
    return w


def _tokens(text: str) -> List[str]:
    return [t for t in _norm(text).split() if t]


def _stem_set(text: str) -> set:
    return {_stem(t) for t in _tokens(text)}


# The "General overview" option sends a query with this prefix; ChatService recognises it and
# answers from the LLM's general knowledge instead of the course index (see parse_general_overview).
GENERAL_OVERVIEW_PREFIX = "Give me a general overview of "


def parse_general_overview(query: str) -> Optional[str]:
    """Return the term if ``query`` is a 'General overview' request created by this feature."""
    q = (query or "").strip()
    if q.lower().startswith(GENERAL_OVERVIEW_PREFIX.lower()):
        term = q[len(GENERAL_OVERVIEW_PREFIX):].strip(" .?!")
        if 0 < len(term) <= 60:
            return term
    return None


_DEFINITIONAL_STARTERS = (
    "what is", "what are", "whats", "what s", "what does", "what do", "define", "definition of",
    "meaning of", "explain", "tell me about", "describe", "who is", "who are",
    "give me a general overview of", "general overview of", "overview of", "brief on", "intro to",
)


def is_definitional_question(query: str) -> bool:
    """
    True for short 'what is X' / 'explain X' / bare-term questions - the kind a tutor can answer in a
    couple of sentences from general knowledge. Longer or procedural questions return False.
    """
    q = _norm(query)
    words = q.split()
    if not words or len(words) > 12:
        return False
    if any(q.startswith(st) for st in _DEFINITIONAL_STARTERS):
        return True
    return len(words) <= 3


def definitional_term(query: str) -> str:
    """'what is temperature in few words?' -> 'temperature'."""
    q = _norm(query)
    for st in sorted(_DEFINITIONAL_STARTERS, key=len, reverse=True):
        if q.startswith(st):
            q = q[len(st):].strip()
            break
    q = re.sub(r"\b(in|within)\s+(a\s+)?(few|short|brief|simple)\s+(words|terms|lines|sentences)\b", "", q)
    q = re.sub(r"\b(in\s+simple\s+terms|briefly|please|pls)\b", "", q)
    words = [w for w in q.split() if w not in ("a", "an", "the")]
    return " ".join(words).strip() or _norm(query)


_GENERIC_TOPIC_WORDS = {
    "system", "systems", "ship", "ships", "vessel", "vessels", "onboard", "board", "operation",
    "operations", "general", "basic", "basics", "introduction", "overview", "including", "related",
    "based", "using", "with", "from", "that", "this", "their", "case", "study", "part",
}


def _clean_label(name: str) -> str:
    """Make a topic title presentable: drop '1. ' numbering and course codes like 'DBMV-8121-'."""
    n = (name or "").strip()
    n = re.sub(r"^\s*\d+\s*[\.\)]\s*", "", n)
    n = re.sub(r"^(?:[A-Z]{2,6}-\d{2,6}-)+", "", n)
    n = re.sub(r"\s+", " ", n).strip(" -:")
    return n or (name or "").strip()


def _short_label(name: str, limit: int = 55) -> str:
    """Button-sized label: cleaned, and cut at ' - ' or a word boundary when very long."""
    n = _clean_label(name)
    if len(n) <= limit:
        return n
    head = n.split(" - ")[0].strip()
    if 8 <= len(head) <= limit:
        return head
    cut = n[:limit].rsplit(" ", 1)[0].rstrip(",;:-")
    return cut + "…"


def _key(name: str) -> str:
    return _norm(_clean_label(name))


def _title(term: str) -> str:
    return term[:1].upper() + term[1:] if term else term


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ClarificationOption:
    id: int
    label: str
    query: str                      # fully specified query sent when the option is picked
    kind: str = "topic"             # topic | general | other
    topic_name: str = ""
    topic_code: str = ""
    hint: str = ""
    description: str = ""           # 3-4 line description of what this subtopic covers

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Clarification:
    term: str
    original_query: str
    question: str
    options: List[ClarificationOption] = field(default_factory=list)
    intro: str = ""                     # comprehensive 4-6 line "what is X" description
    closing: str = ""                   # dynamic interactive final line (LLM-generated or varied)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "term": self.term,
            "original_query": self.original_query,
            "intro": self.intro,
            "question": self.question,
            "closing": self.closing,
            "options": [o.to_dict() for o in self.options],
        }

    @staticmethod
    def _dynamic_fallback_closing(term: str) -> str:
        """Varied, professional maritime closing prompts when LLM closing is not provided."""
        t = term or "this topic"
        variations = [
            f"Select any topic above to explore detailed operational procedures for {t}, or describe your exact vessel scenario.",
            f"Which aspect of {t} would you like to review? Click any focus area above, or ask me about your onboard setup.",
            f"Choose the relevant module above to check standard guidelines, or let me know your specific machinery arrangement.",
            f"Select one of the operational areas above to inspect step-by-step procedures, or specify your vessel's requirements.",
            f"Pick any focus area above to dive into regulatory and maintenance checks, or type your exact question directly.",
        ]
        return random.choice(variations)

    def render_text(self) -> str:
        """Plain-markdown rendering with rich overview, 3-4 line subtopic descriptions, and dynamic interactive closing."""
        lines = ([self.intro, ""] if self.intro else []) + [self.question, ""]
        n = 0
        for opt in self.options:
            if opt.kind == "other":
                continue
            n += 1
            hint = f" — {opt.hint}" if opt.hint and not opt.description else ""
            target_query = opt.query or opt.label
            link_target = f"#ask:{urllib.parse.quote(target_query)}"
            lines.append(f"{n}. **[{opt.label}]({link_target})**{hint}")
            if opt.description:
                lines.append(f"   {opt.description}")
            lines.append("")
        
        closing_line = (self.closing or "").strip()
        if not closing_line:
            closing_line = self._dynamic_fallback_closing(self.term)
        lines.append(closing_line)
        return "\n".join(lines)

    def suggestion_queries(self) -> List[str]:
        """Queries for the legacy ``question_suggestions`` chips (backward compatible)."""
        return [o.query for o in self.options if o.kind == "topic" and o.query]


@dataclass
class _Candidate:
    topic_name: str
    topic_code: str = ""
    retrieved_rank: Optional[int] = None   # position in retrieval results, None if not retrieved
    name_match: bool = False               # term appears in the topic name
    from_history: bool = False             # topic was used in the previous turn
    snippet: str = ""                      # short content excerpt (helps the LLM label options)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class ClarificationService:
    def __init__(
        self,
        openai_service: Any = None,
        enabled: bool = True,
        use_llm: bool = True,
        max_options: int = 5,
        llm_timeout: float = 6.0,
        max_focus_terms: int = 2,
        max_query_words: int = 6,
    ) -> None:
        self.openai_service = openai_service
        self.enabled = enabled
        self.use_llm = use_llm and openai_service is not None
        self.max_options = max(2, max_options)
        self.llm_timeout = llm_timeout
        self.max_focus_terms = max_focus_terms
        self.max_query_words = max_query_words
        self._clarification_cache: Dict[str, Clarification] = {}

    # ------------------------------------------------------------------
    # 1. Is the query a bare term?
    # ------------------------------------------------------------------
    def extract_focus_terms(self, query: str) -> List[str]:
        words = _tokens(query)
        if not words or len(words) > self.max_query_words:
            return []
        return [w for w in words if w not in _FILLER_WORDS]

    @staticmethod
    def _expansions(term: str) -> List[List[str]]:
        """Stem lists for each known expansion of an acronym ("sms" -> [[safety, management, system]])."""
        try:
            from services.maritime_acronyms import get_acronym_expansion, is_known_maritime_acronym
            if not is_known_maritime_acronym(term):
                return []
            out = []
            generic_single_stems = {
                "scheme", "plan", "system", "rule", "code", "guide", "manual",
                "procedur", "oper", "check", "control", "inspect", "standard",
            }
            for phrase in get_acronym_expansion(term) or []:
                raw_toks = _tokens(str(phrase))
                if len(raw_toks) >= 2:
                    stems = [_stem(t) for t in raw_toks if len(t) >= 1]
                else:
                    stems = [_stem(t) for t in raw_toks if len(t) > 2]
                if len(stems) == 1 and stems[0] in generic_single_stems:
                    continue
                if stems and stems not in out:
                    out.append(stems)
            return out
        except Exception:
            return []

    GENERIC_CATEGORY_STEMS = {
        # Shipboard equipment / machinery categories that have multiple distinct types
        "ladder", "pump", "valv", "tank", "alarm", "drill", "inspect", "sensor",
        "meter", "filter", "cooler", "purifi", "compress", "boiler", "generat",
        "gaug", "indicat", "switch", "strainer", "pipe", "pip", "heater",
        # Physical measurements / properties across multiple ship systems
        "temperat", "pressur", "level", "flow", "densit", "viscosit",
    }

    @classmethod
    def _is_generic_category(cls, term: str) -> bool:
        if not term:
            return False
        w = _stem(term.lower().strip())
        return any(w.startswith(s) or s.startswith(w) for s in cls.GENERIC_CATEGORY_STEMS if len(s) >= 4)

    @staticmethod
    def _is_acronym(term: str) -> bool:
        try:
            from services.maritime_acronyms import is_known_maritime_acronym
            return is_known_maritime_acronym(term)
        except Exception:
            return False

    def is_underspecified(self, query: str) -> bool:
        q_lower = (query or "").lower().strip()
        # SMS templates, forms, checklists, and permits are handled by the template engine
        if any(w in q_lower for w in ["template", "permit", "checklist", "ptw", "form"]):
            return False

        focus = self.extract_focus_terms(query)
        if not focus:
            return False

        # Digits / codes (e.g. "SOLAS II-2", "regulation 19") are specific enough.
        if any(ch.isdigit() for ch in query):
            return False

        # 1. Recognized maritime technical acronyms (ECDIS, EGCS, BWMS, SCR, SECP, OMM, VLSFO, etc.)
        # are specific technical systems; user expects the substantive overview, not a bare clarification question.
        if any(self._is_acronym(t) for t in focus):
            return False

        # 2. Multi-word qualified terms (e.g. "combination ladder", "pilot ladder", "centrifugal pump")
        # have specific qualifiers; user wants the direct content of that specific topic.
        if len(focus) >= 2:
            return False

        # 3. Single focus term: only clarify if it is a genuinely vague category noun
        # (e.g. "ladders", "pumps", "valves", "temperature", "pressure", "tanks").
        single_term = focus[0]
        if self._is_generic_category(single_term):
            return True

        # If not an acronym, not a qualified multi-word phrase, and not a generic category, do not clarify
        return False

    # ------------------------------------------------------------------
    # 2. Candidate topics
    # ------------------------------------------------------------------
    @staticmethod
    def _matches(term_stems: Sequence[str], text: str, alts: Sequence[Sequence[str]] = ()) -> bool:
        stems = _stem_set(text)
        if all(t in stems for t in term_stems):
            return True
        return any(a and all(t in stems for t in a) for a in alts)

    def find_candidates(
        self,
        focus_terms: Sequence[str],
        chunks: Sequence[Dict[str, Any]],
        all_topic_names: Iterable[str],
        history_topic_codes: Iterable[str] = (),
        alts: Sequence[Sequence[str]] = (),
    ) -> List[_Candidate]:
        term_stems = [_stem(t) for t in focus_terms]
        history_codes = {str(c) for c in history_topic_codes if c}
        by_key: Dict[str, _Candidate] = {}

        # (a) chunks retrieval already returned, in rank order
        for rank, chunk in enumerate(chunks or []):
            if not isinstance(chunk, dict) or chunk.get("_is_sme_approved"):
                continue
            name = str(chunk.get("topic_name") or "").strip()
            if not name:
                continue
            key = _key(name)
            code = str(chunk.get("topic_code") or "")
            cand = by_key.get(key)
            if cand is None:
                cand = _Candidate(topic_name=name, topic_code=code, retrieved_rank=rank)
                by_key[key] = cand
            if not cand.snippet:
                cand.snippet = re.sub(r"\s+", " ", str(chunk.get("topic_content") or "")).strip()[:140]
            cand.name_match = cand.name_match or self._matches(term_stems, name, alts)
            if code and code in history_codes:
                cand.from_history = True

        # (b) every topic in the index whose NAME contains the term
        for name in all_topic_names or []:
            if not isinstance(name, str) or not name.strip():
                continue
            if not self._matches(term_stems, name, alts):
                continue
            key = _key(name)
            cand = by_key.get(key)
            if cand is None:
                by_key[key] = _Candidate(topic_name=name.strip(), name_match=True)
            else:
                cand.name_match = True

        return list(by_key.values())

    @staticmethod
    def _content_hits(term_stems: Sequence[str], chunks: Sequence[Dict[str, Any]], top: int = 12,
                      alts: Sequence[Sequence[str]] = ()) -> List[str]:
        """Distinct topic names among the top chunks whose body mentions the term."""
        seen, out = set(), []
        for chunk in list(chunks or [])[:top]:
            if not isinstance(chunk, dict) or chunk.get("_is_sme_approved"):
                continue
            name = str(chunk.get("topic_name") or "").strip()
            body = f"{name} {chunk.get('topic_content') or chunk.get('content') or ''}"
            if name and _key(name) not in seen and ClarificationService._matches(term_stems, body, alts):
                seen.add(_key(name))
                out.append(name)
        return out

    # ------------------------------------------------------------------
    # 3. Decision + option building
    # ------------------------------------------------------------------
    async def maybe_clarify(
        self,
        query: str,
        chunks: Sequence[Dict[str, Any]],
        all_topic_names: Iterable[str],
        history_topic_codes: Iterable[str] = (),
    ) -> Optional[Clarification]:
        """Return a Clarification if the query is genuinely ambiguous, else None."""
        if not self.enabled:
            logger.info("[CLARIFY] disabled (ENABLE_CLARIFICATION=false)")
            return None
        if not query or not self.is_underspecified(query):
            logger.info(f"[CLARIFY] '{query}' is specific enough (not a bare term)")
            return None

        # An SME-approved answer is authoritative - never second-guess it.
        if any(isinstance(c, dict) and c.get("_is_sme_approved") for c in (chunks or [])):
            logger.info("[CLARIFY] SME-approved answer present -> skipped")
            return None

        focus = self.extract_focus_terms(query)
        term = " ".join(focus)

        # Normalize maritime acronyms so casing (secp vs SECP) is 100% deterministic
        from services.maritime_acronyms import is_known_maritime_acronym
        is_acronym = len(focus) == 1 and is_known_maritime_acronym(focus[0])
        if is_acronym:
            term = focus[0].upper()
            focus = [focus[0].lower()]

        cache_key = _norm(term)
        if cache_key in self._clarification_cache:
            cached_clar = self._clarification_cache[cache_key]
            logger.info(f"[CLARIFY] Serving cached clarification for '{term}' ({len(cached_clar.options)} options)")
            return cached_clar

        term_stems = [_stem(t) for t in focus]
        topic_names = list(all_topic_names or [])
        alts: List[List[str]] = []
        if len(focus) == 1:
            alts = self._expansions(focus[0])
            if not alts and len(focus[0]) <= 6:
                # Acronym not in the registry: learn its spelled-out form from the course text,
                # e.g. "Introduction to Safety Management System (SMS)" -> safety management system
                spelled = self._full_name(focus[0], chunks, topic_names)
                if spelled:
                    alts = [[_stem(t) for t in _tokens(spelled) if len(t) > 2]]

        candidates = self.find_candidates(focus, chunks, topic_names, history_topic_codes, alts)
        named = [c for c in candidates if c.name_match]

        # Topics whose BODY mentions the term (not just their name) among everything retrieved.
        hit_keys = {_key(h) for h in self._content_hits(term_stems, chunks, alts=alts)}
        content_only = [c for c in candidates if not c.name_match and _key(c.topic_name) in hit_keys]
        pool = named + content_only

        distinct_retrieved = len({_key(str(c.get("topic_name") or "")) for c in (chunks or [])
                                  if isinstance(c, dict) and c.get("topic_name")})
        logger.info(
            f"[CLARIFY] query='{query}' term='{term}' topics_in_index={len(topic_names)} "
            f"name_matches={len(named)} content_only_matches={len(content_only)} "
            f"retrieved_chunks={len(chunks or [])} distinct_retrieved_topics={distinct_retrieved}"
        )

        if len(pool) < 2:
            logger.info("[CLARIFY] -> not ambiguous (fewer than 2 distinct matching topics)")
            return None

        pool = self._rank(pool)
        expansion = self._full_name(term, chunks, topic_names) if alts else ""
        lead_in, intro, options, closing = await self._build_options(term, query, pool, expansion=expansion)
        if len(options) < 2:
            logger.info("[CLARIFY] -> no usable options built")
            return None
        if not intro and self.use_llm:
            intro = await self.quick_intro(term, expansion=expansion)
        if not closing and self.use_llm:
            closing = await self.quick_closing(term, expansion=expansion)
        display = term if is_acronym else (" ".join(w for w in re.findall(r"[A-Za-z0-9\-]+", query) if w.lower() not in _FILLER_WORDS) or term)
        res = self._finalize(display, query, lead_in, options, intro=intro, closing=closing, expansion=expansion)
        if res:
            self._clarification_cache[cache_key] = res
        return res

    @staticmethod
    def _full_name(term: str, chunks: Sequence[Dict[str, Any]], topic_names: Sequence[str]) -> str:
        """Prefer the spelled-out name used in the course, e.g. 'Safety Management System'."""
        term_clean = term.strip().upper()
        # Pattern 1: Full Name (ACR) e.g. "Onboard Monitoring Manual (OMM)"
        pat1 = re.compile(r"([A-Z][A-Za-z&/\-]+(?:\s+(?:of|and|for|the|[A-Z][A-Za-z&/\-]+)){1,5})\s*\(\s*" + re.escape(term_clean) + r"\s*\)")
        # Pattern 2: ACR - Full Name or ACR: Full Name e.g. "OMM- On board Monitoring Manual"
        pat2 = re.compile(r"\b" + re.escape(term_clean) + r"\s*[-:\(]\s*([A-Za-z\s\-]{4,45})\b")

        texts = list(topic_names) + [str(c.get("topic_name") or "") for c in (chunks or []) if isinstance(c, dict)]
        texts += [str(c.get("topic_content") or "")[:4000] for c in (chunks or []) if isinstance(c, dict)]
        for t in texts:
            m1 = pat1.search(t)
            if m1:
                return m1.group(1).strip()
            m2 = pat2.search(t)
            if m2:
                candidate = m2.group(1).strip()
                if len(candidate) > len(term_clean):
                    return " ".join(w.capitalize() for w in candidate.split())
        try:
            from services.maritime_acronyms import get_acronym_expansion
            exp = get_acronym_expansion(term) or []
            if exp:
                return " ".join(w.capitalize() for w in str(exp[0]).split())
        except Exception:
            pass
        return ""

    @staticmethod
    def _rank(pool: List[_Candidate]) -> List[_Candidate]:
        """Previous-turn topics first, then retrieval order, then shorter (more general) names."""
        def key(c: _Candidate):
            return (
                0 if c.from_history else 1,
                c.retrieved_rank if c.retrieved_rank is not None else 10_000,
                len(c.topic_name),
            )
        return sorted(pool, key=key)

    @staticmethod
    def _topic_tokens(name: str, term_stems: Sequence[str]) -> set:
        out = set()
        for t in _tokens(_clean_label(name)):
            st = _stem(t)
            if len(st) < 4 or st in term_stems or t in _FILLER_WORDS or st in _GENERIC_TOPIC_WORDS:
                continue
            out.add(st)
        return out

    def _cluster(self, pool: List[_Candidate], term_stems: Sequence[str]) -> List[List[_Candidate]]:
        """
        Group near-identical topics (e.g. six 'vapour pressure / temperature' topics) so the learner
        sees DISTINCT choices instead of six variations of one thing. Pool must already be ranked.
        """
        clusters: List[Dict[str, Any]] = []
        for cand in pool:
            toks = self._topic_tokens(cand.topic_name, term_stems)
            home = None
            if toks:
                for cl in clusters:
                    if cl["tokens"] & toks:
                        home = cl
                        break
            if home is None:
                clusters.append({"members": [cand], "tokens": set(toks)})
            else:
                home["members"].append(cand)
                home["tokens"] |= toks
        return [cl["members"] for cl in clusters]

    async def _build_options(self, term: str, query: str, pool: List[_Candidate], expansion: str = ""):
        """
        Returns ``(lead_in_or_None, intro_or_empty, [options])``. ``lead_in`` is the question
        sentence and ``intro`` the short "what is X" answer, both written by the LLM when available.
        """
        limit = self.max_options - 1  # leave slot for "Something else"
        term_stems = [_stem(t) for t in _tokens(term)]
        clusters = self._cluster(pool, term_stems)
        reps = [cl[0] for cl in clusters]
        sizes = [len(cl) for cl in clusters]

        if self.use_llm and len(reps) >= 2:
            try:
                llm_opts = await asyncio.wait_for(
                    self._llm_group(term, reps[:24], sizes[:24], expansion=expansion), timeout=self.llm_timeout
                )
                if llm_opts:
                    lead, opts, intro, closing = llm_opts
                    return lead, intro, opts[:limit], closing
            except Exception as exc:  # timeout, bad JSON, API error ...
                logger.info(f"[CLARIFY] LLM grouping skipped ({type(exc).__name__}: {exc}); using deterministic options")

        opts: List[ClarificationOption] = []
        if len(reps) >= 2:
            chosen = list(zip(reps[:limit], sizes[:limit]))
        else:  # everything is one theme: offer the individual topics instead
            chosen = [(c, 1) for c in pool[:limit]]
        for cand, size in chosen:
            full = _clean_label(cand.topic_name)
            q = f"Tell me about {full}" if cand.name_match else f"{_title(term)} in {full}"
            desc = ""
            if cand.snippet and len(cand.snippet.strip()) > 30:
                desc = cand.snippet.strip()[:250]
            else:
                desc = f"Covers maritime procedures, regulatory standards, and practical shipboard operational guidance for {full}."
            opts.append(
                ClarificationOption(
                    id=0, label=_short_label(cand.topic_name), query=q, kind="topic",
                    topic_name=cand.topic_name, topic_code=cand.topic_code,
                    hint=(f"plus {size - 1} related topic{'s' if size > 2 else ''}" if size > 1 else ""),
                    description=desc,
                )
            )
        return None, "", opts, ""

    async def quick_intro(self, term: str, expansion: str = "") -> str:
        """Comprehensive 4-to-6 line explanation saying what ``term`` is from a maritime perspective."""
        if not self.openai_service:
            return ""
        term_subject = f'"{term}" ({expansion})' if expansion else f'"{term}"'
        prompt = (
            "You are Dolphin, an expert maritime training tutor. A learner asked about: "
            f"{term_subject}.\nProvide a comprehensive, high-quality maritime explanation of 4 to 6 lines (approx. 70-110 words) describing what {term_subject} is in practical marine engineering or nautical terms, where and how it is used/rigged onboard, and any key SOLAS, MARPOL, STCW, or maritime safety standards associated with it. "
            "Write in clean prose without headings, bullet points, questions, or sources."
        )
        try:
            text = await asyncio.wait_for(
                self.openai_service.chat(
                    [{"role": "user", "content": prompt}],
                    temperature=0.2, category="CLARIFICATION_INTRO", max_tokens=250,
                ),
                timeout=self.llm_timeout,
            )
            text = (text or "").strip()
            if text and not text.startswith("I apologize, but I encountered an error"):
                return text[:1500]
        except Exception as exc:
            logger.info(f"[CLARIFY] intro skipped ({type(exc).__name__}: {exc})")
        return ""

    async def quick_closing(self, term: str, expansion: str = "") -> str:
        """Dynamic interactive 1-sentence call to action written by the LLM."""
        if not self.openai_service:
            return ""
        term_subject = f"'{term}' ({expansion})" if expansion else f"'{term}'"
        prompt = (
            f"You are Dolphin, an expert maritime training tutor. A learner asked about: {term_subject}. "
            "Write exactly ONE engaging, dynamic interactive final sentence (max 20 words) "
            "inviting the learner to select one of the suggested topics above or ask about a specific onboard scenario or machinery setup. "
            "Do NOT use repetitive boilerplate like 'Tap one of the options'. Make it professional, natural, engaging, and maritime-tailored."
        )
        try:
            text = await asyncio.wait_for(
                self.openai_service.chat(
                    [{"role": "user", "content": prompt}],
                    temperature=0.7, category="CLARIFICATION_CLOSING", max_tokens=60,
                ),
                timeout=self.llm_timeout,
            )
            text = (text or "").strip().strip('"\'')
            if text and not text.startswith("I apologize"):
                return text
        except Exception as exc:
            logger.debug(f"[CLARIFY] quick_closing skipped ({type(exc).__name__}: {exc})")
        return ""

    async def _llm_group(self, term: str, pool: List[_Candidate], sizes: Sequence[int] = (), expansion: str = ""):
        numbered = "\n".join(
            f"{i + 1}. {_clean_label(c.topic_name)}"
            + (f" (+{sizes[i] - 1} similar topics)" if i < len(sizes) and sizes[i] > 1 else "")
            + (f" - {c.snippet}" if c.snippet else "")
            for i, c in enumerate(pool)
        )
        n_opts = max(2, self.max_options - 1)
        target_count = min(n_opts, len(pool))

        expansions_hint = ""
        try:
            from services.maritime_acronyms import get_acronym_expansion
            exps = get_acronym_expansion(term)
            if exps:
                expansions_hint = f"\nKnown maritime expansions/variations for \"{term.upper()}\": {', '.join(exps)}"
        except Exception:
            pass

        term_subject = f'"{term}" ({expansion})' if expansion else f'"{term}"'
        prompt = f"""You are Dolphin, an expert maritime training tutor. A learner asked about: {term_subject}.
This topic or equipment has multiple distinct applications, chapters, or operational aspects in the maritime curriculum:
{numbered}
{expansions_hint}

Provide a comprehensive introductory explanation and distinct subtopic choices for the learner.

Requirements:
1. "intro": A comprehensive, high-quality maritime explanation of 4 to 6 lines (approx. 70-110 words) describing what {term_subject} is in practical marine engineering or nautical terms, where and how it is used/rigged onboard, and any key SOLAS, MARPOL, STCW, or maritime safety standards associated with it. Do NOT use headings, bullet points, or questions in the intro.
2. "question": ONE short natural sentence (max 20 words) asking which specific variation or operational area they want to explore.
3. "options": Pick exactly {target_count} (minimum 2) DISTINCT options strictly relevant to {term_subject} from the numbered course topics above. Do NOT select topics from unrelated acronyms, systems, or different management plans.
For each option provide:
- "label": Clear title (plain English, no course codes).
  * CRITICAL FOR ACRONYMS & ABBREVIATIONS (such as SECP, CBA, SMS, OWS, COW):
    Every option MUST be a direct subtopic, variation, or operational procedure of "{term.upper()}". The label MUST explicitly include the full spelled-out name/variation followed by the parent context in parentheses, e.g. "Scrubber Emission Control Plan (EGC System Approval)" or "Sulfur Emission Control Plan (SOx Regulations)". Do NOT select or display unrelated acronyms or different management plans (e.g. do not show SEEMP or PSC under SECP).
- "query": A complete standalone question of 5+ words that includes the full term and topic.
- "description": A clear, informative 3 to 4 line description (approx. 35-55 words) explaining the specific scope of this subtopic (the procedures, regulations, equipment, or onboard duties involved) in the context of "{term}".
- "topic_ids": List of the matching topic number(s) from the list above.
4. "closing": A dynamic, fresh, and interactive concluding line (1 sentence, max 25 words) encouraging the learner to interact—such as inviting them to select an operational focus area above or specify their particular vessel machinery arrangement. Do NOT use repetitive boilerplate like "Tap one of the options, or just tell me what you're after". Make it lively, unique, and tailored to "{term}".

Return ONLY valid JSON in this exact structure:
{{"ambiguous": true,
  "intro": "4 to 6 lines of comprehensive maritime description...",
  "question": "Which specific area would you like to explore?",
  "options": [
    {{
      "label": "Short Topic Title",
      "description": "3 to 4 lines explaining what this subtopic covers in practical maritime operations...",
      "topic_ids": [1],
      "query": "Tell me about..."
    }}
  ],
  "closing": "Dynamic interactive final line tailored to this topic..."
}}
Rules: Use only the numbered course topics; never invent topics; set 'ambiguous' to false only if every topic is essentially identical."""
        raw = await self.openai_service.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.0,
            category="CLARIFICATION",
            max_tokens=1000,
            response_format={"type": "json_object"},
        )
        data = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(data, dict) or not data.get("ambiguous"):
            return None
        out: List[ClarificationOption] = []
        for item in data.get("options") or []:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label") or "").strip()
            query = str(item.get("query") or "").strip()
            ids = [i for i in (item.get("topic_ids") or []) if isinstance(i, int) and 1 <= i <= len(pool)]
            if not label or len(query.split()) < 3 or not ids:
                continue
            first = pool[ids[0] - 1]
            desc = str(item.get("description") or "").strip()[:600]
            if not desc and first.snippet:
                desc = first.snippet[:200]
            out.append(
                ClarificationOption(
                    id=0, label=label[:60], query=query[:200], kind="topic",
                    topic_name=first.topic_name, topic_code=first.topic_code,
                    hint=str(item.get("hint") or "").strip()[:80],
                    description=desc,
                )
            )
        if len(out) < 2:
            return None
        lead = str(data.get("question") or "").strip() or None
        intro = str(data.get("intro") or "").strip()[:1500]
        closing = str(data.get("closing") or data.get("closing_line") or "").strip()[:300]
        return lead, out, intro, closing

    def _finalize(
        self,
        term: str,
        original_query: str,
        lead_in: Optional[str],
        topic_options: List[ClarificationOption],
        expansion: str = "",
        intro: str = "",
        closing: str = "",
    ) -> Optional[Clarification]:
        if len(topic_options) < 2:
            return None
        title = _title(term)
        options = list(topic_options)
        # Note: "General overview" option removed per user preference
        options.append(ClarificationOption(id=0, label="Something else", query="", kind="other"))
        for i, opt in enumerate(options, 1):
            opt.id = i
        if lead_in:
            question = lead_in
        elif expansion:
            question = (
                f"Sure! Do you mean **{term.upper()}** ({expansion}) in general, "
                f"or a specific part of it? Here's what the course covers:"
            )
        else:
            variants = [
                f"Happy to help with **{term}**! It comes up in a few different places in the course. Which of these are you after?",
                f"Sure! **{title}** can mean a few different things here. What would you like to know about?",
                f"Good one! I have a few topics on **{term}**. Which one did you have in mind?",
            ]
            question = variants[sum(ord(ch) for ch in term) % len(variants)]
        return Clarification(
            term=term, original_query=original_query, question=question, options=options, intro=intro, closing=closing
        )

    # ------------------------------------------------------------------
    # 4. Resolve a typed reply to a pending clarification
    # ------------------------------------------------------------------
    @staticmethod
    def pending_from_messages(messages: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """The clarification is pending only if it was the very last message."""
        if not messages:
            return None
        last = messages[-1]
        if isinstance(last, dict) and last.get("role") == "assistant":
            clar = last.get("clarification")
            if not clar and isinstance(last.get("metadata"), dict):
                clar = last["metadata"].get("clarification")
            if isinstance(clar, dict) and clar.get("options"):
                return clar
        return None

    def resolve_reply(self, reply: str, pending: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Map "2", "second one", "the last one", "general", or "cargo" onto an option.
        Returns the option dict, or None when the reply is a brand-new question.
        """
        if not reply or not pending:
            return None
        options = [o for o in pending.get("options", []) if o.get("kind") != "other" and o.get("query")]
        if not options:
            return None

        norm = _norm(reply)
        if not norm:
            return None

        # Exact or substring label / query match (user clicked option link or pasted title)
        # Check this BEFORE token count limits, as option titles can be long (> 6 tokens).
        for opt in options:
            opt_lbl = _norm(opt.get("label", ""))
            opt_q = _norm(opt.get("query", ""))
            opt_tn = _norm(opt.get("topic_name", ""))
            if norm in (opt_lbl, opt_q, opt_tn):
                return opt
            if opt_lbl and len(opt_lbl) >= 4 and (norm in opt_lbl or opt_lbl in norm):
                return opt
            if opt_q and len(opt_q) >= 4 and (norm in opt_q or opt_q in norm):
                return opt
            if opt_tn and len(opt_tn) >= 4 and (norm in opt_tn or opt_tn in norm):
                return opt

        toks = norm.split()
        if not toks or len(toks) > 6:
            return None

        # Affirmative replies ("yes", "sure", "proceed", "1")
        if any(t in _AFFIRMATIVE_WORDS for t in toks) and not any(t in _NEGATIVE_WORDS for t in toks):
            return options[0]

        # Negative replies ("no", "nope", "cancel")
        if any(t in _NEGATIVE_WORDS for t in toks) and not any(t in _AFFIRMATIVE_WORDS for t in toks):
            return {"kind": "declined", "id": -1, "query": "", "label": "No"}

        content = [t for t in toks if t not in _REPLY_FILLER]

        # Numbers / ordinals / "last"
        if len(content) <= 1:
            word = content[0] if content else (toks[-1] if toks else "")
            if word.isdigit() and 1 <= int(word) <= len(options):
                return options[int(word) - 1]
            if word in _ORDINALS and _ORDINALS[word] <= len(options):
                return options[_ORDINALS[word] - 1]
            if word in _LAST_WORDS:
                return options[-1]

        # "general", "overview" ...
        if content and all(t in _GENERAL_WORDS for t in content):
            for opt in options:
                if opt.get("kind") == "general":
                    return opt

        # Partial label match: every meaningful word the user typed appears in exactly one option
        if content:
            stems = {_stem(t) for t in content}
            hits = [
                o for o in options
                if o.get("kind") != "general"
                and stems <= (_stem_set(o.get("label", "")) | _stem_set(o.get("topic_name", "")))
            ]
            if len(hits) == 1:
                return hits[0]
        return None

    def detect_cross_domain_overlap(
        self,
        query: str,
        all_topic_names: Optional[Sequence[str]] = None,
    ) -> Optional[Tuple[str, str, str]]:
        """
        Dynamically detect if an off-topic / non-marine query contains a legitimate
        maritime course topic (e.g. 'barbell squat' -> 'squat', 'dental bridge' -> 'bridge').
        Returns: (overlap_term, maritime_label, target_query) or None.
        """
        if not query or not isinstance(query, str):
            return None

        q_norm = _norm(query)
        words = q_norm.split()
        if not words or len(words) > 15:
            return None

        from services.off_topic_detector import is_marine_domain_query, MARINE_INDICATORS
        try:
            from services.dynamic_domain_service import dynamic_domain_service
        except Exception:
            dynamic_domain_service = None

        candidates = []
        # Check 2-word n-grams first, then single words
        for n in (2, 1):
            for i in range(len(words) - n + 1):
                chunk = " ".join(words[i:i + n])
                if chunk in _FILLER_WORDS or len(chunk) < 3:
                    continue
                # Is this chunk in our marine indicators or database?
                is_db = dynamic_domain_service and dynamic_domain_service.is_db_domain_match(chunk)
                is_ind = any(re.search(r'\b' + re.escape(chunk) + r'\b', m, re.I) for m in MARINE_INDICATORS)
                if is_db or is_ind:
                    candidates.append(chunk)

        if not candidates:
            return None

        # Pick the most specific candidate (longest)
        best_candidate = max(candidates, key=len)
        cand_stem = _stem(best_candidate)

        # Search matching topic names from course database
        matched_topics = []
        if all_topic_names:
            for t in all_topic_names:
                if not t:
                    continue
                t_stems = _stem_set(t)
                if cand_stem in t_stems:
                    matched_topics.append(t)

        best_topic = None
        if matched_topics:
            # Sort by concise title length
            matched_topics.sort(key=lambda x: (len(x.split()), len(x)))
            best_topic = matched_topics[0]

        maritime_label = best_topic if best_topic else f"Ship {best_candidate.title()}"
        target_query = f"Explain {maritime_label} in maritime navigation and shipboard operations"
        return (best_candidate, maritime_label, target_query)

    def build_cross_domain_text_clarification(
        self,
        user_query: str,
        overlap_term: str,
        maritime_label: str,
        target_query: str,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Build text-only confirmation message (NO BUTTONS) where user confirms by typing in chat.
        """
        clean_user_q = user_query.strip().rstrip("?.!")
        text = (
            f"**\"{clean_user_q}\"** appears to fall outside our maritime training curriculum.\n\n"
            f"However, in maritime navigation and nautical science, **{overlap_term.title()}** refers to **{maritime_label}**.\n\n"
            f"Would you like to learn about this maritime topic?\n"
            f"• Reply with **yes** (or type **{overlap_term}**) to proceed with the explanation.\n"
            f"• Reply with **no** or ask another question to skip."
        )
        clar_payload = {
            "term": overlap_term,
            "original_query": user_query,
            "kind": "cross_domain_confirmation",
            "question": f"Would you like to learn about {maritime_label}?",
            "options": [
                {
                    "id": 1,
                    "label": maritime_label,
                    "query": target_query,
                    "kind": "confirmation",
                    "topic_name": maritime_label,
                    "topic_code": "",
                    "hint": "",
                }
            ],
            "intro": "",
        }
        return text, clar_payload
