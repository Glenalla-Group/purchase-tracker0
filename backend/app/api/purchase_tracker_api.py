"""
Purchase Tracker API Endpoints
FastAPI routes for accessing purchase tracker data
"""

from fastapi import APIRouter, Depends, HTTPException, Query  # pyright: ignore[reportMissingImports]
from sqlalchemy.orm import Session, joinedload, selectinload  # pyright: ignore[reportMissingImports]
from typing import List, Optional
from datetime import date, datetime
from pydantic import BaseModel, field_validator  # pyright: ignore[reportMissingImports]
import logging

from app.config.database import get_db
from app.models.database import AsinBank, OASourcing, PurchaseTracker, Retailer

router = APIRouter(prefix="/api/v1/purchase-tracker", tags=["Purchase Tracker"])
logger = logging.getLogger(__name__)


# ========================
# Request Models
# ========================

class AsinSubmittal(BaseModel):
    """Model for ASIN data in lead submittal"""
    asin: Optional[str] = None
    size: Optional[str] = None
    recommendedQuantity: Optional[int] = None


class LeadSubmittalRequest(BaseModel):
    """Model for creating a new lead submittal"""
    submittedBy: Optional[str] = None
    productName: Optional[str] = None
    productSku: Optional[str] = None
    retailerLink: str  # Required
    retailerName: Optional[str] = None
    amazonLink: str  # Required
    uniqueId: Optional[str] = None
    ppu: str  # Required
    rsp: str  # Required
    margin: str  # Required
    pros: Optional[str] = None
    cons: Optional[str] = None
    otherNotes: Optional[str] = None
    promoCode: Optional[str] = None
    status: Optional[str] = None  # Will default to 'draft' in endpoint
    asins: List[AsinSubmittal] = []


class LeadUpdateRequest(BaseModel):
    """Model for updating an existing lead"""
    productName: Optional[str] = None
    retailerLink: Optional[str] = None
    amazonLink: Optional[str] = None
    uniqueId: Optional[str] = None
    purchased: Optional[str] = None
    purchaseMoreIfAvailable: Optional[str] = None
    monitored: Optional[bool] = None
    pros: Optional[str] = None
    cons: Optional[str] = None
    otherNotesConcerns: Optional[str] = None
    headOfProductReviewNotes: Optional[str] = None
    feedbackAndNotesOnQuantity: Optional[str] = None
    pairsPerLeadId: Optional[int] = None
    pairsPerSku: Optional[int] = None
    salesRank: Optional[str] = None
    ppu: Optional[float] = None
    rsp: Optional[float] = None
    margin: Optional[float] = None
    asin1BuyBox: Optional[float] = None
    asin1NewPrice: Optional[float] = None
    pickPackFee: Optional[float] = None
    referralFee: Optional[float] = None
    totalFee: Optional[float] = None
    promoCode: Optional[str] = None
    status: Optional[str] = None


class AsinUpdateRequest(BaseModel):
    """Model for updating an ASIN in a lead"""
    asin: str
    size: str
    recommended_quantity: int


class AsinAddRequest(BaseModel):
    """Model for adding an ASIN to a lead"""
    asin: str
    size: str
    recommended_quantity: int = 1


class ManualPurchaseRequest(BaseModel):
    """Model for manually creating a purchase tracker entry"""
    unique_id: str  # Product unique ID from OA Sourcing (e.g., retailer SKU)
    size: str  # Product size
    qty: int  # Quantity purchased
    order_number: str  # Order number (extracted from emails)


class PurchaseUpdateRequest(BaseModel):
    """Model for updating a purchase tracker entry"""
    # Quantities
    og_qty: Optional[int] = None
    final_qty: Optional[int] = None
    cancelled_qty: Optional[int] = None
    
    # Fulfillment tracking
    shipped_to_pw: Optional[int] = None
    arrived: Optional[int] = None
    checked_in: Optional[int] = None
    shipped_out: Optional[int] = None
    tracking: Optional[str] = None
    delivery_date: Optional[date] = None
    location: Optional[str] = None
    address: Optional[str] = None
    in_bound: Optional[bool] = None
    
    # FBA fields
    outbound_name: Optional[str] = None
    fba_shipment: Optional[str] = None
    fba_msku: Optional[str] = None
    
    # Other fields
    status: Optional[str] = None
    audited: Optional[bool] = None
    notes: Optional[str] = None
    validation_bank: Optional[str] = None
    
    @field_validator('delivery_date', mode='before')
    @classmethod
    def empty_date_to_none(cls, v):
        """Convert empty strings to None for optional date fields"""
        if v == '' or v is None:
            return None
        return v
    
    @field_validator('tracking', 'location', 'address', 'outbound_name', 'fba_shipment', 'fba_msku', 'status', 'notes', 'validation_bank', mode='before')
    @classmethod
    def empty_string_to_none(cls, v):
        """Convert empty strings to None for optional string fields"""
        if v == '':
            return None
        return v


# ========================
# OA Sourcing Endpoints
# ========================

@router.get("/leads")
def get_all_leads(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    retailer: Optional[str] = None,
    product_name: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get all OA sourcing leads with pagination and filters - includes all fields from CSV
    """
    query = db.query(OASourcing)
    
    if retailer:
        # Filter by retailer through relationship
        query = query.join(Retailer, OASourcing.retailer_id == Retailer.id).filter(
            Retailer.name.ilike(f"%{retailer}%")
        )
    
    if product_name:
        query = query.filter(OASourcing.product_name.ilike(f"%{product_name}%"))
    
    total = query.count()
    leads = query.offset(skip).limit(limit).all()
    
    # Helper function to get ASINs - Two approaches:
    # Approach 1: Via foreign key relationships (complex but uses DB relationships)
    # Approach 2: Direct query by lead_id (simpler and more reliable)
    
    def get_lead_asins_via_relationships(lead):
        """Get ASINs using foreign key relationships"""
        asins = []
        for i in range(1, 16):
            asin_id = getattr(lead, f'asin{i}_id', None)
            if asin_id:
                # Query asin_bank directly using the foreign key ID
                asin_record = db.query(AsinBank).filter_by(id=asin_id).first()
                if asin_record:
                    recommended_qty = getattr(lead, f'asin{i}_recommended_quantity', None)
                    asins.append({
                        "id": asin_record.id,
                        "asin": asin_record.asin,
                        "size": asin_record.size,
                        "recommended_quantity": recommended_qty if recommended_qty else 1
                    })
        return asins
    
    def get_lead_asins_via_query(lead_id):
        """Get ASINs by querying asin_bank with lead_id (simpler approach)"""
        asin_records = db.query(AsinBank).filter(AsinBank.lead_id == lead_id).all()
        return [
            {
                "id": asin.id,
                "asin": asin.asin,
                "size": asin.size,
                "recommended_quantity": 1  # Default, since quantity is in oa_sourcing
            }
            for asin in asin_records
        ]
    
    # Use relationship-based approach (more complete data with quantities)
    def get_lead_asins(lead):
        asins = get_lead_asins_via_relationships(lead)
        if not asins:
            # Fallback to query-based approach if relationships don't work
            asins = get_lead_asins_via_query(lead.lead_id)
        logger.info(f"[OA-SOURCING] Lead {lead.lead_id} has {len(asins)} ASINs")
        return asins
    
    return {
        "status": 200,
        "message": "Leads retrieved successfully",
        "data": {
            "total": total,
            "skip": skip,
            "limit": limit,
            "items": [
                {
                    "id": lead.id,
                    "lead_id": lead.lead_id,
                    "timestamp": lead.timestamp.isoformat() if lead.timestamp else None,
                    "submitted_by": lead.submitted_by,
                    "sourcer": lead.sourcer,
                    "retailer_id": lead.retailer_id,
                    "retailer_name": lead.retailer.name if lead.retailer else None,
                    "product_name": lead.product_name,
                    "product_sku": lead.product_sku,
                    "retailer_link": lead.retailer_link,
                    "amazon_link": lead.amazon_link,
                    "unique_id": lead.unique_id,
                    "purchased": lead.purchased,
                    "purchase_more": lead.purchase_more_if_available,
                    "pros": lead.pros,
                    "cons": lead.cons,
                    "other_notes": lead.other_notes_concerns,
                    "head_review": lead.head_of_product_review_notes,
                    "feedback_qty": lead.feedback_and_notes_on_quantity,
                    "suggested_qty": lead.suggested_total_qty,
                    "pairs_per_lead": lead.pairs_per_lead_id,
                    "pairs_per_sku": lead.pairs_per_sku,
                    "ppu": float(lead.ppu_including_ship) if lead.ppu_including_ship else None,
                    "rsp": float(lead.rsp) if lead.rsp else None,
                    "margin": float(lead.margin) if lead.margin else None,
                    "promo_code": lead.promo_code,
                    "sales_rank": lead.sales_rank,
                    "buy_box": lead.asin1_buy_box,
                    "new_price": lead.asin1_new_price,
                    "pick_pack_fee": float(lead.pick_pack_fee) if lead.pick_pack_fee else None,
                    "referral_fee": float(lead.referral_fee) if lead.referral_fee else None,
                    "total_fee": float(lead.total_fee) if lead.total_fee else None,
                    "margin_using_rsp": float(lead.margin_using_rsp) if lead.margin_using_rsp else None,
                    "monitored": lead.monitored,
                    "asins": get_lead_asins(lead)
                }
                for lead in leads
            ]
        }
    }


@router.get("/asin-bank")
def get_asin_bank(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    lead_id: Optional[str] = None,
    asin: Optional[str] = None,
    size: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get all ASINs from the ASIN Bank with pagination and filters
    """
    query = db.query(AsinBank)
    
    if lead_id:
        query = query.filter(AsinBank.lead_id.ilike(f"%{lead_id}%"))
    
    if asin:
        query = query.filter(AsinBank.asin.ilike(f"%{asin}%"))
    
    if size:
        query = query.filter(AsinBank.size.ilike(f"%{size}%"))
    
    total = query.count()
    asins = query.offset(skip).limit(limit).all()
    
    return {
        "status": 200,
        "message": "ASIN Bank data retrieved successfully",
        "data": {
            "total": total,
            "skip": skip,
            "limit": limit,
            "items": [
                {
                    "id": asin_record.id,
                    "lead_id": asin_record.lead_id,
                    "size": asin_record.size,
                    "asin": asin_record.asin,
                    "created_at": asin_record.created_at.isoformat() if asin_record.created_at else None
                }
                for asin_record in asins
            ]
        }
    }


class AsinBankCreateRequest(BaseModel):
    """Model for creating a new ASIN manually"""
    lead_id: str
    asin: str
    size: Optional[str] = None


@router.post("/asin-bank")
def create_asin(asin_data: AsinBankCreateRequest, db: Session = Depends(get_db)):
    """
    Manually create a new ASIN in the ASIN Bank.
    Reuses existing AsinBank for same (asin, size) to avoid duplicates.
    """
    try:
        # Check if ASIN already exists for this lead
        existing_for_lead = db.query(AsinBank).filter_by(
            lead_id=asin_data.lead_id,
            asin=asin_data.asin,
            size=asin_data.size
        ).first()
        if existing_for_lead:
            return {
                "status": 200,
                "message": f"ASIN '{asin_data.asin}' (size '{asin_data.size}') already exists for lead '{asin_data.lead_id}'",
                "data": {"id": existing_for_lead.id, "lead_id": existing_for_lead.lead_id, "asin": existing_for_lead.asin, "size": existing_for_lead.size}
            }
        
        # Check if (asin, size) exists globally - reuse to avoid duplicates
        existing_global = db.query(AsinBank).filter_by(
            asin=asin_data.asin,
            size=asin_data.size
        ).first()
        if existing_global:
            return {
                "status": 200,
                "message": f"ASIN '{asin_data.asin}' (size '{asin_data.size}') already exists in bank (lead_id={existing_global.lead_id}). Link to your lead via POST /leads/{{lead_id}}/asins",
                "data": {"id": existing_global.id, "lead_id": existing_global.lead_id, "asin": existing_global.asin, "size": existing_global.size}
            }
        
        # Create new ASIN record
        new_asin = AsinBank(
            lead_id=asin_data.lead_id,
            asin=asin_data.asin,
            size=asin_data.size
        )
        
        db.add(new_asin)
        db.commit()
        db.refresh(new_asin)
        
        logger.info(f"Manually created ASIN: lead_id={asin_data.lead_id}, asin={asin_data.asin}, size={asin_data.size}")
        
        return {
            "status": 200,
            "message": "ASIN created successfully",
            "data": {
                "id": new_asin.id,
                "lead_id": new_asin.lead_id,
                "asin": new_asin.asin,
                "size": new_asin.size
            }
        }
        
    except Exception as e:
        db.rollback()
        error_msg = f"Error creating ASIN: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "status": -1,
            "message": error_msg,
            "data": None
        }


