"""
services/off_topic_detector.py

Comprehensive domain classification and out-of-scope detection for Dolphin AI.
Ensures zero-hallucination by strictly identifying non-marine queries and verifying
maritime relevance before retrieval or response generation.
"""

import re
import random
import asyncio
from typing import List, Tuple, Optional, Dict, Any

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

    # Non-marine General Trivia, Science & Everyday Inquiries
    r"\bwho\s+is\s+(?:elon\s+musk|bill\s+gates|jeff\s+bezos|mark\s+zuckerberg|messi|ronaldo|donald\s+trump|joe\s+biden)\b",
    r"\bwho\s+was\s+(?:albert\s+einstein|isaac\s+newton|julius\s+caesar|napoleon|alexander\s+the\s+great|william\s+shakespeare|abraham\s+lincoln|george\s+washington|cleopatra|aristotle|plato|socrates)\b",
    r"\bwhat\s+is\s+the\s+capital\s+of\b",
    r"\bwhat\s+is\s+the\s+population\s+of\b",
    r"\b(tell\s+me\s+a\s+joke|jokes?|dating\s+advice|relationship\s+advice)\b",
    r"\b(eiffel\s*tower|statue\s*of\s*liberty|taj\s*mahal|pyramids?\s*of\s*giza)\b",
    r"\b(dinosaurs?|photosynthesis|human\s*anatomy|dna\s*replication|black\s*holes?|solar\s*system)\b",
    r"\b(airplanes?|aeroplanes?|aircrafts?|helicopters?|boeing\s*\d+|airbus\s*\d+|commercial\s*flight|aerodynamics\s*of\s*flight)\b",
    r"\b(space\s*exploration|mars\s*rover|james\s*webb|hubble\s*telescope|astronauts?|milky\s*way|andromeda|quantum\s*mechanics|quantum\s*physics)\b",
    r"\b(lions?|tigers?|elephants?|giraffes?|leopards?|cheetahs?|bears?|wolf|wolves|monkeys?|gorillas?|chimpanzees?|can\s+dogs\s+eat|dog\s*breeds?|cat\s*breeds?)\b",
    r"\b(how\s+to\s+play\s+(?:guitar|piano|violin|flute|drums)|guitar\s*chords?|piano\s*notes?|acoustic\s*guitar|electric\s*guitar)\b",
    r"\b(symptoms?\s*of\s*(?:flu|fever|diabetes|covid|cancer|malaria|dengue|migraine)|how\s+to\s+cure\s+(?:headache|cough|cold|fever)|weight\s*loss\s*tips|workout\s*plan|gym\s*workout|diet\s*plan)\b",
    r"\b(how\s+to\s+drive\s+a\s+car|fix\s+a\s+(?:bicycle|bike|flat\s*tire)|electric\s*cars?|tesla\s*model)\b",
    r"\b(world\s*war\s*[12i]+|french\s*revolution|american\s*civil\s*war|roman\s*empire|ancient\s*egypt|ancient\s*greece)\b",
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
    # Sports & Board Games
    "cricket", "football", "ipl", "fifa", "world cup", "tennis", "nba", "olympics",
    "baseball", "badminton", "chess", "poker",
    # Politics & News
    "politics", "election", "president", "prime minister", "parliament", "congress",
    # Cooking / Lifestyle
    "recipe", "how to bake", "how to cook", "cake recipe", "cooking recipe",
    # Finance / Crypto
    "crypto", "bitcoin", "ethereum", "stock market", "cryptocurrency",
    # Terrestrial Animals, Space, Science & Music
    "photosynthesis", "dinosaur", "dinosaurs", "airplane", "aeroplane", "helicopter",
    "guitar", "piano", "violin", "flute", "drums", "astronomy", "quantum physics",
    "diabetes", "weight loss", "gym workout", "tesla",
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
    "sextant", "anemometer", "clinometer", "pelorus", "echo sounder", "speed log",
    "chart table", "heading repeater", "gyrocompass", "alidade", "chronometer",

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
    "engine", "engines", "compressor", "compressors", "turbine", "turbines", "boiler", "boilers",
    "cooler", "coolers", "condenser", "condensers", "heater", "heaters", "filter", "filters",
    "strainer", "strainers", "gauge", "gauges", "sensor", "sensors", "detector", "detectors",
    "transmitter", "transmitters", "injector", "injectors", "governor", "governors", "cylinder", "cylinders",
    "piston", "pistons", "bearing", "bearings", "blower", "blowers", "burner", "burners",
    "actuator", "actuators", "evaporator", "evaporators", "purifier", "purifiers", "separator", "separators",
    "generator", "generators", "switchboard", "switchboards", "intercooler", "intercoolers",
    "bbs", "bog", "bob", "boil off gas", "boil-off gas", "bunker on board", "behavior based safety",

    # Safety, Emergency & Life Saving Appliances (LSA/FFA)
    "firefighting", "fire extinguisher", "fire hose", "fire damper", "co2 system",
    "foam system", "scba", "eebd", "lifeboat", "liferaft", "lifebuoy", "lifejacket",
    "immersion suit", "pyrotechnics", "rocket parachute", "hand flare", "epirb",
    "sart", "gmdss", "vhf", "navtex", "hru", "hydrostatic release", "muster",
    "fire drill", "abandon ship", "man overboard", "mob", "damage control",
    "watertight door", "ppe", "safety harness", "smoke signal", "davit",
    "foam monitor", "breathing apparatus", "muster station", "fire pump",

    # Cargo & Tanker Operations
    "cargo", "cargo tank", "cargo hold", "cargo sampling", "ullage", "sounding",
    "tank cleaning", "crude oil washing", "cow", "inert gas", "igg",
    "nitrogen generator", "pressure vacuum", "pv valve", "enclosed space",
    "confined space", "hot work", "cold work", "permit to work", "ptw",
    "risk assessment", "toolbox talk", "atmospheric testing", "gas detector",
    "oxygen analyzer", "explosimeter", "toxic gas", "manifold", "heating coil",
    "butterworth", "butterworth machine", "vapor line", "slop tank", "deepwell pump",
    "stripping pump", "cargo pump",
    "gas detection", "fixed gas detection", "sequential measurement", "detection in nitrogen",
    "nitrogen barrier", "cyclic sampling", "infrared detector",

    # Shipboard Communication Systems (Marine-specific)
    "sound powered phone", "sound-powered phone", "internal phone system",
    "public address", "pa system", "intercom", "inmarsat", "vsat",
    "satellite communication",

    # Mooring & Deck Operations
    "mooring", "anchor", "anchoring", "windlass", "capstan", "heaving line",
    "hawser", "gangway", "safety net", "chain locker", "fairlead", "bollard",
    "cleat", "bitt", "fender", "shackle", "bulwark", "scupper", "stanchion",
    "derrick", "mooring line", "hatch coaming",
    "snap back", "snapback", "snap-back", "snap back zone", "snapback zone", "snap-back zone", "snap backzone",

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

    # Exemption: If query contains any recognized maritime acronym or matches a course topic/model, it is NOT off-topic
    try:
        from services.maritime_acronyms import find_acronyms_in_query
        if find_acronyms_in_query(query):
            return False
        from services.dynamic_domain_service import dynamic_domain_service
        if dynamic_domain_service.is_db_domain_match(query):
            return False
    except Exception:
        pass

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

    q_lower = re.sub(r'\s+', ' ', query.lower().strip())
    if not q_lower:
        return False

    # Also normalize common merged variations like 'backzone' -> 'back zone'
    q_norm = re.sub(r'backzone\b', 'back zone', q_lower)

    for pattern in COMPILED_MARINE:
        if pattern.search(q_lower) or pattern.search(q_norm):
            return True

    # Check singular forms of plural words and phrases (e.g. pumps, boilers, valves, fire hoses, watertight doors)
    words = re.findall(r'\b[a-zA-Z]{3,}\b', q_lower)
    for w in words:
        singular_candidates = []
        if w.endswith('ies') and len(w) > 4:
            singular_candidates.append(w[:-3] + 'y')
        elif w.endswith('es') and len(w) > 4:
            singular_candidates.append(w[:-2])
            singular_candidates.append(w[:-1])
        elif w.endswith('s') and len(w) > 3:
            singular_candidates.append(w[:-1])

        for sing in singular_candidates:
            for pattern in COMPILED_MARINE:
                if pattern.search(sing):
                    return True

    # Check multi-word phrases with plural endings singularized
    for cand_str in [
        re.sub(r'(\b[a-zA-Z]{3,})ies\b', r'\1y', q_lower),
        re.sub(r'(\b[a-zA-Z]{3,})es\b', r'\1', q_lower),
        re.sub(r'(\b[a-zA-Z]{3,})s\b', r'\1', q_lower),
    ]:
        if cand_str != q_lower:
            for pattern in COMPILED_MARINE:
                if pattern.search(cand_str):
                    return True

    # Check against known maritime acronyms (e.g., EGCS, SCR, BWMS, VLSFO)
    try:
        from services.maritime_acronyms import find_acronyms_in_query
        if find_acronyms_in_query(query):
            return True
    except Exception:
        pass

    # Check against dynamically harvested database course topics & video titles
    try:
        from services.dynamic_domain_service import dynamic_domain_service
        if dynamic_domain_service.is_db_domain_match(query):
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


