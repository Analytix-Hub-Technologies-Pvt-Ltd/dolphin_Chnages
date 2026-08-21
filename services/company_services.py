from __future__ import annotations

from typing import Sequence

from asyncpg import Pool
from loguru import logger

from models.company_model import CompanyDocument

class CompanyDocumentService:
    def __init__(self, pool: Pool) -> None:
        self.pool = pool

    async def store_documents(
        self,
        company_id: str,
        documents: Sequence[tuple[str, str | None, str]],
    ) -> list[CompanyDocument]:
        query = """
            INSERT INTO public.company_documents
                (company_id, document_title, document_content, content_type)
            VALUES ($1, $2, $3, $4)
            RETURNING document_id, document_title, document_content,
                      char_length(document_content) AS content_length, created_at
        """
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                rows = [
                    await conn.fetchrow(query, company_id, title, content, content_type)
                    for title, content_type, content in documents
                ]
                logger.info(f"Stored {len(rows)} documents for company_id={company_id}")
        return [CompanyDocument(**dict(row)) for row in rows]

    async def get_all_documents(self) -> list[CompanyDocument]:
        query = """
            SELECT document_id, company_id, document_title, document_content,
                   char_length(document_content) AS content_length, created_at, is_active
            FROM public.company_documents
            WHERE is_active = TRUE
            ORDER BY created_at DESC
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query)
            return [CompanyDocument(**dict(row)) for row in rows]

    async def delete_document(self, document_id: int) -> bool:
        query = """
            UPDATE public.company_documents
            SET is_active = FALSE
            WHERE document_id = $1
            RETURNING document_id
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, document_id)
            if row:
                logger.info(f"Soft deleted document_id={document_id}")
                return True
            return False
