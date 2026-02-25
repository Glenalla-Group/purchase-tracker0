"""
Webhook endpoint for Gmail Pub/Sub notifications.
"""

import base64
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Query
from googleapiclient.errors import HttpError

from app.models.email import PubSubNotification
from app.services.email_parser import EmailParser
from app.services.gmail_service import GmailService
from app.services.footlocker_parser import FootlockerEmailParser
from app.services.champs_parser import ChampsEmailParser
from app.services.hibbett_parser import HibbettEmailParser
from app.services.dicks_parser import DicksEmailParser
from app.services.dtlr_parser import DTLREmailParser
from app.services.finishline_parser import FinishLineEmailParser
from app.services.jdsports_parser import JDSportsEmailParser
from app.services.urban_parser import UrbanOutfittersEmailParser
from app.services.bloomingdales_parser import BloomingdalesEmailParser
from app.services.anthropologie_parser import AnthropologieEmailParser
from app.services.nike_parser import NikeEmailParser
from app.services.carbon38_parser import Carbon38EmailParser
from app.services.gazelle_parser import GazelleEmailParser
from app.services.netaporter_parser import NetAPorterEmailParser
from app.services.fit2run_parser import Fit2RunEmailParser
from app.services.sns_parser import SNSEmailParser
from app.services.adidas_parser import AdidasEmailParser
from app.services.concepts_parser import ConceptsEmailParser
from app.services.sneaker_parser import SneakerPoliticsEmailParser
from app.services.orleans_parser import OrleansEmailParser
from app.services.snipes_parser import SnipesEmailParser
from app.services.shoepalace_parser import ShoepalaceEmailParser
from app.services.endclothing_parser import ENDClothingEmailParser
from app.services.shopwss_parser import ShopWSSEmailParser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1")

# File path for persisting Gmail history ID (to process only new email arrivals)
_GMAIL_HISTORY_ID_FILE = "gmail_history_id"


def _get_history_id_path() -> Path:
    """Return path to the history ID storage file."""
    from app.config import get_settings
    return get_settings().base_dir / f".{_GMAIL_HISTORY_ID_FILE}"


def _load_stored_history_id() -> Optional[str]:
    """Load the last stored history ID from file. Returns None if file doesn't exist."""
    path = _get_history_id_path()
    try:
        if path.exists():
            return path.read_text().strip() or None
    except OSError as e:
        logger.warning(f"Could not read history ID file: {e}")
    return None


