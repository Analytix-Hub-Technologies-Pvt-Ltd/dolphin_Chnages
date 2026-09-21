from __future__ import annotations

from collections.abc import Sequence
import json
import os
from typing import Any

from asyncpg import Pool
from fastapi import UploadFile
from loguru import logger

from config import settings
from models.company_model import CompanyChart
from retrieval.faiss_store import COMPANY_INDEX_PATH, COMPANY_META_PATH, FAISSStore
from services.embedding_service import EmbeddingService
from services.json_img_service import (
    crop_image_to_bbox,
    extract_tree_from_image_openai,
    image_to_base64,
    pdf_to_images,
)
from services.openai_service import OpenAIService

# Directory for processing images during extraction

class CompanyChartService:
    def __init__(
        self,
        pool: Pool,
        store: FAISSStore | None = None,
        embedder: EmbeddingService | None = None,
    ) -> None:
        self.pool = pool
        if store is None:
            store = FAISSStore(index_path=COMPANY_INDEX_PATH, meta_path=COMPANY_META_PATH)
        self.store = store
        self.embedder = embedder

    async def init_table(self) -> None:
        """Ensure company_charts database table exists."""
        logger.info("Checking database table 'public.company_charts'...")
        query = """
        CREATE TABLE IF NOT EXISTS public.company_charts (
            chart_id BIGSERIAL PRIMARY KEY,
            company_id TEXT NOT NULL,
            img_title TEXT,
            image_base64 TEXT NOT NULL,
            chart_json JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
        async with self.pool.acquire() as conn:
            await conn.execute(query)
        logger.info("Table 'public.company_charts' is ready.")

    def _get_openai_client(self):
        """
        Build an OpenAI client from env vars / settings. Raises a clear
        error instead of silently skipping if no key is configured.
        """
        from openai import OpenAI

        openai_key = getattr(settings, "openai_api_key2", None) or settings.openai_api_key
        if not openai_key:
            raise ValueError(
                "No OpenAI API key found. Set OPENAI_API_KEY env var or settings.openai_api_key."
            )

        client_kwargs: dict[str, Any] = {"api_key": openai_key}

        return OpenAI(**client_kwargs)

    async def process_and_store_charts(
        self,
        company_id: str,
        files: Sequence[UploadFile],
    ) -> list[CompanyChart]:
        """
        Processes uploaded PDF files using OpenAI vision pipeline directly inside project IMAGES_DIR,
        extracts visual charts, converts to JSON & Base64 images, stores them in PostgreSQL
        company_charts table, and deletes all image & temporary files from disk after DB insertion.
        """
        logger.info(f"Received request to extract charts for company_id='{company_id}' with {len(files)} file(s).")
        await self.init_table()

        try:
            client = self._get_openai_client()
        except ValueError as e:
            logger.error(str(e))
            raise

        model = getattr(settings, "openai_model2", None) or settings.openai_model
        stored_charts: list[CompanyChart] = []

        output_images_dir = "images"
        os.makedirs(output_images_dir, exist_ok=True)

        for file in files:
            filename = file.filename or "uploaded.pdf"
            logger.info(f"Processing PDF file '{filename}' for company '{company_id}'...")

            content = await file.read()
            if not content:
                logger.warning(f"File '{filename}' is empty. Skipping.")
                continue

            pdf_path = os.path.join(output_images_dir, filename)
            with open(pdf_path, "wb") as f:
                f.write(content)

            image_paths: list[str] = []
            try:
                image_paths = pdf_to_images(
                    pdf_path,
                    output_dir=output_images_dir,
                    filename_prefix=f"{company_id}_{os.path.splitext(filename)[0]}"
                )
                logger.info(f"Converted '{filename}' to {len(image_paths)} page image(s) in '{output_images_dir}'.")
            except Exception as exc:
                logger.error(f"Failed to convert PDF '{filename}' to images: {exc}")
                if os.path.exists(pdf_path):
                    try:
                        os.remove(pdf_path)
                    except Exception:
                        pass
                continue

            try:
                for idx, img_path in enumerate(image_paths):
                    page_num = idx + 1
                    logger.info(f"Analyzing page {page_num}/{len(image_paths)} ({img_path}) using OpenAI ('{model}')...")

                    tree = None
                    chart_name = None
                    bounding_box = None
                    try:
                        tree, chart_name, bounding_box = extract_tree_from_image_openai(img_path, client, model=model)
                    except Exception as extract_err:
                        logger.error(f"OpenAI extraction failed on page {page_num} of '{filename}': {extract_err}")

                    if tree is None:
                        logger.info(f"No visual chart/diagram detected on page {page_num} of '{filename}'.")
                        if os.path.exists(img_path):
                            try:
                                os.remove(img_path)
                            except Exception:
                                pass
                        continue

                    if bounding_box:
                        crop_image_to_bbox(img_path, bounding_box)

                    b64_data, media_type = image_to_base64(img_path)
                    image_base64_val = b64_data

                    img_title = chart_name or f"{os.path.splitext(filename)[0]}_page{page_num}"
                    chart_json_str = json.dumps(tree)

                    insert_query = """
                        INSERT INTO public.company_charts (company_id, img_title, image_base64, chart_json)
                        VALUES ($1, $2, $3, $4::jsonb)
                        RETURNING chart_id, company_id, img_title, image_base64, chart_json, created_at
                    """
                    try:
                        async with self.pool.acquire() as conn:
                            row = await conn.fetchrow(insert_query, company_id, img_title, image_base64_val, chart_json_str)
                            if row:
                                row_dict = dict(row)
                                if isinstance(row_dict["chart_json"], str):
                                    row_dict["chart_json"] = json.loads(row_dict["chart_json"])
                                stored_chart = CompanyChart(**row_dict)
                                stored_charts.append(stored_chart)
                                logger.success(
                                    f"Stored chart_id={stored_chart.chart_id}, title='{img_title}' "
                                    f"in database after page {page_num} extraction."
                                )

                                # Also store in company vector DB simultaneously
                                if self.store is not None:
                                    try:
                                        if not self.store.is_loaded:
                                            self.store.load()
                                        if self.embedder is None:
                                            self.embedder = EmbeddingService(OpenAIService())

                                        text_to_embed = f"Company ID: {company_id}\nChart Title: {img_title}\nChart Structure: {chart_json_str}"
                                        embeddings = await self.embedder.embed_documents([text_to_embed])
                                        metadata = {
                                            "source": "company_document",
                                            "company_id": company_id,
                                            "img_title": img_title,
                                            "chart_json": tree,
                                            "chart_id": stored_chart.chart_id,
                                        }
                                        self.store.add_embeddings(embeddings, [metadata])
                                        self.store.save()
                                        logger.success(
                                            f"Stored vector for chart_id={stored_chart.chart_id}, title='{img_title}' "
                                            f"in company vector DB with metadata (company_id, img_title, complete_json)."
                                        )
                                    except Exception as vec_err:
                                        logger.error(f"Failed to insert chart into company vector DB: {vec_err}")
                    except Exception as db_err:
                        logger.error(f"Failed to insert chart for page {page_num} into database: {db_err}")
                    finally:
                        if os.path.exists(img_path):
                            try:
                                os.remove(img_path)
                                logger.info(f"Deleted image file '{img_path}' after storing values in database.")
                            except Exception as del_err:
                                logger.warning(f"Could not delete image file '{img_path}': {del_err}")

            finally:
                if os.path.exists(pdf_path):
                    try:
                        os.remove(pdf_path)
                    except Exception:
                        pass

        logger.success(
            f"Successfully processed files and stored a total of {len(stored_charts)} chart(s) "
            f"in database for company_id='{company_id}'."
        )
        return stored_charts
