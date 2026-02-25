"""
Holidays API Endpoints
FastAPI routes for managing company holidays
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Any
from datetime import datetime, date
from pydantic import BaseModel
import logging

from app.config.database import get_db
from app.models.database import Holiday

router = APIRouter(prefix="/api/v1/holidays", tags=["Holidays"])
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

class HolidayCreate(BaseModel):
    """Model for creating a new holiday"""
    name: str
    date: date
    country: str  # 'US', 'PH', 'BOTH', etc.
    is_recurring: bool = False
    year: Optional[int] = None  # NULL if recurring, specific year if one-time
    description: Optional[str] = None


class HolidayUpdate(BaseModel):
    """Model for updating a holiday"""
    name: Optional[str] = None
    date: Optional[date] = None
    country: Optional[str] = None
    is_recurring: Optional[bool] = None
    year: Optional[int] = None
    description: Optional[str] = None


class HolidayResponse(BaseModel):
    """Model for holiday response"""
    id: int
    name: str
    date: date
    country: str
    is_recurring: bool
    year: Optional[int] = None
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ========================
# Holidays Endpoints
# ========================

@router.get("/")
def get_all_holidays(
    skip: int = Query(0, ge=0),
    limit: int = Query(1000, ge=1, le=10000),
    country: Optional[str] = None,
    year: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    is_recurring: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """
    Get all holidays with pagination and filters
    """
    query = db.query(Holiday)
    
    # Apply filters
    if country:
        query = query.filter(Holiday.country == country)
    if year:
        query = query.filter(
            (Holiday.year == year) | (Holiday.is_recurring == True)
        )
    if start_date:
        query = query.filter(Holiday.date >= start_date)
    if end_date:
        query = query.filter(Holiday.date <= end_date)
    if is_recurring is not None:
        query = query.filter(Holiday.is_recurring == is_recurring)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    holidays = query.order_by(Holiday.date).offset(skip).limit(limit).all()
    
    # Format response
    results = [HolidayResponse(
        id=h.id,
        name=h.name,
        date=h.date,
        country=h.country,
        is_recurring=h.is_recurring,
        year=h.year,
        description=h.description,
        created_at=h.created_at,
        updated_at=h.updated_at
    ) for h in holidays]
    
    return APIResponse(
        status=200,
        data={
            "total": total,
            "items": results
        },
        message="Holidays retrieved successfully"
    )


@router.get("/{holiday_id}")
def get_holiday_by_id(holiday_id: int, db: Session = Depends(get_db)):
    """Get a specific holiday by ID"""
    holiday = db.query(Holiday).filter(Holiday.id == holiday_id).first()
    
    if not holiday:
        raise HTTPException(status_code=404, detail="Holiday not found")
    
    result = HolidayResponse(
        id=holiday.id,
        name=holiday.name,
        date=holiday.date,
        country=holiday.country,
        is_recurring=holiday.is_recurring,
        year=holiday.year,
        description=holiday.description,
        created_at=holiday.created_at,
        updated_at=holiday.updated_at
    )
    
    return APIResponse(status=200, data=result, message="Holiday retrieved successfully")


@router.post("/")
def create_holiday(holiday: HolidayCreate, db: Session = Depends(get_db)):
    """Create a new holiday"""
    # Validate recurring logic
    if holiday.is_recurring and holiday.year is not None:
        raise HTTPException(
            status_code=400,
            detail="Recurring holidays cannot have a specific year"
        )
    if not holiday.is_recurring and holiday.year is None:
        raise HTTPException(
            status_code=400,
            detail="Non-recurring holidays must have a specific year"
        )
    
    # Check for duplicate
    existing = db.query(Holiday).filter(
        Holiday.name == holiday.name,
        Holiday.date == holiday.date,
        Holiday.country == holiday.country
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Holiday with same name, date, and country already exists"
        )
    
    # Create holiday
    new_holiday = Holiday(
        name=holiday.name,
        date=holiday.date,
        country=holiday.country,
        is_recurring=holiday.is_recurring,
        year=holiday.year,
        description=holiday.description
    )
    
    db.add(new_holiday)
    db.commit()
    db.refresh(new_holiday)
    
    result = HolidayResponse(
        id=new_holiday.id,
        name=new_holiday.name,
        date=new_holiday.date,
        country=new_holiday.country,
        is_recurring=new_holiday.is_recurring,
        year=new_holiday.year,
        description=new_holiday.description,
        created_at=new_holiday.created_at,
        updated_at=new_holiday.updated_at
    )
    
    return APIResponse(status=200, data=result, message="Holiday created successfully")


@router.put("/{holiday_id}")
def update_holiday(holiday_id: int, holiday: HolidayUpdate, db: Session = Depends(get_db)):
    """Update a holiday"""
    existing_holiday = db.query(Holiday).filter(Holiday.id == holiday_id).first()
    
    if not existing_holiday:
        raise HTTPException(status_code=404, detail="Holiday not found")
    
    # Update fields
    if holiday.name is not None:
        existing_holiday.name = holiday.name
    if holiday.date is not None:
        existing_holiday.date = holiday.date
    if holiday.country is not None:
        existing_holiday.country = holiday.country
    if holiday.is_recurring is not None:
        existing_holiday.is_recurring = holiday.is_recurring
    if holiday.year is not None:
        existing_holiday.year = holiday.year
    if holiday.description is not None:
        existing_holiday.description = holiday.description
    
    # Validate recurring logic
    if existing_holiday.is_recurring and existing_holiday.year is not None:
        existing_holiday.year = None
    
    if not existing_holiday.is_recurring and existing_holiday.year is None:
        # Set year from date if not recurring
        existing_holiday.year = existing_holiday.date.year
    
    db.commit()
    db.refresh(existing_holiday)
    
    result = HolidayResponse(
        id=existing_holiday.id,
        name=existing_holiday.name,
        date=existing_holiday.date,
        country=existing_holiday.country,
        is_recurring=existing_holiday.is_recurring,
        year=existing_holiday.year,
        description=existing_holiday.description,
        created_at=existing_holiday.created_at,
        updated_at=existing_holiday.updated_at
    )
    
    return APIResponse(status=200, data=result, message="Holiday updated successfully")


@router.delete("/{holiday_id}")
def delete_holiday(holiday_id: int, db: Session = Depends(get_db)):
    """Delete a holiday"""
    holiday = db.query(Holiday).filter(Holiday.id == holiday_id).first()
    
    if not holiday:
        raise HTTPException(status_code=404, detail="Holiday not found")
    
    db.delete(holiday)
    db.commit()
    
    return APIResponse(status=200, data={"id": holiday_id}, message="Holiday deleted successfully")


@router.get("/calendar/events")
def get_calendar_events(
    start_date: date = Query(..., description="Start date for calendar view"),
    end_date: date = Query(..., description="End date for calendar view"),
    country: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get holidays formatted for calendar display
    Returns holidays that fall within the date range
    For recurring holidays, generates instances for each year in the range
    """
    from datetime import datetime
    
    # Get start and end years
    start_year = start_date.year
    end_year = end_date.year
    
    # Query for non-recurring holidays in the date range
    non_recurring_query = db.query(Holiday).filter(
        Holiday.is_recurring == False,
        Holiday.date >= start_date,
        Holiday.date <= end_date
    )
    
    # Query for recurring holidays (they can appear in any year)
    recurring_query = db.query(Holiday).filter(
        Holiday.is_recurring == True
    )
    
    # Apply country filter to both queries
    if country:
        non_recurring_query = non_recurring_query.filter(
            (Holiday.country == country) | (Holiday.country == 'BOTH')
        )
        recurring_query = recurring_query.filter(
            (Holiday.country == country) | (Holiday.country == 'BOTH')
        )
    
    non_recurring_holidays = non_recurring_query.all()
    recurring_holidays = recurring_query.all()
    
    # Format for calendar
    events = []
    
    # Add non-recurring holidays
    for holiday in non_recurring_holidays:
        events.append({
            "id": f"holiday_{holiday.id}",
            "title": holiday.name,
            "start": holiday.date.isoformat(),
            "end": holiday.date.isoformat(),
            "allDay": True,
            "backgroundColor": "#ff6b6b",
            "borderColor": "#ff5252",
            "extendedProps": {
                "type": "holiday",
                "country": holiday.country,
                "description": holiday.description,
                "is_recurring": False,
                "holiday_id": holiday.id
            }
        })
    
    # Generate instances for recurring holidays for each year in range
    for holiday in recurring_holidays:
        # Get the month and day from the original holiday date
        original_date = holiday.date
        month = original_date.month
        day = original_date.day
        
        # Generate instances for each year in the range
        for year in range(start_year, end_year + 1):
            try:
                # Create date for this year
                holiday_date = date(year, month, day)
                
                # Check if this date falls within the requested range
                if start_date <= holiday_date <= end_date:
                    # Create unique ID for this instance
                    instance_id = f"holiday_{holiday.id}_{year}"
                    
                    events.append({
                        "id": instance_id,
                        "title": holiday.name,
                        "start": holiday_date.isoformat(),
                        "end": holiday_date.isoformat(),
                        "allDay": True,
                        "backgroundColor": "#ff6b6b",
                        "borderColor": "#ff5252",
                        "extendedProps": {
                            "type": "holiday",
                            "country": holiday.country,
                            "description": holiday.description,
                            "is_recurring": True,
                            "holiday_id": holiday.id,
                            "year": year
                        }
                    })
            except ValueError:
                # Skip invalid dates (e.g., Feb 29 in non-leap years)
                # For Feb 29, we could handle it specially, but for now just skip
                continue
    
    # Sort events by date
    events.sort(key=lambda x: x["start"])
    
    return APIResponse(
        status=200,
        data={"events": events},
        message="Calendar events retrieved successfully"
    )

