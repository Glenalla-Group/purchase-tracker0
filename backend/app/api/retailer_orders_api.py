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
    1. Loop through all supported retailers (Footlocker, Champs, Dick's, etc.)
    2. For each retailer, search for unprocessed order confirmation emails
    3. Extract order details and create purchase tracker records
    4. Label processed emails
    5. Return aggregated statistics
    
    Args:
        max_emails: Maximum number of emails to process per retailer (default: 20)
        db: Database session
    
    Returns:
        ProcessingResult with aggregated statistics from all retailers
    """
    try:
        logger.info(f"API request: Process all retailer orders (max: {max_emails} per retailer)")
        
        processor = RetailerOrderProcessor(db)
        
        # Aggregate results from all retailers
        total_results = {
            'total_emails': 0,
            'processed': 0,
            'skipped_duplicate': 0,
            'errors': 0,
            'error_messages': []
        }
        
        # List of retailers with implemented processors
        supported_retailers = ['footlocker', 'champs', 'dicks', 'hibbett', 'shoepalace', 'snipes', 'finishline', 'shopsimon']
        
        for retailer in supported_retailers:
            try:
                logger.info(f"Processing {retailer} orders...")
                
                if retailer == "footlocker":
                    result = processor.process_footlocker_emails(max_emails=max_emails)
                elif retailer == "champs":
                    result = processor.process_champs_emails(max_emails=max_emails)
                elif retailer == "dicks":
                    result = processor.process_dicks_emails(max_emails=max_emails)
                elif retailer == "hibbett":
                    result = processor.process_hibbett_emails(max_emails=max_emails)
                elif retailer == "shoepalace":
                    result = processor.process_shoepalace_emails(max_emails=max_emails)
                elif retailer == "snipes":
                    result = processor.process_snipes_emails(max_emails=max_emails)
                elif retailer == "finishline":
                    result = processor.process_finishline_emails(max_emails=max_emails)
                elif retailer == "shopsimon":
                    result = processor.process_shopsimon_emails(max_emails=max_emails)
                else:
                    continue
                
                # Aggregate results
                total_results['total_emails'] += result['total_emails']
                total_results['processed'] += result['processed']
                total_results['skipped_duplicate'] += result['skipped_duplicate']
                total_results['errors'] += result['errors']
                total_results['error_messages'].extend(result['error_messages'])
                
                logger.info(f"Completed {retailer}: processed={result['processed']}, errors={result['errors']}")
                
            except Exception as e:
                logger.error(f"Error processing {retailer}: {e}", exc_info=True)
                total_results['errors'] += 1
                total_results['error_messages'].append(f"Error processing {retailer}: {str(e)}")
        
        logger.info(f"Total results across all retailers: {total_results}")
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

