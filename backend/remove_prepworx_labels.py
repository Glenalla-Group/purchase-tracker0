"""
Script to remove all "PrepWorx/Processed" labels from Gmail messages.

This allows you to reprocess emails or clean up the label system.
"""

import sys
import os

# Add platform-specific UTF-8 encoding fix
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    os.environ['PYTHONUTF8'] = '1'

import logging
from app.services.gmail_service import GmailService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def remove_all_prepworx_labels():
    """
    Remove the "PrepWorx/Processed" label from all Gmail threads and messages that have it.
    Uses direct label-based search for maximum effectiveness.
    """
    try:
        logger.info("=" * 70)
        logger.info("🏷️  REMOVING ALL PREPWORX/PROCESSED LABELS")
        logger.info("=" * 70)
        
        # Initialize Gmail service
        gmail_service = GmailService()
        
        # Step 1: List all labels to find PrepWorx ones
        logger.info("Step 1: Searching for PrepWorx-related labels...")
        try:
            results = gmail_service.service.users().labels().list(userId='me').execute()
            all_labels = results.get('labels', [])
            
            # Find all PrepWorx labels (case-insensitive)
            prepworx_labels = []
            for label in all_labels:
                label_name = label['name']
                label_id = label['id']
                if 'prepworx' in label_name.lower() or 'prep' in label_name.lower():
                    prepworx_labels.append((label_name, label_id))
                    logger.info(f"  Found PrepWorx label: '{label_name}' (ID: {label_id})")
            
            if not prepworx_labels:
                logger.info("✓ No PrepWorx labels found in Gmail")
                return
            
        except Exception as e:
            logger.error(f"Error listing labels: {e}")
            return
        
        # Step 2: Process each PrepWorx label
        logger.info("\nStep 2: Removing labels from messages and threads...")
        
        total_removed = 0
        total_errors = 0
        
        for label_name, label_id in prepworx_labels:
            logger.info(f"\n  Processing label: '{label_name}'")
            
            try:
                # Search for messages with this label
                results = gmail_service.service.users().messages().list(
                    userId='me',
                    labelIds=[label_id],
                    maxResults=500
                ).execute()
                
                messages = results.get('messages', [])
                logger.info(f"    Found {len(messages)} messages")
                
                if messages:
                    # Remove label from each message
                    removed_count = 0
                    for idx, msg in enumerate(messages, 1):
                        message_id = msg['id']
                        try:
                            gmail_service.service.users().messages().modify(
                                userId='me',
                                id=message_id,
                                body={'removeLabelIds': [label_id]}
                            ).execute()
                            removed_count += 1
                            if idx % 10 == 0:
                                logger.info(f"      Progress: {idx}/{len(messages)} messages")
                        except Exception as e:
                            total_errors += 1
                            if '404' not in str(e) and 'notFound' not in str(e):
                                logger.error(f"      Error: {e}")
                    
                    logger.info(f"    ✅ Removed from {removed_count} messages")
                    total_removed += removed_count
                
                # Also check and remove from threads
                thread_results = gmail_service.service.users().threads().list(
                    userId='me',
                    labelIds=[label_id],
                    maxResults=500
                ).execute()
                
                threads = thread_results.get('threads', [])
                logger.info(f"    Found {len(threads)} threads")
                
                if threads:
                    thread_removed = 0
                    for thread in threads:
                        try:
                            gmail_service.service.users().threads().modify(
                                userId='me',
                                id=thread['id'],
                                body={'removeLabelIds': [label_id]}
                            ).execute()
                            thread_removed += 1
                        except Exception as e:
                            total_errors += 1
                            if '404' not in str(e) and 'notFound' not in str(e):
                                logger.error(f"      Error: {e}")
                    
                    logger.info(f"    ✅ Removed from {thread_removed} threads")
                    total_removed += thread_removed
                
            except Exception as e:
                logger.error(f"  Error processing label '{label_name}': {e}")
                total_errors += 1
        
        # Summary
        logger.info("\n" + "=" * 70)
        logger.info("📊 SUMMARY")
        logger.info("=" * 70)
        logger.info(f"✅ Total items processed: {total_removed}")
        logger.info(f"❌ Total errors: {total_errors}")
        logger.info("=" * 70)
        
        if total_removed > 0:
            logger.info("\n✓ All PrepWorx labels have been removed!")
            logger.info("  You can now reprocess these emails using the frontend button.")
        else:
            logger.info("\n✓ No PrepWorx labels found or all already removed")
    
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    try:
        remove_all_prepworx_labels()
    except KeyboardInterrupt:
        logger.info("\n⚠️  Operation cancelled by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Script failed: {e}")
        sys.exit(1)

