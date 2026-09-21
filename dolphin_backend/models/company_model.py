from __future__ import annotations

from datetime import datetime

from typing import Any

from pydantic import BaseModel


class CompanyDocument(BaseModel):
    document_id: int
    document_title: str
    document_content: str
    content_length: int
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


class CompanyChart(BaseModel):
    chart_id: int
    company_id: str
    img_title: str | None = None
    image_base64: str
    chart_json: dict[str, Any] | list[Any]
    created_at: datetime


class CompanyChartUploadResponse(BaseModel):
    company_id: str
    charts: list[CompanyChart]


