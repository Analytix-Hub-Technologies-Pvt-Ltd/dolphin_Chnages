from langchain_text_splitters import RecursiveCharacterTextSplitter

from retrieval.faiss_store import FAISSStore
from services.embedding_service import EmbeddingService
from services.openai_service import OpenAIService
from retrieval.refresh_chunks import _generate_embeddings_batch
from services.embedding_config import (
    EMBEDDING_BATCH_SIZE,
    BATCH_DELAY,
)


def classify_document_type(title: str = "", content: str = "") -> str:
    """Classify company SMS/QMS documents into structured categories."""
    combined = f"{title} {content[:500]}".lower()
    if any(k in combined for k in ["checklist", "check list", "check-list", "pre-arrival", "pre arrival"]):
        return "Checklist"
    if any(k in combined for k in ["procedure", "sop", "standard operating procedure", "protocol"]):
        return "Procedure"
    if any(k in combined for k in ["policy", "company policy", "safety policy", "environmental policy"]):
        return "Policy"
    if any(k in combined for k in ["risk register", "risk assessment", "hazard identification", "jha", "ra"]):
        return "Risk Register"
    if any(k in combined for k in ["form", "record", "permit to work", "ptw", "log", "report"]):
        return "Record/Form"
    if any(k in combined for k in ["process", "workflow", "management of change", "moc"]):
        return "Process"
    return "Guidance"


class CompanyDocumentStore:
    
    def __init__(self, store: FAISSStore) -> None:
        self.store = store
        self.embedder = EmbeddingService(OpenAIService())
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
        )

    async def add_documents(self,company_id: str,documents: list) -> None:

        all_chunks = []
        all_metadata = []

        for doc in documents:
            doc_type = classify_document_type(doc.document_title or "", doc.document_content or "")
            chunks = self.splitter.split_text(doc.document_content)

            for idx, chunk in enumerate(chunks):

                all_chunks.append(chunk)

                all_metadata.append(
                    {
                        "source": "company_document",
                        "company_id": company_id,
                        "document_id": doc.document_id,
                        "document_title": doc.document_title,
                        "doc_type": doc_type,
                        "chunk_index": idx,
                        "content": chunk,
                    }
                )

        embeddings = await _generate_embeddings_batch(
            texts=all_chunks,
            embedder=self.embedder,
            batch_size=EMBEDDING_BATCH_SIZE,
            delay_between_batches=BATCH_DELAY,
        )
        
        if not self.store.is_loaded:
            self.store.load()

        self.store.add_embeddings(
            embeddings,
            all_metadata,
        )

        self.store.save()