class AsinBankDeleteRequest(BaseModel):
    """Model for bulk deleting ASINs"""
    ids: List[int]


@router.delete("/asin-bank")
def delete_asins(delete_data: AsinBankDeleteRequest, db: Session = Depends(get_db)):
    """
    Bulk delete ASINs from the ASIN Bank
    """
    try:
        if not delete_data.ids:
            return {
                "status": -1,
                "message": "No ASIN IDs provided",
                "data": None
            }
        
        # Find all ASINs to delete
        asins_to_delete = db.query(AsinBank).filter(AsinBank.id.in_(delete_data.ids)).all()
        
        if not asins_to_delete:
            return {
                "status": -1,
                "message": "No ASINs found with the provided IDs",
                "data": None
            }
        
        deleted_count = len(asins_to_delete)
        
        # Delete all found ASINs
        for asin in asins_to_delete:
            db.delete(asin)
        
        db.commit()
        
        logger.info(f"Bulk deleted {deleted_count} ASINs: IDs={delete_data.ids}")
        
        return {
            "status": 200,
            "message": f"Successfully deleted {deleted_count} ASIN(s)",
            "data": {
                "deleted_count": deleted_count,
                "deleted_ids": delete_data.ids
            }
        }
        
    except Exception as e:
        db.rollback()
        error_msg = f"Error deleting ASINs: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "status": -1,
            "message": error_msg,
            "data": None
        }


@router.get("/leads/{lead_id}")
def get_lead_by_id(lead_id: str, db: Session = Depends(get_db)):
    """
    Get detailed information for a specific lead including all ASINs
    """
    lead = db.query(OASourcing)\
        .options(
            joinedload(OASourcing.asin1_ref),
            joinedload(OASourcing.asin2_ref),
            joinedload(OASourcing.asin3_ref),
            joinedload(OASourcing.asin4_ref),
            joinedload(OASourcing.asin5_ref),
            joinedload(OASourcing.asin6_ref),
            joinedload(OASourcing.asin7_ref),
            joinedload(OASourcing.asin8_ref),
            joinedload(OASourcing.asin9_ref),
            joinedload(OASourcing.asin10_ref),
            joinedload(OASourcing.asin11_ref),
            joinedload(OASourcing.asin12_ref),
            joinedload(OASourcing.asin13_ref),
            joinedload(OASourcing.asin14_ref),
            joinedload(OASourcing.asin15_ref)
        )\
        .filter_by(lead_id=lead_id)\
        .first()
    
    if not lead:
        return {
            "status": -1,
            "message": "Lead not found",
            "data": None
        }
    
    # Collect ASINs (same structure as list endpoint)
    asins = []
    for i in range(1, 16):
        asin_ref = getattr(lead, f'asin{i}_ref', None)
        if asin_ref:
            recommended_qty = getattr(lead, f'asin{i}_recommended_quantity', None)
            asins.append({
                "id": asin_ref.id,
                "asin": asin_ref.asin,
                "size": asin_ref.size,
                "recommended_quantity": recommended_qty if recommended_qty is not None else 1
            })

    # Return same structure as list endpoint for consistency (frontend Lead interface)
    return {
        "status": 200,
        "message": "Lead retrieved successfully",
        "data": {
            "id": lead.id,
            "lead_id": lead.lead_id,
            "timestamp": lead.timestamp.isoformat() if lead.timestamp else None,
            "submitted_by": lead.submitted_by,
            "sourcer": lead.sourcer,
            "retailer_id": lead.retailer_id,
            "retailer_name": lead.retailer.name if lead.retailer else None,
            "product_name": lead.product_name,
            "product_sku": lead.product_sku,
            "retailer_link": lead.retailer_link,
            "amazon_link": lead.amazon_link,
            "unique_id": lead.unique_id,
            "purchased": lead.purchased,
            "purchase_more": lead.purchase_more_if_available,
            "pros": lead.pros,
            "cons": lead.cons,
            "other_notes": lead.other_notes_concerns,
            "head_review": lead.head_of_product_review_notes,
            "feedback_qty": lead.feedback_and_notes_on_quantity,
            "suggested_qty": lead.suggested_total_qty,
            "pairs_per_lead": lead.pairs_per_lead_id,
            "pairs_per_sku": lead.pairs_per_sku,
            "ppu": float(lead.ppu_including_ship) if lead.ppu_including_ship else None,
            "rsp": float(lead.rsp) if lead.rsp else None,
            "margin": float(lead.margin) if lead.margin else None,
            "promo_code": lead.promo_code,
            "sales_rank": lead.sales_rank,
            "buy_box": lead.asin1_buy_box,
            "new_price": lead.asin1_new_price,
            "pick_pack_fee": float(lead.pick_pack_fee) if lead.pick_pack_fee else None,
            "referral_fee": float(lead.referral_fee) if lead.referral_fee else None,
            "total_fee": float(lead.total_fee) if lead.total_fee else None,
            "margin_using_rsp": float(lead.margin_using_rsp) if lead.margin_using_rsp else None,
            "monitored": lead.monitored,
            "status": lead.status,
            "asins": asins
        }
    }


