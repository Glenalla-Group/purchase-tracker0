"""
Script to stop Gmail push notifications (watch)
Run this to stop receiving real-time email notifications
"""

import logging
from app.services.gmail_service import GmailService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def stop_gmail_watch():
    """Stop Gmail watch to disable push notifications"""
    try:
        gmail_service = GmailService()
        
        # Stop the watch
        result = gmail_service.service.users().stop(userId='me').execute()
        
        logger.info("✅ Gmail watch stopped successfully!")
        logger.info("📧 You will no longer receive real-time email notifications")
        logger.info("🔄 To start again, run the watch setup script")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Error stopping watch: {e}")
        return None

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🛑 STOPPING GMAIL WATCH")
    print("="*60 + "\n")
    
    stop_gmail_watch()
    
    print("\n" + "="*60)
    print("✅ DONE - Gmail watch stopped")
    print("="*60 + "\n")






