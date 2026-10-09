import os
import asyncio
import json
import re
from pathlib import Path
from typing import Dict, List, Optional
from loguru import logger


class PdfService:
    _instance: Optional["PdfService"] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self.storage_dir = Path("storage")
        self.titles_file = self.storage_dir / "pdf_titles.json"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, str] = {}
        self._load_cache()
        self._async_client: Optional[Any] = None
        self._failed_pdf_urls: set = set()
        self._initialized = True

    async def _get_async_client(self):
        import httpx
        if self._async_client is None or getattr(self._async_client, "is_closed", True):
            self._async_client = httpx.AsyncClient(verify=False, timeout=3.5)
        return self._async_client

    def _normalize_key(self, link_or_id: str) -> str:
        if not link_or_id:
            return ""
        return str(link_or_id).strip().lower()

    def _load_cache(self):
        if self.titles_file.exists():
            try:
                with open(self.titles_file, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load pdf_titles.json: {e}")
                self._cache = {}
        else:
            self._cache = {}

    def _save_cache(self):
        try:
            with open(self.titles_file, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save pdf_titles.json: {e}")

    def get_title(self, link_or_id: str) -> Optional[str]:
        if not link_or_id:
            return None
        norm = self._normalize_key(link_or_id)
        if norm in self._cache:
            return self._cache[norm]

        # Also check UUID only if link is a full URL or path
        if "/" in norm or "\\" in norm:
            clean = norm.replace("\\", "/")
            uuid_part = clean.split("/")[-1].replace(".pdf", "")
            if uuid_part in self._cache:
                return self._cache[uuid_part]
        return None

    def set_title(self, link_or_id: str, title: str):
        if not link_or_id or not title:
            return
        clean_title = title.strip()
        if not clean_title or len(clean_title) < 2:
            return
        norm = self._normalize_key(link_or_id)
        changed = False
        if self._cache.get(norm) != clean_title:
            self._cache[norm] = clean_title
            changed = True

        if "/" in norm or "\\" in norm:
            clean = norm.replace("\\", "/")
            uuid_part = clean.split("/")[-1].replace(".pdf", "")
            if uuid_part and self._cache.get(uuid_part) != clean_title:
                self._cache[uuid_part] = clean_title
                changed = True

        if changed:
            self._save_cache()

    def extract_title_from_pymupdf(self, doc) -> Optional[str]:
        """Extract clean, authentic document title from a PyMuPDF document."""
        try:
            # 1. Document metadata title
            meta_title = (doc.metadata.get("title") or "").strip()
            if meta_title and len(meta_title) > 3 and not meta_title.lower().endswith(".pdf"):
                if meta_title.lower() not in ("microsoft word", "untitled", "document", "document1", "adobe acrobat"):
                    return meta_title

            # 2. Table of Contents / Outline bookmarks
            try:
                toc = doc.get_toc()
                if toc and len(toc) > 0:
                    first_bookmark = toc[0][1].strip()
                    if 4 <= len(first_bookmark) <= 120 and not first_bookmark.lower().startswith("chapter"):
                        return first_bookmark
            except Exception:
                pass

            # 3. Prominent text lines on first 3 pages (Page 0, 1, or 2)
            for page_idx in range(min(3, len(doc))):
                page_text = doc[page_idx].get_text()
                lines = [l.strip() for l in page_text.split("\n") if l.strip()]
                for l in lines[:25]:
                    # Skip date/time lines (e.g. 7/8/22, 4:39 PM)
                    if re.match(r"^\d{1,2}/\d{1,2}/\d{2,4}", l):
                        continue
                    # Skip pure page numbers / fractions (e.g. 2/22, 1)
                    if re.match(r"^\d+(/\d+)?$", l):
                        continue
                    # Skip URLs
                    if l.startswith("http://") or l.startswith("https://") or "www." in l:
                        continue
                    # Skip author / by / page headers
                    if l.lower().startswith("by ") or l.lower().startswith("page ") or l.lower() in ("table of contents", "contents"):
                        continue
                    # Acceptable title line
                    if 4 <= len(l) <= 120:
                        return l
        except Exception as e:
            logger.debug(f"Failed to extract title from PyMuPDF doc: {e}")
        return None

    async def fetch_and_extract_title_async(self, raw_link: str) -> Optional[str]:
        """Fetch remote PDF and extract actual document title using PyMuPDF asynchronously."""
        if not raw_link or not (raw_link.startswith("http://") or raw_link.startswith("https://")):
            return None
        if raw_link in self._failed_pdf_urls:
            return None
        try:
            import pymupdf
            client = await self._get_async_client()
            resp = await asyncio.wait_for(client.get(raw_link), timeout=2.5)
            if resp.status_code == 200 and resp.content:
                doc = pymupdf.open(stream=resp.content, filetype="pdf")
                extracted = self.extract_title_from_pymupdf(doc)
                doc.close()
                if extracted:
                    self.set_title(raw_link, extracted)
                    return extracted
            self._failed_pdf_urls.add(raw_link)
        except Exception as e:
            self._failed_pdf_urls.add(raw_link)
            logger.debug(f"Failed to on-demand extract PDF title for {raw_link}: {e}")
        return None

    def fetch_and_extract_title(self, raw_link: str) -> Optional[str]:
        """Fetch remote PDF and extract actual document title using PyMuPDF."""
        if not raw_link or not (raw_link.startswith("http://") or raw_link.startswith("https://")):
            return None
        if raw_link in self._failed_pdf_urls:
            return None
        try:
            import httpx
            import pymupdf
            with httpx.Client(verify=False, timeout=5.0) as client:
                resp = client.get(raw_link)
                if resp.status_code == 200 and resp.content:
                    doc = pymupdf.open(stream=resp.content, filetype="pdf")
                    extracted = self.extract_title_from_pymupdf(doc)
                    doc.close()
                    if extracted:
                        self.set_title(raw_link, extracted)
                        return extracted
            self._failed_pdf_urls.add(raw_link)
        except Exception as e:
            self._failed_pdf_urls.add(raw_link)
            logger.debug(f"Failed to on-demand extract PDF title for {raw_link}: {e}")
        return None

    async def resolve_pdf_async(self, pdf: dict, chunk_topic_name: str = "") -> dict:
        """Asynchronously enrich a PDF dictionary with its authentic document title without fallbacks."""
        if not isinstance(pdf, dict):
            return pdf

        pdf_copy = dict(pdf)
        raw_link = pdf_copy.get("Link") or pdf_copy.get("link") or pdf_copy.get("Url") or pdf_copy.get("url") or ""
        pdf_copy["link"] = raw_link

        # Priority 1: Already has a non-empty, authentic Title in DB
        existing_title = (pdf_copy.get("title") or pdf_copy.get("Title") or "").strip()
        if existing_title and existing_title.lower() not in ("reference document", "document", "untitled", "pdf"):
            self.set_title(raw_link, existing_title)
            pdf_copy["title"] = existing_title
            return pdf_copy

        # Priority 2: Check cached title
        cached_title = self.get_title(raw_link)
        if cached_title and cached_title.lower() not in ("reference document", "document", "untitled", "pdf"):
            pdf_copy["title"] = cached_title
            return pdf_copy

        # Priority 3: Extract actual document title from the PDF document itself (pages 0-2, TOC, metadata)
        if raw_link and raw_link.startswith("http") and raw_link not in self._failed_pdf_urls:
            doc_title = await self.fetch_and_extract_title_async(raw_link)
            if doc_title:
                pdf_copy["title"] = doc_title
                return pdf_copy

        # Priority 4: Check if filename in URL is an actual document name (not a UUID or hash)
        if raw_link:
            try:
                import urllib.parse
                fname = raw_link.split("/")[-1].split("?")[0].replace(".pdf", "")
                if fname and not re.match(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}', fname) and not re.match(r'^[0-9a-fA-F]{20,}', fname):
                    clean_fname = urllib.parse.unquote(fname).replace("_", " ").replace("-", " ").strip()
                    if clean_fname and len(clean_fname) >= 3:
                        self.set_title(raw_link, clean_fname)
                        pdf_copy["title"] = clean_fname
                        return pdf_copy
            except Exception:
                pass

        # Priority 5: Check About field only if it's an authentic document title (not empty or generic)
        about = (pdf_copy.get("About") or pdf_copy.get("about") or "").strip()
        clean_about = re.sub(r"<[^>]+>", "", about).strip()
        if clean_about and clean_about.lower() not in ("reference document", "document", "pdf"):
            if "-" in clean_about:
                parts = [p.strip() for p in clean_about.split("-") if p.strip()]
                candidate = parts[-1] if parts else clean_about
            else:
                candidate = clean_about
            if 3 <= len(candidate) <= 80:
                self.set_title(raw_link, candidate)
                pdf_copy["title"] = candidate
                return pdf_copy

        # WORST CASE SAFETY NET: If the document is purely a scanned image with 0 text across all pages and no metadata
        if chunk_topic_name and len(chunk_topic_name.strip()) > 2:
            clean_topic = chunk_topic_name.strip()
            pdf_copy["title"] = clean_topic
        else:
            pdf_copy["title"] = "Course Document"
        self.set_title(raw_link, pdf_copy["title"])
        return pdf_copy

    def resolve_pdf(self, pdf: dict, chunk_topic_name: str = "") -> dict:
        """Enrich a PDF dictionary with its authentic document title without fallbacks."""
        if not isinstance(pdf, dict):
            return pdf

        pdf_copy = dict(pdf)
        raw_link = pdf_copy.get("Link") or pdf_copy.get("link") or pdf_copy.get("Url") or pdf_copy.get("url") or ""
        pdf_copy["link"] = raw_link

        # Priority 1: Already has a non-empty, authentic Title in DB
        existing_title = (pdf_copy.get("title") or pdf_copy.get("Title") or "").strip()
        if existing_title and existing_title.lower() not in ("reference document", "document", "untitled", "pdf"):
            self.set_title(raw_link, existing_title)
            pdf_copy["title"] = existing_title
            return pdf_copy

        # Priority 2: Check cached title
        cached_title = self.get_title(raw_link)
        if cached_title and cached_title.lower() not in ("reference document", "document", "untitled", "pdf"):
            pdf_copy["title"] = cached_title
            return pdf_copy

        # Priority 3: Check if filename in URL is an actual document name (not a UUID or hash)
        if raw_link:
            try:
                import urllib.parse
                fname = raw_link.split("/")[-1].split("?")[0].replace(".pdf", "")
                if fname and not re.match(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}', fname) and not re.match(r'^[0-9a-fA-F]{20,}', fname):
                    clean_fname = urllib.parse.unquote(fname).replace("_", " ").replace("-", " ").strip()
                    if clean_fname and len(clean_fname) >= 3:
                        self.set_title(raw_link, clean_fname)
                        pdf_copy["title"] = clean_fname
                        return pdf_copy
            except Exception:
                pass

        # Priority 5: Check About field only if it's an authentic document title (not empty or generic)
        about = (pdf_copy.get("About") or pdf_copy.get("about") or "").strip()
        clean_about = re.sub(r"<[^>]+>", "", about).strip()
        if clean_about and clean_about.lower() not in ("reference document", "document", "pdf"):
            if "-" in clean_about:
                parts = [p.strip() for p in clean_about.split("-") if p.strip()]
                candidate = parts[-1] if parts else clean_about
            else:
                candidate = clean_about
            if 3 <= len(candidate) <= 80:
                self.set_title(raw_link, candidate)
                pdf_copy["title"] = candidate
                return pdf_copy

        # WORST CASE SAFETY NET: If the document is purely a scanned image with 0 text across all pages and no metadata:
        # Transparently label it so the document remains visible and clickable without pretending to be a fake title
        if chunk_topic_name and len(chunk_topic_name.strip()) > 2:
            clean_topic = chunk_topic_name.strip()
            pdf_copy["title"] = clean_topic
        else:
            pdf_copy["title"] = "Course Document"
        return pdf_copy

    def deduplicate_titles(self, pdfs: List[dict]) -> List[dict]:
        """Ensure duplicate PDFs (by normalized title, link, or filename) are removed,
        keeping only the first unique, authentic occurrence.
        """
        if not pdfs:
            return pdfs

        seen_titles = set()
        seen_links = set()
        result = []
        for pdf in pdfs:
            if not isinstance(pdf, dict):
                continue

            pdf_copy = dict(pdf)
            raw_link = (pdf_copy.get("link") or pdf_copy.get("Link") or pdf_copy.get("url") or pdf_copy.get("Url") or "").strip()
            clean_link = raw_link.lower().split("?")[0].rstrip("/")
            if clean_link and clean_link in seen_links:
                continue

            title = (pdf_copy.get("title") or pdf_copy.get("Title") or "").strip()
            # Strip sequential numbers (e.g. " (1)", " (2)") or legacy "(Document)"
            clean_title = re.sub(r'\s*\(\d+\)$', '', title).strip()
            if clean_title.endswith(" (Document)"):
                clean_title = clean_title[:-len(" (Document)")].strip()

            # Normalize title to alphanumeric key to catch slight differences
            norm_title = re.sub(r'[^a-zA-Z0-9]', '', clean_title).lower()
            if norm_title and norm_title in seen_titles:
                continue

            if clean_link:
                seen_links.add(clean_link)
            if norm_title:
                seen_titles.add(norm_title)

            pdf_copy["title"] = clean_title
            result.append(pdf_copy)

        return result


# Global singleton instance
pdf_service = PdfService()
