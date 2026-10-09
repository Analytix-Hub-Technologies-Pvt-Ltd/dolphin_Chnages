"""
services/off_topic_detector.py

Comprehensive domain classification and out-of-scope detection for Dolphin AI.
Ensures zero-hallucination by strictly identifying non-marine queries and verifying
maritime relevance before retrieval or response generation.
"""

import re
from typing import List

# -------------------------------------------------------------
# 1. OUT-OF-SCOPE / OFF-TOPIC PATTERNS (HIGH PRECISION REGEX)
# -------------------------------------------------------------
OFF_TOPIC_REGEX_PATTERNS = [
    # Mobile devices, Consumer Tech, Gadgets
    r"\b(iphones?|ipads?|ipods?|apple\s*watch|airpods?|macbooks?)\b",
    r"\b(smartphones?|smart\s*phones?|smartwatches?|smart\s*watches?)\b",
    r"\b(android\s*phones?|android\s*devices?|android\s*os|ios\s*app|ios\s*version)\b",
    r"\b(playstations?|ps[345]|xboxes?|xbox|nintendo|nintendo\s*switch)\b",
    r"\b(video\s*games?|gaming\s*consoles?|pc\s*gaming|gamers?|gameplay)\b",
    r"\b(fortnite|minecraft|roblox|gta|call\s*of\s*duty|pubg|valorant|fifa\s*game)\b",
    r"\b(samsung\s*galaxy|redmi|oneplus|huawei|pixel\s*phones?|google\s*pixel)\b",
    r"\b(chromebooks?|laptops?|tablets?|bluetooth\s*speakers?|earbuds?|headphones?)\b",
    r"\b(smart\s*tvs?|smart\s*television|app\s*store|play\s*store)\b",
    r"\b(tiktok|instagram|snapchat|facebook|twitter|x\.com|whatsapp|telegram\s*app)\b",

    # Non-marine Computer Science / Software / Programming
    r"\b(python\s*programming|python\s*code|python\s*script|python\s*language|learn\s*python)\b",
    r"\b(javascript|typescript|c\+\+|c#|html\s*css|reactjs|react\s*js|angular|vuejs|nodejs)\b",
    r"\b(machine\s*learning|deep\s*learning|coding\s*interview|software\s*engineering)\b",
    r"\b(programming\s*languages?|golang|rust\s*programming|php\s*code|sql\s*queries?)\b",
    r"\b(git\s*commits?|github|gitlab|chatgpt|openai|llm\s*models?|neural\s*networks?)\b",
    r"\b(write\s+(?:a\s+)?code|write\s+(?:a\s+)?script|debug\s+(?:this\s+)?code|fix\s+(?:this\s+)?bug)\b",

    # Pop Culture, Entertainment, Cinema, Celebrities
    r"\b(movies?|films?|cinema|hollywood|bollywood|kollywood|tollywood)\b",
    r"\b(actors?|actress(?:es)?|oscar\s*awards?|celebrity|celebrities)\b",
    r"\b(netflix|tv\s*shows?|web\s*series|grammy|billboard|pop\s*music|hip\s*hop)\b",
    r"\b(singers?|songs?|album|disney|marvel|dc\s*comics|superhero(?:es)?)\b",
    r"\b(batman|superman|spiderman|avengers|iron\s*man|taylor\s*swift)\b",

    # Sports
    r"\b(cricket|ipl|fifa|world\s*cup|tennis\s*match|nba|olympics|badminton|golf)\b",
    r"\b(soccer|football\s*match|football\s*club|premier\s*league|champions\s*league)\b",
    r"\b(messi|ronaldo|virat\s*kohli|sachin\s*tendulkar|lebron\s*james|formula\s*1|f1\s*race)\b",

    # Politics & Non-marine Governance
    r"\b(presidential\s*elections?|prime\s*minister|parliamentary\s*election)\b",
    r"\b(democrats?|republicans?|political\s*part(?:y|ies)|white\s*house|senate\s*vote)\b",

    # Cooking & Food Recipes
    r"\b(recipes?|how\s+to\s+bake|how\s+to\s+cook|cake\s*recipe|cooking\s*recipe)\b",
    r"\b(pasta\s*recipe|pizza\s*recipe|cocktail\s*recipe|biryani\s*recipe|baking\s*bread)\b",

    # Finance, Stock Market, Crypto
    r"\b(cryptocurrency|cryptos?|bitcoins?|ethereum|dogecoin|binance)\b",
    r"\b(stock\s*market|forex\s*trading|mutual\s*funds?|wall\s*street)\b",

    # Non-marine General Trivia & Everyday Inquiries
    r"\bwho\s+is\s+(?:elon\s+musk|bill\s+gates|jeff\s+bezos|mark\s+zuckerberg|messi|ronaldo|donald\s+trump|joe\s+biden)\b",
    r"\bwhat\s+is\s+the\s+capital\s+of\b",
    r"\bwhat\s+is\s+the\s+population\s+of\b",
    r"\b(tell\s+me\s+a\s+joke|jokes?|dating\s+advice|relationship\s+advice)\b",
    r"\b(eiffel\s*tower|statue\s*of\s*liberty|taj\s*mahal|pyramids?\s*of\s*giza)\b",
    r"\b(dinosaurs?|photosynthesis|human\s*anatomy|dna\s*replication|black\s*holes?|solar\s*system)\b",
]