# -------------------------------------------------------------
# 5. DYNAMIC & VARIED OFF-TOPIC TONE GENERATOR
# -------------------------------------------------------------
def categorize_off_topic_query(query: str) -> str:
    """Classify the user's off-topic query into a specific domain category."""
    if not query:
        return "general"
    q = query.lower()

    if re.search(r"\b(python|javascript|typescript|c\+\+|c#|html|css|react|angular|vue|node|coding|programming|sql|git|script|debug|bug|function|algorithm)\b", q):
        return "coding"
    if re.search(r"\b(recipe|recipes|bake|cook|cooking|cake|pizza|pasta|biryani|bread|cocktail|food|dish|dessert)\b", q):
        return "cooking"
    if re.search(r"\b(movie|movies|film|films|cinema|hollywood|bollywood|actor|actress|oscar|celebrity|netflix|song|songs|singer|music|marvel|dc|disney)\b", q):
        return "entertainment"
    if re.search(r"\b(cricket|football|soccer|ipl|fifa|tennis|nba|olympics|messi|ronaldo|badminton|golf|f1|formula\s*1|race|champions\s*league)\b", q):
        return "sports"
    if re.search(r"\b(iphone|ipad|apple\s*watch|macbook|android|smartphone|playstation|ps5|ps4|xbox|nintendo|fortnite|minecraft|gaming|pubg)\b", q):
        return "consumer_tech"
    if re.search(r"\b(crypto|cryptocurrency|bitcoin|ethereum|dogecoin|stock\s*market|forex|trading|mutual\s*fund|shares)\b", q):
        return "finance"
    if re.search(r"\b(election|presidential|prime\s*minister|parliament|congress|democrat|republican|senate|politics)\b", q):
        return "politics"

    return "general"


