"""
Test script to parse Urban Outfitters order confirmation emails and verify extraction.

Usage:
    python -m test.test_urban                    # Search Gmail for first email
    python -m test.test_urban urban.txt           # Use specific email file
    python test/test_urban.py                     # Run directly (from backend dir)
"""

import sys
from pathlib import Path

# Add parent directory to path for direct execution
if __name__ == "__main__" and __package__ is None:
    backend_dir = Path(__file__).parent.parent
    sys.path.insert(0, str(backend_dir))

from app.services.urban_parser import UrbanOutfittersEmailParser
from app.services.gmail_service import GmailService
from app.models.email import EmailData

def test_urban_email_from_gmail():
    """Test parsing the first Urban Outfitters order confirmation email from Gmail"""
    
    print("Searching Gmail for Urban Outfitters order confirmation emails...")
    print("=" * 80)
    
    try:
        gmail_service = GmailService()
        parser = UrbanOutfittersEmailParser()
        
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
            print("❌ No Urban Outfitters order confirmation emails found")
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
            has_urban_domain = 'urbanoutfitters.com' in html_lower
            
            print(f"\n🔍 Content Analysis:")
            print(f"  Contains 'urbanoutfitters': {has_urban}")
            print(f"  Contains 'images.urbndata.com': {has_urbndata}")
            print(f"  Contains 'urbanoutfitters.com': {has_urban_domain}")
            
            has_urban_indicators = has_urban or has_urbndata or has_urban_domain
        
        # Validate it's actually an Urban Outfitters email before parsing
        # In dev mode, also require HTML content indicators since multiple retailers use same sender
        if parser.settings.is_development and not has_urban_indicators:
            print(f"\n❌ Email does not contain Urban Outfitters indicators in HTML content")
            print(f"   (In dev mode, emails from {parser.order_from_email} must have Urban Outfitters branding)")
            return None
        
        if not parser.is_urban_email(email_data):
            print(f"\n❌ Email is not from Urban Outfitters (from: {email_data.sender})")
            return None
        
        if not parser.is_order_confirmation_email(email_data):
            print(f"\n❌ Email is not an Urban Outfitters order confirmation (subject: {email_data.subject})")
            return None
        
        print(f"\n✅ Email confirmed as Urban Outfitters order confirmation")
        
        # Parse the email
        print("\nParsing Urban Outfitters order confirmation email...")
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
            print(f"  Style Number: {item.style_number}")
            print(f"  Color: {item.color}")
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

def test_urban_email(email_file_name: str):
    """Test parsing an Urban Outfitters order confirmation email file"""
    
    # Read the email HTML file
    email_file = Path(__file__).parent.parent / "feed" / "order-confirmation-emails" / email_file_name
    
    if not email_file.exists():
        print(f"Error: Email file not found at {email_file}")
        return None
    
    print(f"Reading Urban Outfitters email from: {email_file}")
    print("=" * 80)
    
    with open(email_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Create EmailData object
    email_data = EmailData(
        message_id="test-123",
        thread_id="test-thread-123",
        subject="Order Confirmation",
        sender="urbanoutfitters@st.urbanoutfitters.com",
        html_content=html_content
    )
    
    # Parse the email
    parser = UrbanOutfittersEmailParser()
    
    print("\nParsing Urban Outfitters order confirmation email...")
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
        print(f"  Style Number: {item.style_number}")
        print(f"  Color: {item.color}")
        print(f"  Size: {item.size}")
        print(f"  Quantity: {item.quantity}")
    
    if order_data.shipping_address:
        print(f"\nShipping Address: {order_data.shipping_address}")
    
    print("\n" + "=" * 80)
    
    return order_data

if __name__ == "__main__":
    if len(sys.argv) >= 2:
        # Use file if provided
        email_file_name = sys.argv[1]
        test_urban_email(email_file_name)
    else:
        # Search Gmail for first email
        test_urban_email_from_gmail()
