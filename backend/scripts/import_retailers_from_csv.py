"""
Import retailers from CSV with detailed logging
"""
import csv
import psycopg2
from psycopg2 import sql
import os
from dotenv import load_dotenv

load_dotenv()

# CSV file path
csv_file = r'C:\Users\aaa\Downloads\2025 OA Sourcing Sheet - Retailer List.csv.txt'

# Connect to database
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

# Read CSV
with open(csv_file, 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    header = next(reader)  # Skip header
    
    print(f"CSV Header: {header[:10]}")  # Show first 10 columns
    print("\nProcessing retailers...\n")
    
    total_rows = 0
    inserted = 0
    skipped = 0
    duplicates = 0
    errors = []
    
    for row_num, row in enumerate(reader, start=2):
        # Skip completely empty rows
        if not any(row):
            continue
            
        # Check if this is a retailer row (has the expected structure)
        if len(row) < 10:
            skipped += 1
            continue
        
        total_rows += 1
        
        # Extract fields (based on your CSV structure)
        wholesale = row[0].strip() if row[0] else 'n/a'
        cancel_for_bulk = row[1].strip().lower() == 'yes' if row[1] else False
        location = row[2].strip() if row[2] else None
        shopify = row[3].strip().lower() == 'yes' if row[3] else False
        
        # Parse total spend (remove $ and commas)
        total_spend_str = row[4].strip().replace('$', '').replace(',', '') if row[4] else '0'
        try:
            total_spend = float(total_spend_str) if total_spend_str else 0.0
        except ValueError:
            total_spend = 0.0
        
        # Parse total qty
        try:
            total_qty = int(row[5].strip().replace(',', '')) if row[5] else 0
        except ValueError:
            total_qty = 0
        
        # Parse percent cancelled (remove %)
        percent_str = row[6].strip().replace('%', '') if row[6] else '0'
        try:
            percent_cancelled = float(percent_str) if percent_str else 0.0
        except ValueError:
            percent_cancelled = 0.0
        
        # Name and Link
        name = row[8].strip() if len(row) > 8 and row[8] else None
        link = row[9].strip() if len(row) > 9 and row[9] else None
        
        # Skip if no name
        if not name:
            skipped += 1
            print(f"Row {row_num}: SKIPPED - No name")
            continue
        
        try:
            # Try to insert
            cur.execute("""
                INSERT INTO retailers (
                    name, link, wholesale, cancel_for_bulk, location, shopify,
                    total_spend, total_qty_of_items_ordered, percent_of_cancelled_qty
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (name) DO NOTHING
                RETURNING id
            """, (
                name, link, wholesale, cancel_for_bulk, location, shopify,
                total_spend, total_qty, percent_cancelled
            ))
            
            result = cur.fetchone()
            if result:
                inserted += 1
                if inserted <= 10 or inserted % 50 == 0:
                    print(f"Row {row_num}: ✓ Inserted '{name}'")
            else:
                duplicates += 1
                print(f"Row {row_num}: ⊗ Duplicate '{name}'")
                
        except Exception as e:
            errors.append((row_num, name, str(e)))
            print(f"Row {row_num}: ✗ ERROR '{name}': {e}")
    
    # Commit changes
    conn.commit()
    
    # Summary
    print("\n" + "="*60)
    print("IMPORT SUMMARY")
    print("="*60)
    print(f"Total rows processed: {total_rows}")
    print(f"Successfully inserted: {inserted}")
    print(f"Duplicates (skipped): {duplicates}")
    print(f"Skipped (no name/data): {skipped}")
    print(f"Errors: {len(errors)}")
    
    if errors:
        print("\nErrors:")
        for row_num, name, error in errors[:10]:  # Show first 10 errors
            print(f"  Row {row_num} ({name}): {error}")
    
    # Check final count
    cur.execute("SELECT COUNT(*) FROM retailers")
    final_count = cur.fetchone()[0]
    print(f"\nTotal retailers in database: {final_count}")

cur.close()
conn.close()

print("\n✓ Import complete!")

