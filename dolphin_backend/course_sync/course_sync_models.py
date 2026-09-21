from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, date

class CourseListItem(BaseModel):
    CourseCode: str
    Name: str
    FetchedOn: Optional[str] = None
    Changed: Optional[int] = None

class CourseListResponse(BaseModel):
    courses: List[CourseListItem]

class CourseContentResponse(BaseModel):
    value: str  

class MasterCourseData(BaseModel):
    course_id: int
    course_code: str
    course_name: str
    course_added: date

class CourseContent(BaseModel):
    content_id: int
    course_code: str
    topic_code: str
    topic_name: str
    topic_video: List[dict]
    topic_image: List[dict]
    topic_pdf: Optional[List[dict]]
    topic_content: str
    fetched_on: date

class TopicData(BaseModel):
    TopicCode: str
    Name: str

class VideoData(BaseModel):
    TopicCode: str
    Videos: List[dict]

class ImageData(BaseModel):
    TopicCode: str   
    Images: List[dict]

class PdfData(BaseModel):
    TopicCode: str
    Pdfs: List[dict]

class FetchData(BaseModel):
    FetchDate: str

class SyncConfig(BaseModel):
    last_sync_date: datetime