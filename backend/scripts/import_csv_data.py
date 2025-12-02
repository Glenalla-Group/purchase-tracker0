"""
Script to import CSV data into PostgreSQL database
Handles the relationship between asin_bank, oa_sourcing, and purchase_tracker
"""

import csv
import sys
import os
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config.database import SessionLocal, init_db
from app.models.database import AsinBank, OASourcing, PurchaseTracker


def parse_float(value):
    """Parse float value from CSV, handling currency symbols and empty strings"""
    if not value or value.strip() == '':
        return None
    # Remove currency symbols and spaces
    value = value.replace('$', '').replace(',', '').strip()
    try:
        return float(value)
    except ValueError:
        return None


def parse_int(value):
    """Parse integer value from CSV, handling empty strings"""
    if not value or value.strip() == '':
        return None
    try:
        return int(value)
    except ValueError:
        return None


def parse_date(date_str):
    """Parse date string in various formats"""
    if not date_str or date_str.strip() == '':
        return None
    
    formats = ['%m/%d/%Y', '%Y-%m-%d', '%m/%d/%y']
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    return None


def parse_datetime(datetime_str):
    """Parse datetime string"""
    if not datetime_str or datetime_str.strip() == '':
        return None
    
    formats = ['%m/%d/%Y %H:%M', '%Y-%m-%d %H:%M:%S', '%m/%d/%Y %H:%M:%S']
    for fmt in formats:
        try:
            return datetime.strptime(datetime_str.strip(), fmt)
        except ValueError:
            continue
    return None


def parse_boolean(value):
    """Parse boolean value from CSV"""
    if not value or value.strip() == '':
        return None
    value = value.strip().lower()
    if value in ['yes', 'true', '1', 'y']:
        return True
    elif value in ['no', 'false', '0', 'n']:
        return False
    return None


