from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger
import numpy as np
from models.database import get_pool
from services.embedding_service import EmbeddingService
from services.openai_service import OpenAIService
from retrieval.faiss_store import FAISSStore

from course_sync.external_api_client import ExternalAPIClient
from course_sync.course_sync_service import CourseSyncService
from config import settings
from datetime import datetime, timedelta

class SchedulerService:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
    
    async def scheduled_faiss_rebuild(self):
        """Scheduled FAISS index rebuild from tutor_content table"""
        try:
            logger.info("🕒 Starting scheduled FAISS rebuild...")
            
            # Get tutor_content from database
            pool = await get_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT id, title, section, content_text, videourl FROM tutor_content ORDER BY id"
                )
            
            if not rows:
                logger.warning("No tutor_content found for FAISS rebuild")
                return
            
            # Initialize services
            openai_service = OpenAIService()
            embedding_service = EmbeddingService(openai_service)
            
            # Prepare documents and metadata
            documents = []
            metadatas = []
            
            for row in rows:
                # Combine title, section, and content for embedding
                doc_text = f"{row['title']} {row['section']} {row['content_text']}"
                documents.append(doc_text)
                
                metadatas.append({
                    "id": row["id"],
                    "title": row["title"],
                    "section": row["section"],
                    "content_text": row["content_text"],
                    "videourl": row["videourl"]
                })
            
            # Generate embeddings
            logger.info(f"Generating embeddings for {len(documents)} documents...")
            embeddings_list = await embedding_service.embed_documents(documents)
            embeddings_array = np.array(embeddings_list, dtype="float32")
            
            # Rebuild FAISS index
            faiss_store = FAISSStore()
            faiss_store.build_from_embeddings(embeddings_array, metadatas)
            faiss_store.save()
            
            logger.info(f"🎉 FAISS rebuild completed: {len(documents)} documents indexed")
            
        except Exception as e:
            logger.error(f"❌ FAISS rebuild failed: {e}")
    
    async def scheduled_course_sync(self):
        """Scheduled course sync at 6 PM"""
        try:
            logger.info("🕕 Starting scheduled course sync...")
            

            
            # Use yesterday's date for sync
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            
            api_client = ExternalAPIClient(
                api_key=settings.external_api_key,
                base_url=settings.external_api_base_url
            )
            sync_service = CourseSyncService(api_client)
            
            result = await sync_service.run_full_sync(yesterday)
            await api_client.close()
            
            logger.info(f"🎉 Scheduled sync completed: {result}")
            
        except Exception as e:
            logger.error(f"❌ Scheduled sync failed: {e}")
    
    def start_scheduler(self):
        """Start the scheduler with daily jobs"""
        from config import settings
        
        # Daily FAISS rebuild at 3:00 AM
        self.scheduler.add_job(
            self.scheduled_faiss_rebuild,
            'cron',
            hour=3,
            minute=0,
            timezone=settings.scheduler_timezone,
            id='daily_faiss_rebuild'
        )
        
        # Daily course sync at 6:00 PM
        self.scheduler.add_job(
            self.scheduled_course_sync,
            'cron',
            hour=6,
            minute=0,
            timezone=settings.scheduler_timezone,
            id='daily_course_sync'
        )
        
        self.scheduler.start()
        logger.info(f"⏰ Scheduler started - FAISS rebuild at 3:00 AM, Course sync at 6:00 PM {settings.scheduler_timezone}")
    
    def stop_scheduler(self):
        """Stop the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("🛑 FAISS rebuild scheduler stopped")