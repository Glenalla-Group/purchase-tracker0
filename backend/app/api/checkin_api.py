"""
Checkin API Endpoints
FastAPI routes for managing warehouse check-in records
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Any
from datetime import datetime
from pydantic import BaseModel
import logging

from app.config.database import get_db
from app.models.database import Checkin, AsinBank

router = APIRouter(prefix="/api/v1/checkin", tags=["Checkin"])
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

class CheckinCreate(BaseModel):
    """Model for creating a new check-in record"""
    order_number: str
    item_name: str
    asin: Optional[str] = None  # Can provide ASIN directly
    size: Optional[str] = None  # Size if creating new ASIN
    asin_bank_id: Optional[int] = None  # Or provide existing asin_bank_id
    quantity: int
    checked_in_at: Optional[datetime] = None  # Optional, defaults to now


class CheckinUpdate(BaseModel):
    """Model for updating a check-in record"""
    order_number: Optional[str] = None
    item_name: Optional[str] = None
    asin_bank_id: Optional[int] = None
    quantity: Optional[int] = None
    checked_in_at: Optional[datetime] = None


class CheckinResponse(BaseModel):
    """Model for check-in response"""
    id: int
    order_number: Optional[str]
    item_name: Optional[str]
    asin_bank_id: Optional[int]
    asin: Optional[str]  # From relationship
    size: Optional[str]  # From relationship
    quantity: int
    checked_in_at: datetime

    class Config:
        from_attributes = True


# ========================
# Checkin Endpoints
# ========================

@router.get("/")
def get_all_checkins(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    order_number: Optional[str] = None,
    asin: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db)
):
    """
    Get all check-in records with pagination and filters
    
    Query Parameters:
    - skip: Number of records to skip (default: 0)
    - limit: Maximum number of records to return (default: 100, max: 1000)
    - order_number: Filter by order number
    - asin: Filter by ASIN
    - start_date: Filter by check-in date (start)
    - end_date: Filter by check-in date (end)
    """
    query = db.query(Checkin)
    
    # Apply filters
    if order_number:
        query = query.filter(Checkin.order_number.ilike(f"%{order_number}%"))
    
    if asin:
        # Join with asin_bank to filter by ASIN
        query = query.join(AsinBank, Checkin.asin_bank_id == AsinBank.id).filter(
            AsinBank.asin.ilike(f"%{asin}%")
        )
    
    if start_date:
        query = query.filter(Checkin.checked_in_at >= start_date)
    
    if end_date:
        query = query.filter(Checkin.checked_in_at <= end_date)
    
    total = query.count()
    checkins = query.offset(skip).limit(limit).all()
    
    logger.info(f"Retrieved {len(checkins)} check-in records (total: {total})")
    
    # Convert to dict for JSON serialization
    checkins_data = []
    for checkin in checkins:
        checkins_data.append({
            "id": checkin.id,
            "order_number": checkin.order_number,
            "item_name": checkin.item_name,
            "asin_bank_id": checkin.asin_bank_id,
            "asin": checkin.asin,  # Property from relationship
            "size": checkin.size,  # Property from relationship
            "quantity": checkin.quantity,
            "checked_in_at": checkin.checked_in_at.isoformat() if checkin.checked_in_at else None
        })
    
    return {
        "status": 200,
        "data": {
            "items": checkins_data,
            "total": total
        },
        "message": f"Retrieved {len(checkins)} of {total} check-in records"
    }


@router.get("/{checkin_id}")
def get_checkin_by_id(checkin_id: int, db: Session = Depends(get_db)):
    """
    Get a specific check-in record by ID
    """
    checkin = db.query(Checkin).filter(Checkin.id == checkin_id).first()
    
    if not checkin:
        raise HTTPException(status_code=404, detail=f"Check-in record with ID {checkin_id} not found")
    
    checkin_data = {
        "id": checkin.id,
        "order_number": checkin.order_number,
        "item_name": checkin.item_name,
        "asin_bank_id": checkin.asin_bank_id,
        "asin": checkin.asin,
        "size": checkin.size,
        "quantity": checkin.quantity,
        "checked_in_at": checkin.checked_in_at.isoformat() if checkin.checked_in_at else None
    }
    
    return {
        "status": 200,
        "data": checkin_data,
        "message": ""
    }


@router.post("/", status_code=201)
def create_checkin(checkin: CheckinCreate, db: Session = Depends(get_db)):
    """
    Create a new check-in record
    
    You can either:
    1. Provide asin_bank_id if the ASIN already exists
    2. Provide asin (and optionally size) to create/find ASIN in asin_bank
    """
    asin_bank_id = checkin.asin_bank_id
    
    # If ASIN provided but no asin_bank_id, find or create it
    if not asin_bank_id and checkin.asin:
        asin_record = db.query(AsinBank).filter(
            AsinBank.asin == checkin.asin,
            AsinBank.size == checkin.size if checkin.size else True
        ).first()
        
        if not asin_record:
            # Create new ASIN bank entry
            # Use order_number as lead_id for now (you might want to adjust this)
            asin_record = AsinBank(
                lead_id=checkin.order_number or "CHECKIN",
                asin=checkin.asin,
                size=checkin.size
            )
            db.add(asin_record)
            db.flush()  # Get the ID
            logger.info(f"Created new ASIN bank entry: {checkin.asin} (ID: {asin_record.id})")
        
        asin_bank_id = asin_record.id
    
    # Create check-in record
    new_checkin = Checkin(
        order_number=checkin.order_number,
        item_name=checkin.item_name,
        asin_bank_id=asin_bank_id,
        quantity=checkin.quantity,
        checked_in_at=checkin.checked_in_at or datetime.utcnow()
    )
    
    db.add(new_checkin)
    db.commit()
    db.refresh(new_checkin)
    
    logger.info(f"Created new check-in: Order {checkin.order_number}, {checkin.quantity} items (ID: {new_checkin.id})")
    
    checkin_data = {
        "id": new_checkin.id,
        "order_number": new_checkin.order_number,
        "item_name": new_checkin.item_name,
        "asin_bank_id": new_checkin.asin_bank_id,
        "asin": new_checkin.asin,
        "size": new_checkin.size,
        "quantity": new_checkin.quantity,
        "checked_in_at": new_checkin.checked_in_at.isoformat() if new_checkin.checked_in_at else None,
        "notes": new_checkin.notes,
        "checked_in_by": new_checkin.checked_in_by
    }
    
    return {
        "status": 200,
        "data": checkin_data,
        "message": f"Check-in created successfully"
    }


@router.put("/{checkin_id}")
def update_checkin(checkin_id: int, checkin_update: CheckinUpdate, db: Session = Depends(get_db)):
    """
    Update an existing check-in record
    """
    checkin = db.query(Checkin).filter(Checkin.id == checkin_id).first()
    
    if not checkin:
        raise HTTPException(status_code=404, detail=f"Check-in record with ID {checkin_id} not found")
    
    # Update fields if provided
    update_data = checkin_update.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(checkin, field, value)
    
    db.commit()
    db.refresh(checkin)
    
    logger.info(f"Updated check-in: ID {checkin_id}")
    
    checkin_data = {
        "id": checkin.id,
        "order_number": checkin.order_number,
        "item_name": checkin.item_name,
        "asin_bank_id": checkin.asin_bank_id,
        "asin": checkin.asin,
        "size": checkin.size,
        "quantity": checkin.quantity,
        "checked_in_at": checkin.checked_in_at.isoformat() if checkin.checked_in_at else None
    }
    
    return {
        "status": 200,
        "data": checkin_data,
        "message": "Check-in updated successfully"
    }


@router.delete("/{checkin_id}")
def delete_checkin(checkin_id: int, db: Session = Depends(get_db)):
    """
    Delete a check-in record
    """
    checkin = db.query(Checkin).filter(Checkin.id == checkin_id).first()
    
    if not checkin:
        raise HTTPException(status_code=404, detail=f"Check-in record with ID {checkin_id} not found")
    
    order_number = checkin.order_number
    db.delete(checkin)
    db.commit()
    
    logger.info(f"Deleted check-in: Order {order_number} (ID: {checkin_id})")
    
    return {
        "status": 200,
        "data": None,
        "message": f"Check-in for order '{order_number}' deleted successfully"
    }


@router.get("/stats/summary")
def get_checkin_summary(db: Session = Depends(get_db)):
    """
    Get summary statistics for check-ins
    """
    from sqlalchemy import func
    
    total_checkins = db.query(func.count(Checkin.id)).scalar()
    total_quantity = db.query(func.sum(Checkin.quantity)).scalar() or 0
    
    # Check-ins today
    from datetime import date
    today_start = datetime.combine(date.today(), datetime.min.time())
    checkins_today = db.query(func.count(Checkin.id)).filter(
        Checkin.checked_in_at >= today_start
    ).scalar()
    
    # By order number
    by_order = db.query(
        Checkin.order_number,
        func.sum(Checkin.quantity).label('total_qty'),
        func.count(Checkin.id).label('checkin_count')
    ).group_by(Checkin.order_number).order_by(
        func.sum(Checkin.quantity).desc()
    ).limit(10).all()
    
    summary_data = {
        "total_checkins": total_checkins,
        "total_quantity_checked_in": int(total_quantity),
        "checkins_today": checkins_today,
        "top_orders": [
            {
                "order_number": order,
                "total_quantity": int(qty),
                "checkin_count": count
            }
            for order, qty, count in by_order if order
        ]
    }
    
    return {
        "status": 200,
        "data": summary_data,
        "message": ""
    }


@router.get("/by-order/{order_number}")
def get_checkins_by_order(order_number: str, db: Session = Depends(get_db)):
    """
    Get all check-ins for a specific order number
    """
    checkins = db.query(Checkin).filter(
        Checkin.order_number == order_number
    ).order_by(Checkin.checked_in_at.desc()).all()
    
    if not checkins:
        raise HTTPException(status_code=404, detail=f"No check-ins found for order {order_number}")
    
    checkins_data = []
    for checkin in checkins:
        checkins_data.append({
            "id": checkin.id,
            "order_number": checkin.order_number,
            "item_name": checkin.item_name,
            "asin_bank_id": checkin.asin_bank_id,
            "asin": checkin.asin,
            "size": checkin.size,
            "quantity": checkin.quantity,
            "checked_in_at": checkin.checked_in_at.isoformat() if checkin.checked_in_at else None
        })
    
    order_data = {
        "order_number": order_number,
        "total_quantity": sum(c.quantity for c in checkins),
        "checkin_count": len(checkins),
        "checkins": checkins_data
    }
    
    return {
        "status": 200,
        "data": order_data,
        "message": ""
    }



