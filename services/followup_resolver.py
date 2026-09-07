from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple
from loguru import logger

# ---------------------------------------------------------------------------
# Common Maritime Keywords & Acronyms for Domain & Standalone Topic Detection
# ---------------------------------------------------------------------------
MARITIME_DOMAIN_TERMS = {
    "solas", "marpol", "ism", "stcw", "colreg", "eedi", "seemp", "cii", "cow",
    "igs", "ows", "sopep", "smpep", "mlc", "isps", "imdg", "igc", "ibc",
    "enclosed space", "enclosed spaces", "tank entry", "confined space",
    "cargo", "cargo loading", "cargo discharge", "bunker", "bunkering",
    "ballast", "ballast water", "bwts", "anchor", "anchoring", "mooring",
    "engine", "boiler", "purifier", "generator", "turbine", "steering",
    "rudder", "propeller", "shaft", "compressor", "pump", "valve",
    "navigation", "bridge", "oow", "passage planning", "ecdis", "radar", "ais",
    "lifeboat", "liferaft", "fire", "fire fighting", "fire extinguisher",
    "scba", "eebd", "gas detector", "multi-gas", "flammable", "toxic",
    "inert gas", "nitrogen", "purging", "gas freeing", "hot work", "cold work",
    "permit to work", "ptw", "risk assessment", "sms", "sop", "sops",
    "bilge", "sludge", "oily water", "incinerator", "sewage", "garbage",
    "draft", "trim", "stability", "hydrodynamics", "free surface",
    "crane", "winch", "windlass", "hatch cover", "cargo hold", "ullage",
    "sounding", "stripping", "crude oil washing", "tank cleaning"
}

# ---------------------------------------------------------------------------
# Follow-up Pattern Categories (Regex & Keyword Matchers)
# ---------------------------------------------------------------------------
DEPTH_PATTERNS = [
    r"\btell\s+me\s+(in\s*depth|indepth|more|everything|in\s*detail|all\s*about\s*it)\b",
    r"\bexplain\s+(in\s*depth|indepth|more|further|everything|in\s*detail|the\s*above|this|that)\b",
    r"\bgive\s+(me\s+)?(more\s+details?|in\s*depth|indepth|full\s+details?|more\s+info(rmation)?|further\s+details?)\b",
    r"\b(elaborate|go\s+deeper|deep\s+dive|expand(\s+further|\s+more|\s+on\s+this)?|continue|more\s+details?|details?\s+please|indepth|in\s+depth|in\s+detail)\b",
]

REQUIREMENTS_PATTERNS = [
    r"\bwhat\s+(are\s+the\s+)?requirements?\b",
    r"\bwhat\s+is\s+required\b",
    r"\brequirements?\s+for\s+this\b",
    r"\bwhat\s+rules?\s+(apply|are\s+there)\b",
    r"\bwhat\s+regulations?\s+(apply|are\s+there)\b",
    r"\bstatutory\s+requirements?\b",
    r"\bmandatory\s+requirements?\b",
]

PRECAUTIONS_PATTERNS = [
    r"\bwhat\s+(are\s+the\s+)?precautions?\b",
    r"\bwhat\s+(are\s+the\s+)?safety\s+precautions?\b",
    r"\bwhat\s+precautions?\s+should\s+be\s+taken\b",
    r"\bwhat\s+(are\s+the\s+)?hazards?\b",
    r"\bhazards?\s+involved\b",
    r"\bsafety\s+measures?\b",
    r"\bsafety\s+rules?\b",
    r"\bprecautions?\s+and\s+hazards?\b",
]

PROCEDURES_PATTERNS = [
    r"\b(give\s+me\s+)?(the\s+)?full\s+procedure\b",
    r"\bwhat\s+is\s+the\s+procedure\b",
    r"\bwhat\s+are\s+the\s+steps\b",
    r"\bstep\s+by\s+step\b",
    r"\bhow\s+to\s+perform\s+this\b",
    r"\bhow\s+is\s+this\s+done\b",
    r"\boperational\s+steps?\b",
    r"\bexecution\s+steps?\b",
    r"\bcomplete\s+procedure\b",
    r"\bstandard\s+operating\s+procedure\b",
]

