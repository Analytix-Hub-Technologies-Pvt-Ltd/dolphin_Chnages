import asyncio
import aiohttp
import base64
import os
import re
from typing import Any, Dict, List, Optional
from loguru import logger
from config import settings

STORAGE_IMAGES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "storage", "images")
os.makedirs(STORAGE_IMAGES_DIR, exist_ok=True)

UUID_PATTERN = re.compile(r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', re.IGNORECASE)

class ImageManager:
    """Manages fetching, local disk caching, and base64 embedding of course images."""

    @staticmethod
    def extract_image_id(img: Dict[str, Any]) -> str:
        """Extract UUID image id from id, Id, url, or Url."""
        raw_id = str(img.get("id") or img.get("Id") or img.get("image_id") or "").strip()
        match = UUID_PATTERN.search(raw_id)
        if match:
            return match.group(1).lower()
        
        raw_url = str(img.get("url") or img.get("Url") or img.get("imageurl") or "").strip()
        match_url = UUID_PATTERN.search(raw_url)
        if match_url:
            return match_url.group(1).lower()
        return raw_id.lower() if raw_id else (raw_url.lower() if raw_url else "")

    @classmethod
    async def fetch_and_cache_image(cls, image_id: str) -> Optional[str]:
        """Fetch image from API if not cached locally, returns base64 data URI or None."""
        if not image_id:
            return None

        # Check if already exists on disk
        for ext in ["jpeg", "jpg", "png", "webp"]:
            local_path = os.path.join(STORAGE_IMAGES_DIR, f"{image_id}.{ext}")
            if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
                try:
                    with open(local_path, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode("utf-8")
                        mime = "image/png" if ext == "png" else ("image/webp" if ext == "webp" else "image/jpeg")
                        return f"data:{mime};base64,{b64}"
                except Exception as e:
                    logger.warning(f"Failed to read cached image {local_path}: {e}")

        # Fetch from remote API
        api_key = settings.external_api_key or "CDDDCD43BC944F2AA5DC501FB2CDE136"
        base_url = settings.external_api_base_url or "https://ai.marinerskills.com/aidata"
        url = f"{base_url}/ImageData"
        payload = {"Key": api_key, "ID": image_id}

        try:
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=3.0)) as response:
                    if response.status != 200:
                        return None
                    data = await response.json()
                    val = data.get("value", "")
                    if not val or not isinstance(val, str) or not val.startswith("data:image/"):
                        return None

                    header, encoded = val.split(',', 1)
                    fmt = header.split(';')[0].split('/')[1]
                    img_bytes = base64.b64decode(encoded)

                    local_path = os.path.join(STORAGE_IMAGES_DIR, f"{image_id}.{fmt}")
                    with open(local_path, "wb") as f:
                        f.write(img_bytes)

                    return val
        except Exception as e:
            logger.debug(f"Failed to fetch image {image_id} from API: {e}")
            return None

    @classmethod
    async def process_and_cache_images(cls, images: List[Dict[str, Any]], max_images: int = 6) -> List[Dict[str, Any]]:
        """Process a list of image items, ensuring deduplication, local caching, and valid data/URL without blocking."""
        processed = []
        seen_ids = set()
        seen_titles = set()

        base_url = settings.image_base_url.rstrip("/") if getattr(settings, "image_base_url", None) else "http://localhost:8000"

        for img in images:
            if not isinstance(img, dict):
                continue
            
            raw_url = str(img.get("url") or img.get("Url") or img.get("imageurl") or "").strip()
            if "pdf_images" in raw_url:
                continue

            img_id = cls.extract_image_id(img)
            if not img_id:
                continue

            title = str(img.get("title") or img.get("Title") or "").strip()
            clean_title = re.sub(r'[^a-z0-9]+', ' ', title.lower()).strip()

            # Deduplication by UUID/ID
            if img_id in seen_ids:
                continue
            # Deduplication by normalized title
            if clean_title and len(clean_title) > 3 and clean_title in seen_titles:
                continue

            seen_ids.add(img_id)
            if clean_title and len(clean_title) > 3:
                seen_titles.add(clean_title)

            # Check if local image exists
            local_exists = False
            b64_uri = ""
            for ext in ["jpeg", "jpg", "png", "webp"]:
                local_path = os.path.join(STORAGE_IMAGES_DIR, f"{img_id}.{ext}")
                if os.path.exists(local_path):
                    local_exists = True
                    try:
                        with open(local_path, "rb") as f:
                            data = f.read()
                            b64_uri = f"data:image/{ext};base64,{base64.b64encode(data).decode('utf-8')}"
                    except Exception:
                        pass
                    break

            # If not on local disk and valid UUID, trigger background download asynchronously
            if not local_exists and UUID_PATTERN.match(img_id):
                asyncio.create_task(cls.fetch_and_cache_image(img_id))

            display_url = raw_url if (raw_url.startswith("http://") or raw_url.startswith("https://")) else f"{base_url}/storage/images/{img_id}.jpeg"
            about = str(img.get("about") or img.get("About") or "").strip()

            processed.append({
                "id": img_id,
                "Id": img_id,
                "title": title or "Reference Image",
                "Title": title or "Reference Image",
                "about": about,
                "About": about,
                "url": display_url,
                "Url": display_url,
                "base64": b64_uri,
            })

            if len(processed) >= max_images:
                break

        return processed
