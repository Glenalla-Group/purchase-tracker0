"""
Test script to parse Orleans Shoe Co cancellation emails and verify extraction.

Usage:
    python -m test.test_orleans_cancellation                    # Search Gmail for first email (DEFAULT)
    python test/test_orleans_cancellation.py                    # Run directly from Gmail (from backend dir)
    python -m test.test_orleans_cancellation orleans.txt       # Use specific email file (optional)
"""

import sys
import os
import re

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.orleans_parser import OrleansEmailParser, OrleansCancellationData
from app.services.gmail_service import GmailService
from app.models.email import EmailData

def test_orleans_cancellation_from_gmail():
    """Test parsing the first Orleans cancellation email from Gmail"""
    
    print("Searching Gmail for Orleans cancellation emails...")
    print("=" * 80)
    
    try:
        gmail_service = GmailService()
        parser = OrleansEmailParser()
        
        # Build search query - use cancellation email address and subject pattern
        from_email = parser.ORLEANS_FROM_EMAIL
        
        # For Gmail queries, search for cancellation emails
        if parser.settings.is_development:
            query = f'from:{parser.DEV_ORLEANS_ORDER_FROM_EMAIL} (subject:(cancel OR cancellation OR "order cancel") OR "your order has been canceled" OR "removed items")'
        else:
            query = f'from:{from_email} (subject:(cancel OR cancellation OR "order cancel") OR "your order has been canceled" OR "removed items")'
        
        print(f"Search query: {query}")
        print(f"Environment: {'Development' if parser.settings.is_development else 'Production'}")
        
        # Get first email
        message_ids = gmail_service.list_messages_with_query(
            query=query,
            max_results=1
        )
        
        if not message_ids:
            print("❌ No Orleans cancellation emails found")
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
        
        # Check HTML content for Orleans indicators
        has_orleans_indicators = False
        if email_data.html_content:
            html_lower = email_data.html_content.lower()
            has_orleans = 'orleans' in html_lower or 'orleans shoe' in html_lower
            has_cancellation = 'canceled' in html_lower or 'cancelled' in html_lower or 'removed items' in html_lower
            
            if has_orleans and has_cancellation:
                has_orleans_indicators = True
                print(f"  ✓ Contains Orleans cancellation indicators")
            else:
                print(f"  ⚠ Missing indicators (orleans: {has_orleans}, cancellation: {has_cancellation})")
        
        # Verify it's an Orleans email
        if not parser.is_orleans_email(email_data):
            print("\n❌ Email is not identified as Orleans email")
            return None
        
        # Verify it's a cancellation email
        if not parser.is_cancellation_email(email_data):
            print("\n❌ Email is not identified as cancellation email")
            return None
        
        print("\n✅ Email identified as Orleans cancellation")
        
        # Parse cancellation email
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
        
        print("\n" + "-" * 80)
        print("Items:")
        print("-" * 80)
        
        for idx, item in enumerate(cancellation_data.items, 1):
            print(f"\nItem {idx}:")
            print(f"  Product Name: {item.product_name}")
            print(f"  Unique ID: {item.unique_id}")
            print(f"  Size: {item.size}")
            print(f"  Quantity: {item.quantity}")
            
            # Verify unique ID format (should be URL-friendly slug, e.g., "on-womens-cloudgo-rose-magnet")
            print(f"\n  ✅ Unique ID Verification:")
            print(f"     Format: URL-friendly slug from product link or product name")
            print(f"     Expected pattern: lowercase with hyphens (e.g., 'on-womens-cloudgo-rose-magnet')")
            if re.match(r'^[a-z0-9-]+$', item.unique_id):
                print(f"     ✓ Valid format (URL-friendly slug)")
            else:
                print(f"     ⚠ Unexpected format: {item.unique_id}")
        
        print("\n" + "=" * 80)
        
        return cancellation_data
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_orleans_cancellation_from_file(email_file_name: str):
    """Test parsing Orleans cancellation email from a file"""
    
    print(f"Reading Orleans cancellation email from file: {email_file_name}")
    print("=" * 80)
    
    try:
        # Determine file path
        if os.path.isabs(email_file_name):
            file_path = email_file_name
        else:
            # Try relative to test directory
            test_dir = os.path.dirname(__file__)
            file_path = os.path.join(test_dir, '..', 'feed', 'order-cancellation-emails', email_file_name)
            if not os.path.exists(file_path):
                # Try just the filename in current directory
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
            sender="store+15639833@t.shopifyemail.com",
            html_content=html_content
        )
        
        # Parse cancellation email
        parser = OrleansEmailParser()
        cancellation_data = parser.parse_cancellation_email(email_data)
        
        if not cancellation_data:
            print("\n❌ Failed to parse cancellation email")
            return None
        
        print(f"\n✅ Successfully parsed cancellation email!")
        print(f"\n📦 Cancellation Data:")
        print(f"  Order Number: {cancellation_data.order_number}")
        print(f"  Items Count: {len(cancellation_data.items)}")
        
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
            print(f"     Format: URL-friendly slug from product link or product name")
            print(f"     Expected pattern: lowercase with hyphens (e.g., 'on-womens-cloudgo-rose-magnet')")
            if re.match(r'^[a-z0-9-]+$', item.unique_id):
                print(f"     ✓ Valid format (URL-friendly slug)")
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
        # Use file if provided
        email_file_name = sys.argv[1]
        test_orleans_cancellation_from_file(email_file_name)
    else:
        # Search Gmail for first email
        test_orleans_cancellation_from_gmail()
