"""
Add sample retailers to the database
This script adds some example retailers for testing purposes
"""

import sys
import os

# Add parent directory to path so we can import from app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.config.database import SessionLocal
from app.models.database import Retailer
from sqlalchemy.exc import IntegrityError

def add_sample_retailers():
    """Add sample retailers to the database"""
    
    sample_retailers = [
        {
            "name": "Amazon",
            "link": "https://www.amazon.com",
            "wholesale": "yes",
            "cancel_for_bulk": False,
            "location": "USA",
            "shopify": False
        },
        {
            "name": "Walmart",
            "link": "https://www.walmart.com",
            "wholesale": "no",
            "cancel_for_bulk": False,
            "location": "USA",
            "shopify": False
        },
        {
            "name": "Target",
            "link": "https://www.target.com",
            "wholesale": "no",
            "cancel_for_bulk": True,
            "location": "USA",
            "shopify": False
        },
        {
            "name": "Best Buy",
            "link": "https://www.bestbuy.com",
            "wholesale": "no",
            "cancel_for_bulk": False,
            "location": "USA",
            "shopify": False
        },
        {
            "name": "Home Depot",
            "link": "https://www.homedepot.com",
            "wholesale": "yes",
            "cancel_for_bulk": False,
            "location": "USA",
            "shopify": False
        },
        {
            "name": "Costco",
            "link": "https://www.costco.com",
            "wholesale": "yes",
            "cancel_for_bulk": False,
            "location": "USA",
            "shopify": False
        },
        {
            "name": "Tesco",
            "link": "https://www.tesco.com",
            "wholesale": "no",
            "cancel_for_bulk": False,
            "location": "UK",
            "shopify": False
        },
        {
            "name": "ASOS",
            "link": "https://www.asos.com",
            "wholesale": "no",
            "cancel_for_bulk": False,
            "location": "UK",
            "shopify": True
        },
        {
            "name": "Zalando",
            "link": "https://www.zalando.com",
            "wholesale": "no",
            "cancel_for_bulk": False,
            "location": "EU",
            "shopify": False
        },
        {
            "name": "Canadian Tire",
            "link": "https://www.canadiantire.ca",
            "wholesale": "no",
            "cancel_for_bulk": False,
            "location": "CANADA",
            "shopify": False
        }
    ]
    
    db = SessionLocal()
    added_count = 0
    skipped_count = 0
    
    try:
        print("=" * 60)
        print("ADDING SAMPLE RETAILERS")
        print("=" * 60)
        
        for retailer_data in sample_retailers:
            try:
                # Check if retailer already exists
                existing = db.query(Retailer).filter(Retailer.name == retailer_data["name"]).first()
                if existing:
                    print(f"[SKIP] Retailer '{retailer_data['name']}' already exists")
                    skipped_count += 1
                    continue
                
                # Create new retailer
                retailer = Retailer(**retailer_data)
                db.add(retailer)
                db.commit()
                print(f"[OK] Added retailer: {retailer_data['name']} ({retailer_data['location']})")
                added_count += 1
                
            except IntegrityError as e:
                db.rollback()
                print(f"[ERROR] Failed to add {retailer_data['name']}: {e}")
                skipped_count += 1
        
        print("\n" + "=" * 60)
        print(f"COMPLETE! Added {added_count} retailers, skipped {skipped_count}")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[ERROR] Failed to add sample retailers: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    add_sample_retailers()

