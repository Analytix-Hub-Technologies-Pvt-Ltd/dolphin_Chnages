from pydantic import BaseModel

class TranscribeRequest(BaseModel):
    offset: int
    limit: int
    
class VideoInfo(BaseModel):
    id: str | None = None
    url: str | None = None
 
 
class CourseContentItem(BaseModel):
    course_code: str
    topic_code: str
    videos: list[VideoInfo]
    
class BatchTranscriptionResult(BaseModel):
    course_code: str | None = None
    topic_code: str | None = None
    video_id: str | None = None
    status: str
    error_message: str | None = None
 
 
 
class BatchTranscriptionResponse(BaseModel):
    offset: int
    limit: int
    results: list[BatchTranscriptionResult]
    
class VideoInfoRequest(BaseModel):
    id: str
    url: str