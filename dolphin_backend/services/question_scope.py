"""
services/question_scope.py

Question scope classification and specific subject term extraction.
Classifies eligible user questions as either:
  - GENERAL: requests an abbreviation's full form or meaning, a definition,
             or a broad overview (e.g., 'What does EGCS stand for?', 'What is EGCS?', 'Explain EGCS.').
  - SPECIFIC: asks about a particular component, operation, procedure, fault,
              cause, effect, parameter, or other narrow detail (e.g.,
              'How does the EGCS scrubber remove sulphur?', 'What causes high pressure drop in an EGCS?').

Ensures follow-up questions evaluate scope using the resolved standalone query.
"""

from typing import Any, Dict, List, Optional, Set
import re

from services.maritime_acronyms import (
    find_acronyms_in_query,
    COMMON_ENGLISH_STOPWORDS,
    GENERIC_MARITIME_WORDS,
    GLOBAL_MARITIME_FRAMEWORKS,
)

SCOPE_GENERAL = "GENERAL"
SCOPE_SPECIFIC = "SPECIFIC"

# ── Feature Flag ──
# Set to False to completely disable question scope classification and subject filtering.
# All questions will be treated as standard GENERAL queries with zero scope restrictions.
ENABLE_QUESTION_SCOPE: bool = True

# Patterns indicating an abbreviation expansion / meaning request (GENERAL)
ABBREVIATION_PATTERNS = [
    re.compile(r'\b(?:what\s+does|what\s+do)\s+([a-zA-Z0-9\-_]+)\s+stand\s+for\b', re.IGNORECASE),
    re.compile(r'\bstand\s+for\b', re.IGNORECASE),
    re.compile(r'\bfull\s+form\s+(?:of\s+)?([a-zA-Z0-9\-_]+)?\b', re.IGNORECASE),
    re.compile(r'\bfull\s+name\s+(?:of\s+)?([a-zA-Z0-9\-_]+)?\b', re.IGNORECASE),
    re.compile(r'\bmeaning\s+of\s+([a-zA-Z0-9\-_]+)\b', re.IGNORECASE),
    re.compile(r'\bwhat\s+does\s+([a-zA-Z0-9\-_]+)\s+mean\b', re.IGNORECASE),
    re.compile(r'\bexpand\s+(?:the\s+acronym\s+|the\s+abbreviation\s+)?([a-zA-Z0-9\-_]+)\b', re.IGNORECASE),
    re.compile(r'\bwhat\s+is\s+the\s+abbreviation\b', re.IGNORECASE),
    re.compile(r'\bwhat\s+is\s+the\s+acronym\b', re.IGNORECASE),
]

# Patterns indicating broad definition or high-level overview (GENERAL unless overridden by specific indicators)
BROAD_OVERVIEW_PATTERNS = [
    re.compile(r'^(?:what\s+is|what\s+are)\s+(?:an?|the)?\s*([a-zA-Z0-9\s\-_]+)\??$', re.IGNORECASE),
    re.compile(r'^(?:explain|describe|tell\s+me\s+about)\s+(?:an?|the)?\s*([a-zA-Z0-9\s\-_]+)\??$', re.IGNORECASE),
    re.compile(r'^(?:overview\s+of|introduction\s+to|intro\s+to|basics\s+of|fundamentals\s+of)\s+(?:an?|the)?\s*([a-zA-Z0-9\s\-_]+)\??$', re.IGNORECASE),
    re.compile(r'^(?:give\s+me\s+an?\s+overview\s+of)\s+([a-zA-Z0-9\s\-_]+)\??$', re.IGNORECASE),
    re.compile(r'^(?:general\s+principles\s+of)\s+([a-zA-Z0-9\s\-_]+)\??$', re.IGNORECASE),
    re.compile(r'^(?:types\s+of|kinds\s+of|classification\s+of|categories\s+of)\s+([a-zA-Z0-9\s\-_]+)\??$', re.IGNORECASE),
]

