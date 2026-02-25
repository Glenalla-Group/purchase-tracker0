"""
Test Hibbett order confirmation email extraction.

Usage:
    python test/test_hibbett_extraction.py hibbett1.txt
"""

import sys
from pathlib import Path

# Add parent directory to path for direct execution
if __name__ == "__main__" and __package__ is None:
    backend_dir = Path(__file__).parent.parent
    sys.path.insert(0, str(backend_dir))

from app.services.hibbett_parser import HibbettEmailParser
from app.models.email import EmailData

def test_hibbett_extraction(email_file_name: str):
    """Test parsing a Hibbett order confirmation email file"""
    
    # Read the email HTML file
    email_file = Path(__file__).parent.parent / "feed" / "order-confirmation-emails" / email_file_name
    
    if not email_file.exists():
        print(f"Error: Email file not found at {email_file}")
        return None
    
    print(f"Reading Hibbett email from: {email_file}")
    print("=" * 80)
    
    with open(email_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Create EmailData object
    email_data = EmailData(
        message_id="test-123",
        thread_id="test-thread-123",
        subject="Confirmation of your Order",
        sender="hibbett@email.hibbett.com",
        html_content=html_content
    )
    
    # Parse the email
    parser = HibbettEmailParser()
    
    print("\nParsing Hibbett order confirmation email...")
    order_data = parser.parse_email(email_data)
    
    if not order_data:
        print("❌ Failed to parse order email")
        return None
    
    print("\n✅ Successfully parsed order email!")
    print("=" * 80)
    print(f"\nOrder Number: {order_data.order_number}")
    print(f"Number of items: {len(order_data.items)}")
    print(f"Shipping Address: {order_data.shipping_address}")
    print("\nItems:")
    print("-" * 80)
    
    for idx, item in enumerate(order_data.items, 1):
        print(f"\nItem {idx}:")
        print(f"  Product Name: {item.product_name}")
        print(f"  Unique ID: {item.unique_id}")
        print(f"  Size: {item.size}")
        print(f"  Quantity: {item.quantity}")
    
    print("\n" + "=" * 80)
    
    # Expected results
    if email_file_name == "hibbett1.txt":
        print("\nExpected results for hibbett1.txt:")
        print("  Shipping Address: 595 Lloyd Lane")
        print("  (Should NOT include: Griffin Myers, Independence OR, phone number)")
    
    return order_data

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test/test_hibbett_extraction.py <email_file>")
        print("Example: python test/test_hibbett_extraction.py hibbett1.txt")
        sys.exit(1)
    
    email_file_name = sys.argv[1]
    test_hibbett_extraction(email_file_name)
