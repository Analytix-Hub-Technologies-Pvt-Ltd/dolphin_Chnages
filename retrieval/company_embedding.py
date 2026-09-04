from langchain_text_splitters import RecursiveCharacterTextSplitter

from retrieval.faiss_store import FAISSStore
from services.embedding_service import EmbeddingService
from services.openai_service import OpenAIService
from retrieval.refresh_chunks import _generate_embeddings_batch
from services.embedding_config import (
    EMBEDDING_BATCH_SIZE,
    BATCH_DELAY,
)


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

            chunks = self.splitter.split_text(doc.document_content)

            for idx, chunk in enumerate(chunks):

                all_chunks.append(chunk)

                all_metadata.append(
                    {
                        "source": "company_document",
                        "company_id": company_id,
                        "document_id": doc.document_id,
                        "document_title": doc.document_title,
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