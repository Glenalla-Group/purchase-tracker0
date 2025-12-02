"""
Example queries for the Purchase Tracker database
Demonstrates how to use the database models
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config.database import SessionLocal
from app.models.database import AsinBank, OASourcing, PurchaseTracker
from sqlalchemy.orm import joinedload


def example_1_query_lead_with_asins():
    """Query a lead with all its ASINs"""
    print("\n" + "=" * 60)
    print("Example 1: Query Lead with ASINs")
    print("=" * 60)
    
    db = SessionLocal()
    
    try:
        # Get lead with eager loading of ASIN references
        lead = db.query(OASourcing)\
            .options(
                joinedload(OASourcing.asin1_ref),
                joinedload(OASourcing.asin2_ref),
                joinedload(OASourcing.asin3_ref)
            )\
            .first()
        
        if lead:
            print(f"\nLead ID: {lead.lead_id}")
            print(f"Product: {lead.product_name}")
            print(f"Retailer: {lead.retailer.name if lead.retailer else 'N/A'}")
            print(f"PPU: ${lead.ppu_including_ship}")
            print(f"RSP: ${lead.rsp}")
            
            print("\nASINs:")
            for i in range(1, 16):
                asin_ref = getattr(lead, f'asin{i}_ref', None)
                if asin_ref:
                    qty = getattr(lead, f'asin{i}_recommended_quantity', 0)
                    print(f"  ASIN {i}: {asin_ref.asin} (Size: {asin_ref.size}, Qty: {qty})")
        else:
            print("No leads found in database")
            
    finally:
        db.close()


def example_2_query_purchases_for_lead():
    """Query all purchases for a specific lead"""
    print("\n" + "=" * 60)
    print("Example 2: Query Purchases for Lead")
    print("=" * 60)
    
    db = SessionLocal()
    
    try:
        # Get first lead
        lead = db.query(OASourcing).first()
        
        if lead:
            print(f"\nLead ID: {lead.lead_id}")
            print(f"Product: {lead.product_name}")
            
            # Get purchases through relationship
            purchases = lead.purchase_trackers
            
            print(f"\nTotal Purchases: {len(purchases)}")
            
            for purchase in purchases:
                print(f"\n  Order: {purchase.order_number}")
                print(f"  Date: {purchase.date}")
                print(f"  Platform: {purchase.platform}")
                print(f"  Qty: {purchase.final_qty}")
                print(f"  Total Spend: ${purchase.total_spend}")
                print(f"  Status: {purchase.status}")
        else:
            print("No leads found in database")
            
    finally:
        db.close()


def example_3_query_all_asins_for_lead_id():
    """Query all ASINs associated with a lead ID from asin_bank"""
    print("\n" + "=" * 60)
    print("Example 3: Query All ASINs from ASIN Bank")
    print("=" * 60)
    
    db = SessionLocal()
    
    try:
        # Get first lead
        lead = db.query(OASourcing).first()
        
        if lead:
            lead_id = lead.lead_id
            print(f"\nLead ID: {lead_id}")
            
            # Query asin_bank for all ASINs with this lead_id
            asins = db.query(AsinBank).filter_by(lead_id=lead_id).all()
            
            print(f"Total ASINs in bank: {len(asins)}")
            
            for asin in asins:
                print(f"  - {asin.asin} (Size: {asin.size}, Bank ID: {asin.id})")
        else:
            print("No leads found in database")
            
    finally:
        db.close()


def example_4_aggregate_statistics():
    """Get aggregate statistics"""
    print("\n" + "=" * 60)
    print("Example 4: Aggregate Statistics")
    print("=" * 60)
    
    db = SessionLocal()
    
    try:
        from sqlalchemy import func
        
        # Count total records
        total_leads = db.query(func.count(OASourcing.id)).scalar()
        total_purchases = db.query(func.count(PurchaseTracker.id)).scalar()
        total_asins = db.query(func.count(AsinBank.id)).scalar()
        
        print(f"\nTotal Leads: {total_leads}")
        print(f"Total Purchases: {total_purchases}")
        print(f"Total ASINs in Bank: {total_asins}")
        
        # Calculate total spend
        total_spend = db.query(func.sum(PurchaseTracker.total_spend)).scalar()
        if total_spend:
            print(f"Total Spend: ${total_spend:,.2f}")
        
        # Average PPU
        avg_ppu = db.query(func.avg(OASourcing.ppu_including_ship)).scalar()
        if avg_ppu:
            print(f"Average PPU: ${avg_ppu:,.2f}")
        
        # Top brands
        print("\nTop Brands by Purchase Count:")
        top_brands = db.query(
            PurchaseTracker.brand,
            func.count(PurchaseTracker.id).label('count')
        )\
        .group_by(PurchaseTracker.brand)\
        .order_by(func.count(PurchaseTracker.id).desc())\
        .limit(5)\
        .all()
        
        for brand, count in top_brands:
            if brand:
                print(f"  - {brand}: {count} purchases")
                
    finally:
        db.close()


def example_5_join_query():
    """Complex join query"""
    print("\n" + "=" * 60)
    print("Example 5: Join Query - Purchases with Lead Info")
    print("=" * 60)
    
    db = SessionLocal()
    
    try:
        # Join purchase_tracker with oa_sourcing and retailer
        from app.models.database import Retailer
        
        results = db.query(
            PurchaseTracker.order_number,
            PurchaseTracker.total_spend,
            PurchaseTracker.platform,
            OASourcing.product_name,
            Retailer.name
        )\
        .join(OASourcing, PurchaseTracker.oa_sourcing_id == OASourcing.id)\
        .outerjoin(Retailer, OASourcing.retailer_id == Retailer.id)\
        .limit(5)\
        .all()
        
        print(f"\nFound {len(results)} purchases with lead info:")
        
        for order, spend, platform, product, retailer in results:
            print(f"\n  Order: {order}")
            print(f"  Product: {product}")
            print(f"  Retailer: {retailer}")
            print(f"  Platform: {platform}")
            print(f"  Spend: ${spend}")
            
    finally:
        db.close()


def main():
    """Run all examples"""
    print("\n" + "=" * 60)
    print("Purchase Tracker Database Query Examples")
    print("=" * 60)
    
    try:
        example_1_query_lead_with_asins()
        example_2_query_purchases_for_lead()
        example_3_query_all_asins_for_lead_id()
        example_4_aggregate_statistics()
        example_5_join_query()
        
        print("\n" + "=" * 60)
        print("All examples completed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Error running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()


