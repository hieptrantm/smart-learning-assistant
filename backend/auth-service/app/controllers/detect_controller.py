from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
import base64
from datetime import datetime
import jwt

from app.database import get_db
# Why i can't import *?
from app.schemas.detect import GetDetectDetailResponse, GetDetectDetailRequest, CreateDetectRequest, GetDetectsByDateResponse, GetDetectDetailListResponse
from app.models import Detect

detect_router = APIRouter(prefix="/detect", tags=["Detection"])

@detect_router.get("/")
def root():
    return {"service": "detect-service", "status": "running"}

@detect_router.get("/detect-detail/{detect_id}", response_model=GetDetectDetailResponse)
def detect_detail(detect_id: int, db: Session = Depends(get_db)):
    detect = db.query(Detect).filter(Detect.id == detect_id).first()

    if not detect:
        raise HTTPException(status_code=404, detail="Detect not found")

    return GetDetectDetailResponse.from_orm(detect)

@detect_router.post("/detect-detail", response_model=GetDetectDetailResponse)
def create_detect(request: CreateDetectRequest, db: Session = Depends(get_db)):
    detect = Detect(
        user_id=request.user_id,
        image_mime_type=request.image_mime_type,
        detected_ingredients=request.detected_ingredients,
        recommendation=request.recommendation,
    )
    db.add(detect)
    db.commit()
    db.refresh(detect)

    return GetDetectDetailResponse.from_orm(detect)


@detect_router.get("/user/{user_id}", response_model=List[GetDetectDetailResponse])
def get_user_detects(
    user_id: int,
    offset: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    detects = (
        db.query(Detect)
        .filter(Detect.user_id == user_id)
        .order_by(Detect.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [GetDetectDetailResponse.from_orm(d) for d in detects]

@detect_router.get("/user/{user_id}/by-date", response_model=GetDetectsByDateResponse)
def get_detects_by_date(
    user_id: int,
    start_date: Optional[str] = None,  # Format: YYYY-MM-DD
    end_date: Optional[str] = None,    # Format: YYYY-MM-DD
    offset: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """
    Get user's detects filtered by date range (a period of time).
    
    Examples:
    - Get detects from Jan 1 to Jan 31: start_date=2024-01-01&end_date=2024-01-31
    - Get detects from a specific date onwards: start_date=2024-01-01
    - Get detects up to a specific date: end_date=2024-12-31
    - Get all detects: no parameters
    """
    query = db.query(Detect).filter(Detect.user_id == user_id)
    
    # Apply start date filter
    if start_date:
        try:
            start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(Detect.created_at >= start_datetime)
        except ValueError:
            raise HTTPException(
                status_code=400, 
                detail="Invalid start_date format. Use YYYY-MM-DD"
            )
    
    # Apply end date filter (include entire day)
    if end_date:
        try:
            end_datetime = datetime.strptime(end_date, "%Y-%m-%d")
            end_datetime = end_datetime.replace(hour=23, minute=59, second=59)
            query = query.filter(Detect.created_at <= end_datetime)
        except ValueError:
            raise HTTPException(
                status_code=400, 
                detail="Invalid end_date format. Use YYYY-MM-DD"
            )
    
    # Get total count
    total = query.count()
    
    # Get paginated results
    detects = (
        query
        .order_by(Detect.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    
    return GetDetectsByDateResponse(
        total=total,
        offset=offset,
        limit=limit,
        start_date=start_date,
        end_date=end_date,
        detects=[GetDetectDetailListResponse.from_orm(d) for d in detects]

    )