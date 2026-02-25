"""
Test script to parse Hibbett shipping emails and verify extraction.

Usage:
    python -m test.test_hibbett_shipping                    # Search Gmail for first email (DEFAULT)
    python test/test_hibbett_shipping.py                     # Run directly from Gmail (from backend dir)
    python -m test.test_hibbett_shipping hibbett-shipping-order.txt   # Use specific email file (optional)
"""

import sys
import re
from pathlib import Path

# Add parent directory to path for direct execution
if __name__ == "__main__" and __package__ is None:
    backend_dir = Path(__file__).parent.parent
    sys.path.insert(0, str(backend_dir))

from app.services.hibbett_parser import HibbettEmailParser
from app.models.email import EmailData

# Only import GmailService if needed (for Gmail testing)
try:
    from app.services.gmail_service import GmailService
    GMAIL_AVAILABLE = True
except ImportError:
    GMAIL_AVAILABLE = False


def test_hibbett_shipping_from_gmail():
    """Test parsing the first Hibbett shipping email from Gmail"""
    
    if not GMAIL_AVAILABLE:
        print("❌ GmailService not available (google libraries not installed)")
        print("   Please install: pip install google-api-python-client google-auth-oauthlib")
        return None
    
    print("Searching Gmail for Hibbett shipping emails...")
    print("=" * 80)
    
    try:
        gmail_service = GmailService()
        parser = HibbettEmailParser()
        
        # Build search query - use shipping email address and subject pattern
        from_email = parser.update_from_email
        subject_query = parser.shipping_subject_query
        
        if parser.settings.is_development:
            query = f'from:{from_email} {subject_query}'
        else:
            query = f'from:{from_email} {subject_query}'
        
        print(f"Search query: {query}")
        print(f"Environment: {'Development' if parser.settings.is_development else 'Production'}")
        
        # Get first email
        message_ids = gmail_service.list_messages_with_query(
            query=query,
            max_results=1
        )
        
        if not message_ids:
            print("❌ No Hibbett shipping emails found")
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
        
        # Verify it's a Hibbett shipping email
        if not parser.is_hibbett_email(email_data):
            print("\n❌ Email is not identified as Hibbett email")
            return None
        
        if not parser.is_shipping_email(email_data):
            print("\n❌ Email is not identified as shipping email")
            return None
        
        print("\n✅ Email confirmed as Hibbett shipping email")
        
        # Parse the email
        print("\nParsing Hibbett shipping email...")
        shipping_data = parser.parse_shipping_email(email_data)
        
        if not shipping_data:
            print("❌ Failed to parse shipping email")
            return None
        
        _print_shipping_result(shipping_data)
        return shipping_data
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_hibbett_shipping_from_file(email_file_name: str):
    """Test parsing Hibbett shipping email from a file"""
    
    # Determine file path - shipping emails are in order-shipping-emails folder
    email_file = Path(__file__).parent.parent / "feed" / "order-shipping-emails" / email_file_name
    
    if not email_file.exists():
        print(f"Error: Email file not found at {email_file}")
        return None
    
    print(f"Reading Hibbett shipping email from: {email_file}")
    print("=" * 80)
    
    with open(email_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Create EmailData object
    email_data = EmailData(
        message_id="test-123",
        thread_id="test-thread-123",
        subject="Your order has shipped!",
        sender="hibbett@email.hibbett.com",
        html_content=html_content
    )
    
    # Parse the email
    parser = HibbettEmailParser()
    
    # Verify email type detection
    print("\n🔍 Email Type Detection:")
    print(f"  Is Hibbett email: {parser.is_hibbett_email(email_data)}")
    print(f"  Is shipping email: {parser.is_shipping_email(email_data)}")
    
    print("\nParsing Hibbett shipping email...")
    shipping_data = parser.parse_shipping_email(email_data)
    
    if not shipping_data:
        print("❌ Failed to parse shipping email")
        return None
    
    _print_shipping_result(shipping_data)
    return shipping_data


def _print_shipping_result(shipping_data):
    """Print shipping parse results"""
    print("\n✅ Successfully parsed shipping email!")
    print("=" * 80)
    print(f"\n📦 Shipping Data:")
    print(f"  Order Number: {shipping_data.order_number}")
    print(f"  Items Count: {len(shipping_data.items)}")
    
    print("\n" + "-" * 80)
    print("Items:")
    print("-" * 80)
    
    for idx, item in enumerate(shipping_data.items, 1):
        print(f"\nItem {idx}:")
        print(f"  Product Name: {item.product_name}")
        print(f"  Unique ID: {item.unique_id}")
        print(f"  Size: {item.size} {'(placeholder - Size missing in email)' if item.size == '0' else ''}")
        print(f"  Quantity: {item.quantity}")
        if item.product_number:
            print(f"  Product #: {item.product_number}")
        if item.color:
            print(f"  Color: {item.color}")
        if item.price:
            print(f"  Price: ${item.price}")
        
        # Verify unique ID format
        print(f"\n  ✅ Unique ID Verification:")
        print(f"     Format: Product # (numeric) or generated from product name")
        if re.match(r'^\d+$', item.unique_id):
            print(f"     ✓ Valid format (Product #)")
        else:
            print(f"     Format: {item.unique_id}")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    if len(sys.argv) >= 2:
        # Use file if provided
        email_file_name = sys.argv[1]
        test_hibbett_shipping_from_file(email_file_name)
    else:
        # Search Gmail for first email (DEFAULT)
        test_hibbett_shipping_from_gmail()