@router.patch("/leads/{lead_id}")
def update_lead(lead_id: str, update_data: LeadUpdateRequest, db: Session = Depends(get_db)):
    """
    Update an existing lead by lead_id
    """
    try:
        # Find the lead
        lead = db.query(OASourcing).filter_by(lead_id=lead_id).first()
        
        if not lead:
            raise HTTPException(status_code=404, detail=f"Lead with ID {lead_id} not found")
        
        # Update fields if provided
        if update_data.productName is not None:
            lead.product_name = update_data.productName
            lead.product_name_pt_input = update_data.productName
        
        if update_data.retailerLink is not None:
            lead.retailer_link = update_data.retailerLink
        
        if update_data.amazonLink is not None:
            lead.amazon_link = update_data.amazonLink
        
        if update_data.uniqueId is not None:
            lead.unique_id = update_data.uniqueId
        
        if update_data.purchased is not None:
            lead.purchased = update_data.purchased
        
        if update_data.purchaseMoreIfAvailable is not None:
            lead.purchase_more_if_available = update_data.purchaseMoreIfAvailable
        
        if update_data.monitored is not None:
            lead.monitored = update_data.monitored
        
        if update_data.pros is not None:
            lead.pros = update_data.pros
        
        if update_data.cons is not None:
            lead.cons = update_data.cons
        
        if update_data.otherNotesConcerns is not None:
            lead.other_notes_concerns = update_data.otherNotesConcerns
        
        if update_data.headOfProductReviewNotes is not None:
            lead.head_of_product_review_notes = update_data.headOfProductReviewNotes
        
        if update_data.feedbackAndNotesOnQuantity is not None:
            lead.feedback_and_notes_on_quantity = update_data.feedbackAndNotesOnQuantity
        
        if update_data.pairsPerLeadId is not None:
            lead.pairs_per_lead_id = update_data.pairsPerLeadId
        
        if update_data.pairsPerSku is not None:
            lead.pairs_per_sku = update_data.pairsPerSku
        
        if update_data.salesRank is not None:
            lead.sales_rank = update_data.salesRank
        
        if update_data.ppu is not None:
            lead.ppu_including_ship = update_data.ppu
        
        if update_data.rsp is not None:
            lead.rsp = update_data.rsp
        
        if update_data.margin is not None:
            lead.margin = update_data.margin
        
        if update_data.asin1BuyBox is not None:
            lead.asin1_buy_box = update_data.asin1BuyBox
        
        if update_data.asin1NewPrice is not None:
            lead.asin1_new_price = update_data.asin1NewPrice
        
        if update_data.pickPackFee is not None:
            lead.pick_pack_fee = update_data.pickPackFee
        
        if update_data.referralFee is not None:
            lead.referral_fee = update_data.referralFee
        
        if update_data.totalFee is not None:
            lead.total_fee = update_data.totalFee
        
        if update_data.promoCode is not None:
            lead.promo_code = update_data.promoCode
        
        if update_data.status is not None:
            lead.status = update_data.status
        
        # Commit changes
        db.commit()
        db.refresh(lead)
        
        logger.info(f"Lead {lead_id} updated successfully")
        
        return {
            "status": 200,
            "message": "Lead updated successfully",
            "data": {
                "lead_id": lead.lead_id,
                "product_name": lead.product_name,
                "updated_fields": {k: v for k, v in update_data.dict(exclude_unset=True).items()}
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating lead {lead_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update lead: {str(e)}")


@router.delete("/leads/{lead_id}")
def delete_lead(lead_id: str, db: Session = Depends(get_db)):
    """
    Delete a lead by lead_id.
    Returns error if lead has linked purchase records (constraint).
    """
    try:
        lead = db.query(OASourcing).filter_by(lead_id=lead_id).first()
        if not lead:
            return {
                "status": -1,
                "message": f"Lead with ID {lead_id} not found",
                "data": None
            }

        product_name = lead.product_name
        lead_db_id = lead.id

        # Check for PurchaseTracker records - block delete if any exist
        count = db.query(PurchaseTracker).filter(
            PurchaseTracker.oa_sourcing_id == lead_db_id
        ).count()
        if count > 0:
            pname = product_name or "(no name)"
            msg = f"Purchase Record Constraint: Cannot delete. Product \"{pname}\" has {count} linked purchase record(s)."
            return {"status": -1, "message": msg, "data": None}

        # Delete the lead
        db.delete(lead)
        db.commit()
        
        logger.info(f"Lead {lead_id} ({product_name}) deleted successfully")
        
        return {
            "status": 200,
            "message": f"Lead {lead_id} deleted successfully",
            "data": {
                "lead_id": lead_id,
                "product_name": product_name,
                "deleted": True
            }
        }
        
    except Exception as e:
        db.rollback()
        error_msg = f"Error deleting lead {lead_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "status": -1,
            "message": error_msg,
            "data": None
        }


@router.post("/leads/{lead_id}/asins")
def add_asin_to_lead(lead_id: str, asin_data: AsinAddRequest, db: Session = Depends(get_db)):
    """
    Add an ASIN to a lead at the next available position (1-15)
    """
    try:
        # Find the lead
        lead = db.query(OASourcing).filter_by(lead_id=lead_id).first()
        
        if not lead:
            return {
                "status": -1,
                "message": f"Lead with ID {lead_id} not found",
                "data": None
            }
        
        # Find next available position (1-15)
        position = None
        for i in range(1, 16):
            asin_id_field = getattr(lead, f'asin{i}_id', None)
            if not asin_id_field:
                position = i
                break
        
        if not position:
            return {
                "status": -1,
                "message": "Maximum 15 ASINs allowed per lead. Please delete an existing ASIN first.",
                "data": None
            }
        
        # Check if (asin, size) exists: for this lead first, else globally (reuse)
        existing_for_lead = db.query(AsinBank).filter_by(
            lead_id=lead_id,
            asin=asin_data.asin,
            size=asin_data.size
        ).first()
        existing_global = db.query(AsinBank).filter_by(
            asin=asin_data.asin,
            size=asin_data.size
        ).first() if not existing_for_lead else None
        
        if existing_for_lead:
            asin_bank_id = existing_for_lead.id
        elif existing_global:
            asin_bank_id = existing_global.id
            # Skip if already linked to this lead (avoid duplicate linkage)
            for j in range(1, 16):
                if getattr(lead, f'asin{j}_id', None) == asin_bank_id:
                    return {
                        "status": 200,
                        "message": f"ASIN {asin_data.asin} (size: {asin_data.size}) already linked to this lead at position {j}",
                        "data": {"position": j, "asin": asin_data.asin, "size": asin_data.size}
                    }
            logger.info(f"[REUSE] ASIN {asin_data.asin} (size: {asin_data.size}) already in bank, linking to lead {lead_id}")
        else:
            # Create new ASIN in asin_bank
            new_asin = AsinBank(
                lead_id=lead_id,
                asin=asin_data.asin,
                size=asin_data.size
            )
            db.add(new_asin)
            db.flush()
            asin_bank_id = new_asin.id
        
        # Set the ASIN at the found position
        setattr(lead, f'asin{position}_id', asin_bank_id)
        setattr(lead, f'asin{position}_recommended_quantity', asin_data.recommended_quantity)
        
        db.commit()
        db.refresh(lead)
        
        logger.info(f"Added ASIN {asin_data.asin} to lead {lead_id} at position {position}")
        
        return {
            "status": 200,
            "message": f"ASIN added successfully at position {position}",
            "data": {
                "position": position,
                "asin": asin_data.asin,
                "size": asin_data.size,
                "recommended_quantity": asin_data.recommended_quantity
            }
        }
        
    except Exception as e:
        db.rollback()
        error_msg = f"Error adding ASIN to lead {lead_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "status": -1,
            "message": error_msg,
            "data": None
        }


@router.patch("/leads/{lead_id}/asins/{position}")
def update_asin_in_lead(
    lead_id: str, 
    position: int, 
    asin_data: AsinUpdateRequest, 
    db: Session = Depends(get_db)
):
    """
    Update an ASIN at a specific position (1-15) in a lead
    """
    try:
        if position < 1 or position > 15:
            return {
                "status": -1,
                "message": "Position must be between 1 and 15",
                "data": None
            }
        
        # Find the lead
        lead = db.query(OASourcing).filter_by(lead_id=lead_id).first()
        
        if not lead:
            return {
                "status": -1,
                "message": f"Lead with ID {lead_id} not found",
                "data": None
            }
        
        # Check if ASIN exists at this position
        current_asin_id = getattr(lead, f'asin{position}_id', None)
        if not current_asin_id:
            return {
                "status": -1,
                "message": f"No ASIN found at position {position}",
                "data": None
            }
        
        # Check if ASIN with same asin+size already exists in asin_bank for this lead
        existing_asin = db.query(AsinBank).filter_by(
            lead_id=lead_id,
            asin=asin_data.asin,
            size=asin_data.size
        ).first()
        
        if existing_asin:
            # Use existing ASIN (don't create duplicate)
            asin_bank_id = existing_asin.id
        else:
            # Create NEW ASIN in asin_bank (don't update the old one)
            new_asin = AsinBank(
                lead_id=lead_id,
                asin=asin_data.asin,
                size=asin_data.size
            )
            db.add(new_asin)
            db.flush()
            asin_bank_id = new_asin.id
        
        # Note: We don't delete or update the old ASIN in asin_bank
        # The old ASIN record remains in asin_bank table unchanged
        
        # Update position with new ASIN and quantity
        setattr(lead, f'asin{position}_id', asin_bank_id)
        setattr(lead, f'asin{position}_recommended_quantity', asin_data.recommended_quantity)
        
        db.commit()
        db.refresh(lead)
        
        logger.info(f"Updated ASIN at position {position} for lead {lead_id}")
        
        return {
            "status": 200,
            "message": f"ASIN updated successfully at position {position}",
            "data": {
                "position": position,
                "asin": asin_data.asin,
                "size": asin_data.size,
                "recommended_quantity": asin_data.recommended_quantity
            }
        }
        
    except Exception as e:
        db.rollback()
        error_msg = f"Error updating ASIN at position {position} for lead {lead_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "status": -1,
            "message": error_msg,
            "data": None
        }


