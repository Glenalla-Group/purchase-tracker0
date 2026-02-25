"""
Test script to parse Hibbett cancellation emails and verify extraction.

Usage:
    python -m test.test_hibbett_cancellation                    # Search Gmail for latest email (DEFAULT)
    python test/test_hibbett_cancellation.py                    # Run directly from Gmail (from backend dir)
    python -m test.test_hibbett_cancellation hibbett.txt    # Use specific email file (optional)
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
parser_path = os.path.join(backend_dir, 'app', 'services', 'hibbett_parser.py')
spec = importlib.util.spec_from_file_location("hibbett_parser", parser_path)
hibbett_parser_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hibbett_parser_module)

HibbettEmailParser = hibbett_parser_module.HibbettEmailParser
HibbettCancellationData = hibbett_parser_module.HibbettCancellationData

# Only import GmailService if needed (for Gmail testing)
try:
    from app.services.gmail_service import GmailService
    GMAIL_AVAILABLE = True
except ImportError:
    GMAIL_AVAILABLE = False

def test_hibbett_cancellation_from_gmail():
    """Test parsing the latest Hibbett cancellation email from Gmail"""
    
    if not GMAIL_AVAILABLE:
        print("❌ GmailService not available (google libraries not installed)")
        print("   Please install: pip install google-api-python-client google-auth-oauthlib")
        return None
    
    print("Searching Gmail for latest Hibbett cancellation email...")
    print("=" * 80)
    
    try:
        gmail_service = GmailService()
        parser = HibbettEmailParser()
        
        # Build search query - use cancellation email address and subject pattern
        from_email = parser.HIBBETT_FROM_EMAIL
        
        # For Gmail queries, search for cancellation emails
        if parser.settings.is_development:
            query = f'from:{parser.DEV_HIBBETT_ORDER_FROM_EMAIL} (subject:(cancel OR cancellation OR "order has been cancelled") OR "your recent order has been cancelled")'
        else:
            query = f'from:{from_email} (subject:(cancel OR cancellation OR "order has been cancelled") OR "your recent order has been cancelled")'
        
        print(f"Search query: {query}")
        print(f"Environment: {'Development' if parser.settings.is_development else 'Production'}")
        
        # Get latest email (first result is most recent)
        message_ids = gmail_service.list_messages_with_query(
            query=query,
            max_results=1
        )
        
        if not message_ids:
            print("❌ No Hibbett cancellation emails found")
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
        
        # Check HTML content for Hibbett indicators
        has_hibbett_indicators = False
        if email_data.html_content:
            html_lower = email_data.html_content.lower()
            has_hibbett = 'hibbett' in html_lower
            has_cancellation = 'order has been cancelled' in html_lower or 'cancelled' in html_lower or 'item(s) canceled' in html_lower
            
            if has_hibbett and has_cancellation:
                has_hibbett_indicators = True
                print(f"  ✓ Contains Hibbett cancellation indicators")
            else:
                print(f"  ⚠ Missing indicators (hibbett: {has_hibbett}, cancellation: {has_cancellation})")
        
        # Verify it's a Hibbett email
        if not parser.is_hibbett_email(email_data):
            print("\n❌ Email is not identified as Hibbett email")
            return None
        
        # Verify it's a cancellation email
        if not parser.is_cancellation_email(email_data):
            print("\n❌ Email is not identified as cancellation email")
            return None
        
        print("\n✅ Email identified as Hibbett cancellation")
        
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
            
            # Verify unique ID format (should be Product #, e.g., "54388017")
            print(f"\n  ✅ Unique ID Verification:")
            print(f"     Format: Product # (numeric)")
            print(f"     Expected pattern: digits only (e.g., '54388017', '54170572')")
            if re.match(r'^\d+$', item.unique_id):
                print(f"     ✓ Valid format (Product #)")
            else:
                print(f"     ⚠ Unexpected format: {item.unique_id}")
        
        print("\n" + "=" * 80)
        
        return cancellation_data
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_hibbett_cancellation_from_file(email_file_name: str):
    """Test parsing Hibbett cancellation email from a file"""
    
    print(f"Reading Hibbett cancellation email from file: {email_file_name}")
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
            subject="Your recent order has been cancelled",
            sender="hibbett@email.hibbett.com",
            html_content=html_content
        )
        
        # Parse cancellation email
        parser = HibbettEmailParser()
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
            print(f"     Format: Product # (numeric)")
            print(f"     Expected pattern: digits only (e.g., '54388017', '54170572')")
            if re.match(r'^\d+$', item.unique_id):
                print(f"     ✓ Valid format (Product #)")
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
        test_hibbett_cancellation_from_file(email_file_name)
    else:
        # Search Gmail for latest email (DEFAULT)
        test_hibbett_cancellation_from_gmail()
