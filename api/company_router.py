from __future__ import annotations


from asyncpg import Pool
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from api.dependencies import get_company_store, get_db_pool 
from models.company_model import CompanyDocumentUploadResponse
from retrieval.company_embedding import CompanyDocumentStore
from retrieval.faiss_store import FAISSStore
from services.company_services import CompanyDocumentService
from services.document_extractor import DocumentExtractionError, extract_document_text


router = APIRouter(prefix="/companies", tags=["companies"])


@router.post(
    "/upload",
    response_model=CompanyDocumentUploadResponse,
)
async def upload_company_documents(
    company_id: str = Form(..., description="Company identifier e.g. comp-01 or company name"),
    file: UploadFile | None = File(default=None, description="Select document (.pdf, .docx, .txt, .xlsx, .csv)"),
    files: list[UploadFile] | None = File(default=None, description="Select multiple documents"),
    pool: Pool = Depends(get_db_pool),
    store: FAISSStore = Depends(get_company_store),
) -> CompanyDocumentUploadResponse:
    """Extract uploaded documents and store their text against a company."""
    uploaded_files: list[UploadFile] = []
    if file and file.filename:
        uploaded_files.append(file)
    if files:
        for f in files:
            if f and f.filename:
                uploaded_files.append(f)

    if not uploaded_files:
        raise HTTPException(status_code=400, detail="At least one file must be selected for upload")

    service = CompanyDocumentService(pool)
    documents = []
    for f in uploaded_files:
        try:
            content = await extract_document_text(f)
        except DocumentExtractionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        finally:
            await f.close()

        documents.append((f.filename or "uploaded-file", f.content_type, content))

    stored = await service.store_documents(company_id.strip(), documents)
    embedding_service = CompanyDocumentStore(store)
    
    await embedding_service.add_documents(company_id=company_id.strip(), documents=stored)

    return CompanyDocumentUploadResponse(company_id=company_id.strip(), documents=stored)
