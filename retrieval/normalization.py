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
    "aspects", "point", "points", "item", "items", "flow", "device", "devices",
    "zone", "zones", "back", "area", "areas", "side", "sides", "part", "parts",
    "fuel", "fuels", "bunker", "bunkers", "tank", "tanks", "low", "high", "drop",
    "drops", "capacity", "store", "storage", "carry", "carrying",
    "detailed", "explanation", "explanations", "relevant", "arrangements", "arrangement",
    "responsibilities", "responsibility", "guidelines", "guideline", "instructions", "instruction",
    "measures", "measure", "provisions", "provision", "criteria", "elements", "element"
}

QUERY_STOP_WORDS: Set[str] = {
    "what", "is", "are", "the", "a", "an", "of", "and", "or", "in", "on", "for", "to",
    "how", "can", "you", "tell", "telling", "me", "about", "explain", "explaining",
    "explan", "explai", "exlpain", "give", "giving", "details", "detail", "describe", "describing",
    "discuss", "discussing", "state", "stating", "outline", "outlining", "summarize",
    "summarizing", "elaborate", "elaborat", "elaborating", "define", "defining", "brief",
    "briefing", "show", "showing", "provide", "providing", "write", "writing",
    "checklist", "checklists", "sms", "qms", "from", "my", "our", "please",
    "with", "entry", "work", "procedure", "procedures", "do", "we", "have",
    "list", "steps", "guidelines", "guideline", "document", "manual", "i", "need", "want",
    "know", "related", "any", "which", "when", "why", "where", "according",
    "regulations", "regulation", "does", "by", "at", "as", "into", "through",
    "during", "after", "before", "between", "under", "above", "used", "onboard", "board",
    "difference", "differences", "different", "differ", "differs",
    "between", "among", "compare", "comparison", "comparisons", "comparative",
    "contrasting", "contrast", "versus", "vs",
    "distinguish", "distinction", "distinctions", "similarity", "similarities", "similar",
    "meaning", "definition", "definitions", "significance", "purpose", "purposes",
    "objective", "objectives", "importance",
    "advantage", "advantages", "disadvantage", "disadvantages", "benefit", "benefits",
    "limitation", "limitations", "pros", "cons",
    "concept", "concepts", "aspect", "aspects", "feature", "features",
    "detailed", "explanation", "explanations", "relevant", "responsibilities", "responsibility",
    "arrangements", "arrangement", "more", "mor", "further", "furthur", "deeper", "deep", "dive",
    "everything", "anything", "all"
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


# Precomputed fast character translation table and compiled whitespace regex
_NORM_TRANSLATION_TABLE = str.maketrans({
    "'": "", "’": "", "‘": "", "`": "", "´": "", '"': "", "“": "", "”": "", "„": "", "‚": "", "«": "", "»": "", "‗": "",
    "-": " ", "—": " ", "–": " ", "―": " ", "‒": " ", "_": " ", "/": " ", "\\": " ",
    ":": " ", ";": " ", ",": " ", ".": " ", "!": " ", "?": " ",
    "(": " ", ")": " ", "[": " ", "]": " ", "{": " ", "}": " ",
    "<": " ", ">": " ", "@": " ", "#": " ", "$": " ", "%": " ",
    "^": " ", "&": " ", "*": " ", "+": " ", "=": " ", "|": " ",
    "~": " ", "•": " ", "·": " ", "\t": " ", "\r": " ", "\n": " ",
})
_NON_ALPHANUM_RE = re.compile(r"[^\w\s]")
_WHITESPACE_RE = re.compile(r"\s+")


KNOWN_COMPOUND_MAP: Dict[str, str] = {
    "snapback": "snap back",
    "snapbacks": "snap backs",
    "flashpoint": "flash point",
    "flashpoints": "flash points",
    "lifeboat": "life boat",
    "lifeboats": "life boats",
    "liferaft": "life raft",
    "liferafts": "life rafts",
    "lifebuoy": "life buoy",
    "lifebuoys": "life buoys",
    "lifejacket": "life jacket",
    "lifejackets": "life jackets",
    "firefighting": "fire fighting",
    "firefighter": "fire fighter",
    "firefighters": "fire fighters",
    "firepump": "fire pump",
    "firepumps": "fire pumps",
    "crudeoil": "crude oil",
    "inertgas": "inert gas",
    "freshwater": "fresh water",
    "seawater": "sea water",
    "shipboard": "ship board",
    "bilgewater": "bilge water",
    "blackwater": "black water",
    "greywater": "grey water",
    "oilwater": "oil water",
    "nonreturn": "non return",
    "quickclosing": "quick closing",
    "selfpriming": "self priming",
    "watertight": "water tight",
    "weathertight": "weather tight",
    "gasfree": "gas free",
    "gasfreeing": "gas freeing",
    "antifouling": "anti fouling",
    "overpressure": "over pressure",
    "overcurrent": "over current",
    "backpressure": "back pressure",
    "hawsepipe": "hawse pipe",
    "flowmeter": "flow meter",
    "crankcase": "crank case",
    "crosshead": "cross head",
    "camshaft": "cam shaft",
    "crankshaft": "crank shaft",
    "turbocharger": "turbo charger",
    "supercharger": "super charger",
    "airlock": "air lock",
    "deckhead": "deck head",
    "bulkhead": "bulk head",
    "shipshore": "ship shore",
    "blowby": "blow by",
    "blowdown": "blow down",
    "washwater": "wash water",
    "feedwater": "feed water",
    "coolingwater": "cooling water",
    "portside": "port side",
    "towline": "tow line",
    "towlines": "tow lines",
    "heavingline": "heaving line",
    "heavinglines": "heaving lines",
    "pilotladder": "pilot ladder",
}

_COMPOUND_REGEX = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in sorted(KNOWN_COMPOUND_MAP.keys(), key=len, reverse=True)) + r")\b",
    re.IGNORECASE
)