@router.delete("/leads/{lead_id}/asins/{position}")
def delete_asin_from_lead(lead_id: str, position: int, db: Session = Depends(get_db)):
    """
    Delete an ASIN at a specific position (1-15) from a lead
    """
    try:
        if position < 1 or position > 15:
            return {
                "status": -1,
                "message": "Position must be between 1 and 15",
                "data": None
            }
        
        # Find the lead
        lead = db.query(OASourcing).filter_by(lead_id=lead_id).first()
        
        if not lead:
            return {
                "status": -1,
                "message": f"Lead with ID {lead_id} not found",
                "data": None
            }
        
        # Check if ASIN exists at this position
        asin_id = getattr(lead, f'asin{position}_id', None)
        if not asin_id:
            return {
                "status": -1,
                "message": f"No ASIN found at position {position}",
                "data": None
            }
        
        # Clear the position
        setattr(lead, f'asin{position}_id', None)
        setattr(lead, f'asin{position}_recommended_quantity', None)
        
        # Check if this ASIN is used by other leads
        asin_bank = db.query(AsinBank).filter_by(id=asin_id).first()
        if asin_bank:
            # Check if any other lead uses this ASIN
            other_lead_uses = db.query(OASourcing).filter(
                (OASourcing.asin1_id == asin_id) |
                (OASourcing.asin2_id == asin_id) |
                (OASourcing.asin3_id == asin_id) |
                (OASourcing.asin4_id == asin_id) |
                (OASourcing.asin5_id == asin_id) |
                (OASourcing.asin6_id == asin_id) |
                (OASourcing.asin7_id == asin_id) |
                (OASourcing.asin8_id == asin_id) |
                (OASourcing.asin9_id == asin_id) |
                (OASourcing.asin10_id == asin_id) |
                (OASourcing.asin11_id == asin_id) |
                (OASourcing.asin12_id == asin_id) |
                (OASourcing.asin13_id == asin_id) |
                (OASourcing.asin14_id == asin_id) |
                (OASourcing.asin15_id == asin_id)
            ).filter(OASourcing.id != lead.id).first()
            
            # Delete ASIN from asin_bank if not used by other leads
            if not other_lead_uses:
                db.delete(asin_bank)
        
        db.commit()
        
        logger.info(f"Deleted ASIN at position {position} from lead {lead_id}")
        
        return {
            "status": 200,
            "message": f"ASIN deleted successfully from position {position}",
            "data": {
                "position": position,
                "deleted": True
            }
        }
        
    except Exception as e:
        db.rollback()
        error_msg = f"Error deleting ASIN at position {position} from lead {lead_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "status": -1,
            "message": error_msg,
            "data": None
        }


@router.get("/leads/{lead_id}/purchases")
def get_purchases_for_lead(lead_id: str, db: Session = Depends(get_db)):
    """
    Get all purchases associated with a specific lead
    """
    lead = db.query(OASourcing).filter_by(lead_id=lead_id).first()
    
    if not lead:
        return {
            "status": -1,
            "message": "Lead not found",
            "data": None
        }
    
    purchases = lead.purchase_trackers
    
    return {
        "status": 200,
        "message": "Purchases retrieved successfully",
        "data": {
            "lead_id": lead_id,
            "product_name": lead.product_name,
            "total_purchases": len(purchases),
            "purchases": [
                {
                    "id": p.id,
                    "date": p.date.isoformat() if p.date else None,
                    "platform": p.platform,
                    "order_number": p.order_number,
                    "final_qty": p.final_qty,
                    "ppu": float(p.ppu) if p.ppu else None,
                    "total_spend": float(p.total_spend) if p.total_spend else None,
                    "size": p.size,
                    "asin": p.asin,
                    "status": p.status,
                    "supplier": p.supplier
                }
                for p in purchases
            ]
        }
    }


def get_sourcer_initials(name: Optional[str]) -> str:
    """
    Extract first and last letter from a name to create sourcer initials.
    
    Examples:
    - "Griffin" -> "GN"
    - "Rocky" -> "RY"
    - "Carlo" -> "CO"
    - "Jo" -> "JO"
    - "A" -> "AA"
    - None -> "XX"
    """
    if not name:
        return "XX"
    
    # Remove any whitespace and get only alphabetic characters
    clean_name = ''.join(c for c in name if c.isalpha())
    
    if len(clean_name) >= 2:
        first_letter = clean_name[0].upper()
        last_letter = clean_name[-1].upper()
    elif len(clean_name) == 1:
        # If only one letter, use it twice
        first_letter = clean_name[0].upper()
        last_letter = clean_name[0].upper()
    else:
        # Fallback if no alphabetic characters
        first_letter = 'X'
        last_letter = 'X'
    
    return f"{first_letter}{last_letter}"


def generate_lead_id(timestamp: datetime, sourcer_name: Optional[str]) -> str:
    """
    Generate Lead ID in format: YYMMDDHHMMSSFL
    - YY: Year (2 digits)
    - MM: Month (2 digits)
    - DD: Day (2 digits)
    - HHMMSS: Time (6 digits)
    - F: First letter of sourcer name
    - L: Last letter of sourcer name
    
    Example: 2025-10-13 14:30:45 with sourcer "John" -> 251013143045JN
    """
    # Extract date and time components
    year = timestamp.strftime('%y')  # 2-digit year
    month = timestamp.strftime('%m')
    day = timestamp.strftime('%d')
    hour = timestamp.strftime('%H')
    minute = timestamp.strftime('%M')
    second = timestamp.strftime('%S')
    
    # Get sourcer initials
    initials = get_sourcer_initials(sourcer_name)
    
    # Construct the Lead ID
    lead_id = f"{year}{month}{day}{hour}{minute}{second}{initials}"
    
    return lead_id


@router.post("/leads")
def create_lead_submittal(lead_data: LeadSubmittalRequest, db: Session = Depends(get_db)):
    """
    Create a new lead submittal with ASINs
    """
    try:
        # Generate unique lead_id with duplicate checking
        timestamp = datetime.now()
        lead_id = generate_lead_id(timestamp, lead_data.submittedBy)
        
        # Check if lead_id already exists (unlikely but possible)
        existing_lead = db.query(OASourcing).filter_by(lead_id=lead_id).first()
        if existing_lead:
            # Add microseconds to make it unique
            old_lead_id = lead_id
            lead_id = f"{lead_id}{timestamp.microsecond:06d}"
            logger.warning(f"[DUPLICATE] Lead ID collision detected: {old_lead_id} -> {lead_id}")
        
        # Parse numeric values
        try:
            ppu_value = float(lead_data.ppu.replace('$', '').replace(',', '').strip())
        except (ValueError, AttributeError):
            ppu_value = None
            
        try:
            rsp_value = float(lead_data.rsp.replace('$', '').replace(',', '').strip())
        except (ValueError, AttributeError):
            rsp_value = None
            
        try:
            # Handle margin as percentage or decimal
            margin_str = lead_data.margin.replace('%', '').replace('$', '').replace(',', '').strip()
            margin_value = float(margin_str)
        except (ValueError, AttributeError):
            margin_value = None
        
        # Get or create retailer
        retailer_id = None
        if lead_data.retailerName:
            retailer = db.query(Retailer).filter(Retailer.name == lead_data.retailerName).first()
            if not retailer:
                # Create new retailer
                retailer = Retailer(name=lead_data.retailerName)
                db.add(retailer)
                db.flush()  # Get the ID
            retailer_id = retailer.id
        
        # Create OA Sourcing record
        new_lead = OASourcing(
            timestamp=timestamp,
            submitted_by=lead_data.submittedBy,
            lead_id=lead_id,
            retailer_id=retailer_id,
            product_name=lead_data.productName,
            product_name_pt_input=lead_data.productName,  # Same as product_name
            product_sku=lead_data.productSku,
            retailer_link=lead_data.retailerLink,
            amazon_link=lead_data.amazonLink,
            unique_id=lead_data.uniqueId,
            ppu_including_ship=ppu_value,
            rsp=rsp_value,
            margin=margin_value,
            pros=lead_data.pros,
            cons=lead_data.cons,
            other_notes_concerns=lead_data.otherNotes,
            promo_code=lead_data.promoCode,
            sourcer=get_sourcer_initials(lead_data.submittedBy),  # Convert "Griffin" -> "GN"
            status=lead_data.status or 'draft'  # Add status field
        )
        
        # Add to session
        db.add(new_lead)
        db.flush()  # Flush to get the ID
        
        # Process ASINs
        asin_records = []
        total_suggested_qty = 0
        
        for idx, asin_data in enumerate(lead_data.asins):
            if not asin_data.asin:  # Skip empty ASINs
                continue
            
            # Check if ASIN already exists in asin_bank
            existing_asin = db.query(AsinBank).filter_by(
                asin=asin_data.asin,
                size=asin_data.size
            ).first()
            
            if existing_asin:
                # Reuse existing ASIN record
                asin_bank = existing_asin
                logger.info(f"[REUSE] ASIN {asin_data.asin} (size: {asin_data.size}) already exists, reusing ID {asin_bank.id}")
            else:
                # Create new ASIN Bank record
                asin_bank = AsinBank(
                    lead_id=lead_id,
                    size=asin_data.size,
                    asin=asin_data.asin
                )
                db.add(asin_bank)
                db.flush()  # Get the ID
            
            asin_records.append({
                'id': asin_bank.id,
                'asin': asin_bank.asin,
                'size': asin_bank.size,
                'quantity': asin_data.recommendedQuantity or 0,
                'reused': existing_asin is not None
            })
            
            # Add quantity to total
            total_suggested_qty += (asin_data.recommendedQuantity or 0)
            
            # Link ASIN to lead (up to 15 ASINs)
            if idx < 15:
                setattr(new_lead, f'asin{idx + 1}_id', asin_bank.id)
                setattr(new_lead, f'asin{idx + 1}_recommended_quantity', asin_data.recommendedQuantity or 0)
        
        # Set suggested total quantity
        new_lead.suggested_total_qty = total_suggested_qty
        
        # Commit transaction
        db.commit()
        db.refresh(new_lead)
        
        # Count reused vs new ASINs
        reused_asins = sum(1 for record in asin_records if record['reused'])
        new_asins = len(asin_records) - reused_asins
        
        logger.info(f"[SUCCESS] Lead {lead_id} created | ASINs: {new_asins} new, {reused_asins} reused | Total Qty: {total_suggested_qty}")
        
        return {
            "status": 200,  # SUCCESS
            "message": "Lead created successfully",
            "data": {
                "success": True,
                "lead_id": lead_id,
                "id": new_lead.id,
                "asins_created": new_asins,
                "asins_reused": reused_asins,
                "total_asins": len(asin_records),
                "total_suggested_qty": total_suggested_qty
            }
        }
        
    except Exception as e:
        db.rollback()
        return {
            "status": -1,  # ERROR
            "message": f"Error creating lead: {str(e)}",
            "data": None
        }


