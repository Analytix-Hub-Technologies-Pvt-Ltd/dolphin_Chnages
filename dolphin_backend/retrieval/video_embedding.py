from langchain_text_splitters import RecursiveCharacterTextSplitter
from loguru import logger
from retrieval.faiss_store import FAISSStore
from services.embedding_service import EmbeddingService
from services.openai_service import OpenAIService
from retrieval.refresh_chunks import _generate_embeddings_batch
from services.embedding_config import (
    EMBEDDING_BATCH_SIZE,
    BATCH_DELAY,
)


class VideoTranscriptStore:

    def __init__(self, store: FAISSStore) -> None:
        self.store = store
        self.embedder = EmbeddingService(OpenAIService())
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
        )

    async def add_transcripts(self, transcripts: list[dict]) -> None:
        """
        Store one or more video transcripts in the FAISS index, one video at
        a time in the source data, but chunked into multiple vectors like
        company documents (so long transcripts stay searchable at a useful
        granularity).

        Each item in `transcripts` should be a dict with:
            course_code, topic_code, video_id, video_link, transcript_text
        """

        logger.info("=" * 60)
        logger.info(f"Starting transcript processing for {len(transcripts)} video(s)")
        logger.info("=" * 60)

        all_chunks = []
        all_metadata = []

        for item in transcripts:
            course_code = item["course_code"]
            topic_code = item["topic_code"]
            video_id = item["video_id"]
            video_link = item["video_link"]
            video_title = item["video_title"]
            video_duration = item["video_duration"]
            video_thumbnail = item["video_thumbnail"]
            transcript_text = item["transcript_text"]

            chunks = self.splitter.split_text(transcript_text)

            for idx, chunk in enumerate(chunks):

                all_chunks.append(chunk)

                all_metadata.append(
                    {
                        "source": "video_transcript",
                        "course_code": course_code,
                        "topic_code": topic_code,
                        "video_id": video_id,
                        "video_link": video_link,
                        "video_title": video_title,
                        "video_duration": video_duration,
                        "video_thumbnail": video_thumbnail,
                        "chunk_index": idx,
                        "content": chunk,
                    }
                )

        if not all_chunks:
            logger.info(" No chunks to embed, skipping.")
            return

        logger.info(f" Total chunks created: {len(all_chunks)}")
        logger.info(" Starting embedding generation...")

        embeddings = await _generate_embeddings_batch(
            texts=all_chunks,
            embedder=self.embedder,
            batch_size=EMBEDDING_BATCH_SIZE,
            delay_between_batches=BATCH_DELAY,
        )

        logger.info(f" Received {len(embeddings)} embeddings")

        if not self.store.is_loaded:
            self.store.load()

        logger.info(" Adding embeddings to FAISS index...")
        self.store.add_embeddings(embeddings, all_metadata)

        logger.info(" Saving FAISS index to disk...")
        self.store.save()

        logger.success(f" Successfully added {len(transcripts)} video transcript(s)")