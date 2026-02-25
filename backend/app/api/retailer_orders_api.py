"""
Retailer Orders API Endpoints
FastAPI routes for processing retailer order confirmation emails
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
import logging

from app.config.database import get_db
from app.services.retailer_order_processor import RetailerOrderProcessor

router = APIRouter(prefix="/api/v1/retailer-orders", tags=["Retailer Orders"])
logger = logging.getLogger(__name__)


# ========================
# Response Models
# ========================

class ProcessingResult(BaseModel):
    """Result of email processing"""
    total_emails: int
    processed: int
    skipped_duplicate: int
    errors: int
    error_messages: list[str] = []


# ========================
# Endpoints
# ========================

@router.post("/process-all", response_model=ProcessingResult)
def process_all_retailer_orders(
    max_emails: int = 20,
    db: Session = Depends(get_db)
):
    """
    Process order confirmation emails from ALL supported retailers.
    
    This endpoint will:
    1. Collect unprocessed emails from all retailers
    2. Sort them by date (newest first)
    3. Process only the latest max_emails (default: 20) emails total across all retailers
    4. Extract order details and create purchase tracker records
    5. Label processed emails
    6. Return aggregated statistics
    
    Args:
        max_emails: Maximum number of emails to process TOTAL across all retailers (default: 20)
        db: Database session
    
    Returns:
        ProcessingResult with aggregated statistics from all retailers
    """
    try:
        logger.info(f"API request: Process all retailer orders (max: {max_emails} total emails)")
        
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
                
                logger.debug(f"Found {len(message_ids)} unprocessed {retailer_name} emails (collecting for sorting)")
                
            except Exception as e:
                logger.error(f"Error collecting {retailer_name} emails: {e}", exc_info=True)
                continue
        
        if not all_message_ids_with_retailer:
            logger.info("No unprocessed emails found from any retailer")
            return ProcessingResult(
                total_emails=0,
                processed=0,
                skipped_duplicate=0,
                errors=0,
                error_messages=[]
            )
        
        # Get message metadata to sort by date
        # Gmail API returns messages sorted by date, but we need to merge across retailers
        # Get metadata for all messages to sort by internalDate
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
        
        # Take only the top max_emails
        messages_to_process = messages_with_date[:max_emails]
        
        logger.info(f"Processing top {len(messages_to_process)} emails (sorted by date, newest first)")
        
        # Aggregate results
        total_results = {
            'total_emails': len(messages_to_process),
            'processed': 0,
            'skipped_duplicate': 0,
            'errors': 0,
            'error_messages': []
        }
        
        # Process each email
        for msg_id, retailer_name, _ in messages_to_process:
            try:
                # Get full message
                message = gmail_service.get_message(msg_id)
                if not message:
                    logger.warning(f"Could not retrieve message {msg_id}")
                    total_results['errors'] += 1
                    total_results['error_messages'].append(f"Could not retrieve message {msg_id}")
                    continue
                
                # Parse to EmailData
                email_data = gmail_service.parse_message_to_email_data(message)
                
                # Process the email using the single email processor
                result = processor.process_single_email(email_data, msg_id, retailer_name)
                
                # Aggregate results
                if result.get('success', False):
                    if result.get('duplicate', False):
                        total_results['skipped_duplicate'] += 1
                    else:
                        total_results['processed'] += 1
                else:
                    total_results['errors'] += 1
                    error_msg = result.get('error', 'Unknown error')
                    total_results['error_messages'].append(f"{retailer_name}: {error_msg}")
                
            except Exception as e:
                logger.error(f"Error processing {retailer_name} email {msg_id}: {e}", exc_info=True)
                total_results['errors'] += 1
                total_results['error_messages'].append(f"Error processing {retailer_name} email {msg_id}: {str(e)}")
        
        logger.info(f"Total results: {total_results}")
        return ProcessingResult(**total_results)
    
    except Exception as e:
        logger.error(f"Error processing all retailer orders: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process retailer orders: {str(e)}"
        )


@router.get("/processing-stats")
def get_processing_stats():
    """
    Get statistics about processed retailer order emails.
    
    Returns:
        Statistics about labeled emails
    """
    try:
        from app.services.gmail_service import GmailService
        
        gmail_service = GmailService()
        
        # Get label stats
        processed_label = gmail_service.get_or_create_label(RetailerOrderProcessor.PROCESSED_LABEL)
        error_label = gmail_service.get_or_create_label(RetailerOrderProcessor.ERROR_LABEL)
        
        # Count emails with each label
        processed_count = 0
        error_count = 0
        
        if processed_label:
            query = f'label:{processed_label["name"]}'
            processed_count = len(gmail_service.list_messages_with_query(query, max_results=500))
        
        if error_label:
            query = f'label:{error_label["name"]}'
            error_count = len(gmail_service.list_messages_with_query(query, max_results=500))
        
        return {
            'processed_emails': processed_count,
            'error_emails': error_count,
            'processed_label': processed_label['name'] if processed_label else None,
            'error_label': error_label['name'] if error_label else None
        }
    
    except Exception as e:
        logger.error(f"Error getting processing stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get processing stats: {str(e)}"
        )


@router.post("/process/footlocker", response_model=ProcessingResult)
def process_footlocker_orders(
    max_emails: int = 20,
    db: Session = Depends(get_db)
):
    """
    Process Footlocker order confirmation emails.
    
    Args:
        max_emails: Maximum number of emails to process (default: 20)
        db: Database session
    
    Returns:
        ProcessingResult with processing statistics
    """
    try:
        logger.info(f"API request: Process Footlocker orders (max: {max_emails})")
        
        processor = RetailerOrderProcessor(db)
        result = processor.process_footlocker_emails(max_emails=max_emails)
        
        return ProcessingResult(**result)
    
    except Exception as e:
        logger.error(f"Error processing Footlocker orders: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process Footlocker orders: {str(e)}"
        )


@router.post("/process/champs", response_model=ProcessingResult)
def process_champs_orders(
    max_emails: int = 20,
    db: Session = Depends(get_db)
):
    """
    Process Champs Sports order confirmation emails.
    
    Args:
        max_emails: Maximum number of emails to process (default: 20)
        db: Database session
    
    Returns:
        ProcessingResult with processing statistics
    """
    try:
        logger.info(f"API request: Process Champs Sports orders (max: {max_emails})")
        
        processor = RetailerOrderProcessor(db)
        result = processor.process_champs_emails(max_emails=max_emails)
        
        return ProcessingResult(**result)
    
    except Exception as e:
        logger.error(f"Error processing Champs Sports orders: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process Champs Sports orders: {str(e)}"
        )


@router.post("/process/dicks", response_model=ProcessingResult)
def process_dicks_orders(
    max_emails: int = 20,
    db: Session = Depends(get_db)
):
    """
    Process Dick's Sporting Goods order confirmation emails.
    
    Args:
        max_emails: Maximum number of emails to process (default: 20)
        db: Database session
    
    Returns:
        ProcessingResult with processing statistics
    """
    try:
        logger.info(f"API request: Process Dick's Sporting Goods orders (max: {max_emails})")
        
        processor = RetailerOrderProcessor(db)
        result = processor.process_dicks_emails(max_emails=max_emails)
        
        return ProcessingResult(**result)
    
    except Exception as e:
        logger.error(f"Error processing Dick's Sporting Goods orders: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process Dick's Sporting Goods orders: {str(e)}"
        )


@router.post("/process/hibbett", response_model=ProcessingResult)
def process_hibbett_orders(
    max_emails: int = 20,
    db: Session = Depends(get_db)
):
    """
    Process Hibbett order confirmation emails.
    
    Args:
        max_emails: Maximum number of emails to process (default: 20)
        db: Database session
    
    Returns:
        ProcessingResult with processing statistics
    """
    try:
        logger.info(f"API request: Process Hibbett orders (max: {max_emails})")
        
        processor = RetailerOrderProcessor(db)
        result = processor.process_hibbett_emails(max_emails=max_emails)
        
        return ProcessingResult(**result)
    
    except Exception as e:
        logger.error(f"Error processing Hibbett orders: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process Hibbett orders: {str(e)}"
        )


@router.post("/process/shoepalace", response_model=ProcessingResult)
def process_shoepalace_orders(
    max_emails: int = 20,
    db: Session = Depends(get_db)
):
    """
    Process Shoe Palace order confirmation emails.
    
    Args:
        max_emails: Maximum number of emails to process (default: 20)
        db: Database session
    
    Returns:
        ProcessingResult with processing statistics
    """
    try:
        logger.info(f"API request: Process Shoe Palace orders (max: {max_emails})")
        
        processor = RetailerOrderProcessor(db)
        result = processor.process_shoepalace_emails(max_emails=max_emails)
        
        return ProcessingResult(**result)
    
    except Exception as e:
        logger.error(f"Error processing Shoe Palace orders: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process Shoe Palace orders: {str(e)}"
        )


@router.post("/process/snipes")
async def process_snipes_orders(
    max_emails: int = 20,
    db: Session = Depends(get_db)
) -> ProcessingResult:
    """
    Process Snipes order confirmation emails and create purchase tracker records.
    
    Args:
        max_emails: Maximum number of emails to process (default: 20)
        db: Database session
    
    Returns:
        ProcessingResult with summary of processing results
    """
    try:
        logger.info(f"API request: Process Snipes orders (max: {max_emails})")
        
        processor = RetailerOrderProcessor(db)
        result = processor.process_snipes_emails(max_emails=max_emails)
        
        return ProcessingResult(**result)
    
    except Exception as e:
        logger.error(f"Error processing Snipes orders: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process Snipes orders: {str(e)}"
        )


@router.post("/process/finishline")
async def process_finishline_orders(
    max_emails: int = 20,
    db: Session = Depends(get_db)
) -> ProcessingResult:
    """
    Process Finish Line order confirmation emails and create purchase tracker records.
    
    Args:
        max_emails: Maximum number of emails to process (default: 20)
        db: Database session
    
    Returns:
        ProcessingResult with summary of processing results
    """
    try:
        logger.info(f"API request: Process Finish Line orders (max: {max_emails})")
        
        processor = RetailerOrderProcessor(db)
        result = processor.process_finishline_emails(max_emails=max_emails)
        
        return ProcessingResult(**result)
    
    except Exception as e:
        logger.error(f"Error processing Finish Line orders: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process Finish Line orders: {str(e)}"
        )


@router.post("/process/shopsimon")
async def process_shopsimon_orders(
    max_emails: int = 20,
    db: Session = Depends(get_db)
) -> ProcessingResult:
    """
    Process ShopSimon order confirmation emails and create purchase tracker records.
    
    Args:
        max_emails: Maximum number of emails to process (default: 20)
        db: Database session
    
    Returns:
        ProcessingResult with summary of processing results
    """
    try:
        logger.info(f"API request: Process ShopSimon orders (max: {max_emails})")
        
        processor = RetailerOrderProcessor(db)
        result = processor.process_shopsimon_emails(max_emails=max_emails)
        
        return ProcessingResult(**result)
    
    except Exception as e:
        logger.error(f"Error processing ShopSimon orders: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process ShopSimon orders: {str(e)}"
        )

