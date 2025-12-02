"""
Webhook endpoint for Gmail Pub/Sub notifications.
"""

import base64
import json
import logging
from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Query

from app.models.email import PubSubNotification
from app.services.email_parser import EmailParser
from app.services.gmail_service import GmailService

logger = logging.getLogger(__name__)

router = APIRouter()


async def process_email_notification(message_id: str, gmail_service: GmailService = None) -> None:
    """
    Background task to process email notification.
    
    Args:
        message_id: Gmail message ID to process
        gmail_service: Optional pre-initialized Gmail service (to avoid re-initialization)
    """
    try:
        logger.info(f"Processing email notification for message {message_id}")
        
        # Initialize services (reuse if provided)
        if gmail_service is None:
            gmail_service = GmailService()
        email_parser = EmailParser()
        
        # Fetch the email
        message = gmail_service.get_message(message_id)
        if not message:
            logger.error(f"Failed to fetch message {message_id}")
            return
        
        # Parse message to EmailData
        email_data = gmail_service.parse_message_to_email_data(message)
        logger.info(f"Fetched email: {email_data.subject} from {email_data.sender}")
        
        # ============================================================
        # CHECK FOR PREPWORX "INBOUND PROCESSED" EMAILS
        # ============================================================
        from app.services.prepworx_parser import PrepWorxEmailParser, PrepWorxCheckinProcessor
        from app.config.database import get_db
        
        prepworx_parser = PrepWorxEmailParser()
        
        if prepworx_parser.can_parse(email_data):
            logger.info(f"📦 Detected PrepWorx 'Inbound processed' email")
            
            # Parse PrepWorx email
            shipment_data = prepworx_parser.parse_email(email_data)
            
            if shipment_data:
                logger.info(
                    f"✓ Extracted PrepWorx shipment: {shipment_data.shipment_number} "
                    f"with {len(shipment_data.items)} items"
                )
                
                # Store to checkin table
                db = next(get_db())
                try:
                    processor = PrepWorxCheckinProcessor(db, gmail_service)
                    result = processor.process_and_store(shipment_data, message_id)
                    
                    if result.get('success'):
                        logger.info(
                            f"✅ Stored PrepWorx checkin: Shipment {result['shipment_number']} - "
                            f"Stored {result['stored_count']}/{result['total_items']} items, "
                            f"Skipped {result['skipped_count']} duplicates"
                        )
                    else:
                        logger.error(
                            f"❌ Failed to store PrepWorx checkin: {result.get('error')}"
                        )
                finally:
                    db.close()
                
                # Skip general email parsing for PrepWorx emails
                return
            else:
                logger.warning("Failed to parse PrepWorx shipment data")
        
        # ============================================================
        # CHECK FOR RETAILER ORDER CONFIRMATION EMAILS
        # ============================================================
        from app.services.retailer_order_processor import RetailerOrderProcessor
        from app.services.footlocker_parser import FootlockerEmailParser
        from app.services.champs_parser import ChampsEmailParser
        from app.services.dicks_parser import DicksEmailParser
        from app.services.hibbett_parser import HibbettEmailParser
        from app.services.shoepalace_parser import ShoepalaceEmailParser
        from app.services.snipes_parser import SnipesEmailParser
        from app.services.finishline_parser import FinishLineEmailParser
        from app.services.shopsimon_parser import ShopSimonEmailParser
        
        # Initialize parsers
        retailer_parsers = {
            'Footlocker': FootlockerEmailParser(),
            'Champs': ChampsEmailParser(),
            "Dick's": DicksEmailParser(),
            'Hibbett': HibbettEmailParser(),
            'Shoe Palace': ShoepalaceEmailParser(),
            'Snipes': SnipesEmailParser(),
            'Finish Line': FinishLineEmailParser(),
            'Shop Simon': ShopSimonEmailParser()
        }
        
        # Check each retailer parser
        for retailer_name, parser in retailer_parsers.items():
            # Check if this email is from this retailer and is an order confirmation
            is_retailer_email = False
            
            # Each parser has different method names, check accordingly
            if hasattr(parser, 'is_footlocker_email') and parser.is_footlocker_email(email_data):
                is_retailer_email = parser.is_order_confirmation_email(email_data)
            elif hasattr(parser, 'is_champs_email') and parser.is_champs_email(email_data):
                is_retailer_email = parser.is_order_confirmation_email(email_data)
            elif hasattr(parser, 'is_dicks_email') and parser.is_dicks_email(email_data):
                is_retailer_email = parser.is_order_confirmation_email(email_data)
            elif hasattr(parser, 'is_hibbett_email') and parser.is_hibbett_email(email_data):
                is_retailer_email = parser.is_order_confirmation_email(email_data)
            elif hasattr(parser, 'is_shoepalace_email') and parser.is_shoepalace_email(email_data):
                is_retailer_email = parser.is_order_confirmation_email(email_data)
            elif hasattr(parser, 'is_snipes_email') and parser.is_snipes_email(email_data):
                is_retailer_email = parser.is_order_confirmation_email(email_data)
            elif hasattr(parser, 'is_finishline_email') and parser.is_finishline_email(email_data):
                is_retailer_email = parser.is_order_confirmation_email(email_data)
            elif hasattr(parser, 'is_shopsimon_email') and parser.is_shopsimon_email(email_data):
                is_retailer_email = parser.is_order_confirmation_email(email_data)
            
            if is_retailer_email:
                logger.info(f"🛒 Detected {retailer_name} order confirmation email")
                
                # Process this retailer order
                db = next(get_db())
                try:
                    processor = RetailerOrderProcessor(db)
                    
                    # Call the appropriate processing method
                    result = processor.process_single_email(
                        email_data=email_data,
                        message_id=message_id,
                        retailer_name=retailer_name.lower().replace(' ', '').replace("'", "")
                    )
                    
                    if result.get('success'):
                        logger.info(
                            f"✅ Processed {retailer_name} order: {result.get('order_number')} - "
                            f"Created {result.get('items_count', 0)} purchase tracker records"
                        )
                    else:
                        logger.error(
                            f"❌ Failed to process {retailer_name} order: {result.get('error')}"
                        )
                finally:
                    db.close()
                
                # Skip general email parsing for retailer orders
                return
        
        # ============================================================
        # GENERAL EMAIL PROCESSING (for non-PrepWorx emails)
        # ============================================================
        # Extract information using BeautifulSoup
        extracted_info = email_parser.parse_email(email_data)
        
        if extracted_info.extraction_successful:
            logger.info(
                f"✓ Extracted from email {message_id}: "
                f"Order#{extracted_info.order_number or 'N/A'} | "
                f"Amount:{extracted_info.total_amount or 'N/A'} | "
                f"Merchant:{extracted_info.merchant or 'N/A'}"
            )
            # For detailed data, use DEBUG level
            logger.debug(f"Full extracted data: {extracted_info.model_dump_json(indent=2)}")
            
            # TODO: Store extracted information in database
            # TODO: Trigger any additional processing (notifications, webhooks, etc.)
            
        else:
            logger.warning(
                f"Failed to extract information from email {message_id}: "
                f"{extracted_info.error_message}"
            )
    
    except Exception as e:
        logger.error(f"Error processing email notification {message_id}: {e}", exc_info=True)


