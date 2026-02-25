"""
PTO API Endpoints
FastAPI routes for managing PTO (Paid Time Off) requests
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from typing import List, Optional, Any
from datetime import datetime, date, timedelta
from pydantic import BaseModel
import logging

from app.config.database import get_db
from app.models.database import PTORequest, User

router = APIRouter(prefix="/api/v1/pto", tags=["PTO"])
logger = logging.getLogger(__name__)


# ========================
# API Response Wrapper
# ========================

class APIResponse(BaseModel):
    """Standard API response wrapper"""
    status: int = 200  # 200 = SUCCESS, -1 = ERROR (matches frontend ResultStatus enum)
    data: Any
    message: str = ""
    
    class Config:
        arbitrary_types_allowed = True


# ========================
# Request/Response Models
# ========================

class PTORequestCreate(BaseModel):
    """Model for creating a new PTO request"""
    user_id: int
    start_date: date
    end_date: date
    request_type: str = "pto"  # 'pto', 'sick', 'personal', 'holiday'
    reason: Optional[str] = None
    notes: Optional[str] = None


class PTORequestUpdate(BaseModel):
    """Model for updating a PTO request"""
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    request_type: Optional[str] = None
    status: Optional[str] = None  # 'pending', 'approved', 'rejected', 'cancelled'
    reason: Optional[str] = None
    notes: Optional[str] = None
    approved_by_id: Optional[int] = None


class PTORequestResponse(BaseModel):
    """Model for PTO request response"""
    id: int
    user_id: int
    username: Optional[str] = None
    start_date: date
    end_date: date
    total_days: float
    request_type: str
    status: str
    reason: Optional[str] = None
    notes: Optional[str] = None
    approved_by_id: Optional[int] = None
    approved_by_username: Optional[str] = None
    approved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PTOStatsResponse(BaseModel):
    """Model for PTO statistics"""
    user_id: int
    username: str
    total_pto_days: float
    pending_requests: int
    approved_requests: int
    rejected_requests: int
    upcoming_pto: List[PTORequestResponse]


# ========================
# Helper Functions
# ========================

def calculate_total_days(start_date: date, end_date: date) -> float:
    """Calculate total days between start and end date (inclusive)"""
    delta = end_date - start_date
    return delta.days + 1


# ========================
# PTO Endpoints
# ========================

@router.get("/")
def get_all_pto_requests(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    user_id: Optional[int] = None,
    status: Optional[str] = None,
    request_type: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """
    Get all PTO requests with pagination and filters
    """
    query = db.query(PTORequest).join(User, PTORequest.user_id == User.id)
    
    # Apply filters
    if user_id:
        query = query.filter(PTORequest.user_id == user_id)
    if status:
        query = query.filter(PTORequest.status == status)
    if request_type:
        query = query.filter(PTORequest.request_type == request_type)
    if start_date:
        query = query.filter(PTORequest.start_date >= start_date)
    if end_date:
        query = query.filter(PTORequest.end_date <= end_date)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    pto_requests = query.order_by(PTORequest.start_date.desc()).offset(skip).limit(limit).all()
    
    # Format response
    results = []
    for pto in pto_requests:
        result = PTORequestResponse(
            id=pto.id,
            user_id=pto.user_id,
            username=pto.user.username if pto.user else None,
            start_date=pto.start_date,
            end_date=pto.end_date,
            total_days=pto.total_days,
            request_type=pto.request_type,
            status=pto.status,
            reason=pto.reason,
            notes=pto.notes,
            approved_by_id=pto.approved_by_id,
            approved_by_username=pto.approved_by.username if pto.approved_by else None,
            approved_at=pto.approved_at,
            created_at=pto.created_at,
            updated_at=pto.updated_at
        )
        results.append(result)
    
    return APIResponse(
        status=200,
        data={
            "total": total,
            "items": results
        },
        message="PTO requests retrieved successfully"
    )


@router.get("/{pto_id}")
def get_pto_request_by_id(pto_id: int, db: Session = Depends(get_db)):
    """Get a specific PTO request by ID"""
    pto = db.query(PTORequest).join(User, PTORequest.user_id == User.id).filter(PTORequest.id == pto_id).first()
    
    if not pto:
        raise HTTPException(status_code=404, detail="PTO request not found")
    
    result = PTORequestResponse(
        id=pto.id,
        user_id=pto.user_id,
        username=pto.user.username if pto.user else None,
        start_date=pto.start_date,
        end_date=pto.end_date,
        total_days=pto.total_days,
        request_type=pto.request_type,
        status=pto.status,
        reason=pto.reason,
        notes=pto.notes,
        approved_by_id=pto.approved_by_id,
        approved_by_username=pto.approved_by.username if pto.approved_by else None,
        approved_at=pto.approved_at,
        created_at=pto.created_at,
        updated_at=pto.updated_at
    )
    
    return APIResponse(status=200, data=result, message="PTO request retrieved successfully")


@router.post("/")
def create_pto_request(request: PTORequestCreate, db: Session = Depends(get_db)):
    """Create a new PTO request"""
    # Validate user exists
    user = db.query(User).filter(User.id == request.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Validate dates
    if request.end_date < request.start_date:
        raise HTTPException(status_code=400, detail="End date must be after or equal to start date")
    
    # Calculate total days
    total_days = calculate_total_days(request.start_date, request.end_date)
    
    # Check for overlapping requests
    overlapping = db.query(PTORequest).filter(
        PTORequest.user_id == request.user_id,
        PTORequest.status.in_(['pending', 'approved']),
        or_(
            and_(PTORequest.start_date <= request.end_date, PTORequest.end_date >= request.start_date)
        )
    ).first()
    
    if overlapping:
        raise HTTPException(
            status_code=400,
            detail=f"Overlapping PTO request exists (ID: {overlapping.id}, {overlapping.start_date} to {overlapping.end_date})"
        )
    
    # Create PTO request
    pto_request = PTORequest(
        user_id=request.user_id,
        start_date=request.start_date,
        end_date=request.end_date,
        total_days=total_days,
        request_type=request.request_type,
        status='pending',
        reason=request.reason,
        notes=request.notes
    )
    
    db.add(pto_request)
    db.commit()
    db.refresh(pto_request)
    
    # Get user info
    pto_request.user = user
    
    result = PTORequestResponse(
        id=pto_request.id,
        user_id=pto_request.user_id,
        username=pto_request.user.username if pto_request.user else None,
        start_date=pto_request.start_date,
        end_date=pto_request.end_date,
        total_days=pto_request.total_days,
        request_type=pto_request.request_type,
        status=pto_request.status,
        reason=pto_request.reason,
        notes=pto_request.notes,
        created_at=pto_request.created_at,
        updated_at=pto_request.updated_at
    )
    
    return APIResponse(status=200, data=result, message="PTO request created successfully")


@router.put("/{pto_id}")
def update_pto_request(pto_id: int, request: PTORequestUpdate, db: Session = Depends(get_db)):
    """Update a PTO request"""
    pto = db.query(PTORequest).filter(PTORequest.id == pto_id).first()
    
    if not pto:
        raise HTTPException(status_code=404, detail="PTO request not found")
    
    # Update fields
    if request.start_date is not None:
        pto.start_date = request.start_date
    if request.end_date is not None:
        pto.end_date = request.end_date
    if request.request_type is not None:
        pto.request_type = request.request_type
    if request.status is not None:
        pto.status = request.status
        if request.status == 'approved' and not pto.approved_at:
            pto.approved_at = datetime.utcnow()
            if request.approved_by_id:
                pto.approved_by_id = request.approved_by_id
    if request.reason is not None:
        pto.reason = request.reason
    if request.notes is not None:
        pto.notes = request.notes
    if request.approved_by_id is not None:
        pto.approved_by_id = request.approved_by_id
    
    # Recalculate total days if dates changed
    if request.start_date is not None or request.end_date is not None:
        pto.total_days = calculate_total_days(pto.start_date, pto.end_date)
    
    db.commit()
    db.refresh(pto)
    
    # Load relationships
    pto.user = db.query(User).filter(User.id == pto.user_id).first()
    if pto.approved_by_id:
        pto.approved_by = db.query(User).filter(User.id == pto.approved_by_id).first()
    
    result = PTORequestResponse(
        id=pto.id,
        user_id=pto.user_id,
        username=pto.user.username if pto.user else None,
        start_date=pto.start_date,
        end_date=pto.end_date,
        total_days=pto.total_days,
        request_type=pto.request_type,
        status=pto.status,
        reason=pto.reason,
        notes=pto.notes,
        approved_by_id=pto.approved_by_id,
        approved_by_username=pto.approved_by.username if pto.approved_by else None,
        approved_at=pto.approved_at,
        created_at=pto.created_at,
        updated_at=pto.updated_at
    )
    
    return APIResponse(status=200, data=result, message="PTO request updated successfully")


@router.delete("/{pto_id}")
def delete_pto_request(pto_id: int, db: Session = Depends(get_db)):
    """Delete a PTO request"""
    pto = db.query(PTORequest).filter(PTORequest.id == pto_id).first()
    
    if not pto:
        raise HTTPException(status_code=404, detail="PTO request not found")
    
    db.delete(pto)
    db.commit()
    
    return APIResponse(status=200, data={"id": pto_id}, message="PTO request deleted successfully")


@router.get("/user/{user_id}/stats")
def get_user_pto_stats(user_id: int, db: Session = Depends(get_db)):
    """Get PTO statistics for a specific user"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get all approved PTO requests
    approved_pto = db.query(func.sum(PTORequest.total_days)).filter(
        PTORequest.user_id == user_id,
        PTORequest.status == 'approved'
    ).scalar() or 0.0
    
    # Get counts by status
    pending_count = db.query(func.count(PTORequest.id)).filter(
        PTORequest.user_id == user_id,
        PTORequest.status == 'pending'
    ).scalar() or 0
    
    approved_count = db.query(func.count(PTORequest.id)).filter(
        PTORequest.user_id == user_id,
        PTORequest.status == 'approved'
    ).scalar() or 0
    
    rejected_count = db.query(func.count(PTORequest.id)).filter(
        PTORequest.user_id == user_id,
        PTORequest.status == 'rejected'
    ).scalar() or 0
    
    # Get upcoming approved PTO
    today = date.today()
    upcoming_pto_list = db.query(PTORequest).filter(
        PTORequest.user_id == user_id,
        PTORequest.status == 'approved',
        PTORequest.start_date >= today
    ).order_by(PTORequest.start_date).limit(10).all()
    
    upcoming_pto = []
    for pto in upcoming_pto_list:
        upcoming_pto.append(PTORequestResponse(
            id=pto.id,
            user_id=pto.user_id,
            username=user.username,
            start_date=pto.start_date,
            end_date=pto.end_date,
            total_days=pto.total_days,
            request_type=pto.request_type,
            status=pto.status,
            reason=pto.reason,
            notes=pto.notes,
            created_at=pto.created_at,
            updated_at=pto.updated_at
        ))
    
    stats = PTOStatsResponse(
        user_id=user_id,
        username=user.username,
        total_pto_days=float(approved_pto),
        pending_requests=pending_count,
        approved_requests=approved_count,
        rejected_requests=rejected_count,
        upcoming_pto=upcoming_pto
    )
    
    return APIResponse(status=200, data=stats, message="PTO statistics retrieved successfully")


