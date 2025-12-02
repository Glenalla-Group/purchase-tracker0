"""
Manual email processing script with control over how many emails to process.

Usage:
    python process_emails.py           # Process 5 latest emails
    python process_emails.py 10        # Process 10 latest emails
    python process_emails.py 1         # Process 1 latest email
"""

import sys
import asyncio
from app.services.gmail_service import GmailService
from app.services.email_parser import EmailParser

def process_emails(max_emails: int = 5):
    """Process emails manually."""
    print(f"Fetching and processing {max_emails} latest emails...\n")
    
    # Initialize services
    gmail_service = GmailService()
    email_parser = EmailParser()
    
    # Fetch message IDs
    message_ids = gmail_service.list_messages(max_results=max_emails)
    
    if not message_ids:
        print("No messages found.")
        return
    
    print(f"Found {len(message_ids)} messages\n")
    print("=" * 80)
    
    # Process each message
    for idx, message_id in enumerate(message_ids, 1):
        try:
            print(f"\n[{idx}/{len(message_ids)}] Processing message {message_id}...")
            
            # Fetch email
            message = gmail_service.get_message(message_id)
            if not message:
                print(f"  ✗ Failed to fetch message")
                continue
            
            # Parse to EmailData
            email_data = gmail_service.parse_message_to_email_data(message)
            print(f"  Subject: {email_data.subject}")
            print(f"  From: {email_data.sender}")
            print(f"  Date: {email_data.date}")
            
            # Extract information
            extracted_info = email_parser.parse_email(email_data)
            
            if extracted_info.extraction_successful:
                print(f"  ✓ Extraction successful!")
                
                if extracted_info.order_number:
                    print(f"    Order #: {extracted_info.order_number}")
                if extracted_info.total_amount:
                    print(f"    Amount: ${extracted_info.total_amount}")
                if extracted_info.merchant:
                    print(f"    Merchant: {extracted_info.merchant}")
                if extracted_info.purchase_date:
                    print(f"    Date: {extracted_info.purchase_date}")
                if extracted_info.items:
                    print(f"    Items: {len(extracted_info.items)} item(s)")
            else:
                print(f"  ✗ Extraction failed: {extracted_info.error_message}")
            
        except Exception as e:
            print(f"  ✗ Error: {e}")
    
    print("\n" + "=" * 80)
    print(f"\nProcessed {len(message_ids)} emails")


if __name__ == "__main__":
    # Get number of emails from command line
    max_emails = 5
    if len(sys.argv) > 1:
        try:
            max_emails = int(sys.argv[1])
        except ValueError:
            print(f"Invalid number: {sys.argv[1]}")
            print("Usage: python process_emails.py [number]")
            sys.exit(1)
    
    process_emails(max_emails)