def _save_history_id(history_id: str) -> None:
    """Save history ID to file for next webhook invocation."""
    path = _get_history_id_path()
    try:
        path.write_text(str(history_id))
    except OSError as e:
        logger.warning(f"Could not write history ID file: {e}")


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
        # RETAILER EMAILS: Unified (retailer, email_type) classification
        # Uses RetailerEmailClassifier for detection, registry for routing
        # ============================================================
        from app.services.retailer_email_classifier import (
            RetailerEmailClassifier,
            ClassificationResult,
            EmailType,
        )
        from app.services.retailer_order_processor import RetailerOrderProcessor
        from app.services.retailer_order_update_processor import RetailerOrderUpdateProcessor
        
        classifier = RetailerEmailClassifier()
        classification = classifier.classify(email_data)
        
        if classification:
            db = next(get_db())
            try:
                if classification.email_type == EmailType.SHIPPING:
                    logger.info(f"📦 Detected {classification.display_name} shipping notification email")
                    update_processor = RetailerOrderUpdateProcessor(db)
                    result = update_processor.process_single_shipping_email(
                        email_data=email_data,
                        message_id=message_id,
                        retailer_name=classification.retailer_id,
                    )
                    if result.get('success'):
                        logger.info(
                            f"✅ Processed {classification.display_name} shipping update: {result.get('order_number')} - "
                            f"Updated {result.get('items_count', 0)} items, Tracking: {result.get('tracking_number')}"
                        )
                    else:
                        logger.error(
                            f"❌ Failed to process {classification.display_name} shipping update: {result.get('error')}"
                        )
                
                elif classification.email_type == EmailType.CANCELLATION:
                    logger.info(f"❌ Detected {classification.display_name} cancellation notification email")
                    update_processor = RetailerOrderUpdateProcessor(db)
                    result = update_processor.process_single_cancellation_email(
                        email_data=email_data,
                        message_id=message_id,
                        retailer_name=classification.retailer_id,
                    )
                    if result.get('success'):
                        logger.info(
                            f"✅ Processed {classification.display_name} cancellation update: {result.get('order_number')} - "
                            f"Updated {result.get('items_count', 0)} items"
                        )
                    else:
                        logger.error(
                            f"❌ Failed to process {classification.display_name} cancellation update: {result.get('error')}"
                        )
                
                elif classification.email_type == EmailType.CONFIRMATION:
                    logger.info(f"🛒 Detected {classification.display_name} order confirmation email")
                    processor = RetailerOrderProcessor(db)
                    result = processor.process_single_email(
                        email_data=email_data,
                        message_id=message_id,
                        retailer_name=classification.retailer_id,
                    )
                    if result.get('success'):
                        logger.info(
                            f"✅ Processed {classification.display_name} order: {result.get('order_number')} - "
                            f"Created {result.get('items_count', 0)} purchase tracker records"
                        )
                    else:
                        logger.error(
                            f"❌ Failed to process {classification.display_name} order: {result.get('error')}"
                        )
            finally:
                db.close()
            
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
) -> Dict[str, Any]:
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
        # Get raw body first to check if it's empty
        raw_body = await request.body()
        
        # Log the incoming request for debugging
        logger.info(f"[WEBHOOK] Received request from {request.client.host if request.client else 'unknown'}")
        logger.debug(f"[WEBHOOK] Headers: {dict(request.headers)}")
        logger.debug(f"[WEBHOOK] Body length: {len(raw_body)} bytes")
        
        # Check if body is empty (ngrok interstitial page issue)
        if not raw_body or len(raw_body) == 0:
            logger.warning("[WEBHOOK] Received empty body - likely ngrok interstitial or health check")
            return {"status": "200", "message": "Empty body received"}
        
        # Parse the Pub/Sub message
        try:
            body = json.loads(raw_body)
        except json.JSONDecodeError as e:
            logger.error(f"[WEBHOOK] Invalid JSON body: {e}")
            logger.error(f"[WEBHOOK] Raw body (first 500 chars): {raw_body[:500]}")
            return {"status": "400", "message": "Invalid JSON"}
        
        # Validate and decode to get email information
        email_address = None
        history_id = None
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
            # If it's not a valid Pub/Sub notification, just acknowledge it
            logger.info("[WEBHOOK] Not a valid Pub/Sub notification, acknowledging anyway")
        
        # Check if auto-processing is enabled via settings
        from app.config import get_settings
        settings = get_settings()
        auto_process_enabled = settings.enable_auto_email_processing
        
        if not auto_process_enabled:
            # Just acknowledge, don't process
            return {"status": "200", "message": "Email logged but auto-processing disabled"}
        
        logger.info("[AUTO-PROCESS] Processing email...")
        
        # Initialize Gmail service
        gmail_service = GmailService()
        
        # Try history-based processing first (only new email arrivals, skip read/unread)
        all_message_ids: list[str] = []
        stored_history_id = _load_stored_history_id()
        
        if stored_history_id:
            try:
                new_message_ids, new_history_id = gmail_service.get_new_message_ids_from_history(
                    stored_history_id
                )
                _save_history_id(new_history_id)
                if not new_message_ids:
                    logger.debug("[AUTO-PROCESS] No new emails (was likely read/unread) - skipped")
                    return {"status": "200", "message": "No new emails, skipped"}
                # Filter to only emails matching our criteria (intersect with search)
                interested_ids = _get_interested_message_ids(gmail_service)
                all_message_ids = [mid for mid in new_message_ids if mid in interested_ids]
                logger.info(f"[AUTO-PROCESS] History: {len(new_message_ids)} new, {len(all_message_ids)} match our criteria")
            except HttpError as err:
                status = getattr(getattr(err, "resp", None), "status", None)
                if status == 404:
                    logger.warning("[AUTO-PROCESS] History expired (404) - resyncing, skipping this notification")
                    profile_hid = gmail_service.get_profile_history_id()
                    if profile_hid:
                        _save_history_id(profile_hid)
                    return {"status": "200", "message": "History expired, resynced"}
                raise
        
        # Fallback: no stored history (first run) or use search-based approach
        if not all_message_ids:
            all_message_ids = _get_interested_message_ids(gmail_service)
            if history_id and not stored_history_id:
                _save_history_id(history_id)
        
        if not all_message_ids:
            logger.debug("No new unprocessed emails found")
            return {"status": "200", "message": "No unprocessed emails"}
        
        logger.info(f"Found {len(all_message_ids)} unprocessed messages to process")
        
        for message_id in all_message_ids:
            background_tasks.add_task(process_email_notification, message_id, gmail_service)
        
        return {"status": "200", "message": "Notification received", "processed": len(all_message_ids)}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _get_interested_message_ids(gmail_service: GmailService) -> list[str]:
    """Get message IDs matching our processing criteria (search-based)."""
    from app.services.revolve_parser import RevolveEmailParser
    from app.services.asos_parser import ASOSEmailParser
    footlocker_parser = FootlockerEmailParser()
    champs_parser = ChampsEmailParser()
    snipes_parser = SnipesEmailParser()
    shoepalace_parser = ShoepalaceEmailParser()
    endclothing_parser = ENDClothingEmailParser()
    shopwss_parser = ShopWSSEmailParser()
    dicks_parser = DicksEmailParser()
    hibbett_parser = HibbettEmailParser()
    dtlr_parser = DTLREmailParser()
    finishline_parser = FinishLineEmailParser()
    jdsports_parser = JDSportsEmailParser()
    revolve_parser = RevolveEmailParser()
    asos_parser = ASOSEmailParser()
    
    search_queries = [
            # PrepWorx inbound processed emails
            {
                'query': "from:beta@prepworx.io subject:(Inbound has been processed) -label:PrepWorx/Processed -label:PrepWorx/Error",
                'exclude_label': None,
                'max_results': 1
            },
            # Retailer order confirmation emails
            # Exclude Retailer-Updates/Processed: shipping/cancel emails match "order" in subject but are handled elsewhere
            {
                'query': f"(from:{footlocker_parser.order_from_email} OR from:champs@em.champssports.com OR "
                         f"from:{snipes_parser.order_from_email} OR "
                         f"from:{shoepalace_parser.order_from_email} OR "
                         f"from:{endclothing_parser.order_from_email} OR "
                         f"from:{shopwss_parser.order_from_email} OR "
                         "from:dickssportinggoods@order.email.dickssportinggoods.com OR "
                         "from:hibbet@transact.hibbett.com OR "
                         "from:FinishLine@e.finishline.com OR "
                         "from:Shop-Simon@e.shopsimon.com OR from:anthropologie@st.anthropologie.com OR "
                         "from:nike@official.nike.com OR from:orders@asos.com) subject:(order OR confirmation) "
                         "-label:Retailer-Orders/Processed -label:Retailer-Orders/Error -label:Retailer-Updates/Processed",
                'exclude_label': None,
                'max_results': 1
            },
            # Footlocker shipping notification emails
            {
                'query': (
                    f'from:{footlocker_parser.update_from_email} '
                    f'{footlocker_parser.shipping_subject_query} '
                    f'-label:Retailer-Updates/Processed -label:Retailer-Updates/Error'
                ),
                'exclude_label': None,
                'max_results': 1
            },
            # Champs shipping notification emails
            {
                'query': (
                    f'from:{champs_parser.update_from_email} '
                    f'{champs_parser.shipping_subject_query} '
                    f'-label:Retailer-Updates/Processed -label:Retailer-Updates/Error'
                ),
                'exclude_label': None,
                'max_results': 1
            },
            # Dick's shipping notification emails
            {
                'query': (
                    f'from:{dicks_parser.shipping_from_email} '
                    f'{dicks_parser.shipping_subject_query} '
                    f'-label:Retailer-Updates/Processed -label:Retailer-Updates/Error'
                ),
                'exclude_label': None,
                'max_results': 1
            },
            # Hibbett shipping notification emails
            {
                'query': (
                    f'from:{hibbett_parser.update_from_email} '
                    f'{hibbett_parser.shipping_subject_query} '
                    f'-label:Retailer-Updates/Processed -label:Retailer-Updates/Error'
                ),
                'exclude_label': None,
                'max_results': 1
            },
            # DTLR shipping notification emails
            {
                'query': (
                    f'from:{dtlr_parser.update_from_email} '
                    f'{dtlr_parser.shipping_subject_query} '
                    f'-label:Retailer-Updates/Processed -label:Retailer-Updates/Error'
                ),
                'exclude_label': None,
                'max_results': 1
            },
            # Finish Line shipping/update notification emails (incl. partial ship+cancel)
            {
                'query': (
                    f'from:{finishline_parser.update_from_email} '
                    f'{finishline_parser.shipping_subject_query} '
                    f'-label:Retailer-Updates/Processed -label:Retailer-Updates/Error'
                ),
                'exclude_label': None,
                'max_results': 1
            },
            # JD Sports shipping/update notification emails (same template as Finish Line)
            {
                'query': (
                    f'from:{jdsports_parser.update_from_email} '
                    f'{jdsports_parser.shipping_subject_query} '
                    f'-label:Retailer-Updates/Processed -label:Retailer-Updates/Error'
                ),
                'exclude_label': None,
                'max_results': 1
            },
            # Revolve shipping notification emails (full and partial)
            {
                'query': (
                    f'from:{revolve_parser.update_from_email} '
                    f'{revolve_parser.shipping_subject_query} '
                    f'-label:Retailer-Updates/Processed -label:Retailer-Updates/Error'
                ),
                'exclude_label': None,
                'max_results': 1
            },
            # ASOS shipping notification emails (Your order's on its way!)
            {
                'query': (
                    f'from:{asos_parser.update_from_email} '
                    f'{asos_parser.shipping_subject_query} '
                    f'-label:Retailer-Updates/Processed -label:Retailer-Updates/Error'
                ),
                'exclude_label': None,
                'max_results': 1
            },
            # Snipes shipping notification emails (Get Hyped! Your Order Has Shipped)
            {
                'query': (
                    f'from:{snipes_parser.update_from_email} '
                    f'{snipes_parser.shipping_subject_query} '
                    f'-label:Retailer-Updates/Processed -label:Retailer-Updates/Error'
                ),
                'exclude_label': None,
                'max_results': 1
            },
            # Shoe Palace shipping notification emails (A shipment from order #SP... is on the way)
            {
                'query': (
                    f'from:{shoepalace_parser.update_from_email} '
                    f'{shoepalace_parser.shipping_subject_query} '
                    f'-label:Retailer-Updates/Processed -label:Retailer-Updates/Error'
                ),
                'exclude_label': None,
                'max_results': 1
            },
            # END Clothing shipping notification emails (Your END. order has shipped)
            {
                'query': (
                    f'from:{endclothing_parser.update_from_email} '
                    f'{endclothing_parser.shipping_subject_query} '
                    f'-label:Retailer-Updates/Processed -label:Retailer-Updates/Error'
                ),
                'exclude_label': None,
                'max_results': 1
            },
            # ShopWSS shipping notification emails (Order #xxx is about to ship! / partially shipped)
            {
                'query': (
                    f'from:{shopwss_parser.update_from_email} '
                    f'{shopwss_parser.shipping_subject_query} '
                    f'-label:Retailer-Updates/Processed -label:Retailer-Updates/Error'
                ),
                'exclude_label': None,
                'max_results': 1
            },
            # ShopWSS cancellation notification emails (Order X has been canceled)
            {
                'query': (
                    f'from:{shopwss_parser.update_from_email} '
                    f'{shopwss_parser.cancellation_subject_query} '
                    f'-label:Retailer-Updates/Processed -label:Retailer-Updates/Error'
                ),
                'exclude_label': None,
                'max_results': 1
            },
            # Snipes cancellation notification emails (Cancelation Update)
            {
                'query': (
                    f'from:{snipes_parser.update_from_email} '
                    f'{snipes_parser.cancellation_subject_query} '
                    f'-label:Retailer-Updates/Processed -label:Retailer-Updates/Error'
                ),
                'exclude_label': None,
                'max_results': 1
            },
            # Footlocker cancellation notification emails
            {
                'query': (
                    f'from:{footlocker_parser.update_from_email} '
                    f'{footlocker_parser.cancellation_subject_query} '
                    f'-label:Retailer-Updates/Processed -label:Retailer-Updates/Error'
                ),
                'exclude_label': None,
                'max_results': 1
            },
            # Champs cancellation notification emails
            {
                'query': (
                    f'from:{champs_parser.update_from_email} '
                    f'{champs_parser.cancellation_subject_query} '
                    f'-label:Retailer-Updates/Processed -label:Retailer-Updates/Error'
                ),
                'exclude_label': None,
                'max_results': 1
            },
            # Dick's cancellation notification emails
            {
                'query': (
                    f'from:{dicks_parser.cancellation_from_email} '
                    f'{dicks_parser.cancellation_subject_query} '
                    f'-label:Retailer-Updates/Processed -label:Retailer-Updates/Error'
                ),
                'exclude_label': None,
                'max_results': 1
            },
            # Hibbett cancellation notification emails
            {
                'query': (
                    f'from:{hibbett_parser.update_from_email} '
                    f'{hibbett_parser.cancellation_subject_query} '
                    f'-label:Retailer-Updates/Processed -label:Retailer-Updates/Error'
                ),
                'exclude_label': None,
                'max_results': 1
            },
            # DTLR cancellation notification emails
            {
                'query': (
                    f'from:{dtlr_parser.update_from_email} '
                    f'{dtlr_parser.cancellation_subject_query} '
                    f'-label:Retailer-Updates/Processed -label:Retailer-Updates/Error'
                ),
                'exclude_label': None,
                'max_results': 1
            },
            # Finish Line full cancellation notification emails
            {
                'query': (
                    f'from:{finishline_parser.update_from_email} '
                    f'{finishline_parser.cancellation_subject_query} '
                    f'-label:Retailer-Updates/Processed -label:Retailer-Updates/Error'
                ),
                'exclude_label': None,
                'max_results': 1
            },
            # JD Sports full cancellation notification emails
            {
                'query': (
                    f'from:{jdsports_parser.update_from_email} '
                    f'{jdsports_parser.cancellation_subject_query} '
                    f'-label:Retailer-Updates/Processed -label:Retailer-Updates/Error'
                ),
                'exclude_label': None,
                'max_results': 1
            },
            # Revolve cancellation notification emails (type 1 + type 2)
            {
                'query': (
                    f'{revolve_parser.cancellation_from_query} '
                    f'{revolve_parser.cancellation_subject_query} '
                    f'-label:Retailer-Updates/Processed -label:Retailer-Updates/Error'
                ),
                'exclude_label': None,
                'max_results': 1
            }
    ]

    # Deduplicate queries (in dev mode, Footlocker and Champs produce identical queries)
    seen_queries = set()
    unique_search_queries = []
    for search_config in search_queries:
        query_key = search_config['query'].strip()
        if query_key not in seen_queries:
            seen_queries.add(query_key)
            unique_search_queries.append(search_config)

    # Collect unprocessed message IDs from all search queries
    result = []
    seen = set()
    for search_config in unique_search_queries:
        message_ids = gmail_service.list_messages_with_query(
            query=search_config['query'],
            max_results=search_config['max_results'],
            exclude_label=search_config['exclude_label']
        )
        for mid in message_ids:
            if mid not in seen:
                seen.add(mid)
                result.append(mid)
    return result


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