CHECKLIST_PATTERNS = [
    r"\bwhat\s+(are\s+the\s+)?(specific\s+)?checklists?(\s+for\s+this)?\b",
    r"\bchecklists?\s+for\s+this\b",
    r"\bwhat\s+forms?\s+(are\s+needed|required)\b",
    r"\bpermits?\s+required\b",
    r"\bentry\s+permit\b",
    r"\bptw\s+for\s+this\b",
    r"\bpermit\s+to\s+work\s+checklist\b",
    r"\bforms?\s+and\s+checklists?\b",
]

EQUIPMENT_PATTERNS = [
    r"\bwhat\s+(are\s+the\s+)?equipment(\s+needed|\s+required)?\b",
    r"\bequipment\s+required\b",
    r"\btools\s+and\s+equipment\b",
    r"\bwhat\s+ppe\s+is\s+required\b",
    r"\bpersonal\s+protective\s+equipment\b",
    r"\bminimum\s+equipment\b",
]

RESPONSIBILITY_PATTERNS = [
    r"\bwho\s+is\s+responsible(\s+for\s+this)?\b",
    r"\bduties\s+and\s+responsibilities\b",
    r"\bcrew\s+responsibilities\b",
    r"\bmaster'?s\s+responsibility\b",
    r"\bchief\s+officer'?s\s+responsibility\b",
]

ANAPHORIC_PRONOUN_PATTERNS = [
    r"^(what\s+about|explain|tell\s+me\s+about|how\s+about)\s+(this|that|these|those|it|the\s+above)\b",
    r"^(why|how|when|where)\s+(is|are|does|do|did|was|were)\s+(this|that|it)\b",
    r"^(what\s+does\s+this\s+mean|what\s+does\s+that\s+mean)\b",
    r"^(why\s+so|how\s+so)\b",
]

POINT_REFERENCE_PATTERNS = [
    r"\b(point|step|item|section|clause|paragraph|part)\s+(\d+|[ivx]+|one|two|three|four|five|first|second|third|last|previous)\b",
    r"\b(first|second|third|fourth|fifth|last)\s+(point|step|item|section|clause|part)\b",
    r"\bthe\s+(first|second|third|fourth|fifth|last)\s+one\b",
]

TOPIC_SWITCH_PREFIXES = [
    r"^now\s+(explain|tell\s+me\s+about|describe|what\s+is|what\s+are|how\s+about)\s+",
    r"^switch\s+to\s+",
    r"^let'?s\s+talk\s+about\s+",
    r"^next\s+(topic\s+is|question\s+is|explain)\s+",
    r"^change\s+topic\s+to\s+",
    r"^what\s+about\s+(?!this\b|that\b|it\b|the\s+above\b)",
]


FOLLOWUP_META_WORDS = {
    "tell", "me", "in", "depth", "indepth", "more", "everything", "detail", "details", "detailed",
    "explain", "explanation", "give", "further", "elaborate", "elaboration", "go", "deeper", "deep",
    "dive", "expand", "expansion", "continue", "continuation", "what", "is", "are", "the", "a", "an",
    "for", "of", "about", "to", "on", "and", "or", "this", "that", "these", "those", "it", "above",
    "precaution", "precautions", "safety", "hazard", "hazards", "procedure", "procedures", "step",
    "steps", "checklist", "checklists", "form", "forms", "permit", "permits", "ptw", "equipment",
    "ppe", "requirement", "requirements", "rule", "rules", "regulation", "regulations",
    "responsible", "responsibility", "responsibilities", "duties", "duty", "who", "why", "how",
    "when", "where", "can", "could", "would", "will", "you", "please", "point", "points", "item",
    "items", "section", "sections", "clause", "clauses", "paragraph", "first", "second", "third",
    "fourth", "fifth", "last", "one", "two", "three", "four", "five", "all", "full", "complete",
    "specific", "necessary", "needed", "required", "info", "information", "guidance", "standard",
    "operating", "sop", "sops", "meaning", "does", "do", "did", "was", "were", "so", "case",
    "during", "regarding", "work", "look", "overview", "summary", "summarize", "brief", "briefly",
    "clarify", "clarification", "outline", "list", "notes", "note", "provide", "show"
}


def clean_query_text(text: str) -> str:
    """Normalize whitespace and strip punctuation for pattern testing."""
    if not text:
        return ""
    t = re.sub(r"\s+", " ", text.strip())
    return t