OFF_TOPIC_TONES_MAP: Dict[str, List[Tuple[str, List[str]]]] = {
    "coding": [
        (
            "I don't write computer software or general code! My expertise is strictly focused on "
            "shipboard automation, PLC logic, marine electrical systems, and bridge navigation equipment. "
            "Feel free to ask about any vessel control systems or automation instead.",
            [
                "How do PLCs function in shipboard machinery spaces?",
                "What is the network architecture of an ECDIS system?",
                "How does the Bridge Navigational Watch Alarm System (BNWAS) operate?"
            ]
        ),
        (
            "That's outside my shipping wheelhouse! As a maritime AI, I specialize in marine engineering, "
            "navigation protocols, and shipboard operations rather than general software programming. "
            "Let's steer back on course—what marine machinery or safety topic can I assist you with?",
            [
                "What are the main components of a marine auxiliary boiler?",
                "How does a centrifugal pump work onboard?",
                "What are the operational checks for marine air compressors?"
            ]
        ),
        (
            "General programming languages and web development fall outside our maritime curriculum. "
            "However, I can assist you with shipboard control systems, engine room automation, or alarm monitoring architectures! "
            "What vessel system would you like to explore?",
            [
                "How does electronic fuel injection work on two-stroke marine engines?",
                "What are the fail-safe mechanisms in steering gear systems?",
                "Explain the working principle of a fresh water generator."
            ]
        ),
    ],
    "cooking": [
        (
            "Culinary recipes aren't in my training log, but I know all about galley fire safety protocols and "
            "MARPOL Annex V food waste comminuter regulations! What shipboard procedure can I assist you with?",
            [
                "What are the food waste disposal rules under MARPOL Annex V?",
                "What are galley fire precautions and deep fat fryer fire extinguishing systems?",
                "How does a shipboard provision refrigeration plant operate?"
            ]
        ),
        (
            "That's outside our maritime training curriculum! While I can't provide cooking recipes, "
            "I'm fully equipped to help with catering safety, provision refrigeration plants, or potable water management on board.",
            [
                "How is potable water tested and treated on board?",
                "What are the hygiene and safety standards under MLC 2006 for food and catering?",
                "What is the procedure for bunkering fresh water?"
            ]
        ),
    ],
    "entertainment": [
        (
            "That belongs to Hollywood rather than the high seas! I'm Dolphin, your marine training tutor, "
            "dedicated strictly to navigation, vessel operations, and marine safety. Let's get back on course!",
            [
                "How does COLREG Rule 15 handle a crossing situation?",
                "What is the anchor watchkeeping procedure?",
                "Explain the emergency steering drill procedure."
            ]
        ),
        (
            "Pop culture and cinema fall outside my maritime curriculum. I specialize in shipboard procedures, "
            "COLREGs, firefighting, and engine room systems. What vessel topic would you like to discuss today?",
            [
                "What are the checks before entering an enclosed space?",
                "What are the requirements for an Emergency Escape Breathing Device (EEBD)?",
                "Explain the operation of an Oily Water Separator (OWS)."
            ]
        ),
    ],
    "sports": [
        (
            "I'm engineered for the high seas, not the sports arena! My knowledge is anchored in nautical science, "
            "marine diesel engines, and maritime safety. What shipboard operation can I help you learn about?",
            [
                "How does a two-stroke marine diesel engine scavenging system work?",
                "What are the daily routines of an Officer of the Watch (OOW)?",
                "How does a marine turbocharger operate?"
            ]
        ),
        (
            "Athletics and sports tournaments fall outside our seafarer training syllabus. "
            "Let's steer back toward maritime topics—feel free to ask about bridge watchkeeping, cargo handling, or vessel stability.",
            [
                "What are the key principles of ship stability and metacenter?",
                "What precautions are required during heavy weather navigation?",
                "How is crude oil washing (COW) conducted on tankers?"
            ]
        ),
    ],
    "consumer_tech": [
        (
            "Consumer gadgets and consumer electronics fall outside my maritime syllabus. "
            "I specialize exclusively in marine electronics, bridge consoles, radar systems, and shipboard power distribution. "
            "What maritime equipment would you like to review?",
            [
                "How does Automatic Radar Plotting Aid (ARPA) acquire targets?",
                "What are the carriage requirements for GMDSS radio equipment?",
                "Explain the function of a Voyage Data Recorder (VDR)."
            ]
        ),
        (
            "That's outside our maritime training curriculum! While I don't cover consumer smartphones or gaming, "
            "I can guide you through shipboard communication, Inmarsat systems, or navigational aids.",
            [
                "How does an AIS transponder transmit navigational data?",
                "What is the purpose of a Bridge Navigational Watch Alarm System (BNWAS)?",
                "Explain the operating principles of an echo sounder."
            ]
        ),
    ],
    "finance": [
        (
            "Crypto and stock markets aren't on my maritime charts! My training is focused on vessel chartering terms, "
            "bunker management, cargo manifests, and port state control compliance. What maritime operational topic can I assist with?",
            [
                "What is a Bunker Delivery Note (BDN) and why is it important under MARPOL?",
                "How is fuel oil consumption monitored using SEEMP?",
                "What are the procedures during a Port State Control (PSC) inspection?"
            ]
        ),
    ],
    "politics": [
        (
            "Political commentary lies outside our seafarer training scope! I specialize in maritime governance, "
            "such as IMO conventions (SOLAS, MARPOL, STCW) and flag state regulations. What maritime regulation would you like to discuss?",
            [
                "What are the mandatory certificates required under MARPOL?",
                "How does the International Safety Management (ISM) Code function?",
                "What are the duties of Port State Control (PSC) inspectors?"
            ]
        ),
    ],
    "general": [
        (
            "Ahoy! That subject lies outside my navigational charts. I'm Dolphin, your marine training tutor, "
            "specialized exclusively in maritime education, marine engineering, ship operations, and seafarer safety. "
            "What maritime system can I assist you with today?",
            [
                "What is the procedure for an enclosed space entry?",
                "How does COLREG Rule 15 handle a crossing situation?",
                "What are the essential checks for a marine auxiliary boiler?"
            ]
        ),
        (
            "That topic falls outside the maritime training curriculum. I am dedicated to helping seafarers master "
            "nautical navigation, engine room operations, COLREGs, and SOLAS safety standards. What would you like to explore?",
            [
                "What are the main types of marine pumps and their applications?",
                "Explain the starting sequence of a marine diesel generator.",
                "What are the life-saving appliances required on cargo vessels under SOLAS?"
            ]
        ),
        (
            "That's outside our seafaring curriculum! My training is focused entirely on ship operations, "
            "marine propulsion, bridge watchkeeping, and safety compliance. Let's steer back to a maritime topic!",
            [
                "What are the actions to take in a Man Overboard (MOB) situation?",
                "How does a marine sewage treatment plant function?",
                "Explain the working principle of an oily water separator (15 ppm)."
            ]
        ),
        (
            "I'm Dolphin, specialized strictly in nautical science, marine engineering, and maritime regulations. "
            "I'm not equipped for general non-marine questions, but I'd be glad to help you with shipboard procedures, "
            "machinery troubleshooting, or navigation rules!",
            [
                "What is the difference between fixed pitch and controllable pitch propellers?",
                "What are the precautions during bunkering operations?",
                "How does an inert gas system (IGS) protect cargo tanks on tankers?"
            ]
        ),
    ]
}


