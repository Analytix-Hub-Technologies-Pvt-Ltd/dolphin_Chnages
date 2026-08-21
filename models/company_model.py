from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CompanyDocument(BaseModel):
    document_id: int
    company_id: str | None = None
    document_title: str
    document_content: str
    content_length: int
    is_active: bool | None = True
    created_at: datetime


class CompanyDocumentUploadResponse(BaseModel):

    company_id: str
    documents: list[CompanyDocument]
    
class CompanyDocumentStoreRequest(BaseModel):
    company_id: str
    documents: list[tuple[str, str | None, str]]  # (title, content_type, content)

class CompanyDocumentListResponse(BaseModel):
    documents: list[CompanyDocument]

class CompanyDocumentDeleteResponse(BaseModel):
    message: str
    document_id: int