def extract_topic_from_query(query: str) -> str:
    """
    Extract a clean canonical topic string from a standalone user question.
    Examples:
    - 'Procedures for Enclosed Space Entry' -> 'Procedures for Enclosed Space Entry'
    - 'Explain cargo loading sequence' -> 'Cargo Loading Sequence'
    - 'What is boiler water treatment?' -> 'Boiler Water Treatment'
    - 'Can you explain the COLREG Rule 15?' -> 'COLREG Rule 15'
    """
    if not query:
        return ""

    q = clean_query_text(query)

    # Check for explicit topic switch prefixes first
    for prefix_pat in TOPIC_SWITCH_PREFIXES:
        if re.search(prefix_pat, q, re.IGNORECASE):
            q = re.sub(prefix_pat, "", q, flags=re.IGNORECASE).strip()
            break

    # Strip standard conversational opening phrases
    openers = [
        r"^(can|could|would|will)\s+(you\s+)?(please\s+)?(explain|tell\s+me\s+about|describe|detail|show|give\s+me)\s+(to\s+me\s+)?",
        r"^(please\s+)?(explain|tell\s+me\s+about|describe|detail|give\s+me\s+details\s+on)\s+",
        r"^(what\s+is|what\s+are|what\s+do\s+you\s+know\s+about|how\s+does|how\s+do|how\s+to)\s+",
        r"^(tell\s+me\s+the\s+procedure\s+for|give\s+me\s+the\s+procedure\s+for)\s+",
    ]
    cleaned = q
    for pat in openers:
        if re.search(pat, cleaned, re.IGNORECASE):
            cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE).strip()
            break

    # Strip leading articles like 'the', 'a', 'an'
    cleaned = re.sub(r"^(the|a|an)\s+", "", cleaned, flags=re.IGNORECASE).strip()

    # Clean punctuation
    cleaned = cleaned.rstrip("?.!,:;").strip()

    # If the resulting string is meaningful, title-case or preserve
    if len(cleaned) >= 3:
        # Preserve acronyms like SOLAS, MARPOL, EEDI, COLREG
        words = cleaned.split()
        title_cased = []
        for i, w in enumerate(words):
            if w.isupper() and len(w) >= 2:
                title_cased.append(w)
            elif i > 0 and w.lower() in {"and", "or", "for", "to", "in", "of", "on", "the", "a", "an"}:
                title_cased.append(w.lower())
            else:
                title_cased.append(w.capitalize())
        topic = " ".join(title_cased)
        return topic

    return q.rstrip("?.!,:;").strip()


