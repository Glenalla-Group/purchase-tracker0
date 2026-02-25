"""
Test script to parse Sneaker Politics order confirmation emails and verify extraction.

Usage:
    python -m test.test_sneaker                    # Search Gmail for first email
    python -m test.test_sneaker sneaker.txt       # Use specific email file
    python test/test_sneaker.py                    # Run directly (from backend dir)
"""

import sys
import re
from pathlib import Path

# Add parent directory to path for direct execution
if __name__ == "__main__" and __package__ is None:
    backend_dir = Path(__file__).parent.parent
    sys.path.insert(0, str(backend_dir))

from app.services.sneaker_parser import SneakerPoliticsEmailParser
from app.services.gmail_service import GmailService
from app.models.email import EmailData

def test_sneaker_email_from_gmail():
    """Test parsing the first Sneaker Politics order confirmation email from Gmail"""
    
    print("Searching Gmail for Sneaker Politics order confirmation emails...")
    print("=" * 80)
    
    try:
        gmail_service = GmailService()
        parser = SneakerPoliticsEmailParser()
        
        # Build search query - use environment-aware email address and subject pattern
        from_email = parser.order_from_email
        subject_query = parser.order_subject_query
        # For forwarded emails, use a more flexible pattern
        # Gmail queries work better without quotes for partial matches
        if parser.settings.is_development:
            # Search for emails from sender with "order" or "sneaker" in subject (more flexible)
            query = f'from:{from_email} subject:(order OR sneaker OR "order confirmation" OR "thank you for your purchase")'
        else:
            query = f'from:{from_email} subject:"{subject_query}"'
        
        print(f"Search query: {query}")
        
        # Get first email
        message_ids = gmail_service.list_messages_with_query(
            query=query,
            max_results=1
        )
        
        if not message_ids:
            print("❌ No Sneaker Politics order confirmation emails found")
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
        
        # Check HTML content for Sneaker Politics indicators
        has_sneaker_indicators = False
        if email_data.html_content:
            html_lower = email_data.html_content.lower()
            has_sneaker = 'sneaker politics' in html_lower or 'sneakerpolitics' in html_lower
            has_order_text = "order confirmation" in html_lower or "order #" in html_lower or "thank you for your purchase" in html_lower
            
            print(f"\n🔍 Content Analysis:")
            print(f"  Contains 'sneaker politics': {has_sneaker}")
            print(f"  Contains 'order confirmation' or 'order #': {has_order_text}")
            
            has_sneaker_indicators = has_sneaker or has_order_text
        
        # Validate it's actually a Sneaker Politics email before parsing
        # In dev mode, also require HTML content indicators since multiple retailers use same sender
        if parser.settings.is_development and not has_sneaker_indicators:
            print(f"\n❌ Email does not contain Sneaker Politics indicators in HTML content")
            print(f"   (In dev mode, emails from {parser.order_from_email} must have Sneaker Politics branding)")
            return None
        
        if not parser.is_sneaker_email(email_data):
            print(f"\n❌ Email is not from Sneaker Politics (from: {email_data.sender})")
            return None
        
        if not parser.is_order_confirmation_email(email_data):
            print(f"\n❌ Email is not a Sneaker Politics order confirmation (subject: {email_data.subject})")
            return None
        
        print(f"\n✅ Email confirmed as Sneaker Politics order confirmation")
        
        # Parse the email
        print("\nParsing Sneaker Politics order confirmation email...")
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

def test_sneaker_email(email_file_name: str):
    """Test parsing a Sneaker Politics order confirmation email file"""
    
    # Read the email HTML file
    email_file = Path(__file__).parent.parent / "feed" / "order-confirmation-emails" / email_file_name
    
    if not email_file.exists():
        print(f"Error: Email file not found at {email_file}")
        return None
    
    print(f"Reading Sneaker Politics email from: {email_file}")
    print("=" * 80)
    
    with open(email_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Create EmailData object
    email_data = EmailData(
        message_id="test-123",
        thread_id="test-thread-123",
        subject="Order confirmation",
        sender="store+2147974@t.shopifyemail.com",
        html_content=html_content
    )
    
    # Parse the email
    parser = SneakerPoliticsEmailParser()
    
    print("\nParsing Sneaker Politics order confirmation email...")
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

if __name__ == "__main__":
    if len(sys.argv) >= 2:
        # Use file if provided
        email_file_name = sys.argv[1]
        test_sneaker_email(email_file_name)
    else:
        # Search Gmail for first email
        test_sneaker_email_from_gmail()
