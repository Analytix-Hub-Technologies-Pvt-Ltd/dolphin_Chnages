import httpx
import json
from course_sync.course_sync_models import CourseListResponse, CourseContentResponse
from loguru import logger

class ExternalAPIClient:
    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=60.0, verify=False)  
    
    async def get_course_list(self, updated_after: str) -> CourseListResponse:
        payload = {"Key": self.api_key, "UpdatedAfter": updated_after}
        return await self._call_course_list_api(payload)
    
    async def get_all_courses(self) -> CourseListResponse:
        payload = {"Key": self.api_key}
        return await self._call_course_list_api(payload)
    
    async def _call_course_list_api(self, payload: dict) -> CourseListResponse:
        try:
            url = f"{self.base_url}/CourseList"
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            
            data = response.json()
            courses_data = data.get('value', data)
            
            if not courses_data or courses_data == '':
                courses_data = []
            elif isinstance(courses_data, str):
                try:
                    courses_data = json.loads(courses_data)
                except Exception:
                    courses_data = []
            elif not isinstance(courses_data, list):
                courses_data = []
            
            changed_count = sum(1 for course in courses_data if course.get('Changed') == 1)
            unchanged_count = len(courses_data) - changed_count
            
            logger.info(f"Retrieved {len(courses_data)} courses from API (Changed: {changed_count}, Unchanged: {unchanged_count})")
            return CourseListResponse(courses=courses_data)
            
        except Exception as e:
            logger.error(f"CourseList API error: {e}")
            raise
    
    async def get_course_content(self, course_code: str) -> CourseContentResponse:
        try:
            url = f"{self.base_url}/CourseContent"
            payload = {"Key": self.api_key, "CourseCode": course_code}
            
            response = await self.client.post(url, json=payload)
            
            if response.status_code == 500:
                logger.warning(f"API server error (500) for course {course_code} - course may be corrupted or unavailable")
                raise Exception(f"API Server Error: Course {course_code} is currently unavailable (Internal Server Error)")
            
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('errorCode', 0) != 0:
                error_msg = data.get('error', 'Unknown error')
                logger.warning(f"API returned error for course {course_code}: {error_msg}")
                raise Exception(f"API Error: {error_msg}")
            
            if not data.get('value'):
                logger.warning(f"No content URL available for course {course_code}")
                raise Exception("No content URL available")
            
            return CourseContentResponse(value=data["value"])
            
        except Exception as e:
            logger.error(f"CourseContent API error for {course_code}: {e}")
            raise
    
    async def download_content_zip(self, zip_url: str) -> bytes:
        try:
            response = await self.client.get(zip_url)
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.error(f"Zip download error: {e}")
            raise
    
    async def close(self):
        await self.client.aclose()   