"""
Test script to parse Finish Line cancellation emails and verify extraction.

Usage:
    python -m test.test_finishline_cancellation                    # Search Gmail for first email (DEFAULT)
    python test/test_finishline_cancellation.py                    # Run directly from Gmail (from backend dir)
    python -m test.test_finishline_cancellation finishline.txt    # Use specific email file (optional)
"""

import sys
import os
import re

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import EmailData first (no dependencies)
from app.models.email import EmailData

# Import parser directly to avoid __init__.py GmailService dependency
import importlib.util
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
parser_path = os.path.join(backend_dir, 'app', 'services', 'finishline_parser.py')
spec = importlib.util.spec_from_file_location("finishline_parser", parser_path)
finishline_parser_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(finishline_parser_module)

FinishLineEmailParser = finishline_parser_module.FinishLineEmailParser
FinishLineCancellationData = finishline_parser_module.FinishLineCancellationData

# Only import GmailService if needed (for Gmail testing)
try:
    from app.services.gmail_service import GmailService
    GMAIL_AVAILABLE = True
except ImportError:
    GMAIL_AVAILABLE = False

def test_finishline_cancellation_from_gmail():
    """Test parsing the latest Finish Line cancellation email from Gmail"""
    
    if not GMAIL_AVAILABLE:
        print("❌ GmailService not available (google libraries not installed)")
        print("   Please install: pip install google-api-python-client google-auth-oauthlib")
        return None
    
    print("Searching Gmail for latest Finish Line cancellation email...")
    print("=" * 80)
    
    try:
        gmail_service = GmailService()
        parser = FinishLineEmailParser()
        
        # Build search query - use cancellation email address and subject pattern
        from_email = parser.FINISHLINE_FROM_EMAIL
        
        # For Gmail queries, search for cancellation emails
        if parser.settings.is_development:
            query = f'from:{parser.DEV_FINISHLINE_ORDER_FROM_EMAIL} (subject:(cancel OR cancellation OR "order cancel") OR "your order has been canceled" OR "order canceled")'
        else:
            query = f'from:{from_email} (subject:(cancel OR cancellation OR "order cancel") OR "your order has been canceled" OR "order canceled")'
        
        print(f"Search query: {query}")
        print(f"Environment: {'Development' if parser.settings.is_development else 'Production'}")
        
        # Get latest email (first result is most recent)
        message_ids = gmail_service.list_messages_with_query(
            query=query,
            max_results=1
        )
        
        if not message_ids:
            print("❌ No Finish Line cancellation emails found")
            return None
        
        message_id = message_ids[0]
        print(f"Found latest email: {message_id}")
        
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
        
        # Check HTML content for Finish Line indicators
        has_finishline_indicators = False
        if email_data.html_content:
            html_lower = email_data.html_content.lower()
            has_finishline = 'finish line' in html_lower or 'finishline' in html_lower
            has_cancellation = 'order canceled' in html_lower or 'canceled' in html_lower or 'your order has been canceled' in html_lower
            
            if has_finishline and has_cancellation:
                has_finishline_indicators = True
                print(f"  ✓ Contains Finish Line cancellation indicators")
            else:
                print(f"  ⚠ Missing indicators (finishline: {has_finishline}, cancellation: {has_cancellation})")
        
        # Verify it's a Finish Line email
        if not parser.is_finishline_email(email_data):
            print("\n❌ Email is not identified as Finish Line email")
            return None
        
        # Verify it's a cancellation email
        if not parser.is_cancellation_email(email_data):
            print("\n❌ Email is not identified as cancellation email")
            return None
        
        print("\n✅ Email identified as Finish Line cancellation")
        
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
            
            # Verify unique ID format (should be SKU from image URL, e.g., "HQ2037_100" or "943345_041")
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

def test_finishline_cancellation_from_file(email_file_name: str):
    """Test parsing Finish Line cancellation email from a file"""
    
    print(f"Reading Finish Line cancellation email from file: {email_file_name}")
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
            sender="finishline@notifications.finishline.com",
            html_content=html_content
        )
        
        # Parse cancellation email
        parser = FinishLineEmailParser()
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
        # Use file if provided
        email_file_name = sys.argv[1]
        test_finishline_cancellation_from_file(email_file_name)
    else:
        # Search Gmail for latest email (DEFAULT)
        test_finishline_cancellation_from_gmail()
