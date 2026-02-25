"""
Test script to parse Bloomingdale's order confirmation emails and verify extraction.

Usage:
    python -m test.test_bloomingdales                    # Search Gmail for first email
    python -m test.test_bloomingdales bloomingdale.txt    # Use specific email file
    python test/test_bloomingdales.py                     # Run directly (from backend dir)
"""

import sys
import re
from pathlib import Path

# Add parent directory to path for direct execution
if __name__ == "__main__" and __package__ is None:
    backend_dir = Path(__file__).parent.parent
    sys.path.insert(0, str(backend_dir))

from app.services.bloomingdales_parser import BloomingdalesEmailParser
from app.services.gmail_service import GmailService
from app.models.email import EmailData

def test_bloomingdales_email_from_gmail():
    """Test parsing the first Bloomingdale's order confirmation email from Gmail"""
    
    print("Searching Gmail for Bloomingdale's order confirmation emails...")
    print("=" * 80)
    
    try:
        gmail_service = GmailService()
        parser = BloomingdalesEmailParser()
        
        # Build search query - use environment-aware email address and subject pattern
        from_email = parser.order_from_email
        subject_query = parser.order_subject_query
        # For forwarded emails, use a more flexible pattern
        # Gmail queries work better without quotes for partial matches
        if parser.settings.is_development:
            # Search for emails from sender with "order" in subject (more flexible)
            query = f'from:{from_email} subject:order'
        else:
            query = f'from:{from_email} subject:"{subject_query}"'
        
        print(f"Search query: {query}")
        
        # Get first email
        message_ids = gmail_service.list_messages_with_query(
            query=query,
            max_results=1
        )
        
        if not message_ids:
            print("❌ No Bloomingdale's order confirmation emails found")
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
        
        # Check HTML content for Bloomingdale's indicators
        if email_data.html_content:
            html_lower = email_data.html_content.lower()
            has_bloomingdale = 'bloomingdale' in html_lower
            has_bloomingdales_domain = 'emails.bloomingdales.com' in html_lower
            has_order_text = 'we received your order' in html_lower
            has_order_number = bool(re.search(r'order\s*#?\s*:?\s*\d+', html_lower, re.IGNORECASE))
            
            print(f"\n🔍 Content Analysis:")
            print(f"  Contains 'bloomingdale': {has_bloomingdale}")
            print(f"  Contains 'emails.bloomingdales.com': {has_bloomingdales_domain}")
            print(f"  Contains 'we received your order': {has_order_text}")
            print(f"  Contains order number pattern: {has_order_number}")
        
        # Validate it's actually a Bloomingdale's email before parsing
        is_bloomingdales = parser.is_bloomingdales_email(email_data)
        is_order_confirmation = parser.is_order_confirmation_email(email_data)
        
        print(f"\n✅ Email Detection:")
        print(f"  Is Bloomingdale's email: {is_bloomingdales}")
        print(f"  Is order confirmation: {is_order_confirmation}")
        
        if not is_bloomingdales:
            print(f"\n❌ Email is not from Bloomingdale's (from: {email_data.sender})")
            return None
        
        if not is_order_confirmation:
            print(f"\n❌ Email is not a Bloomingdale's order confirmation (subject: {email_data.subject})")
            return None
        
        # Parse the email
        print("\nParsing Bloomingdale's order confirmation email...")
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
            print(f"  UPC: {item.upc}")
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

def test_bloomingdales_email(email_file_name: str):
    """Test parsing a Bloomingdale's order confirmation email file"""
    
    # Read the email HTML file
    email_file = Path(__file__).parent.parent / "feed" / "order-confirmation-emails" / email_file_name
    
    if not email_file.exists():
        print(f"Error: Email file not found at {email_file}")
        return None
    
    print(f"Reading Bloomingdale's email from: {email_file}")
    print("=" * 80)
    
    with open(email_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Create EmailData object
    email_data = EmailData(
        message_id="test-123",
        thread_id="test-thread-123",
        subject="We received your order, Griffin!",
        sender="CustomerService@oes.bloomingdales.com",
        html_content=html_content
    )
    
    # Parse the email
    parser = BloomingdalesEmailParser()
    
    print("\nParsing Bloomingdale's order confirmation email...")
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
        print(f"  UPC: {item.upc}")
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
        test_bloomingdales_email(email_file_name)
    else:
        # Search Gmail for first email
        test_bloomingdales_email_from_gmail()