@router.post("/gmail/webhook")
async def gmail_webhook(
    request: Request,
    background_tasks: BackgroundTasks
) -> Dict[str, str]:
    """
    Webhook endpoint for Gmail Pub/Sub notifications.
    
    This endpoint receives push notifications from Google Cloud Pub/Sub
    when new emails arrive in the monitored Gmail inbox.
    
    NOTE: WEBHOOK_SECRET is currently not enforced. For production,
    consider adding Pub/Sub message signature verification.
    See PUBSUB_SETUP.md for security enhancements.
    
    Args:
        request: FastAPI request object
        background_tasks: FastAPI background tasks
    
    Returns:
        Success response
    """
    try:
        # Parse the Pub/Sub message first to get email info
        body = await request.json()
        
        # Validate and decode to get email information
        try:
            notification = PubSubNotification(**body)
            decoded_data = base64.b64decode(notification.message.data).decode('utf-8')
            data = json.loads(decoded_data)
            
            email_address = data.get('emailAddress')
            history_id = data.get('historyId')
            
            # ALWAYS log the email notification (minimal logging)
            logger.info(f"[EMAIL] New notification from {email_address} | History: {history_id}")
            
        except Exception as e:
            logger.warning(f"Could not decode notification data: {e}")
        
        # Check if auto-processing is enabled via environment variable
        import os
        auto_process_enabled = os.getenv('ENABLE_AUTO_EMAIL_PROCESSING', 'false').lower() == 'true'
        
        if not auto_process_enabled:
            # Just acknowledge, don't process
            return {"status": 200, "message": "Email logged but auto-processing disabled", "data": {}}
        
        logger.info("[AUTO-PROCESS] Processing email...")
        
        # Initialize Gmail service
        gmail_service = GmailService()
        
        # Build search queries for all supported email types
        search_queries = [
            # PrepWorx inbound processed emails
            {
                'query': "from:beta@prepworx.io subject:(Inbound has been processed)",
                'exclude_label': "PrepWorx/Processed",
                'max_results': 5
            },
            # Retailer order confirmation emails
            {
                'query': "(from:accountservices@em.footlocker.com OR from:champs@em.champssports.com OR "
                         "from:dickssportinggoods@order.email.dickssportinggoods.com OR "
                         "from:hibbet@transact.hibbett.com OR from:orders@shoepalace.com OR "
                         "from:noreply@snipesusa.com OR from:FinishLine@e.finishline.com OR "
                         "from:Shop-Simon@e.shopsimon.com) subject:(order OR confirmation)",
                'exclude_label': "Retailer-Orders/Processed",
                'max_results': 10
            }
        ]
        
        # Collect all unprocessed message IDs from all search queries
        all_message_ids = []
        for search_config in search_queries:
            unprocessed_threads = gmail_service.list_messages_with_query(
                query=search_config['query'],
                max_results=search_config['max_results'],
                exclude_label=search_config['exclude_label']
            )
            
            # Extract individual messages from threads
            for thread_id in unprocessed_threads:
                try:
                    # Get the thread to access all messages within it
                    thread = gmail_service.service.users().threads().get(
                        userId='me',
                        id=thread_id
                    ).execute()
                    
                    # Extract message IDs from the thread
                    thread_messages = thread.get('messages', [])
                    for msg in thread_messages:
                        all_message_ids.append(msg['id'])
                except Exception as e:
                    logger.error(f"Error getting thread {thread_id}: {e}")
                    # Fall back to treating it as a message ID
                    all_message_ids.append(thread_id)
        
        if not all_message_ids:
            logger.info("No new unprocessed emails found")
            return {"status": 200, "message": "No unprocessed emails", "data": {}}
        
        logger.info(f"Found {len(all_message_ids)} unprocessed messages to process")
        
        # Process each new message in the background (reuse gmail_service)
        for message_id in all_message_ids:
            background_tasks.add_task(process_email_notification, message_id, gmail_service)
        
        return {"status": 200, "message": "Notification received", "data": {}}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/gmail/process-prepworx")
