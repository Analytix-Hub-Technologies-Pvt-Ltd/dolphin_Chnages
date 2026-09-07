# retrieval/normalization.py
from __future__ import annotations

import re
import unicodedata
from typing import List, Set, Tuple


# ---------------------------------------------------------------------------
# DOMAIN LEXICON: GENERIC VS DISTINCTIVE WORDS
# ---------------------------------------------------------------------------
COMMON_GENERIC_WORDS: Set[str] = {
    "oil", "system", "systems", "rule", "rules", "water", "air", "ship", "ships",
    "marine", "gas", "safety", "pump", "pumps", "engine", "engines", "process",
    "processes", "operation", "operations", "management", "equipment", "vessel",
    "vessels", "tanker", "tankers", "types", "type", "guide", "procedure",
    "procedures", "basics", "case", "study", "part", "duties", "service", "services",
    "introduction", "overview", "standard", "standards", "general", "precautions",
    "checklist", "checklists", "work", "entry", "requirement", "requirements",
    "action", "actions", "plan", "plans", "method", "methods", "practice", "practices",
    "video", "videos", "image", "images", "course", "training", "level", "levels",
    "media", "medium", "agent", "agents", "material", "materials", "information",
    "details", "notes", "manual", "document", "regulation", "regulations", "code",
    "codes", "control", "controls", "function", "functions", "pressure", "discharge",
    "suction", "line", "lines", "use", "using", "used", "way", "ways", "aspect",
    "aspects", "point", "points", "item", "items", "flow", "device", "devices"
}

QUERY_STOP_WORDS: Set[str] = {
    "what", "is", "are", "the", "a", "an", "of", "and", "or", "in", "on", "for", "to",
    "how", "can", "you", "tell", "me", "about", "explain", "give", "details",
    "checklist", "checklists", "sms", "qms", "from", "my", "our", "provide",
    "please", "with", "entry", "work", "procedure", "procedures", "do", "we",
    "have", "show", "list", "steps", "guidelines", "document", "manual", "i",
    "need", "want", "know", "related", "any", "which", "when", "why", "where",
    "according", "regulations", "regulation", "does", "by", "at", "as", "into",
    "through", "during", "after", "before", "between", "under", "above"
}


# ---------------------------------------------------------------------------
# STEMMING & MORPHOLOGY HELPERS
# ---------------------------------------------------------------------------
def simple_stem(word: str) -> str:
    """
    Lightweight, conservative English singularization/stemming.
    Converts plurals to singular forms without aggressive stemming.
    """
    if not word or len(word) <= 3:
        return word
    w = word.lower()
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("es") and len(w) > 4 and w[-3] in ("s", "x", "z", "h"):
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


# ---------------------------------------------------------------------------
# CORE NORMALIZATION FUNCTIONS
# ---------------------------------------------------------------------------
def normalize_text_for_retrieval(text: str) -> str:
    """
    Canonical retrieval normalization function.
    
    Handles:
    - Lowercase
    - Unicode normalization (NFKD)
    - Apostrophes and smart quotes (' ’ ‘ ` ´ ")
    - Hyphens, en-dashes, em-dashes, underscores (-, —, –, _) -> replaced with spaces
    - Punctuation removal
    - Whitespace collapsing
    
    Example:
        "snap-back' zone" -> "snap back zone"
        "Centrifugal Pumps:" -> "centrifugal pumps"
    """
    if not text or not isinstance(text, str):
        return ""

    # 1. Unicode decomposition
    text = unicodedata.normalize("NFKD", text)

    # 2. Strip quotes, apostrophes, backticks, primes
    text = re.sub(r"['’‘`´\"]", "", text)

    # 3. Replace dashes, hyphens, slashes, underscores with space
    text = re.sub(r"[\-—–_/\\]", " ", text)

    # 4. Remove all other punctuation
    text = re.sub(r"[^\w\s]", " ", text)

    # 5. Lowercase and collapse whitespace
    return re.sub(r"\s+", " ", text.lower()).strip()


def tokenize_for_retrieval(text: str, stem: bool = False) -> List[str]:
    """
    Tokenize normalized text into a list of words.
    Optionally applies singularization (stem=True).
    """
    norm = normalize_text_for_retrieval(text)
    if not norm:
        return []
    tokens = norm.split()
    if stem:
        return [simple_stem(t) for t in tokens]
    return tokens


def get_collapsed_form(text: str) -> str:
    """
    Returns string with all spaces/hyphens removed for compound word matching.
    Example: "snap back zone" -> "snapbackzone"
    """
    norm = normalize_text_for_retrieval(text)
    return re.sub(r"\s+", "", norm)


def extract_distinctive_terms(text: str) -> List[str]:
    """
    Extract meaningful, domain-distinctive keywords from a query or title.
    Filters out stop words and common generic maritime words.
    """
    tokens = tokenize_for_retrieval(text)
    distinctive = []
    for t in tokens:
        stemmed = simple_stem(t)
        if t not in QUERY_STOP_WORDS and stemmed not in COMMON_GENERIC_WORDS and len(t) > 2:
            distinctive.append(t)
    return distinctive


def generate_ngrams(tokens: List[str], min_n: int = 2, max_n: int = 4) -> List[str]:
    """Generate multi-word n-gram phrases from a token list."""
    ngrams = []
    n_tokens = len(tokens)
    for n in range(min_n, min(max_n + 1, n_tokens + 1)):
        for i in range(n_tokens - n + 1):
            ngrams.append(" ".join(tokens[i:i+n]))
    return ngrams


def match_phrase_flexible(query_phrase: str, target_text: str) -> bool:
    """
    Checks whether query_phrase matches target_text under multiple normalized forms:
    1. Direct normalized phrase substring match
    2. Stemmed/singularized phrase match
    3. Collapsed compound word match (e.g. "snapback zone" in "snap back zone")
    """
    if not query_phrase or not target_text:
        return False

    norm_query = normalize_text_for_retrieval(query_phrase)
    norm_target = normalize_text_for_retrieval(target_text)

    if not norm_query or not norm_target:
        return False

    # 1. Exact normalized substring match with word boundary awareness
    if norm_query == norm_target:
        return True
    if re.search(r"\b" + re.escape(norm_query) + r"\b", norm_target):
        return True

    # 2. Singularized / stemmed token sequence match
    q_stems = [simple_stem(t) for t in norm_query.split()]
    t_stems = [simple_stem(t) for t in norm_target.split()]
    q_stem_phrase = " ".join(q_stems)
    t_stem_phrase = " ".join(t_stems)

    if q_stem_phrase == t_stem_phrase:
        return True
    if re.search(r"\b" + re.escape(q_stem_phrase) + r"\b", t_stem_phrase):
        return True

    # 3. Compound / collapsed match
    # Example: "snapback zone" vs "snap back zone" -> collapsed query "snapbackzone"
    collapsed_q = re.sub(r"\s+", "", norm_query)
    collapsed_t = re.sub(r"\s+", "", norm_target)
    if collapsed_q in collapsed_t and len(collapsed_q) >= 6:
        # Verify significant token overlap to prevent false positive short substring collisions
        q_tokens = set(q_stems)
        t_tokens = set(t_stems)
        if q_tokens.intersection(t_tokens) or any(qt in collapsed_t for qt in q_tokens if len(qt) >= 4):
            return True

    return False
