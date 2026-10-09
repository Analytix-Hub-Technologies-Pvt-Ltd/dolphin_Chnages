from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
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
            return {"matched": False, "user_role": "", "user_type": "", "data": None, "message": "User session not found"}
        
        user_role = user_data.get("role", "")
        user_type = user_data.get("user_type", "")
        company_courses = user_data.get("company_courses", [])
        
        if not company_courses:
            return {"matched": False, "user_role": user_role, "user_type": user_type, "data": None, "message": "No company courses found"}
        
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
            
            # Find the first matching course in company_courses
            matched_course = next(
                (
                    c for c in company_courses 
                    if isinstance(c, dict) and 
                    str(c.get("CourseCode") or c.get("courseCode", "")).lower().strip() == str(db_course_code).lower().strip()
                ),
                None
            )

            # Base standard response
            response = {
                "matched": matched_course is not None,
                "user_role": user_role,
                "user_type": user_type,
                "message": "" if matched_course else "Course not assigned to company",
                "data": {
                    "topic_code": request.topic_code,
                    "topic_name": topic_name,
                    "course": matched_course
                }
            }

            # If not matched, but user is not a student, still provide the course metadata
            if not matched_course and str(user_type).lower() != "student":
                response["data"]["course"] = {
                    "CourseCode": db_course_code,
                    "CourseName": db_course_name
                }
            elif not matched_course:
                # For students who aren't matched, keep data as None to maintain consistent failure shape
                response["data"] = None

            return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
