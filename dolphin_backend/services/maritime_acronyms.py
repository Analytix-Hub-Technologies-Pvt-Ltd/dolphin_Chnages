"""
services/maritime_acronyms.py

Centralized maritime acronym mapping and domain term resolution.
Ensures short-form maritime queries (e.g., EGCS, SCR, BWMS, VLSFO, ECDIS)
are recognized by query analyzers, retrieval nodes, and media relevance filters.
"""

from typing import Dict, List, Set
import re

# Comprehensive dictionary of maritime abbreviations and acronyms
# mapped to their full descriptive terms and domain keywords
MARITIME_ACRONYMS_MAP: Dict[str, List[str]] = {
    # Environmental & Emission Regulations (MARPOL Annex VI / BWM)
    "EGCS": ["exhaust gas cleaning system", "scrubber", "scrubbers", "sox scrubber", "wash water"],
    "SCR": ["selective catalytic reduction", "nox", "catalytic reduction", "urea"],
    "BWMS": ["ballast water management system", "ballast water", "bwm", "treatment"],
    "VLSFO": ["very low sulphur fuel oil", "fuel oil", "sulphur cap", "bunker"],
    "ULSFO": ["ultra low sulphur fuel oil", "fuel oil", "bunker"],
    "HFO": ["heavy fuel oil", "residual fuel", "bunker"],
    "MGO": ["marine gas oil", "distillate fuel"],
    "MDO": ["marine diesel oil", "diesel"],
    "EEDI": ["energy efficiency design index", "efficiency"],
    "SEEMP": ["ship energy efficiency management plan", "carbon"],
    "CII": ["carbon intensity indicator", "emissions"],
    "EEXI": ["energy efficiency existing ship index"],
    "MEPC": ["marine environment protection committee", "imo", "pollution"],
    "SOPEP": ["shipboard oil pollution emergency plan", "oil spill"],
    "SMPEP": ["shipboard marine pollution emergency plan"],
    "IOPP": ["international oil pollution prevention", "certificate"],
    "ODME": ["oil discharge monitoring equipment", "oil discharge", "tanker"],
    "ODMCS": ["oil discharge monitoring and control system"],
    "OWS": ["oily water separator", "15 ppm", "bilge", "separator"],

    # Navigation & Bridge Systems
    "ECDIS": ["electronic chart display and information system", "electronic chart", "enc"],
    "ARPA": ["automatic radar plotting aid", "radar", "target tracking"],
    "AIS": ["automatic identification system", "transponder"],
    "BNWAS": ["bridge navigational watch alarm system", "bridge watch"],
    "VDR": ["voyage data recorder", "black box"],
    "SVDR": ["simplified voyage data recorder"],
    "GPS": ["global positioning system", "navigation"],
    "DGPS": ["differential global positioning system"],
    "LRIT": ["long range identification and tracking"],
    "SSAS": ["ship security alert system"],
    "OOW": ["officer of the watch", "bridge watchkeeping"],
    "COLREG": ["convention on international regulations for preventing collisions at sea", "rules of the road"],
    "COLREGS": ["collision regulations", "rules of the road"],
    "TSS": ["traffic separation scheme"],
    "UKC": ["under keel clearance"],

    # Radio & Emergency Communications (GMDSS)
    "GMDSS": ["global maritime distress and safety system", "distress", "vhf", "mf/hf"],
    "EPIRB": ["emergency position indicating radio beacon", "beacon", "satellite"],
    "SART": ["search and rescue transponder", "radar transponder"],
    "NAVTEX": ["navigational telex", "maritime safety information"],
    "DSC": ["digital selective calling"],
    "VHF": ["very high frequency", "radio"],
    "HF": ["high frequency radio"],
    "MF": ["medium frequency radio"],
    "MSI": ["maritime safety information"],

    # Life Saving & Fire Fighting Appliances (LSA/FFA)
    "EEBD": ["emergency escape breathing device", "breathing apparatus", "escape"],
    "SCBA": ["self contained breathing apparatus", "firefighting", "breathing"],
    "BA": ["breathing apparatus"],
    "LSA": ["life saving appliances", "lifeboat", "liferaft", "lifebuoy"],
    "FFA": ["fire fighting appliances", "firefighting", "fire extinguisher"],
    "HRU": ["hydrostatic release unit", "liferaft"],
    "MOB": ["man overboard", "rescue"],
    "MES": ["marine evacuation system"],

    # Tanker, Cargo & Machinery Operations
    "IGG": ["inert gas generator", "inert gas", "flue gas"],
    "IGS": ["inert gas system", "inert gas"],
    "COW": ["crude oil washing", "tank cleaning"],
    "PV": ["pressure vacuum", "pv valve", "pv breaker"],
    "CPP": ["controllable pitch propeller", "propeller"],
    "FPP": ["fixed pitch propeller", "propeller"],
    "PTW": ["permit to work", "hot work", "enclosed space"],
    "RA": ["risk assessment", "hazard identification"],
    "JSA": ["job safety analysis"],
    "TBT": ["toolbox talk"],
    "CSE": ["confined space entry", "enclosed space"],
    "UMS": ["unattended machinery space"],
    "ME": ["main engine"],
    "AE": ["auxiliary engine"],
    "FWG": ["fresh water generator"],
    "EGB": ["exhaust gas boiler"],
    "BBS": ["behavior based safety", "behaviour based safety", "safety observation", "safety"],
    "BOG": ["boil off gas", "boil-off gas", "cargo boil off", "cargo handling"],
    "BOB": ["bunker on board", "bunkering", "fuel oil remaining"],
    "CPD": ["continuous professional development", "seafarer training", "stcw", "competence"],

    # Conventions, Codes & Organizations
    "SOLAS": ["safety of life at sea", "convention"],
    "MARPOL": ["marine pollution", "annex"],
    "STCW": ["standards of training certification and watchkeeping", "seafarer"],
    "ISM": ["international safety management", "safety management", "sms"],
    "ISPS": ["international ship and port facility security"],
    "MLC": ["maritime labour convention", "seafarer rights"],
    "IMDG": ["international maritime dangerous goods", "dangerous cargo"],
    "IGC": ["international gas carrier", "gas code"],
    "IBC": ["international bulk chemical", "chemical code"],
    "IMSBC": ["international maritime solid bulk cargoes"],
    "PSC": ["port state control", "inspection", "deficiency"],
    "FSI": ["flag state inspection"],
    "IMO": ["international maritime organization"],
    "ILO": ["international labour organization"],
    "IACS": ["international association of classification societies"],
}

