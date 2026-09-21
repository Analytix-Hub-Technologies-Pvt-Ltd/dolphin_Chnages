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