@router.post("/gmail/process-footlocker-shipping")
async def process_footlocker_shipping_emails(
    max_emails: int = Query(20, description="Maximum number of emails to process", ge=1, le=100)
) -> Dict[str, Any]:
    """
    Manually process Footlocker shipping notification emails.
    
    This endpoint searches for Footlocker shipping emails that haven't been processed yet
    and updates the purchase tracker records with shipped quantities.
    
    Args:
        max_emails: Maximum number of emails to process (default: 20, max: 100)
    
    Returns:
        Processing results with counts and details
    """
    try:
        from app.services.retailer_order_update_processor import RetailerOrderUpdateProcessor
        from app.config.database import get_db
        
        logger.info("=" * 60)
        logger.info(f"📦 PROCESSING FOOTLOCKER SHIPPING EMAILS (max: {max_emails})")
        logger.info("=" * 60)
        
        # Process emails synchronously
        db = next(get_db())
        try:
            processor = RetailerOrderUpdateProcessor(db)
            results = processor.process_footlocker_shipping_emails(max_emails=max_emails)
            
            logger.info("=" * 60)
            logger.info(f"✅ COMPLETED: {results}")
            logger.info("=" * 60)
            
            return {
                "status": 200,
                "message": f"Processed {results['processed']} Footlocker shipping emails",
                "data": results
            }
        finally:
            db.close()
    
    except Exception as e:
        logger.error(f"Error processing Footlocker shipping emails: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/gmail/process-footlocker-cancellation")
