"""
Test script to parse cancellation email and verify it extracts order number, size, and quantity correctly.

Usage:
    python test_cancellation.py
"""

import sys
from pathlib import Path
from app.services.footlocker_parser import FootlockerEmailParser
from app.models.email import EmailData

def test_cancellation_email():
    """Test parsing the cancellation email file"""
    
    # Read the cancellation email HTML file
    email_file = Path(__file__).parent / "feed" / "footlocker-cancel-order.txt"
    
    if not email_file.exists():
        print(f"Error: Email file not found at {email_file}")
        return
    
    print(f"Reading cancellation email from: {email_file}")
    print("=" * 80)
    
    with open(email_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Create EmailData object
    email_data = EmailData(
        message_id="test-123",
        thread_id="test-thread-123",
        subject="An item is no longer available",
        sender="accountservices@em.footlocker.com",
        html_content=html_content
    )
    
    # Parse the cancellation email
    parser = FootlockerEmailParser()
    
    print("\nParsing cancellation email...")
    cancellation_data = parser.parse_cancellation_email(email_data)
    
    if not cancellation_data:
        print("❌ Failed to parse cancellation email")
        return
    
    print("\n✅ Successfully parsed cancellation email!")
    print("=" * 80)
    print(f"\nOrder Number: {cancellation_data.order_number}")
    print(f"Number of items: {len(cancellation_data.items)}")
    print("\nItems:")
    print("-" * 80)
    
    for idx, item in enumerate(cancellation_data.items, 1):
        print(f"\nItem {idx}:")
        print(f"  Product Name: {item.product_name}")
        print(f"  Size: {item.size}")
        print(f"  Quantity: {item.quantity}")
        print(f"  Unique ID: {item.unique_id}")
    
    print("\n" + "=" * 80)
    print("\nExpected values:")
    print("  Order Number: P7382450382716272640")
    print("  Product Name: Nike Air Zoom Pegasus 41 - Men's")
    print("  Size: 11.0 (should normalize to 11)")
    print("  Quantity: 1")
    print("\n" + "=" * 80)
    
    # Verify expected values
    expected_order = "P7382450382716272640"
    expected_size = "11.0"  # Will be normalized to "11"
    expected_qty = 1
    
    success = True
    
    if cancellation_data.order_number != expected_order:
        print(f"\n⚠️  Order number mismatch: expected {expected_order}, got {cancellation_data.order_number}")
        success = False
    
    if len(cancellation_data.items) == 0:
        print("\n⚠️  No items found in cancellation email")
        success = False
    else:
        item = cancellation_data.items[0]
        # Check normalized size (should be "11" not "11.0")
        normalized_size = parser._clean_size(item.size) if hasattr(parser, '_clean_size') else item.size
        if normalized_size != "11" and item.size != expected_size:
            print(f"\n⚠️  Size mismatch: expected {expected_size} (normalized: 11), got {item.size} (normalized: {normalized_size})")
            success = False
        
        if item.quantity != expected_qty:
            print(f"\n⚠️  Quantity mismatch: expected {expected_qty}, got {item.quantity}")
            success = False
    
    if success:
        print("\n✅ All values match expected results!")
    else:
        print("\n❌ Some values don't match expected results")


if __name__ == "__main__":
    test_cancellation_email()

