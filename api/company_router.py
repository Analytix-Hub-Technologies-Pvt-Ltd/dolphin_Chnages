from __future__ import annotations


from asyncpg import Pool
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from api.dependencies import get_company_store, get_db_pool, get_openai_service, get_faiss_store
from models.company_model import (
    CompanyDocumentUploadResponse,
    CompanyDocumentListResponse,
    CompanyDocumentDeleteResponse
)
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


@router.get(
    "/documents",
    response_model=CompanyDocumentListResponse,
)
async def list_company_documents(
    pool: Pool = Depends(get_db_pool),
) -> CompanyDocumentListResponse:
    """Retrieve all uploaded documents."""
    service = CompanyDocumentService(pool)
    documents = await service.get_all_documents()
    return CompanyDocumentListResponse(documents=documents)

@router.delete(
    "/documents/{document_id}",
    response_model=CompanyDocumentDeleteResponse,
)
async def delete_company_document(
    document_id: int,
    pool: Pool = Depends(get_db_pool),
) -> CompanyDocumentDeleteResponse:
    """Soft delete a company document."""
    service = CompanyDocumentService(pool)
    deleted = await service.delete_document(document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Document with ID {document_id} not found")
    
    return CompanyDocumentDeleteResponse(message="Document deleted successfully", document_id=document_id)

@router.post("/check-gaps")
async def check_document_gaps(
    file: UploadFile = File(..., description="Document (.pdf, .docx, .txt, .xlsx, .csv) to check for gaps"),
    stream: bool = False,
    core_store = Depends(get_faiss_store),
    openai_service = Depends(get_openai_service),
):
    """Analyze uploaded document against industry standards for gaps without saving it to database or vector index."""
    import json
    import re
    from loguru import logger
    from fastapi.responses import StreamingResponse

    try:
        content = await extract_document_text(file)
    except DocumentExtractionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        await file.close()

    # Heuristic helper to extract paragraphs from the document for a given topic
    def extract_relevant_context(doc_text: str, topic_name: str, max_chars: int = 8000) -> str:
        # Clean topic and split into key search terms
        clean_name = re.sub(r'[^\w\s]', ' ', topic_name)
        terms = [t.strip() for t in clean_name.replace("and", "").replace("or", "").split() if len(t.strip()) > 3]
        if not terms:
            terms = [topic_name]
            
        matches = []
        doc_lower = doc_text.lower()
        
        # 1. Search for exact phrase matches
        phrase = topic_name.lower()
        start = 0
        while True:
            idx = doc_lower.find(phrase, start)
            if idx == -1:
                break
            matches.append((idx, len(phrase) * 2))
            start = idx + len(phrase)
            if len(matches) >= 3:
                break
                
        # 2. Search for individual terms
        for term in terms[:3]:
            term_lower = term.lower()
            start = 0
            while True:
                idx = doc_lower.find(term_lower, start)
                if idx == -1:
                    break
                matches.append((idx, len(term_lower)))
                start = idx + len(term_lower)
                if len(matches) >= 6:
                    break
                        
        # Sort matches by index
        matches = sorted(matches, key=lambda x: x[0])
        
        # Merge overlapping ranges and extract text blocks
        blocks = []
        extracted_chars = 0
        
        for idx, _ in matches:
            if extracted_chars >= max_chars:
                break
            # Take 3000 characters before and after the match
            start_pos = max(0, idx - 1500)
            end_pos = min(len(doc_text), idx + 2500)
            
            # Adjust to paragraph boundaries
            p_start = doc_text.rfind("\n", start_pos, idx)
            if p_start != -1:
                start_pos = p_start + 1
            p_end = doc_text.find("\n", idx, end_pos)
            if p_end != -1:
                end_pos = p_end
                
            block_text = doc_text[start_pos:end_pos].strip()
            if block_text and block_text not in blocks:
                blocks.append(f"... {block_text} ...")
                extracted_chars += len(block_text)
                
        return "\n\n---\n\n".join(blocks)

    # 1. Sample the entire document evenly to build a comprehensive outline (up to 25 samples of 4000 chars)
    total_len = len(content)
    num_samples = 25
    sample_size = 4000
    step = total_len // num_samples if total_len > num_samples * sample_size else sample_size
    
    samples = []
    for i in range(num_samples):
        start_idx = i * step
        if start_idx + sample_size < total_len:
            samples.append(content[start_idx : start_idx + sample_size])
        else:
            samples.append(content[start_idx:])
            break
            
    sampled_outline = "\n\n---\n\n".join(samples)

    # 2. Extract topics from the outline using a lightweight prompt
    extract_prompt = f"""Analyze the following sampled sections from a company document (filename: {file.filename}) and identify 15-20 actual, specific operational procedures, safety checks, or checklist sections described in the text (for example: specific cargo loading sequences, tank cleaning protocols, bunkering procedures, gas detection guidelines, enclosed space entry steps, engine room emergencies, etc.). 
    Focus on the actual, granular procedures present in the document. Do NOT return generic headings like "Safety Management System" or "Cargo Operations".
    
    Respond ONLY with a JSON list of strings representing these specific topics. Example: ["Venting Procedures", "Enclosed Space Entry Checklist"]. Do not include markdown formatting or any explanation.
    
    SAMPLED DOCUMENT CONTENT:
    {sampled_outline}
    """
    
    topics = []
    try:
        extract_response = await openai_service.chat(
            [{"role": "user", "content": extract_prompt}],
            temperature=0.0,
            category="TOPIC_EXTRACTION"
        )
        # Parse the JSON response
        cleaned_json = extract_response.strip()
        if cleaned_json.startswith("```json"):
            cleaned_json = cleaned_json[7:]
        if cleaned_json.endswith("```"):
            cleaned_json = cleaned_json[:-3]
        topics = json.loads(cleaned_json.strip())
        if not isinstance(topics, list):
            topics = []
    except Exception as e:
        logger.error(f"Failed to extract topics: {e}")

    # 3. For each topic, perform standards search and company text substring extraction
    synthesized_context_blocks = []
    
    for t in topics[:20]:  # Cap at 20 topics to ensure response fits output token limits
        # Search international standards
        core_chunks = []
        try:
            core_chunks = await core_store.search_with_embeddings(t, k=2)
        except Exception as e:
            logger.error(f"Failed searching standards for topic {t}: {e}")
            
        standards_text = "\n".join(
            f"- {c.get('topic_name', 'Maritime Standard')}: {c.get('content', '')}"
            for c in core_chunks
        )
        
        # Substring search in company document content
        company_text = extract_relevant_context(content, t, max_chars=6000)
        
        synthesized_context_blocks.append(
            f"""### Topic: {t}
---
[INDUSTRY STANDARD REQUIREMENTS]
{standards_text or "General Maritime Industry Standards (SOLAS / MARPOL / STCW / ISM Code)"}

[COMPANY DOCUMENT PROCEDURES]
{company_text or "No specific procedures found for this topic in the company document."}
"""
        )
        
    synthesized_context = "\n\n=========================================\n\n".join(synthesized_context_blocks)

    # Prepare prompt for LLM gap analysis
    prompt = f"""You are Marine Tutor AI, a Senior Marine Compliance Auditor, Maritime Safety Management Specialist, and Maritime Documentation Analyst.

You have been provided with synthesized topic-specific contexts comparing the uploaded company document and the international maritime standards (SOLAS, MARPOL, STCW, ISM Code).

UPLOADED DOCUMENT FILENAME: {file.filename}

TOPIC COMPARISON CONTEXTS:
{synthesized_context}

TASK:
Perform a comprehensive and detailed gap analysis between the uploaded Company Document and the International/Industry Maritime Standards for ALL topics listed in the contexts above.
Your objective is to produce a COMPLETE Marine Document Gap Analysis in ONE SINGLE RESPONSE. DO NOT USE BATCHES. Do NOT output "BATCH X OF Y" or "CONTINUE TO NEXT BATCH".

Structure your response to strictly follow the sections below in order:

---

# Detailed Gap Analysis

For each topic listed in the context, analyze it in detail using the following structure:

## Topic: [Topic Name]

**Compliance Status:** [Status (Compliant / Partially Compliant / Minor Gap / Major Gap / Critical Gap / Not Addressed / Not Applicable / Applicability Requires Confirmation)]

### Current Coverage
In 2–3 concise sentences, explain what the document currently contains. Mention only relevant items (e.g. procedures, responsibilities, operational steps, controls, records).

### Applicable Requirement
In 1–2 concise sentences, identify the applicable marine regulation, code, standard, or company requirement (e.g. SOLAS, MARPOL, ISM Code, STCW, MLC, COLREG, etc.). Do not invent regulation numbers or clauses. If applicability cannot be confirmed, state: "Applicability Requires Confirmation."

### Gap Analysis

**Gap 1 – [Specific Gap Name]**
* **Requirement:** [What is expected]
* **Evidence:** [What the document currently states]
* **Gap:** [Exact deficiency]
* **Risk:** [Specific consequence]
* **Corrective Action:** [Specific action]
* **Severity:** [Critical / Major / Minor]
* **Priority:** [High / Medium / Low]

(Repeat for additional material gaps if applicable, e.g. Gap 2 – ...)

### Existing Controls
One concise sentence describing controls that are already present. If none: "No specific existing control identified."

### Evidence
Strongest relevant evidence (section, heading, paragraph, or quote) from the document. If no relevant evidence exists: "No corresponding provision identified in the provided document."

---

# Final Summary

End with only these exact three sections:

## Critical / Major Gaps
List the most important Critical and Major findings in this format:
**1. [Topic] – [Gap]**
* **Reason:** [Why it is important]
* **Priority:** [Priority]

If there are no Critical/Major findings: "No Critical or Major gaps identified in the analyzed topics."

## Priority Corrective Actions
List the corrective actions that should be performed first (prioritizing critical safety risks first, then major safety/compliance, environmental, regulatory/documentation, and lower-priority improvements) in this format:
**1. [Corrective Action]**
* **Topic:** [Topic]
* **Reason:** [Reason]
* **Priority:** [Priority]

## Overall Status
Provide:
**Topics Analyzed:** [Number]

**Compliance Summary:**
* Compliant: [Number]
* Partially Compliant: [Number]
* Minor Gap: [Number]
* Major Gap: [Number]
* Critical Gap: [Number]
* Not Addressed: [Number]
* Not Applicable: [Number]

**Overall Assessment:**
[2–4 concise sentences.]

**Main Attention Areas:**
* [Area 1]
* [Area 2]
* [Area 3]

---

IMPORTANT RULES & GUIDELINES:
1. Do NOT save this document to any database or vector store.
2. Analyze ONLY requested topics. Do not expand the scope automatically.
3. Optimize the wording to fit within the output limit (3,500–4,000 tokens). Do not output "CONTINUE TO NEXT BATCH" or use batches.
4. Do not invent page numbers, regulations, or assume procedures exist when not shown.
5. Identify specific deficiencies (e.g. define exact missing elements, responsibilities, or inspection frequencies) rather than generic weaknesses.
"""

    if stream:
        async def stream_response():
            try:
                async for token in openai_service.stream_chat(
                    [{"role": "user", "content": prompt}],
                    temperature=0.0,
                    max_tokens=5000,
                ):
                    payload_data = {
                        "type": "content",
                        "token": token
                    }
                    yield f"data: {json.dumps(payload_data)}\n\n"
            except Exception as e:
                logger.exception(f"Streaming gap analysis failed: {e}")
                error_payload = {
                    "type": "error",
                    "message": str(e)
                }
                yield f"data: {json.dumps(error_payload)}\n\n"

        return StreamingResponse(
            stream_response(),
            media_type="text/event-stream",
            headers={
                "X-Accel-Buffering": "no",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Encoding": "identity",
            }
        )

    try:
        answer = await openai_service.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=5000,
        )
        return {
            "filename": file.filename,
            "gap_analysis": answer,
        }
    except Exception as e:
        logger.exception(f"Gap analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Gap analysis failed: {str(e)}")