async def process_prepworx_emails(
    background_tasks: BackgroundTasks,
    max_emails: int = Query(20, description="Maximum number of emails to process", ge=1, le=100)
) -> Dict[str, Any]:
    """
    Manually process unprocessed PrepWorx "Inbound processed" emails.
    
    This endpoint searches for PrepWorx emails that haven't been processed yet
    (without the "PrepWorx/Processed" label) and processes them automatically.
    
    Args:
        max_emails: Maximum number of emails to process (default: 20, max: 100)
    
    Returns:
        Processing results with counts and details
    """
    try:
        logger.info("=" * 60)
        logger.info(f"📦 PROCESSING PREPWORX EMAILS (max: {max_emails})")
        logger.info("=" * 60)
        
        logger.info("⚡ Starting background email search and processing...")
        
        # Define background task to search and process emails
        def search_and_process_emails():
            """Background task that searches for and processes emails"""
            try:
                gmail_service = GmailService()
                
                # Search for unprocessed PrepWorx emails
                search_query = "from:beta@prepworx.io subject:(Inbound has been processed)"
                message_ids = gmail_service.list_messages_with_query(
                    query=search_query,
                    max_results=max_emails,
                    exclude_label="PrepWorx/Processed"
                )
                
                logger.info(f"Found {len(message_ids)} unprocessed PrepWorx messages")
                
                if not message_ids:
                    logger.info("No unprocessed PrepWorx emails found in background search")
                    return
                
                logger.info(f"Processing {len(message_ids)} emails in background...")
                
                # Process each message
                for message_id in message_ids:
                    # Call the processing function directly (not as background task)
                    import asyncio
                    asyncio.run(process_email_notification(message_id, gmail_service))
                
                logger.info(f"✅ Completed background processing of {len(message_ids)} emails")
            except Exception as e:
                logger.error(f"Error in background search and process: {e}", exc_info=True)
        
        # Queue the entire search + processing as ONE background task
        background_tasks.add_task(search_and_process_emails)
        
        logger.info("✓ Background task queued successfully")
        logger.info("  Processing will continue in the background. Check server logs for status.")
        
        return {
            "status": 200,  # ResultStatus.SUCCESS for frontend
            "message": f"Started searching and processing PrepWorx emails in the background (max: {max_emails})",
            "data": {
                "processing_count": max_emails  # Estimated, actual count determined in background
            }
        }
    
    except Exception as e:
        logger.error(f"Error processing PrepWorx emails: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/gmail/test")
