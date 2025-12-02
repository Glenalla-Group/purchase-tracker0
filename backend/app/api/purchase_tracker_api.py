"""
Purchase Tracker API Endpoints
FastAPI routes for accessing purchase tracker data
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload, selectinload
from typing import List, Optional
from datetime import date, datetime
from pydantic import BaseModel
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
    submittedBy: str
    productName: str
    productSku: str
    retailerLink: Optional[str] = None
    retailerName: str
    amazonLink: Optional[str] = None
    uniqueId: Optional[str] = None
    ppu: str
    rsp: str
    margin: str
    pros: str
    cons: str
    otherNotes: Optional[str] = None
    promoCode: Optional[str] = None
    asins: List[AsinSubmittal] = []


class LeadUpdateRequest(BaseModel):
    """Model for updating an existing lead"""
    productName: Optional[str] = None
    retailerLink: Optional[str] = None
    amazonLink: Optional[str] = None
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
    asin1BuyBox: Optional[float] = None
    asin1NewPrice: Optional[float] = None
    pickPackFee: Optional[float] = None
    referralFee: Optional[float] = None
    totalFee: Optional[float] = None
    promoCode: Optional[str] = None


# ========================
# OA Sourcing Endpoints
# ========================

@router.get("/leads")
def get_all_leads(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    retailer: Optional[str] = None,
    sourcer: Optional[str] = None,
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
    
    if sourcer:
        query = query.filter(OASourcing.sourcer == sourcer)
    
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
                    "asin": asin_record.asin
                }
                for asin_record in asins
            ]
        }
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
    
    # Collect ASINs
    asins = []
    for i in range(1, 16):
        asin_ref = getattr(lead, f'asin{i}_ref', None)
        if asin_ref:
            asins.append({
                "position": i,
                "asin": asin_ref.asin,
                "size": asin_ref.size,
                "recommended_quantity": getattr(lead, f'asin{i}_recommended_quantity', None)
            })
    
    return {
        "status": 200,
        "message": "Lead retrieved successfully",
        "data": {
            "id": lead.id,
            "lead_id": lead.lead_id,
            "timestamp": lead.timestamp.isoformat() if lead.timestamp else None,
            "submitted_by": lead.submitted_by,
            "retailer_id": lead.retailer_id,
            "retailer_name": lead.retailer.name if lead.retailer else None,
            "product_name": lead.product_name,
            "product_sku": lead.product_sku,
            "retailer_link": lead.retailer_link,
            "amazon_link": lead.amazon_link,
            "unique_id": lead.unique_id,
            "purchased": lead.purchased,
            "ppu_including_ship": float(lead.ppu_including_ship) if lead.ppu_including_ship else None,
            "rsp": float(lead.rsp) if lead.rsp else None,
            "margin": float(lead.margin) if lead.margin else None,
            "suggested_total_qty": lead.suggested_total_qty,
            "sourcer": lead.sourcer,
            "asins": asins,
            "pros": lead.pros,
            "cons": lead.cons,
            "other_notes": lead.other_notes_concerns
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


def get_sourcer_initials(name: str) -> str:
    """
    Extract first and last letter from a name to create sourcer initials.
    
    Examples:
    - "Griffin" -> "GN"
    - "Rocky" -> "RY"
    - "Carlo" -> "CO"
    - "Jo" -> "JO"
    - "A" -> "AA"
    """
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


def generate_lead_id(timestamp: datetime, sourcer_name: str) -> str:
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
            sourcer=get_sourcer_initials(lead_data.submittedBy)  # Convert "Griffin" -> "GN"
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
        query = query.filter(PurchaseTracker.date >= start_date)
    
    if end_date:
        query = query.filter(PurchaseTracker.date <= end_date)
    
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
                    "lead_id": p.lead_id,
                    "platform": p.platform,
                    "brand": p.brand,  # From oa_sourcing via property
                    "name": p.product_name,  # From oa_sourcing via property
                    "size": p.size,  # From asin_bank via property
                    "asin": p.asin,  # From asin_bank via property
                    "order_number": p.order_number,
                    "final_qty": p.final_qty,
                    "ppu": float(p.ppu) if p.ppu else None,  # From oa_sourcing via property
                    "total_spend": p.total_spend,  # Calculated property
                    "status": p.status
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
            
            # Pricing
            "rsp": float(purchase.rsp) if purchase.rsp else None,
            "total_spend": purchase.total_spend,  # calculated property
            "profit": purchase.profit,  # calculated property
            "margin_percent": purchase.margin_percent,  # calculated property
            
            # Fulfillment (NUMBERS for workflow stages, not dates)
            "address": purchase.address,
            "shipped_to_pw": purchase.shipped_to_pw,  # Integer (e.g., 1, 2, 3)
            "arrived": purchase.arrived,  # Integer (e.g., 1, 2, 3)
            "checked_in": purchase.checked_in,  # Integer (e.g., 1, 2, 3)
            "shipped_out": purchase.shipped_out,  # Integer (e.g., 1, 2, 3)
            "delivery_date": purchase.delivery_date.isoformat() if purchase.delivery_date else None,
            "status": purchase.status,
            "location": purchase.location,
            "tracking": purchase.tracking,
            
            # Other
            "audited": purchase.audited,
            "notes": purchase.notes
        }
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