COMPILED_OFF_TOPIC = [
    re.compile(p, re.IGNORECASE) for p in OFF_TOPIC_REGEX_PATTERNS
]


# -------------------------------------------------------------
# 2. DEFINITE OFF-TOPIC KEYWORDS
# -------------------------------------------------------------
OFF_TOPIC_KEYWORDS = [
    # Consumer electronics / phones / gadgets
    "iphone", "iphones", "ipad", "ipads", "ipod", "apple watch", "airpods", "macbook",
    "android phone", "smartphone", "smartphones", "smart watch", "smartwatch",
    "playstation", "ps5", "ps4", "xbox", "nintendo", "video game", "video games",
    "gaming console", "samsung galaxy", "redmi", "oneplus", "google pixel",
    # Programming & Tech
    "python", "javascript", "java programming", "c++", "c#", "html css", "reactjs",
    "angular", "machine learning", "deep learning", "coding", "software engineering",
    "programming language", "typescript", "golang", "rust programming", "php", "sql query",
    # Pop culture & Media
    "movie", "movies", "film", "films", "actor", "actress", "oscar", "cinema",
    "hollywood", "bollywood", "celebrity", "netflix", "series", "tv show", "tv shows",
    "kollywood", "tollywood", "song", "singer", "pop music",
    # Sports
    "cricket", "football", "ipl", "fifa", "world cup", "tennis", "nba", "olympics",
    "baseball", "badminton",
    # Politics & News
    "politics", "election", "president", "prime minister", "parliament", "congress",
    # Cooking / Lifestyle
    "recipe", "how to bake", "how to cook", "cake recipe", "cooking recipe",
    # Finance / Crypto
    "crypto", "bitcoin", "ethereum", "stock market", "cryptocurrency",
]


# -------------------------------------------------------------
# 3. MARITIME DOMAIN INDICATORS
# -------------------------------------------------------------
MARINE_INDICATORS = [
    # Regulations, Conventions & Codes
    "colreg", "colregs", "solas", "marpol", "stcw", "ism", "isps", "mlc", "imdg",
    "igc code", "ibc code", "imo", "psc", "port state control", "flag state",
    "class survey", "drydock", "load line", "musters", "maritime", "nautical",
    "eedi", "seemp", "cii", "eexi", "sopep", "smpep", "iopp", "bwm", "mepc",

    # Environmental Regulations, Emissions & Exhaust Cleaning (EGCS / Scrubbers)
    "egcs", "scrubber", "scrubbers", "wet scrubber", "dry scrubber", "sox scrubber",
    "exhaust gas cleaning", "wash water criteria", "washwater", "scr", "selective catalytic reduction",
    "bwms", "ballast water management", "bwm convention", "vlsfo", "ulsfo", "hfo", "mgo", "mdo",
    "sulphur cap", "sulfur cap", "marpol annex vi",

    # Vessel Types & Shipboard Terms
    "vessel", "vessels", "ship", "ships", "tanker", "tankers", "chemical carrier",
    "bulk carrier", "container ship", "lng carrier", "lpg carrier", "tug", "barge",
    "offshore", "chemical tanker", "oil tanker", "sbox", "shipboard",

    # Ranks & Shipboard Roles
    "master", "captain", "chief officer", "chief mate", "second officer", "third officer",
    "2/o", "3/o", "oow", "officer of the watch", "chief engineer", "second engineer",
    "third engineer", "fourth engineer", "motorman", "fitter", "bosun", "able seaman",
    "ordinary seaman", "deck cadet", "engine cadet", "seafarer", "seafarers",
    "seaman", "seamanship", "helmsman", "lookout",

    # Bridge, Navigation & Deck Equipment
    "navigation", "bridge", "anchor watch", "bridge watch", "passage plan",
    "ecdis", "radar", "arpa", "ais", "gyro", "magnetic compass", "autopilot",
    "rudder", "helm", "crossing situation", "head-on", "head on", "overtaking",
    "restricted visibility", "fog signal", "sound signal", "navigation light",
    "day shape", "pilot", "pilotage", "pilot ladder", "draft", "draught",
    "under keel clearance", "ukc", "tide", "squat", "bank effect", "interaction",

    # Engine Room & Machinery
    "engine room", "marine engine", "diesel engine", "main engine", "auxiliary engine",
    "two stroke", "four stroke", "boiler", "auxiliary boiler", "exhaust gas boiler",
    "economizer", "turbocharger", "scavenge fire", "crankcase", "purifier",
    "separator", "oily water separator", "ows", "15 ppm", "bilge", "ballast water",
    "steering gear", "propeller", "stern tube", "generator", "switchboard",
    "air compressor", "fresh water generator", "incinerator", "bunker", "bunkering",
    "pump", "pumps", "centrifugal pump", "reciprocating pump", "gear pump", "screw pump", "eductor", "ejector",
    "valve", "valves", "relief valve", "safety valve", "quick closing valve", "non return valve", "storm valve",
    "hazard", "hazards", "alarm", "alarms", "extinguisher", "extinguishers", "tank", "tanks",
    "bbs", "bog", "bob", "boil off gas", "boil-off gas", "bunker on board", "behavior based safety",

    # Safety, Emergency & Life Saving Appliances (LSA/FFA)
    "firefighting", "fire extinguisher", "fire hose", "fire damper", "co2 system",
    "foam system", "scba", "eebd", "lifeboat", "liferaft", "lifebuoy", "lifejacket",
    "immersion suit", "pyrotechnics", "rocket parachute", "hand flare", "epirb",
    "sart", "gmdss", "vhf", "navtex", "hru", "hydrostatic release", "muster",
    "fire drill", "abandon ship", "man overboard", "mob", "damage control",
    "watertight door", "ppe", "safety harness",

    # Cargo & Tanker Operations
    "cargo", "cargo tank", "cargo hold", "cargo sampling", "ullage", "sounding",
    "tank cleaning", "crude oil washing", "cow", "inert gas", "igg",
    "nitrogen generator", "pressure vacuum", "pv valve", "enclosed space",
    "confined space", "hot work", "cold work", "permit to work", "ptw",
    "risk assessment", "toolbox talk", "atmospheric testing", "gas detector",
    "oxygen analyzer", "explosimeter", "toxic gas",

    # Shipboard Communication Systems (Marine-specific)
    "sound powered phone", "sound-powered phone", "internal phone system",
    "public address", "pa system", "intercom", "inmarsat", "vsat",
    "satellite communication",

    # Mooring & Deck Operations
    "mooring", "anchor", "anchoring", "windlass", "capstan", "heaving line",
    "hawser", "gangway", "safety net", "chain locker",

    # Crew Safety, Conduct & Wellbeing
    "harassment", "bullying", "intoxication", "intoxicated", "drug test",
    "alcohol test", "workplace safety", "near miss", "incident investigation",
    "crew safety", "crew member",
]