def is_followup_query(
    current_query: str,
    previous_questions: List[str] | None = None,
    conversation_topic: str = "",
) -> bool:
    """
    Determine whether the current user message is a conversational follow-up or a standalone new question.
    """
    if not current_query:
        return False

    if isinstance(conversation_topic, list):
        conversation_topic = str(conversation_topic[0]) if conversation_topic else ""
    elif not isinstance(conversation_topic, str):
        conversation_topic = str(conversation_topic or "")

    q = clean_query_text(current_query).lower()
    words = re.findall(r"\b[a-z0-9]+\b", q)

    # If no prior conversation history or active topic exists, cannot be a follow-up
    has_prior_context = bool(previous_questions) or bool(conversation_topic)
    if not has_prior_context:
        return False

    # Check for explicit topic switch prefixes
    for prefix_pat in TOPIC_SWITCH_PREFIXES:
        if re.search(prefix_pat, q, re.IGNORECASE):
            # If switching topic with a specific non-pronoun topic, it is a NEW question
            remaining = re.sub(prefix_pat, "", q, flags=re.IGNORECASE).strip()
            if len(remaining) > 3 and not any(re.match(p, remaining) for p in [r"^(this|that|it|the\s+above)\b"]):
                return False

    # Check if this is an explicit anaphoric reference to previous topic
    has_anaphoric = any(re.search(pat, q) for pat in ANAPHORIC_PRONOUN_PATTERNS) or bool(
        re.search(r"\b(for\s+this|about\s+this|of\s+this|in\s+this\s+case|for\s+that|about\s+that)\b", q)
    )

    # Check if query introduces a distinct new subject / maritime domain term
    if conversation_topic and not has_anaphoric:
        topic_words = set(re.findall(r"\b[a-z0-9]+\b", conversation_topic.lower()))
        query_words = set(words)
        substantive_words = {w for w in query_words if w not in FOLLOWUP_META_WORDS and not w.isdigit()}
        new_subject_words = substantive_words - topic_words

        has_new_domain_term = any(
            (
                re.search(rf"\b{re.escape(term)}\b", q)
                and not any(re.search(rf"\b{re.escape(w)}\b", conversation_topic.lower()) for w in term.split())
            )
            for term in MARITIME_DOMAIN_TERMS
        )
        if len(new_subject_words) >= 2 or has_new_domain_term:
            return False

    # 1. Check Depth / Detail / Continuation matchers
    for pat in DEPTH_PATTERNS:
        if re.search(pat, q, re.IGNORECASE):
            return True

    # 2. Check Requirements matchers
    for pat in REQUIREMENTS_PATTERNS:
        if re.search(pat, q, re.IGNORECASE):
            return True

    # 3. Check Precautions / Safety matchers
    for pat in PRECAUTIONS_PATTERNS:
        if re.search(pat, q, re.IGNORECASE):
            return True

    # 4. Check Procedures / Steps matchers
    for pat in PROCEDURES_PATTERNS:
        if re.search(pat, q, re.IGNORECASE):
            return True

    # 5. Check Checklists / Forms matchers
    for pat in CHECKLIST_PATTERNS:
        if re.search(pat, q, re.IGNORECASE):
            return True

    # 6. Check Equipment / Responsibility matchers
    for pat in EQUIPMENT_PATTERNS + RESPONSIBILITY_PATTERNS:
        if re.search(pat, q, re.IGNORECASE):
            return True

    # 7. Check Anaphoric pronouns (this, that, it, the above)
    for pat in ANAPHORIC_PRONOUN_PATTERNS:
        if re.search(pat, q, re.IGNORECASE):
            return True

    # 8. Check Point / Item references (e.g. "point 2", "step 3", "first item")
    for pat in POINT_REFERENCE_PATTERNS:
        if re.search(pat, q, re.IGNORECASE):
            return True

    # 9. Short phrases (<= 4 words) that lack a distinct maritime subject
    if len(words) <= 4:
        followup_short_terms = {
            "this", "that", "these", "those", "it", "above", "more", "detail", "details",
            "indepth", "depth", "elaborate", "further", "continue", "deeper", "procedure",
            "checklist", "checklists", "precaution", "precautions", "requirement", "requirements",
            "rules", "regulations", "equipment", "responsible", "responsibility", "steps", "why",
            "how", "when", "clarify", "explain", "tell", "expand"
        }
        if any(w in followup_short_terms for w in words):
            domain_overlap = set(words).intersection(MARITIME_DOMAIN_TERMS)
            if not domain_overlap or (conversation_topic and any(d in conversation_topic.lower() for d in domain_overlap)):
                return True

    # 10. Questions containing "for this", "about this", "of this", "in this case"
    if re.search(r"\b(for\s+this|about\s+this|of\s+this|in\s+this\s+case|for\s+that|about\s+that)\b", q):
        return True

    return False


def _extract_point_context_from_answer(
    current_query: str,
    last_answer: str | None,
) -> str:
    """
    If the user asks about 'point 2', 'step 3', or 'second item', extract that specific
    point or line from the previous assistant answer.
    """
    if not last_answer:
        return ""

    q = current_query.lower()

    # Match numeric point/step (e.g., "point 2", "step 3")
    num_match = re.search(r"\b(?:point|step|item|section|clause)\s+(\d+)\b", q)
    target_num = int(num_match.group(1)) if num_match else None

    # Match word ordinal (e.g., "first", "second", "third")
    if target_num is None:
        word_ordinals = {
            "first": 1, "one": 1,
            "second": 2, "two": 2,
            "third": 3, "three": 3,
            "fourth": 4, "four": 4,
            "fifth": 5, "five": 5,
            "sixth": 6, "six": 6,
        }
        for word, num in word_ordinals.items():
            if re.search(rf"\b(?:the\s+)?{word}\s+(?:point|step|item|one)\b", q):
                target_num = num
                break

    if target_num is not None:
        # Search for numbered lines or bullet headers in last_answer
        lines = last_answer.split("\n")
        # Pattern 1: "1. **Title:**" or "1. Title"
        for line in lines:
            m = re.match(rf"^\s*{target_num}[\.\)]\s+(.+)", line)
            if m:
                clean_line = re.sub(r"[*#_]", "", m.group(1)).strip()
                return clean_line[:120]
        # Pattern 2: "#### 2. Title" or "##### 2. Title"
        for line in lines:
            m = re.match(rf"^\s*#+\s*(?:\d+\.)?\s*{target_num}[\.\)]?\s*(.+)", line)
            if m:
                clean_line = re.sub(r"[*#_]", "", m.group(1)).strip()
                return clean_line[:120]

    return ""