@router.get("/stats/all-users")
def get_all_users_pto_stats(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """
    Get PTO statistics for all users with optional date range filtering
    
    Query Parameters:
    - start_date: Filter PTO requests starting from this date (optional)
    - end_date: Filter PTO requests ending before this date (optional)
    """
    users = db.query(User).filter(User.is_active == True).all()
    
    stats_list = []
    for user in users:
        # Build base query for approved PTO
        approved_query = db.query(func.sum(PTORequest.total_days)).filter(
            PTORequest.user_id == user.id,
            PTORequest.status == 'approved'
        )
        
        # Build base query for pending requests
        pending_query = db.query(func.count(PTORequest.id)).filter(
            PTORequest.user_id == user.id,
            PTORequest.status == 'pending'
        )
        
        # Build base query for approved count
        approved_count_query = db.query(func.count(PTORequest.id)).filter(
            PTORequest.user_id == user.id,
            PTORequest.status == 'approved'
        )
        
        # Build base query for rejected count
        rejected_count_query = db.query(func.count(PTORequest.id)).filter(
            PTORequest.user_id == user.id,
            PTORequest.status == 'rejected'
        )
        
        # Apply date filters if provided
        if start_date:
            approved_query = approved_query.filter(PTORequest.start_date >= start_date)
            pending_query = pending_query.filter(PTORequest.start_date >= start_date)
            approved_count_query = approved_count_query.filter(PTORequest.start_date >= start_date)
            rejected_count_query = rejected_count_query.filter(PTORequest.start_date >= start_date)
        
        if end_date:
            approved_query = approved_query.filter(PTORequest.end_date <= end_date)
            pending_query = pending_query.filter(PTORequest.end_date <= end_date)
            approved_count_query = approved_count_query.filter(PTORequest.end_date <= end_date)
            rejected_count_query = rejected_count_query.filter(PTORequest.end_date <= end_date)
        
        approved_pto = approved_query.scalar() or 0.0
        pending_count = pending_query.scalar() or 0
        approved_count = approved_count_query.scalar() or 0
        rejected_count = rejected_count_query.scalar() or 0
        
        stats_list.append({
            "user_id": user.id,
            "username": user.username,
            "total_pto_days": float(approved_pto),
            "pending_requests": pending_count,
            "approved_requests": approved_count,
            "rejected_requests": rejected_count
        })
    
    return APIResponse(
        status=200,
        data={
            "users": stats_list,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None
        },
        message="All users PTO statistics retrieved successfully"
    )