async def process_footlocker_cancellation_emails(
    max_emails: int = Query(20, description="Maximum number of emails to process", ge=1, le=100)
) -> Dict[str, Any]:
    """
    Manually process Footlocker cancellation notification emails.
    
    This endpoint searches for Footlocker cancellation emails that haven't been processed yet
    and updates the purchase tracker records with cancelled quantities.
    
    Args:
        max_emails: Maximum number of emails to process (default: 20, max: 100)
    
    Returns:
        Processing results with counts and details
    """
    try:
        from app.services.retailer_order_update_processor import RetailerOrderUpdateProcessor
        from app.config.database import get_db
        
        logger.info("=" * 60)
        logger.info(f"❌ PROCESSING FOOTLOCKER CANCELLATION EMAILS (max: {max_emails})")
        logger.info("=" * 60)
        
        # Process emails synchronously
        db = next(get_db())
        try:
            processor = RetailerOrderUpdateProcessor(db)
            results = processor.process_footlocker_cancellation_emails(max_emails=max_emails)
            
            logger.info("=" * 60)
            logger.info(f"✅ COMPLETED: {results}")
            logger.info("=" * 60)
            
            return {
                "status": 200,
                "message": f"Processed {results['processed']} Footlocker cancellation emails",
                "data": results
            }
        finally:
            db.close()
    
    except Exception as e:
        logger.error(f"Error processing Footlocker cancellation emails: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/gmail/process-footlocker-updates")