# Strong keywords indicating a narrow detail, particular component, operational mechanism,
# procedure, fault, cause, effect, parameter, threshold, physical instrument, or regulatory timeline (SPECIFIC)
SPECIFIC_KEYWORDS_PATTERN = re.compile(
    r'\b('
    # Faults, Causes, Effects, Symptoms
    r'cause|causes|caused|what\s+causes|why\s+does|why\s+is|fault|faults|faulty|failure|failures|fail|fails|failed|'
    r'troubleshoot|troubleshooting|alarm|alarms|tripping|tripped|trip|trips|defect|defects|malfunction|'
    r'pressure\s+drop|differential\s+pressure|high\s+pressure|low\s+pressure|high\s+temp|low\s+temp|'
    r'overheating|overheat|leak|leakage|leaking|vibration|vibrating|black\s+smoke|white\s+smoke|'
    r'symptom|symptoms|remedy|remedies|consequence|consequences|what\s+happens\s+if|in\s+case\s+of|'
    # Operational mechanisms & chemical/physical processes
    r'how\s+does\s+.*?\s+remove|how\s+does\s+.*?\s+work|how\s+does\s+.*?\s+operate|'
    r'remove|removes|removal|removing|absorb|absorbs|absorption|scrubbing|neutralize|neutralization|'
    r'chemical\s+reaction|reaction|dilution|washwater|wash\s+water|effluent|sox\s+removal|nox\s+reduction|'
    # Procedures, Actions, Operations
    r'how\s+to\s+calibrate|how\s+to\s+start|how\s+to\s+stop|how\s+to\s+operate|how\s+to\s+maintain|how\s+to\s+clean|'
    r'how\s+to\s+test|how\s+to\s+inspect|how\s+to\s+prepare|how\s+to\s+set|'
    r'procedure|procedures|step|steps|checklist|action|actions|guidelines\s+to|'
    r'calibrate|calibration|calibrating|maintenance|overhaul|overhauling|inspection|inspecting|'
    r'pre-start|starting|shutting\s+down|shutdown|bunkering|purging|flushing|sampling|'
    # Narrow Parameters, Limits, Thresholds
    r'ph\s+limit|ph\s+value|ph\s+requirement|limit|limits|threshold|thresholds|criterion|criteria|'
    r'permissible|maximum\s+limit|minimum\s+limit|operating\s+range|setpoint|set\s+point|'
    r'turbidity|pah|nitrate|nitrates|ppm|15\s*ppm|discharge\s+criteria|discharge\s+limit|'
    # Physical Instruments, Measuring Devices & Detectors
    r'gas\s*meter|gas\s*meters|flowmeter|flowmeters|flow\s*meter|flow\s*meters|'
    r'meter|meters|gauge|gauges|pyrometer|pyrometers|manometer|manometers|'
    r'detector|detectors|gas\s*detector|gas\s*detectors|smoke\s*detector|flame\s*detector|'
    r'analyzer|analyzers|analyser|analysers|recorder|recorders|'
    r'indicator|indicators|transmitter|transmitters|tachometer|tachometers|'
    r'viscometer|viscometers|densitometer|densitometers|calorimeter|salinometer|'
    # Particular components & subsystems
    r'sensor|sensors|transducer|transducers|electrode|electrodes|probe|probes|'
    r'valve|valves|pump|pumps|strainer|strainers|demister|nozzle|nozzles|spray\s+nozzle|'
    r'heat\s+exchanger|cooler|condenser|burner|injector|atomizer|'
    r'scrubber\s+tower|holding\s+tank|settling\s+tank|caustic\s+soda|cyclone|separator\s+bowl|'
    r'bilge\s+alarm|oil\s+content\s+meter|ocm|15\s*ppm\s+bilge|'
    r'governor|actuator|actuators|filter\s+element|fuel\s+injector|intercooler|turbocharger|'
    # Specialized machinery sub-types, propulsion & engine architectures (SPECIFIC)
    r'camshaft[\s\-]*less|camless|cam[\s\-]*shaft|camshaft|camshafts|'
    r'common[\s\-]*rail|electronic(?:ally)?[\s\-]*controlled|intelligent[\s\-]*engine|'
    r'dual[\s\-]*fuel|tri[\s\-]*fuel|two[\s\-]*stroke|four[\s\-]*stroke|2[\s\-]*stroke|4[\s\-]*stroke|'
    r'crosshead|trunk[\s\-]*piston|waste[\s\-]*heat[\s\-]*recovery|'
    r'variable[\s\-]*pitch|controllable[\s\-]*pitch|cpp|fpp|'
    r'shaft[\s\-]*generator|bow[\s\-]*thruster|stern[\s\-]*thruster|azipod|'
    r'exhaust[\s\-]*valve|cylinder[\s\-]*liner|piston[\s\-]*ring|piston[\s\-]*crown|'
    r'crankcase|crankshaft|connecting[\s\-]*rod|bedplate|thrust[\s\-]*bearing|main[\s\-]*bearing|'
    r'stuffing[\s\-]*box|scavenge[\s\-]*air|'
    # Regulatory timelines, specific effective dates & entry-into-force triggers
    r'effective\s+(?:date|dates|from|on|in|as\s+of)|'
    r'effective\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)|'
    r'effective\s+(?:20\d\d)|'
    r'entry\s+into\s+force|coming\s+into\s+force|enter\s+into\s+force|comes\s+into\s+force|'
    r'enforcement\s+date|compliance\s+deadline|compliance\s+date|implementation\s+date|'
    r'mandated\s+(?:from|by|in|on)|mandatory\s+(?:from|by|in|on)'
    r')\b',
    re.IGNORECASE
)