async def test_email_processing() -> Dict[str, Any]:
    """
    Test endpoint to manually trigger email processing.
    
    This endpoint fetches the latest emails and processes them synchronously,
    useful for testing without waiting for Pub/Sub notifications.
    
    Returns:
        Status and processed message IDs with extraction results
    """
    try:
        logger.info("=" * 60)
        logger.info("🔍 STARTING EMAIL PROCESSING TEST")
        logger.info("=" * 60)
        
        gmail_service = GmailService()
        email_parser = EmailParser()
        
        # Import PrepWorx parser
        from app.services.prepworx_parser import PrepWorxEmailParser, PrepWorxCheckinProcessor
        from app.config.database import get_db
        prepworx_parser = PrepWorxEmailParser()
        
        # Fetch latest messages
        message_ids = gmail_service.list_messages(max_results=5)
        
        if not message_ids:
            logger.info("No messages found")
            logger.info("=" * 60)
            return {
                "status": 200,
                "message": "No messages found",
                "data": {
                    "processed_count": 0
                }
            }
        
        logger.info(f"Found {len(message_ids)} messages to process")
        logger.info("")
        
        # Process each message synchronously
        results = []
        for idx, message_id in enumerate(message_ids, 1):
            try:
                logger.info(f"[{idx}/{len(message_ids)}] Processing message {message_id}")
                
                # Fetch email
                message = gmail_service.get_message(message_id)
                if not message:
                    logger.error(f"  ❌ Failed to fetch message")
                    results.append({"message_id": message_id, "status": "failed", "error": "Could not fetch"})
                    continue
                
                # Parse message
                email_data = gmail_service.parse_message_to_email_data(message)
                logger.info(f"  Subject: {email_data.subject[:50]}...")
                logger.info(f"  From: {email_data.sender}")
                
                # Check if it's a PrepWorx email
                if prepworx_parser.can_parse(email_data):
                    logger.info(f"  📦 PrepWorx 'Inbound processed' email detected")
                    
                    # Parse PrepWorx email
                    shipment_data = prepworx_parser.parse_email(email_data)
                    
                    if shipment_data:
                        logger.info(
                            f"  ✓ Shipment: {shipment_data.shipment_number} | "
                            f"Items: {len(shipment_data.items)}"
                        )
                        
                        # Store to checkin table
                        db = next(get_db())
                        try:
                            processor = PrepWorxCheckinProcessor(db, gmail_service)
                            result = processor.process_and_store(shipment_data, message_id)
                            
                            if result.get('success'):
                                logger.info(
                                    f"  ✅ Stored to checkin: {result['stored_count']}/{result['total_items']} items"
                                )
                                results.append({
                                    "message_id": message_id,
                                    "status": "prepworx_success",
                                    "type": "prepworx_checkin",
                                    "subject": email_data.subject,
                                    "shipment_number": result['shipment_number'],
                                    "order_number": result['order_number'],
                                    "stored_count": result['stored_count'],
                                    "skipped_count": result['skipped_count'],
                                    "total_items": result['total_items']
                                })
                            else:
                                logger.error(f"  ❌ Failed to store: {result.get('error')}")
                                results.append({
                                    "message_id": message_id,
                                    "status": "prepworx_failed",
                                    "type": "prepworx_checkin",
                                    "error": result.get('error')
                                })
                        finally:
                            db.close()
                    else:
                        logger.warning(f"  ⚠️ Failed to parse PrepWorx shipment data")
                        results.append({
                            "message_id": message_id,
                            "status": "prepworx_parse_failed",
                            "error": "Could not parse PrepWorx shipment data"
                        })
                else:
                    # Extract information using general parser
                    extracted_info = email_parser.parse_email(email_data)
                    
                    if extracted_info.extraction_successful:
                        logger.info(
                            f"  ✓ Order#{extracted_info.order_number or 'N/A'} | "
                            f"${extracted_info.total_amount or 'N/A'} | "
                            f"{extracted_info.merchant or 'N/A'}"
                        )
                        results.append({
                            "message_id": message_id,
                            "status": "success",
                            "type": "general",
                            "subject": email_data.subject,
                            "order_number": extracted_info.order_number,
                            "amount": extracted_info.total_amount,
                            "merchant": extracted_info.merchant
                        })
                    else:
                        logger.warning(f"  ⚠️ Extraction failed: {extracted_info.error_message}")
                        results.append({
                            "message_id": message_id,
                            "status": "extraction_failed",
                            "error": extracted_info.error_message
                        })
                
                logger.info("")  # Blank line between emails
                
            except Exception as e:
                logger.error(f"  ❌ Error: {e}")
                results.append({"message_id": message_id, "status": "error", "error": str(e)})
        
        logger.info("=" * 60)
        logger.info(f"✅ COMPLETED: Processed {len(message_ids)} emails")
        logger.info("=" * 60)
        
        return {
            "status": 200,
            "message": f"Processed {len(message_ids)} messages",
            "data": {
                "processed_count": len(message_ids),
                "results": results
            }
        }
    
    except Exception as e:
        logger.error(f"Error in test endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