# Pre-computed uppercase set for fast O(1) membership test
KNOWN_ACRONYMS_SET: Set[str] = set(MARITIME_ACRONYMS_MAP.keys())


# Ambiguous short words that are common English words; only count as acronyms if written in ALL CAPS
AMBIGUOUS_SHORT_WORDS: Set[str] = {
    "ME", "TO", "IN", "ON", "SO", "NO", "DO", "AT", "BY", "IS", "IT", "AN", "AS", "AM", "HE", "WE", "OR", "IF"
}

# Generic maritime terms that must NOT be used alone to qualify an image/video as relevant
GENERIC_MARITIME_WORDS: Set[str] = {
    "system", "systems", "onboard", "board", "ship", "ships", "vessel", "vessels",
    "operation", "operations", "procedure", "procedures", "marine", "maritime",
    "component", "components", "unit", "units", "equipment", "overview", "introduction",
    "basics", "basic", "general", "feature", "features", "training", "course", "guideline", "guidelines"
}


def get_acronym_expansion(acronym: str) -> List[str]:
    """Get expansion keywords for a given acronym (case-insensitive)."""
    if not acronym:
        return []
    acr = acronym.strip().upper()
    if acr in MARITIME_ACRONYMS_MAP:
        return MARITIME_ACRONYMS_MAP[acr]
    try:
        from services.dynamic_acronym_service import dynamic_acronym_service
        return dynamic_acronym_service.get_expansion_sync(acr)
    except Exception:
        return []


def is_known_maritime_acronym(token: str) -> bool:
    """Check if token is recognized as a maritime acronym in static or dynamic registry."""
    if not token:
        return False
    t_clean = token.strip().upper()
    if t_clean in KNOWN_ACRONYMS_SET:
        return True
    try:
        from services.dynamic_acronym_service import dynamic_acronym_service
        return dynamic_acronym_service.is_known_acronym(t_clean)
    except Exception:
        return False


def find_acronyms_in_query(query: str) -> List[str]:
    """Find all maritime acronyms present in a user query or text."""
    if not query:
        return []
    # Extract candidate words/tokens (2 to 8 characters)
    words = re.findall(r'\b[a-zA-Z0-9_\-\/]{2,8}\b', query)
    found = []
    for w in words:
        w_clean = re.sub(r'[^a-zA-Z0-9]', '', w).upper()
        if is_known_maritime_acronym(w_clean):
            # If it's a common English word like "me", require it to be uppercase in the input
            if w_clean in AMBIGUOUS_SHORT_WORDS and not w.isupper():
                continue
            found.append(w_clean)
        elif len(w_clean) >= 3 and w_clean.endswith('S') and is_known_maritime_acronym(w_clean[:-1]):
            # Support plural acronyms (e.g. EEBDs -> EEBD, SCBAs -> SCBA, BOGs -> BOG, PLCs -> PLC)
            sing_acr = w_clean[:-1]
            if sing_acr in AMBIGUOUS_SHORT_WORDS and not w[:-1].isupper():
                continue
            found.append(sing_acr)
    return found


GLOBAL_MARITIME_FRAMEWORKS: Set[str] = {
    "IMO", "ILO", "MARPOL", "SOLAS", "STCW", "ISM", "ISPS", "MLC", "MEPC", "PSC", "FSI", "IACS", "USCG"
}


