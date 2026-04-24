from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime

class GetDetectDetailRequest(BaseModel):
    id: str
    
class GetDetectDetailResponse(BaseModel):
    id: int
    user_id: int
    image_mime_type: Optional[str] = None
    detected_ingredients: Optional[List[str]] = None
    recommendation: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
    

class CreateDetectRequest(BaseModel):
    user_id: int
    image_mime_type: Optional[str]
    detected_ingredients: Optional[List[str]] = None
    recommendation: Optional[str] = None
    
class GetDetectDetailListResponse(BaseModel):
    id: int
    user_id: int
    image_mime_type: Optional[str] = None
    detected_ingredients: Optional[List[str]] = None
    recommendation: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class GetDetectsByDateResponse(BaseModel):
    total: int
    offset: int
    limit: int
    start_date: Optional[str]
    end_date: Optional[str]
    detects: List[GetDetectDetailListResponse]
    
    class Config:
        from_attributes = True