def decompound_known_words(text: str) -> str:
    """Split known compound maritime words into their separated constituent words."""
    if not text:
        return ""
    return _COMPOUND_REGEX.sub(lambda m: KNOWN_COMPOUND_MAP[m.group(0).lower()], text)


def is_term_or_compound_in_text(term: str, text: str) -> bool:
    """
    Check if term (or its singular stem or collapsed compound form) appears in text.
    Handles 'snapback' in 'snap-back', 'life boat' in 'lifeboat', etc.
    """
    if not term or not text:
        return False
    t_lower = text.lower()
    term_lower = term.lower()
    
    if term_lower in t_lower or simple_stem(term_lower) in t_lower:
        return True

    # Check decompounded form
    decomp = decompound_known_words(term_lower)
    if decomp != term_lower and (decomp in t_lower or simple_stem(decomp) in t_lower):
        return True

    # Check collapsed form (spaces, hyphens, underscores removed)
    collapsed_term = re.sub(r"[\s\-_]+", "", term_lower)
    collapsed_text = re.sub(r"[\s\-_]+", "", t_lower)
    if len(collapsed_term) >= 4 and collapsed_term in collapsed_text:
        return True

    return False


def normalize_text_for_retrieval(text: str) -> str:
    """
    Canonical high-speed retrieval normalization function.
    
    Handles:
    - Lowercase
    - Unicode normalization (NFKD)
    - Apostrophes and smart quotes (' ’ ‘ ` ´ ")
    - Hyphens, en-dashes, em-dashes, underscores (-, —, –, _) -> replaced with spaces
    - Punctuation removal
    - Decompounding of known compound words
    - Whitespace collapsing
    
    Example:
        "snap-back' zone" -> "snap back zone"
        "snapback zone" -> "snap back zone"
        "Centrifugal Pumps:" -> "centrifugal pumps"
    """
    if not text or not isinstance(text, str):
        return ""

    # 1. Unicode decomposition
    t = unicodedata.normalize("NFKD", text)

    # 2. Fast character translation
    t = t.translate(_NORM_TRANSLATION_TABLE)

    # 3. Strip remaining non-alphanumeric/non-space symbols if any
    if not t.isascii():
        t = _NON_ALPHANUM_RE.sub(" ", t)

    # 4. Decompound known compound words
    t = decompound_known_words(t)

    # 5. Lowercase and collapse whitespace
    return _WHITESPACE_RE.sub(" ", t.lower()).strip()



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
    Includes both original distinctive tokens and decompounded constituent tokens.
    """
    if not text or not isinstance(text, str):
        return []

    # 1. Tokens from normalized decompounded text
    tokens = tokenize_for_retrieval(text)
    
    # 2. Raw words before decompounding (to preserve words like 'snapback', 'lifeboat', etc.)
    raw_cleaned = unicodedata.normalize("NFKD", text).translate(_NORM_TRANSLATION_TABLE)
    raw_tokens = raw_cleaned.lower().split()
    
    distinctive = []
    seen = set()

    for t in raw_tokens + tokens:
        stemmed = simple_stem(t)
        if t not in seen and t not in QUERY_STOP_WORDS and stemmed not in COMMON_GENERIC_WORDS and len(t) > 2:
            seen.add(t)
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