def resolve_followup_retrieval_query(
    current_query: str,
    topic: str,
    last_answer: str | None = None,
) -> Tuple[str, bool]:
    """
    Resolve a follow-up query against the active conversation topic into an internal retrieval query.

    Returns:
        Tuple[str, bool]: (resolved_retrieval_query, is_depth_expansion)
    """
    if isinstance(topic, list):
        topic = str(topic[0]) if topic else ""
    elif not isinstance(topic, str):
        topic = str(topic or "")

    if not topic:
        return current_query, False

    q = clean_query_text(current_query)
    q_lower = q.lower()

    # 1. Depth / In-depth / Elaboration Requests
    if any(re.search(pat, q_lower) for pat in DEPTH_PATTERNS):
        resolved = (
            f"{topic} — detailed explanation of all relevant procedures, requirements, "
            f"precautions, equipment, responsibilities and emergency arrangements."
        )
        return resolved, True

    # 2. Checklists / Forms / PTW Requests
    if any(re.search(pat, q_lower) for pat in CHECKLIST_PATTERNS):
        resolved = (
            f"{topic} — checklists, permit to work forms, verification steps, "
            f"and safety checks."
        )
        return resolved, False

    # 3. Requirements / Statutory Regulations Requests
    if any(re.search(pat, q_lower) for pat in REQUIREMENTS_PATTERNS):
        resolved = (
            f"{topic} — statutory requirements, SOLAS regulations, ISM code standards, "
            f"and mandatory operational criteria."
        )
        return resolved, False

    # 4. Precautions / Safety / Hazards Requests
    if any(re.search(pat, q_lower) for pat in PRECAUTIONS_PATTERNS):
        resolved = (
            f"{topic} — safety precautions, hazard identification, risk assessment, "
            f"atmospheric testing, personal protective equipment, and protective measures."
        )
        return resolved, False

    # 5. Procedures / Steps / Execution Requests
    if any(re.search(pat, q_lower) for pat in PROCEDURES_PATTERNS):
        resolved = (
            f"{topic} — step-by-step operating procedure, preparation, execution, "
            f"and completion checklist."
        )
        return resolved, False

    # 6. Equipment / Tools / PPE Requests
    if any(re.search(pat, q_lower) for pat in EQUIPMENT_PATTERNS):
        resolved = (
            f"{topic} — required safety equipment, gas detectors, personal protective equipment (PPE), "
            f"minimum required quantities, and testing instruments."
        )
        return resolved, False

    # 7. Responsibility / Duties Requests
    if any(re.search(pat, q_lower) for pat in RESPONSIBILITY_PATTERNS):
        resolved = (
            f"{topic} — duties and responsibilities of Master, Chief Officer, "
            f"officers of the watch (OOW), safety officer, and entry team."
        )
        return resolved, False

    # 8. Point / Step Reference (e.g. "explain point 2", "step 3")
    point_context = _extract_point_context_from_answer(current_query, last_answer)
    if point_context:
        resolved = f"{topic} — detailed explanation of {point_context}"
        return resolved, True

    # 9. Generic Anaphoric or Combined Follow-up
    # Strip pronouns like "what about this" -> combine with topic
    clean_followup = re.sub(r"^(what\s+about|tell\s+me\s+about|explain|how\s+about)\s+(this|that|it|the\s+above)\s*", "", q, flags=re.IGNORECASE).strip()
    if not clean_followup or clean_followup.lower() in {"this", "that", "it", "the above"}:
        resolved = f"{topic} — comprehensive details, procedures, and guidance."
    else:
        resolved = f"{topic} — {clean_followup}"

    return resolved, False