COMPILED_MARINE = [
    re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE) for term in MARINE_INDICATORS
]


# -------------------------------------------------------------
# 4. CORE FUNCTIONS
# -------------------------------------------------------------
def is_off_topic_query(query: str) -> bool:
    """
    Check if a query is definitely non-marine / off-topic.
    Returns True if query matches any known off-topic keywords or patterns.
    """
    if not query or not isinstance(query, str):
        return False

    q_lower = query.lower().strip()
    if not q_lower:
        return False

    # Check regex patterns
    for pattern in COMPILED_OFF_TOPIC:
        if pattern.search(q_lower):
            return True

    # Check keyword list
    for kw in OFF_TOPIC_KEYWORDS:
        if re.search(r"\b" + re.escape(kw) + r"\b", q_lower):
            return True

    return False


def is_marine_domain_query(query: str) -> bool:
    """
    Check if a query contains explicit maritime domain terminology.
    """
    if not query or not isinstance(query, str):
        return False

    q_lower = query.lower().strip()
    if not q_lower:
        return False

    for pattern in COMPILED_MARINE:
        if pattern.search(q_lower):
            return True

    # Check against known maritime acronyms (e.g., EGCS, SCR, BWMS, VLSFO)
    try:
        from services.maritime_acronyms import find_acronyms_in_query
        if find_acronyms_in_query(query):
            return True
    except Exception:
        pass

    return False


def is_obvious_marine_query(query: str) -> bool:
    """
    Check if query is clearly a maritime question or operational inquiry.
    Only fast-paths queries that BOTH look like questions/inquiries AND contain
    explicit maritime domain keywords.
    """
    if not query or not isinstance(query, str):
        return False

    # Never fast-path off-topic queries
    if is_off_topic_query(query):
        return False

    # Must contain maritime domain indicators
    if not is_marine_domain_query(query):
        return False

    q = query.lower().strip()

    # Question structure check
    if q.endswith("?") and len(q.split()) >= 2:
        return True

    question_starters = (
        "what", "how", "why", "where", "when", "which", "who",
        "explain", "describe", "tell", "define", "list", "give", "show", "check",
        "procedure", "procedures", "precaution", "precautions", "requirement", "requirements",
        "guidance", "rules", "regulations", "checklist", "difference", "compare",
        "is ", "are ", "do ", "does ", "did ", "can ", "could ", "should ", "would ", "will ",
    )
    if any(q.startswith(starter) for starter in question_starters):
        return True

    # Phrase containing marine indicators with 2+ words
    return len(q.split()) >= 2
