"""
Test script to parse Urban Outfitters shipping emails and verify extraction.

Usage:
    python -m test.test_urban_shipping                    # Search Gmail for first email (DEFAULT)
    python test/test_urban_shipping.py                    # Run directly from Gmail (from backend dir)
    python -m test.test_urban_shipping urban.txt          # Use specific email file (optional)
"""

import sys
import re
from pathlib import Path

# Add parent directory to path for direct execution
if __name__ == "__main__" and __package__ is None:
    backend_dir = Path(__file__).parent.parent
    sys.path.insert(0, str(backend_dir))

from app.services.urban_parser import UrbanOutfittersEmailParser
from app.services.gmail_service import GmailService
from app.models.email import EmailData

def test_urban_shipping_from_gmail():
    """Test parsing the first Urban Outfitters shipping email from Gmail"""
    
    print("Searching Gmail for Urban Outfitters shipping emails...")
    print("=" * 80)
    
    try:
        gmail_service = GmailService()
        parser = UrbanOutfittersEmailParser()
        
        # Build search query - use shipping email address and subject pattern
        from_email = parser.URBAN_FROM_EMAIL
        
        # For Gmail queries, search for shipping confirmation emails
        if parser.settings.is_development:
            # In dev, search from dev email with shipping-related terms
            query = f'from:{parser.DEV_URBAN_ORDER_FROM_EMAIL} (subject:(shipping OR "shipping confirmation" OR "order shipped") OR "shipping confirmation" OR "the below items shipped")'
        else:
            # In production, search from Urban Outfitters email
            query = f'from:{from_email} (subject:("Shipping Confirmation" OR "shipping confirmation") OR "shipping confirmation" OR "the below items shipped")'
        
        print(f"Search query: {query}")
        print(f"Environment: {'Development' if parser.settings.is_development else 'Production'}")
        
        # Get first email
        message_ids = gmail_service.list_messages_with_query(
            query=query,
            max_results=1
        )
        
        if not message_ids:
            print("❌ No Urban Outfitters shipping emails found")
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
        
        print(f"\n📧 Email Details:")
        print(f"  From: {email_data.sender}")
        print(f"  Subject: {email_data.subject}")
        print(f"  Date: {email_data.date}")
        print(f"  Has HTML: {bool(email_data.html_content)}")
        
        # Check HTML content for Urban Outfitters indicators
        has_urban_indicators = False
        if email_data.html_content:
            html_lower = email_data.html_content.lower()
            has_urban = 'urbanoutfitters' in html_lower or 'urban outfitters' in html_lower
            has_urbndata = 'images.urbndata.com' in html_lower
            has_shipping_text = "shipping confirmation" in html_lower or "the below items shipped" in html_lower or "tracking number" in html_lower
            
            print(f"\n🔍 Content Analysis:")
            print(f"  Contains 'urbanoutfitters': {has_urban}")
            print(f"  Contains 'images.urbndata.com': {has_urbndata}")
            print(f"  Contains shipping text: {has_shipping_text}")
            
            has_urban_indicators = has_urban or has_urbndata or has_shipping_text
        
        # Validate it's actually an Urban Outfitters email before parsing
        if not parser.is_urban_email(email_data):
            print(f"\n❌ Email is not from Urban Outfitters (from: {email_data.sender})")
            return None
        
        if not parser.is_shipping_email(email_data):
            print(f"\n❌ Email is not an Urban Outfitters shipping email (subject: {email_data.subject})")
            print(f"   Expected pattern: {parser.SUBJECT_SHIPPING_PATTERN}")
            return None
        
        print(f"\n✅ Email confirmed as Urban Outfitters shipping email")
        
        # Parse the email
        print("\nParsing Urban Outfitters shipping email...")
        shipping_data = parser.parse_shipping_email(email_data)
        
        if not shipping_data:
            print("❌ Failed to parse shipping email")
            return None
        
        print("\n✅ Successfully parsed shipping email!")
        print("=" * 80)
        print(f"\nOrder Number: {shipping_data.order_number}")
        print(f"Shipment Type: {shipping_data.shipment_type}")
        print(f"Tracking Number: {shipping_data.tracking_number or 'N/A'}")
        print(f"Number of items: {len(shipping_data.items)}")
        print("\nItems:")
        print("-" * 80)
        
        for idx, item in enumerate(shipping_data.items, 1):
            print(f"\nItem {idx}:")
            print(f"  Product Name: {item.product_name}")
            print(f"  Unique ID: {item.unique_id}")
            if hasattr(item, 'style_number') and item.style_number:
                print(f"  Style Number: {item.style_number}")
            if hasattr(item, 'color') and item.color:
                print(f"  Color: {item.color}")
            print(f"  Size: {item.size}")
            print(f"  Quantity: {item.quantity}")
            
            # Verify unique ID format
            print(f"\n  ✅ Unique ID Verification:")
            print(f"     Format: product-slug-color-code")
            print(f"     Expected pattern: [a-z0-9-]+-[0-9]{3}")
            if re.match(r'^[a-z0-9-]+-[0-9]{3}$', item.unique_id):
                print(f"     ✓ Valid format")
            else:
                print(f"     ✗ Invalid format")
        
        print("\n" + "=" * 80)
        
        return shipping_data
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_urban_shipping_from_file(email_file_name: str):
    """Test parsing an Urban Outfitters shipping email file"""
    
    # Read the email HTML file
    email_file = Path(__file__).parent.parent / "feed" / "order-shipping-emails" / email_file_name
    
    if not email_file.exists():
        print(f"Error: Email file not found at {email_file}")
        return None
    
    print(f"Reading Urban Outfitters shipping email from: {email_file}")
    print("=" * 80)
    
    with open(email_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Create EmailData object
    email_data = EmailData(
        message_id="test-123",
        thread_id="test-thread-123",
        subject="Shipping Confirmation",
        sender="urbanoutfitters@st.urbanoutfitters.com",
        html_content=html_content
    )
    
    # Parse the email
    parser = UrbanOutfittersEmailParser()
    
    # Verify email type detection
    print("\n🔍 Email Type Detection:")
    print(f"  Is Urban Outfitters email: {parser.is_urban_email(email_data)}")
    print(f"  Is shipping email: {parser.is_shipping_email(email_data)}")
    print(f"  Is cancellation email: {parser.is_cancellation_email(email_data)}")
    print(f"  Is order confirmation: {parser.is_order_confirmation_email(email_data)}")
    
    print("\nParsing Urban Outfitters shipping email...")
    shipping_data = parser.parse_shipping_email(email_data)
    
    if not shipping_data:
        print("❌ Failed to parse shipping email")
        return None
    
    print("\n✅ Successfully parsed shipping email!")
    print("=" * 80)
    print(f"\nOrder Number: {shipping_data.order_number}")
    print(f"Shipment Type: {shipping_data.shipment_type}")
    print(f"Tracking Number: {shipping_data.tracking_number or 'N/A'}")
    print(f"Number of items: {len(shipping_data.items)}")
    print("\nItems:")
    print("-" * 80)
    
    for idx, item in enumerate(shipping_data.items, 1):
        print(f"\nItem {idx}:")
        print(f"  Product Name: {item.product_name}")
        print(f"  Unique ID: {item.unique_id}")
        if hasattr(item, 'style_number') and item.style_number:
            print(f"  Style Number: {item.style_number}")
        if hasattr(item, 'color') and item.color:
            print(f"  Color: {item.color}")
        print(f"  Size: {item.size}")
        print(f"  Quantity: {item.quantity}")
        
        # Verify unique ID format
        print(f"\n  ✅ Unique ID Verification:")
        print(f"     Format: product-slug-color-code")
        print(f"     Expected pattern: [a-z0-9-]+-[0-9]{3}")
        if re.match(r'^[a-z0-9-]+-[0-9]{3}$', item.unique_id):
            print(f"     ✓ Valid format")
        else:
            print(f"     ✗ Invalid format")
    
    print("\n" + "=" * 80)
    
    return shipping_data

if __name__ == "__main__":
    if len(sys.argv) >= 2:
        # Use file if provided
        email_file_name = sys.argv[1]
        test_urban_shipping_from_file(email_file_name)
    else:
        # Search Gmail for first email
        test_urban_shipping_from_gmail()
