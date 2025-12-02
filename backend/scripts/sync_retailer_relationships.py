"""
Sync retailer relationships between oa_sourcing and retailers tables

This script:
1. Creates retailers from existing oa_sourcing.retailer_name entries
2. Updates oa_sourcing.retailer_id to link to retailers.id
3. Provides statistics and validation
"""

import sys
import os

# Add parent directory to path so we can import from app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.config.database import SessionLocal
from app.models.database import Retailer, OASourcing
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError


def sync_retailers_from_oa_sourcing():
    """
    Extract unique retailer names from oa_sourcing and create retailers
    """
    db = SessionLocal()
    created_count = 0
    skipped_count = 0
    
    try:
        print("=" * 70)
        print("STEP 1: CREATE RETAILERS FROM OA_SOURCING")
        print("=" * 70)
        
        # Get unique retailer names from oa_sourcing
        unique_retailers = db.query(OASourcing.retailer_name).filter(
            OASourcing.retailer_name.isnot(None),
            OASourcing.retailer_name != ''
        ).distinct().all()
        
        print(f"Found {len(unique_retailers)} unique retailer names in oa_sourcing\n")
        
        for (retailer_name,) in unique_retailers:
            # Check if retailer already exists
            existing = db.query(Retailer).filter(Retailer.name == retailer_name).first()
            
            if existing:
                print(f"[SKIP] Retailer '{retailer_name}' already exists (ID: {existing.id})")
                skipped_count += 1
            else:
                # Create new retailer
                new_retailer = Retailer(name=retailer_name)
                db.add(new_retailer)
                db.flush()  # Get the ID without committing
                print(f"[NEW]  Created retailer '{retailer_name}' (ID: {new_retailer.id})")
                created_count += 1
        
        db.commit()
        
        print(f"\n{'=' * 70}")
        print(f"Created {created_count} new retailers, skipped {skipped_count} existing")
        print(f"{'=' * 70}\n")
        
    except Exception as e:
        db.rollback()
        print(f"\n[ERROR] Failed to create retailers: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()
    
    return True


def link_oa_sourcing_to_retailers():
    """
    Update oa_sourcing.retailer_id to link to retailers.id
    """
    db = SessionLocal()
    linked_count = 0
    already_linked = 0
    no_match = 0
    
    try:
        print("=" * 70)
        print("STEP 2: LINK OA_SOURCING TO RETAILERS")
        print("=" * 70)
        
        # Get all oa_sourcing records
        oa_sourcing_records = db.query(OASourcing).all()
        print(f"Processing {len(oa_sourcing_records)} OA sourcing records\n")
        
        for record in oa_sourcing_records:
            if record.retailer_id:
                already_linked += 1
                continue
            
            if not record.retailer_name:
                no_match += 1
                continue
            
            # Find matching retailer
            retailer = db.query(Retailer).filter(
                Retailer.name == record.retailer_name
            ).first()
            
            if retailer:
                record.retailer_id = retailer.id
                linked_count += 1
                if linked_count % 10 == 0:
                    print(f"[INFO] Linked {linked_count} records so far...")
            else:
                no_match += 1
                print(f"[WARN] No retailer found for '{record.retailer_name}' (Lead: {record.lead_id})")
        
        db.commit()
        
        print(f"\n{'=' * 70}")
        print(f"Newly linked: {linked_count}")
        print(f"Already linked: {already_linked}")
        print(f"No match found: {no_match}")
        print(f"{'=' * 70}\n")
        
    except Exception as e:
        db.rollback()
        print(f"\n[ERROR] Failed to link records: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()
    
    return True


def calculate_retailer_stats():
    """
    Calculate and update retailer statistics from oa_sourcing data
    """
    db = SessionLocal()
    
    try:
        print("=" * 70)
        print("STEP 3: CALCULATE RETAILER STATISTICS")
        print("=" * 70)
        
        retailers = db.query(Retailer).all()
        print(f"Calculating stats for {len(retailers)} retailers\n")
        
        for retailer in retailers:
            # Count number of leads
            lead_count = db.query(OASourcing).filter(
                OASourcing.retailer_id == retailer.id
            ).count()
            
            print(f"[INFO] {retailer.name}: {lead_count} leads")
            
            # You can add more statistics here based on purchase_tracker data
            # For now, just showing lead count
        
        print(f"\n{'=' * 70}")
        print("Statistics calculation complete")
        print(f"{'=' * 70}\n")
        
    except Exception as e:
        print(f"\n[ERROR] Failed to calculate stats: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()
    
    return True


def display_summary():
    """
    Display summary of retailer relationships
    """
    db = SessionLocal()
    
    try:
        print("=" * 70)
        print("SUMMARY")
        print("=" * 70)
        
        # Total retailers
        total_retailers = db.query(Retailer).count()
        print(f"Total retailers: {total_retailers}")
        
        # Total OA sourcing records
        total_oa_sourcing = db.query(OASourcing).count()
        print(f"Total OA sourcing records: {total_oa_sourcing}")
        
        # Linked records
        linked = db.query(OASourcing).filter(OASourcing.retailer_id.isnot(None)).count()
        print(f"Linked records: {linked}")
        
        # Unlinked records
        unlinked = total_oa_sourcing - linked
        print(f"Unlinked records: {unlinked}")
        
        # Percentage
        if total_oa_sourcing > 0:
            percentage = (linked / total_oa_sourcing) * 100
            print(f"Link percentage: {percentage:.2f}%")
        
        print("\nTop 10 retailers by lead count:")
        top_retailers = db.query(
            Retailer.name,
            func.count(OASourcing.id).label('lead_count')
        ).outerjoin(
            OASourcing, Retailer.id == OASourcing.retailer_id
        ).group_by(
            Retailer.id, Retailer.name
        ).order_by(
            func.count(OASourcing.id).desc()
        ).limit(10).all()
        
        for i, (name, count) in enumerate(top_retailers, 1):
            print(f"  {i}. {name}: {count} leads")
        
        print(f"\n{'=' * 70}")
        print("SYNC COMPLETE!")
        print(f"{'=' * 70}\n")
        
    except Exception as e:
        print(f"\n[ERROR] Failed to display summary: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


def main():
    """
    Main function to run all sync steps
    """
    print("\n")
    print("=" * 70)
    print("RETAILER RELATIONSHIP SYNC")
    print("=" * 70)
    print("\nThis script will:")
    print("1. Create retailers from oa_sourcing.retailer_name")
    print("2. Link oa_sourcing.retailer_id to retailers.id")
    print("3. Calculate retailer statistics")
    print("4. Display summary")
    print("\n")
    
    # Step 1: Create retailers
    if not sync_retailers_from_oa_sourcing():
        print("[ERROR] Failed at step 1. Aborting.")
        return
    
    # Step 2: Link relationships
    if not link_oa_sourcing_to_retailers():
        print("[ERROR] Failed at step 2. Aborting.")
        return
    
    # Step 3: Calculate stats
    if not calculate_retailer_stats():
        print("[ERROR] Failed at step 3. Continuing anyway...")
    
    # Step 4: Display summary
    display_summary()


if __name__ == "__main__":
    main()