async def process_footlocker_update_emails(
    max_emails: int = Query(20, description="Maximum number of emails to process", ge=1, le=100)
) -> Dict[str, Any]:
    """
    Manually process Footlocker order update emails (both shipping and cancellation).
    
    This endpoint searches for both shipping and cancellation emails from Footlocker
    that haven't been processed yet and updates the purchase tracker records accordingly.
    
    Args:
        max_emails: Maximum number of emails to process per type (default: 20, max: 100)
    
    Returns:
        Processing results with aggregated counts and details
    """
    try:
        from app.services.retailer_order_update_processor import RetailerOrderUpdateProcessor
        from app.config.database import get_db
        
        logger.info("=" * 60)
        logger.info(f"📦 PROCESSING FOOTLOCKER ORDER UPDATES (max: {max_emails} per type)")
        logger.info("=" * 60)
        
        # Process emails synchronously
        db = next(get_db())
        try:
            processor = RetailerOrderUpdateProcessor(db)
            
            # Process shipping emails
            logger.info("Processing shipping emails...")
            shipping_results = processor.process_footlocker_shipping_emails(max_emails=max_emails)
            
            # Process cancellation emails
            logger.info("Processing cancellation emails...")
            cancellation_results = processor.process_footlocker_cancellation_emails(max_emails=max_emails)
            
            # Aggregate results
            total_results = {
                'total_emails': shipping_results['total_emails'] + cancellation_results['total_emails'],
                'processed': shipping_results['processed'] + cancellation_results['processed'],
                'errors': shipping_results['errors'] + cancellation_results['errors'],
                'error_messages': shipping_results['error_messages'] + cancellation_results['error_messages'],
                'shipping': {
                    'total_emails': shipping_results['total_emails'],
                    'processed': shipping_results['processed'],
                    'errors': shipping_results['errors']
                },
                'cancellation': {
                    'total_emails': cancellation_results['total_emails'],
                    'processed': cancellation_results['processed'],
                    'errors': cancellation_results['errors']
                }
            }
            
            logger.info("=" * 60)
            logger.info(f"✅ COMPLETED: {total_results}")
            logger.info("=" * 60)
            
            return {
                "status": 200,
                "message": (
                    f"Processed {total_results['processed']} Footlocker update emails "
                    f"({total_results['shipping']['processed']} shipping, "
                    f"{total_results['cancellation']['processed']} cancellation)"
                ),
                "data": total_results
            }
        finally:
            db.close()
    
    except Exception as e:
        logger.error(f"Error processing Footlocker update emails: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/gmail/process-hibbett-updates")