def get_varied_off_topic_response(query: str, category: Optional[str] = None) -> Tuple[str, List[str]]:
    """Get a varied, category-specific off-topic response and tailored question suggestions (0.00ms)."""
    cat = category or categorize_off_topic_query(query)
    templates = OFF_TOPIC_TONES_MAP.get(cat, OFF_TOPIC_TONES_MAP["general"])
    return random.choice(templates)


async def generate_dynamic_off_topic_response(
    query: str,
    openai_client: Optional[Any] = None,
    timeout_sec: float = 1.6,
) -> Tuple[str, List[str]]:
    """
    Hybrid off-topic generator:
    1. Tries a fast LLM generation via gpt-4o-mini to produce a tailored 1-2 sentence response.
    2. If LLM is slow, fails, or unavailable, instantly falls back to the curated category tone generator (0ms).
    """
    category = categorize_off_topic_query(query)
    fallback_text, fallback_suggestions = get_varied_off_topic_response(query, category)

    try:
        if openai_client is None:
            from openai import AsyncOpenAI
            from config import settings
            openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

        system_prompt = (
            "You are Dolphin, an expert Marine Tutor AI specialized exclusively in maritime education, "
            "marine engineering, nautical science (COLREGs), and shipboard safety for seafarers.\n"
            "The user asked a non-marine or off-topic question.\n"
            "In 1 to 2 engaging, natural sentences, politely decline answering the off-topic question and warmly "
            "invite them to ask about shipboard procedures, engine room systems, navigation, or maritime safety.\n"
            "CRITICAL RULES:\n"
            "1. Vary your opening phrasing naturally. Avoid repetitive cliches; do NOT start every response with 'Ahoy' or 'Ahoy there'. Use fresh openings such as:\n"
            "   - 'That topic lies beyond our maritime training scope...'\n"
            "   - 'I specialize exclusively in marine engineering and shipboard operations...'\n"
            "   - 'That one is outside my navigational course...'\n"
            "   - 'While that is an interesting question, my knowledge is dedicated to seafaring...'\n"
            "   - 'That subject belongs outside our vessel curriculum...'\n"
            "2. Briefly and naturally acknowledge what they asked, then warmly pivot to a relevant marine topic.\n"
            "3. Do NOT provide answers, solutions, or code for the non-marine question."
        )

        resp = await asyncio.wait_for(
            openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"User question: {query}"}
                ],
                temperature=0.75,
                max_tokens=80,
            ),
            timeout=timeout_sec
        )

        content = resp.choices[0].message.content.strip()
        if content and len(content) >= 20:
            return content, fallback_suggestions

    except Exception:
        pass

    return fallback_text, fallback_suggestions

