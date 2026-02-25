"""
Test script to parse Foot Locker cancellation emails and verify extraction.

Usage:
    python -m test.test_footlocker_cancellation                    # Search Gmail for first email
    python -m test.test_footlocker_cancellation footlocker.txt    # Use specific email file
    python test/test_footlocker_cancellation.py                    # Run directly (from backend dir)
"""

import sys
import re
from pathlib import Path

# Add parent directory to path for direct execution
if __name__ == "__main__" and __package__ is None:
    backend_dir = Path(__file__).parent.parent
    sys.path.insert(0, str(backend_dir))

from app.services.footlocker_parser import FootlockerEmailParser
from app.services.gmail_service import GmailService
from app.models.email import EmailData

def test_footlocker_cancellation_from_gmail():
    """Test parsing the first Foot Locker cancellation email from Gmail"""
    
    print("Searching Gmail for Foot Locker cancellation emails...")
    print("=" * 80)
    
    try:
        gmail_service = GmailService()
        parser = FootlockerEmailParser()
        
        # Build search query - use cancellation email address and subject pattern
        from_email = parser.FOOTLOCKER_UPDATE_FROM_EMAIL
        subject_pattern = parser.SUBJECT_CANCELLATION_PATTERN
        
        # For Gmail queries, use a simpler pattern
        if parser.settings.is_development:
            query = f'from:{parser.DEV_FOOTLOCKER_ORDER_FROM_EMAIL} subject:(footlocker OR cancellation OR "out of stock" OR "no longer available")'
        else:
            query = f'from:{from_email} subject:("Sorry, your item is out of stock" OR "An item is no longer available")'
        
        print(f"Search query: {query}")
        
        # Get first email
        message_ids = gmail_service.list_messages_with_query(
            query=query,
            max_results=1
        )
        
        if not message_ids:
            print("❌ No Foot Locker cancellation emails found")
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
        
        # Check HTML content for Foot Locker indicators
        has_footlocker_indicators = False
        if email_data.html_content:
            html_lower = email_data.html_content.lower()
            has_footlocker = 'footlocker' in html_lower or 'foot locker' in html_lower
            has_cancellation_text = "sorry, your item is out of stock" in html_lower or "no longer available" in html_lower or "cancellation" in html_lower
            
            print(f"\n🔍 Content Analysis:")
            print(f"  Contains 'footlocker': {has_footlocker}")
            print(f"  Contains cancellation text: {has_cancellation_text}")
            
            has_footlocker_indicators = has_footlocker or has_cancellation_text
        
        # Validate it's actually a Foot Locker email before parsing
        if not parser.is_footlocker_email(email_data):
            print(f"\n❌ Email is not from Foot Locker (from: {email_data.sender})")
            return None
        
        if not parser.is_cancellation_email(email_data):
            print(f"\n❌ Email is not a Foot Locker cancellation (subject: {email_data.subject})")
            print(f"   Expected pattern: {parser.SUBJECT_CANCELLATION_PATTERN}")
            return None
        
        print(f"\n✅ Email confirmed as Foot Locker cancellation")
        
        # Parse the email
        print("\nParsing Foot Locker cancellation email...")
        cancellation_data = parser.parse_cancellation_email(email_data)
        
        if not cancellation_data:
            print("❌ Failed to parse cancellation email")
            return None
        
        print("\n✅ Successfully parsed cancellation email!")
        print("=" * 80)
        print(f"\nOrder Number: {cancellation_data.order_number}")
        print(f"Number of items: {len(cancellation_data.items)}")
        print("\nItems:")
        print("-" * 80)
        
        for idx, item in enumerate(cancellation_data.items, 1):
            print(f"\nItem {idx}:")
            print(f"  Product Name: {item.product_name}")
            print(f"  Unique ID: {item.unique_id}")
            print(f"  Size: {item.size}")
            print(f"  Quantity: {item.quantity}")
        
        print("\n" + "=" * 80)
        
        return cancellation_data
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_footlocker_cancellation_from_file(email_file_name: str):
    """Test parsing a Foot Locker cancellation email file"""
    
    # Read the email HTML file
    email_file = Path(__file__).parent.parent / "feed" / "order-cancellation-emails" / email_file_name
    
    if not email_file.exists():
        print(f"Error: Email file not found at {email_file}")
        return None
    
    print(f"Reading Foot Locker cancellation email from: {email_file}")
    print("=" * 80)
    
    with open(email_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Create EmailData object
    email_data = EmailData(
        message_id="test-123",
        thread_id="test-thread-123",
        subject="Sorry, your item is out of stock",
        sender="accountservices@em.footlocker.com",
        html_content=html_content
    )
    
    # Parse the email
    parser = FootlockerEmailParser()
    
    print("\nParsing Foot Locker cancellation email...")
    cancellation_data = parser.parse_cancellation_email(email_data)
    
    if not cancellation_data:
        print("❌ Failed to parse cancellation email")
        return None
    
    print("\n✅ Successfully parsed cancellation email!")
    print("=" * 80)
    print(f"\nOrder Number: {cancellation_data.order_number}")
    print(f"Number of items: {len(cancellation_data.items)}")
    print("\nItems:")
    print("-" * 80)
    
    for idx, item in enumerate(cancellation_data.items, 1):
        print(f"\nItem {idx}:")
        print(f"  Product Name: {item.product_name}")
        print(f"  Unique ID: {item.unique_id}")
        print(f"  Size: {item.size}")
        print(f"  Quantity: {item.quantity}")
    
    print("\n" + "=" * 80)
    
    return cancellation_data

if __name__ == "__main__":
    if len(sys.argv) >= 2:
        # Use file if provided
        email_file_name = sys.argv[1]
        test_footlocker_cancellation_from_file(email_file_name)
    else:
        # Search Gmail for first email
        test_footlocker_cancellation_from_gmail()