def has_conflicting_acronym(query_text: str, candidate_text: str) -> bool:
    """
    Check if candidate_text contains a distinct maritime acronym that conflicts with
    the acronyms in the user's query.
    Example:
      query: 'explain me EGCS onboard ?' (acronym: EGCS)
      candidate: 'Components of ECDIS' (acronym: ECDIS)
      -> Returns True because ECDIS != EGCS!
    """
    query_acronyms = set(find_acronyms_in_query(query_text))
    if not query_acronyms:
        return False

    candidate_lower = (candidate_text or "").lower()

    # If the candidate explicitly mentions any of the queried acronyms or their expansions,
    # it is directly relevant and not conflicting
    for q_acr in query_acronyms:
        if q_acr.lower() in candidate_lower:
            return False
        for exp in get_acronym_expansion(q_acr):
            if len(exp) >= 4 and exp.lower() in candidate_lower:
                return False

    candidate_acronyms = set(find_acronyms_in_query(candidate_text))
    if not candidate_acronyms:
        return False

    # Check if candidate mentions a conflicting specific equipment/domain acronym
    for c_acr in candidate_acronyms:
        if c_acr in query_acronyms:
            continue
        if c_acr in GLOBAL_MARITIME_FRAMEWORKS:
            continue
        # Check if this acronym is an expansion synonym of the queried acronym
        is_synonym = False
        for q_acr in query_acronyms:
            expansions = [exp.upper() for exp in get_acronym_expansion(q_acr)]
            if c_acr in expansions or any(c_acr in exp for exp in expansions):
                is_synonym = True
                break
        if not is_synonym:
            return True

    return False


# Generic English words, pronouns, auxiliary verbs, and structural question words
# that should never qualify an image or video as relevant
COMMON_ENGLISH_STOPWORDS: Set[str] = {
    "the", "and", "for", "are", "was", "were", "been", "has", "had", "have",
    "can", "could", "would", "should", "will", "shall", "all", "any", "both",
    "each", "few", "more", "most", "other", "some", "such", "than", "too",
    "very", "not", "only", "own", "same", "so", "our", "its", "their", "his",
    "her", "them", "these", "those", "this", "that", "there", "here", "just",
    "into", "through", "during", "before", "after", "above", "below", "to",
    "from", "up", "down", "in", "out", "on", "off", "over", "under", "again",
    "further", "then", "once", "why", "how", "what", "which", "who", "whom",
    "when", "where", "different", "difference", "differences", "various",
    "type", "types", "kind", "kinds", "category", "categories", "classification",
    "classifications", "purpose", "purposes", "name", "names", "common", "list",
    "between", "among", "example", "examples", "please", "explain", "explanation",
    "describe", "description", "detail", "details", "brief", "tell", "show",
    "many", "much", "want", "need", "know", "provide", "discuss", "image",
    "images", "video", "videos", "photo", "photos", "picture", "pictures",
    "watch", "clip", "lesson", "module", "with", "does", "your", "give", "like"
}


def expand_query_terms_for_media(query: str, chunks: List[dict] = None) -> Set[str]:
    """
    Given a query, extract effective query words plus domain synonyms from any detected acronyms,
    ensuring strict relevance for images and videos without dropping valid media or matching on generic words.
    """
    query_clean = (query or "").lower().strip()
    query_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', query_clean))

    stop_words = COMMON_ENGLISH_STOPWORDS | GENERIC_MARITIME_WORDS

    effective_words = query_words - stop_words

    # If all terms in query were filtered because of GENERIC_MARITIME_WORDS (e.g. 'tell me about ships'),
    # keep the generic maritime terms so the query term set is not empty
    if not effective_words:
        effective_words = query_words - COMMON_ENGLISH_STOPWORDS

    # Expand any detected acronyms into their distinctive domain keywords
    detected_acronyms = find_acronyms_in_query(query)
    for acr in detected_acronyms:
        effective_words.add(acr.lower())
        expansions = get_acronym_expansion(acr)
        for exp in expansions:
            for w in re.findall(r'\b[a-zA-Z]{3,}\b', exp.lower()):
                if w not in COMMON_ENGLISH_STOPWORDS and w not in GENERIC_MARITIME_WORDS:
                    effective_words.add(w)

    # For queries specifically asking about ship types, classifications, or merchant vessels,
    # preserve ship-type terminology and primary merchant vessel categories
    is_ship_type_query = any(phrase in query_clean for phrase in [
        "types of ship", "types of merchant ship", "ship type", "types of vessel",
        "kind of ship", "classification of ship", "different types of"
    ]) or ("merchant" in query_clean and any(w in query_clean for w in ["ship", "ships", "vessel", "vessels"]))
    if not is_ship_type_query and chunks:
        for chk in (chunks or [])[:3]:
            c_topic = str(chk.get("topic_name") or chk.get("title") or "").lower()
            if "ship type" in c_topic or "types of ship" in c_topic or "merchant ship" in c_topic:
                is_ship_type_query = True
                break

    if is_ship_type_query:
        effective_words.update({
            "merchant", "ship", "ships", "vessel", "vessels",
            "cargo", "tanker", "tankers", "container", "carrier", "carriers"
        })

    return effective_words
