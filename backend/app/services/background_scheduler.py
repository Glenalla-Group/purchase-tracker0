"""
Background scheduler service for periodic tasks.
"""

import logging
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import get_settings
from app.config.database import SessionLocal

logger = logging.getLogger(__name__)

# Global scheduler instance
_scheduler: Optional[AsyncIOScheduler] = None


def get_scheduler() -> Optional[AsyncIOScheduler]:
    """Get the global scheduler instance."""
    return _scheduler


def start_scheduler():
    """Start the background scheduler."""
    global _scheduler
    
    if _scheduler is not None:
        logger.warning("Scheduler is already running")
        return
    
    settings = get_settings()
    
    # Only start scheduler if retailer orders API is enabled
    if not settings.enable_retailer_orders_api:
        logger.info("Retailer Orders API is disabled - skipping scheduler startup")
        return
    
    _scheduler = AsyncIOScheduler()
    
    # Schedule periodic email processing job
    # Run every hour at minute 0 (e.g., 1:00, 2:00, 3:00, etc.)
    _scheduler.add_job(
        process_retailer_emails_periodic,
        trigger=CronTrigger(minute=0),  # Every hour at minute 0
        id='process_retailer_emails',
        name='Process Retailer Order Emails',
        replace_existing=True,
        max_instances=1,  # Only one instance can run at a time
        misfire_grace_time=300  # 5 minutes grace time if job is delayed
    )
    
    _scheduler.start()
    logger.info("✅ Background scheduler started")
    logger.info("   - Retailer email processing: Every hour (at :00 minutes)")
    logger.info("   - Processing 20 emails per run")


def stop_scheduler():
    """Stop the background scheduler."""
    global _scheduler
    
    if _scheduler is None:
        return
    
    _scheduler.shutdown(wait=True)
    _scheduler = None
    logger.info("Background scheduler stopped")


