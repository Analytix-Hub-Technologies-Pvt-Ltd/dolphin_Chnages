# pipeline/retrieval.py

import re
import json
from typing import Any, Dict, List, Optional
from loguru import logger

from config import settings
from models.database import get_pool
from retrieval.faiss_store import DEFAULT_TOP_K
from retrieval.postgres_loader import PostgresLoader
from pipeline.manual_filter import is_manual_allowed_for_ship_type


# -----------------------------
# SAFE GET
# -----------------------------
def safe_get(state: Any, key: str, default=None):
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


# -----------------------------
# NORMALIZE VIDEO URL
# -----------------------------
def normalize_video_url(url: str) -> str:
    if not url:
        return ""

    url = url.strip().lower()

    if url.startswith("http://"):
        url = url.replace("http://", "https://", 1)

    if "?" in url:
        base, query = url.split("?", 1)
        important = []
        for p in query.split("&"):
            if p.split("=")[0] in ["v", "id", "video_id"]:
                important.append(p)
        url = base + ("?" + "&".join(important) if important else "")

    return url.rstrip("/")


# -----------------------------
# MEDIA PARSER
# -----------------------------
def coerce_media(value):
    if value is None:
        return []

    if isinstance(value, list):
        return [v for v in value if isinstance(v, dict)]

    if isinstance(value, dict):
        return [value]

    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict):
                return [parsed]
        except:
            return []

    return []


# -----------------------------
# NORMALIZE VIDEO OBJECT
# -----------------------------
def normalize_video_item(v: Any, default_title: str = "") -> Optional[Dict[str, Any]]:
    if not isinstance(v, dict):
        return None
    url = v.get("url") or v.get("Url") or v.get("videourl") or v.get("VideoUrl") or ""
    if not url:
        return None
    thumbnail = v.get("thumbnail") or v.get("Thumbnail") or v.get("thumbnail_url") or v.get("ThumbnailUrl") or ""
    title = v.get("title") or v.get("Title") or default_title or "Video"
    about = v.get("about") or v.get("About") or ""
    vid_id = v.get("id") or v.get("Id") or ""

    return {
        "id": vid_id,
        "Id": vid_id,
        "url": url,
        "Url": url,
        "thumbnail": thumbnail,
        "Thumbnail": thumbnail,
        "title": title,
        "Title": title,
        "about": about,
        "About": about,
    }


