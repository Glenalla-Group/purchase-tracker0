"""
Test script to parse ShopWSS order confirmation emails and verify extraction.

Usage:
    python -m test.test_shopwss                    # Search Gmail for first email
    python -m test.test_shopwss shopwss.txt        # Use specific email file
    python test/test_shopwss.py                   # Run directly (from backend dir)
"""

import sys
from pathlib import Path

# Add parent directory to path for direct execution
if __name__ == "__main__" and __package__ is None:
    backend_dir = Path(__file__).parent.parent
    sys.path.insert(0, str(backend_dir))

from app.services.shopwss_parser import ShopWSSEmailParser
from app.services.gmail_service import GmailService
from app.models.email import EmailData

def test_shopwss_email_from_gmail():
    """Test parsing the first ShopWSS order confirmation email from Gmail"""
    
    print("Searching Gmail for ShopWSS order confirmation emails...")
    print("=" * 80)
    
    try:
        gmail_service = GmailService()
        parser = ShopWSSEmailParser()
        
        # Build search query - use environment-aware email address and subject pattern
        from_email = parser.order_from_email
        subject_query = parser.order_subject_query
        query = f'from:{from_email} subject:"{subject_query}"'
        
        print(f"Search query: {query}")
        
        # Get first email
        message_ids = gmail_service.list_messages_with_query(
            query=query,
            max_results=1
        )
        
        if not message_ids:
            print("❌ No ShopWSS order confirmation emails found")
            return None
        
        message_id = message_ids[0]
        print(f"Found email: {message_id}")
        
        # Get full message
        message = gmail_service.get_message(message_id, format='full')
        if not message:
            print("❌ Failed to retrieve message")
            return None
        
        # Parse to EmailData
        email_data = gmail_service.parse_message_to_email_data(message)
        
        print(f"\nEmail Subject: {email_data.subject}")
        print(f"Email From: {email_data.sender}")
        print(f"Email Date: {email_data.date}")
        
        # Validate it's actually a ShopWSS email before parsing
        if not parser.is_shopwss_email(email_data):
            print(f"❌ Email is not from ShopWSS (from: {email_data.sender})")
            return None
        
        if not parser.is_order_confirmation_email(email_data):
            print(f"❌ Email is not a ShopWSS order confirmation (subject: {email_data.subject})")
            return None
        
        # Parse the email
        print("\nParsing ShopWSS order confirmation email...")
        order_data = parser.parse_email(email_data)
        
        if not order_data:
            print("❌ Failed to parse order email")
            return None
        
        print("\n✅ Successfully parsed order email!")
        print("=" * 80)
        print(f"\nOrder Number: {order_data.order_number}")
        print(f"Number of items: {len(order_data.items)}")
        print("\nItems:")
        print("-" * 80)
        
        for idx, item in enumerate(order_data.items, 1):
            print(f"\nItem {idx}:")
            print(f"  Product Name: {item.product_name}")
            print(f"  Unique ID: {item.unique_id}")
            print(f"  Size: {item.size}")
            print(f"  Quantity: {item.quantity}")
        
        if order_data.shipping_address:
            print(f"\nShipping Address: {order_data.shipping_address}")
        
        print("\n" + "=" * 80)
        
        return order_data
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_shopwss_email(email_file_name: str):
    """Test parsing a ShopWSS email file"""
    
    # Read the email HTML file
    email_file = Path(__file__).parent.parent / "feed" / "order-confirmation-emails" / email_file_name
    
    if not email_file.exists():
        print(f"Error: Email file not found at {email_file}")
        return None
    
    print(f"Reading ShopWSS email from: {email_file}")
    print("=" * 80)
    
    with open(email_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Create EmailData object
    email_data = EmailData(
        message_id="test-123",
        thread_id="test-thread-123",
        subject="Order #1361825686 was received!",
        sender="help@shopwss.com",
        html_content=html_content
    )
    
    # Parse the email
    parser = ShopWSSEmailParser()
    
    print("\nParsing ShopWSS order confirmation email...")
    order_data = parser.parse_email(email_data)
    
    if not order_data:
        print("❌ Failed to parse order email")
        return None
    
    print("\n✅ Successfully parsed order email!")
    print("=" * 80)
    print(f"\nOrder Number: {order_data.order_number}")
    print(f"Number of items: {len(order_data.items)}")
    print("\nItems:")
    print("-" * 80)
    
    for idx, item in enumerate(order_data.items, 1):
        print(f"\nItem {idx}:")
        print(f"  Product Name: {item.product_name}")
        print(f"  Unique ID: {item.unique_id}")
        print(f"  Size: {item.size}")
        print(f"  Quantity: {item.quantity}")
    
    if order_data.shipping_address:
        print(f"\nShipping Address: {order_data.shipping_address}")
    
    print("\n" + "=" * 80)
    
    return order_data


def test_shopwss_shipping_email(email_file_name: str = "shopwss.txt"):
    """Test parsing a ShopWSS shipping email (Order #xxx is about to ship! / partially shipped)."""
    email_file = Path(__file__).parent.parent / "feed" / "order-shipping-emails" / email_file_name
    if not email_file.exists():
        print(f"Error: Email file not found at {email_file}")
        return None
    with open(email_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    email_data = EmailData(
        message_id="test-123",
        thread_id="test-thread-123",
        subject="Order #1361824017 is about to ship!",
        sender="help@shopwss.com",
        html_content=html_content
    )
    parser = ShopWSSEmailParser()
    if not parser.is_shopwss_email(email_data) or not parser.is_shipping_email(email_data):
        print("Email not recognized as ShopWSS shipping")
        return None
    shipping_data = parser.parse_shipping_email(email_data)
    if not shipping_data:
        print("Failed to parse shipping email")
        return None
    print("\n✅ ShopWSS shipping parsed successfully!")
    print(f"Order: {shipping_data.order_number}, Tracking: {shipping_data.tracking_number}")
    for i, item in enumerate(shipping_data.items, 1):
        print(f"  Item {i}: unique_id={item.unique_id}, qty={item.quantity}, product={item.product_name}")
    return shipping_data


if __name__ == "__main__":
    if len(sys.argv) >= 2:
        arg = sys.argv[1]
        if arg == "shipping":
            fname = sys.argv[2] if len(sys.argv) >= 3 else "shopwss.txt"
            test_shopwss_shipping_email(fname)
        else:
            test_shopwss_email(arg)
    else:
        test_shopwss_shipping_email()
