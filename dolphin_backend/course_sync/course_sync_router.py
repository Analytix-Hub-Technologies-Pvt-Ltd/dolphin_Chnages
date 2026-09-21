from fastapi import APIRouter, HTTPException, File, Form, Depends, UploadFile
from pydantic import BaseModel
from typing import Optional, List
from models.database import get_pool
from course_sync.course_sync_service import CourseSyncService
from course_sync.external_api_client import ExternalAPIClient
from config import settings
from loguru import logger

router = APIRouter(prefix="/sync", tags=["course-sync"])

class CourseSyncRequest(BaseModel):
    UpdatedAfter:Optional[str] = None
    Changed: Optional[int] = None
    Offset: Optional[int]=None
    Limit: Optional[int]=None

class RetryCoursesRequest(BaseModel):
    course_codes: List[str]

@router.post("/courses")
async def sync_courses(request: Optional[CourseSyncRequest] = None):
    updated_after = None
    changed = None
    
    if request:
        updated_after = request.UpdatedAfter
        changed = request.Changed
    
    logger.info(f"Starting course sync with UpdatedAfter: {updated_after}, Changed: {changed}")
    
    try:
        api_client = ExternalAPIClient(
            api_key=settings.external_api_key,
            base_url=settings.external_api_base_url
        )
        sync_service = CourseSyncService(api_client)
        
        result = await sync_service.run_full_sync(updated_after, changed)
        
        await api_client.close()
        logger.info(f"Sync completed: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Sync error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/delete")
async def delete_courses():
    """Delete courses that no longer exist in external API"""
    logger.info("Starting course deletion sync...")
    
    try:
        api_client = ExternalAPIClient(
            api_key=settings.external_api_key,
            base_url=settings.external_api_base_url
        )
        sync_service = CourseSyncService(api_client)
        
        result = await sync_service.run_delete_sync()
        
        await api_client.close()
        logger.info(f"Delete sync completed: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Delete sync error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/retry")
async def retry_failed_courses(request: RetryCoursesRequest):
    
    try:
        api_client = ExternalAPIClient(
            api_key=settings.external_api_key,
            base_url=settings.external_api_base_url
        )
        sync_service = CourseSyncService(api_client)
        
        result = await sync_service.retry_failed_courses(request.course_codes)
        
        await api_client.close()
        logger.info(f"Retry completed: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Retry error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
@router.post("/masterData")
async def sync_master_courses(request: CourseSyncRequest):
    logger.info(f"Starting course sync with UpdatedAfter: {request.UpdatedAfter}, Changed: {request.Changed}")
    
    try:
        api_client = ExternalAPIClient(
            api_key=settings.external_api_key,
            base_url=settings.external_api_base_url
        )
        sync_service = CourseSyncService(api_client)
        
        result = await sync_service.run_full_sync_master(request.UpdatedAfter, request.Changed)
        
        await api_client.close()
        logger.info(f"Sync completed: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Sync error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/masterContent")
async def sync_master_content(request: CourseSyncRequest):
    logger.info(f"Starting course sync with Offset: {request.Offset}, Limit: {request.Limit}")
    
    try:
        api_client = ExternalAPIClient(
            api_key=settings.external_api_key,
            base_url=settings.external_api_base_url
        )

        sync_service = CourseSyncService(api_client)

        result = await sync_service.run_full_sync_content(
            Offset=request.Offset,
            Limit=request.Limit
        )

        await api_client.close()
        return result

    
        
    except Exception as e:
        logger.error(f"Sync error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sync-course-content-excel")
async def sync_course_content_excel(
    start_row: int = Form(...),
    end_row: int = Form(...),
    file: UploadFile = File(...)
):
    logger.info(
        f"Starting Excel content sync | StartRow: {start_row}, EndRow: {end_row}"
    )

    try:
        file_bytes = await file.read()

        # Excel file validation
        if not file.filename.endswith((".xlsx", ".xls")):
            raise HTTPException(
                status_code=400,
                detail="Only Excel files (.xlsx, .xls) are allowed"
            )

        # Create service (API client not required here, but keeping structure consistent)
        api_client = ExternalAPIClient(
            api_key=settings.external_api_key,
            base_url=settings.external_api_base_url
        )

        sync_service = CourseSyncService(api_client)

        pool = await get_pool()

        topics_inserted = await sync_service.sync_course_content_from_excel(
            file_bytes=file_bytes,
            start_row=start_row,
            end_row=end_row,
            pool=pool
        )

        await api_client.close()

        logger.info(f"Excel sync completed. Topics inserted: {topics_inserted}")

        return {
            "status": "success",
            "topics_inserted": topics_inserted
        }

    except Exception as e:
        logger.error(f"Excel sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))