async def process_hibbett_update_emails(
    max_emails: int = Query(20, description="Maximum number of emails to process", ge=1, le=100)
) -> Dict[str, Any]:
    """
    Manually process Hibbett order update emails (shipping and cancellation).
    Same pattern as Foot Locker.
    """
    try:
        from app.services.retailer_order_update_processor import RetailerOrderUpdateProcessor
        from app.config.database import get_db

        logger.info("=" * 60)
        logger.info(f"📦 PROCESSING HIBBETT ORDER UPDATES (max: {max_emails} per type)")
        logger.info("=" * 60)

        db = next(get_db())
        try:
            processor = RetailerOrderUpdateProcessor(db)
            shipping_results = processor.process_hibbett_shipping_emails(max_emails=max_emails)
            cancellation_results = processor.process_hibbett_cancellation_emails(max_emails=max_emails)
            total_results = {
                'total_emails': shipping_results['total_emails'] + cancellation_results['total_emails'],
                'processed': shipping_results['processed'] + cancellation_results['processed'],
                'errors': shipping_results['errors'] + cancellation_results['errors'],
                'error_messages': shipping_results['error_messages'] + cancellation_results['error_messages'],
                'shipping': {'total_emails': shipping_results['total_emails'], 'processed': shipping_results['processed'], 'errors': shipping_results['errors']},
                'cancellation': {'total_emails': cancellation_results['total_emails'], 'processed': cancellation_results['processed'], 'errors': cancellation_results['errors']}
            }
            logger.info("=" * 60)
            logger.info(f"✅ COMPLETED: {total_results}")
            logger.info("=" * 60)
            return {
                "status": 200,
                "message": f"Processed {total_results['processed']} Hibbett update emails ({total_results['shipping']['processed']} shipping, {total_results['cancellation']['processed']} cancellation)",
                "data": total_results
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error processing Hibbett update emails: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/gmail/process-finishline-updates")
async def process_finishline_update_emails(
    max_emails: int = Query(20, description="Maximum number of emails to process", ge=1, le=100)
) -> Dict[str, Any]:
    """
    Manually process Finish Line order update emails (shipping and full cancellation).
    Shipping emails may include partial ship+cancel in one email.
    """
    try:
        from app.services.retailer_order_update_processor import RetailerOrderUpdateProcessor
        from app.config.database import get_db

        logger.info("=" * 60)
        logger.info(f"📦 PROCESSING FINISH LINE ORDER UPDATES (max: {max_emails} per type)")
        logger.info("=" * 60)

        db = next(get_db())
        try:
            processor = RetailerOrderUpdateProcessor(db)
            shipping_results = processor.process_finishline_shipping_emails(max_emails=max_emails)
            cancellation_results = processor.process_finishline_cancellation_emails(max_emails=max_emails)
            total_results = {
                'total_emails': shipping_results['total_emails'] + cancellation_results['total_emails'],
                'processed': shipping_results['processed'] + cancellation_results['processed'],
                'errors': shipping_results['errors'] + cancellation_results['errors'],
                'error_messages': shipping_results['error_messages'] + cancellation_results['error_messages'],
                'shipping': {'total_emails': shipping_results['total_emails'], 'processed': shipping_results['processed'], 'errors': shipping_results['errors']},
                'cancellation': {'total_emails': cancellation_results['total_emails'], 'processed': cancellation_results['processed'], 'errors': cancellation_results['errors']}
            }
            return {
                "status": 200,
                "message": f"Processed {total_results['processed']} Finish Line update emails ({total_results['shipping']['processed']} shipping, {total_results['cancellation']['processed']} cancellation)",
                "data": total_results
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error processing Finish Line update emails: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/gmail/process-jdsports-updates")
async def process_jdsports_update_emails(
    max_emails: int = Query(20, description="Maximum number of emails to process", ge=1, le=100)
) -> Dict[str, Any]:
    """Manually process JD Sports order update emails (shipping and full cancellation). Same template as Finish Line."""
    try:
        from app.services.retailer_order_update_processor import RetailerOrderUpdateProcessor
        from app.config.database import get_db

        logger.info("=" * 60)
        logger.info(f"📦 PROCESSING JD SPORTS ORDER UPDATES (max: {max_emails} per type)")
        logger.info("=" * 60)

        db = next(get_db())
        try:
            processor = RetailerOrderUpdateProcessor(db)
            shipping_results = processor.process_jdsports_shipping_emails(max_emails=max_emails)
            cancellation_results = processor.process_jdsports_cancellation_emails(max_emails=max_emails)
            total_results = {
                'total_emails': shipping_results['total_emails'] + cancellation_results['total_emails'],
                'processed': shipping_results['processed'] + cancellation_results['processed'],
                'errors': shipping_results['errors'] + cancellation_results['errors'],
                'error_messages': shipping_results['error_messages'] + cancellation_results['error_messages'],
                'shipping': {'total_emails': shipping_results['total_emails'], 'processed': shipping_results['processed'], 'errors': shipping_results['errors']},
                'cancellation': {'total_emails': cancellation_results['total_emails'], 'processed': cancellation_results['processed'], 'errors': cancellation_results['errors']}
            }
            return {
                "status": 200,
                "message": f"Processed {total_results['processed']} JD Sports update emails ({total_results['shipping']['processed']} shipping, {total_results['cancellation']['processed']} cancellation)",
                "data": total_results
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error processing JD Sports update emails: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/gmail/process-shopwss-shipping")
async def process_shopwss_shipping_emails(
    max_emails: int = Query(20, description="Maximum number of emails to process", ge=1, le=100)
) -> Dict[str, Any]:
    """Manually process ShopWSS shipping notification emails (Order #xxx is about to ship! / partially shipped)."""
    try:
        from app.services.retailer_order_update_processor import RetailerOrderUpdateProcessor
        from app.config.database import get_db

        logger.info("=" * 60)
        logger.info(f"📦 PROCESSING SHOPWSS SHIPPING EMAILS (max: {max_emails})")
        logger.info("=" * 60)

        db = next(get_db())
        try:
            processor = RetailerOrderUpdateProcessor(db)
            results = processor.process_shopwss_shipping_emails(max_emails=max_emails)
            return {
                "status": 200,
                "message": f"Processed {results['processed']} ShopWSS shipping emails",
                "data": results
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error processing ShopWSS shipping emails: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/gmail/process-shopwss-cancellation")
async def process_shopwss_cancellation_emails(
    max_emails: int = Query(20, description="Maximum number of emails to process", ge=1, le=100)
) -> Dict[str, Any]:
    """Manually process ShopWSS full order cancellation emails (Order X has been canceled)."""
    try:
        from app.services.retailer_order_update_processor import RetailerOrderUpdateProcessor
        from app.config.database import get_db

        logger.info("=" * 60)
        logger.info(f"❌ PROCESSING SHOPWSS CANCELLATION EMAILS (max: {max_emails})")
        logger.info("=" * 60)

        db = next(get_db())
        try:
            processor = RetailerOrderUpdateProcessor(db)
            results = processor.process_shopwss_cancellation_emails(max_emails=max_emails)
            return {
                "status": 200,
                "message": f"Processed {results['processed']} ShopWSS cancellation emails",
                "data": results
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error processing ShopWSS cancellation emails: {e}", exc_info=True)
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