def process_retailer_emails_periodic():
    """
    Periodic background job to process retailer order confirmation emails.
    Runs every hour and processes up to 20 unprocessed emails.
    """
    try:
        logger.info("=" * 70)
        logger.info("🔄 [PERIODIC JOB] Starting retailer email processing...")
        logger.info("=" * 70)
        
        # Get database session using context manager pattern
        from app.config.database import SessionLocal
        db = SessionLocal()
        
        try:
            from app.services.retailer_order_processor import RetailerOrderProcessor
            
            processor = RetailerOrderProcessor(db)
            gmail_service = processor.gmail_service
            
            # Collect unprocessed message IDs from all retailers
            # Get more emails per retailer to have a good pool for sorting (get 50 per retailer)
            all_message_ids_with_retailer = []
            
            # List of retailers with implemented processors
            supported_retailers = [
                ('footlocker', processor.footlocker_parser),
                ('champs', processor.champs_parser),
                ('dicks', processor.dicks_parser),
                ('hibbett', processor.hibbett_parser),
                ('shoepalace', processor.shoepalace_parser),
                ('snipes', processor.snipes_parser),
                ('finishline', processor.finishline_parser),
                ('shopsimon', processor.shopsimon_parser),
                ('jdsports', processor.jdsports_parser),
                ('revolve', processor.revolve_parser),
                ('asos', processor.asos_parser),
                ('dtlr', processor.dtlr_parser),
                ('endclothing', processor.endclothing_parser),
                ('shopwss', processor.shopwss_parser),
                ('on', processor.on_parser),
                ('urban', processor.urban_parser),
                ('bloomingdales', processor.bloomingdales_parser),
                ('carbon38', processor.carbon38_parser),
                ('gazelle', processor.gazelle_parser),
                ('netaporter', processor.netaporter_parser),
                ('fit2run', processor.fit2run_parser),
            ]
            
            # Collect emails from each retailer
            for retailer_name, parser in supported_retailers:
                try:
                    # Build query based on retailer
                    if retailer_name == "footlocker":
                        from_email = parser.order_from_email
                        subject_query = parser.order_subject_query
                        query = f'from:{from_email} subject:"{subject_query}" -label:{processor.PROCESSED_LABEL}'
                    elif retailer_name == "champs":
                        # Use environment-aware email address and subject pattern
                        from_email = processor.champs_parser.order_from_email
                        subject_query = processor.champs_parser.order_subject_query
                        query = f'from:{from_email} subject:"{subject_query}" -label:{processor.PROCESSED_LABEL}'
                    elif retailer_name == "dicks":
                        # Use environment-aware email address and subject pattern
                        from_email = processor.dicks_parser.order_from_email
                        subject_query = processor.dicks_parser.order_subject_query
                        query = f'from:{from_email} subject:"{subject_query}" -label:{processor.PROCESSED_LABEL}'
                    elif retailer_name == "hibbett":
                        # Use environment-aware email address and subject pattern
                        from_email = processor.hibbett_parser.order_from_email
                        subject_query = processor.hibbett_parser.order_subject_query
                        query = f'from:{from_email} subject:"{subject_query}" -label:{processor.PROCESSED_LABEL}'
                    elif retailer_name == "shoepalace":
                        # Use environment-aware email address and subject pattern
                        # Add "shopifyemail" to distinguish from other retailers using "confirmed"
                        from_email = processor.shoepalace_parser.order_from_email
                        subject_query = processor.shoepalace_parser.order_subject_query
                        query = f'from:{from_email} subject:"{subject_query}" shopifyemail -label:{processor.PROCESSED_LABEL}'
                    elif retailer_name == "snipes":
                        # Use environment-aware email address and subject pattern
                        from_email = processor.snipes_parser.order_from_email
                        subject_query = processor.snipes_parser.order_subject_query
                        query = f'from:{from_email} subject:"{subject_query}" -label:{processor.PROCESSED_LABEL}'
                    elif retailer_name == "finishline":
                        # Use environment-aware email address and subject pattern
                        from_email = processor.finishline_parser.order_from_email
                        subject_query = processor.finishline_parser.order_subject_query
                        query = f'from:{from_email} subject:"{subject_query}" -label:{processor.PROCESSED_LABEL}'
                    elif retailer_name == "shopsimon":
                        from app.services.shopsimon_parser import ShopSimonEmailParser
                        query = f'from:{ShopSimonEmailParser.SHOPSIMON_FROM_EMAIL} subject:"{ShopSimonEmailParser.SUBJECT_ORDER_PATTERN}" -label:{processor.PROCESSED_LABEL}'
                    elif retailer_name == "jdsports":
                        # Use environment-aware email address and subject pattern
                        from_email = processor.jdsports_parser.order_from_email
                        subject_query = processor.jdsports_parser.order_subject_query
                        query = f'from:{from_email} subject:"{subject_query}" -label:{processor.PROCESSED_LABEL}'
                    elif retailer_name == "revolve":
                        # Use environment-aware email address and subject pattern
                        from_email = processor.revolve_parser.order_from_email
                        subject_query = processor.revolve_parser.order_subject_query
                        query = f'from:{from_email} subject:"{subject_query}" -label:{processor.PROCESSED_LABEL}'
                    elif retailer_name == "asos":
                        # Use environment-aware email address and subject pattern
                        from_email = processor.asos_parser.order_from_email
                        subject_query = processor.asos_parser.order_subject_query
                        query = f'from:{from_email} subject:"{subject_query}" -label:{processor.PROCESSED_LABEL}'
                    elif retailer_name == "dtlr":
                        # Use environment-aware email address and subject pattern
                        from_email = processor.dtlr_parser.order_from_email
                        subject_query = processor.dtlr_parser.order_subject_query
                        query = f'from:{from_email} subject:"{subject_query}" -label:{processor.PROCESSED_LABEL}'
                    elif retailer_name == "endclothing":
                        # Use environment-aware email address and subject pattern
                        from_email = processor.endclothing_parser.order_from_email
                        subject_query = processor.endclothing_parser.order_subject_query
                        query = f'from:{from_email} subject:"{subject_query}" -label:{processor.PROCESSED_LABEL}'
                    elif retailer_name == "shopwss":
                        # Use environment-aware email address and subject pattern
                        from_email = processor.shopwss_parser.order_from_email
                        subject_query = processor.shopwss_parser.order_subject_query
                        query = f'from:{from_email} subject:"{subject_query}" -label:{processor.PROCESSED_LABEL}'
                    elif retailer_name == "on":
                        # Use environment-aware email address and subject pattern
                        from_email = processor.on_parser.order_from_email
                        subject_query = processor.on_parser.order_subject_query
                        query = f'from:{from_email} subject:"{subject_query}" -label:{processor.PROCESSED_LABEL}'
                    elif retailer_name == "urban":
                        # Use environment-aware email address and subject pattern
                        from_email = processor.urban_parser.order_from_email
                        subject_query = processor.urban_parser.order_subject_query
                        query = f'from:{from_email} subject:"{subject_query}" -label:{processor.PROCESSED_LABEL}'
                    elif retailer_name == "bloomingdales":
                        # Use environment-aware email address and subject pattern
                        from_email = processor.bloomingdales_parser.order_from_email
                        subject_query = processor.bloomingdales_parser.order_subject_query
                        # For development, use a more flexible pattern without quotes
                        if processor.bloomingdales_parser.settings.is_development:
                            query = f'from:{from_email} subject:order -label:{processor.PROCESSED_LABEL}'
                        else:
                            query = f'from:{from_email} subject:"{subject_query}" -label:{processor.PROCESSED_LABEL}'
                    elif retailer_name == "carbon38":
                        # Use environment-aware email address and subject pattern
                        from_email = processor.carbon38_parser.order_from_email
                        subject_query = processor.carbon38_parser.order_subject_query
                        query = f'from:{from_email} subject:"{subject_query}" -label:{processor.PROCESSED_LABEL}'
                    elif retailer_name == "gazelle":
                        # Use environment-aware email address and subject pattern
                        from_email = processor.gazelle_parser.order_from_email
                        subject_query = processor.gazelle_parser.order_subject_query
                        query = f'from:{from_email} subject:"{subject_query}" -label:{processor.PROCESSED_LABEL}'
                    elif retailer_name == "netaporter":
                        # Use environment-aware email address and subject pattern
                        from_email = processor.netaporter_parser.order_from_email
                        subject_query = processor.netaporter_parser.order_subject_query
                        query = f'from:{from_email} subject:"{subject_query}" -label:{processor.PROCESSED_LABEL}'
                    elif retailer_name == "fit2run":
                        # Use environment-aware email address and subject pattern
                        from_email = processor.fit2run_parser.order_from_email
                        subject_query = processor.fit2run_parser.order_subject_query
                        query = f'from:{from_email} subject:"{subject_query}" -label:{processor.PROCESSED_LABEL}'
                    else:
                        continue
                    
                    # Get unprocessed emails from this retailer (get 50 to have a good pool)
                    message_ids = gmail_service.list_messages_with_query(
                        query=query,
                        max_results=50  # Get more to have a good pool for sorting
                    )
                    
                    # Add retailer name to each message ID
                    for msg_id in message_ids:
                        all_message_ids_with_retailer.append((msg_id, retailer_name))
                    
                    # Log at INFO level so users can see which retailers have emails
                    if len(message_ids) > 0:
                        logger.info(f"📧 Found {len(message_ids)} unprocessed {retailer_name} emails")
                    else:
                        logger.debug(f"No unprocessed {retailer_name} emails found")
                    
                except Exception as e:
                    logger.error(f"Error collecting {retailer_name} emails: {e}", exc_info=True)
                    continue
            
            if not all_message_ids_with_retailer:
                logger.info("No unprocessed emails found from any retailer")
                return
            
            # Get message metadata to sort by date
            messages_with_date = []
            for msg_id, retailer_name in all_message_ids_with_retailer:
                try:
                    # Get message with metadata format (lightweight, just headers)
                    message = gmail_service.get_message(msg_id, format='metadata')
                    if message:
                        internal_date = int(message.get('internalDate', 0))
                        messages_with_date.append((msg_id, retailer_name, internal_date))
                except Exception as e:
                    logger.warning(f"Error getting metadata for message {msg_id}: {e}")
                    # If we can't get date, use 0 (will be sorted last)
                    messages_with_date.append((msg_id, retailer_name, 0))
            
            # Sort by internalDate (newest first - higher timestamp = newer)
            messages_with_date.sort(key=lambda x: x[2], reverse=True)
            
            # Process only the top 20 emails
            max_emails = 20
            messages_to_process = messages_with_date[:max_emails]
            
            logger.info(f"Processing top {len(messages_to_process)} emails (sorted by date, newest first)")
            
            # Process each email
            processed_count = 0
            skipped_duplicate_count = 0
            error_count = 0
            retailer_stats = {}  # Track stats per retailer
            
            for msg_id, retailer_name, _ in messages_to_process:
                try:
                    # Initialize retailer stats if not exists
                    if retailer_name not in retailer_stats:
                        retailer_stats[retailer_name] = {'processed': 0, 'duplicates': 0, 'errors': 0}
                    
                    # Get full message
                    message = gmail_service.get_message(msg_id)
                    if not message:
                        logger.warning(f"Could not retrieve message {msg_id}")
                        error_count += 1
                        retailer_stats[retailer_name]['errors'] += 1
                        continue
                    
                    # Parse to EmailData
                    email_data = gmail_service.parse_message_to_email_data(message)
                    
                    # Process the email using the single email processor
                    result = processor.process_single_email(email_data, msg_id, retailer_name)
                    
                    # Track results
                    if result.get('success', False):
                        if result.get('duplicate', False):
                            skipped_duplicate_count += 1
                            retailer_stats[retailer_name]['duplicates'] += 1
                        else:
                            processed_count += 1
                            retailer_stats[retailer_name]['processed'] += 1
                    else:
                        error_count += 1
                        retailer_stats[retailer_name]['errors'] += 1
                        error_msg = result.get('error', 'Unknown error')
                        logger.warning(f"Error processing {retailer_name} email {msg_id}: {error_msg}")
                
                except Exception as e:
                    logger.error(f"Error processing {retailer_name} email {msg_id}: {e}", exc_info=True)
                    error_count += 1
                    if retailer_name in retailer_stats:
                        retailer_stats[retailer_name]['errors'] += 1
            
            logger.info("=" * 70)
            logger.info(f"✅ [PERIODIC JOB] Completed retailer email processing")
            logger.info(f"   Total Processed: {processed_count}")
            logger.info(f"   Total Skipped (duplicates): {skipped_duplicate_count}")
            logger.info(f"   Total Errors: {error_count}")
            
            # Show breakdown by retailer
            if retailer_stats:
                logger.info("   ")
                logger.info("   📊 Breakdown by Retailer:")
                for retailer, stats in sorted(retailer_stats.items()):
                    total = stats['processed'] + stats['duplicates'] + stats['errors']
                    logger.info(f"      {retailer.capitalize()}: {total} emails "
                               f"({stats['processed']} processed, "
                               f"{stats['duplicates']} duplicates, "
                               f"{stats['errors']} errors)")
            
            logger.info("=" * 70)
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in periodic retailer email processing job: {e}", exc_info=True)

