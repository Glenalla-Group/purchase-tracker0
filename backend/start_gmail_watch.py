"""
Script to start Gmail watch (push notifications)
Run this to enable real-time email notifications
"""

import logging
from app.services.gmail_service import GmailService
from app.config import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def start_gmail_watch():
    """Start Gmail watch to enable push notifications"""
    try:
        settings = get_settings()
        gmail_service = GmailService()
        
        # Setup watch request
        request_body = {
            'labelIds': ['INBOX'],
            'topicName': settings.gmail_pubsub_topic  # e.g., 'projects/YOUR_PROJECT/topics/gmail-notifications'
        }
        
        # Start the watch
        result = gmail_service.service.users().watch(
            userId='me',
            body=request_body
        ).execute()
        
        logger.info("✅ Gmail watch started successfully!")
        logger.info(f"📧 Watching inbox: {result.get('emailAddress')}")
        logger.info(f"📅 Expiration: {result.get('expiration')} (7 days from now)")
        logger.info(f"🆔 History ID: {result.get('historyId')}")
        logger.info("")
        logger.info("🔔 You will now receive real-time email notifications")
        logger.info("⚙️  Set ENABLE_AUTO_EMAIL_PROCESSING=false to disable processing")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Error starting watch: {e}")
        logger.error("")
        logger.error("💡 Make sure:")
        logger.error("   1. GMAIL_PUBSUB_TOPIC is set in .env")
        logger.error("   2. Google Cloud Pub/Sub is configured")
        logger.error("   3. Service account has permissions")
        return None

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🔔 STARTING GMAIL WATCH")
    print("="*60 + "\n")
    
    start_gmail_watch()
    
    print("\n" + "="*60)
    print("✅ DONE - Restart your backend to see notifications")
    print("="*60 + "\n")