# Targeted regulatory inquiries on a concrete subject or subsystem
TARGETED_REGULATION_PATTERN = re.compile(
    r'\b(?:regulations?|rules?|amendments?|requirements?|standards?|mandates?|guidelines?|circulars?)\s+(?:on|for|regarding|concerning|governing)\s+([a-zA-Z0-9\s\-_]+)',
    re.IGNORECASE
)

# Administrative and timeline carrier words to strip when extracting specific subject terms
REGULATORY_AND_TIMELINE_STOPWORDS: Set[str] = {
    # Administrative & regulatory carrier words
    "regulation", "regulations", "rule", "rules", "amendment", "amendments",
    "requirement", "requirements", "standard", "standards", "compliance",
    "mandate", "mandates", "code", "convention", "circular", "circulars",
    "resolution", "resolutions", "guideline", "guidelines", "statutory",
    "legislation", "legislations", "act", "acts", "provision", "provisions",
    "annex", "annexes", "chapter", "chapters", "matrix", "policy", "policies",
    # Timeline, effective dates & calendar words
    "effective", "force", "entry", "coming", "comes", "enter", "enters",
    "enforcement", "implementation", "deadline", "deadlines", "timeline",
    "timelines", "schedule", "schedules", "date", "dates", "year", "years",
    "month", "months", "period", "periods", "jan", "january", "feb", "february",
    "mar", "march", "apr", "april", "may", "jun", "june", "jul", "july",
    "aug", "august", "sep", "september", "oct", "october", "nov", "november",
    "dec", "december"
}


def classify_question_scope(
    query: str,
    standalone_query: Optional[str] = None,
) -> str:
    """
    Classify a question as GENERAL or SPECIFIC.
    When ENABLE_QUESTION_SCOPE is False, question scope functionality is disabled
    and all queries default to SCOPE_GENERAL without filtering media or restricting sibling search.
    """
    if not ENABLE_QUESTION_SCOPE:
        return SCOPE_GENERAL

    text_to_eval = (standalone_query or query or "").strip()
    if not text_to_eval:
        return SCOPE_GENERAL

    raw_query = (query or "").strip()

    # 1. Check if the query is an explicit abbreviation / full-form request
    # (e.g. "What does EGCS stand for?", "What is the full form of ECDIS?")
    for pat in ABBREVIATION_PATTERNS:
        if pat.search(text_to_eval) or pat.search(raw_query):
            return SCOPE_GENERAL

    # 2. Check for strong SPECIFIC indicators (narrow details, faults, operations, procedures, components, instruments, limits, timelines)
    # Check both resolved standalone_query and raw_query
    has_specific_signals = bool(
        SPECIFIC_KEYWORDS_PATTERN.search(text_to_eval)
        or (raw_query and SPECIFIC_KEYWORDS_PATTERN.search(raw_query))
    )

    if has_specific_signals:
        return SCOPE_SPECIFIC

    # 3. Check for targeted regulatory queries on a specific technical subject
    reg_match = TARGETED_REGULATION_PATTERN.search(text_to_eval) or (raw_query and TARGETED_REGULATION_PATTERN.search(raw_query))
    if reg_match:
        subject_candidate = reg_match.group(1).strip()
        subject_candidate = re.sub(r'[\?\.!,;]+$', '', subject_candidate).strip()
        sub_tokens = [w.lower() for w in re.findall(r'\b[a-zA-Z0-9]+\b', subject_candidate)]
        meaningful_tokens = [
            w for w in sub_tokens
            if w not in COMMON_ENGLISH_STOPWORDS
            and w not in GENERIC_MARITIME_WORDS
            and w not in REGULATORY_AND_TIMELINE_STOPWORDS
            and w.upper() not in GLOBAL_MARITIME_FRAMEWORKS
        ]
        if meaningful_tokens:
            return SCOPE_SPECIFIC

    # 4. Check for broad overview or definition patterns
    # (e.g. "What is EGCS?", "Explain EGCS", "Overview of ECDIS", "What is an oily water separator?")
    for pat in BROAD_OVERVIEW_PATTERNS:
        if pat.match(text_to_eval) or (raw_query and pat.match(raw_query)):
            return SCOPE_GENERAL

    # 5. Check if the query is a single-term or standalone acronym / concept
    # (e.g. "EGCS", "ECDIS", "SOLAS", "scrubber", "auxiliary boiler")
    words = re.findall(r'\b[a-zA-Z0-9\-_]+\b', text_to_eval)
    if len(words) <= 3:
        # If no specific procedural/fault keywords, short queries default to GENERAL
        return SCOPE_GENERAL

    # 6. Default heuristic: questions asking "how", "why", "what causes", "when should",
    # or containing specific operational words are SPECIFIC.
    q_lower = text_to_eval.lower()
    if any(q_lower.startswith(w) for w in ["how ", "why ", "what causes ", "when should ", "where is the "]):
        return SCOPE_SPECIFIC

    # Broad questions like "tell me about ...", "give details on ..." default to GENERAL
    if any(q_lower.startswith(w) for w in ["tell me", "explain", "overview", "what is", "what are", "describe"]):
        return SCOPE_GENERAL

    # If length is moderate and no specific component/fault signals were found, default to GENERAL
    return SCOPE_GENERAL


