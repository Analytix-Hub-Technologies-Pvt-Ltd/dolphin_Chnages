from loguru import logger
import asyncio
import json
import asyncpg
import warnings
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
from fastapi import HTTPException

from typing import Any
from asyncpg import Pool
from models.database import get_pool
from models.transcribe_models import BatchTranscriptionResponse, BatchTranscriptionResult, TranscribeRequest, VideoInfoRequest
from retrieval.video_embedding import VideoTranscriptStore

def html_to_text(html_content: str) -> str:
    """Strip HTML tags/entities from About content, returning clean plain text."""
    if not html_content:
        return ""

    if "<" not in html_content:
        return " ".join(html_content.split()).strip()

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)
        soup = BeautifulSoup(html_content, "html.parser")
        text = soup.get_text(separator=" ")
        text = " ".join(text.split())
        return text.strip()


class VideoTranscribeService:
    
    def __init__(self, pool: Pool, video_transcribe_store: VideoTranscriptStore) -> None:
            self.pool = pool
            self.video_transcribe_store = video_transcribe_store
            
    async def get_course_list(self, request:TranscribeRequest) -> list[dict[str, Any]]:
        """
        Fetch course_code, topic_code, and video id/url/about pairs from course_content,
        paginated with offset/limit.
        """
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT course_code, topic_code, topic_video
                    FROM course_content
                    ORDER BY content_id
                    OFFSET $1 LIMIT $2
                    """,
                    request.offset, request.limit,
                    timeout=120.0,
                )
        except (asyncio.TimeoutError, TimeoutError) as e:
            raise HTTPException(
                status_code=504,
                detail="Database query timed out while fetching course content. Please try reducing limit or offset."
            )
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(
                status_code=500,
                detail=f"Database error while fetching course content: {str(e)}"
            )
    
        results: list[dict[str, Any]] = []
    
        for row in rows:
            topic_video = row["topic_video"]
    
            # asyncpg may return JSONB as a str depending on codec setup, handle both
            if isinstance(topic_video, str):
                try:
                    topic_video = json.loads(topic_video)
                except (json.JSONDecodeError, TypeError):
                    topic_video = []
    
            if not isinstance(topic_video, list):
                topic_video = []
    
            # videos = [
            #     {
            #         "id": video.get("Id"),
            #         "url": video.get("Url"),
            #         "about": video.get("About"),
            #     }
            #     for video in topic_video
            #     if isinstance(video, dict)
            # ]

            videos = [
                {
                    "id": video.get("Id"),
                    "url": video.get("Url"),
                    "about": video.get("About"),
                    "duration":video.get("Duration"),
                    "title": video.get("Title"),
                    "thumbnail":video.get("Thumbnail"),
                    "caption": video.get("Caption")
                }
                for video in topic_video
                if isinstance(video, dict)
            ]
    
            results.append({
                "course_code": row["course_code"],
                "topic_code": row["topic_code"],
                "videos": videos,
            })
    
        return results
    
    async def _insert_transcript(
        self,
        course_code: str,
        topic_code: str,
        video_id: str,
        video_link: str,
        video_title: str,
        video_duration: str,
        video_thumbnail: str,
        transcription_content: str,
        status: str,
        error_message: str | None = None,
    ) -> asyncpg.Record:

        pool = await get_pool()
        async with pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT transcribe_id FROM transcribe WHERE video_id = $1",
                video_id,
            )
            if existing:
                row = await conn.fetchrow(
                    """
                    UPDATE transcribe
                    SET course_code = $1,
                        topic_code = $2,
                        video_link = $4,
                        video_title = $5,
                        video_duration = $6,
                        video_thumbnail = $7,
                        transcription_content = $8,
                        status = $9,
                        error_message = $10,
                        updated_at = now()
                    WHERE video_id = $3
                    RETURNING *
                    """,
                    course_code, topic_code, video_id, video_link, video_title, video_duration, video_thumbnail, transcription_content, status, error_message,
                )
            else:
                row = await conn.fetchrow(
                    """
                    INSERT INTO transcribe (course_code, topic_code, video_id, video_link,
                                            video_title, video_duration, video_thumbnail,
                                            transcription_content, status, error_message, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7,
                            $8, $9, $10, now())
                    RETURNING *
                    """,
                    course_code, topic_code, video_id, video_link, video_title, video_duration, video_thumbnail, transcription_content, status, error_message,
                )
        return row
        
    async def video_transcribe(self, request: TranscribeRequest) -> BatchTranscriptionResponse:
        """
        Fetch a page of course_content, pull each video's 'About' HTML,
        convert it to plain text, store it in the video_about table, and
        embed the cleaned text in FAISS. No download/transcription needed —
        the raw content is already sitting in the JSON, it just needs
        cleaning up first.
        """
        # if request.limit < 1 or request.limit > 100:
        #     raise HTTPException(status_code=400, detail="limit must be between 1 and 100")
 
        if request.offset < 0:
            raise HTTPException(status_code=400, detail="offset must be >= 0")
 
        courses = await self.get_course_list(request)
        items: list[dict[str, Any]] = []
        summary: list[dict[str, Any]] = []

        total_videos = sum(len(c.get("videos", [])) for c in courses)
        current_index = 0

        logger.info("Starting video transcription batch for {} video item(s)", total_videos)

        for course in courses:
            course_code = course["course_code"]
            topic_code = course["topic_code"]

            for video in course["videos"]:
                current_index += 1
                video_id = video.get("id")
                video_link = video.get("url")
                about_html = video.get("about")
                video_title = video.get("title")
                video_duration = video.get("duration")
                video_thumbnail = video.get("thumbnail")

                logger.info(
                    "Processing item {}/{} | course_code={} topic_code={} video_id={}",
                    current_index, total_videos, course_code, topic_code, video_id,
                )

                if not video_id:
                    logger.warning(
                        "[{}/{}] Skipped video in course_code={} topic_code={}: missing video id",
                        current_index, total_videos, course_code, topic_code,
                    )
                    summary.append({
                        "course_code": course_code,
                        "topic_code": topic_code,
                        "video_id": video_id,
                        "status": "skipped",
                        "error_message": "Missing video id",
                    })
                    continue

                transcription_text = html_to_text(about_html)

                try:
                    await self._insert_transcript(
                        course_code, topic_code, video_id, video_link,
                        video_title, video_duration, video_thumbnail,
                        transcription_content=transcription_text, status="completed",
                    )
                    logger.info(
                        "[{}/{}] Inserted transcript for course_code={} topic_code={} video_id={}",
                        current_index, total_videos, course_code, topic_code, video_id,
                    )
                    items.append({
                        "course_code": course_code,
                        "topic_code": topic_code,
                        "video_id": video_id,
                        "video_link": video_link,
                        "video_title": video_title,
                        "video_duration": video_duration,
                        "video_thumbnail": video_thumbnail,
                        "transcript_text": transcription_text,
                    })
                    summary.append({
                        "course_code": course_code,
                        "topic_code": topic_code,
                        "video_id": video_id,
                        "status": "completed",
                    })

                except Exception as e:
                    logger.error(
                        "[{}/{}] Failed to insert transcript for course_code={} topic_code={} video_id={}: {}",
                        current_index, total_videos, course_code, topic_code, video_id, str(e),
                    )
                    await self._insert_transcript(
                        course_code, topic_code, video_id, video_link,
                        video_title, video_duration, video_thumbnail,
                        transcription_content=None, status="failed", error_message=str(e),
                    )
                    summary.append({
                        "course_code": course_code,
                        "topic_code": topic_code,
                        "video_id": video_id,
                        "status": "failed",
                        "error_message": str(e),
                    })
 
        if items:
            await self.video_transcribe_store.add_transcripts(items)
            logger.info("Stored {} transcript(s) in vector store", len(items))
        
        logger.info(
            "video_transcribe finished: offset={} limit={} total={} completed={} skipped={} failed={}",
            request.offset, request.limit, len(summary),
            sum(1 for s in summary if s["status"] == "completed"),
            sum(1 for s in summary if s["status"] == "skipped"),
            sum(1 for s in summary if s["status"] == "failed"),
        )
 
        return BatchTranscriptionResponse(
                    offset=request.offset, 
                    limit=request.limit, 
                    results=[BatchTranscriptionResult.model_validate(item) for item in summary]
                )