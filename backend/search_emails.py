"""
Search emails with Gmail query and display HTML content of the first matching email.

Usage:
    python search_emails.py "from:example@email.com"                    # Search by from email
    python search_emails.py "from:example@email.com subject:order"      # Search with multiple filters
    python search_emails.py "from:example@email.com" --html-only       # Show only HTML content
    python search_emails.py --last                                     # Get last email from inbox
    python search_emails.py --last --html-only                          # Get last email, HTML only
"""

import sys
import logging
from app.services.gmail_service import GmailService

# Configure logging to console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_last_email(html_only: bool = False):
    """
    Get the last (most recent) email from inbox and display HTML content.
    
    Args:
        html_only: If True, only print HTML content without other metadata
    """
    print(f"\n{'=' * 80}")
    print("Getting last email from inbox...")
    print(f"{'=' * 80}\n")
    
    # Initialize Gmail service
    try:
        gmail_service = GmailService()
    except Exception as e:
        print(f"✗ Failed to initialize Gmail service: {e}")
        return
    
    # Get the last message from inbox (no query, just get latest)
    message_ids = gmail_service.list_messages(max_results=1, query="")
    
    if not message_ids:
        print("No messages found in inbox.")
        return
    
    message_id = message_ids[0]
    _display_email(message_id, gmail_service, html_only, is_last=True)


def search_emails(query: str, html_only: bool = False):
    """
    Search emails with Gmail query and display HTML content of the first matching email.
    
    Args:
        query: Gmail search query (e.g., "from:example@email.com subject:test")
        html_only: If True, only print HTML content without other metadata
    """
    print(f"\n{'=' * 80}")
    print(f"Searching for first matching email with query: {query}")
    print(f"{'=' * 80}\n")
    
    # Initialize Gmail service
    try:
        gmail_service = GmailService()
    except Exception as e:
        print(f"✗ Failed to initialize Gmail service: {e}")
        return
    
    # Search for messages (only need first one)
    message_ids = gmail_service.list_messages_with_query(
        query=query,
        max_results=1
    )
    
    if not message_ids:
        print("No messages found matching the query.")
        return
    
    message_id = message_ids[0]
    _display_email(message_id, gmail_service, html_only, is_last=False)


def _display_email(message_id: str, gmail_service: GmailService, html_only: bool, is_last: bool = False):
    """
    Display email content (shared by search and last email functions).
    
    Args:
        message_id: Gmail message ID
        gmail_service: GmailService instance
        html_only: If True, only print HTML content without other metadata
        is_last: If True, this is the last email (affects header message)
    """
    try:
        if not html_only:
            print(f"Message ID: {message_id}")
            print("-" * 80)
        
        # Fetch email
        message = gmail_service.get_message(message_id, format='full')
        if not message:
            print(f"✗ Failed to fetch message")
            return
        
        # Parse to EmailData
        email_data = gmail_service.parse_message_to_email_data(message)
        
        if not html_only:
            print(f"Subject: {email_data.subject}")
            print(f"From: {email_data.sender}")
            print(f"Date: {email_data.date}")
            print(f"Message ID: {email_data.message_id}")
            print(f"Thread ID: {email_data.thread_id}")
            print(f"Labels: {', '.join(email_data.labels) if email_data.labels else 'None'}")
            print(f"\nSnippet: {email_data.snippet or 'N/A'}")
            print("\nHTML Content:")
            print("-" * 80)
        
        # Display HTML content
        if email_data.html_content:
            html_lines = email_data.html_content.split('\n')
            for line in html_lines:
                if html_only:
                    print(line)
                else:
                    print(line)
        else:
            print("(No HTML content available)")
            if email_data.text_content:
                if not html_only:
                    print("\nPlain text content:")
                    print("-" * 80)
                text_lines = email_data.text_content.split('\n')
                for line in text_lines:
                    if html_only:
                        print(line)
                    else:
                        print(line)
        
        if not html_only:
            print("-" * 80)
    
    except Exception as e:
        print(f"✗ Error processing message {message_id}: {e}")
        logger.exception(f"Error processing message {message_id}")
    
    print("=" * 80)


if __name__ == "__main__":
    # Parse command line arguments
    html_only = '--html-only' in sys.argv
    get_last = '--last' in sys.argv or '--latest' in sys.argv
    
    # Filter out flags to find the query (if any)
    non_flag_args = [arg for arg in sys.argv[1:] if not arg.startswith('--')]
    
    # If --last flag is used, get the last email
    if get_last:
        get_last_email(html_only)
    else:
        # Otherwise, require a query
        if not non_flag_args:
            print("Usage: python search_emails.py <query> [--html-only]")
            print("   OR: python search_emails.py --last [--html-only]")
            print("\nExamples:")
            print('  python search_emails.py "from:example@email.com"')
            print('  python search_emails.py "subject:order"')
            print('  python search_emails.py \'subject:"footlocker get ready"\'')
            print('  python search_emails.py "from:example@email.com subject:order"')
            print('  python search_emails.py "from:example@email.com" --html-only')
            print('  python search_emails.py --last                    # Get last email from inbox')
            print('  python search_emails.py --last --html-only          # Get last email, HTML only')
            print("\nGmail query syntax:")
            print("  from:email@example.com              - Search by sender")
            print("  subject:keyword                      - Search single word in subject")
            print('  subject:"multiple words"             - Search phrase in subject (use quotes!)')
            print("  has:attachment                       - Has attachments")
            print("  after:2024/1/1                       - After date")
            print("  before:2024/12/31                    - Before date")
            print("  label:INBOX                          - In specific label")
            print("  -label:Processed                     - Exclude label")
            print("  Combine with AND/OR: from:email AND subject:test")
            print("\nNote: For multi-word subject searches, use quotes:")
            print('  subject:"footlocker get ready"      ✓ Correct')
            print('  subject:footlocker get ready         ✗ Wrong (will search for "get ready" separately)')
            sys.exit(1)
        
        query = non_flag_args[0]  # Use first non-flag argument as query
        search_emails(query, html_only)