# -----------------------------
# NORMALIZE IMAGE OBJECT
# -----------------------------
def normalize_image_item(img: Any, default_title: str = "") -> Optional[Dict[str, Any]]:
    if not isinstance(img, dict):
        return None
    url = img.get("url") or img.get("Url") or img.get("imageurl") or img.get("ImageUrl") or ""
    if not url or not isinstance(url, str):
        return None
    # Fix accidental double slashes in URL path (preserving https:// or http://)
    url = re.sub(r'([^:])//+', r'\1/', url.strip())
    
    # Exclude broken pdf_images
    if "pdf_images" in url:
        return None

    raw_id = str(img.get("id") or img.get("Id") or "").strip()
    uuid_match = re.search(r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', raw_id + " " + url, re.I)
    img_id = uuid_match.group(1).lower() if uuid_match else raw_id.lower()

    if not img_id:
        return None

    title = img.get("title") or img.get("Title") or default_title or "Reference Image"
    about = img.get("about") or img.get("About") or ""

    return {
        "id": img_id,
        "Id": img_id,
        "url": url,
        "Url": url,
        "title": str(title).strip(),
        "Title": str(title).strip(),
        "about": str(about).strip(),
        "About": str(about).strip(),
    }


# -----------------------------
# DOMAIN ACRONYM & KEYWORD MAPPINGS
# -----------------------------
COMMON_GENERIC_WORDS = {
    "oil", "system", "systems", "rule", "rules", "water", "air", "ship", "ships",
    "marine", "gas", "safety", "pump", "pumps", "engine", "engines", "process",
    "processes", "operation", "operations", "management", "equipment", "vessel",
    "vessels", "tanker", "tankers", "types", "type", "guide", "procedure",
    "procedures", "basics", "case", "study", "part", "duties", "service", "services",
    "introduction", "overview", "standard", "standards", "general", "precautions",
    "checklist", "checklists", "work", "entry", "requirement", "requirements",
    "action", "actions", "plan", "plans", "method", "methods", "practice", "practices",
    "video", "videos", "image", "images", "course", "training", "level", "levels",
    "media", "medium", "agent", "agents", "material", "materials"
}

QUERY_STOP_WORDS = {
    "what", "is", "are", "the", "a", "an", "of", "and", "or", "in", "on", "for", "to",
    "how", "can", "you", "tell", "me", "about", "explain", "give", "details",
    "checklist", "checklists", "sms", "qms", "from", "my", "our", "provide",
    "please", "with", "entry", "work", "procedure", "procedures", "do", "we",
    "have", "show", "list", "steps", "guidelines", "document", "manual", "i",
    "need", "want", "know", "related", "any", "which", "when", "why", "where",
    "according", "regulations", "regulation"
}

ACRONYM_MAP = {
    "cow": {
        "phrases": [
            "crude oil washing", "cow system", "cow procedure", "cow operation",
            "crude oil washing machine", "washing cycles of crude oil", "cow pipeline",
            "cow machines", "tank cleaning nozzles", "crude oil washing lines"
        ],
        "fallback_phrases": [
            "oil tankers tank cleaning", "cargo tank cleaning", "tank cleaning on crude oil"
        ],
        "negative": [
            "chemical tanker", "chemical tankers", "fatigue", "leadership",
            "fire fighting", "fire-fighting", "boiler", "bulk carrier",
            "ballast water", "steering", "navigation", "colreg", "anchor", "hitch"
        ]
    },
    "igs": {
        "phrases": [
            "inert gas system", "inert gas plant", "inert gas generator",
            "igs system", "inert gas operation", "inert gas"
        ],
        "fallback_phrases": [
            "flue gas", "inerting", "gas freeing"
        ],
        "negative": [
            "fatigue", "leadership", "colreg", "chemical tanker", "anchor", "hitch"
        ]
    },
    "ows": {
        "phrases": [
            "oily water separator", "oil water separator", "15 ppm",
            "bilge separator", "ows operation", "15ppm monitor"
        ],
        "fallback_phrases": [
            "bilge water", "oily bilge", "bilge oil separator"
        ],
        "negative": [
            "fatigue", "leadership", "colreg", "crude oil washing", "cow",
            "two stroke", "four stroke", "engine cycle"
        ]
    },
    "odme": {
        "phrases": [
            "oil discharge monitoring", "odme system", "oil discharge monitor"
        ],
        "fallback_phrases": [
            "oil discharge", "marpol annex 1"
        ],
        "negative": [
            "fatigue", "leadership", "colreg", "fire fighting"
        ]
    },
    "ecdis": {
        "phrases": [
            "electronic chart display", "ecdis operation", "electronic chart", "ecdis safety"
        ],
        "fallback_phrases": [
            "ecdis", "enc"
        ],
        "negative": [
            "engine", "boiler", "cow", "ows", "fatigue"
        ]
    },
    "colreg": {
        "phrases": [
            "collision regulations", "colreg", "steering and sailing rules",
            "rule 15", "rule 14", "rule 13", "rule 18", "rule 19", "rule 10",
            "rule 8", "rule 7", "rule 6", "rule 5", "crossing situation",
            "head on situation", "overtaking"
        ],
        "fallback_phrases": [
            "rules of the road", "collision avoidance", "navigational watch"
        ],
        "negative": [
            "engine", "boiler", "cow", "ows", "chemical tanker", "tank cleaning"
        ]
    },
    "solas": {
        "phrases": [
            "safety of life at sea", "solas convention", "solas requirements"
        ],
        "fallback_phrases": [
            "solas"
        ],
        "negative": []
    },
    "marpol": {
        "phrases": [
            "marpol convention", "prevention of pollution", "marpol annex i",
            "marpol annex ii", "marpol annex v", "marpol annex vi"
        ],
        "fallback_phrases": [
            "marpol", "marine pollution"
        ],
        "negative": []
    },
    "bwm": {
        "phrases": [
            "ballast water management", "ballast water treatment", "bwts",
            "bwm convention", "ballast exchange"
        ],
        "fallback_phrases": [
            "ballast water", "bwm"
        ],
        "negative": [
            "cow", "crude oil washing"
        ]
    },
    "mlc": {
        "phrases": [
            "maritime labour convention", "mlc 2006", "seafarer rights", "hours of rest"
        ],
        "fallback_phrases": [
            "mlc"
        ],
        "negative": [
            "engine", "boiler", "cow", "ows"
        ]
    },
    "ism": {
        "phrases": [
            "international safety management", "ism code", "safety management system"
        ],
        "fallback_phrases": [
            "safety management", "ism"
        ],
        "negative": []
    },
    "fire": {
        "phrases": [
            "fire fighting", "fire-fighting", "fire extinguisher", "fire extinguishers",
            "fire extinguishing", "fire detection", "fire safety", "fire fighting appliances",
            "fire fighting system", "fire prevention", "foam fire extinguishing", "carbon dioxide fire"
        ],
        "fallback_phrases": [
            "fire", "extinguish", "extinguisher", "fire fighting", "firefighting", "foam operation"
        ],
        "negative": [
            "crude oil washing", "cow", "ows", "ecdis", "colreg"
        ]
    },
    "fss": {
        "phrases": [
            "fire safety systems", "fss code", "fire fighting appliances", "fire extinguishing"
        ],
        "fallback_phrases": [
            "fss", "fire safety"
        ],
        "negative": []
    },
}

GENERIC_PLACEHOLDERS = {
    "video", "course video", "reference image", "image", "splash page mssv",
    "welcome test", "msve splash video", ""
}


# -----------------------------
# VIDEO RELEVANCE SCORING
# -----------------------------
def compute_video_relevance_score(video: dict, query: str, topic_name: str = "") -> float:
    """
    Score relevance of a video to the query (0.0 to 1.0).
    Requires title/topic precision, domain acronym expansion, and negative filtering.
    """
    if not query or not query.strip():
        return 0.0

    q = query.lower().strip()
    title = str(video.get("title") or video.get("Title") or "").lower().strip()
    t_name = str(topic_name or video.get("topic_name") or "").lower().strip()

    is_generic_title = title in GENERIC_PLACEHOLDERS or len(title) < 3
    effective_title = t_name if is_generic_title else title

    if not effective_title:
        return 0.0

    q_words = set(re.findall(r'\b[a-z0-9]+\b', q))
    content_q_words = [w for w in re.findall(r'\b[a-z0-9]+\b', q) if w not in QUERY_STOP_WORDS]

    # Negative filtering check
    for acr, config in ACRONYM_MAP.items():
        if acr in q_words or acr == q or any(p in q for p in config["phrases"]):
            for neg in config.get("negative", []):
                if neg in title:
                    return 0.0
                if is_generic_title and neg in t_name:
                    return 0.0

    # 1. Exact query phrase in title or topic
    if len(q) >= 3 and q in title:
        return 1.0
    if len(q) >= 3 and is_generic_title and q in t_name:
        return 0.95

    # 2. Acronym expansion check
    for acr, config in ACRONYM_MAP.items():
        if acr in q_words or acr == q or any(p in q for p in config["phrases"]):
            for phrase in config["phrases"]:
                if phrase in title:
                    return 0.98
                if is_generic_title and phrase in t_name:
                    return 0.95
                if phrase in t_name and not is_generic_title:
                    title_words = set(re.findall(r'\b[a-z0-9]+\b', title))
                    phrase_words = set(re.findall(r'\b[a-z0-9]+\b', phrase))
                    if title_words.intersection(phrase_words) or len(title_words - COMMON_GENERIC_WORDS) == 0:
                        return 0.90
                    if any(w in title for w in ["wash", "clean", "tank", "valve", "pipe", "nozzle", "procedure", "operation"]):
                        return 0.88

            for fb_phrase in config.get("fallback_phrases", []):
                if fb_phrase in title:
                    return 0.85
                if is_generic_title and fb_phrase in t_name:
                    return 0.80

    # 3. Multi-word phrase from query matching in title
    if len(content_q_words) >= 2:
        for length in [min(len(content_q_words), 3), 2]:
            for i in range(len(content_q_words) - length + 1):
                subphrase = " ".join(content_q_words[i:i+length])
                if len(subphrase) > 4:
                    if subphrase in title:
                        return 0.92
                    if is_generic_title and subphrase in t_name:
                        return 0.88

    # 4. Distinctive keyword overlap in title
    distinctive_q_words = {w for w in content_q_words if w not in COMMON_GENERIC_WORDS and len(w) > 2}
    if distinctive_q_words:
        target_words = set(re.findall(r'\b[a-z0-9]+\b', title if not is_generic_title else t_name))
        overlap = distinctive_q_words.intersection(target_words)
        if overlap:
            score = len(overlap) / len(distinctive_q_words)
            if score >= 0.5:
                return 0.75 + (score * 0.2)
            else:
                return 0.72

    return 0.0


# -----------------------------
# IMAGE RELEVANCE SCORING
# -----------------------------
def compute_image_relevance_score(image: dict, query: str, topic_name: str = "") -> float:
    """
    Score relevance of an image to the query (0.0 to 1.0).
    Requires title/topic precision, domain acronym expansion, and negative filtering.
    """
    if not query or not query.strip():
        return 0.0

    q = query.lower().strip()
    title = str(image.get("title") or image.get("Title") or "").lower().strip()
    t_name = str(topic_name or image.get("topic_name") or "").lower().strip()

    is_generic_title = title in GENERIC_PLACEHOLDERS or len(title) < 3
    effective_title = t_name if is_generic_title else title

    if not effective_title:
        return 0.0

    q_words = set(re.findall(r'\b[a-z0-9]+\b', q))
    content_q_words = [w for w in re.findall(r'\b[a-z0-9]+\b', q) if w not in QUERY_STOP_WORDS]
    distinctive_q_words = {w for w in content_q_words if w not in COMMON_GENERIC_WORDS and len(w) > 2}

    # Negative filtering check
    for acr, config in ACRONYM_MAP.items():
        if acr in q_words or acr == q or any(p in q for p in config["phrases"]):
            for neg in config.get("negative", []):
                if neg in title:
                    return 0.0
                if is_generic_title and neg in t_name:
                    return 0.0

    # If distinctive keywords exist (e.g. "burner", "chain"), require matching at least one distinctive word
    if distinctive_q_words:
        target_text = (title + " " + t_name).lower()
        matched_any = False
        for dw in distinctive_q_words:
            stem = dw[:-1] if dw.endswith("s") and len(dw) > 3 else dw
            if stem in target_text:
                matched_any = True
                break
        if not matched_any:
            return 0.0

    # 1. Exact query phrase in title or topic
    if len(q) >= 3 and q in title:
        return 1.0
    if len(q) >= 3 and is_generic_title and q in t_name:
        return 0.95

    # 2. Acronym expansion check
    for acr, config in ACRONYM_MAP.items():
        if acr in q_words or acr == q or any(p in q for p in config["phrases"]):
            for phrase in config["phrases"]:
                if phrase in title:
                    return 0.98
                if is_generic_title and phrase in t_name:
                    return 0.95
                if phrase in t_name and not is_generic_title:
                    title_words = set(re.findall(r'\b[a-z0-9]+\b', title))
                    phrase_words = set(re.findall(r'\b[a-z0-9]+\b', phrase))
                    if title_words.intersection(phrase_words) or len(title_words - COMMON_GENERIC_WORDS) == 0:
                        return 0.90
                    if any(w in title for w in ["wash", "clean", "tank", "valve", "pipe", "nozzle", "procedure", "operation"]):
                        return 0.88

            for fb_phrase in config.get("fallback_phrases", []):
                if fb_phrase in title:
                    return 0.85
                if is_generic_title and fb_phrase in t_name:
                    return 0.80

    # 3. Multi-word phrase from query matching in title
    if len(content_q_words) >= 2:
        for length in [min(len(content_q_words), 3), 2]:
            for i in range(len(content_q_words) - length + 1):
                subphrase = " ".join(content_q_words[i:i+length])
                if len(subphrase) > 4:
                    if subphrase in title:
                        return 0.92
                    if is_generic_title and subphrase in t_name:
                        return 0.88

    # 4. Distinctive keyword overlap in title
    if distinctive_q_words:
        target_words = set(re.findall(r'\b[a-z0-9]+\b', title if not is_generic_title else t_name))
        overlap = distinctive_q_words.intersection(target_words)
        if overlap:
            score = len(overlap) / len(distinctive_q_words)
            if score >= 0.5:
                return 0.75 + (score * 0.2)
            else:
                return 0.72

    # 5. Generic content word overlap
    if content_q_words:
        target_words = set(re.findall(r'\b[a-z0-9]+\b', title if not is_generic_title else t_name))
        overlap = set(content_q_words).intersection(target_words)
        if len(overlap) >= 2:
            return 0.70 + (len(overlap) / len(content_q_words) * 0.15)

    return 0.0


# -----------------------------
# SEARCH MATCHING VIDEOS IN DB
# -----------------------------
async def search_matching_videos_in_db(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Search for relevant videos in course_content based on query terms."""
    if not query or not query.strip():
        return []

    q = query.lower().strip()
    q_words = set(re.findall(r'\b[a-z0-9]+\b', q))
    content_q_words = [w for w in re.findall(r'\b[a-z0-9]+\b', q) if w not in QUERY_STOP_WORDS]
    distinctive_words = [w for w in content_q_words if w not in COMMON_GENERIC_WORDS and len(w) > 2]

    search_phrases = []
    # Check acronyms first
    for acr, config in ACRONYM_MAP.items():
        if acr in q_words or acr == q or any(p in q for p in config["phrases"]):
            search_phrases.extend(config["phrases"][:4])

    if distinctive_words:
        if len(distinctive_words) >= 2:
            search_phrases.append(" ".join(distinctive_words[:2]))
        for dw in distinctive_words[:3]:
            if dw not in search_phrases:
                search_phrases.append(dw)
            # Add singular/plural form
            if dw.endswith("s") and len(dw) > 3 and dw[:-1] not in search_phrases:
                search_phrases.append(dw[:-1])
            elif not dw.endswith("s") and len(dw) > 3 and (dw + "s") not in search_phrases:
                search_phrases.append(dw + "s")
    elif len(content_q_words) >= 2:
        search_phrases.append(" ".join(content_q_words[:2]))
        for w in content_q_words[:3]:
            if w not in search_phrases:
                search_phrases.append(w)

    if not search_phrases:
        return []

    try:
        pool = await get_pool()
        conditions = []
        params = []
        for i, phrase in enumerate(search_phrases[:5], start=1):
            conditions.append(f"topic_name ILIKE ${i} OR topic_video::text ILIKE ${i}")
            params.append(f"%{phrase}%")

        where_clause = " OR ".join(conditions)
        sql = f"""
            SELECT content_id, topic_name, topic_code, topic_video
            FROM course_content
            WHERE topic_video IS NOT NULL
              AND topic_video::text != '[]'
              AND topic_video::text != '"[]"'
              AND ({where_clause})
            LIMIT 50
        """
        rows = await pool.fetch(sql, *params)
        scored = []
        seen_ids = set()
        seen_titles = set()
        for r in rows:
            vids = coerce_media(r["topic_video"])
            for v in vids:
                norm_v = normalize_video_item(v, default_title=r["topic_name"])
                if not norm_v:
                    continue
                score = compute_video_relevance_score(norm_v, query, r["topic_name"])
                if score < 0.70:
                    continue
                vid_id = str(norm_v.get("id") or norm_v.get("video_id") or "").strip().lower()
                title_key = str(norm_v.get("title") or "").strip().lower()
                if vid_id and vid_id in seen_ids:
                    continue
                if title_key and len(title_key) > 3 and title_key in seen_titles:
                    continue
                if vid_id:
                    seen_ids.add(vid_id)
                if title_key and len(title_key) > 3:
                    seen_titles.add(title_key)
                scored.append((score, norm_v))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [v for s, v in scored[:limit]]
    except Exception as e:
        logger.debug(f"DB matching video search failed: {e}")
        return []


# -----------------------------
# SEARCH MATCHING IMAGES IN DB
# -----------------------------
async def search_matching_images_in_db(query: str, limit: int = 6) -> List[Dict[str, Any]]:
    """Search for relevant reference images in course_content based on query terms."""
    if not query or not query.strip():
        return []

    q = query.lower().strip()
    q_words = set(re.findall(r'\b[a-z0-9]+\b', q))
    content_q_words = [w for w in re.findall(r'\b[a-z0-9]+\b', q) if w not in QUERY_STOP_WORDS]
    distinctive_words = [w for w in content_q_words if w not in COMMON_GENERIC_WORDS and len(w) > 2]

    search_phrases = []
    # Check acronyms first
    for acr, config in ACRONYM_MAP.items():
        if acr in q_words or acr == q or any(p in q for p in config["phrases"]):
            search_phrases.extend(config["phrases"][:4])

    if distinctive_words:
        if len(distinctive_words) >= 2:
            search_phrases.append(" ".join(distinctive_words[:2]))
        for dw in distinctive_words[:3]:
            if dw not in search_phrases:
                search_phrases.append(dw)
            # Add singular/plural form
            if dw.endswith("s") and len(dw) > 3 and dw[:-1] not in search_phrases:
                search_phrases.append(dw[:-1])
            elif not dw.endswith("s") and len(dw) > 3 and (dw + "s") not in search_phrases:
                search_phrases.append(dw + "s")
    elif len(content_q_words) >= 2:
        search_phrases.append(" ".join(content_q_words[:2]))
        for w in content_q_words[:3]:
            if w not in search_phrases:
                search_phrases.append(w)

    if not search_phrases:
        return []

    try:
        pool = await get_pool()
        conditions = []
        params = []
        for i, phrase in enumerate(search_phrases[:6], start=1):
            conditions.append(f"topic_name ILIKE ${i} OR topic_image::text ILIKE ${i}")
            params.append(f"%{phrase}%")

        where_clause = " OR ".join(conditions)
        sql = f"""
            SELECT content_id, topic_name, topic_code, topic_image
            FROM course_content
            WHERE topic_image IS NOT NULL
              AND topic_image::text != '[]'
              AND topic_image::text != '"[]"'
              AND ({where_clause})
            LIMIT 50
        """
        rows = await pool.fetch(sql, *params)
        scored = []
        seen_ids = set()
        seen_titles = set()
        for r in rows:
            imgs = coerce_media(r["topic_image"])
            for img in imgs:
                norm_img = normalize_image_item(img, default_title=r["topic_name"])
                if not norm_img:
                    continue
                score = compute_image_relevance_score(norm_img, query, r["topic_name"])
                if score < 0.70:
                    continue
                img_id = str(norm_img.get("id") or "").strip().lower()
                clean_title = re.sub(r'[^a-z0-9]+', ' ', str(norm_img.get("title") or "").lower()).strip()
                if img_id and img_id in seen_ids:
                    continue
                if clean_title and len(clean_title) > 3 and clean_title in seen_titles:
                    continue
                if img_id:
                    seen_ids.add(img_id)
                if clean_title and len(clean_title) > 3:
                    seen_titles.add(clean_title)
                scored.append((score, norm_img))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [img for s, img in scored[:limit]]
    except Exception as e:
        logger.debug(f"DB matching image search failed: {e}")
        return []


# -----------------------------
# VIDEO EXTRACTION
# -----------------------------
def extract_videos(chunks, existing_videos, query: str = "", max_videos=15):
    """Extract and score videos from chunks and existing videos."""
    if not query or not query.strip():
        return []

    seen_ids = set()
    seen_titles = set()
    scored_candidates = []

    for c in chunks:
        t_name = c.get("topic_name", "")
        for v in c.get("videos", []):
            normalized_v = normalize_video_item(v, default_title=t_name)
            if not normalized_v:
                continue
            score = compute_video_relevance_score(normalized_v, query, t_name)
            if score < 0.70:
                continue
            vid_id = str(normalized_v.get("id") or normalized_v.get("video_id") or "").strip().lower()
            title_key = str(normalized_v.get("title") or "").strip().lower()
            if vid_id and vid_id in seen_ids:
                continue
            if title_key and len(title_key) > 3 and title_key in seen_titles:
                continue
            if vid_id:
                seen_ids.add(vid_id)
            if title_key and len(title_key) > 3:
                seen_titles.add(title_key)
            scored_candidates.append((score, normalized_v))

    for v in existing_videos:
        normalized_v = normalize_video_item(v) if isinstance(v, dict) else None
        if not normalized_v:
            continue
        score = compute_video_relevance_score(normalized_v, query)
        if score < 0.70:
            continue
        vid_id = str(normalized_v.get("id") or normalized_v.get("video_id") or "").strip().lower()
        title_key = str(normalized_v.get("title") or "").strip().lower()
        if vid_id and vid_id in seen_ids:
            continue
        if title_key and len(title_key) > 3 and title_key in seen_titles:
            continue
        if vid_id:
            seen_ids.add(vid_id)
        if title_key and len(title_key) > 3:
            seen_titles.add(title_key)
        scored_candidates.append((score, normalized_v))

    scored_candidates.sort(key=lambda x: x[0], reverse=True)
    return [v for s, v in scored_candidates[:max_videos]]


# -----------------------------
# IMAGE EXTRACTION
# -----------------------------
def extract_images(chunks, existing_images, query: str = "", max_images=6):
    """Extract and score images from chunks and existing images."""
    if not query or not query.strip():
        return []

    seen_ids = set()
    seen_titles = set()
    scored_candidates = []

    for c in chunks:
        t_name = c.get("topic_name", "")
        for img in c.get("images", []):
            norm_img = normalize_image_item(img, default_title=t_name)
            if not norm_img:
                continue
            score = compute_image_relevance_score(norm_img, query, t_name)
            if score < 0.70:
                continue
            img_id = str(norm_img.get("id") or "").strip().lower()
            clean_title = re.sub(r'[^a-z0-9]+', ' ', str(norm_img.get("title") or "").lower()).strip()
            if img_id and img_id in seen_ids:
                continue
            if clean_title and len(clean_title) > 3 and clean_title in seen_titles:
                continue
            if img_id:
                seen_ids.add(img_id)
            if clean_title and len(clean_title) > 3:
                seen_titles.add(clean_title)
            scored_candidates.append((score, norm_img))

    for img in existing_images:
        norm_img = normalize_image_item(img) if isinstance(img, dict) else None
        if not norm_img:
            continue
        score = compute_image_relevance_score(norm_img, query)
        if score < 0.70:
            continue
        img_id = str(norm_img.get("id") or "").strip().lower()
        clean_title = re.sub(r'[^a-z0-9]+', ' ', str(norm_img.get("title") or "").lower()).strip()
        if img_id and img_id in seen_ids:
            continue
        if clean_title and len(clean_title) > 3 and clean_title in seen_titles:
            continue
        if img_id:
            seen_ids.add(img_id)
        if clean_title and len(clean_title) > 3:
            seen_titles.add(clean_title)
        scored_candidates.append((score, norm_img))

    scored_candidates.sort(key=lambda x: x[0], reverse=True)
    return [img for s, img in scored_candidates[:max_images]]




# -----------------------------
# MAIN FUNCTION
# -----------------------------
async def retrieval_node(
    state: Dict[str, Any],
    vector_store,
    query_expansion_service=None,
) -> Dict[str, Any]:

    user_profile = (
            safe_get(state, "user_profile") or
            safe_get(state, "user") or   # fallback support
            {}
        )

    query = safe_get(state, "current_query", "") or ""
    decision = safe_get(state, "router_decision", {}) or {}
    company_id = user_profile.get("company_id")
    node_type = decision.get("node_type", "query")

    existing_chunks = safe_get(state, "retrieval_chunks", []) or []
    existing_videos = safe_get(state, "video_suggestions", []) or []

    standalone_query = decision.get("standalone_query") or query

    # -----------------------------
    # ⚡ SKIP DUPLICATE RETRIEVAL
    # -----------------------------
    if existing_chunks and node_type != "quiz":
        logger.info("⚡ Reusing existing chunks")

        state["retrieval_chunks"] = existing_chunks
        state["video_suggestions"] = extract_videos(existing_chunks, existing_videos, query=standalone_query)
        return state

    search_query = standalone_query

    # -----------------------------
    # QUERY EXPANSION
    # -----------------------------
    if query_expansion_service:
        try:
            search_query = await query_expansion_service.expand_query(
                search_query,
                chat_history=safe_get(state, "messages", []),
                use_llm=settings.query_expansion_use_llm,
            )
        except Exception as e:
            logger.warning(f"Query expansion failed: {e}")

    # -----------------------------
    # VECTOR SEARCH
    # -----------------------------
    try:
        chunks = await vector_store.search_with_embeddings(
            search_query,
            k=DEFAULT_TOP_K
        )
    except Exception as e:
        logger.error(f"Retrieval failed: {e}")
        chunks = []

    # Direct database keyword search fallback if FAISS index returns 0 results
    if not chunks and search_query:
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                keywords = [w for w in re.split(r'[^a-zA-Z0-9]+', search_query.strip()) if len(w) > 2 and w.lower() not in {"what", "is", "the", "and", "explain", "how", "process", "for", "with", "about", "tell"}]
                if keywords:
                    clauses = []
                    params = []
                    for idx, kw in enumerate(keywords[:4], 1):
                        clauses.append(f"(topic_name ILIKE ${idx} OR topic_content ILIKE ${idx})")
                        params.append(f"%{kw}%")
                    if clauses:
                        sql = f"SELECT content_id, topic_name, topic_code, topic_content, topic_video, topic_image, topic_pdf FROM course_content WHERE {' OR '.join(clauses)} LIMIT 10"
                        db_matches = await conn.fetch(sql, *params)
                        if db_matches:
                            chunks = [dict(r) for r in db_matches]
                            logger.info(f"Fallback DB search retrieved {len(chunks)} chunks")
        except Exception as e:
            logger.debug(f"Direct DB fallback search failed: {e}")

    # -----------------------------
    # DB FETCH
    # -----------------------------
    content_ids = [c.get("content_id") for c in chunks if c.get("content_id")]

    db_rows = {}
    if content_ids:
        try:
            pool = await get_pool()
            loader = PostgresLoader(pool)
            db_rows = await loader.fetch_course_content_by_ids(content_ids)
        except Exception as e:
            logger.error(f"DB fetch failed: {e}")

    # -----------------------------
    # NORMALIZE
    # -----------------------------
    normalized = []
    for c in chunks:
        db = db_rows.get(c.get("content_id"))
        merged = {**c, **(db or {})}
        normalized.append(normalize_chunk(merged))

    final_chunks = normalized or existing_chunks

    company_vector_store = safe_get(
        state,
        "company_vector_store"
    )

    # -----------------------------
    # COMPANY RETRIEVAL
    # -----------------------------
    existing_company_chunks = state.get("company_chunks", []) or []
    company_chunks = list(existing_company_chunks)

    if company_id and company_vector_store and not company_chunks:
        from pipeline.company_retrieval import is_company_match

        ship_type = user_profile.get("ship_type") or user_profile.get("ShipType") or ""
        company_name = (
            user_profile.get("company_name")
            or user_profile.get("CompanyName")
            or user_profile.get("company")
            or ""
        )
        logger.info(f"Searching company documents for company_id={company_id}, ship_type={ship_type}")

        try:
            company_results = await company_vector_store.search_with_embeddings(
                search_query,
                k=40,
            )

            logger.info(
                f"Company FAISS returned {len(company_results)} chunks"
            )

            for chunk in company_results:
                chunk_company_id = chunk.get("company_id")
                chunk_cname = chunk.get("company_name", "")
                if not is_company_match(chunk_company_id, company_id, company_name, chunk_cname):
                    continue

                doc_title = chunk.get("document_title", "")
                if not is_manual_allowed_for_ship_type(doc_title, ship_type):
                    logger.info(f"Filtered out chunk ('{doc_title}') for ship type '{ship_type}'")
                    continue

                company_chunks.append(
                    normalize_chunk(chunk)
                )
                if len(company_chunks) >= 20:
                    break

            logger.info(
                f"Matched company chunks: {len(company_chunks)}"
            )

        except Exception as e:
            logger.exception(f"Company retrieval failed: {e}")

    # -----------------------------
    # VIDEOS
    # -----------------------------
    effective_query = standalone_query or query
    videos = extract_videos(final_chunks, existing_videos, query=effective_query)

    if not videos and effective_query:
        # First attempt: targeted database search for matching video titles / topics
        try:
            db_matched_videos = await search_matching_videos_in_db(effective_query, limit=5)
            if db_matched_videos:
                videos = db_matched_videos
        except Exception as e:
            logger.debug(f"DB matching video search fallback failed: {e}")

    if not videos and vector_store and search_query:
        try:
            extra_raw = await vector_store.search_with_embeddings(search_query, k=25)
            extra_cids = [c.get("content_id") for c in (extra_raw or []) if c.get("content_id")]
            if extra_cids:
                pool = await get_pool()
                loader = PostgresLoader(pool)
                extra_rows = await loader.fetch_course_content_by_ids(extra_cids)
                extra_chunks = []
                for ec in extra_raw:
                    db_r = extra_rows.get(ec.get("content_id"))
                    merged = {**ec, **(db_r or {})}
                    extra_chunks.append(normalize_chunk(merged))
                # Only accept videos that are relevant to the query
                videos = extract_videos(extra_chunks, existing_videos, query=effective_query)
        except Exception as e:
            logger.debug(f"Extended video search failed: {e}")

    # -----------------------------
    # UPDATE STATE
    # -----------------------------
    state["retrieval_chunks"] = final_chunks
    state["company_chunks"] = company_chunks
    state["video_suggestions"] = videos
    state["standalone_query"] = standalone_query
    state["company_answer"] = None

    logger.info(
        f"Marine chunks : {len(final_chunks)}"
    )

    logger.info(
        f"Company chunks : {len(company_chunks)}"
    )

    return state