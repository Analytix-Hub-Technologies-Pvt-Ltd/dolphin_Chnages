import os
import asyncio
import re
import io
import json
import base64
from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx
from loguru import logger

from config import settings


class ImageService:

    def __init__(self):
        self.image_dir = Path("storage/image_json")
        self.storage_images_dir = Path("storage/images")
        self.storage_pdf_images_dir = Path("storage/pdf_images")
        self.storage_images_dir.mkdir(parents=True, exist_ok=True)
        self.storage_pdf_images_dir.mkdir(parents=True, exist_ok=True)
        self._client: Optional[httpx.AsyncClient] = None
        self._failed_image_ids: set = set()
        self._failed_pdf_extracts: set = set()

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(verify=False, timeout=5.0)
        return self._client

    def get_images_by_topic_code(self, topic_code: str):
        if not topic_code or not self.image_dir.exists():
            return []

        try:
            file_path = self.image_dir / f"{topic_code}.json"
            if not file_path.exists():
                return []

            with open(
                file_path,
                "r",
                encoding="utf-8"
            ) as f:
                images = json.load(f)

            result = []
            seen = set()
            for image in images:
                image_id = str(image.get("Id") or "").strip()
                b64 = str(image.get("base64") or "").strip()

                unique_key = image_id if image_id else b64
                if unique_key in seen:
                    continue

                seen.add(unique_key)

                raw_b64 = image.get("base64")
                clean_b64 = raw_b64 if (raw_b64 and str(raw_b64).strip() not in ("None", "null", "")) else None
                image_format = image.get("format") or "png"
                img_id = image.get("Id") or image.get("id")

                result.append(
                    {
                        "id": img_id,
                        "title": image.get("Title") or image.get("title") or "Image",
                        "about": image.get("About") or image.get("about"),
                        "format": image_format,
                        "base64": clean_b64,
                        "url": f"/storage/images/{img_id}.{image_format}" if img_id else None
                    }
                )

            return result

        except Exception as e:
            logger.debug(f"Failed to read image JSON for topic {topic_code}: {e}")
            return []

    async def fetch_remote_image(self, image_id: str, target_path: str | Path) -> Optional[bytes]:
        """Fetch image on-demand from external course API and cache locally on disk."""
        if not image_id or image_id.lower() in ("none", "null", ""):
            return None

        clean_id = str(image_id).strip()
        if clean_id in self._failed_image_ids:
            return None

        api_key = settings.external_api_key or "CDDDCD43BC944F2AA5DC501FB2CDE136"
        api_base = settings.external_api_base_url or "https://ai.marinerskills.com/aidata"
        if api_key == "test-mode":
            api_key = "CDDDCD43BC944F2AA5DC501FB2CDE136"
        if api_base == "test-mode":
            api_base = "https://ai.marinerskills.com/aidata"

        try:
            url = f"{api_base.rstrip('/')}/ImageData"
            payload = {"Key": api_key, "ID": clean_id}
            client = await self._get_client()
            resp = await asyncio.wait_for(client.post(url, json=payload), timeout=6.0)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("errorCode", 0) == 0 and data.get("value"):
                    image_data_str = data["value"]
                    if image_data_str.startswith("data:image/"):
                        _, encoded = image_data_str.split(",", 1)
                        image_bytes = base64.b64decode(encoded)
                    else:
                        image_bytes = base64.b64decode(image_data_str)

                    if image_bytes and len(image_bytes) > 50:
                        t_path = Path(target_path)
                        t_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(t_path, "wb") as f:
                            f.write(image_bytes)

                        # Also ensure cached in storage/images
                        fallback_path = self.storage_images_dir / t_path.name
                        if not fallback_path.exists():
                            with open(fallback_path, "wb") as f2:
                                f2.write(image_bytes)

                        return image_bytes
            self._failed_image_ids.add(clean_id)
        except Exception as e:
            self._failed_image_ids.add(clean_id)
            logger.debug(f"On-demand remote image fetch failed for {image_id}: {e}")

        return None

    async def extract_pdf_image(self, filename: str, target_path: str | Path) -> Optional[bytes]:
        """On-demand extract image from remote PDF if local pdf_images file is missing."""
        if not filename or filename in self._failed_pdf_extracts:
            return None
        try:
            import PyPDF2
            base_name, _ = os.path.splitext(filename)
            match = re.match(r'^([0-9a-fA-F-]+)_img_(\d+)_(.+)$', base_name)
            if not match:
                self._failed_pdf_extracts.add(filename)
                return None

            pdf_id, page_num_str, obj_name = match.groups()
            page_num = int(page_num_str)

            pdf_url = f"https://ai.marinerskills.com/pdf/{pdf_id}.pdf"
            client = await self._get_client()
            resp = await asyncio.wait_for(client.get(pdf_url), timeout=2.5)
            if resp.status_code != 200:
                self._failed_pdf_extracts.add(filename)
                return None
            pdf_bytes = resp.content

            reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
            if page_num >= len(reader.pages):
                self._failed_pdf_extracts.add(filename)
                return None

            page = reader.pages[page_num]
            if '/Resources' not in page or '/XObject' not in page['/Resources']:
                self._failed_pdf_extracts.add(filename)
                return None

            xObject = page['/Resources']['/XObject'].get_object()
            target_obj = None
            for k in [f"/{obj_name}", obj_name]:
                if k in xObject and xObject[k].get('/Subtype') == '/Image':
                    target_obj = xObject[k]
                    break

            if not target_obj:
                for k in xObject:
                    if xObject[k].get('/Subtype') == '/Image':
                        target_obj = xObject[k]
                        break

            if target_obj:
                img_data = target_obj.get_data()
                if img_data and len(img_data) > 100:
                    t_path = Path(target_path)
                    t_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(t_path, "wb") as f:
                        f.write(img_data)

                    fallback_path = self.storage_pdf_images_dir / t_path.name
                    if not fallback_path.exists():
                        with open(fallback_path, "wb") as f2:
                            f2.write(img_data)

                    return img_data

            self._failed_pdf_extracts.add(filename)
        except Exception as e:
            self._failed_pdf_extracts.add(filename)
            logger.debug(f"On-demand PDF image extraction failed for {filename}: {e}")

        return None

    def get_local_cached_url(self, img: Dict[str, Any] | str) -> Optional[str]:
        """
        Fast synchronous check to see if an image is already verified and available on local disk.
        Returns the resolved local URL without triggering any network I/O, or None if not found locally.
        """
        if not img:
            return None

        if isinstance(img, str):
            raw_url = img.strip()
            raw_b64 = ""
            img_id = ""
            img_fmt = "jpeg"
        elif isinstance(img, dict):
            raw_url = str(
                img.get("Url") or img.get("url") or img.get("image_url") or img.get("imageUrl") or img.get("path") or ""
            ).strip()
            raw_b64 = str(img.get("base64") or img.get("Base64") or "").strip()
            img_id = str(img.get("Id") or img.get("id") or "").strip()
            img_fmt = str(img.get("format") or "jpeg").lower()
        else:
            return None

        # Handle embedded base64 directly
        if raw_b64 and raw_b64 not in ("None", "null", "") and len(raw_b64) > 50:
            try:
                if not img_id:
                    import hashlib
                    img_id = hashlib.md5(raw_b64.encode("utf-8")).hexdigest()
                clean_b64 = raw_b64.split(",", 1)[1] if raw_b64.startswith("data:") else raw_b64
                img_bytes = base64.b64decode(clean_b64)
                if img_bytes and len(img_bytes) > 50:
                    filename = f"{img_id}.{img_fmt}"
                    out_path = self.storage_images_dir / filename
                    if not out_path.exists():
                        with open(out_path, "wb") as f:
                            f.write(img_bytes)
                    return f"/storage/images/{filename}"
            except Exception:
                pass

        if not raw_url or raw_url.lower() in ("none", "null", "undefined", ""):
            if img_id:
                raw_url = f"/storage/images/{img_id}.{img_fmt}"
            else:
                return None

        norm_url = re.sub(r'(?<!:)/{2,}', '/', raw_url)
        clean_lower = norm_url.lower()

        # Case 1: PDF extracted image
        is_pdf_image = "/storage/pdf_images/" in clean_lower or "_img_" in clean_lower or norm_url.lower().startswith("pdf_")
        if is_pdf_image:
            fname = norm_url.split("/")[-1].split("?")[0].strip()
            local_pdf_path = self.storage_pdf_images_dir / fname
            if local_pdf_path.exists() and local_pdf_path.stat().st_size > 50:
                return f"/storage/pdf_images/{fname}"
            return None

        # Case 2: Standard course image in /storage/images/ or from external course API
        if "/storage/images/" in clean_lower or img_id or clean_lower.endswith((".jpeg", ".jpg", ".png", ".webp")):
            fname = norm_url.split("/")[-1].split("?")[0].strip()
            if not fname and img_id:
                fname = f"{img_id}.{img_fmt}"

            base_name, ext = os.path.splitext(fname)
            for folder in [self.storage_images_dir, self.storage_pdf_images_dir]:
                for alt_ext in [ext, ".jpeg", ".jpg", ".png", ".webp", ""]:
                    check_path = folder / f"{base_name}{alt_ext}"
                    if check_path.exists() and check_path.stat().st_size > 50:
                        folder_name = "images" if folder == self.storage_images_dir else "pdf_images"
                        return f"/storage/{folder_name}/{check_path.name}"
            return None

        # Case 3: External independent image URL (e.g. https://example.com/photo.jpg)
        if norm_url.startswith(("http://", "https://")) and "marinerskills.com" not in norm_url:
            return norm_url

        return None

    async def ensure_image_cached(self, img: Dict[str, Any] | str) -> Optional[str]:
        """
        Validates that an image exists on disk or successfully fetches/caches it.
        Returns the resolved local URL (e.g. /storage/images/xyz.jpeg) if available and non-broken,
        or None if image is broken/unavailable.
        """
        if not img:
            return None

        # Fast local disk check first
        local_url = self.get_local_cached_url(img)
        if local_url:
            return local_url

        if isinstance(img, str):
            raw_url = img.strip()
            raw_b64 = ""
            img_id = ""
            img_fmt = "jpeg"
        elif isinstance(img, dict):
            raw_url = str(
                img.get("Url") or img.get("url") or img.get("image_url") or img.get("imageUrl") or img.get("path") or ""
            ).strip()
            raw_b64 = str(img.get("base64") or img.get("Base64") or "").strip()
            img_id = str(img.get("Id") or img.get("id") or "").strip()
            img_fmt = str(img.get("format") or "jpeg").lower()
        else:
            return None

        if not raw_url or raw_url.lower() in ("none", "null", "undefined", ""):
            if img_id:
                raw_url = f"/storage/images/{img_id}.{img_fmt}"
            else:
                return None

        norm_url = re.sub(r'(?<!:)/{2,}', '/', raw_url)
        clean_lower = norm_url.lower()

        # Case 1: PDF extracted image
        is_pdf_image = "/storage/pdf_images/" in clean_lower or "_img_" in clean_lower or norm_url.lower().startswith("pdf_")
        if is_pdf_image:
            fname = norm_url.split("/")[-1].split("?")[0].strip()
            local_pdf_path = self.storage_pdf_images_dir / fname
            if local_pdf_path.exists() and local_pdf_path.stat().st_size > 50:
                return f"/storage/pdf_images/{fname}"

            # Try on-demand extraction
            extracted = await self.extract_pdf_image(fname, local_pdf_path)
            if extracted and len(extracted) > 50:
                return f"/storage/pdf_images/{fname}"
            return None

        # Case 2: Standard course image in /storage/images/ or from external course API
        if "/storage/images/" in clean_lower or img_id or clean_lower.endswith((".jpeg", ".jpg", ".png", ".webp")):
            fname = norm_url.split("/")[-1].split("?")[0].strip()
            if not fname and img_id:
                fname = f"{img_id}.{img_fmt}"

            base_name, ext = os.path.splitext(fname)
            for folder in [self.storage_images_dir, self.storage_pdf_images_dir]:
                for alt_ext in [ext, ".jpeg", ".jpg", ".png", ".webp", ""]:
                    check_path = folder / f"{base_name}{alt_ext}"
                    if check_path.exists() and check_path.stat().st_size > 50:
                        folder_name = "images" if folder == self.storage_images_dir else "pdf_images"
                        return f"/storage/{folder_name}/{check_path.name}"

            # Try fetching from remote course API
            target_id = img_id or base_name
            target_file = f"{target_id}.jpeg"
            target_path = self.storage_images_dir / target_file
            fetched = await self.fetch_remote_image(target_id, target_path)
            if fetched and len(fetched) > 50:
                return f"/storage/images/{target_file}"

            return None

        # Case 3: External independent image URL (e.g. https://example.com/photo.jpg)
        if norm_url.startswith(("http://", "https://")) and "marinerskills.com" not in norm_url:
            return norm_url

        return None