# ========================
# Purchase Tracker Endpoints
# ========================

@router.get("/purchases")
def get_all_purchases(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    platform: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    product_name: Optional[str] = None,
    asin: Optional[str] = None,
    order_number: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get all purchases with pagination and filters (ULTRA-OPTIMIZED SCHEMA)
    """
    query = db.query(PurchaseTracker)\
        .options(
            joinedload(PurchaseTracker.oa_sourcing),
            joinedload(PurchaseTracker.asin_bank_ref)
        )
    
    if platform:
        query = query.filter(PurchaseTracker.platform.ilike(f"%{platform}%"))
    
    if status:
        query = query.filter(PurchaseTracker.status == status)
    
    if start_date:
        query = query.filter(PurchaseTracker.date >= datetime.combine(start_date, datetime.min.time()))
    
    if end_date:
        # Include full end_date (through 23:59:59)
        end_of_day = datetime.combine(end_date, datetime.max.time())
        query = query.filter(PurchaseTracker.date <= end_of_day)
    
    if product_name:
        # Filter by product_name from oa_sourcing relationship
        query = query.join(OASourcing, PurchaseTracker.oa_sourcing_id == OASourcing.id)\
            .filter(OASourcing.product_name.ilike(f"%{product_name}%"))
    
    if asin:
        # Filter by asin from asin_bank relationship
        query = query.join(AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id)\
            .filter(AsinBank.asin.ilike(f"%{asin}%"))
    
    if order_number:
        query = query.filter(PurchaseTracker.order_number.ilike(f"%{order_number}%"))
    
    # Order by id descending (newest first) to ensure stable ordering
    # This ensures records don't move between pages after updates since ID never changes
    # Using ID ensures consistent pagination even when other fields are updated
    query = query.order_by(PurchaseTracker.id.desc())
    
    total = query.count()
    purchases = query.offset(skip).limit(limit).all()
    
    return {
        "status": 200,
        "message": "Purchases retrieved successfully",
        "data": {
            "total": total,
            "skip": skip,
            "limit": limit,
            "items": [
                {
                    "id": p.id,
                    "date": p.date.isoformat() if p.date else None,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                    "lead_id": p.lead_id,
                    "platform": p.platform,
                    "brand": p.brand,  # From oa_sourcing via property
                    "product_name": p.product_name,  # From oa_sourcing via property
                    "size": p.size,  # From asin_bank via property
                    "asin": p.asin,  # From asin_bank via property
                    "order_number": p.order_number,
                    "sourced_by": p.sourced_by,  # From oa_sourcing via property
                    "supplier": p.supplier,  # From retailer via oa_sourcing
                    
                    # Quantities
                    "og_qty": p.og_qty,
                    "final_qty": p.final_qty,
                    "cancelled_qty": p.cancelled_qty,
                    
                    # Pricing
                    "ppu": float(p.ppu) if p.ppu else None,  # From oa_sourcing via property
                    "rsp": float(p.rsp) if p.rsp else None,
                    "total_spend": p.total_spend,  # Calculated property
                    "profit": p.profit,  # Calculated property
                    "margin_percent": p.margin_percent,  # Calculated property
                    
                    # Fulfillment tracking (NUMBERS indicating stages)
                    "shipped_to_pw": p.shipped_to_pw if p.shipped_to_pw is not None else 0,
                    "arrived": p.arrived if p.arrived is not None else 0,
                    "checked_in": p.checked_in if p.checked_in is not None else 0,
                    "shipped_out": p.shipped_out if p.shipped_out is not None else 0,
                    "tracking": p.tracking,
                    "delivery_date": p.delivery_date.isoformat() if p.delivery_date else None,
                    "location": p.location,
                    "address": p.address,
                    "in_bound": p.in_bound,
                    
                    # FBA fields
                    "outbound_name": p.outbound_name,
                    "fba_shipment": p.fba_shipment,
                    "fba_msku": p.fba_msku,
                    
                    # Refund tracking
                    "amt_of_cancelled_qty_credit_card": p.amt_of_cancelled_qty_credit_card,
                    "amt_of_cancelled_qty_gift_card": p.amt_of_cancelled_qty_gift_card,
                    "expected_refund_amount": p.expected_refund_amount,
                    "amount_refunded": p.amount_refunded,
                    "refund_status": p.refund_status,
                    "refund_method": p.refund_method,
                    "date_of_refund": p.date_of_refund.isoformat() if p.date_of_refund else None,
                    
                    # Other
                    "status": p.status,
                    "audited": p.audited,
                    "notes": p.notes,
                    "validation_bank": p.validation_bank,
                    "concat": p.concat
                }
                for p in purchases
            ]
        }
    }


@router.get("/purchases/{purchase_id}")
def get_purchase_by_id(purchase_id: int, db: Session = Depends(get_db)):
    """
    Get detailed information for a specific purchase (ULTRA-OPTIMIZED SCHEMA)
    """
    purchase = db.query(PurchaseTracker)\
        .options(
            joinedload(PurchaseTracker.oa_sourcing),
            joinedload(PurchaseTracker.asin_bank_ref)
        )\
        .filter_by(id=purchase_id)\
        .first()
    
    if not purchase:
        return {
            "status": -1,
            "message": "Purchase not found",
            "data": None
        }
    
    return {
        "status": 200,
        "message": "Purchase retrieved successfully",
        "data": {
            "id": purchase.id,
            "date": purchase.date.isoformat() if purchase.date else None,
            "created_at": purchase.created_at.isoformat() if purchase.created_at else None,
            "platform": purchase.platform,
            "lead_id": purchase.lead_id,
            "oa_sourcing_id": purchase.oa_sourcing_id,
            "asin_bank_id": purchase.asin_bank_id,
            
            # Fields from oa_sourcing (via properties)
            "product_name": purchase.product_name,  # property → oa_sourcing
            "sourced_by": purchase.sourced_by,  # property → oa_sourcing
            "sku_upc": purchase.sku_upc,  # property → oa_sourcing
            "ppu": float(purchase.ppu) if purchase.ppu else None,  # property → oa_sourcing
            
            # Fields from asin_bank (via properties)
            "asin": purchase.asin,  # property → asin_bank
            "size": purchase.size,  # property → asin_bank
            
            # Purchase-specific fields
            "order_number": purchase.order_number,
            "supplier": purchase.supplier,  # property → retailer.name via oa_sourcing
            "og_qty": purchase.og_qty,
            "final_qty": purchase.final_qty,
            "cancelled_qty": purchase.cancelled_qty,
            
            # Pricing
            "rsp": float(purchase.rsp) if purchase.rsp else None,
            "total_spend": purchase.total_spend,  # calculated property
            "profit": purchase.profit,  # calculated property
            "margin_percent": purchase.margin_percent,  # calculated property
            
            # Fulfillment (NUMBERS for workflow stages, not dates)
            "address": purchase.address,
            "shipped_to_pw": purchase.shipped_to_pw if purchase.shipped_to_pw is not None else 0,  # Integer (e.g., 1, 2, 3)
            "arrived": purchase.arrived if purchase.arrived is not None else 0,  # Integer (e.g., 1, 2, 3)
            "checked_in": purchase.checked_in if purchase.checked_in is not None else 0,  # Integer (e.g., 1, 2, 3)
            "shipped_out": purchase.shipped_out if purchase.shipped_out is not None else 0,  # Integer (e.g., 1, 2, 3)
            "delivery_date": purchase.delivery_date.isoformat() if purchase.delivery_date else None,
            "status": purchase.status,
            "location": purchase.location,
            "tracking": purchase.tracking,
            "in_bound": purchase.in_bound,
            
            # FBA fields
            "outbound_name": purchase.outbound_name,
            "fba_shipment": purchase.fba_shipment,
            "fba_msku": purchase.fba_msku,
            
            # Other
            "audited": purchase.audited,
            "notes": purchase.notes
        }
    }


@router.patch("/purchases/{purchase_id}")
def update_purchase(
    purchase_id: int,
    update_data: PurchaseUpdateRequest,
    db: Session = Depends(get_db)
):
    """
    Update a purchase tracker record
    """
    purchase = db.query(PurchaseTracker).filter_by(id=purchase_id).first()
    
    if not purchase:
        return {
            "status": -1,
            "message": "Purchase not found",
            "data": None
        }
    
    # Update fields if provided
    if update_data.og_qty is not None:
        purchase.og_qty = update_data.og_qty
    if update_data.final_qty is not None:
        purchase.final_qty = update_data.final_qty
    if update_data.cancelled_qty is not None:
        purchase.cancelled_qty = update_data.cancelled_qty
    if update_data.shipped_to_pw is not None:
        purchase.shipped_to_pw = update_data.shipped_to_pw
    if update_data.arrived is not None:
        purchase.arrived = update_data.arrived
    if update_data.checked_in is not None:
        purchase.checked_in = update_data.checked_in
    if update_data.shipped_out is not None:
        purchase.shipped_out = update_data.shipped_out
    if update_data.tracking is not None:
        purchase.tracking = update_data.tracking
    if update_data.delivery_date is not None:
        purchase.delivery_date = update_data.delivery_date
    if update_data.location is not None:
        purchase.location = update_data.location
    if update_data.address is not None:
        purchase.address = update_data.address
    if update_data.in_bound is not None:
        purchase.in_bound = update_data.in_bound
    if update_data.outbound_name is not None:
        purchase.outbound_name = update_data.outbound_name
    if update_data.fba_shipment is not None:
        purchase.fba_shipment = update_data.fba_shipment
    if update_data.fba_msku is not None:
        purchase.fba_msku = update_data.fba_msku
    if update_data.status is not None:
        purchase.status = update_data.status
    if update_data.audited is not None:
        purchase.audited = update_data.audited
    if update_data.notes is not None:
        purchase.notes = update_data.notes
    if update_data.validation_bank is not None:
        purchase.validation_bank = update_data.validation_bank
    
    # Automatically recalculate status and location based on fulfillment fields
    # Import here to avoid circular imports
    from app.utils.purchase_status import calculate_status_and_location
    
    # Recalculate status and location if any relevant fields were updated
    if (update_data.shipped_to_pw is not None or 
        update_data.checked_in is not None or 
        update_data.shipped_out is not None or 
        update_data.final_qty is not None):
        
        status, location = calculate_status_and_location(
            shipped_to_pw=purchase.shipped_to_pw,
            checked_in=purchase.checked_in,
            shipped_out=purchase.shipped_out,
            final_qty=purchase.final_qty
        )
        purchase.status = status
        purchase.location = location
    
    try:
        db.commit()
        db.refresh(purchase)
        
        return {
            "status": 200,
            "message": "Purchase updated successfully",
            "data": {
                "id": purchase.id,
                "updated": True
            }
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating purchase {purchase_id}: {e}")
        return {
            "status": -1,
            "message": f"Failed to update purchase: {str(e)}",
            "data": None
        }


@router.delete("/purchases/{purchase_id}")
def delete_purchase(purchase_id: int, db: Session = Depends(get_db)):
    """
    Delete a purchase tracker record
    """
    purchase = db.query(PurchaseTracker).filter_by(id=purchase_id).first()
    
    if not purchase:
        return {
            "status": -1,
            "message": "Purchase not found",
            "data": None
        }
    
    try:
        db.delete(purchase)
        db.commit()
        
        return {
            "status": 200,
            "message": "Purchase deleted successfully",
            "data": {
                "id": purchase_id,
                "deleted": True
            }
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting purchase {purchase_id}: {e}")
        return {
            "status": -1,
            "message": f"Failed to delete purchase: {str(e)}",
            "data": None
        }


class PurchaseBulkDeleteRequest(BaseModel):
    """Model for bulk deleting purchases"""
    ids: List[int]


@router.delete("/purchases")
def bulk_delete_purchases(delete_data: PurchaseBulkDeleteRequest, db: Session = Depends(get_db)):
    """
    Bulk delete purchase tracker records
    
    Request body should contain a list of purchase IDs to delete
    """
    try:
        if not delete_data.ids:
            return {
                "status": -1,
                "data": None,
                "message": "No purchase IDs provided"
            }
        
        # Find all purchases to delete
        purchases_to_delete = db.query(PurchaseTracker).filter(PurchaseTracker.id.in_(delete_data.ids)).all()
        
        if not purchases_to_delete:
            return {
                "status": -1,
                "data": None,
                "message": "No purchases found with the provided IDs"
            }
        
        deleted_count = len(purchases_to_delete)
        
        # Delete all found purchases
        for purchase in purchases_to_delete:
            db.delete(purchase)
        
        db.commit()
        
        logger.info(f"Bulk deleted {deleted_count} purchases: IDs={delete_data.ids}")
        
        return {
            "status": 200,
            "data": {
                "deleted_count": deleted_count,
                "deleted_ids": delete_data.ids
            },
            "message": f"Successfully deleted {deleted_count} purchase(s)"
        }
        
    except Exception as e:
        db.rollback()
        error_msg = f"Error deleting purchases: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "status": -1,
            "data": None,
            "message": error_msg
        }


@router.post("/purchases/manual")
def create_manual_purchase(
    purchase_data: ManualPurchaseRequest,
    db: Session = Depends(get_db)
):
    """
    Manually create a purchase tracker entry
    
    This endpoint allows manual entry of purchase records by providing:
    - unique_id: The unique product ID from OA Sourcing (e.g., product SKU from retailer)
    - size: The product size
    - qty: The quantity purchased
    - order_number: The order number (required)
    
    The system will:
    1. Look up the OASourcing record by unique_id
    2. Look up the AsinBank record by lead_id (from OASourcing) + size
    3. Create a PurchaseTracker record with auto-filled fields
    """
    try:
        # 1. Look up OASourcing by unique_id
        oa_sourcing = db.query(OASourcing).filter_by(unique_id=purchase_data.unique_id).first()
        
        if not oa_sourcing:
            return {
                "status": -1,
                "message": f"Unique ID '{purchase_data.unique_id}' not found in OA Sourcing",
                "data": None
            }
        
        # 2. Look up AsinBank by lead_id (from oa_sourcing) + size
        asin_record = db.query(AsinBank).filter_by(
            lead_id=oa_sourcing.lead_id,
            size=purchase_data.size
        ).first()
        
        if not asin_record:
            logger.warning(
                f"No ASIN found for lead_id={oa_sourcing.lead_id} and size={purchase_data.size}. "
                f"Creating purchase record without ASIN."
            )
        
        # 3. Generate FBA MSKU if we have the required data
        fba_msku = None
        if asin_record and oa_sourcing.product_sku and purchase_data.order_number:
            fba_msku = f"{purchase_data.size}-{oa_sourcing.product_sku}-{purchase_data.order_number}"
        
        # 4. Create purchase tracker record
        purchase_record = PurchaseTracker(
            # Foreign keys
            oa_sourcing_id=oa_sourcing.id,
            asin_bank_id=asin_record.id if asin_record else None,
            
            # Denormalized for performance
            lead_id=oa_sourcing.lead_id,
            
            # Purchase metadata
            date=datetime.utcnow(),  # Use current datetime
            platform="AMZ",  # Default platform
            order_number=purchase_data.order_number,
            
            # Quantities
            og_qty=purchase_data.qty,
            final_qty=purchase_data.qty,
            
            # Pricing - use from oa_sourcing
            rsp=oa_sourcing.rsp,
            
            # FBA fields
            fba_msku=fba_msku,
            
            # Status and Location - set to Pending/Retailer for new purchases
            status="Pending",
            location="Retailer",
            
            # Audit
            audited=False
        )
        
        db.add(purchase_record)
        db.commit()
        db.refresh(purchase_record)
        
        logger.info(
            f"Manually created purchase tracker record: "
            f"unique_id={purchase_data.unique_id}, "
            f"lead_id={oa_sourcing.lead_id}, "
            f"size={purchase_data.size}, "
            f"qty={purchase_data.qty}, "
            f"order_number={purchase_data.order_number}"
        )
        
        # Return the created record with all fields
        return {
            "status": 200,
            "message": "Purchase record created successfully",
            "data": {
                "id": purchase_record.id,
                "lead_id": purchase_record.lead_id,
                "date": purchase_record.date.isoformat() if purchase_record.date else None,
                "platform": purchase_record.platform,
                "order_number": purchase_record.order_number,
                "product_name": purchase_record.product_name,
                "size": purchase_record.size,
                "asin": purchase_record.asin,
                "og_qty": purchase_record.og_qty,
                "final_qty": purchase_record.final_qty,
                "ppu": float(purchase_record.ppu) if purchase_record.ppu else None,
                "rsp": float(purchase_record.rsp) if purchase_record.rsp else None,
                "total_spend": purchase_record.total_spend,
                "status": purchase_record.status,
                "fba_msku": purchase_record.fba_msku,
                "supplier": purchase_record.supplier
            }
        }
        
    except Exception as e:
        db.rollback()
        error_msg = f"Error creating manual purchase record: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "status": -1,
            "message": error_msg,
            "data": None
        }


# ========================
# ASIN Bank Endpoints
# ========================

@router.get("/asins")
def get_asins(
    lead_id: Optional[str] = None,
    asin: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """
    Get ASINs from the ASIN bank with filters
    """
    query = db.query(AsinBank)
    
    if lead_id:
        query = query.filter(AsinBank.lead_id == lead_id)
    
    if asin:
        query = query.filter(AsinBank.asin.ilike(f"%{asin}%"))
    
    total = query.count()
    asins = query.offset(skip).limit(limit).all()
    
    return {
        "status": 200,
        "message": "ASINs retrieved successfully",
        "data": {
            "total": total,
            "skip": skip,
            "limit": limit,
            "items": [
                {
                    "id": a.id,
                    "lead_id": a.lead_id,
                    "size": a.size,
                    "asin": a.asin
                }
                for a in asins
            ]
        }
    }


# ========================
# Statistics Endpoints
# ========================

@router.get("/statistics/summary")
def get_statistics_summary(db: Session = Depends(get_db)):
    """
    Get overall statistics summary (ULTRA-OPTIMIZED SCHEMA)
    """
    from sqlalchemy import func
    
    total_leads = db.query(func.count(OASourcing.id)).scalar()
    total_purchases = db.query(func.count(PurchaseTracker.id)).scalar()
    total_asins = db.query(func.count(AsinBank.id)).scalar()
    
    # Calculate total spend: JOIN with oa_sourcing to get ppu, then multiply by final_qty
    total_spend_result = db.query(
        func.sum(OASourcing.ppu_including_ship * PurchaseTracker.final_qty)
    )\
    .join(OASourcing, PurchaseTracker.oa_sourcing_id == OASourcing.id)\
    .scalar()
    
    avg_ppu = db.query(func.avg(OASourcing.ppu_including_ship)).scalar()
    
    # Top platforms
    top_platforms = db.query(
        PurchaseTracker.platform,
        func.count(PurchaseTracker.id).label('count')
    )\
    .group_by(PurchaseTracker.platform)\
    .order_by(func.count(PurchaseTracker.id).desc())\
    .limit(5)\
    .all()
    
    # Top brands - from retailers via oa_sourcing JOIN
    top_brands = db.query(
        Retailer.name,
        func.count(PurchaseTracker.id).label('count')
    )\
    .join(OASourcing, PurchaseTracker.oa_sourcing_id == OASourcing.id)\
    .join(Retailer, OASourcing.retailer_id == Retailer.id)\
    .group_by(Retailer.name)\
    .order_by(func.count(PurchaseTracker.id).desc())\
    .limit(5)\
    .all()
    
    return {
        "status": 200,
        "message": "Statistics retrieved successfully",
        "data": {
            "total_leads": total_leads,
            "total_purchases": total_purchases,
            "total_asins_in_bank": total_asins,
            "total_spend": float(total_spend_result) if total_spend_result else 0,
            "average_ppu": float(avg_ppu) if avg_ppu else 0,
            "top_platforms": [{"platform": p, "count": c} for p, c in top_platforms if p],
            "top_brands": [{"brand": b, "count": c} for b, c in top_brands if b]
        }
    }


@router.get("/statistics/by-retailer")
def get_statistics_by_retailer(db: Session = Depends(get_db)):
    """
    Get statistics grouped by retailer
    """
    from sqlalchemy import func
    
    stats = db.query(
        Retailer.id,
        Retailer.name,
        func.count(OASourcing.id).label('lead_count'),
        func.avg(OASourcing.ppu_including_ship).label('avg_ppu'),
        func.avg(OASourcing.margin).label('avg_margin')
    )\
    .join(OASourcing, Retailer.id == OASourcing.retailer_id)\
    .group_by(Retailer.id, Retailer.name)\
    .order_by(func.count(OASourcing.id).desc())\
    .all()
    
    return {
        "status": 200,
        "message": "Retailer statistics retrieved successfully",
        "data": {
            "items": [
                {
                    "retailer_id": retailer_id,
                    "retailer": retailer_name,
                    "lead_count": count,
                    "avg_ppu": float(avg_ppu) if avg_ppu else None,
                    "avg_margin": float(avg_margin) if avg_margin else None
                }
                for retailer_id, retailer_name, count, avg_ppu, avg_margin in stats
            ]
        }
    }


# ========================
# Inbound Creation Automation
# ========================

@router.post("/process-inbound-creation")
def process_inbound_creation(db: Session = Depends(get_db)):
    """
    Process inbound creation automation
    
    1. Extract purchase records where final_qty = shipped_to_pw AND shipped_to_pw > 0
    2. Group by address (595 Lloyd Lane or 2025 Vista Ave)
    3. Automate login and inbound creation on PrepWorx platform
    
    Returns:
        Processing results with status
    """
    try:
        logger.info("Starting inbound creation process...")
        
        # Query purchase records where final_qty = shipped_to_pw
        # This means items that have been fully shipped to PrepWorx
        # Exclude records where shipped_to_pw is 0
        # Exclude records that have already been processed (in_bound = True)
        purchases = db.query(PurchaseTracker)\
            .options(joinedload(PurchaseTracker.oa_sourcing))\
            .options(joinedload(PurchaseTracker.asin_bank_ref))\
            .filter(
                PurchaseTracker.final_qty.isnot(None),
                PurchaseTracker.shipped_to_pw.isnot(None),
                PurchaseTracker.final_qty == PurchaseTracker.shipped_to_pw,
                PurchaseTracker.shipped_to_pw > 0,  # Exclude records where shipped_to_pw is 0
                # Only process records that haven't been processed yet
                # If in_bound is NULL or False, process it
                # If in_bound is True, skip it (already processed)
                (PurchaseTracker.in_bound.is_(None) | (PurchaseTracker.in_bound == False))
                # PurchaseTracker.address.isnot(None)
            )\
            .all()
        
        logger.info(f"Found {len(purchases)} purchase records where final_qty = shipped_to_pw AND shipped_to_pw > 0")
        
        if not purchases:
            return {
                "status": 200,
                "message": "No purchase records found matching criteria (final_qty = shipped_to_pw AND shipped_to_pw > 0)",
                "data": {
                    "total_records": 0,
                    "processed_by_address": {},
                    "success": True
                }
            }
        
        # Filter only records with supported addresses
        supported_addresses = ["595 Lloyd Lane", "2025 Vista Ave"]
        filtered_purchases = []
        skipped_addresses = []
        
        for purchase in purchases:
            address = purchase.address or ""
            address_lower = address.lower()

            if "595 lloyd lane" in address_lower or "2025 vista ave" in address_lower:
                filtered_purchases.append(purchase)
            else:
                skipped_addresses.append(address)
        
        logger.info(f"Filtered to {len(filtered_purchases)} records with supported addresses")
        
        if skipped_addresses:
            logger.warning(f"Skipped {len(skipped_addresses)} records with unsupported addresses")
        
        if not filtered_purchases:
            return {
                "status": 200,
                "message": "No purchase records with supported addresses (595 Lloyd Lane or 2025 Vista Ave)",
                "data": {
                    "total_records": len(purchases),
                    "supported_records": 0,
                    "skipped_addresses": list(set(skipped_addresses)),
                    "success": True
                }
            }
        
        # Convert to dictionaries for automation service
        purchase_records = []
        for purchase in filtered_purchases:
            record = {
                "id": purchase.id,
                "lead_id": purchase.lead_id,
                "order_number": purchase.order_number,
                "product_name": purchase.product_name,
                "size": purchase.size,
                "asin": purchase.asin,
                "final_qty": purchase.final_qty,
                "shipped_to_pw": purchase.shipped_to_pw,
                "address": purchase.address,
                "platform": purchase.platform,
                "date": purchase.date.isoformat() if purchase.date else None,
                "supplier": purchase.supplier,  # Retailer name
                "sku_upc": purchase.sku_upc,  # SKU/UPC from oa_sourcing
                "ppu": purchase.ppu,  # Price per unit
            }
            purchase_records.append(record)
        
        # Check Selenium availability before running automation
        try:
            from selenium import webdriver
            # Quick check - try to import and verify it's available
            selenium_available = True
        except ImportError:
            selenium_available = False
        
        if not selenium_available:
            return {
                "status": 500,
                "message": "Selenium not installed. Please install: pip install selenium",
                "data": {
                    "success": False,
                    "error": "Selenium not installed",
                    "installation_instructions": "Run: pip install selenium. Also ensure Chrome and ChromeDriver are installed."
                }
            }
        
        # Run automation using subprocess approach to avoid server context issues
        # On Ubuntu servers, browser automation can hang when run directly in server process
        # Running in subprocess isolates it from server environment
        try:
            from app.services.prepworx_automation_subprocess import run_playwright_automation_script
            
            # Allow headless to be controlled via query parameter or settings
            # For development/debugging, you can set SELENIUM_HEADLESS=false to see browser
            # NOTE: On servers without display, headless=True is required
            from app.config import get_settings
            settings = get_settings()
            # Check for both old (playwright_headless) and new (selenium_headless) settings
            headless_mode = getattr(settings, 'selenium_headless', getattr(settings, 'playwright_headless', True))
            
            logger.info(f"Running automation in subprocess for {len(purchase_records)} records...")
            logger.info(f"Browser mode: {'headless' if headless_mode else 'visible (for debugging)'}")
            from pathlib import Path
            backend_dir = Path(__file__).parent.parent.parent
            logger.info(f"📸 Screenshots will be saved to {backend_dir / 'tmp'}/prepworx_login_*.png for debugging")
            result = run_playwright_automation_script(purchase_records, headless=headless_mode)
            
        except ImportError:
            # Fallback to direct execution if subprocess module not available
            logger.warning("Subprocess module not available, falling back to direct execution")
            from app.services.prepworx_automation import process_inbound_creation as run_automation
            logger.info(f"Running automation directly for {len(purchase_records)} records...")
            result = run_automation(purchase_records, headless=True)
        
        logger.info(f"Automation completed with success: {result.get('success', False)}")
        
        # Update database: Set in_bound=True for successfully submitted records
        successful_record_ids = result.get("successful_record_ids", [])
        if successful_record_ids:
            try:
                logger.info(f"Updating {len(successful_record_ids)} records: setting in_bound=True")
                
                updated_count = db.query(PurchaseTracker)\
                    .filter(PurchaseTracker.id.in_(successful_record_ids))\
                    .update({"in_bound": True}, synchronize_session=False)
                db.commit()
                
                logger.info(f"✅ Successfully updated {updated_count} records with in_bound=True")
            except Exception as e:
                logger.error(f"❌ Error updating database records: {e}", exc_info=True)
                db.rollback()
                # Don't fail the whole request if DB update fails - log it
        else:
            logger.info("No successfully submitted records to update in database")
        
        # Log any errors for failed submissions
        if result.get("errors"):
            logger.warning(f"⚠️  {len(result.get('errors', []))} errors occurred during automation:")
            for error in result.get("errors", []):
                logger.warning(f"   - {error}")
        
        # Get available screenshots from project tmp folder
        from pathlib import Path
        backend_dir = Path(__file__).parent.parent.parent  # Go up from app/api to backend
        screenshot_dir = backend_dir / "tmp"
        screenshot_pattern = "prepworx_login_*.png"
        screenshots = []
        if screenshot_dir.exists():
            for screenshot_path in sorted(screenshot_dir.glob(screenshot_pattern)):
                try:
                    screenshots.append({
                        "filename": screenshot_path.name,
                        "url": f"/api/v1/purchase-tracker/inbound-creation-screenshots/{screenshot_path.name}",
                        "step": screenshot_path.stem.split("_")[-1] if "_" in screenshot_path.stem else "unknown"
                    })
                except Exception as e:
                    logger.warning(f"Error reading screenshot {screenshot_path}: {e}")
        
        # Add screenshots to result
        if screenshots:
            result["screenshots"] = screenshots
            logger.info(f"Found {len(screenshots)} screenshots from automation")
        
        # Return results
        status_code = 200 if result["success"] else 500
        message = "Inbound creation processed successfully" if result["success"] else "Inbound creation failed"
        
        return {
            "status": status_code,
            "message": message,
            "data": result
        }
        
    except Exception as e:
        logger.error(f"Error processing inbound creation: {e}", exc_info=True)
        return {
            "status": 500,
            "message": f"Error processing inbound creation: {str(e)}",
            "data": {
                "success": False,
                "error": str(e)
            }
        }


@router.post("/process-outbound-creation")
def process_outbound_creation(db: Session = Depends(get_db)):
    """
    Process outbound creation for Lloyd Lane
    - Filter records where checked_in = shipped_to_pw
    - Generate Inventory Lab CSV file with:
      * ASIN
      * TITLE (from concat/name)
      * COSTUNIT (weighted average PPU per ASIN)
      * LISTPRICE (from Keepa API with 15% markup)
      * QUANTITY (total checked_in quantity per ASIN)
      * PURCHASEDDATE (current date)
      * SUPPLIER (majority supplier by quantity)
      * CONDITION (always "NEW")
      * MSKU (format: SIZE-SKU-DATE(OB))
    - Generate Prepworx CSV file from the IL file
    - Save both files to tmp directory:
      * IL: "MM-DD-YYYY Lloyd Outbound IL.csv"
      * PW: "MM-DD-YYYY Outbound PW.csv"
    
    Returns:
        Processing results with file paths and statistics for both files
    """
    try:
        logger.info("Starting outbound creation process for Lloyd Lane...")
        
        from app.services.outbound_creation_service import OutboundCreationService
        
        # Create service and generate IL CSV
        service = OutboundCreationService(db)
        il_result = service.generate_csv()
        
        if not il_result["success"]:
            logger.error(f"IL file generation failed: {il_result.get('error')}")
            return {
                "status": 500,
                "message": il_result.get("error", "IL file generation failed"),
                "data": {
                    "il_file": il_result,
                    "pw_file": {
                        "success": False,
                        "error": "IL file generation failed, skipping Prepworx generation"
                    }
                }
            }
        
        logger.info(f"✅ IL file generated successfully: {il_result['filename']}")
        
        # Generate Prepworx file from the IL file that was just created
        pw_result = service.generate_prepworx_csv(il_csv_path=il_result["file_path"])
        
        if not pw_result["success"]:
            logger.warning(f"Prepworx file generation failed: {pw_result.get('error')}")
            logger.warning("IL file was generated successfully, but Prepworx file generation failed")
        
        # Combine results
        combined_result = {
            "success": il_result["success"] and pw_result["success"],
            "il_file": il_result,
            "pw_file": pw_result,
            "total_asins": il_result.get("total_asins", 0),
            "total_records": il_result.get("total_records", 0),
            "total_items": pw_result.get("total_items", 0)
        }
        
        if combined_result["success"]:
            logger.info(f"✅ Outbound creation completed successfully")
            logger.info(f"   IL File: {il_result['filename']}")
            logger.info(f"   PW File: {pw_result['filename']}")
            logger.info(f"   Total ASINs: {il_result['total_asins']}")
            logger.info(f"   Total records: {il_result['total_records']}")
            logger.info(f"   Total items: {pw_result['total_items']}")
            
            return {
                "status": 200,
                "message": "Outbound creation completed successfully - both IL and Prepworx files generated",
                "data": combined_result
            }
        else:
            error_msg = "IL file generated, but Prepworx file generation failed"
            if not il_result["success"]:
                error_msg = "IL file generation failed"
            
            logger.error(f"Outbound creation partially failed: {error_msg}")
            return {
                "status": 500,
                "message": error_msg,
                "data": combined_result
            }
            
    except Exception as e:
        logger.error(f"Error processing outbound creation: {e}", exc_info=True)
        return {
            "status": 500,
            "message": f"Error processing outbound creation: {str(e)}",
            "data": {
                "success": False,
                "error": str(e),
                "il_file": {"success": False, "error": str(e)},
                "pw_file": {"success": False, "error": str(e)}
            }
        }


@router.post("/generate-prepworx-file")
def generate_prepworx_file(
    il_csv_path: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Generate Prepworx CSV file from IL upload CSV file
    
    Reads the IL upload CSV file from tmp folder and generates a Prepworx file with:
    - Reference Name: "MM-DD-YYYY Outbound" (today's date)
    - Workflow Name: "AMZ"
    - Shipment Notes: blank
    - Items:
      * Name: Product name from IL file (TITLE column)
      * ASIN: ASIN from IL file
      * UPC: blank
      * Multipack/bundle: "None"
      * Number of Units: Quantity from IL file (QUANTITY column)
      * Notes: blank
    
    Args:
        il_csv_path: Optional path to IL CSV file. If not provided, uses most recent IL file in tmp folder.
    
    Returns:
        Processing results with file path and statistics
    """
    try:
        logger.info("Starting Prepworx file generation...")
        
        from app.services.outbound_creation_service import OutboundCreationService
        
        # Create service and generate Prepworx CSV
        service = OutboundCreationService(db)
        result = service.generate_prepworx_csv(il_csv_path=il_csv_path)
        
        if result["success"]:
            logger.info(f"✅ Prepworx file generation completed successfully")
            logger.info(f"   File: {result['filename']}")
            logger.info(f"   Total items: {result['total_items']}")
            logger.info(f"   Reference Name: {result.get('reference_name', 'N/A')}")
            
            return {
                "status": 200,
                "message": "Prepworx file generation completed successfully",
                "data": result
            }
        else:
            logger.error(f"Prepworx file generation failed: {result.get('error')}")
            return {
                "status": 500,
                "message": result.get("error", "Prepworx file generation failed"),
                "data": result
            }
            
    except Exception as e:
        logger.error(f"Error generating Prepworx file: {e}", exc_info=True)
        return {
            "status": 500,
            "message": f"Error generating Prepworx file: {str(e)}",
            "data": {
                "success": False,
                "error": str(e)
            }
        }


@router.get("/inbound-creation-screenshots")
def get_inbound_creation_screenshots():
    """
    Get list of available screenshots from the last automation run
    
    Returns:
        List of screenshot file paths and metadata
    """
    import os
    import glob
    from pathlib import Path
    
    # Use project tmp folder
    backend_dir = Path(__file__).parent.parent.parent  # Go up from app/api to backend
    screenshot_dir = backend_dir / "tmp"
    screenshot_pattern = "prepworx_login_*.png"
    
    # Find all screenshots
    screenshots = []
    for screenshot_path in sorted(screenshot_dir.glob(screenshot_pattern)):
        try:
            stat = screenshot_path.stat()
            screenshots.append({
                "filename": screenshot_path.name,
                "path": str(screenshot_path),
                "size": stat.st_size,
                "created": stat.st_mtime,
                "url": f"/api/v1/purchase-tracker/inbound-creation-screenshots/{screenshot_path.name}"
            })
        except Exception as e:
            logger.warning(f"Error reading screenshot {screenshot_path}: {e}")
    
    return {
        "status": 200,
        "message": f"Found {len(screenshots)} screenshots",
        "data": {
            "screenshots": screenshots,
            "count": len(screenshots)
        }
    }


@router.get("/inbound-creation-screenshots/{filename}")
def get_inbound_creation_screenshot(filename: str):
    """
    Get a specific screenshot file
    
    Args:
        filename: Name of the screenshot file (e.g., prepworx_login_5_after_login.png)
    
    Returns:
        Screenshot image file
    """
    from fastapi.responses import FileResponse
    import os
    from pathlib import Path
    
    # Security: Only allow files matching the pattern
    if not filename.startswith("prepworx_login_") or not filename.endswith(".png"):
        raise HTTPException(status_code=400, detail="Invalid screenshot filename")
    
    # Use project tmp folder
    backend_dir = Path(__file__).parent.parent.parent  # Go up from app/api to backend
    screenshot_path = backend_dir / "tmp" / filename
    
    if not screenshot_path.exists():
        raise HTTPException(status_code=404, detail=f"Screenshot not found: {filename}")
    
    return FileResponse(
        path=str(screenshot_path),
        media_type="image/png",
        filename=filename
    )

