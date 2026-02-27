"""
Email Manual Review API
For resolving emails that failed parsing due to missing order_number or unique_id (e.g. Revolve cancellation)
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.database import EmailManualReview, OASourcing, PurchaseTracker, AsinBank
from app.services.revolve_parser import RevolveCancellationData, RevolveOrderItem
from app.services.hibbett_parser import HibbettShippingData, HibbettOrderItem
from app.services.snipes_parser import SnipesCancellationData, SnipesOrderItem
from app.services.shopwss_parser import ShopWSSCancellationData, ShopWSSCancellationOrderItem
from app.services.shoepalace_parser import ShoepalaceCancellationData, ShoepalaceOrderItem

router = APIRouter(prefix="/api/v1/email-manual-review", tags=["Email Manual Review"])
logger = logging.getLogger(__name__)


# ========================
# Response models
# ========================


class ManualReviewItem(BaseModel):
    unique_id: str
    size: str
    product_name: Optional[str] = None
    quantity: int = 1


class ManualReviewEntry(BaseModel):
    id: int
    gmail_message_id: str
    retailer: str
    email_type: str
    subject: Optional[str]
    extracted_order_number: Optional[str]
    extracted_items: Optional[List[dict]]
    missing_fields: str
    error_reason: Optional[str]
    status: str
    created_at: Optional[str]

    class Config:
        from_attributes = True


class ResolveRequest(BaseModel):
    """Payload for resolving a manual review entry - supply the missing fields."""
    order_number: Optional[str] = None  # Required if missing_fields contains 'order_number'
    unique_id: Optional[str] = None     # Required if missing_fields contains 'unique_id'
    size: Optional[str] = None         # Required when supplying unique_id (type 1)
    quantity: int = 1
    items: Optional[List[ManualReviewItem]] = None  # For multi-item (e.g. ShopWSS partial cancel)


# ========================
# Endpoints
# ========================


def _success(data, message: str = "OK"):
    return {"status": 200, "data": data, "message": message}


@router.get("")
def list_manual_review(
    status: str = Query("pending", description="Filter by status"),
    retailer: Optional[str] = Query(None, description="Filter by retailer"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List manual review entries (default: pending only)."""
    q = db.query(EmailManualReview).filter(EmailManualReview.status == status)
    if retailer:
        q = q.filter(EmailManualReview.retailer == retailer)
    total = q.count()
    rows = q.order_by(EmailManualReview.created_at.desc()).offset(offset).limit(limit).all()
    items = [
        {
            "id": r.id,
            "gmail_message_id": r.gmail_message_id,
            "retailer": r.retailer,
            "email_type": r.email_type,
            "subject": r.subject,
            "extracted_order_number": r.extracted_order_number,
            "extracted_items": r.extracted_items,
            "missing_fields": (r.missing_fields or "").split(",") if r.missing_fields else [],
            "error_reason": r.error_reason,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return _success({"items": items, "total": total})


@router.get("/count")
def pending_count(db: Session = Depends(get_db)):
    """Get count of pending items (for notification badge)."""
    count = db.query(EmailManualReview).filter(EmailManualReview.status == "pending").count()
    return _success({"pending_count": count})


@router.get("/{entry_id}")
def get_manual_review(entry_id: int, db: Session = Depends(get_db)):
    """Get a single manual review entry."""
    entry = db.query(EmailManualReview).filter(EmailManualReview.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    entry_data = {
        "id": entry.id,
        "gmail_message_id": entry.gmail_message_id,
        "retailer": entry.retailer,
        "email_type": entry.email_type,
        "subject": entry.subject,
        "extracted_order_number": entry.extracted_order_number,
        "extracted_items": entry.extracted_items,
        "missing_fields": (entry.missing_fields or "").split(",") if entry.missing_fields else [],
        "error_reason": entry.error_reason,
        "status": entry.status,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
    }
    return _success(entry_data)


@router.post("/{entry_id}/resolve")
def resolve_manual_review(
    entry_id: int,
    body: ResolveRequest,
    db: Session = Depends(get_db),
):
    """
    Resolve a manual review entry by supplying missing data and applying the cancellation.
    For Revolve: builds RevolveCancellationData and runs the same logic as automatic processing.
    """
    entry = db.query(EmailManualReview).filter(EmailManualReview.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    if entry.status != "pending":
        raise HTTPException(status_code=400, detail=f"Entry already {entry.status}")

    missing = [x.strip() for x in (entry.missing_fields or "").split(",") if x.strip()]
    order_number = entry.extracted_order_number or body.order_number
    items_payload = list(entry.extracted_items or [])

    if "order_number" in missing and not body.order_number:
        raise HTTPException(status_code=400, detail="order_number is required")
    if "order_number" in missing:
        order_number = body.order_number

    # When missing_fields is empty, extracted_items may have full data - use as-is (e.g. no matching records case)
    if "unique_id" in missing:
        if body.items and len(body.items) > 0:
            items_payload = [
                {
                    "unique_id": it.unique_id,
                    "size": it.size,
                    "product_name": it.product_name,
                    "quantity": it.quantity or 1,
                }
                for it in body.items
            ]
            if any(not it.get("unique_id") or not it.get("size") for it in items_payload):
                raise HTTPException(status_code=400, detail="Each item must have unique_id and size")
        elif body.unique_id and body.size:
            items_payload = [{
                "unique_id": body.unique_id,
                "size": body.size,
                "product_name": None,
                "quantity": body.quantity,
            }]
        else:
            raise HTTPException(status_code=400, detail="unique_id and size are required (or provide items for multi-item)")

    if not order_number:
        raise HTTPException(status_code=400, detail="order_number is missing")
    if not items_payload and not (entry.retailer == "snipes" and entry.email_type == "cancellation"):
        raise HTTPException(status_code=400, detail="No items to process")

    from app.services.retailer_order_update_processor import RetailerOrderUpdateProcessor
    from datetime import datetime

    processor = RetailerOrderUpdateProcessor(db)

    if entry.retailer == "snipes" and entry.email_type == "cancellation" and not items_payload:
        # Snipes full cancellation: order_number only, items=[] means cancel all
        cancellation_data = SnipesCancellationData(order_number=order_number, items=[])
        success, error_msg = processor._process_snipes_cancellation_update(cancellation_data)
        action_msg = "Processed full cancellation"
    elif entry.retailer == "hibbett" and entry.email_type == "shipping":
        # Hibbett shipping: from user input or extracted_items (when data complete, no matching records)
        if not items_payload:
            raise HTTPException(status_code=400, detail="No items to process")
        for it in items_payload:
            if not it.get("unique_id") or not it.get("size"):
                raise HTTPException(
                    status_code=400,
                    detail="Items missing unique_id/size - please supply manually (order confirmation may not be processed yet)",
                )
        hibbett_items = [
            HibbettOrderItem(
                unique_id=it["unique_id"],
                size=it["size"],
                quantity=int(it.get("quantity", 1)),
                product_name=it.get("product_name"),
            )
            for it in items_payload
        ]
        shipping_data = HibbettShippingData(order_number=order_number, items=hibbett_items)
        success, error_msg = processor._process_hibbett_shipping_update(shipping_data)
        action_msg = "Processed shipping update"
    elif entry.retailer == "shopwss" and entry.email_type == "cancellation":
        # ShopWSS partial cancellation: user supplies unique_id per item
        shopwss_items = [
            ShopWSSCancellationOrderItem(
                unique_id=it["unique_id"],
                size=it["size"],
                quantity=int(it.get("quantity", 1)),
                product_name=it.get("product_name"),
            )
            for it in items_payload
        ]
        cancellation_data = ShopWSSCancellationData(order_number=order_number, items=shopwss_items)
        success, error_msg = processor._process_shopwss_cancellation_update(cancellation_data)
        action_msg = "Processed ShopWSS cancellation"
    elif entry.retailer == "shoepalace" and entry.email_type == "cancellation":
        # Shoe Palace cancellation: user supplies unique_id per item
        shoepalace_items = [
            ShoepalaceOrderItem(
                unique_id=it["unique_id"],
                size=it["size"],
                quantity=int(it.get("quantity", 1)),
                product_name=it.get("product_name"),
            )
            for it in items_payload
        ]
        cancellation_data = ShoepalaceCancellationData(order_number=order_number, items=shoepalace_items)
        success, error_msg = processor._process_shoepalace_cancellation_update(cancellation_data)
        action_msg = "Processed Shoe Palace cancellation"
    else:
        # Revolve cancellation (default)
        items = [
            RevolveOrderItem(
                unique_id=it["unique_id"],
                size=it["size"],
                quantity=int(it.get("quantity", 1)),
                product_name=it.get("product_name"),
            )
            for it in items_payload
        ]
        cancellation_data = RevolveCancellationData(order_number=order_number, items=items)
        success, error_msg = processor._process_revolve_cancellation_update(cancellation_data)
        action_msg = "Processed cancellation"

    if success:
        # Update Gmail label from Manual-Review/Error to Processed (also removes those labels)
        processor._add_processed_label(entry.gmail_message_id, entry.email_type)
        entry.status = "resolved"
        entry.resolved_at = datetime.utcnow()
        db.commit()
        return _success({
            "success": True,
            "message": f"{action_msg} for order {order_number}",
            "items_count": len(items_payload),
        })
    else:
        raise HTTPException(status_code=400, detail=error_msg or "Processing failed")


@router.post("/{entry_id}/dismiss")
def dismiss_manual_review(entry_id: int, db: Session = Depends(get_db)):
    """Mark a manual review entry as dismissed (no action taken)."""
    entry = db.query(EmailManualReview).filter(EmailManualReview.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    if entry.status != "pending":
        raise HTTPException(status_code=400, detail=f"Entry already {entry.status}")

    from datetime import datetime
    entry.status = "dismissed"
    entry.resolved_at = datetime.utcnow()
    db.commit()
    return _success({"success": True, "message": "Entry dismissed"})
