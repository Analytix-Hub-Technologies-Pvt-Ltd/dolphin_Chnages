from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
import json
from loguru import logger
from asyncpg import Pool
from api.dependencies import get_db_pool
from core.redis_client import redis_service

router = APIRouter(prefix="/course", tags=["course"])

class CheckTopicCourseRequest(BaseModel):
    topic_code: str
    user_id: str

@router.post("/check-topic-course")
async def check_topic_course(
    request: CheckTopicCourseRequest,
    pool: Pool = Depends(get_db_pool)
):
    try:
        user_data = await redis_service.get_user_data(request.user_id)
        if not user_data:
            # Fallback to DB if Redis session is absent, expired, or Redis server is down
            try:
                async with pool.acquire() as conn:
                    db_u = await conn.fetchrow(
                        "SELECT id, role, user_type, user_courses, company_id FROM users WHERE id::text = $1 LIMIT 1",
                        str(request.user_id)
                    )
                    if db_u:
                        user_data = dict(db_u)
            except Exception as db_err:
                logger.warning(f"DB fallback fetch for user {request.user_id} failed: {db_err}")

        if not user_data:
            return {"matched": False, "user_role": "", "user_type": "", "data": None, "message": "User session not found"}
        
        user_role = user_data.get("role", "")
        user_type = user_data.get("user_type", "")
        
        # Parse user_courses (individual user / student licensed courses)
        raw_user_courses = user_data.get("user_courses") or []
        if isinstance(raw_user_courses, str):
            try:
                raw_user_courses = json.loads(raw_user_courses)
            except Exception:
                raw_user_courses = []

        user_courses = []
        if isinstance(raw_user_courses, list):
            user_courses = raw_user_courses
        elif isinstance(raw_user_courses, dict):
            if "courses" in raw_user_courses and isinstance(raw_user_courses["courses"], list):
                user_courses = raw_user_courses["courses"]
            else:
                # Handle CMS studentcourses format: {"StudentId": ..., "CompletedCourses": "...", "PendingCourses": "..."}
                raw_entries = []
                for k in ["CompletedCourses", "PendingCourses"]:
                    v = raw_user_courses.get(k)
                    if isinstance(v, str) and v.strip():
                        raw_entries.extend([item.strip() for item in v.split(",") if item.strip()])
                    elif isinstance(v, list):
                        raw_entries.extend(v)
                for entry in raw_entries:
                    if isinstance(entry, dict):
                        user_courses.append(entry)
                    elif isinstance(entry, str):
                        parts = entry.split("-", 1)
                        code_prefix = parts[0].strip() if len(parts) > 1 else entry.strip()
                        user_courses.append({
                            "CourseCode": code_prefix,
                            "CourseName": entry.strip()
                        })

        # Parse company_courses (company licensed courses - preserved and untouched)
        raw_company_courses = user_data.get("company_courses") or []
        if isinstance(raw_company_courses, str):
            try:
                company_courses = json.loads(raw_company_courses)
            except Exception:
                company_courses = []
        elif isinstance(raw_company_courses, list):
            company_courses = raw_company_courses
        else:
            company_courses = []

        # Determine context: regular user / student vs company admin / company-level
        is_user_side = (
            bool(user_courses)
            or str(user_type).lower() in ("student", "user", "") 
            or str(user_role).lower() in ("student", "user", "")
        )

        # On the user side, check user_courses only; for company context, check company_courses
        target_course_list = user_courses if (is_user_side and user_courses) else company_courses
        if is_user_side and not user_courses:
            return {
                "matched": False,
                "user_role": user_role,
                "user_type": user_type,
                "data": None,
                "message": "No licensed user courses found"
            }
        elif not is_user_side and not company_courses:
            return {
                "matched": False,
                "user_role": user_role,
                "user_type": user_type,
                "data": None,
                "message": "No company courses found"
            }
        
        async with pool.acquire() as conn:
            query = """
                SELECT c.course_code, c.topic_name, m.course_name 
                FROM course_content c
                LEFT JOIN master_course_data m ON c.course_code = m.course_code
                WHERE c.topic_code = $1
                LIMIT 1
            """
            row = await conn.fetchrow(query, request.topic_code)
            if not row:
                return {"matched": False, "user_role": user_role, "user_type": user_type, "data": None, "message": "Topic not found"}
            
            db_course_code = row["course_code"]
            topic_name = row["topic_name"]
            db_course_name = dict(row).get("course_name", "")
            
            def is_course_matched(c_item, target_code, target_name):
                if not isinstance(c_item, dict):
                    return False
                c_code = str(c_item.get("CourseCode") or c_item.get("courseCode") or c_item.get("course_code") or "").lower().strip()
                c_name = str(c_item.get("CourseName") or c_item.get("courseName") or c_item.get("course_name") or "").lower().strip()
                t_code = str(target_code or "").lower().strip()
                t_name = str(target_name or "").lower().strip()
                
                # Direct code match (e.g. UUID in company courses)
                if c_code and t_code and c_code == t_code:
                    return True
                # Direct name match
                if c_name and t_name and (c_name == t_name or c_name in t_name or t_name in c_name):
                    return True
                # Code in name match (e.g. "dbmv-201" inside "dbmv-201-bridge procedures...")
                if c_code and t_name and c_code in t_name:
                    return True
                return False

            # Find matching course in target_course_list
            matched_course = next(
                (c for c in target_course_list if is_course_matched(c, db_course_code, db_course_name)),
                None
            )

            if matched_course and not (matched_course.get("CourseName") or matched_course.get("courseName")):
                matched_course["CourseName"] = db_course_name

            # Return matched true strictly if the course is in the licensed list
            response = {
                "matched": matched_course is not None,
                "user_role": user_role,
                "user_type": user_type,
                "message": "" if matched_course else ("Course not licensed for user" if is_user_side else "Course not assigned to company"),
                "data": {
                    "topic_code": request.topic_code,
                    "topic_name": topic_name,
                    "course": matched_course
                } if matched_course else None
            }

            return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/topic-info/{topic_code}")
async def get_topic_info(
    topic_code: str,
    pool: Pool = Depends(get_db_pool),
):
    """Return course_code, course_name, and topic_name for a given topic_code for media inspection."""
    try:
        async with pool.acquire() as conn:
            query = """
                SELECT c.course_code, c.topic_name, COALESCE(m.course_name, '') as course_name 
                FROM course_content c
                LEFT JOIN master_course_data m ON c.course_code = m.course_code
                WHERE c.topic_code = $1
                LIMIT 1
            """
            row = await conn.fetchrow(query, topic_code)
            if not row:
                return {
                    "course_code": "",
                    "course_name": "",
                    "topic_name": "",
                    "found": False,
                }
            return {
                "course_code": str(row["course_code"] or ""),
                "course_name": str(row["course_name"] or ""),
                "topic_name": str(row["topic_name"] or ""),
                "found": True,
            }
    except Exception as e:
        return {
            "course_code": "",
            "course_name": "",
            "topic_name": "",
            "found": False,
            "error": str(e),
        }
