"""
Retailers API Endpoints
FastAPI routes for managing retailer data
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Any
from datetime import datetime
from pydantic import BaseModel
import logging

from app.config.database import get_db
from app.models.database import Retailer

router = APIRouter(prefix="/api/v1/retailers", tags=["Retailers"])
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

class RetailerCreate(BaseModel):
    """Model for creating a new retailer"""
    name: str
    link: Optional[str] = None
    wholesale: Optional[str] = None  # 'yes', 'no', 'n/a'
    cancel_for_bulk: Optional[bool] = False
    location: Optional[str] = None  # 'EU', 'USA', 'CANADA', 'AU', 'UK', 'SA'
    shopify: Optional[bool] = False
    total_spend: Optional[float] = 0.0
    total_qty_of_items_ordered: Optional[int] = 0
    percent_of_cancelled_qty: Optional[float] = 0.0


class RetailerUpdate(BaseModel):
    """Model for updating a retailer"""
    name: Optional[str] = None
    link: Optional[str] = None
    wholesale: Optional[str] = None
    cancel_for_bulk: Optional[bool] = None
    location: Optional[str] = None
    shopify: Optional[bool] = None
    total_spend: Optional[float] = None
    total_qty_of_items_ordered: Optional[int] = None
    percent_of_cancelled_qty: Optional[float] = None


class RetailerResponse(BaseModel):
    """Model for retailer response"""
    id: int
    name: str
    link: Optional[str] = None
    wholesale: Optional[str] = None
    cancel_for_bulk: bool
    location: Optional[str] = None
    shopify: bool
    total_spend: float
    total_qty_of_items_ordered: int
    percent_of_cancelled_qty: float
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ========================
# Retailers Endpoints
# ========================

@router.get("/")
def get_all_retailers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    location: Optional[str] = None,
    wholesale: Optional[str] = None,
    shopify: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """
    Get all retailers with pagination and filters
    
    Query Parameters:
    - skip: Number of records to skip (default: 0)
    - limit: Maximum number of records to return (default: 100, max: 1000)
    - location: Filter by location (EU, USA, CANADA, AU, UK, SA)
    - wholesale: Filter by wholesale status (yes, no, n/a)
    - shopify: Filter by Shopify status (true/false)
    """
    query = db.query(Retailer)
    
    # Apply filters
    if location:
        query = query.filter(Retailer.location == location)
    
    if wholesale:
        query = query.filter(Retailer.wholesale == wholesale)
    
    if shopify is not None:
        query = query.filter(Retailer.shopify == shopify)
    
    total = query.count()
    retailers = query.offset(skip).limit(limit).all()
    
    logger.info(f"Retrieved {len(retailers)} retailers (total: {total})")
    
    # Convert to dict for JSON serialization
    retailers_data = [
        {
            "id": r.id,
            "name": r.name,
            "link": r.link,
            "wholesale": r.wholesale,
            "cancel_for_bulk": r.cancel_for_bulk,
            "location": r.location,
            "shopify": r.shopify,
            "total_spend": float(r.total_spend) if r.total_spend else 0.0,
            "total_qty_of_items_ordered": r.total_qty_of_items_ordered or 0,
            "percent_of_cancelled_qty": float(r.percent_of_cancelled_qty) if r.percent_of_cancelled_qty else 0.0,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in retailers
    ]
    
    return {
        "status": 200,
        "data": {
            "items": retailers_data,
            "total": total
        },
        "message": f"Retrieved {len(retailers)} of {total} retailers"
    }


@router.get("/{retailer_id}")
def get_retailer_by_id(retailer_id: int, db: Session = Depends(get_db)):
    """
    Get a specific retailer by ID
    """
    retailer = db.query(Retailer).filter(Retailer.id == retailer_id).first()
    
    if not retailer:
        raise HTTPException(status_code=404, detail=f"Retailer with ID {retailer_id} not found")
    
    retailer_data = {
        "id": retailer.id,
        "name": retailer.name,
        "link": retailer.link,
        "wholesale": retailer.wholesale,
        "cancel_for_bulk": retailer.cancel_for_bulk,
        "location": retailer.location,
        "shopify": retailer.shopify,
        "total_spend": float(retailer.total_spend) if retailer.total_spend else 0.0,
        "total_qty_of_items_ordered": retailer.total_qty_of_items_ordered or 0,
        "percent_of_cancelled_qty": float(retailer.percent_of_cancelled_qty) if retailer.percent_of_cancelled_qty else 0.0,
        "created_at": retailer.created_at.isoformat() if retailer.created_at else None,
        "updated_at": retailer.updated_at.isoformat() if retailer.updated_at else None,
    }
    
    return {
        "status": 200,
        "data": retailer_data,
        "message": ""
    }


@router.get("/name/{retailer_name}")
def get_retailer_by_name(retailer_name: str, db: Session = Depends(get_db)):
    """
    Get a specific retailer by name (case-insensitive)
    """
    retailer = db.query(Retailer).filter(Retailer.name.ilike(retailer_name)).first()
    
    if not retailer:
        raise HTTPException(status_code=404, detail=f"Retailer '{retailer_name}' not found")
    
    retailer_data = {
        "id": retailer.id,
        "name": retailer.name,
        "link": retailer.link,
        "wholesale": retailer.wholesale,
        "cancel_for_bulk": retailer.cancel_for_bulk,
        "location": retailer.location,
        "shopify": retailer.shopify,
        "total_spend": float(retailer.total_spend) if retailer.total_spend else 0.0,
        "total_qty_of_items_ordered": retailer.total_qty_of_items_ordered or 0,
        "percent_of_cancelled_qty": float(retailer.percent_of_cancelled_qty) if retailer.percent_of_cancelled_qty else 0.0,
        "created_at": retailer.created_at.isoformat() if retailer.created_at else None,
        "updated_at": retailer.updated_at.isoformat() if retailer.updated_at else None,
    }
    
    return {
        "status": 200,
        "data": retailer_data,
        "message": ""
    }


@router.post("/", status_code=201)
def create_retailer(retailer: RetailerCreate, db: Session = Depends(get_db)):
    """
    Create a new retailer
    """
    # Check if retailer with this name already exists
    existing = db.query(Retailer).filter(Retailer.name == retailer.name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Retailer with name '{retailer.name}' already exists")
    
    # Validate wholesale value
    if retailer.wholesale and retailer.wholesale not in ['yes', 'no', 'n/a']:
        raise HTTPException(status_code=400, detail="Wholesale must be one of: yes, no, n/a")
    
    # Validate location value
    valid_locations = ['EU', 'USA', 'CANADA', 'AU', 'UK', 'SA']
    if retailer.location and retailer.location not in valid_locations:
        raise HTTPException(status_code=400, detail=f"Location must be one of: {', '.join(valid_locations)}")
    
    # Create new retailer
    new_retailer = Retailer(
        name=retailer.name,
        link=retailer.link,
        wholesale=retailer.wholesale,
        cancel_for_bulk=retailer.cancel_for_bulk,
        location=retailer.location,
        shopify=retailer.shopify,
        total_spend=retailer.total_spend,
        total_qty_of_items_ordered=retailer.total_qty_of_items_ordered,
        percent_of_cancelled_qty=retailer.percent_of_cancelled_qty
    )
    
    db.add(new_retailer)
    db.commit()
    db.refresh(new_retailer)
    
    logger.info(f"Created new retailer: {new_retailer.name} (ID: {new_retailer.id})")
    
    retailer_data = {
        "id": new_retailer.id,
        "name": new_retailer.name,
        "link": new_retailer.link,
        "wholesale": new_retailer.wholesale,
        "cancel_for_bulk": new_retailer.cancel_for_bulk,
        "location": new_retailer.location,
        "shopify": new_retailer.shopify,
        "total_spend": float(new_retailer.total_spend) if new_retailer.total_spend else 0.0,
        "total_qty_of_items_ordered": new_retailer.total_qty_of_items_ordered or 0,
        "percent_of_cancelled_qty": float(new_retailer.percent_of_cancelled_qty) if new_retailer.percent_of_cancelled_qty else 0.0,
        "created_at": new_retailer.created_at.isoformat() if new_retailer.created_at else None,
        "updated_at": new_retailer.updated_at.isoformat() if new_retailer.updated_at else None,
    }
    
    return {
        "status": 200,
        "data": retailer_data,
        "message": f"Retailer '{new_retailer.name}' created successfully"
    }


@router.put("/{retailer_id}")
def update_retailer(retailer_id: int, retailer_update: RetailerUpdate, db: Session = Depends(get_db)):
    """
    Update an existing retailer
    """
    retailer = db.query(Retailer).filter(Retailer.id == retailer_id).first()
    
    if not retailer:
        raise HTTPException(status_code=404, detail=f"Retailer with ID {retailer_id} not found")
    
    # Update fields if provided
    update_data = retailer_update.model_dump(exclude_unset=True)
    
    # Validate wholesale value if provided
    if 'wholesale' in update_data and update_data['wholesale'] not in ['yes', 'no', 'n/a', None]:
        raise HTTPException(status_code=400, detail="Wholesale must be one of: yes, no, n/a")
    
    # Validate location value if provided
    valid_locations = ['EU', 'USA', 'CANADA', 'AU', 'UK', 'SA']
    if 'location' in update_data and update_data['location'] not in valid_locations + [None]:
        raise HTTPException(status_code=400, detail=f"Location must be one of: {', '.join(valid_locations)}")
    
    # Check if name is being changed and if it conflicts with existing retailer
    if 'name' in update_data and update_data['name'] != retailer.name:
        existing = db.query(Retailer).filter(Retailer.name == update_data['name']).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"Retailer with name '{update_data['name']}' already exists")
    
    # Apply updates
    for field, value in update_data.items():
        setattr(retailer, field, value)
    
    db.commit()
    db.refresh(retailer)
    
    logger.info(f"Updated retailer: {retailer.name} (ID: {retailer.id})")
    
    retailer_data = {
        "id": retailer.id,
        "name": retailer.name,
        "link": retailer.link,
        "wholesale": retailer.wholesale,
        "cancel_for_bulk": retailer.cancel_for_bulk,
        "location": retailer.location,
        "shopify": retailer.shopify,
        "total_spend": float(retailer.total_spend) if retailer.total_spend else 0.0,
        "total_qty_of_items_ordered": retailer.total_qty_of_items_ordered or 0,
        "percent_of_cancelled_qty": float(retailer.percent_of_cancelled_qty) if retailer.percent_of_cancelled_qty else 0.0,
        "created_at": retailer.created_at.isoformat() if retailer.created_at else None,
        "updated_at": retailer.updated_at.isoformat() if retailer.updated_at else None,
    }
    
    return {
        "status": 200,
        "data": retailer_data,
        "message": f"Retailer '{retailer.name}' updated successfully"
    }


@router.delete("/{retailer_id}")
def delete_retailer(retailer_id: int, db: Session = Depends(get_db)):
    """
    Delete a retailer
    """
    retailer = db.query(Retailer).filter(Retailer.id == retailer_id).first()
    
    if not retailer:
        raise HTTPException(status_code=404, detail=f"Retailer with ID {retailer_id} not found")
    
    retailer_name = retailer.name
    db.delete(retailer)
    db.commit()
    
    logger.info(f"Deleted retailer: {retailer_name} (ID: {retailer_id})")
    
    return {
        "status": 200,
        "data": None,
        "message": f"Retailer '{retailer_name}' deleted successfully"
    }


@router.get("/stats/summary")
def get_retailers_summary(db: Session = Depends(get_db)):
    """
    Get summary statistics for all retailers
    """
    from sqlalchemy import func
    
    total_retailers = db.query(func.count(Retailer.id)).scalar()
    total_spend = db.query(func.sum(Retailer.total_spend)).scalar() or 0.0
    total_items = db.query(func.sum(Retailer.total_qty_of_items_ordered)).scalar() or 0
    
    # Count by location
    location_counts = db.query(
        Retailer.location, 
        func.count(Retailer.id)
    ).group_by(Retailer.location).all()
    
    # Count by wholesale status
    wholesale_counts = db.query(
        Retailer.wholesale, 
        func.count(Retailer.id)
    ).group_by(Retailer.wholesale).all()
    
    summary_data = {
        "total_retailers": total_retailers,
        "total_spend": float(total_spend),
        "total_items_ordered": int(total_items),
        "by_location": {loc: count for loc, count in location_counts if loc},
        "by_wholesale": {ws: count for ws, count in wholesale_counts if ws},
        "shopify_count": db.query(Retailer).filter(Retailer.shopify == True).count()
    }
    
    return {
        "status": 200,
        "data": summary_data,
        "message": ""
    }

