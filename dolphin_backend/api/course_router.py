import asyncio
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from asyncpg import Pool
import requests
from loguru import logger
from api.dependencies import get_db_pool
from core.redis_client import redis_service

COMPANY_COURSES_API_URL = "https://cms.marinerskills.com/api/companycourses"
COMPANY_COURSES_SECURITY_KEY = "FslKvipEQ3hT2PfdZla00hp"

router = APIRouter(prefix="/course", tags=["course"])

class CheckTopicCourseRequest(BaseModel):
    topic_code: Optional[str] = None
    source_code: Optional[str] = None
    user_id: Optional[str] = None

@router.post("/check-topic-course")
async def check_topic_course(
    request: CheckTopicCourseRequest,
    pool: Pool = Depends(get_db_pool)
):
    try:
        resolved_topic_code = (request.topic_code or request.source_code or "").strip()
        if not resolved_topic_code:
            return {
                "matched": False,
                "user_role": "",
                "user_type": "",
                "data": None,
                "message": "Topic code required"
            }

        user_id = str(request.user_id).strip() if request.user_id else None
        user_role = ""
        user_type = ""
        company_courses = []
        company_id = None
        user_data = None

        # 1. Try Redis cache first
        if user_id:
            try:
                user_data = await redis_service.get_user_data(user_id)
                if user_data and isinstance(user_data, dict):
                    user_role = user_data.get("role") or user_data.get("user_role") or ""
                    user_type = user_data.get("user_type") or ""
                    company_courses = user_data.get("company_courses") or []
                    company_id = user_data.get("company_id")
            except Exception as e:
                logger.warning(f"Redis get_user_data error in check_topic_course: {e}")

        # 2. Database fallback if user details or company courses are missing
        if user_id and user_id not in ("anonymous", "guest") and (not user_data or not company_courses):
            try:
                async with pool.acquire() as conn:
                    user_row = await conn.fetchrow(
                        "SELECT id, name, email, role, user_type, company_id, company_name FROM users WHERE id = $1",
                        user_id
                    )
                    if user_row:
                        user_role = user_role or user_row.get("role") or ""
                        user_type = user_type or user_row.get("user_type") or ""
                        company_id = company_id or user_row.get("company_id")

                        # Resolve company_id by company_name if missing
                        if not company_id and user_row.get("company_name"):
                            cid_row = await conn.fetchrow(
                                "SELECT company_id FROM users WHERE LOWER(company_name) = LOWER($1) AND company_id IS NOT NULL LIMIT 1",
                                user_row["company_name"]
                            )
                            if cid_row and cid_row.get("company_id"):
                                company_id = cid_row["company_id"]
            except Exception as e:
                logger.warning(f"Database user fallback error in check_topic_course: {e}")

        # 3. Fetch company courses from CMS API if missing but company_id is available
        if not company_courses and company_id:
            try:
                def _fetch_courses():
                    return requests.get(
                        COMPANY_COURSES_API_URL,
                        json={
                            "CompanyId": str(company_id),
                            "SecurityKey": COMPANY_COURSES_SECURITY_KEY
                        },
                        timeout=10.0
                    )

                cc_resp = await asyncio.to_thread(_fetch_courses)
                if cc_resp.status_code == 200:
                    cc_data = cc_resp.json()
                    company_courses = cc_data.get("courses", []) or []

                    # Backfill Redis cache with retrieved company courses
                    if user_id:
                        cached_dict = user_data if isinstance(user_data, dict) else {}
                        cached_dict.update({
                            "id": user_id,
                            "role": user_role or cached_dict.get("role", ""),
                            "user_type": user_type or cached_dict.get("user_type", ""),
                            "company_id": company_id,
                            "company_courses": company_courses
                        })
                        await redis_service.set_user_data(user_id, cached_dict)
            except Exception as e:
                logger.warning(f"Failed to fetch company courses from CMS API: {e}")

        # 4. Query course content and metadata from Postgres
        async with pool.acquire() as conn:
            query = """
                SELECT c.course_code, c.topic_name, m.course_name 
                FROM course_content c
                LEFT JOIN master_course_data m ON c.course_code = m.course_code
                WHERE c.topic_code = $1
                LIMIT 1
            """
            row = await conn.fetchrow(query, resolved_topic_code)
            if not row:
                # Fallback to case-insensitive match on topic_code
                query_ci = """
                    SELECT c.course_code, c.topic_name, m.course_name 
                    FROM course_content c
                    LEFT JOIN master_course_data m ON c.course_code = m.course_code
                    WHERE LOWER(c.topic_code) = LOWER($1)
                    LIMIT 1
                """
                row = await conn.fetchrow(query_ci, resolved_topic_code)

            if not row:
                return {
                    "matched": False,
                    "user_role": user_role,
                    "user_type": user_type,
                    "data": None,
                    "message": "Topic not found"
                }

            db_course_code = row["course_code"]
            topic_name = row["topic_name"]
            db_course_name = dict(row).get("course_name") or topic_name

            # Find matching course in company_courses
            matched_course = next(
                (
                    c for c in company_courses 
                    if isinstance(c, dict) and 
                    str(c.get("CourseCode") or c.get("courseCode", "")).lower().strip() == str(db_course_code).lower().strip()
                ),
                None
            )

            # Build base standard response
            response = {
                "matched": matched_course is not None,
                "user_role": user_role,
                "user_type": user_type,
                "message": "" if matched_course else ("Course not assigned to company" if company_courses else "No company courses found"),
                "data": {
                    "topic_code": resolved_topic_code,
                    "topic_name": topic_name,
                    "course": matched_course
                }
            }

            # If not matched, but user is not a student, still provide the course metadata
            is_student = str(user_type).strip().lower() == "student" or str(user_role).strip().lower() == "student"
            if not matched_course and not is_student:
                response["data"]["course"] = {
                    "CourseCode": db_course_code,
                    "CourseName": db_course_name
                }
            elif not matched_course:
                # For students who aren't matched, keep data as None to maintain consistent failure shape
                response["data"] = None

            return response
    except Exception as e:
        logger.error(f"Error in check_topic_course: {e}")
        raise HTTPException(status_code=500, detail=str(e))