def extract_specific_subject_terms(query: str) -> Set[str]:
    """
    Extract distinctive specific subject terms from a query.
    When ENABLE_QUESTION_SCOPE is False, returns an empty set so no media items are restricted.
    """
    if not ENABLE_QUESTION_SCOPE or not query:
        return set()

    detected_acrs = {a.lower() for a in find_acronyms_in_query(query)}
    raw_tokens = re.findall(r'\b[a-zA-Z]{3,}\b', query.lower())

    # Include special 2-letter domain terms like 'ph' or 'dp'
    two_letter_terms = set(re.findall(r'\b(ph|dp)\b', query.lower()))

    structural_words = {
        "what", "does", "stand", "mean", "meaning", "explain", "overview",
        "describe", "about", "tell", "show", "give", "please", "would",
        "could", "should", "with", "from", "that", "this", "they", "them",
        "some", "many", "much", "more", "most", "also", "into", "onto"
    }

    framework_words = {f.lower() for f in GLOBAL_MARITIME_FRAMEWORKS}

    stop_words = (
        COMMON_ENGLISH_STOPWORDS
        | GENERIC_MARITIME_WORDS
        | structural_words
        | REGULATORY_AND_TIMELINE_STOPWORDS
        | framework_words
        | detected_acrs
    )

    filtered_terms = {t for t in raw_tokens if t not in stop_words} | two_letter_terms

    # Fallback: if all tokens were stripped by regulatory/timeline/generic words, keep non-structural tokens
    if not filtered_terms:
        fallback_stop = COMMON_ENGLISH_STOPWORDS | structural_words | detected_acrs
        filtered_terms = {t for t in raw_tokens if t not in fallback_stop} | two_letter_terms

    # Broad machinery and parent carrier words that should not act as specific filters
    # when more distinctive sub-type, fault, or component qualifiers exist
    parent_machinery_carrier_words = {
        "engine", "engines", "machinery", "motor", "motors", "main", "auxiliary"
    }
    distinctive_terms = {t for t in filtered_terms if t not in parent_machinery_carrier_words and t != "less"}
    if distinctive_terms:
        filtered_terms = distinctive_terms

    # Special normalization for compound sub-types like camshaft-less / camshaftless
    q_lower = query.lower()
    if re.search(r'\bcamshaft[\s\-]*less\b|\bcamless\b', q_lower):
        filtered_terms.add("camshaft")
        filtered_terms.add("camshaftless")

    # Add stemmed variations for matching
    expanded_terms = set(filtered_terms)
    for term in filtered_terms:
        # Add basic stemmed forms (e.g., 'causes' -> 'cause', 'scrubbers' -> 'scrubber', 'leaking' -> 'leak', 'meters' -> 'meter')
        stem = re.sub(r'(ing|tion|tions|ed|es|s)$', '', term)
        if len(stem) >= 3:
            expanded_terms.add(stem)

    return expanded_terms