def import_oa_sourcing_csv(csv_file_path, db_session):
    """Import OA Sourcing CSV data"""
    print(f"\nImporting OA Sourcing data from {csv_file_path}...")
    
    with open(csv_file_path, 'r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        count = 0
        
        for row in reader:
            lead_id = row.get('Lead ID', '').strip()
            if not lead_id:
                continue
            
            # First, create ASIN bank entries for this lead
            asin_refs = {}
            for i in range(1, 16):  # ASIN 1 through ASIN 15
                asin_col = f'ASIN {i}'
                size_col = f'ASIN {i} Size'
                
                asin_value = row.get(asin_col, '').strip()
                size_value = row.get(size_col, '').strip()
                
                if asin_value:
                    # Create or get ASIN bank entry
                    asin_bank_entry = AsinBank(
                        lead_id=lead_id,
                        size=size_value if size_value else None,
                        asin=asin_value
                    )
                    db_session.add(asin_bank_entry)
                    db_session.flush()  # Get the ID
                    asin_refs[i] = asin_bank_entry.id
            
            # Get or create retailer
            retailer_id = None
            retailer_name_value = row.get('Retailer Name', '').strip()
            if retailer_name_value:
                from app.models.database import Retailer
                retailer = db_session.query(Retailer).filter(Retailer.name == retailer_name_value).first()
                if not retailer:
                    retailer = Retailer(name=retailer_name_value)
                    db_session.add(retailer)
                    db_session.flush()
                retailer_id = retailer.id
            
            # Create OA Sourcing entry
            oa_sourcing = OASourcing(
                timestamp=parse_datetime(row.get('Timestamp', '')),
                submitted_by=row.get('Submitted By', '').strip() or None,
                lead_id=lead_id,
                retailer_id=retailer_id,
                product_name_pt_input=row.get('Product Name (PT Input)', '').strip() or None,
                product_name=row.get('Product Name', '').strip() or None,
                product_sku=row.get('Product SKU', '').strip() or None,
                retailer_link=row.get('Retailer Link', '').strip() or None,
                amazon_link=row.get('Amazon link', '').strip() or None,
                purchased=row.get('Purchased?', '').strip() or None,
                purchase_more_if_available=row.get('Purchase More If Available?', '').strip() or None,
                pros=row.get('Pros:', '').strip() or None,
                cons=row.get('Cons:', '').strip() or None,
                other_notes_concerns=row.get('Other Notes/Concerns', '').strip() or None,
                head_of_product_review_notes=row.get('Head of Product Review/Notes', '').strip() or None,
                feedback_and_notes_on_quantity=row.get('Feedback and Notes on Quantity', '').strip() or None,
                suggested_total_qty=parse_int(row.get('Suggested Total QTY', '')),
                pairs_per_lead_id=parse_int(row.get('Pairs Per LEAD ID', '')),
                pairs_per_sku=parse_int(row.get('Pairs Per SKU', '')),
                ppu_including_ship=parse_float(row.get('PPU (including ship)', '')),
                rsp=parse_float(row.get('RSP', '')),
                margin=parse_float(row.get('MARGIN', '')),
                promo_code=row.get('Promo Code?', '').strip() or None,
                sales_rank=row.get('Sales Rank', '').strip() or None,
                asin1_buy_box=parse_float(row.get('ASIN 1 Buy Box', '')),
                asin1_new_price=parse_float(row.get('ASIN 1 New Price', '')),
                pick_pack_fee=parse_float(row.get('Pick&Pack Fee', '')),
                referral_fee=parse_float(row.get('Referral Fee', '')),
                total_fee=parse_float(row.get('Total Fee', '')),
                margin_using_rsp=parse_float(row.get('Margin Using RSP', '')),
                monitored=parse_boolean(row.get('Monitored?', '')),
                sourcer=row.get('Sourcer', '').strip() or None
            )
            
            # Set ASIN references
            for i in range(1, 16):
                if i in asin_refs:
                    setattr(oa_sourcing, f'asin{i}_id', asin_refs[i])
                    qty_col = f'ASIN {i} Recommended Quantity'
                    setattr(oa_sourcing, f'asin{i}_recommended_quantity', parse_int(row.get(qty_col, '')))
            
            db_session.add(oa_sourcing)
            count += 1
            
            if count % 10 == 0:
                db_session.commit()
                print(f"  Imported {count} OA sourcing records...")
        
        db_session.commit()
        print(f"✓ Imported {count} OA sourcing records successfully!")


def import_purchase_tracker_csv(csv_file_path, db_session):
    """Import Purchase Tracker CSV data"""
    print(f"\nImporting Purchase Tracker data from {csv_file_path}...")
    
    with open(csv_file_path, 'r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        count = 0
        
        for row in reader:
            lead_id = row.get('Lead ID', '').strip()
            
            # Find corresponding oa_sourcing record
            oa_sourcing_id = None
            if lead_id:
                oa_sourcing = db_session.query(OASourcing).filter_by(lead_id=lead_id).first()
                if oa_sourcing:
                    oa_sourcing_id = oa_sourcing.id
            
            # Find asin_bank_id for the purchased ASIN
            asin_value = row.get('ASIN', '').strip()
            size_value = row.get('Size', '').strip()
            asin_bank_id = None
            
            if asin_value and lead_id:
                # Find the asin_bank record matching this ASIN and lead_id
                asin_bank_record = db_session.query(AsinBank).filter_by(
                    lead_id=lead_id,
                    asin=asin_value
                ).first()
                if asin_bank_record:
                    asin_bank_id = asin_bank_record.id
            
            # Create purchase record (ULTRA-OPTIMIZED - maximum normalization)
            purchase = PurchaseTracker(
                # Relationships
                oa_sourcing_id=oa_sourcing_id,
                asin_bank_id=asin_bank_id,  # FK to asin_bank for ASIN/size
                lead_id=lead_id or None,  # Denormalized for performance
                
                # Purchase metadata
                date=parse_date(row.get('Date', '')),
                platform=row.get('Platform', '').strip() or None,
                order_number=row.get('Order Number', '').strip() or None,
                # NOTE: supplier removed - same as oa_sourcing.retailer_name
                # NOTE: unique_id removed - product unique_id belongs in oa_sourcing table
                
                # Quantities
                og_qty=parse_int(row.get('OG QTY', '')),
                final_qty=parse_int(row.get('Final QTY', '')),
                
                # Pricing (actual prices if different from planned)
                rsp=parse_float(row.get('RSP', '')),
                # NOTE: ppu removed - get from oa_sourcing.ppu_including_ship
                # NOTE: total_spend is calculated: ppu * final_qty
                
                # Fulfillment tracking (NUMBERS not dates - 1, 2, 3, etc.)
                address=row.get('Address', '').strip() or None,
                shipped_to_pw=parse_int(row.get('Shipped to PW', '')),  # Number, not boolean
                arrived=parse_int(row.get('Arrived', '')),  # Number, not date
                checked_in=parse_int(row.get('Checked In', '')),  # Number, not date
                shipped_out=parse_int(row.get('Shipped Out', '')),  # Number, not date
                delivery_date=parse_date(row.get('Delivery Date', '')),  # Actual date
                status=row.get('Status', '').strip() or None,
                location=row.get('Location', '').strip() or None,
                in_bound=parse_boolean(row.get('In Bound?', '')),
                tracking=row.get('Tracking', '').strip() or None,
                
                # FBA fields
                outbound_name=row.get('Outbound Name', '').strip() or None,
                fba_shipment=row.get('FBA Shipment', '').strip() or None,
                fba_msku=row.get('FBA MSKU', '').strip() or None,
                concat=row.get('Concat', '').strip() or None,
                audited=parse_boolean(row.get('Audited?', '')),
                
                # Refund tracking
                cancelled_qty=parse_int(row.get('Cancelled QTY', '')),
                amt_of_cancelled_qty_credit_card=parse_float(row.get('Amt of Cancelled QTY \n(Credit Card)', '')),
                amt_of_cancelled_qty_gift_card=parse_float(row.get('Amt of Cancelled QTY \n(Gift Card)', '')),
                expected_refund_amount=parse_float(row.get('Expected Refund Amount', '')),
                amount_refunded=parse_float(row.get('Amount Refunded', '')),
                refund_status=row.get('Refund Status', '').strip() or None,
                refund_method=row.get('Refund Method', '').strip() or None,
                date_of_refund=parse_date(row.get('Date of Refund', '')),
                
                # Misc
                notes=row.get('Notes', '').strip() or None,
                validation_bank=row.get('Validation Bank', '').strip() or None
                
                # REMOVED FIELDS (access via relationships):
                # - name → oa_sourcing.product_name
                # - brand → oa_sourcing.retailer_name
                # - sourced_by → oa_sourcing.submitted_by
                # - sku_upc → oa_sourcing.product_sku
                # - supplier → oa_sourcing.retailer_name
                # - ppu → oa_sourcing.ppu_including_ship
                # - asin → asin_bank.asin (via asin_bank_id)
                # - size → asin_bank.size (via asin_bank_id)
                # - total_spend → calculated property
            )
            
            db_session.add(purchase)
            count += 1
            
            if count % 10 == 0:
                db_session.commit()
                print(f"  Imported {count} purchase tracker records...")
        
        db_session.commit()
        print(f"✓ Imported {count} purchase tracker records successfully!")


def main():
    """Main import function"""
    print("=" * 60)
    print("CSV Data Import Script")
    print("=" * 60)
    
    # Initialize database (create tables if they don't exist)
    print("\nInitializing database...")
    init_db()
    
    # Get database session
    db = SessionLocal()
    
    try:
        # Import OA Sourcing data
        oa_sourcing_file = 'feed/2025 OA Sourcing Sheet - Lead Submittal.csv'
        if os.path.exists(oa_sourcing_file):
            import_oa_sourcing_csv(oa_sourcing_file, db)
        else:
            print(f"Warning: OA Sourcing file not found: {oa_sourcing_file}")
        
        # Import Purchase Tracker data
        purchase_tracker_file = 'feed/2025 Purchase Tracker and Reconciliation - Purchase Tracker.csv'
        if os.path.exists(purchase_tracker_file):
            import_purchase_tracker_csv(purchase_tracker_file, db)
        else:
            print(f"Warning: Purchase Tracker file not found: {purchase_tracker_file}")
        
        print("\n" + "=" * 60)
        print("Import completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Error during import: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()

