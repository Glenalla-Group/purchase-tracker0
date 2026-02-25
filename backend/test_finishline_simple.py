#!/usr/bin/env python3
"""
Simple test script to parse Finish Line cancellation emails from files.
No Gmail dependencies required.
"""

import sys
import os
import re

# Add current directory to path
sys.path.insert(0, os.path.abspath('.'))

# Direct imports to avoid GmailService dependency
# Import directly from the module file to bypass __init__.py
import importlib.util
spec = importlib.util.spec_from_file_location(
    "finishline_parser",
    os.path.join(os.path.abspath('.'), "app", "services", "finishline_parser.py")
)
finishline_parser_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(finishline_parser_module)

FinishLineEmailParser = finishline_parser_module.FinishLineEmailParser
FinishLineCancellationData = finishline_parser_module.FinishLineCancellationData

# Import EmailData directly
from app.models.email import EmailData

def test_finishline_cancellation_from_file(email_file_name: str):
    """Test parsing Finish Line cancellation email from a file"""
    
    print(f"Reading Finish Line cancellation email from file: {email_file_name}")
    print("=" * 80)
    
    try:
        # Determine file path
        if os.path.isabs(email_file_name):
            file_path = email_file_name
        else:
            # Try relative to current directory
            file_path = os.path.join('feed', 'order-cancellation-emails', email_file_name)
            if not os.path.exists(file_path):
                # Try just the filename
                file_path = email_file_name
        
        if not os.path.exists(file_path):
            print(f"❌ File not found: {file_path}")
            return None
        
        # Read file content
        with open(file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        print(f"✅ Read {len(html_content)} characters from file")
        
        # Create EmailData object
        email_data = EmailData(
            message_id="test-123",
            thread_id="test-thread-123",
            subject="Your order has been canceled",
            sender="finishline@notifications.finishline.com",
            html_content=html_content
        )
        
        # Parse cancellation email
        parser = FinishLineEmailParser()
        
        print("\n" + "=" * 80)
        print("Checking email identification...")
        print("=" * 80)
        
        is_finishline = parser.is_finishline_email(email_data)
        is_cancellation = parser.is_cancellation_email(email_data)
        
        print(f"Is Finish Line email: {is_finishline}")
        print(f"Is cancellation email: {is_cancellation}")
        
        if not is_finishline:
            print("\n❌ Email is not identified as Finish Line email")
            return None
        
        if not is_cancellation:
            print("\n❌ Email is not identified as cancellation email")
            return None
        
        print("\n✅ Email identified as Finish Line cancellation")
        
        print("\n" + "=" * 80)
        print("Parsing cancellation email...")
        print("=" * 80)
        
        cancellation_data = parser.parse_cancellation_email(email_data)
        
        if not cancellation_data:
            print("\n❌ Failed to parse cancellation email")
            return None
        
        print(f"\n✅ Successfully parsed cancellation email!")
        print(f"\n📦 Cancellation Data:")
        print(f"  Order Number: {cancellation_data.order_number}")
        print(f"  Items Count: {len(cancellation_data.items)}")
        print(f"  Is Full Cancellation: {cancellation_data.is_full_cancellation}")
        
        print("\n" + "-" * 80)
        print("Items:")
        print("-" * 80)
        
        for idx, item in enumerate(cancellation_data.items, 1):
            print(f"\nItem {idx}:")
            print(f"  Product Name: {item.product_name}")
            print(f"  Unique ID: {item.unique_id}")
            print(f"  Size: {item.size}")
            print(f"  Quantity: {item.quantity}")
            
            # Verify unique ID format
            print(f"\n  ✅ Unique ID Verification:")
            print(f"     Format: SKU from product image URL")
            print(f"     Expected pattern: alphanumeric with underscores (e.g., 'HQ2037_100', '943345_041')")
            if re.match(r'^[A-Z0-9_-]+$', item.unique_id):
                print(f"     ✓ Valid format (SKU)")
            else:
                print(f"     ⚠ Unexpected format: {item.unique_id}")
        
        print("\n" + "=" * 80)
        
        return cancellation_data
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    if len(sys.argv) >= 2:
        email_file_name = sys.argv[1]
    else:
        email_file_name = "finishline.txt"
    
    test_finishline_cancellation_from_file(email_file_name)
