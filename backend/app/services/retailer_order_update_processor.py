"""
Retailer Order Update Processor Service
Processes order update emails (shipping and cancellation) from retailers
"""

import logging
import re
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.services.gmail_service import GmailService
from app.services.footlocker_parser import (
    FootlockerEmailParser, 
    FootlockerShippingData, 
    FootlockerCancellationData,
    FootlockerOrderItem
)
from app.services.champs_parser import (
    ChampsEmailParser,
    ChampsShippingData,
    ChampsCancellationData,
    ChampsOrderItem
)
from app.services.hibbett_parser import (
    HibbettEmailParser,
    HibbettShippingData,
    HibbettCancellationData,
    HibbettOrderItem
)
from app.services.dicks_parser import (
    DicksEmailParser,
    DicksShippingData,
    DicksShippingOrderItem,
    DicksCancellationData,
    DicksCancellationOrderItem
)
from app.services.dtlr_parser import (
    DTLREmailParser,
    DTLRShippingData,
    DTLRShippingOrderItem,
    DTLRCancellationData,
    DTLRCancellationOrderItem
)
from app.services.urban_parser import (
    UrbanOutfittersEmailParser,
    UrbanOutfittersCancellationData,
    UrbanOutfittersShippingData,
    UrbanOrderItem as UrbanOutfittersOrderItem
)
from app.services.shoepalace_parser import (
    ShoepalaceEmailParser,
    ShoepalaceShippingData,
    ShoepalaceCancellationData,
    ShoepalaceOrderItem
)
from app.services.endclothing_parser import (
    ENDClothingEmailParser,
    ENDClothingShippingData,
    ENDClothingOrderItem
)
from app.services.shopwss_parser import (
    ShopWSSEmailParser,
    ShopWSSShippingData,
    ShopWSSShippingOrderItem,
    ShopWSSCancellationData,
)
from app.services.orleans_parser import (
    OrleansEmailParser,
    OrleansCancellationData,
    OrleansOrderItem
)
from app.services.finishline_parser import (
    FinishLineEmailParser,
    FinishLineCancellationData,
    FinishLineOrderItem,
    FinishLineShippingData,
    FinishLineShippingOrderItem
)
from app.services.jdsports_parser import JDSportsEmailParser
from app.services.revolve_parser import (
    RevolveEmailParser,
    RevolveShippingData,
    RevolveCancellationData,
)
from app.services.asos_parser import (
    ASOSEmailParser,
    ASOSShippingData,
)
from app.services.snipes_parser import (
    SnipesEmailParser,
    SnipesShippingData,
    SnipesCancellationData,
)
from app.services.als_parser import (
    AlsEmailParser,
    AlsShippingData,
    AlsCancellationData,
    AlsOrderItem
)
from app.services.fwrd_parser import FwrdEmailParser
from app.services.academy_parser import AcademyEmailParser, AcademyShippingData
from app.services.scheels_parser import SceelsEmailParser, SceelsShippingData
from app.models.database import AsinBank, EmailManualReview, OASourcing, PurchaseTracker
from app.models.email import EmailData
from app.utils.purchase_status import calculate_status_and_location

logger = logging.getLogger(__name__)


class RetailerOrderUpdateProcessor:
    """Service for processing retailer order update emails (shipping/cancellation)"""
    
    # Gmail labels - separate by email type
    SHIPPING_PROCESSED_LABEL = "Retailer-Shipping/Processed"
    SHIPPING_ERROR_LABEL = "Retailer-Shipping/Error"
    SHIPPING_MANUAL_REVIEW_LABEL = "Retailer-Shipping/Manual-Review"
    CANCEL_PROCESSED_LABEL = "Retailer-Cancel/Processed"
    CANCEL_ERROR_LABEL = "Retailer-Cancel/Error"
    CANCEL_MANUAL_REVIEW_LABEL = "Retailer-Cancel/Manual-Review"
    # Legacy labels kept for backward-compatible duplicate detection
    PROCESSED_LABEL = "Retailer-Updates/Processed"
    ERROR_LABEL = "Retailer-Updates/Error"
    
    def __init__(self, db_session: Session):
        """
        Initialize the processor.
        
        Args:
            db_session: SQLAlchemy database session
        """
        self.db = db_session
        self.gmail_service = GmailService()
        self.footlocker_parser = FootlockerEmailParser()
        self.champs_parser = ChampsEmailParser()
        self.hibbett_parser = HibbettEmailParser()
        self.dicks_parser = DicksEmailParser()
        self.dtlr_parser = DTLREmailParser()
        self.urban_parser = UrbanOutfittersEmailParser()
        self.shoepalace_parser = ShoepalaceEmailParser()
        self.orleans_parser = OrleansEmailParser()
        self.finishline_parser = FinishLineEmailParser()
        self.jdsports_parser = JDSportsEmailParser()
        self.revolve_parser = RevolveEmailParser()
        self.asos_parser = ASOSEmailParser()
        self.snipes_parser = SnipesEmailParser()
        self.endclothing_parser = ENDClothingEmailParser()
        self.shopwss_parser = ShopWSSEmailParser()
        self.als_parser = AlsEmailParser()
        self.fwrd_parser = FwrdEmailParser()
        self.academy_parser = AcademyEmailParser()
        self.scheels_parser = SceelsEmailParser()

        # Ensure type-specific labels exist
        self.shipping_processed_label = self.gmail_service.get_or_create_label(self.SHIPPING_PROCESSED_LABEL)
        self.shipping_error_label = self.gmail_service.get_or_create_label(self.SHIPPING_ERROR_LABEL)
        self.shipping_manual_review_label = self.gmail_service.get_or_create_label(self.SHIPPING_MANUAL_REVIEW_LABEL)
        self.cancel_processed_label = self.gmail_service.get_or_create_label(self.CANCEL_PROCESSED_LABEL)
        self.cancel_error_label = self.gmail_service.get_or_create_label(self.CANCEL_ERROR_LABEL)
        self.cancel_manual_review_label = self.gmail_service.get_or_create_label(self.CANCEL_MANUAL_REVIEW_LABEL)
        # Legacy labels for backward-compatible duplicate detection
        self.processed_label = self.gmail_service.get_or_create_label(self.PROCESSED_LABEL)
        self.error_label = self.gmail_service.get_or_create_label(self.ERROR_LABEL)
    
    def process_footlocker_shipping_emails(self, max_emails: int = 20) -> dict:
        """
        Process Footlocker shipping notification emails.
        
        Args:
            max_emails: Maximum number of emails to process
        
        Returns:
            Dictionary with processing results
        """
        logger.info(f"Starting Footlocker shipping email processing (max {max_emails} emails)")
        
        results = {
            'total_emails': 0,
            'processed': 0,
            'errors': 0,
            'error_messages': []
        }
        
        try:
            # Search for Footlocker and Kids Foot Locker shipping emails
            query = (
                f'{{from:{FootlockerEmailParser.FOOTLOCKER_UPDATE_FROM_EMAIL} '
                f'from:{FootlockerEmailParser.KIDS_FOOTLOCKER_UPDATE_FROM_EMAIL}}} '
                f'subject:"{FootlockerEmailParser.SUBJECT_SHIPPING_PATTERN}" '
                f'-label:{self.SHIPPING_PROCESSED_LABEL} -label:{self.SHIPPING_ERROR_LABEL} -label:{self.SHIPPING_MANUAL_REVIEW_LABEL}'
            )
            
            message_ids = self.gmail_service.list_messages_with_query(
                query=query,
                max_results=max_emails
            )
            
            results['total_emails'] = len(message_ids)
            logger.info(f"Found {len(message_ids)} unprocessed Footlocker shipping emails")
            
            for message_id in message_ids:
                try:
                    # Get full message
                    message = self.gmail_service.get_message(message_id)
                    if not message:
                        logger.warning(f"Could not retrieve message {message_id}")
                        continue
                    
                    # Parse to EmailData
                    email_data = self.gmail_service.parse_message_to_email_data(message)
                    
                    # Verify it's a Footlocker email
                    if not self.footlocker_parser.is_footlocker_email(email_data):
                        logger.warning(f"Email {message_id} is not from Footlocker")
                        continue
                    
                    if not self.footlocker_parser.is_shipping_email(email_data):
                        logger.warning(f"Email {message_id} is not a shipping notification")
                        continue
                    
                    # Parse shipping details
                    shipping_data = self.footlocker_parser.parse_shipping_email(email_data)
                    if not shipping_data:
                        error_msg = f"Failed to parse shipping data from email {message_id}"
                        logger.error(error_msg)
                        results['errors'] += 1
                        results['error_messages'].append(error_msg)
                        self._add_error_label(message_id, 'shipping')
                        continue
                    
                    # Process the shipping update
                    success, error_msg = self._process_shipping_update(shipping_data)
                    
                    if success:
                        logger.info(f"Successfully processed shipping update for order {shipping_data.order_number}")
                        results['processed'] += 1
                        self._add_processed_label(message_id, 'shipping')
                    else:
                        logger.error(f"Failed to process shipping update for order {shipping_data.order_number}: {error_msg}")
                        results['errors'] += 1
                        results['error_messages'].append(error_msg)
                        self._add_error_label(message_id, 'shipping')
                
                except Exception as e:
                    error_msg = f"Error processing message {message_id}: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    results['errors'] += 1
                    results['error_messages'].append(error_msg)
                    self._add_error_label(message_id, 'shipping')
        
        except Exception as e:
            error_msg = f"Fatal error in Footlocker shipping email processing: {str(e)}"
            logger.error(error_msg, exc_info=True)
            results['error_messages'].append(error_msg)
        
        logger.info(f"Footlocker shipping processing complete: {results}")
        return results
    
    def process_shopwss_shipping_emails(self, max_emails: int = 20) -> dict:
        """Process ShopWSS shipping notification emails (Order #xxx is about to ship! / partially shipped)."""
        logger.info(f"Starting ShopWSS shipping email processing (max {max_emails} emails)")
        results = {'total_emails': 0, 'processed': 0, 'errors': 0, 'error_messages': []}
        try:
            query = (
                f'{self.shopwss_parser.cancellation_from_query} '
                f'{self.shopwss_parser.shipping_subject_query} '
                f'-label:{self.SHIPPING_PROCESSED_LABEL} -label:{self.SHIPPING_ERROR_LABEL} -label:{self.SHIPPING_MANUAL_REVIEW_LABEL}'
            )
            message_ids = self.gmail_service.list_messages_with_query(query=query, max_results=max_emails)
            results['total_emails'] = len(message_ids)
            logger.info(f"Found {len(message_ids)} unprocessed ShopWSS shipping emails")
            for message_id in message_ids:
                try:
                    if self._is_email_processed(message_id, 'shipping'):
                        continue
                    message = self.gmail_service.get_message(message_id)
                    if not message:
                        continue
                    email_data = self.gmail_service.parse_message_to_email_data(message)
                    if not self.shopwss_parser.is_shopwss_email(email_data):
                        continue
                    if not self.shopwss_parser.is_shipping_email(email_data):
                        continue
                    shipping_data = self.shopwss_parser.parse_shipping_email(email_data)
                    if not shipping_data:
                        results['errors'] += 1
                        results['error_messages'].append('Failed to parse ShopWSS shipping data')
                        self._add_error_label(message_id, 'shipping')
                        continue
                    success, error_msg = self._process_shopwss_shipping_update(shipping_data)
                    if success:
                        results['processed'] += 1
                        self._add_processed_label(message_id, 'shipping')
                    else:
                        results['errors'] += 1
                        results['error_messages'].append(error_msg or 'Unknown error')
                        self._add_error_label(message_id, 'shipping')
                except Exception as e:
                    results['errors'] += 1
                    results['error_messages'].append(str(e))
                    self._add_error_label(message_id, 'shipping')
        except Exception as e:
            error_msg = f"Fatal error in ShopWSS shipping email processing: {str(e)}"
            logger.error(error_msg, exc_info=True)
            results['error_messages'].append(error_msg)
        logger.info(f"ShopWSS shipping processing complete: {results}")
        return results
    
    def process_shopwss_cancellation_emails(self, max_emails: int = 20) -> dict:
        """Process ShopWSS full order cancellation emails (Order X has been canceled)."""
        logger.info(f"Starting ShopWSS cancellation email processing (max {max_emails} emails)")
        results = {'total_emails': 0, 'processed': 0, 'errors': 0, 'error_messages': []}
        try:
            query = (
                f'{self.shopwss_parser.cancellation_from_query} '
                f'{self.shopwss_parser.cancellation_subject_query} '
                f'-label:{self.CANCEL_PROCESSED_LABEL} -label:{self.CANCEL_ERROR_LABEL} -label:{self.CANCEL_MANUAL_REVIEW_LABEL}'
            )
            message_ids = self.gmail_service.list_messages_with_query(query=query, max_results=max_emails)
            results['total_emails'] = len(message_ids)
            logger.info(f"Found {len(message_ids)} unprocessed ShopWSS cancellation emails")
            for message_id in message_ids:
                try:
                    if self._is_email_processed(message_id, 'cancellation'):
                        continue
                    message = self.gmail_service.get_message(message_id)
                    if not message:
                        continue
                    email_data = self.gmail_service.parse_message_to_email_data(message)
                    if not self.shopwss_parser.is_shopwss_email(email_data):
                        continue
                    if not self.shopwss_parser.is_cancellation_email(email_data):
                        continue
                    cancellation_data = self.shopwss_parser.parse_cancellation_email(email_data)
                    if not cancellation_data:
                        partial = self.shopwss_parser.parse_cancellation_email_partial(email_data)
                        if partial:
                            try:
                                existing = self.db.query(EmailManualReview).filter(
                                    EmailManualReview.gmail_message_id == message_id
                                ).first()
                                if not existing:
                                    entry = EmailManualReview(
                                        gmail_message_id=message_id,
                                        retailer='shopwss',
                                        email_type='cancellation',
                                        subject=partial.get('subject', '') or email_data.subject,
                                        extracted_order_number=partial.get('order_number'),
                                        extracted_items=partial.get('items', []),
                                        missing_fields=','.join(partial.get('missing_fields', [])),
                                        error_reason='ShopWSS partial cancellation: unique_id not in email - needs manual entry',
                                        status='pending',
                                    )
                                    self.db.add(entry)
                                    self.db.commit()
                                    logger.info(
                                        f"Queued ShopWSS partial cancellation for manual review: message_id={message_id}"
                                    )
                            except Exception as e:
                                logger.warning(f"Failed to enqueue ShopWSS partial cancellation: {e}")
                                self.db.rollback()
                            self._add_manual_review_label(message_id, 'cancellation')
                        else:
                            results['errors'] += 1
                            results['error_messages'].append('Failed to parse ShopWSS cancellation data')
                            self._add_error_label(message_id, 'cancellation')
                        continue
                    success, error_msg = self._process_shopwss_cancellation_update(cancellation_data)
                    if success:
                        results['processed'] += 1
                        self._add_processed_label(message_id, 'cancellation')
                    else:
                        results['errors'] += 1
                        results['error_messages'].append(error_msg or 'Unknown error')
                        self._add_error_label(message_id, 'cancellation')
                except Exception as e:
                    results['errors'] += 1
                    results['error_messages'].append(str(e))
                    self._add_error_label(message_id, 'cancellation')
        except Exception as e:
            error_msg = f"Fatal error in ShopWSS cancellation email processing: {str(e)}"
            logger.error(error_msg, exc_info=True)
            results['error_messages'].append(error_msg)
        logger.info(f"ShopWSS cancellation processing complete: {results}")
        return results
    
    def process_finishline_shipping_emails(self, max_emails: int = 20) -> dict:
        """
        Process Finish Line shipping/update emails (incl. partial ship+cancel).
        Skips 'Processing - This item will ship soon' blocks.
        """
        logger.info(f"Starting Finish Line shipping/update email processing (max {max_emails} emails)")
        results = {'total_emails': 0, 'processed': 0, 'errors': 0, 'error_messages': []}
        try:
            query = (
                f'from:{self.finishline_parser.update_from_email} '
                f'{self.finishline_parser.shipping_subject_query} '
                f'-label:{self.SHIPPING_PROCESSED_LABEL} -label:{self.SHIPPING_ERROR_LABEL} -label:{self.SHIPPING_MANUAL_REVIEW_LABEL}'
            )
            message_ids = self.gmail_service.list_messages_with_query(query=query, max_results=max_emails)
            results['total_emails'] = len(message_ids)
            logger.info(f"Found {len(message_ids)} unprocessed Finish Line shipping emails")
            for message_id in message_ids:
                try:
                    if self._is_email_processed(message_id, 'shipping'):
                        continue
                    message = self.gmail_service.get_message(message_id)
                    if not message:
                        continue
                    email_data = self.gmail_service.parse_message_to_email_data(message)
                    if not self.finishline_parser.is_shipping_email(email_data):
                        continue
                    shipping_data = self.finishline_parser.parse_shipping_email(email_data)
                    if not shipping_data:
                        results['errors'] += 1
                        self._add_error_label(message_id, 'shipping')
                        continue
                    success, error_msg = self._process_finishline_shipping_update(shipping_data)
                    if success:
                        results['processed'] += 1
                        self._add_processed_label(message_id, 'shipping')
                    else:
                        results['errors'] += 1
                        results['error_messages'].append(error_msg or 'Unknown error')
                        self._add_error_label(message_id, 'shipping')
                except Exception as e:
                    results['errors'] += 1
                    results['error_messages'].append(str(e))
                    self._add_error_label(message_id, 'shipping')
        except Exception as e:
            results['error_messages'].append(str(e))
        logger.info(f"Finish Line shipping processing complete: {results}")
        return results
    
    def process_finishline_cancellation_emails(self, max_emails: int = 20) -> dict:
        """Process Finish Line full cancellation emails."""
        logger.info(f"Starting Finish Line cancellation email processing (max {max_emails} emails)")
        results = {'total_emails': 0, 'processed': 0, 'errors': 0, 'error_messages': []}
        try:
            query = (
                f'from:{self.finishline_parser.update_from_email} '
                f'{self.finishline_parser.cancellation_subject_query} '
                f'-label:{self.CANCEL_PROCESSED_LABEL} -label:{self.CANCEL_ERROR_LABEL} -label:{self.CANCEL_MANUAL_REVIEW_LABEL}'
            )
            message_ids = self.gmail_service.list_messages_with_query(query=query, max_results=max_emails)
            results['total_emails'] = len(message_ids)
            for message_id in message_ids:
                try:
                    if self._is_email_processed(message_id, 'cancellation'):
                        continue
                    message = self.gmail_service.get_message(message_id)
                    if not message:
                        continue
                    email_data = self.gmail_service.parse_message_to_email_data(message)
                    if not self.finishline_parser.is_cancellation_email(email_data):
                        continue
                    cancellation_data = self.finishline_parser.parse_cancellation_email(email_data)
                    if not cancellation_data:
                        results['errors'] += 1
                        self._add_error_label(message_id, 'cancellation')
                        continue
                    success, error_msg = self._process_finishline_cancellation_update(cancellation_data)
                    if success:
                        results['processed'] += 1
                        self._add_processed_label(message_id, 'cancellation')
                    else:
                        results['errors'] += 1
                        results['error_messages'].append(error_msg or 'Unknown error')
                        self._add_error_label(message_id, 'cancellation')
                except Exception as e:
                    results['errors'] += 1
                    results['error_messages'].append(str(e))
                    self._add_error_label(message_id, 'cancellation')
        except Exception as e:
            results['error_messages'].append(str(e))
        logger.info(f"Finish Line cancellation processing complete: {results}")
        return results
    
    def process_jdsports_shipping_emails(self, max_emails: int = 20) -> dict:
        """Process JD Sports shipping/update emails (same template as Finish Line)."""
        logger.info(f"Starting JD Sports shipping/update email processing (max {max_emails} emails)")
        results = {'total_emails': 0, 'processed': 0, 'errors': 0, 'error_messages': []}
        try:
            query = (
                f'from:{self.jdsports_parser.update_from_email} '
                f'{self.jdsports_parser.shipping_subject_query} '
                f'-label:{self.SHIPPING_PROCESSED_LABEL} -label:{self.SHIPPING_ERROR_LABEL} -label:{self.SHIPPING_MANUAL_REVIEW_LABEL}'
            )
            message_ids = self.gmail_service.list_messages_with_query(query=query, max_results=max_emails)
            results['total_emails'] = len(message_ids)
            for message_id in message_ids:
                try:
                    if self._is_email_processed(message_id, 'shipping'):
                        continue
                    message = self.gmail_service.get_message(message_id)
                    if not message:
                        continue
                    email_data = self.gmail_service.parse_message_to_email_data(message)
                    if not self.jdsports_parser.is_shipping_email(email_data):
                        continue
                    shipping_data = self.jdsports_parser.parse_shipping_email(email_data)
                    if not shipping_data:
                        results['errors'] += 1
                        self._add_error_label(message_id, 'shipping')
                        continue
                    success, error_msg = self._process_finishline_shipping_update(shipping_data)
                    if success:
                        results['processed'] += 1
                        self._add_processed_label(message_id, 'shipping')
                    else:
                        results['errors'] += 1
                        results['error_messages'].append(error_msg or 'Unknown error')
                        self._add_error_label(message_id, 'shipping')
                except Exception as e:
                    results['errors'] += 1
                    results['error_messages'].append(str(e))
                    self._add_error_label(message_id, 'shipping')
        except Exception as e:
            results['error_messages'].append(str(e))
        logger.info(f"JD Sports shipping processing complete: {results}")
        return results
    
    def process_jdsports_cancellation_emails(self, max_emails: int = 20) -> dict:
        """Process JD Sports full cancellation emails."""
        logger.info(f"Starting JD Sports cancellation email processing (max {max_emails} emails)")
        results = {'total_emails': 0, 'processed': 0, 'errors': 0, 'error_messages': []}
        try:
            query = (
                f'from:{self.jdsports_parser.update_from_email} '
                f'{self.jdsports_parser.cancellation_subject_query} '
                f'-label:{self.CANCEL_PROCESSED_LABEL} -label:{self.CANCEL_ERROR_LABEL} -label:{self.CANCEL_MANUAL_REVIEW_LABEL}'
            )
            message_ids = self.gmail_service.list_messages_with_query(query=query, max_results=max_emails)
            results['total_emails'] = len(message_ids)
            for message_id in message_ids:
                try:
                    if self._is_email_processed(message_id, 'cancellation'):
                        continue
                    message = self.gmail_service.get_message(message_id)
                    if not message:
                        continue
                    email_data = self.gmail_service.parse_message_to_email_data(message)
                    if not self.jdsports_parser.is_cancellation_email(email_data):
                        continue
                    cancellation_data = self.jdsports_parser.parse_cancellation_email(email_data)
                    if not cancellation_data:
                        results['errors'] += 1
                        self._add_error_label(message_id, 'cancellation')
                        continue
                    success, error_msg = self._process_finishline_cancellation_update(cancellation_data)
                    if success:
                        results['processed'] += 1
                        self._add_processed_label(message_id, 'cancellation')
                    else:
                        results['errors'] += 1
                        results['error_messages'].append(error_msg or 'Unknown error')
                        self._add_error_label(message_id, 'cancellation')
                except Exception as e:
                    results['errors'] += 1
                    results['error_messages'].append(str(e))
                    self._add_error_label(message_id, 'cancellation')
        except Exception as e:
            results['error_messages'].append(str(e))
        logger.info(f"JD Sports cancellation processing complete: {results}")
        return results
    
    def process_hibbett_shipping_emails(self, max_emails: int = 20) -> dict:
        """Process Hibbett shipping notification emails (same pattern as Foot Locker)."""
        logger.info(f"Starting Hibbett shipping email processing (max {max_emails} emails)")
        results = {'total_emails': 0, 'processed': 0, 'errors': 0, 'error_messages': []}
        try:
            query = (
                f'from:{self.hibbett_parser.update_from_email} '
                f'{self.hibbett_parser.shipping_subject_query} '
                f'-label:{self.SHIPPING_PROCESSED_LABEL} -label:{self.SHIPPING_ERROR_LABEL} -label:{self.SHIPPING_MANUAL_REVIEW_LABEL}'
            )
            message_ids = self.gmail_service.list_messages_with_query(query=query, max_results=max_emails)
            results['total_emails'] = len(message_ids)
            for message_id in message_ids:
                try:
                    if self._is_email_processed(message_id, 'shipping'):
                        continue
                    message = self.gmail_service.get_message(message_id)
                    if not message:
                        continue
                    email_data = self.gmail_service.parse_message_to_email_data(message)
                    if not self.hibbett_parser.is_shipping_email(email_data):
                        continue
                    shipping_data = self.hibbett_parser.parse_shipping_email(email_data)
                    if not shipping_data:
                        partial = self.hibbett_parser.parse_shipping_email_partial(email_data)
                        if partial:
                            try:
                                existing = self.db.query(EmailManualReview).filter(
                                    EmailManualReview.gmail_message_id == message_id
                                ).first()
                                if not existing:
                                    extracted_items = [
                                        {
                                            'product_name': it.get('product_name'),
                                            'product_number': it.get('product_number'),
                                            'color': it.get('color'),
                                            'quantity': it.get('quantity', 1),
                                        }
                                        for it in partial.get('items', [])
                                    ]
                                    entry = EmailManualReview(
                                        gmail_message_id=message_id,
                                        retailer='hibbett',
                                        email_type='shipping',
                                        subject=partial.get('subject', '') or email_data.subject,
                                        extracted_order_number=partial.get('order_number'),
                                        extracted_items=extracted_items,
                                        missing_fields=','.join(partial.get('missing_fields', ['unique_id', 'size'])),
                                        error_reason='Hibbett shipping: no unique_id/size in email - needs manual entry',
                                        status='pending',
                                    )
                                    self.db.add(entry)
                                    self.db.commit()
                                    logger.info(f"📋 Queued Hibbett shipping for manual review: message_id={message_id}")
                            except Exception as e:
                                logger.warning(f"Failed to enqueue Hibbett shipping for manual review: {e}")
                                self.db.rollback()
                            self._add_manual_review_label(message_id, 'shipping')
                        else:
                            self._add_error_label(message_id, 'shipping')
                        results['errors'] += 1
                        continue
                    success, error_msg = self._process_hibbett_shipping_update(shipping_data)
                    if success:
                        results['processed'] += 1
                        self._add_processed_label(message_id, 'shipping')
                    else:
                        try:
                            existing = self.db.query(EmailManualReview).filter(
                                EmailManualReview.gmail_message_id == message_id
                            ).first()
                            if not existing:
                                # Preserve unique_id/size - data is complete, failure was no matching records
                                extracted_items = [
                                    {
                                        'unique_id': it.unique_id,
                                        'size': it.size,
                                        'product_name': it.product_name,
                                        'product_number': it.product_number,
                                        'color': it.color,
                                        'quantity': it.quantity,
                                    }
                                    for it in shipping_data.items
                                ]
                                entry = EmailManualReview(
                                    gmail_message_id=message_id,
                                    retailer='hibbett',
                                    email_type='shipping',
                                    subject=email_data.subject or '',
                                    extracted_order_number=shipping_data.order_number,
                                    extracted_items=extracted_items,
                                    missing_fields='',  # Data complete - can resolve without feeding in
                                    error_reason=error_msg or 'No matching records - process order confirmation first, then resolve',
                                    status='pending',
                                )
                                self.db.add(entry)
                                self.db.commit()
                                logger.info(f"📋 Queued Hibbett shipping for manual review (no matches): message_id={message_id}")
                                self._add_manual_review_label(message_id, 'shipping')
                            else:
                                self._add_error_label(message_id, 'shipping')
                        except Exception as e:
                            logger.warning(f"Failed to enqueue Hibbett shipping for manual review: {e}")
                            self.db.rollback()
                            self._add_error_label(message_id, 'shipping')
                        results['errors'] += 1
                        results['error_messages'].append(error_msg or 'Unknown error')
                except Exception as e:
                    results['errors'] += 1
                    results['error_messages'].append(str(e))
                    self._add_error_label(message_id, 'shipping')
        except Exception as e:
            results['error_messages'].append(str(e))
        logger.info(f"Hibbett shipping processing complete: {results}")
        return results
    
    def process_hibbett_cancellation_emails(self, max_emails: int = 20) -> dict:
        """Process Hibbett cancellation notification emails (same pattern as Foot Locker)."""
        logger.info(f"Starting Hibbett cancellation email processing (max {max_emails} emails)")
        results = {'total_emails': 0, 'processed': 0, 'errors': 0, 'error_messages': []}
        try:
            query = (
                f'from:{self.hibbett_parser.update_from_email} '
                f'{self.hibbett_parser.cancellation_subject_query} '
                f'-label:{self.CANCEL_PROCESSED_LABEL} -label:{self.CANCEL_ERROR_LABEL} -label:{self.CANCEL_MANUAL_REVIEW_LABEL}'
            )
            message_ids = self.gmail_service.list_messages_with_query(query=query, max_results=max_emails)
            results['total_emails'] = len(message_ids)
            for message_id in message_ids:
                try:
                    if self._is_email_processed(message_id, 'cancellation'):
                        continue
                    message = self.gmail_service.get_message(message_id)
                    if not message:
                        continue
                    email_data = self.gmail_service.parse_message_to_email_data(message)
                    if not self.hibbett_parser.is_cancellation_email(email_data):
                        continue
                    cancellation_data = self.hibbett_parser.parse_cancellation_email(email_data)
                    if not cancellation_data:
                        results['errors'] += 1
                        self._add_error_label(message_id, 'cancellation')
                        continue
                    success, error_msg = self._process_hibbett_cancellation_update(cancellation_data)
                    if success:
                        results['processed'] += 1
                        self._add_processed_label(message_id, 'cancellation')
                    else:
                        results['errors'] += 1
                        results['error_messages'].append(error_msg or 'Unknown error')
                        self._add_error_label(message_id, 'cancellation')
                except Exception as e:
                    results['errors'] += 1
                    results['error_messages'].append(str(e))
                    self._add_error_label(message_id, 'cancellation')
        except Exception as e:
            results['error_messages'].append(str(e))
        logger.info(f"Hibbett cancellation processing complete: {results}")
        return results
    
    def process_footlocker_cancellation_emails(self, max_emails: int = 20) -> dict:
        """
        Process Footlocker cancellation notification emails.
        
        Args:
            max_emails: Maximum number of emails to process
        
        Returns:
            Dictionary with processing results
        """
        logger.info(f"Starting Footlocker cancellation email processing (max {max_emails} emails)")
        
        results = {
            'total_emails': 0,
            'processed': 0,
            'errors': 0,
            'error_messages': []
        }
        
        try:
            # Search for Footlocker and Kids Foot Locker cancellation emails
            query = (
                f'{{from:{FootlockerEmailParser.FOOTLOCKER_UPDATE_FROM_EMAIL} '
                f'from:{FootlockerEmailParser.KIDS_FOOTLOCKER_UPDATE_FROM_EMAIL}}} '
                f'subject:"{FootlockerEmailParser.SUBJECT_CANCELLATION_PATTERN}" '
                f'-label:{self.CANCEL_PROCESSED_LABEL} -label:{self.CANCEL_ERROR_LABEL} -label:{self.CANCEL_MANUAL_REVIEW_LABEL}'
            )
            
            message_ids = self.gmail_service.list_messages_with_query(
                query=query,
                max_results=max_emails
            )
            
            results['total_emails'] = len(message_ids)
            logger.info(f"Found {len(message_ids)} unprocessed Footlocker cancellation emails")
            
            for message_id in message_ids:
                try:
                    # Get full message
                    message = self.gmail_service.get_message(message_id)
                    if not message:
                        logger.warning(f"Could not retrieve message {message_id}")
                        continue
                    
                    # Parse to EmailData
                    email_data = self.gmail_service.parse_message_to_email_data(message)
                    
                    # Verify it's a Footlocker email
                    if not self.footlocker_parser.is_footlocker_email(email_data):
                        logger.warning(f"Email {message_id} is not from Footlocker")
                        continue
                    
                    if not self.footlocker_parser.is_cancellation_email(email_data):
                        logger.warning(f"Email {message_id} is not a cancellation notification")
                        continue
                    
                    # Parse cancellation details
                    cancellation_data = self.footlocker_parser.parse_cancellation_email(email_data)
                    if not cancellation_data:
                        error_msg = f"Failed to parse cancellation data from email {message_id}"
                        logger.error(error_msg)
                        results['errors'] += 1
                        results['error_messages'].append(error_msg)
                        self._add_error_label(message_id, 'cancellation')
                        continue
                    
                    # Process the cancellation update
                    success, error_msg = self._process_cancellation_update(cancellation_data)
                    
                    if success:
                        logger.info(f"Successfully processed cancellation update for order {cancellation_data.order_number}")
                        results['processed'] += 1
                        self._add_processed_label(message_id, 'cancellation')
                    else:
                        logger.error(f"Failed to process cancellation update for order {cancellation_data.order_number}: {error_msg}")
                        results['errors'] += 1
                        results['error_messages'].append(error_msg)
                        self._add_error_label(message_id, 'cancellation')
                
                except Exception as e:
                    error_msg = f"Error processing message {message_id}: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    results['errors'] += 1
                    results['error_messages'].append(error_msg)
                    self._add_error_label(message_id, 'cancellation')
        
        except Exception as e:
            error_msg = f"Fatal error in Footlocker cancellation email processing: {str(e)}"
            logger.error(error_msg, exc_info=True)
            results['error_messages'].append(error_msg)
        
        logger.info(f"Footlocker cancellation processing complete: {results}")
        return results

    def process_snipes_cancellation_emails(self, max_emails: int = 20) -> dict:
        """
        Process Snipes cancellation emails (partial and full).
        Partial: "Cancelation Update" - extractable data.
        Full: "Update on Your SNIPES Order" - no extractable data, queued for manual review.
        """
        logger.info(f"Starting Snipes cancellation email processing (max {max_emails} emails)")
        results = {'total_emails': 0, 'processed': 0, 'errors': 0, 'error_messages': [], 'queued': 0}
        try:
            query = (
                f'from:{self.snipes_parser.update_from_email} '
                f'({self.snipes_parser.cancellation_subject_query} OR {self.snipes_parser.full_cancellation_subject_query}) '
                f'-label:{self.CANCEL_PROCESSED_LABEL} -label:{self.CANCEL_ERROR_LABEL} -label:{self.CANCEL_MANUAL_REVIEW_LABEL}'
            )
            message_ids = self.gmail_service.list_messages_with_query(query=query, max_results=max_emails)
            results['total_emails'] = len(message_ids)
            for message_id in message_ids:
                try:
                    if self._is_email_processed(message_id, 'cancellation'):
                        continue
                    message = self.gmail_service.get_message(message_id)
                    if not message:
                        continue
                    email_data = self.gmail_service.parse_message_to_email_data(message)
                    if not self.snipes_parser.is_cancellation_email(email_data):
                        continue
                    cancellation_data = self.snipes_parser.parse_cancellation_email(email_data)
                    if not cancellation_data:
                        if self.snipes_parser.is_full_cancellation_email(email_data):
                            try:
                                existing = self.db.query(EmailManualReview).filter(
                                    EmailManualReview.gmail_message_id == message_id
                                ).first()
                                if not existing:
                                    entry = EmailManualReview(
                                        gmail_message_id=message_id,
                                        retailer='snipes',
                                        email_type='cancellation',
                                        subject=email_data.subject or '',
                                        extracted_order_number=None,
                                        extracted_items=[],
                                        missing_fields='order_number',
                                        error_reason='Snipes full cancellation: no extractable data - enter order number manually',
                                        status='pending',
                                    )
                                    self.db.add(entry)
                                    self.db.commit()
                                    results['queued'] += 1
                                    logger.info(f"📋 Queued Snipes full cancellation for manual review: message_id={message_id}")
                            except Exception as e:
                                logger.warning(f"Failed to enqueue Snipes full cancellation: {e}")
                                self.db.rollback()
                        results['errors'] += 1
                        self._add_error_label(message_id, 'cancellation')
                        continue
                    success, error_msg = self._process_snipes_cancellation_update(cancellation_data)
                    if success:
                        results['processed'] += 1
                        self._add_processed_label(message_id, 'cancellation')
                    else:
                        results['errors'] += 1
                        results['error_messages'].append(error_msg or 'Unknown error')
                        self._add_error_label(message_id, 'cancellation')
                except Exception as e:
                    results['errors'] += 1
                    results['error_messages'].append(str(e))
                    self._add_error_label(message_id, 'cancellation')
        except Exception as e:
            results['error_messages'].append(str(e))
        logger.info(f"Snipes cancellation processing complete: {results}")
        return results
    
    def _recalculate_status_and_location(self, record: PurchaseTracker) -> None:
        """
        Recalculate status and location for a purchase tracker record based on fulfillment fields.
        
        Args:
            record: PurchaseTracker record to update
        """
        try:
            status, location = calculate_status_and_location(
                shipped_to_pw=record.shipped_to_pw,
                checked_in=record.checked_in,
                shipped_out=record.shipped_out,
                final_qty=record.final_qty
            )
            record.status = status
            record.location = location
        except Exception as e:
            logger.error(f"Error recalculating status/location for record {record.id}: {e}")
    
    def _is_email_processed(self, message_id: str, email_type: str = 'shipping') -> bool:
        """
        Check if an email has already been processed.
        
        Args:
            message_id: Gmail message ID
            email_type: 'shipping' or 'cancellation'
        
        Returns:
            True if email has been processed, False otherwise
        """
        try:
            message = self.gmail_service.get_message(message_id)
            if not message:
                return False
            
            label_ids = message.get('labelIds', [])
            
            # Check new type-specific processed label
            if email_type == 'cancellation':
                new_label = self.cancel_processed_label
                new_label_name = self.CANCEL_PROCESSED_LABEL
            else:
                new_label = self.shipping_processed_label
                new_label_name = self.SHIPPING_PROCESSED_LABEL
            
            if new_label and new_label['id'] in label_ids:
                logger.info(f"Email {message_id} has already been processed (has {new_label_name} label)")
                return True
            
            # Backward compat: also check legacy Retailer-Updates/Processed
            legacy_id = self.processed_label['id'] if self.processed_label else None
            if legacy_id and legacy_id in label_ids:
                logger.info(f"Email {message_id} has already been processed (has {self.PROCESSED_LABEL} label)")
                return True
            
            return False
        except Exception as e:
            logger.error(f"Error checking if email {message_id} is processed: {e}")
            return False  # If we can't check, allow processing to proceed
    
    def process_single_shipping_email(
        self, 
        email_data: EmailData, 
        message_id: str, 
        retailer_name: str
    ) -> dict:
        """
        Process a single shipping notification email (called from webhook).
        
        Checks if email has already been processed before processing to prevent duplicates.
        
        Args:
            email_data: EmailData object
            message_id: Gmail message ID
            retailer_name: Retailer name (e.g., 'footlocker')
        
        Returns:
            Dictionary with processing results
        """
        # Check if email has already been processed
        if self._is_email_processed(message_id, 'shipping'):
            logger.info(f"Skipping already processed email {message_id}")
            return {
                'success': True,
                'order_number': None,
                'tracking_number': None,
                'items_count': 0,
                'already_processed': True
            }
        
        try:
            if retailer_name == 'footlocker' or retailer_name == 'kidsfootlocker':
                shipping_data = self.footlocker_parser.parse_shipping_email(email_data)
                if not shipping_data:
                    self._add_error_label(message_id, 'shipping')
                    return {'success': False, 'error': 'Failed to parse shipping data'}
                
                success, error_msg = self._process_shipping_update(shipping_data)
                
                if success:
                    self._add_processed_label(message_id, 'shipping')
                    return {
                        'success': True,
                        'order_number': shipping_data.order_number,
                        'tracking_number': shipping_data.tracking_number,
                        'items_count': len(shipping_data.items)
                    }
                else:
                    self._add_error_label(message_id, 'shipping')
                    return {'success': False, 'error': error_msg}
            elif retailer_name == 'champs':
                shipping_data = self.champs_parser.parse_shipping_email(email_data)
                if not shipping_data:
                    self._add_error_label(message_id, 'shipping')
                    return {'success': False, 'error': 'Failed to parse shipping data'}
                
                success, error_msg = self._process_champs_shipping_update(shipping_data)
                
                if success:
                    self._add_processed_label(message_id, 'shipping')
                    return {
                        'success': True,
                        'order_number': shipping_data.order_number,
                        'tracking_number': shipping_data.tracking_number,
                        'items_count': len(shipping_data.items)
                    }
                else:
                    self._add_error_label(message_id, 'shipping')
                    return {'success': False, 'error': error_msg}
            elif retailer_name == 'hibbett':
                shipping_data = self.hibbett_parser.parse_shipping_email(email_data)
                if not shipping_data:
                    partial = self.hibbett_parser.parse_shipping_email_partial(email_data)
                    queued = False
                    if partial:
                        try:
                            existing = self.db.query(EmailManualReview).filter(
                                EmailManualReview.gmail_message_id == message_id
                            ).first()
                            if not existing:
                                extracted_items = [
                                    {
                                        'product_name': it.get('product_name'),
                                        'product_number': it.get('product_number'),
                                        'color': it.get('color'),
                                        'quantity': it.get('quantity', 1),
                                    }
                                    for it in partial.get('items', [])
                                ]
                                entry = EmailManualReview(
                                    gmail_message_id=message_id,
                                    retailer='hibbett',
                                    email_type='shipping',
                                    subject=partial.get('subject', '') or email_data.subject,
                                    extracted_order_number=partial.get('order_number'),
                                    extracted_items=extracted_items,
                                    missing_fields=','.join(partial.get('missing_fields', ['unique_id', 'size'])),
                                    error_reason='Hibbett shipping: no unique_id/size in email - needs manual entry',
                                    status='pending',
                                )
                                self.db.add(entry)
                                self.db.commit()
                                queued = True
                                logger.info(
                                    f"📋 Queued Hibbett shipping for manual review: message_id={message_id}"
                                )
                        except Exception as e:
                            logger.warning(f"Failed to enqueue Hibbett shipping for manual review: {e}")
                            self.db.rollback()
                    self._add_manual_review_label(message_id, 'shipping')
                    return {
                        'success': False,
                        'error': 'Failed to parse Hibbett shipping data',
                        'queued_for_manual_review': queued,
                    }
                
                success, error_msg = self._process_hibbett_shipping_update(shipping_data)
                
                if success:
                    self._add_processed_label(message_id, 'shipping')
                    return {
                        'success': True,
                        'order_number': shipping_data.order_number,
                        'tracking_number': None,  # Hibbett typically doesn't provide tracking in email
                        'items_count': len(shipping_data.items)
                    }
                else:
                    # Process failed (e.g. no matching records) - queue for manual review
                    queued = False
                    try:
                        existing = self.db.query(EmailManualReview).filter(
                            EmailManualReview.gmail_message_id == message_id
                        ).first()
                        if not existing:
                            # Preserve unique_id/size - data is complete, failure was no matching records
                            extracted_items = [
                                {
                                    'unique_id': it.unique_id,
                                    'size': it.size,
                                    'product_name': it.product_name,
                                    'product_number': it.product_number,
                                    'color': it.color,
                                    'quantity': it.quantity,
                                }
                                for it in shipping_data.items
                            ]
                            entry = EmailManualReview(
                                gmail_message_id=message_id,
                                retailer='hibbett',
                                email_type='shipping',
                                subject=email_data.subject or '',
                                extracted_order_number=shipping_data.order_number,
                                extracted_items=extracted_items,
                                missing_fields='',  # Data complete - can resolve without feeding in
                                error_reason=error_msg or 'No matching records - process order confirmation first, then resolve',
                                status='pending',
                            )
                            self.db.add(entry)
                            self.db.commit()
                            queued = True
                            logger.info(
                                f"📋 Queued Hibbett shipping for manual review (no matches): message_id={message_id}"
                            )
                            self._add_manual_review_label(message_id, 'shipping')
                        else:
                            self._add_error_label(message_id, 'shipping')
                    except Exception as e:
                        logger.warning(f"Failed to enqueue Hibbett shipping for manual review: {e}")
                        self.db.rollback()
                        self._add_error_label(message_id, 'shipping')
                    return {
                        'success': False,
                        'error': error_msg,
                        'queued_for_manual_review': queued,
                    }
            elif retailer_name == 'dicks':
                shipping_data = self.dicks_parser.parse_shipping_email(email_data)
                if not shipping_data:
                    self._add_error_label(message_id, 'shipping')
                    return {'success': False, 'error': 'Failed to parse shipping data'}
                
                success, error_msg = self._process_dicks_shipping_update(shipping_data)
                
                if success:
                    self._add_processed_label(message_id, 'shipping')
                    return {
                        'success': True,
                        'order_number': shipping_data.order_number,
                        'tracking_number': None,  # Dick's typically doesn't provide tracking in email
                        'items_count': len(shipping_data.items)
                    }
                else:
                    self._add_error_label(message_id, 'shipping')
                    return {'success': False, 'error': error_msg}
            elif retailer_name == 'dtlr':
                shipping_data = self.dtlr_parser.parse_shipping_email(email_data)
                if not shipping_data:
                    self._add_error_label(message_id, 'shipping')
                    return {'success': False, 'error': 'Failed to parse shipping data'}
                
                success, error_msg = self._process_dtlr_shipping_update(shipping_data)
                
                if success:
                    self._add_processed_label(message_id, 'shipping')
                    return {
                        'success': True,
                        'order_number': shipping_data.order_number,
                        'tracking_number': None,  # DTLR has multiple tracking numbers per email
                        'items_count': len(shipping_data.items)
                    }
                else:
                    self._add_error_label(message_id, 'shipping')
                    return {'success': False, 'error': error_msg}
            elif retailer_name == 'finishline':
                shipping_data = self.finishline_parser.parse_shipping_email(email_data)
                if not shipping_data:
                    self._add_error_label(message_id, 'shipping')
                    return {'success': False, 'error': 'Failed to parse Finish Line shipping data'}
                
                success, error_msg = self._process_finishline_shipping_update(shipping_data)
                
                if success:
                    self._add_processed_label(message_id, 'shipping')
                    items_count = len(shipping_data.items)
                    if shipping_data.cancellation_items:
                        items_count += len(shipping_data.cancellation_items)
                    first_tracking = next((i.tracking for i in shipping_data.items if i.tracking), None)
                    return {
                        'success': True,
                        'order_number': shipping_data.order_number,
                        'tracking_number': first_tracking,
                        'items_count': items_count
                    }
                else:
                    self._add_error_label(message_id, 'shipping')
                    return {'success': False, 'error': error_msg}
            elif retailer_name == 'jdsports':
                shipping_data = self.jdsports_parser.parse_shipping_email(email_data)
                if not shipping_data:
                    self._add_error_label(message_id, 'shipping')
                    return {'success': False, 'error': 'Failed to parse JD Sports shipping data'}
                
                success, error_msg = self._process_finishline_shipping_update(shipping_data)
                
                if success:
                    self._add_processed_label(message_id, 'shipping')
                    items_count = len(shipping_data.items)
                    if shipping_data.cancellation_items:
                        items_count += len(shipping_data.cancellation_items)
                    first_tracking = next((i.tracking for i in shipping_data.items if i.tracking), None)
                    return {
                        'success': True,
                        'order_number': shipping_data.order_number,
                        'tracking_number': first_tracking,
                        'items_count': items_count
                    }
                else:
                    self._add_error_label(message_id, 'shipping')
                    return {'success': False, 'error': error_msg}
            elif retailer_name == 'revolve':
                shipping_data = self.revolve_parser.parse_shipping_email(email_data)
                if not shipping_data:
                    self._add_error_label(message_id, 'shipping')
                    return {'success': False, 'error': 'Failed to parse Revolve shipping data'}
                
                success, error_msg = self._process_revolve_shipping_update(shipping_data)
                
                if success:
                    self._add_processed_label(message_id, 'shipping')
                    return {
                        'success': True,
                        'order_number': shipping_data.order_number,
                        'tracking_number': shipping_data.tracking_number or None,
                        'items_count': len(shipping_data.items)
                    }
                else:
                    self._add_error_label(message_id, 'shipping')
                    return {'success': False, 'error': error_msg}
            elif retailer_name == 'asos':
                shipping_data = self.asos_parser.parse_shipping_email(email_data)
                if not shipping_data:
                    self._add_error_label(message_id, 'shipping')
                    return {'success': False, 'error': 'Failed to parse ASOS shipping data'}
                
                success, error_msg = self._process_asos_shipping_update(shipping_data)
                
                if success:
                    self._add_processed_label(message_id, 'shipping')
                    return {
                        'success': True,
                        'order_number': shipping_data.order_number,
                        'tracking_number': shipping_data.tracking_number or None,
                        'items_count': len(shipping_data.items)
                    }
                else:
                    self._add_error_label(message_id, 'shipping')
                    return {'success': False, 'error': error_msg}
            elif retailer_name == 'snipes':
                shipping_data = self.snipes_parser.parse_shipping_email(email_data)
                if not shipping_data:
                    self._add_error_label(message_id, 'shipping')
                    return {'success': False, 'error': 'Failed to parse Snipes shipping data'}
                
                success, error_msg = self._process_snipes_shipping_update(shipping_data)
                
                if success:
                    self._add_processed_label(message_id, 'shipping')
                    return {
                        'success': True,
                        'order_number': shipping_data.order_number,
                        'tracking_number': shipping_data.tracking_number or None,
                        'items_count': len(shipping_data.items)
                    }
                else:
                    self._add_error_label(message_id, 'shipping')
                    return {'success': False, 'error': error_msg}
            elif retailer_name == 'shoepalace':
                shipping_data = self.shoepalace_parser.parse_shipping_email(email_data)
                if not shipping_data:
                    self._add_error_label(message_id, 'shipping')
                    return {'success': False, 'error': 'Failed to parse Shoe Palace shipping data'}
                
                success, error_msg = self._process_shoepalace_shipping_update(shipping_data)
                
                if success:
                    self._add_processed_label(message_id, 'shipping')
                    return {
                        'success': True,
                        'order_number': shipping_data.order_number,
                        'tracking_number': shipping_data.tracking_number or None,
                        'items_count': len(shipping_data.items)
                    }
                else:
                    self._add_error_label(message_id, 'shipping')
                    return {'success': False, 'error': error_msg}
            elif retailer_name == 'endclothing':
                shipping_data = self.endclothing_parser.parse_shipping_email(email_data)
                if not shipping_data:
                    self._add_error_label(message_id, 'shipping')
                    return {'success': False, 'error': 'Failed to parse END Clothing shipping data'}
                
                success, error_msg = self._process_endclothing_shipping_update(shipping_data)
                
                if success:
                    self._add_processed_label(message_id, 'shipping')
                    return {
                        'success': True,
                        'order_number': shipping_data.order_number,
                        'tracking_number': shipping_data.tracking_number or None,
                        'items_count': len(shipping_data.items)
                    }
                else:
                    self._add_error_label(message_id, 'shipping')
                    return {'success': False, 'error': error_msg}
            elif retailer_name == 'shopwss':
                shipping_data = self.shopwss_parser.parse_shipping_email(email_data)
                if not shipping_data:
                    self._add_error_label(message_id, 'shipping')
                    return {'success': False, 'error': 'Failed to parse ShopWSS shipping data'}
                
                success, error_msg = self._process_shopwss_shipping_update(shipping_data)
                
                if success:
                    self._add_processed_label(message_id, 'shipping')
                    return {
                        'success': True,
                        'order_number': shipping_data.order_number,
                        'tracking_number': shipping_data.tracking_number or None,
                        'items_count': len(shipping_data.items)
                    }
                else:
                    self._add_error_label(message_id, 'shipping')
                    return {'success': False, 'error': error_msg}
            elif retailer_name == 'als':
                shipping_data = self.als_parser.parse_shipping_email(email_data)
                if not shipping_data:
                    self._add_error_label(message_id, 'shipping')
                    return {'success': False, 'error': "Failed to parse Al's shipping data"}

                success, error_msg = self._process_als_shipping_update(shipping_data)

                if success:
                    self._add_processed_label(message_id, 'shipping')
                    return {
                        'success': True,
                        'order_number': shipping_data.order_number,
                        'tracking_number': shipping_data.tracking_number or None,
                        'items_count': len(shipping_data.items)
                    }
                else:
                    self._add_error_label(message_id, 'shipping')
                    return {'success': False, 'error': error_msg}
            elif retailer_name == 'academy':
                shipping_data = self.academy_parser.parse_shipping_email(email_data)
                if not shipping_data:
                    self._add_error_label(message_id, 'shipping')
                    return {'success': False, 'error': "Failed to parse Academy Sports shipping data"}

                success, error_msg = self._process_academy_shipping_update(shipping_data)

                if success:
                    self._add_processed_label(message_id, 'shipping')
                    return {
                        'success': True,
                        'order_number': shipping_data.order_number,
                        'tracking_number': shipping_data.tracking_number or None,
                        'items_count': len(shipping_data.items)
                    }
                else:
                    self._add_error_label(message_id, 'shipping')
                    return {'success': False, 'error': error_msg}
            elif retailer_name == 'scheels':
                shipping_data = self.scheels_parser.parse_shipping_email(email_data)
                if not shipping_data:
                    self._add_error_label(message_id, 'shipping')
                    return {'success': False, 'error': "Failed to parse Scheels shipping data"}

                success, error_msg = self._process_scheels_shipping_update(shipping_data)

                if success:
                    self._add_processed_label(message_id, 'shipping')
                    return {
                        'success': True,
                        'order_number': shipping_data.order_number,
                        'tracking_number': shipping_data.tracking_number or None,
                        'items_count': len(shipping_data.items)
                    }
                else:
                    self._add_error_label(message_id, 'shipping')
                    return {'success': False, 'error': error_msg}
            elif retailer_name == 'urban' or retailer_name == 'urbanoutfitters':
                shipping_data = self.urban_parser.parse_shipping_email(email_data)
                if not shipping_data:
                    self._add_error_label(message_id, 'shipping')
                    return {'success': False, 'error': 'Failed to parse Urban Outfitters shipping data'}

                success, error_msg = self._process_urban_shipping_update(shipping_data)

                if success:
                    self._add_processed_label(message_id, 'shipping')
                    return {
                        'success': True,
                        'order_number': shipping_data.order_number,
                        'tracking_number': shipping_data.tracking_number or None,
                        'items_count': len(shipping_data.items)
                    }
                else:
                    self._add_error_label(message_id, 'shipping')
                    return {'success': False, 'error': error_msg}
            else:
                return {'success': False, 'error': f'Retailer {retailer_name} not supported for shipping updates yet'}

        except Exception as e:
            logger.error(f"Error processing single shipping email: {e}", exc_info=True)
            self._add_error_label(message_id, 'shipping')
            return {'success': False, 'error': str(e)}

    def process_single_cancellation_email(
        self, 
        email_data: EmailData, 
        message_id: str, 
        retailer_name: str
    ) -> dict:
        """
        Process a single cancellation notification email (called from webhook).
        
        Checks if email has already been processed before processing to prevent duplicates.
        
        Args:
            email_data: EmailData object
            message_id: Gmail message ID
            retailer_name: Retailer name (e.g., 'footlocker')
        
        Returns:
            Dictionary with processing results
        """
        # Check if email has already been processed
        if self._is_email_processed(message_id, 'cancellation'):
            logger.info(f"Skipping already processed email {message_id}")
            return {
                'success': True,
                'order_number': None,
                'items_count': 0,
                'already_processed': True
            }
        
        try:
            if retailer_name == 'footlocker' or retailer_name == 'kidsfootlocker':
                cancellation_data = self.footlocker_parser.parse_cancellation_email(email_data)
                if not cancellation_data:
                    self._add_error_label(message_id, 'cancellation')
                    return {'success': False, 'error': 'Failed to parse cancellation data'}
                
                success, error_msg = self._process_cancellation_update(cancellation_data)
                
                if success:
                    self._add_processed_label(message_id, 'cancellation')
                    return {
                        'success': True,
                        'order_number': cancellation_data.order_number,
                        'items_count': len(cancellation_data.items)
                    }
                else:
                    self._add_error_label(message_id, 'cancellation')
                    return {'success': False, 'error': error_msg}
            elif retailer_name == 'champs':
                cancellation_data = self.champs_parser.parse_cancellation_email(email_data)
                if not cancellation_data:
                    self._add_error_label(message_id, 'cancellation')
                    return {'success': False, 'error': 'Failed to parse cancellation data'}
                
                success, error_msg = self._process_champs_cancellation_update(cancellation_data)
                
                if success:
                    self._add_processed_label(message_id, 'cancellation')
                    return {
                        'success': True,
                        'order_number': cancellation_data.order_number,
                        'items_count': len(cancellation_data.items)
                    }
                else:
                    self._add_error_label(message_id, 'cancellation')
                    return {'success': False, 'error': error_msg}
            elif retailer_name == 'hibbett':
                cancellation_data = self.hibbett_parser.parse_cancellation_email(email_data)
                if not cancellation_data:
                    self._add_error_label(message_id, 'cancellation')
                    return {'success': False, 'error': 'Failed to parse cancellation data'}
                
                success, error_msg = self._process_hibbett_cancellation_update(cancellation_data)
                
                if success:
                    self._add_processed_label(message_id, 'cancellation')
                    return {
                        'success': True,
                        'order_number': cancellation_data.order_number,
                        'items_count': len(cancellation_data.items)
                    }
                else:
                    self._add_error_label(message_id, 'cancellation')
                    return {'success': False, 'error': error_msg}
            elif retailer_name == 'dicks':
                cancellation_data = self.dicks_parser.parse_cancellation_email(email_data)
                if not cancellation_data:
                    self._add_error_label(message_id, 'cancellation')
                    return {'success': False, 'error': 'Failed to parse cancellation data'}
                
                success, error_msg = self._process_dicks_cancellation_update(cancellation_data)
                
                if success:
                    self._add_processed_label(message_id, 'cancellation')
                    return {
                        'success': True,
                        'order_number': cancellation_data.order_number,
                        'items_count': len(cancellation_data.items)
                    }
                else:
                    self._add_error_label(message_id, 'cancellation')
                    return {'success': False, 'error': error_msg}
            elif retailer_name == 'dtlr':
                cancellation_data = self.dtlr_parser.parse_cancellation_email(email_data)
                if not cancellation_data:
                    self._add_error_label(message_id, 'cancellation')
                    return {'success': False, 'error': 'Failed to parse cancellation data'}
                
                success, error_msg = self._process_dtlr_cancellation_update(cancellation_data)
                
                if success:
                    self._add_processed_label(message_id, 'cancellation')
                    return {
                        'success': True,
                        'order_number': cancellation_data.order_number,
                        'items_count': len(cancellation_data.items)
                    }
                else:
                    self._add_error_label(message_id, 'cancellation')
                    return {'success': False, 'error': error_msg}
            elif retailer_name == 'urban' or retailer_name == 'urbanoutfitters':
                cancellation_data = self.urban_parser.parse_cancellation_email(email_data)
                if not cancellation_data:
                    self._add_error_label(message_id, 'cancellation')
                    return {'success': False, 'error': 'Failed to parse cancellation data'}
                
                success, error_msg = self._process_urban_cancellation_update(cancellation_data)
                
                if success:
                    self._add_processed_label(message_id, 'cancellation')
                    return {
                        'success': True,
                        'order_number': cancellation_data.order_number,
                        'items_count': len(cancellation_data.items)
                    }
                else:
                    self._add_error_label(message_id, 'cancellation')
                    return {'success': False, 'error': error_msg}
            elif retailer_name == 'shoepalace':
                cancellation_data = self.shoepalace_parser.parse_cancellation_email(email_data)
                if not cancellation_data:
                    partial = self.shoepalace_parser.parse_cancellation_email_partial(email_data)
                    if partial:
                        try:
                            existing = self.db.query(EmailManualReview).filter(
                                EmailManualReview.gmail_message_id == message_id
                            ).first()
                            if not existing:
                                entry = EmailManualReview(
                                    gmail_message_id=message_id,
                                    retailer='shoepalace',
                                    email_type='cancellation',
                                    subject=partial.get('subject', '') or email_data.subject,
                                    extracted_order_number=partial.get('order_number'),
                                    extracted_items=partial.get('items', []),
                                    missing_fields=','.join(partial.get('missing_fields', [])),
                                    error_reason='Shoe Palace cancellation: unique_id not in email - needs manual entry',
                                    status='pending',
                                )
                                self.db.add(entry)
                                self.db.commit()
                                logger.info(
                                    f"Queued Shoe Palace cancellation for manual review: message_id={message_id}"
                                )
                        except Exception as e:
                            logger.warning(f"Failed to enqueue Shoe Palace cancellation: {e}")
                            self.db.rollback()
                        self._add_manual_review_label(message_id, 'cancellation')
                        return {
                            'success': False,
                            'error': 'Shoe Palace cancellation - queued for manual review',
                            'queued_for_manual_review': True,
                        }
                    self._add_error_label(message_id, 'cancellation')
                    return {'success': False, 'error': 'Failed to parse Shoe Palace cancellation data'}
                success, error_msg = self._process_shoepalace_cancellation_update(cancellation_data)
                
                if success:
                    self._add_processed_label(message_id, 'cancellation')
                    return {
                        'success': True,
                        'order_number': cancellation_data.order_number,
                        'items_count': len(cancellation_data.items)
                    }
                else:
                    self._add_error_label(message_id, 'cancellation')
                    return {'success': False, 'error': error_msg}
            elif retailer_name == 'orleans':
                cancellation_data = self.orleans_parser.parse_cancellation_email(email_data)
                if not cancellation_data:
                    self._add_error_label(message_id, 'cancellation')
                    return {'success': False, 'error': 'Failed to parse cancellation data'}
                
                success, error_msg = self._process_orleans_cancellation_update(cancellation_data)
                
                if success:
                    self._add_processed_label(message_id, 'cancellation')
                    return {
                        'success': True,
                        'order_number': cancellation_data.order_number,
                        'items_count': len(cancellation_data.items)
                    }
                else:
                    self._add_error_label(message_id, 'cancellation')
                    return {'success': False, 'error': error_msg}
            elif retailer_name == 'finishline':
                cancellation_data = self.finishline_parser.parse_cancellation_email(email_data)
                if not cancellation_data:
                    self._add_error_label(message_id, 'cancellation')
                    return {'success': False, 'error': 'Failed to parse cancellation data'}
                
                success, error_msg = self._process_finishline_cancellation_update(cancellation_data)
                
                if success:
                    self._add_processed_label(message_id, 'cancellation')
                    return {
                        'success': True,
                        'order_number': cancellation_data.order_number,
                        'items_count': len(cancellation_data.items)
                    }
                else:
                    self._add_error_label(message_id, 'cancellation')
                    return {'success': False, 'error': error_msg}
            elif retailer_name == 'jdsports':
                cancellation_data = self.jdsports_parser.parse_cancellation_email(email_data)
                if not cancellation_data:
                    self._add_error_label(message_id, 'cancellation')
                    return {'success': False, 'error': 'Failed to parse JD Sports cancellation data'}
                
                success, error_msg = self._process_finishline_cancellation_update(cancellation_data)
                
                if success:
                    self._add_processed_label(message_id, 'cancellation')
                    return {
                        'success': True,
                        'order_number': cancellation_data.order_number,
                        'items_count': len(cancellation_data.items)
                    }
                else:
                    self._add_error_label(message_id, 'cancellation')
                    return {'success': False, 'error': error_msg}
            elif retailer_name == 'revolve':
                cancellation_data = self.revolve_parser.parse_cancellation_email(email_data)
                if not cancellation_data:
                    partial = self.revolve_parser.parse_cancellation_email_partial(email_data)
                    queued = False
                    if partial:
                        try:
                            existing = self.db.query(EmailManualReview).filter(
                                EmailManualReview.gmail_message_id == message_id
                            ).first()
                            if not existing:
                                entry = EmailManualReview(
                                    gmail_message_id=message_id,
                                    retailer='revolve',
                                    email_type='cancellation',
                                    subject=partial.get('subject', '') or email_data.subject,
                                    extracted_order_number=partial.get('order_number'),
                                    extracted_items=partial.get('items', []),
                                    missing_fields=','.join(partial.get('missing_fields', [])),
                                    error_reason='Partial extraction - needs manual completion',
                                    status='pending',
                                )
                                self.db.add(entry)
                                self.db.commit()
                                queued = True
                                logger.info(
                                    f"📋 Queued Revolve cancellation for manual review: message_id={message_id}, "
                                    f"missing={partial.get('missing_fields')}"
                                )
                        except Exception as e:
                            logger.warning(f"Failed to enqueue manual review: {e}")
                            self.db.rollback()
                    self._add_manual_review_label(message_id, 'cancellation')
                    return {
                        'success': False,
                        'error': 'Failed to parse Revolve cancellation data',
                        'queued_for_manual_review': queued,
                    }
                
                success, error_msg = self._process_revolve_cancellation_update(cancellation_data)
                
                if success:
                    self._add_processed_label(message_id, 'cancellation')
                    return {
                        'success': True,
                        'order_number': cancellation_data.order_number,
                        'items_count': len(cancellation_data.items)
                    }
                else:
                    self._add_error_label(message_id, 'cancellation')
                    return {'success': False, 'error': error_msg}
            elif retailer_name == 'snipes':
                cancellation_data = self.snipes_parser.parse_cancellation_email(email_data)
                if not cancellation_data:
                    if self.snipes_parser.is_full_cancellation_email(email_data):
                        queued = False
                        try:
                            existing = self.db.query(EmailManualReview).filter(
                                EmailManualReview.gmail_message_id == message_id
                            ).first()
                            if not existing:
                                entry = EmailManualReview(
                                    gmail_message_id=message_id,
                                    retailer='snipes',
                                    email_type='cancellation',
                                    subject=email_data.subject or '',
                                    extracted_order_number=None,
                                    extracted_items=[],
                                    missing_fields='order_number',
                                    error_reason='Snipes full cancellation: no extractable data - enter order number manually',
                                    status='pending',
                                )
                                self.db.add(entry)
                                self.db.commit()
                                queued = True
                                logger.info(f"📋 Queued Snipes full cancellation for manual review: message_id={message_id}")
                        except Exception as e:
                            logger.warning(f"Failed to enqueue Snipes full cancellation for manual review: {e}")
                            self.db.rollback()
                        self._add_error_label(message_id, 'cancellation')
                        return {
                            'success': False,
                            'error': 'Snipes full cancellation - no extractable data',
                            'queued_for_manual_review': queued,
                        }
                    self._add_error_label(message_id, 'cancellation')
                    return {'success': False, 'error': 'Failed to parse Snipes cancellation data'}
                
                success, error_msg = self._process_snipes_cancellation_update(cancellation_data)
                
                if success:
                    self._add_processed_label(message_id, 'cancellation')
                    return {
                        'success': True,
                        'order_number': cancellation_data.order_number,
                        'items_count': len(cancellation_data.items)
                    }
                else:
                    self._add_error_label(message_id, 'cancellation')
                    return {'success': False, 'error': error_msg}
            elif retailer_name == 'shopwss':
                cancellation_data = self.shopwss_parser.parse_cancellation_email(email_data)
                if not cancellation_data:
                    partial = self.shopwss_parser.parse_cancellation_email_partial(email_data)
                    if partial:
                        try:
                            existing = self.db.query(EmailManualReview).filter(
                                EmailManualReview.gmail_message_id == message_id
                            ).first()
                            if not existing:
                                entry = EmailManualReview(
                                    gmail_message_id=message_id,
                                    retailer='shopwss',
                                    email_type='cancellation',
                                    subject=partial.get('subject', '') or email_data.subject,
                                    extracted_order_number=partial.get('order_number'),
                                    extracted_items=partial.get('items', []),
                                    missing_fields=','.join(partial.get('missing_fields', [])),
                                    error_reason='ShopWSS partial cancellation: unique_id not in email - needs manual entry',
                                    status='pending',
                                )
                                self.db.add(entry)
                                self.db.commit()
                                logger.info(
                                    f"Queued ShopWSS partial cancellation for manual review: message_id={message_id}"
                                )
                        except Exception as e:
                            logger.warning(f"Failed to enqueue ShopWSS partial cancellation: {e}")
                            self.db.rollback()
                        self._add_manual_review_label(message_id, 'cancellation')
                        return {
                            'success': False,
                            'error': 'ShopWSS partial cancellation - queued for manual review',
                            'queued_for_manual_review': True,
                        }
                    self._add_error_label(message_id, 'cancellation')
                    return {'success': False, 'error': 'Failed to parse ShopWSS cancellation data'}
                success, error_msg = self._process_shopwss_cancellation_update(cancellation_data)
                if success:
                    self._add_processed_label(message_id, 'cancellation')
                    return {
                        'success': True,
                        'order_number': cancellation_data.order_number,
                        'items_count': len(cancellation_data.items) if cancellation_data.items else None
                    }
                else:
                    self._add_error_label(message_id, 'cancellation')
                    return {'success': False, 'error': error_msg}
            elif retailer_name == 'als':
                cancellation_data = self.als_parser.parse_cancellation_email(email_data)
                if not cancellation_data:
                    self._add_error_label(message_id, 'cancellation')
                    return {'success': False, 'error': "Failed to parse Al's cancellation data"}

                success, error_msg = self._process_als_cancellation_update(cancellation_data)

                if success:
                    self._add_processed_label(message_id, 'cancellation')
                    return {
                        'success': True,
                        'order_number': cancellation_data.order_number,
                        'items_count': len(cancellation_data.items)
                    }
                else:
                    self._add_error_label(message_id, 'cancellation')
                    return {'success': False, 'error': error_msg}
            else:
                return {'success': False, 'error': f'Retailer {retailer_name} not supported for cancellation updates yet'}

        except Exception as e:
            logger.error(f"Error processing single cancellation email: {e}", exc_info=True)
            self._add_error_label(message_id, 'cancellation')
            return {'success': False, 'error': str(e)}
    
    def _process_shipping_update(self, shipping_data: FootlockerShippingData) -> Tuple[bool, Optional[str]]:
        """
        Process shipping update: Update shipped_to_pw and tracking.
        
        For each item in the shipping notification:
        1. Find matching purchase tracker record by order_number + unique_id + size
        2. Add the quantity to 'shipped_to_pw' (cumulative - sums from multiple shipping emails)
        3. Update tracking number
        
        Note: final_qty is set from order confirmation emails, not shipping emails.
        
        Args:
            shipping_data: FootlockerShippingData object
        
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            logger.info(f"Processing shipping update for order {shipping_data.order_number}")
            
            items_updated = 0
            
            for item in shipping_data.items:
                normalized_size = self._normalize_size(item.size)
                
                # Find matching purchase tracker record by order_number + unique_id + size
                matching_records = self.db.query(PurchaseTracker).join(
                    OASourcing, PurchaseTracker.oa_sourcing_id == OASourcing.id
                ).outerjoin(
                    AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                ).filter(
                    and_(
                        PurchaseTracker.order_number == shipping_data.order_number,
                        OASourcing.unique_id == item.unique_id,
                        or_(
                            AsinBank.size == item.size,
                            AsinBank.size == normalized_size
                        )
                    )
                ).all()
                
                # Fallback: manual size normalization
                if not matching_records:
                    all_for_order = self.db.query(PurchaseTracker).join(
                        OASourcing, PurchaseTracker.oa_sourcing_id == OASourcing.id
                    ).outerjoin(
                        AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                    ).filter(
                        and_(
                            PurchaseTracker.order_number == shipping_data.order_number,
                            OASourcing.unique_id == item.unique_id
                        )
                    ).all()
                    
                    for record in all_for_order:
                        db_size = record.asin_bank_ref.size if record.asin_bank_ref else None
                        if db_size and self._normalize_size(db_size) == normalized_size:
                            matching_records.append(record)
                
                if not matching_records:
                    logger.warning(
                        f"No purchase tracker record found for order {shipping_data.order_number}, "
                        f"unique_id {item.unique_id}, size {item.size}"
                    )
                    continue
                
                # Update each matching record (should typically be 1)
                for record in matching_records:
                    # Add quantity to shipped_to_pw (cumulative - sums from multiple shipping emails)
                    current_shipped_to_pw = record.shipped_to_pw or 0
                    record.shipped_to_pw = current_shipped_to_pw + item.quantity
                    
                    # Update tracking number if not already set
                    if not record.tracking and shipping_data.tracking_number:
                        record.tracking = shipping_data.tracking_number
                    
                    # Recalculate status and location
                    self._recalculate_status_and_location(record)
                    
                    logger.info(
                        f"Updated purchase tracker ID {record.id}: "
                        f"order={shipping_data.order_number}, unique_id={item.unique_id}, size={item.size}, "
                        f"shipped_to_pw {current_shipped_to_pw} -> {record.shipped_to_pw}"
                    )
                    items_updated += 1
            
            # Commit changes
            self.db.commit()
            
            logger.info(f"Successfully updated {items_updated} purchase tracker records")
            return (True, None)
        
        except Exception as e:
            self.db.rollback()
            error_msg = f"Error processing shipping update: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return (False, error_msg)
    
    def _normalize_size(self, size: str) -> str:
        """
        Normalize size for comparison (handles "11.0" vs "11" etc.)
        
        Args:
            size: Size string (e.g., "11.0", "11", "9.5")
        
        Returns:
            Normalized size string
        """
        if not size:
            return size
        
        # Convert "11.0" to "11", "09.5" to "9.5", etc.
        if re.match(r'^\d{1,2}\.\d$', size):
            num = float(size)
            # Remove .0 if it's a whole number
            return str(int(num)) if num % 1 == 0 else str(num)
        
        return size
    
    def _process_cancellation_update(self, cancellation_data: FootlockerCancellationData) -> Tuple[bool, Optional[str]]:
        """
        Process cancellation update: Deduct quantity from 'final_qty' and update 'cancelled_qty'.
        
        For each item in the cancellation notification:
        1. Find matching purchase tracker record by order_number + unique_id + size
        2. Deduct the quantity from 'final_qty'
        3. Add the quantity to 'cancelled_qty' (cumulative)
        
        Args:
            cancellation_data: FootlockerCancellationData object
        
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            logger.info(f"Processing cancellation update for order {cancellation_data.order_number}")
            
            items_updated = 0
            
            for item in cancellation_data.items:
                normalized_cancel_size = self._normalize_size(item.size)
                
                # Find matching purchase tracker record by order_number + unique_id + size
                matching_records = self.db.query(PurchaseTracker).join(
                    OASourcing, PurchaseTracker.oa_sourcing_id == OASourcing.id
                ).outerjoin(
                    AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                ).filter(
                    and_(
                        PurchaseTracker.order_number == cancellation_data.order_number,
                        OASourcing.unique_id == item.unique_id,
                        or_(
                            AsinBank.size == item.size,
                            AsinBank.size == normalized_cancel_size
                        )
                    )
                ).all()
                
                # Fallback: manual size normalization
                if not matching_records:
                    all_for_order = self.db.query(PurchaseTracker).join(
                        OASourcing, PurchaseTracker.oa_sourcing_id == OASourcing.id
                    ).outerjoin(
                        AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                    ).filter(
                        and_(
                            PurchaseTracker.order_number == cancellation_data.order_number,
                            OASourcing.unique_id == item.unique_id
                        )
                    ).all()
                    
                    for record in all_for_order:
                        db_size = record.asin_bank_ref.size if record.asin_bank_ref else None
                        if db_size and self._normalize_size(db_size) == normalized_cancel_size:
                            matching_records.append(record)
                
                if not matching_records:
                    logger.warning(
                        f"No purchase tracker record found for order {cancellation_data.order_number}, "
                        f"unique_id {item.unique_id}, size {item.size} (normalized: {normalized_cancel_size})"
                    )
                    continue
                
                # Update each matching record
                for record in matching_records:
                    # Deduct from final_qty
                    current_final_qty = record.final_qty or 0
                    record.final_qty = max(0, current_final_qty - item.quantity)
                    
                    # Add to cancelled_qty (cumulative)
                    current_cancelled = record.cancelled_qty or 0
                    record.cancelled_qty = current_cancelled + item.quantity
                    
                    # Recalculate status and location
                    self._recalculate_status_and_location(record)
                    
                    logger.info(
                        f"Updated purchase tracker ID {record.id}: "
                        f"order={cancellation_data.order_number}, unique_id={item.unique_id}, "
                        f"size={item.size} (matched DB size: {record.asin_bank_ref.size if record.asin_bank_ref else 'N/A'}), "
                        f"final_qty {current_final_qty} -> {record.final_qty}, "
                        f"cancelled_qty {current_cancelled} -> {record.cancelled_qty}"
                    )
                    items_updated += 1
            
            # Commit changes
            self.db.commit()
            
            logger.info(f"Successfully updated {items_updated} purchase tracker records for cancellation")
            return (True, None)
        
        except Exception as e:
            self.db.rollback()
            error_msg = f"Error processing cancellation update: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return (False, error_msg)
    
    def _process_champs_shipping_update(self, shipping_data: ChampsShippingData) -> Tuple[bool, Optional[str]]:
        """
        Process Champs Sports shipping update: Update shipped_to_pw and tracking.
        
        For each item in the shipping notification:
        1. Find matching purchase tracker record by order number and size
        2. Add the quantity to 'shipped_to_pw' (cumulative - sums from multiple shipping emails)
        3. Update tracking number
        
        Note: final_qty is set from order confirmation emails, not shipping emails.
        
        Args:
            shipping_data: ChampsShippingData object
        
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            logger.info(f"Processing Champs shipping update for order {shipping_data.order_number}")
            
            items_updated = 0
            
            for item in shipping_data.items:
                # Normalize the size from shipping email for comparison
                normalized_shipping_size = self._normalize_size(item.size)
                
                # Find matching purchase tracker record(s)
                # Match by order_number and size (handle both normalized and non-normalized sizes)
                matching_records = self.db.query(PurchaseTracker).join(
                    AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                ).filter(
                    and_(
                        PurchaseTracker.order_number == shipping_data.order_number,
                        or_(
                            AsinBank.size == item.size,  # Exact match
                            AsinBank.size == normalized_shipping_size  # Normalized match
                        )
                    )
                ).all()
                
                # If no exact matches, try to match by normalizing all sizes manually
                if not matching_records:
                    all_order_records = self.db.query(PurchaseTracker).join(
                        AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                    ).filter(
                        PurchaseTracker.order_number == shipping_data.order_number
                    ).all()
                    
                    for record in all_order_records:
                        db_size = record.asin_bank_ref.size if record.asin_bank_ref else None
                        if db_size:
                            normalized_db_size = self._normalize_size(db_size)
                            if normalized_db_size == normalized_shipping_size:
                                matching_records.append(record)
                
                if not matching_records:
                    logger.warning(
                        f"No purchase tracker record found for order {shipping_data.order_number}, "
                        f"size {item.size} (normalized: {normalized_shipping_size})"
                    )
                    continue
                
                # Update each matching record
                for record in matching_records:
                    # Add quantity to shipped_to_pw (cumulative - sums from multiple shipping emails)
                    current_shipped_to_pw = record.shipped_to_pw or 0
                    record.shipped_to_pw = current_shipped_to_pw + item.quantity
                    
                    # Update tracking number if not already set
                    if not record.tracking and shipping_data.tracking_number:
                        record.tracking = shipping_data.tracking_number
                    
                    # Recalculate status and location
                    self._recalculate_status_and_location(record)
                    
                    logger.info(
                        f"Updated purchase tracker ID {record.id}: "
                        f"shipped_to_pw {current_shipped_to_pw} -> {record.shipped_to_pw}"
                    )
                    items_updated += 1
            
            # Commit changes
            self.db.commit()
            
            logger.info(f"Successfully updated {items_updated} purchase tracker records")
            return (True, None)
        
        except Exception as e:
            self.db.rollback()
            error_msg = f"Error processing Champs shipping update: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return (False, error_msg)
    
    def _process_champs_cancellation_update(self, cancellation_data: ChampsCancellationData) -> Tuple[bool, Optional[str]]:
        """
        Process Champs Sports cancellation update: Deduct quantity from 'final_qty' and update 'cancelled_qty'.
        
        For each item in the cancellation notification:
        1. Find matching purchase tracker record by order number and size (with size normalization)
        2. Deduct the quantity from 'final_qty'
        3. Add the quantity to 'cancelled_qty' (cumulative)
        
        Args:
            cancellation_data: ChampsCancellationData object
        
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            logger.info(f"Processing Champs cancellation update for order {cancellation_data.order_number}")
            
            items_updated = 0
            
            for item in cancellation_data.items:
                # Normalize the size from cancellation email for comparison
                normalized_cancel_size = self._normalize_size(item.size)
                
                # Find matching purchase tracker record(s)
                # Match by order_number and size (handle both normalized and non-normalized sizes)
                matching_records = self.db.query(PurchaseTracker).join(
                    AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                ).filter(
                    and_(
                        PurchaseTracker.order_number == cancellation_data.order_number,
                        or_(
                            AsinBank.size == item.size,  # Exact match
                            AsinBank.size == normalized_cancel_size  # Normalized match
                        )
                    )
                ).all()
                
                # If no exact matches, try to match by normalizing all sizes manually
                if not matching_records:
                    all_order_records = self.db.query(PurchaseTracker).join(
                        AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                    ).filter(
                        PurchaseTracker.order_number == cancellation_data.order_number
                    ).all()
                    
                    for record in all_order_records:
                        db_size = record.asin_bank_ref.size if record.asin_bank_ref else None
                        if db_size:
                            normalized_db_size = self._normalize_size(db_size)
                            if normalized_db_size == normalized_cancel_size:
                                matching_records.append(record)
                
                if not matching_records:
                    logger.warning(
                        f"No purchase tracker record found for order {cancellation_data.order_number}, "
                        f"size {item.size} (normalized: {normalized_cancel_size})"
                    )
                    continue
                
                # Update each matching record
                for record in matching_records:
                    # Deduct from final_qty
                    current_final_qty = record.final_qty or 0
                    record.final_qty = max(0, current_final_qty - item.quantity)
                    
                    # Add to cancelled_qty (cumulative)
                    current_cancelled = record.cancelled_qty or 0
                    record.cancelled_qty = current_cancelled + item.quantity
                    
                    # Recalculate status and location
                    self._recalculate_status_and_location(record)
                    
                    logger.info(
                        f"Updated purchase tracker ID {record.id}: "
                        f"order={cancellation_data.order_number}, "
                        f"size={item.size} (matched DB size: {record.asin_bank_ref.size if record.asin_bank_ref else 'N/A'}), "
                        f"final_qty {current_final_qty} -> {record.final_qty}, "
                        f"cancelled_qty {current_cancelled} -> {record.cancelled_qty}"
                    )
                    items_updated += 1
            
            # Commit changes
            self.db.commit()
            
            logger.info(f"Successfully updated {items_updated} purchase tracker records")
            return (True, None)
        
        except Exception as e:
            self.db.rollback()
            error_msg = f"Error processing Champs cancellation update: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return (False, error_msg)
    
    def _process_hibbett_shipping_update(self, shipping_data: HibbettShippingData) -> Tuple[bool, Optional[str]]:
        """
        Process Hibbett shipping update: Update shipped_to_pw.
        
        For each item in the shipping notification:
        1. Find matching purchase tracker record by order number and size
        2. Add the quantity to 'shipped_to_pw' (cumulative - sums from multiple shipping emails)
        
        Fallback: When Size is missing from shipping email (parser uses "0"), match by order_number + unique_id.
        
        Note: final_qty is set from order confirmation emails, not shipping emails.
        
        Args:
            shipping_data: HibbettShippingData object
        
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            logger.info(f"Processing Hibbett shipping update for order {shipping_data.order_number}")
            
            items_updated = 0
            
            for item in shipping_data.items:
                # Normalize the size from shipping email for comparison
                normalized_shipping_size = self._normalize_size(item.size)
                
                # Find matching purchase tracker record(s)
                # Match by order_number and size (handle both normalized and non-normalized sizes)
                matching_records = self.db.query(PurchaseTracker).join(
                    AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                ).filter(
                    and_(
                        PurchaseTracker.order_number == shipping_data.order_number,
                        or_(
                            AsinBank.size == item.size,  # Exact match
                            AsinBank.size == normalized_shipping_size  # Normalized match
                        )
                    )
                ).all()
                
                # If no exact matches, try to match by normalizing all sizes manually
                if not matching_records:
                    all_order_records = self.db.query(PurchaseTracker).join(
                        AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                    ).filter(
                        PurchaseTracker.order_number == shipping_data.order_number
                    ).all()
                    
                    for record in all_order_records:
                        db_size = record.asin_bank_ref.size if record.asin_bank_ref else None
                        if db_size:
                            normalized_db_size = self._normalize_size(db_size)
                            if normalized_db_size == normalized_shipping_size:
                                matching_records.append(record)
                
                # Fallback: when size is "0" (placeholder from parser when Size missing in email),
                # match by order_number + unique_id (product_number) from OASourcing
                if not matching_records and item.size == "0" and item.unique_id:
                    matching_records = self.db.query(PurchaseTracker).join(
                        OASourcing, PurchaseTracker.oa_sourcing_id == OASourcing.id
                    ).filter(
                        and_(
                            PurchaseTracker.order_number == shipping_data.order_number,
                            OASourcing.unique_id == item.unique_id
                        )
                    ).all()
                    if matching_records:
                        logger.info(
                            f"Matched by unique_id (size missing in email): "
                            f"order={shipping_data.order_number}, unique_id={item.unique_id}"
                        )
                
                if not matching_records:
                    logger.warning(
                        f"No purchase tracker record found for order {shipping_data.order_number}, "
                        f"size {item.size} (normalized: {normalized_shipping_size})"
                    )
                    continue
                
                # Update each matching record
                for record in matching_records:
                    # Add quantity to shipped_to_pw (cumulative - sums from multiple shipping emails)
                    current_shipped_to_pw = record.shipped_to_pw or 0
                    record.shipped_to_pw = current_shipped_to_pw + item.quantity
                    
                    logger.info(
                        f"Updated purchase tracker ID {record.id}: "
                        f"shipped_to_pw {current_shipped_to_pw} -> {record.shipped_to_pw}"
                    )
                    items_updated += 1
            
            # Commit changes
            self.db.commit()
            
            if items_updated == 0:
                logger.warning("No purchase tracker records matched for Hibbett shipping - needs manual review")
                return (False, "No matching records - unique_id/size may be missing or incorrect in email")
            logger.info(f"Successfully updated {items_updated} purchase tracker records")
            return (True, None)
        
        except Exception as e:
            self.db.rollback()
            error_msg = f"Error processing Hibbett shipping update: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return (False, error_msg)
    
    def _process_hibbett_cancellation_update(self, cancellation_data: HibbettCancellationData) -> Tuple[bool, Optional[str]]:
        """
        Process Hibbett cancellation update: Deduct quantity from 'final_qty' and update 'cancelled_qty'.
        
        Match by order_number + unique_id + size (like Foot Locker), fallback to size-only.
        Ensures final_qty and cancelled_qty never go negative.
        
        Args:
            cancellation_data: HibbettCancellationData object
        
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            logger.info(f"Processing Hibbett cancellation update for order {cancellation_data.order_number}")
            
            items_updated = 0
            
            for item in cancellation_data.items:
                cancel_qty = max(0, item.quantity or 0)
                if cancel_qty <= 0:
                    continue
                normalized_cancel_size = self._normalize_size(item.size)
                
                # Match by order_number + unique_id + size (like Foot Locker)
                matching_records = []
                if item.unique_id:
                    matching_records = self.db.query(PurchaseTracker).join(
                        OASourcing, PurchaseTracker.oa_sourcing_id == OASourcing.id
                    ).outerjoin(
                        AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                    ).filter(
                        and_(
                            PurchaseTracker.order_number == cancellation_data.order_number,
                            OASourcing.unique_id == item.unique_id,
                            or_(
                                AsinBank.size == item.size,
                                AsinBank.size == normalized_cancel_size
                            )
                        )
                    ).all()
                    if not matching_records and item.unique_id:
                        all_for_order = self.db.query(PurchaseTracker).join(
                            OASourcing, PurchaseTracker.oa_sourcing_id == OASourcing.id
                        ).outerjoin(
                            AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                        ).filter(
                            and_(
                                PurchaseTracker.order_number == cancellation_data.order_number,
                                OASourcing.unique_id == item.unique_id
                            )
                        ).all()
                        for record in all_for_order:
                            db_size = record.asin_bank_ref.size if record.asin_bank_ref else None
                            if db_size and self._normalize_size(db_size) == normalized_cancel_size:
                                matching_records.append(record)
                
                # Fallback: match by order_number + size only
                if not matching_records:
                    matching_records = self.db.query(PurchaseTracker).join(
                        AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                    ).filter(
                        and_(
                            PurchaseTracker.order_number == cancellation_data.order_number,
                            or_(
                                AsinBank.size == item.size,
                                AsinBank.size == normalized_cancel_size
                            )
                        )
                    ).all()
                if not matching_records:
                    all_order_records = self.db.query(PurchaseTracker).join(
                        AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                    ).filter(
                        PurchaseTracker.order_number == cancellation_data.order_number
                    ).all()
                    for record in all_order_records:
                        db_size = record.asin_bank_ref.size if record.asin_bank_ref else None
                        if db_size and self._normalize_size(db_size) == normalized_cancel_size:
                            matching_records.append(record)
                
                if not matching_records:
                    logger.warning(
                        f"No purchase tracker record found for order {cancellation_data.order_number}, "
                        f"unique_id={item.unique_id}, size={item.size} (normalized: {normalized_cancel_size})"
                    )
                    continue
                
                for record in matching_records:
                    current_final_qty = record.final_qty or 0
                    og_qty = max(0, record.og_qty or 0)
                    effective_cancel = min(cancel_qty, current_final_qty)
                    record.final_qty = max(0, current_final_qty - effective_cancel)
                    current_cancelled = record.cancelled_qty or 0
                    record.cancelled_qty = min(og_qty, max(0, current_cancelled + effective_cancel))
                    self._recalculate_status_and_location(record)
                    logger.info(
                        f"Updated purchase tracker ID {record.id}: order={cancellation_data.order_number}, "
                        f"unique_id={item.unique_id}, size={item.size} (matched: {record.asin_bank_ref.size if record.asin_bank_ref else 'N/A'}), "
                        f"final_qty {current_final_qty} -> {record.final_qty}, cancelled_qty {current_cancelled} -> {record.cancelled_qty}"
                    )
                    items_updated += 1
            
            self.db.commit()
            logger.info(f"Successfully updated {items_updated} purchase tracker records for Hibbett cancellation")
            return (True, None)
        
        except Exception as e:
            self.db.rollback()
            error_msg = f"Error processing Hibbett cancellation update: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return (False, error_msg)
    
    def _process_dicks_shipping_update(self, shipping_data: DicksShippingData) -> Tuple[bool, Optional[str]]:
        """
        Process Dick's shipping update: Update shipped_to_pw.

        For each item in the shipping notification:
        1. Find matching purchase tracker record by order number and size (if available)
        2. If size is not available, try matching by unique_id or product name
        3. Add the quantity to 'shipped_to_pw' (cumulative - sums from multiple shipping emails)

        Note: final_qty is set from order confirmation emails, not shipping emails.

        Args:
            shipping_data: DicksShippingData object

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            logger.info(f"Processing Dick's shipping update for order {shipping_data.order_number}")

            items_updated = 0

            for item in shipping_data.items:
                matching_records = []

                # If size is available, match by order number and size (like Hibbett)
                if item.size:
                    normalized_shipping_size = self._normalize_size(item.size)

                    matching_records = self.db.query(PurchaseTracker).join(
                        AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                    ).filter(
                        and_(
                            PurchaseTracker.order_number == shipping_data.order_number,
                            or_(
                                AsinBank.size == item.size,  # Exact match
                                AsinBank.size == normalized_shipping_size  # Normalized match
                            )
                        )
                    ).all()

                    # If no exact matches, try to match by normalizing all sizes manually
                    if not matching_records:
                        all_order_records = self.db.query(PurchaseTracker).join(
                            AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                        ).filter(
                            PurchaseTracker.order_number == shipping_data.order_number
                        ).all()

                        for record in all_order_records:
                            db_size = record.asin_bank_ref.size if record.asin_bank_ref else None
                            if db_size:
                                normalized_db_size = self._normalize_size(db_size)
                                if normalized_db_size == normalized_shipping_size:
                                    matching_records.append(record)
                else:
                    # Size not available - match by order number only
                    # This is less precise but necessary when size is missing
                    matching_records = self.db.query(PurchaseTracker).filter(
                        PurchaseTracker.order_number == shipping_data.order_number
                    ).all()

                    logger.info(
                        f"Size not available for item {item.unique_id}, "
                        f"found {len(matching_records)} records for order {shipping_data.order_number}"
                    )

                if not matching_records:
                    logger.warning(
                        f"No purchase tracker record found for order {shipping_data.order_number}, "
                        f"size {item.size if item.size else 'N/A'}, unique_id {item.unique_id}"
                    )
                    continue

                # Update each matching record
                for record in matching_records:
                    # Add quantity to shipped_to_pw (cumulative - sums from multiple shipping emails)
                    current_shipped_to_pw = record.shipped_to_pw or 0
                    record.shipped_to_pw = current_shipped_to_pw + item.quantity

                    logger.info(
                        f"Updated purchase tracker ID {record.id}: "
                        f"shipped_to_pw {current_shipped_to_pw} -> {record.shipped_to_pw}"
                    )
                    items_updated += 1

            # Commit changes
            self.db.commit()

            logger.info(f"Successfully updated {items_updated} purchase tracker records")
            return (True, None)

        except Exception as e:
            self.db.rollback()
            error_msg = f"Error processing Dick's shipping update: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return (False, error_msg)
    
    def _process_dtlr_shipping_update(self, shipping_data: DTLRShippingData) -> Tuple[bool, Optional[str]]:
        """
        Process DTLR shipping update: Update shipped_to_pw.
        
        For each item in the shipping notification:
        1. Find matching purchase tracker record by order number and size
        2. Add the quantity to 'shipped_to_pw' (cumulative - sums from multiple shipping emails)
        
        Note: final_qty is set from order confirmation emails, not shipping emails.
        
        Args:
            shipping_data: DTLRShippingData object
        
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            logger.info(f"Processing DTLR shipping update for order {shipping_data.order_number}")
            
            items_updated = 0
            
            for item in shipping_data.items:
                matching_records = []
                
                # Match by order number and size (like Hibbett/Dicks)
                if item.size:
                    normalized_shipping_size = self._normalize_size(item.size)
                    
                    matching_records = self.db.query(PurchaseTracker).join(
                        AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                    ).filter(
                        and_(
                            PurchaseTracker.order_number == shipping_data.order_number,
                            or_(
                                AsinBank.size == item.size,  # Exact match
                                AsinBank.size == normalized_shipping_size  # Normalized match
                            )
                        )
                    ).all()
                    
                    # If no exact matches, try to match by normalizing all sizes manually
                    if not matching_records:
                        all_order_records = self.db.query(PurchaseTracker).join(
                            AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                        ).filter(
                            PurchaseTracker.order_number == shipping_data.order_number
                        ).all()
                        
                        for record in all_order_records:
                            db_size = record.asin_bank_ref.size if record.asin_bank_ref else None
                            if db_size:
                                normalized_db_size = self._normalize_size(db_size)
                                if normalized_db_size == normalized_shipping_size:
                                    matching_records.append(record)
                else:
                    # Size not available - match by order number only
                    matching_records = self.db.query(PurchaseTracker).filter(
                        PurchaseTracker.order_number == shipping_data.order_number
                    ).all()
                    
                    logger.info(
                        f"Size not available for shipped item {item.unique_id}, "
                        f"found {len(matching_records)} records for order {shipping_data.order_number}"
                    )
                
                if not matching_records:
                    logger.warning(
                        f"No purchase tracker record found for order {shipping_data.order_number}, "
                        f"size {item.size if item.size else 'N/A'}, unique_id {item.unique_id}"
                    )
                    continue
                
                # Update each matching record
                for record in matching_records:
                    # Add quantity to shipped_to_pw (cumulative - sums from multiple shipping emails)
                    current_shipped_to_pw = record.shipped_to_pw or 0
                    record.shipped_to_pw = current_shipped_to_pw + item.quantity
                    
                    logger.info(
                        f"Updated purchase tracker ID {record.id}: "
                        f"shipped_to_pw {current_shipped_to_pw} -> {record.shipped_to_pw}, "
                        f"tracking={item.tracking_number}"
                    )
                    items_updated += 1
            
            # Commit changes
            self.db.commit()
            
            logger.info(f"Successfully updated {items_updated} purchase tracker records")
            return (True, None)
        
        except Exception as e:
            self.db.rollback()
            error_msg = f"Error processing DTLR shipping update: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return (False, error_msg)
    
    def _process_dtlr_cancellation_update(self, cancellation_data: DTLRCancellationData) -> Tuple[bool, Optional[str]]:
        """
        Process DTLR cancellation update: Deduct quantity from 'final_qty' and update 'cancelled_qty'.
        
        For each item in the cancellation notification:
        1. Find matching purchase tracker record by order number and product name (since size is not available)
        2. Deduct the quantity from 'final_qty'
        3. Add the quantity to 'cancelled_qty' (cumulative)
        
        Args:
            cancellation_data: DTLRCancellationData object
        
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            logger.info(f"Processing DTLR cancellation update for order {cancellation_data.order_number}")
            
            items_updated = 0
            
            for item in cancellation_data.items:
                matching_records = []
                
                # Since size is not available in DTLR cancellation emails, match by order number and product name
                # Try to match by unique_id first (product code from image URL)
                all_order_records = self.db.query(PurchaseTracker).join(
                    AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                ).filter(
                    PurchaseTracker.order_number == cancellation_data.order_number
                ).all()
                
                # Match by product name (case-insensitive partial match)
                for record in all_order_records:
                    # Check if product name matches (case-insensitive, partial match)
                    if record.asin_bank_ref and record.asin_bank_ref.product_name:
                        db_product_name = record.asin_bank_ref.product_name.lower()
                        item_product_name = (item.product_name or "").lower()
                        
                        # Check for partial match (product name contains item name or vice versa)
                        if item_product_name in db_product_name or db_product_name in item_product_name:
                            matching_records.append(record)
                            continue
                    
                    # Also try matching by unique_id if available
                    if item.unique_id and record.asin_bank_ref:
                        # Check if unique_id matches any part of the product identifier
                        if item.unique_id.lower() in (record.asin_bank_ref.product_name or "").lower():
                            matching_records.append(record)
                
                # If no matches found, match by order number only (less precise but better than nothing)
                if not matching_records:
                    matching_records = all_order_records
                    logger.info(
                        f"No product name match found for cancelled item {item.product_name}, "
                        f"matching all {len(matching_records)} records for order {cancellation_data.order_number}"
                    )
                
                if not matching_records:
                    logger.warning(
                        f"No purchase tracker record found for order {cancellation_data.order_number}, "
                        f"product {item.product_name} (unique_id={item.unique_id})"
                    )
                    continue
                
                # Update each matching record
                for record in matching_records:
                    # Deduct from final_qty
                    current_final_qty = record.final_qty or 0
                    record.final_qty = max(0, current_final_qty - item.quantity)
                    
                    # Add to cancelled_qty (cumulative)
                    current_cancelled = record.cancelled_qty or 0
                    record.cancelled_qty = current_cancelled + item.quantity
                    
                    # Recalculate status and location
                    self._recalculate_status_and_location(record)
                    
                    logger.info(
                        f"Updated purchase tracker ID {record.id}: "
                        f"order={cancellation_data.order_number}, "
                        f"product={item.product_name}, "
                        f"final_qty {current_final_qty} -> {record.final_qty}, "
                        f"cancelled_qty {current_cancelled} -> {record.cancelled_qty}"
                    )
                    items_updated += 1
            
            # Commit changes
            self.db.commit()
            
            logger.info(f"Successfully updated {items_updated} purchase tracker records")
            return (True, None)
        
        except Exception as e:
            self.db.rollback()
            error_msg = f"Error processing DTLR cancellation update: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return (False, error_msg)
    
    def _process_dicks_cancellation_update(self, cancellation_data: DicksCancellationData) -> Tuple[bool, Optional[str]]:
        """
        Process Dick's cancellation update: Deduct quantity from 'final_qty' and update 'cancelled_qty'.
        
        For each item in the cancellation notification:
        1. Find matching purchase tracker record by order number and size (if available)
        2. If size is not available, match by order number only
        3. Deduct the quantity from 'final_qty'
        4. Add the quantity to 'cancelled_qty' (cumulative)
        
        Args:
            cancellation_data: DicksCancellationData object
        
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            logger.info(f"Processing Dick's cancellation update for order {cancellation_data.order_number}")
            
            items_updated = 0
            
            for item in cancellation_data.items:
                matching_records = []
                
                # If size is available, match by order number and size
                if item.size:
                    normalized_cancellation_size = self._normalize_size(item.size)
                    
                    matching_records = self.db.query(PurchaseTracker).join(
                        AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                    ).filter(
                        
                        and_(
                            PurchaseTracker.order_number == cancellation_data.order_number,
                            or_(
                                AsinBank.size == item.size,  # Exact match
                                AsinBank.size == normalized_cancellation_size  # Normalized match
                            )
                        )
                    ).all()
                    
                    # If no exact matches, try to match by normalizing all sizes manually
                    if not matching_records:
                        all_order_records = self.db.query(PurchaseTracker).join(
                            AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                        ).filter(
                            PurchaseTracker.order_number == cancellation_data.order_number
                        ).all()
                        
                        for record in all_order_records:
                            db_size = record.asin_bank_ref.size if record.asin_bank_ref else None
                            if db_size:
                                normalized_db_size = self._normalize_size(db_size)
                                if normalized_db_size == normalized_cancellation_size:
                                    matching_records.append(record)
                else:
                    # Size not available - match by order number only
                    matching_records = self.db.query(PurchaseTracker).filter(
                        PurchaseTracker.order_number == cancellation_data.order_number
                    ).all()
                    
                    logger.info(
                        f"Size not available for cancelled item {item.unique_id}, "
                        f"found {len(matching_records)} records for order {cancellation_data.order_number}"
                    )
                
                if not matching_records:
                    logger.warning(
                        f"No purchase tracker record found for order {cancellation_data.order_number}, "
                        f"size {item.size if item.size else 'N/A'}, unique_id {item.unique_id}"
                    )
                    continue
                
                # Update each matching record
                for record in matching_records:
                    # Deduct quantity from final_qty
                    current_final_qty = record.final_qty or 0
                    new_final_qty = max(0, current_final_qty - item.quantity)  # Don't go below 0
                    record.final_qty = new_final_qty
                    
                    # Add quantity to cancelled_qty (cumulative)
                    current_cancelled = record.cancelled_qty or 0
                    record.cancelled_qty = current_cancelled + item.quantity
                    
                    # Recalculate status and location
                    self._recalculate_status_and_location(record)
                    
                    logger.info(
                        f"Updated purchase tracker ID {record.id}: "
                        f"final_qty {current_final_qty} -> {new_final_qty}, "
                        f"cancelled_qty {current_cancelled} -> {record.cancelled_qty}"
                    )
                    items_updated += 1
            
            # Commit changes
            self.db.commit()
            
            # Check if order was paid with gift card and send notification
            self._check_and_notify_gift_card_cancellation(cancellation_data.order_number)
            
            logger.info(f"Successfully updated {items_updated} purchase tracker records")
            return (True, None)
        
        except Exception as e:
            self.db.rollback()
            error_msg = f"Error processing Dick's cancellation update: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return (False, error_msg)
    
    def _process_urban_cancellation_update(self, cancellation_data: UrbanOutfittersCancellationData) -> Tuple[bool, Optional[str]]:
        """
        Process Urban Outfitters cancellation update: Deduct quantity from 'final_qty' and update 'cancelled_qty'.
        
        For each item in the cancellation notification:
        1. Find matching purchase tracker record by order number and size (with size normalization)
        2. Deduct the quantity from 'final_qty'
        3. Add the quantity to 'cancelled_qty' (cumulative)
        
        Args:
            cancellation_data: UrbanOutfittersCancellationData object
        
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            logger.info(f"Processing Urban Outfitters cancellation update for order {cancellation_data.order_number}")
            
            items_updated = 0
            
            for item in cancellation_data.items:
                # Normalize the size from cancellation email for comparison
                normalized_cancel_size = self._normalize_size(item.size)
                
                # Find matching purchase tracker record(s)
                # Match by order_number and size (handle both normalized and non-normalized sizes)
                matching_records = self.db.query(PurchaseTracker).join(
                    AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                ).filter(
                    and_(
                        PurchaseTracker.order_number == cancellation_data.order_number,
                        or_(
                            AsinBank.size == item.size,  # Exact match
                            AsinBank.size == normalized_cancel_size  # Normalized match
                        )
                    )
                ).all()
                
                # If no exact matches, try to match by normalizing all sizes manually
                if not matching_records:
                    all_order_records = self.db.query(PurchaseTracker).join(
                        AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                    ).filter(
                        PurchaseTracker.order_number == cancellation_data.order_number
                    ).all()
                    
                    for record in all_order_records:
                        db_size = record.asin_bank_ref.size if record.asin_bank_ref else None
                        if db_size:
                            normalized_db_size = self._normalize_size(db_size)
                            if normalized_db_size == normalized_cancel_size:
                                matching_records.append(record)
                
                if not matching_records:
                    logger.warning(
                        f"No purchase tracker record found for order {cancellation_data.order_number}, "
                        f"size {item.size} (normalized: {normalized_cancel_size}), unique_id {item.unique_id}"
                    )
                    continue
                
                # Update each matching record
                for record in matching_records:
                    # Deduct from final_qty
                    current_final_qty = record.final_qty or 0
                    record.final_qty = max(0, current_final_qty - item.quantity)
                    
                    # Add to cancelled_qty (cumulative)
                    current_cancelled = record.cancelled_qty or 0
                    record.cancelled_qty = current_cancelled + item.quantity
                    
                    # Recalculate status and location
                    self._recalculate_status_and_location(record)
                    
                    logger.info(
                        f"Updated purchase tracker ID {record.id}: "
                        f"order={cancellation_data.order_number}, "
                        f"size={item.size} (matched DB size: {record.asin_bank_ref.size if record.asin_bank_ref else 'N/A'}), "
                        f"final_qty {current_final_qty} -> {record.final_qty}, "
                        f"cancelled_qty {current_cancelled} -> {record.cancelled_qty}"
                    )
                    items_updated += 1
            
            # Commit changes
            self.db.commit()
            
            logger.info(f"Successfully updated {items_updated} purchase tracker records for cancellation")
            return (True, None)
        
        except Exception as e:
            self.db.rollback()
            error_msg = f"Error processing Urban Outfitters cancellation update: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return (False, error_msg)

    def _process_urban_shipping_update(self, shipping_data: UrbanOutfittersShippingData) -> Tuple[bool, Optional[str]]:
        """
        Process Urban Outfitters shipping update: Add quantity to 'shipped_to_pw' (cumulative)
        and set tracking number.

        For each item in the shipping notification:
        1. Find matching purchase tracker record by order number and size (with size normalization)
        2. Add the quantity to 'shipped_to_pw' (cumulative — supports partial shipments)
        3. Set tracking number if provided
        4. Recalculate status and location

        Matches by order_number + size (same pattern as _process_urban_cancellation_update).
        Urban does not reliably map unique_ids across partial shipments, so size is the
        primary matching key.

        Args:
            shipping_data: UrbanOutfittersShippingData object

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            logger.info(
                f"Processing Urban Outfitters shipping update for order {shipping_data.order_number} "
                f"(type: {shipping_data.shipment_type}, tracking: {shipping_data.tracking_number})"
            )

            items_updated = 0

            for item in shipping_data.items:
                # Normalize the size from shipping email for comparison
                normalized_ship_size = self._normalize_size(item.size)

                # Find matching purchase tracker record(s) by order_number + size
                matching_records = self.db.query(PurchaseTracker).join(
                    AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                ).filter(
                    and_(
                        PurchaseTracker.order_number == shipping_data.order_number,
                        or_(
                            AsinBank.size == item.size,
                            AsinBank.size == normalized_ship_size
                        )
                    )
                ).all()

                # If no exact matches, fall back to manual size normalization across all order records
                if not matching_records:
                    all_order_records = self.db.query(PurchaseTracker).join(
                        AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                    ).filter(
                        PurchaseTracker.order_number == shipping_data.order_number
                    ).all()

                    for record in all_order_records:
                        db_size = record.asin_bank_ref.size if record.asin_bank_ref else None
                        if db_size:
                            normalized_db_size = self._normalize_size(db_size)
                            if normalized_db_size == normalized_ship_size:
                                matching_records.append(record)

                if not matching_records:
                    logger.warning(
                        f"No purchase tracker record found for Urban Outfitters shipping: "
                        f"order {shipping_data.order_number}, size {item.size} "
                        f"(normalized: {normalized_ship_size}), unique_id {item.unique_id}"
                    )
                    continue

                # Update each matching record
                for record in matching_records:
                    # Add to shipped_to_pw (cumulative)
                    current_shipped = record.shipped_to_pw or 0
                    record.shipped_to_pw = current_shipped + item.quantity

                    # Set tracking number (if provided)
                    if shipping_data.tracking_number:
                        record.tracking_number = shipping_data.tracking_number

                    # Recalculate status and location
                    self._recalculate_status_and_location(record)

                    logger.info(
                        f"Updated purchase tracker ID {record.id}: "
                        f"order={shipping_data.order_number}, "
                        f"size={item.size} (matched DB size: {record.asin_bank_ref.size if record.asin_bank_ref else 'N/A'}), "
                        f"shipped_to_pw {current_shipped} -> {record.shipped_to_pw}, "
                        f"tracking={shipping_data.tracking_number}"
                    )
                    items_updated += 1

            # Commit changes
            self.db.commit()

            logger.info(f"Successfully updated {items_updated} purchase tracker records for Urban Outfitters shipping")
            return (True, None)

        except Exception as e:
            self.db.rollback()
            error_msg = f"Error processing Urban Outfitters shipping update: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return (False, error_msg)

    def _process_shoepalace_cancellation_update(self, cancellation_data: ShoepalaceCancellationData) -> Tuple[bool, Optional[str]]:
        """
        Process Shoe Palace cancellation update: Deduct quantity from 'final_qty' and update 'cancelled_qty'.
        
        For each item in the cancellation notification:
        1. Find matching purchase tracker record by order number and unique_id (or size as fallback)
        2. Deduct the quantity from 'final_qty'
        3. Add the quantity to 'cancelled_qty' (cumulative)
        
        Note: Order numbers in cancellation emails have SP prefix (e.g., "SP1893166"),
        but order confirmations store them without prefix (e.g., "1893166").
        This method handles both formats.
        
        Args:
            cancellation_data: ShoepalaceCancellationData object
        
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            logger.info(f"Processing Shoe Palace cancellation update for order {cancellation_data.order_number}")
            
            # Normalize order number: remove SP prefix if present for database matching
            # Database stores order numbers without SP prefix (from order confirmation emails)
            order_number = cancellation_data.order_number
            order_number_without_prefix = order_number
            if order_number.upper().startswith('SP'):
                order_number_without_prefix = order_number[2:]  # Remove "SP" prefix
            
            items_updated = 0
            
            for item in cancellation_data.items:
                # Normalize the size from cancellation email for comparison
                normalized_cancel_size = self._normalize_size(item.size)
                
                # Find matching purchase tracker record(s)
                # Match by order_number (try both with and without SP prefix) and unique_id first, then fallback to size matching
                # Use PurchaseTracker.oa_sourcing_id (not AsinBank - AsinBank has no oa_sourcing_id)
                matching_records = self.db.query(PurchaseTracker).join(
                    OASourcing, PurchaseTracker.oa_sourcing_id == OASourcing.id
                ).outerjoin(
                    AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                ).filter(
                    and_(
                        or_(
                            PurchaseTracker.order_number == order_number,  # With SP prefix
                            PurchaseTracker.order_number == order_number_without_prefix  # Without SP prefix
                        ),
                        OASourcing.unique_id == item.unique_id
                    )
                ).all()
                
                # If no matches by unique_id, try matching by size
                if not matching_records:
                    matching_records = self.db.query(PurchaseTracker).join(
                        AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                    ).filter(
                        and_(
                            or_(
                                PurchaseTracker.order_number == order_number,  # With SP prefix
                                PurchaseTracker.order_number == order_number_without_prefix  # Without SP prefix
                            ),
                            or_(
                                AsinBank.size == item.size,  # Exact match
                                AsinBank.size == normalized_cancel_size  # Normalized match
                            )
                        )
                    ).all()
                
                # If still no matches, try to match by normalizing all sizes manually
                if not matching_records:
                    all_order_records = self.db.query(PurchaseTracker).join(
                        AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                    ).filter(
                        or_(
                            PurchaseTracker.order_number == order_number,  # With SP prefix
                            PurchaseTracker.order_number == order_number_without_prefix  # Without SP prefix
                        )
                    ).all()
                    
                    for record in all_order_records:
                        db_size = record.asin_bank_ref.size if record.asin_bank_ref else None
                        if db_size:
                            normalized_db_size = self._normalize_size(db_size)
                            if normalized_db_size == normalized_cancel_size:
                                matching_records.append(record)
                
                if not matching_records:
                    logger.warning(
                        f"No purchase tracker record found for order {cancellation_data.order_number} "
                        f"(tried: {order_number}, {order_number_without_prefix}), "
                        f"unique_id {item.unique_id}, size {item.size} (normalized: {normalized_cancel_size})"
                    )
                    continue
                
                # Update each matching record
                for record in matching_records:
                    # Deduct from final_qty
                    current_final_qty = record.final_qty or 0
                    record.final_qty = max(0, current_final_qty - item.quantity)
                    
                    # Add to cancelled_qty (cumulative)
                    current_cancelled = record.cancelled_qty or 0
                    record.cancelled_qty = current_cancelled + item.quantity
                    
                    # Recalculate status and location
                    self._recalculate_status_and_location(record)
                    
                    logger.info(
                        f"Updated purchase tracker ID {record.id}: "
                        f"order={cancellation_data.order_number}, "
                        f"unique_id={item.unique_id}, "
                        f"size={item.size} (matched DB size: {record.asin_bank_ref.size if record.asin_bank_ref else 'N/A'}), "
                        f"final_qty {current_final_qty} -> {record.final_qty}, "
                        f"cancelled_qty {current_cancelled} -> {record.cancelled_qty}"
                    )
                    items_updated += 1
            
            # Commit changes
            self.db.commit()
            
            logger.info(f"Successfully updated {items_updated} purchase tracker records for cancellation")
            return (True, None)
        
        except Exception as e:
            self.db.rollback()
            error_msg = f"Error processing Shoe Palace cancellation update: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return (False, error_msg)
    
    def _process_orleans_cancellation_update(self, cancellation_data: OrleansCancellationData) -> Tuple[bool, Optional[str]]:
        """
        Process Orleans Shoe Co cancellation update: Deduct quantity from 'final_qty' and update 'cancelled_qty'.
        
        For each item in the cancellation notification:
        1. Find matching purchase tracker record by order number and unique_id (or size as fallback)
        2. Deduct the quantity from 'final_qty'
        3. Add the quantity to 'cancelled_qty' (cumulative)
        
        Args:
            cancellation_data: OrleansCancellationData object
        
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            logger.info(f"Processing Orleans cancellation update for order {cancellation_data.order_number}")
            
            items_updated = 0
            
            for item in cancellation_data.items:
                # Normalize the size from cancellation email for comparison
                normalized_cancel_size = self._normalize_size(item.size)
                
                # Find matching purchase tracker record(s)
                # Match by order_number and unique_id first, then fallback to size matching
                # Use PurchaseTracker.oa_sourcing_id (not AsinBank - AsinBank has no oa_sourcing_id)
                matching_records = self.db.query(PurchaseTracker).join(
                    OASourcing, PurchaseTracker.oa_sourcing_id == OASourcing.id
                ).outerjoin(
                    AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                ).filter(
                    and_(
                        PurchaseTracker.order_number == cancellation_data.order_number,
                        OASourcing.unique_id == item.unique_id
                    )
                ).all()
                
                # If no matches by unique_id, try matching by size
                if not matching_records:
                    matching_records = self.db.query(PurchaseTracker).join(
                        AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                    ).filter(
                        and_(
                            PurchaseTracker.order_number == cancellation_data.order_number,
                            or_(
                                AsinBank.size == item.size,  # Exact match
                                AsinBank.size == normalized_cancel_size  # Normalized match
                            )
                        )
                    ).all()
                
                # If still no matches, try to match by normalizing all sizes manually
                if not matching_records:
                    all_order_records = self.db.query(PurchaseTracker).join(
                        AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                    ).filter(
                        PurchaseTracker.order_number == cancellation_data.order_number
                    ).all()
                    
                    for record in all_order_records:
                        db_size = record.asin_bank_ref.size if record.asin_bank_ref else None
                        if db_size:
                            normalized_db_size = self._normalize_size(db_size)
                            if normalized_db_size == normalized_cancel_size:
                                matching_records.append(record)
                
                if not matching_records:
                    logger.warning(
                        f"No purchase tracker record found for order {cancellation_data.order_number}, "
                        f"unique_id {item.unique_id}, size {item.size} (normalized: {normalized_cancel_size})"
                    )
                    continue
                
                # Update each matching record
                for record in matching_records:
                    # Deduct from final_qty
                    current_final_qty = record.final_qty or 0
                    record.final_qty = max(0, current_final_qty - item.quantity)
                    
                    # Add to cancelled_qty (cumulative)
                    current_cancelled = record.cancelled_qty or 0
                    record.cancelled_qty = current_cancelled + item.quantity
                    
                    # Recalculate status and location
                    self._recalculate_status_and_location(record)
                    
                    logger.info(
                        f"Updated purchase tracker ID {record.id}: "
                        f"order={cancellation_data.order_number}, "
                        f"unique_id={item.unique_id}, "
                        f"size={item.size} (matched DB size: {record.asin_bank_ref.size if record.asin_bank_ref else 'N/A'}), "
                        f"final_qty {current_final_qty} -> {record.final_qty}, "
                        f"cancelled_qty {current_cancelled} -> {record.cancelled_qty}"
                    )
                    items_updated += 1
            
            # Commit changes
            self.db.commit()
            
            logger.info(f"Successfully updated {items_updated} purchase tracker records for cancellation")
            return (True, None)
        
        except Exception as e:
            self.db.rollback()
            error_msg = f"Error processing Orleans cancellation update: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return (False, error_msg)

    def _process_als_shipping_update(self, shipping_data: AlsShippingData) -> Tuple[bool, Optional[str]]:
        """
        Process Al's shipping update: Update shipped_to_pw and tracking.

        Match by order_number + unique_id + size (same pattern as END Clothing).
        """
        try:
            logger.info(f"Processing Al's shipping update for order {shipping_data.order_number}")
            items_updated = 0

            for item in shipping_data.items:
                normalized_size = self._normalize_size(item.size)

                matching_records = self.db.query(PurchaseTracker).join(
                    OASourcing, PurchaseTracker.oa_sourcing_id == OASourcing.id
                ).outerjoin(
                    AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                ).filter(
                    and_(
                        PurchaseTracker.order_number == shipping_data.order_number,
                        OASourcing.unique_id == item.unique_id,
                        or_(
                            AsinBank.size == item.size,
                            AsinBank.size == normalized_size
                        )
                    )
                ).all()

                if not matching_records:
                    all_for_order = self.db.query(PurchaseTracker).join(
                        OASourcing, PurchaseTracker.oa_sourcing_id == OASourcing.id
                    ).outerjoin(
                        AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                    ).filter(
                        and_(
                            PurchaseTracker.order_number == shipping_data.order_number,
                            OASourcing.unique_id == item.unique_id
                        )
                    ).all()
                    for record in all_for_order:
                        db_size = record.asin_bank_ref.size if record.asin_bank_ref else None
                        if db_size and self._normalize_size(db_size) == normalized_size:
                            matching_records.append(record)

                if not matching_records:
                    logger.warning(
                        f"No purchase tracker record found for Al's order {shipping_data.order_number}, "
                        f"unique_id {item.unique_id}, size {item.size}"
                    )
                    continue

                for record in matching_records:
                    current_shipped = record.shipped_to_pw or 0
                    record.shipped_to_pw = current_shipped + item.quantity
                    if not record.tracking and shipping_data.tracking_number:
                        record.tracking = shipping_data.tracking_number
                    self._recalculate_status_and_location(record)
                    logger.info(
                        f"Updated Al's purchase tracker ID {record.id}: "
                        f"order={shipping_data.order_number}, unique_id={item.unique_id}, size={item.size}, "
                        f"shipped_to_pw {current_shipped} -> {record.shipped_to_pw}"
                    )
                    items_updated += 1

            self.db.commit()
            logger.info(f"Successfully updated {items_updated} Al's purchase tracker records")
            return (True, None)

        except Exception as e:
            self.db.rollback()
            error_msg = f"Error processing Al's shipping update: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return (False, error_msg)

    def _process_academy_shipping_update(self, shipping_data: AcademyShippingData) -> Tuple[bool, Optional[str]]:
        """
        Process Academy Sports shipping update: Update shipped_to_pw and tracking.

        Match by order_number + unique_id + size.
        """
        try:
            logger.info(f"Processing Academy shipping update for order {shipping_data.order_number}")
            items_updated = 0

            for item in shipping_data.items:
                normalized_size = self._normalize_size(item.size)

                matching_records = self.db.query(PurchaseTracker).join(
                    OASourcing, PurchaseTracker.oa_sourcing_id == OASourcing.id
                ).outerjoin(
                    AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                ).filter(
                    and_(
                        PurchaseTracker.order_number == shipping_data.order_number,
                        OASourcing.unique_id == item.unique_id,
                        or_(
                            AsinBank.size == item.size,
                            AsinBank.size == normalized_size
                        )
                    )
                ).all()

                if not matching_records:
                    all_for_order = self.db.query(PurchaseTracker).join(
                        OASourcing, PurchaseTracker.oa_sourcing_id == OASourcing.id
                    ).outerjoin(
                        AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                    ).filter(
                        and_(
                            PurchaseTracker.order_number == shipping_data.order_number,
                            OASourcing.unique_id == item.unique_id
                        )
                    ).all()
                    for record in all_for_order:
                        db_size = record.asin_bank_ref.size if record.asin_bank_ref else None
                        if db_size and self._normalize_size(db_size) == normalized_size:
                            matching_records.append(record)

                if not matching_records:
                    logger.warning(
                        f"No purchase tracker record found for Academy order {shipping_data.order_number}, "
                        f"unique_id {item.unique_id}, size {item.size}"
                    )
                    continue

                for record in matching_records:
                    current_shipped = record.shipped_to_pw or 0
                    record.shipped_to_pw = current_shipped + item.quantity
                    if not record.tracking and shipping_data.tracking_number:
                        record.tracking = shipping_data.tracking_number
                    self._recalculate_status_and_location(record)
                    logger.info(
                        f"Updated Academy purchase tracker ID {record.id}: "
                        f"order={shipping_data.order_number}, unique_id={item.unique_id}, size={item.size}, "
                        f"shipped_to_pw {current_shipped} -> {record.shipped_to_pw}"
                    )
                    items_updated += 1

            self.db.commit()
            logger.info(f"Successfully updated {items_updated} Academy purchase tracker records")
            return (True, None)

        except Exception as e:
            self.db.rollback()
            error_msg = f"Error processing Academy shipping update: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return (False, error_msg)

    def _process_scheels_shipping_update(self, shipping_data: SceelsShippingData) -> Tuple[bool, Optional[str]]:
        """Process Scheels shipping update: Update shipped_to_pw. No tracking number available."""
        try:
            logger.info(f"Processing Scheels shipping update for order {shipping_data.order_number}")
            items_updated = 0

            for item in shipping_data.items:
                matching_records = self.db.query(PurchaseTracker).join(
                    OASourcing, PurchaseTracker.oa_sourcing_id == OASourcing.id
                ).filter(
                    and_(
                        PurchaseTracker.order_number == shipping_data.order_number,
                        OASourcing.unique_id == item.unique_id
                    )
                ).all()

                if not matching_records:
                    logger.warning(
                        f"No purchase tracker record found for Scheels order {shipping_data.order_number}, "
                        f"unique_id {item.unique_id}"
                    )
                    continue

                for record in matching_records:
                    current_shipped = record.shipped_to_pw or 0
                    record.shipped_to_pw = current_shipped + item.quantity
                    self._recalculate_status_and_location(record)
                    logger.info(
                        f"Updated Scheels purchase tracker ID {record.id}: "
                        f"order={shipping_data.order_number}, unique_id={item.unique_id}, "
                        f"shipped_to_pw {current_shipped} -> {record.shipped_to_pw}"
                    )
                    items_updated += 1

            self.db.commit()
            logger.info(f"Successfully updated {items_updated} Scheels purchase tracker records")
            return (True, None)

        except Exception as e:
            self.db.rollback()
            error_msg = f"Error processing Scheels shipping update: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return (False, error_msg)

    def _process_als_cancellation_update(self, cancellation_data: AlsCancellationData) -> Tuple[bool, Optional[str]]:
        """
        Process Al's cancellation update: Deduct quantity from 'final_qty' and update 'cancelled_qty'.

        For each item in the cancellation notification:
        1. Find matching purchase tracker record by order number and unique_id (or size as fallback)
        2. Deduct the quantity from 'final_qty'
        3. Add the quantity to 'cancelled_qty' (cumulative)
        """
        try:
            logger.info(f"Processing Al's cancellation update for order {cancellation_data.order_number}")

            items_updated = 0

            for item in cancellation_data.items:
                normalized_cancel_size = self._normalize_size(item.size)

                matching_records = self.db.query(PurchaseTracker).join(
                    OASourcing, PurchaseTracker.oa_sourcing_id == OASourcing.id
                ).outerjoin(
                    AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                ).filter(
                    and_(
                        PurchaseTracker.order_number == cancellation_data.order_number,
                        OASourcing.unique_id == item.unique_id
                    )
                ).all()

                # If no matches by unique_id, try matching by size
                if not matching_records:
                    matching_records = self.db.query(PurchaseTracker).join(
                        AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                    ).filter(
                        and_(
                            PurchaseTracker.order_number == cancellation_data.order_number,
                            or_(
                                AsinBank.size == item.size,
                                AsinBank.size == normalized_cancel_size
                            )
                        )
                    ).all()

                # If still no matches, try to match by normalizing all sizes manually
                if not matching_records:
                    all_order_records = self.db.query(PurchaseTracker).join(
                        AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                    ).filter(
                        PurchaseTracker.order_number == cancellation_data.order_number
                    ).all()

                    for record in all_order_records:
                        db_size = record.asin_bank_ref.size if record.asin_bank_ref else None
                        if db_size:
                            normalized_db_size = self._normalize_size(db_size)
                            if normalized_db_size == normalized_cancel_size:
                                matching_records.append(record)

                if not matching_records:
                    logger.warning(
                        f"No purchase tracker record found for Al's order {cancellation_data.order_number}, "
                        f"unique_id {item.unique_id}, size {item.size} (normalized: {normalized_cancel_size})"
                    )
                    continue

                # Update each matching record
                for record in matching_records:
                    # Deduct from final_qty
                    current_final_qty = record.final_qty or 0
                    record.final_qty = max(0, current_final_qty - item.quantity)

                    # Add to cancelled_qty (cumulative)
                    current_cancelled = record.cancelled_qty or 0
                    record.cancelled_qty = current_cancelled + item.quantity

                    # Recalculate status and location
                    self._recalculate_status_and_location(record)

                    logger.info(
                        f"Updated Al's purchase tracker ID {record.id}: "
                        f"order={cancellation_data.order_number}, "
                        f"unique_id={item.unique_id}, "
                        f"size={item.size}, "
                        f"final_qty {current_final_qty} -> {record.final_qty}, "
                        f"cancelled_qty {current_cancelled} -> {record.cancelled_qty}"
                    )
                    items_updated += 1

            # Commit changes
            self.db.commit()

            logger.info(f"Successfully updated {items_updated} Al's purchase tracker records for cancellation")
            return (True, None)

        except Exception as e:
            self.db.rollback()
            error_msg = f"Error processing Al's cancellation update: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return (False, error_msg)

    def _process_finishline_shipping_update(self, shipping_data: FinishLineShippingData) -> Tuple[bool, Optional[str]]:
        """
        Process Finish Line shipping/update: shipping items (shipped_to_pw) + optional cancellation items.

        For partial update emails, processes both shipping and cancellation in one pass.

        IMPORTANT — Cumulative emails (Finish Line + JD Sports only):
        These "scoop" emails show the CUMULATIVE order state — every email lists ALL
        items that have shipped so far, not just newly shipped items.  Therefore
        shipped_to_pw is set via MAX (not ADD) to avoid double-counting items that
        appeared in a previous email.  This differs from all other retailers (Foot Locker,
        Champs, etc.) whose shipping emails only contain items in the current package
        (incremental).  Keep this MAX logic exclusive to Finish Line and JD Sports.
        """
        try:
            # Process shipping items first
            for item in shipping_data.items:
                normalized_size = self._normalize_size(item.size)
                matching_records = self.db.query(PurchaseTracker).join(
                    OASourcing, PurchaseTracker.oa_sourcing_id == OASourcing.id
                ).outerjoin(
                    AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                ).filter(
                    and_(
                        PurchaseTracker.order_number == shipping_data.order_number,
                        OASourcing.unique_id == item.unique_id,
                        or_(
                            AsinBank.size == item.size,
                            AsinBank.size == normalized_size
                        )
                    )
                ).all()

                if not matching_records:
                    all_for_order = self.db.query(PurchaseTracker).join(
                        OASourcing, PurchaseTracker.oa_sourcing_id == OASourcing.id
                    ).outerjoin(
                        AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                    ).filter(
                        and_(
                            PurchaseTracker.order_number == shipping_data.order_number,
                            OASourcing.unique_id == item.unique_id
                        )
                    ).all()
                    for record in all_for_order:
                        db_size = record.asin_bank_ref.size if record.asin_bank_ref else None
                        if db_size and self._normalize_size(db_size) == normalized_size:
                            matching_records.append(record)

                for record in matching_records:
                    current_shipped = record.shipped_to_pw or 0
                    # Use MAX: FNL scoop emails report cumulative shipped count, not incremental
                    record.shipped_to_pw = max(current_shipped, item.quantity)
                    if not record.tracking and item.tracking:
                        record.tracking = item.tracking
                    self._recalculate_status_and_location(record)
            
            # Process cancellation items if present (partial update email)
            if shipping_data.cancellation_items:
                cancel_data = FinishLineCancellationData(
                    order_number=shipping_data.order_number,
                    items=shipping_data.cancellation_items,
                    is_full_cancellation=False
                )
                success, error = self._process_finishline_cancellation_update(cancel_data)
                if not success:
                    return (False, error)
            
            self.db.commit()
            logger.info(f"Processed Finish Line shipping update for order {shipping_data.order_number}")
            return (True, None)
        except Exception as e:
            self.db.rollback()
            error_msg = f"Error processing Finish Line shipping update: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return (False, error_msg)

    def _process_revolve_shipping_update(self, shipping_data: RevolveShippingData) -> Tuple[bool, Optional[str]]:
        """
        Process Revolve shipping update (full or partial): Update shipped_to_pw and tracking.
        
        Items are consolidated by unique_id + size (same as order confirmation).
        Match by order_number + unique_id + size, add quantity to shipped_to_pw.
        
        Args:
            shipping_data: RevolveShippingData object
        
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            logger.info(f"Processing Revolve shipping update for order {shipping_data.order_number}")
            items_updated = 0
            
            for item in shipping_data.items:
                normalized_size = self._normalize_size(item.size)
                
                matching_records = self.db.query(PurchaseTracker).join(
                    OASourcing, PurchaseTracker.oa_sourcing_id == OASourcing.id
                ).outerjoin(
                    AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                ).filter(
                    and_(
                        PurchaseTracker.order_number == shipping_data.order_number,
                        OASourcing.unique_id == item.unique_id,
                        or_(
                            AsinBank.size == item.size,
                            AsinBank.size == normalized_size
                        )
                    )
                ).all()
                
                if not matching_records:
                    all_for_order = self.db.query(PurchaseTracker).join(
                        OASourcing, PurchaseTracker.oa_sourcing_id == OASourcing.id
                    ).outerjoin(
                        AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                    ).filter(
                        and_(
                            PurchaseTracker.order_number == shipping_data.order_number,
                            OASourcing.unique_id == item.unique_id
                        )
                    ).all()
                    for record in all_for_order:
                        db_size = record.asin_bank_ref.size if record.asin_bank_ref else None
                        if db_size and self._normalize_size(db_size) == normalized_size:
                            matching_records.append(record)
                
                if not matching_records:
                    logger.warning(
                        f"No purchase tracker record found for order {shipping_data.order_number}, "
                        f"unique_id {item.unique_id}, size {item.size}"
                    )
                    continue
                
                for record in matching_records:
                    current_shipped = record.shipped_to_pw or 0
                    record.shipped_to_pw = current_shipped + item.quantity
                    if not record.tracking and shipping_data.tracking_number:
                        record.tracking = shipping_data.tracking_number
                    self._recalculate_status_and_location(record)
                    logger.info(
                        f"Updated Revolve purchase tracker ID {record.id}: "
                        f"order={shipping_data.order_number}, unique_id={item.unique_id}, size={item.size}, "
                        f"shipped_to_pw {current_shipped} -> {record.shipped_to_pw}"
                    )
                    items_updated += 1
            
            self.db.commit()
            logger.info(f"Successfully updated {items_updated} Revolve purchase tracker records")
            return (True, None)
        
        except Exception as e:
            self.db.rollback()
            error_msg = f"Error processing Revolve shipping update: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return (False, error_msg)

    def _process_asos_shipping_update(self, shipping_data: ASOSShippingData) -> Tuple[bool, Optional[str]]:
        """
        Process ASOS shipping update: Update shipped_to_pw and tracking.
        
        Same unique_id logic as order confirmation (extracted from image URL).
        Match by order_number + unique_id + size, add quantity to shipped_to_pw.
        
        Args:
            shipping_data: ASOSShippingData object
        
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            logger.info(f"Processing ASOS shipping update for order {shipping_data.order_number}")
            items_updated = 0
            
            for item in shipping_data.items:
                normalized_size = self._normalize_size(item.size)
                
                matching_records = self.db.query(PurchaseTracker).join(
                    OASourcing, PurchaseTracker.oa_sourcing_id == OASourcing.id
                ).outerjoin(
                    AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                ).filter(
                    and_(
                        PurchaseTracker.order_number == shipping_data.order_number,
                        OASourcing.unique_id == item.unique_id,
                        or_(
                            AsinBank.size == item.size,
                            AsinBank.size == normalized_size
                        )
                    )
                ).all()
                
                if not matching_records:
                    all_for_order = self.db.query(PurchaseTracker).join(
                        OASourcing, PurchaseTracker.oa_sourcing_id == OASourcing.id
                    ).outerjoin(
                        AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                    ).filter(
                        and_(
                            PurchaseTracker.order_number == shipping_data.order_number,
                            OASourcing.unique_id == item.unique_id
                        )
                    ).all()
                    for record in all_for_order:
                        db_size = record.asin_bank_ref.size if record.asin_bank_ref else None
                        if db_size and self._normalize_size(db_size) == normalized_size:
                            matching_records.append(record)
                
                if not matching_records:
                    logger.warning(
                        f"No purchase tracker record found for order {shipping_data.order_number}, "
                        f"unique_id {item.unique_id}, size {item.size}"
                    )
                    continue
                
                for record in matching_records:
                    current_shipped = record.shipped_to_pw or 0
                    record.shipped_to_pw = current_shipped + item.quantity
                    if not record.tracking and shipping_data.tracking_number:
                        record.tracking = shipping_data.tracking_number
                    self._recalculate_status_and_location(record)
                    logger.info(
                        f"Updated ASOS purchase tracker ID {record.id}: "
                        f"order={shipping_data.order_number}, unique_id={item.unique_id}, size={item.size}, "
                        f"shipped_to_pw {current_shipped} -> {record.shipped_to_pw}"
                    )
                    items_updated += 1
            
            self.db.commit()
            logger.info(f"Successfully updated {items_updated} ASOS purchase tracker records")
            return (True, None)
        
        except Exception as e:
            self.db.rollback()
            error_msg = f"Error processing ASOS shipping update: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return (False, error_msg)

    def _process_snipes_shipping_update(self, shipping_data: SnipesShippingData) -> Tuple[bool, Optional[str]]:
        """
        Process Snipes shipping update: Update shipped_to_pw and tracking.
        
        Same logic as Footlocker/ASOS - match by order_number + unique_id + size.
        unique_id is style code (e.g. fj4146-100), identical to order confirmation.
        """
        try:
            logger.info(f"Processing Snipes shipping update for order {shipping_data.order_number}")
            items_updated = 0
            
            for item in shipping_data.items:
                normalized_size = self._normalize_size(item.size)
                
                matching_records = self.db.query(PurchaseTracker).join(
                    OASourcing, PurchaseTracker.oa_sourcing_id == OASourcing.id
                ).outerjoin(
                    AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                ).filter(
                    and_(
                        PurchaseTracker.order_number == shipping_data.order_number,
                        OASourcing.unique_id == item.unique_id,
                        or_(
                            AsinBank.size == item.size,
                            AsinBank.size == normalized_size
                        )
                    )
                ).all()
                
                if not matching_records:
                    all_for_order = self.db.query(PurchaseTracker).join(
                        OASourcing, PurchaseTracker.oa_sourcing_id == OASourcing.id
                    ).outerjoin(
                        AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                    ).filter(
                        and_(
                            PurchaseTracker.order_number == shipping_data.order_number,
                            OASourcing.unique_id == item.unique_id
                        )
                    ).all()
                    for record in all_for_order:
                        db_size = record.asin_bank_ref.size if record.asin_bank_ref else None
                        if db_size and self._normalize_size(db_size) == normalized_size:
                            matching_records.append(record)
                
                if not matching_records:
                    logger.warning(
                        f"No purchase tracker record found for order {shipping_data.order_number}, "
                        f"unique_id {item.unique_id}, size {item.size}"
                    )
                    continue
                
                for record in matching_records:
                    current_shipped = record.shipped_to_pw or 0
                    record.shipped_to_pw = current_shipped + item.quantity
                    if not record.tracking and shipping_data.tracking_number:
                        record.tracking = shipping_data.tracking_number
                    self._recalculate_status_and_location(record)
                    logger.info(
                        f"Updated Snipes purchase tracker ID {record.id}: "
                        f"order={shipping_data.order_number}, unique_id={item.unique_id}, size={item.size}, "
                        f"shipped_to_pw {current_shipped} -> {record.shipped_to_pw}"
                    )
                    items_updated += 1
            
            self.db.commit()
            logger.info(f"Successfully updated {items_updated} Snipes purchase tracker records")
            return (True, None)
        
        except Exception as e:
            self.db.rollback()
            error_msg = f"Error processing Snipes shipping update: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return (False, error_msg)

    def _process_shoepalace_shipping_update(self, shipping_data: ShoepalaceShippingData) -> Tuple[bool, Optional[str]]:
        """
        Process Shoe Palace shipping update: Update shipped_to_pw and tracking.
        
        Same logic as Footlocker/Snipes - match by order_number + unique_id + size.
        unique_id is slugified product name (e.g. pegasus-41-road-womens-running-shoes-photon-dust-metallic-pewter-sail-echo-pink),
        identical to order confirmation.
        """
        try:
            logger.info(f"Processing Shoe Palace shipping update for order {shipping_data.order_number}")
            items_updated = 0
            
            for item in shipping_data.items:
                normalized_size = self._normalize_size(item.size)
                
                matching_records = self.db.query(PurchaseTracker).join(
                    OASourcing, PurchaseTracker.oa_sourcing_id == OASourcing.id
                ).outerjoin(
                    AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                ).filter(
                    and_(
                        PurchaseTracker.order_number == shipping_data.order_number,
                        OASourcing.unique_id == item.unique_id,
                        or_(
                            AsinBank.size == item.size,
                            AsinBank.size == normalized_size
                        )
                    )
                ).all()
                
                if not matching_records:
                    all_for_order = self.db.query(PurchaseTracker).join(
                        OASourcing, PurchaseTracker.oa_sourcing_id == OASourcing.id
                    ).outerjoin(
                        AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                    ).filter(
                        and_(
                            PurchaseTracker.order_number == shipping_data.order_number,
                            OASourcing.unique_id == item.unique_id
                        )
                    ).all()
                    for record in all_for_order:
                        db_size = record.asin_bank_ref.size if record.asin_bank_ref else None
                        if db_size and self._normalize_size(db_size) == normalized_size:
                            matching_records.append(record)
                
                if not matching_records:
                    logger.warning(
                        f"No purchase tracker record found for order {shipping_data.order_number}, "
                        f"unique_id {item.unique_id}, size {item.size}"
                    )
                    continue
                
                for record in matching_records:
                    current_shipped = record.shipped_to_pw or 0
                    record.shipped_to_pw = current_shipped + item.quantity
                    if not record.tracking and shipping_data.tracking_number:
                        record.tracking = shipping_data.tracking_number
                    self._recalculate_status_and_location(record)
                    logger.info(
                        f"Updated Shoe Palace purchase tracker ID {record.id}: "
                        f"order={shipping_data.order_number}, unique_id={item.unique_id}, size={item.size}, "
                        f"shipped_to_pw {current_shipped} -> {record.shipped_to_pw}"
                    )
                    items_updated += 1
            
            self.db.commit()
            logger.info(f"Successfully updated {items_updated} Shoe Palace purchase tracker records")
            return (True, None)
        
        except Exception as e:
            self.db.rollback()
            error_msg = f"Error processing Shoe Palace shipping update: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return (False, error_msg)

    def _process_endclothing_shipping_update(self, shipping_data: ENDClothingShippingData) -> Tuple[bool, Optional[str]]:
        """
        Process END Clothing shipping update: Update shipped_to_pw and tracking.
        
        Same logic as Footlocker/Snipes - match by order_number + unique_id + size.
        unique_id from image URL (e.g. fj2028-101), size is UK->US converted via formula.
        """
        try:
            logger.info(f"Processing END Clothing shipping update for order {shipping_data.order_number}")
            items_updated = 0
            
            for item in shipping_data.items:
                normalized_size = self._normalize_size(item.size)
                
                matching_records = self.db.query(PurchaseTracker).join(
                    OASourcing, PurchaseTracker.oa_sourcing_id == OASourcing.id
                ).outerjoin(
                    AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                ).filter(
                    and_(
                        PurchaseTracker.order_number == shipping_data.order_number,
                        OASourcing.unique_id == item.unique_id,
                        or_(
                            AsinBank.size == item.size,
                            AsinBank.size == normalized_size
                        )
                    )
                ).all()
                
                if not matching_records:
                    all_for_order = self.db.query(PurchaseTracker).join(
                        OASourcing, PurchaseTracker.oa_sourcing_id == OASourcing.id
                    ).outerjoin(
                        AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                    ).filter(
                        and_(
                            PurchaseTracker.order_number == shipping_data.order_number,
                            OASourcing.unique_id == item.unique_id
                        )
                    ).all()
                    for record in all_for_order:
                        db_size = record.asin_bank_ref.size if record.asin_bank_ref else None
                        if db_size and self._normalize_size(db_size) == normalized_size:
                            matching_records.append(record)
                
                if not matching_records:
                    logger.warning(
                        f"No purchase tracker record found for order {shipping_data.order_number}, "
                        f"unique_id {item.unique_id}, size {item.size}"
                    )
                    continue
                
                for record in matching_records:
                    current_shipped = record.shipped_to_pw or 0
                    record.shipped_to_pw = current_shipped + item.quantity
                    if not record.tracking and shipping_data.tracking_number:
                        record.tracking = shipping_data.tracking_number
                    self._recalculate_status_and_location(record)
                    logger.info(
                        f"Updated END Clothing purchase tracker ID {record.id}: "
                        f"order={shipping_data.order_number}, unique_id={item.unique_id}, size={item.size}, "
                        f"shipped_to_pw {current_shipped} -> {record.shipped_to_pw}"
                    )
                    items_updated += 1
            
            self.db.commit()
            logger.info(f"Successfully updated {items_updated} END Clothing purchase tracker records")
            return (True, None)
        
        except Exception as e:
            self.db.rollback()
            error_msg = f"Error processing END Clothing shipping update: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return (False, error_msg)

    def _process_shopwss_shipping_update(self, shipping_data: ShopWSSShippingData) -> Tuple[bool, Optional[str]]:
        """
        Process ShopWSS shipping update: Update shipped_to_pw and tracking.
        
        ShopWSS shipping email has NO size - match by order_number + unique_id only.
        Size comes from purchase record saved at order confirmation.
        When exactly 1 match: update it. When multiple (same product, different sizes):
        update the record with most unshipped qty remaining.
        """
        try:
            logger.info(f"Processing ShopWSS shipping update for order {shipping_data.order_number}")
            items_updated = 0
            
            for item in shipping_data.items:
                # Match by order_number + unique_id only (no size in email)
                matching_records = self.db.query(PurchaseTracker).join(
                    OASourcing, PurchaseTracker.oa_sourcing_id == OASourcing.id
                ).filter(
                    and_(
                        PurchaseTracker.order_number == shipping_data.order_number,
                        OASourcing.unique_id == item.unique_id
                    )
                ).all()
                
                if not matching_records:
                    logger.warning(
                        f"No purchase tracker record found for order {shipping_data.order_number}, "
                        f"unique_id {item.unique_id}"
                    )
                    continue
                
                # If multiple (same product, different sizes): pick record with most unshipped qty
                if len(matching_records) > 1:
                    def unshipped_qty(r):
                        fq = r.final_qty or 0
                        sp = r.shipped_to_pw or 0
                        return max(0, fq - sp)
                    matching_records = sorted(
                        matching_records,
                        key=unshipped_qty,
                        reverse=True
                    )
                    # Update the one with most remaining (or first if tied)
                    target = matching_records[0]
                    if unshipped_qty(target) <= 0:
                        logger.warning(
                            f"All records for order {shipping_data.order_number}, unique_id {item.unique_id} "
                            "already fully shipped - skipping"
                        )
                        continue
                    matching_records = [target]
                
                for record in matching_records:
                    current_shipped = record.shipped_to_pw or 0
                    record.shipped_to_pw = current_shipped + item.quantity
                    if not record.tracking and shipping_data.tracking_number:
                        record.tracking = shipping_data.tracking_number
                    self._recalculate_status_and_location(record)
                    db_size = record.asin_bank_ref.size if record.asin_bank_ref else None
                    logger.info(
                        f"Updated ShopWSS purchase tracker ID {record.id}: "
                        f"order={shipping_data.order_number}, unique_id={item.unique_id}, size={db_size}, "
                        f"shipped_to_pw {current_shipped} -> {record.shipped_to_pw}"
                    )
                    items_updated += 1
            
            self.db.commit()
            logger.info(f"Successfully updated {items_updated} ShopWSS purchase tracker records")
            return (True, None)
        
        except Exception as e:
            self.db.rollback()
            error_msg = f"Error processing ShopWSS shipping update: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return (False, error_msg)

    def _process_shopwss_cancellation_update(self, cancellation_data: ShopWSSCancellationData) -> Tuple[bool, Optional[str]]:
        """
        Process ShopWSS cancellation: full or partial.
        items=[] means cancel ALL purchase tracker records for order_number.
        items non-empty: match by order_number + unique_id + size, deduct from final_qty.
        """
        try:
            if not cancellation_data.items:
                # Full cancellation - cancel all for order
                logger.info(f"Processing ShopWSS full cancellation for order {cancellation_data.order_number}")
                records = self.db.query(PurchaseTracker).filter(
                    PurchaseTracker.order_number == cancellation_data.order_number
                ).all()
                if not records:
                    logger.warning(f"No purchase tracker records found for order {cancellation_data.order_number}")
                    self.db.commit()
                    return (True, None)
                items_updated = 0
                for record in records:
                    current_final = record.final_qty or 0
                    record.final_qty = 0
                    record.cancelled_qty = (record.cancelled_qty or 0) + current_final
                    self._recalculate_status_and_location(record)
                    logger.info(
                        f"Cancelled ShopWSS purchase tracker ID {record.id}: order={cancellation_data.order_number}, "
                        f"final_qty {current_final} -> 0, cancelled_qty += {current_final}"
                    )
                    items_updated += 1
                self.db.commit()
                logger.info(f"Successfully cancelled {items_updated} ShopWSS purchase tracker records")
                return (True, None)

            # Partial cancellation - match by order_number + unique_id + size
            logger.info(f"Processing ShopWSS partial cancellation for order {cancellation_data.order_number}, {len(cancellation_data.items)} items")
            items_updated = 0
            for item in cancellation_data.items:
                cancel_qty = max(0, item.quantity or 0)
                if cancel_qty <= 0:
                    continue
                normalized_size = self._normalize_size(item.size)
                matching_records = self.db.query(PurchaseTracker).join(
                    OASourcing, PurchaseTracker.oa_sourcing_id == OASourcing.id
                ).outerjoin(
                    AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                ).filter(
                    and_(
                        PurchaseTracker.order_number == cancellation_data.order_number,
                        OASourcing.unique_id == item.unique_id,
                        or_(
                            AsinBank.size == item.size,
                            AsinBank.size == normalized_size
                        )
                    )
                ).all()
                if not matching_records:
                    all_for_order = self.db.query(PurchaseTracker).join(
                        OASourcing, PurchaseTracker.oa_sourcing_id == OASourcing.id
                    ).outerjoin(
                        AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                    ).filter(
                        and_(
                            PurchaseTracker.order_number == cancellation_data.order_number,
                            OASourcing.unique_id == item.unique_id
                        )
                    ).all()
                    for record in all_for_order:
                        db_size = record.asin_bank_ref.size if record.asin_bank_ref else None
                        if db_size and self._normalize_size(db_size) == normalized_size:
                            matching_records.append(record)
                if not matching_records:
                    logger.warning(
                        f"No purchase tracker record for order {cancellation_data.order_number}, "
                        f"unique_id={item.unique_id}, size={item.size}"
                    )
                    continue
                for record in matching_records:
                    current_final = record.final_qty or 0
                    og_qty = max(0, record.og_qty or 0)
                    effective_cancel = min(cancel_qty, current_final)
                    record.final_qty = max(0, current_final - effective_cancel)
                    record.cancelled_qty = min(og_qty, (record.cancelled_qty or 0) + effective_cancel)
                    self._recalculate_status_and_location(record)
                    logger.info(
                        f"Updated ShopWSS partial cancel ID {record.id}: order={cancellation_data.order_number}, "
                        f"unique_id={item.unique_id}, size={item.size}, final_qty {current_final} -> {record.final_qty}"
                    )
                    items_updated += 1
            self.db.commit()
            logger.info(f"Successfully updated {items_updated} ShopWSS purchase tracker records (partial cancellation)")
            return (True, None)
        except Exception as e:
            self.db.rollback()
            error_msg = f"Error processing ShopWSS cancellation: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return (False, error_msg)

    def _process_snipes_cancellation_update(self, cancellation_data: SnipesCancellationData) -> Tuple[bool, Optional[str]]:
        """
        Process Snipes cancellation update: Deduct from final_qty, add to cancelled_qty.
        
        Partial: match by order_number + unique_id + size.
        Full (items=[]): cancel ALL purchase tracker records for order_number.
        """
        try:
            logger.info(f"Processing Snipes cancellation update for order {cancellation_data.order_number}")
            items_updated = 0

            if not cancellation_data.items:
                # Full cancellation - cancel all for order (like ShopWSS)
                records = self.db.query(PurchaseTracker).filter(
                    PurchaseTracker.order_number == cancellation_data.order_number
                ).all()
                if not records:
                    logger.warning(f"No purchase tracker records found for order {cancellation_data.order_number}")
                    self.db.commit()
                    return (True, None)
                for record in records:
                    current_final = record.final_qty or 0
                    record.final_qty = 0
                    record.cancelled_qty = (record.cancelled_qty or 0) + current_final
                    self._recalculate_status_and_location(record)
                    logger.info(
                        f"Cancelled Snipes purchase tracker ID {record.id}: order={cancellation_data.order_number}, "
                        f"final_qty {current_final} -> 0, cancelled_qty += {current_final}"
                    )
                    items_updated += 1
                self.db.commit()
                logger.info(f"Successfully cancelled {items_updated} Snipes purchase tracker records (full cancellation)")
                return (True, None)
            
            for item in cancellation_data.items:
                normalized_size = self._normalize_size(item.size)
                
                matching_records = self.db.query(PurchaseTracker).join(
                    OASourcing, PurchaseTracker.oa_sourcing_id == OASourcing.id
                ).outerjoin(
                    AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                ).filter(
                    and_(
                        PurchaseTracker.order_number == cancellation_data.order_number,
                        OASourcing.unique_id == item.unique_id,
                        or_(
                            AsinBank.size == item.size,
                            AsinBank.size == normalized_size
                        )
                    )
                ).all()
                
                if not matching_records:
                    all_for_order = self.db.query(PurchaseTracker).join(
                        OASourcing, PurchaseTracker.oa_sourcing_id == OASourcing.id
                    ).outerjoin(
                        AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                    ).filter(
                        and_(
                            PurchaseTracker.order_number == cancellation_data.order_number,
                            OASourcing.unique_id == item.unique_id
                        )
                    ).all()
                    for record in all_for_order:
                        db_size = record.asin_bank_ref.size if record.asin_bank_ref else None
                        if db_size and self._normalize_size(db_size) == normalized_size:
                            matching_records.append(record)
                
                if not matching_records:
                    logger.warning(
                        f"No purchase tracker record found for order {cancellation_data.order_number}, "
                        f"unique_id {item.unique_id}, size {item.size}"
                    )
                    continue
                
                for record in matching_records:
                    current_final = record.final_qty or 0
                    record.final_qty = max(0, current_final - item.quantity)
                    current_cancelled = record.cancelled_qty or 0
                    record.cancelled_qty = current_cancelled + item.quantity
                    self._recalculate_status_and_location(record)
                    logger.info(
                        f"Updated Snipes cancellation ID {record.id}: "
                        f"order={cancellation_data.order_number}, unique_id={item.unique_id}, size={item.size}, "
                        f"final_qty {current_final} -> {record.final_qty}, cancelled_qty {current_cancelled} -> {record.cancelled_qty}"
                    )
                    items_updated += 1
            
            self.db.commit()
            logger.info(f"Successfully updated {items_updated} Snipes cancellation records")
            return (True, None)
        
        except Exception as e:
            self.db.rollback()
            error_msg = f"Error processing Snipes cancellation update: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return (False, error_msg)

    def _process_revolve_cancellation_update(self, cancellation_data: RevolveCancellationData) -> Tuple[bool, Optional[str]]:
        """
        Process Revolve cancellation update: Deduct quantity from 'final_qty' and update 'cancelled_qty'.
        
        Match by order_number + unique_id + size (same as Footlocker).
        Items are consolidated by unique_id + size.
        
        Args:
            cancellation_data: RevolveCancellationData object
        
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            logger.info(f"Processing Revolve cancellation update for order {cancellation_data.order_number}")
            items_updated = 0
            
            for item in cancellation_data.items:
                normalized_size = self._normalize_size(item.size)
                
                matching_records = self.db.query(PurchaseTracker).join(
                    OASourcing, PurchaseTracker.oa_sourcing_id == OASourcing.id
                ).outerjoin(
                    AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                ).filter(
                    and_(
                        PurchaseTracker.order_number == cancellation_data.order_number,
                        OASourcing.unique_id == item.unique_id,
                        or_(
                            AsinBank.size == item.size,
                            AsinBank.size == normalized_size
                        )
                    )
                ).all()
                
                if not matching_records:
                    all_for_order = self.db.query(PurchaseTracker).join(
                        OASourcing, PurchaseTracker.oa_sourcing_id == OASourcing.id
                    ).outerjoin(
                        AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                    ).filter(
                        and_(
                            PurchaseTracker.order_number == cancellation_data.order_number,
                            OASourcing.unique_id == item.unique_id
                        )
                    ).all()
                    for record in all_for_order:
                        db_size = record.asin_bank_ref.size if record.asin_bank_ref else None
                        if db_size and self._normalize_size(db_size) == normalized_size:
                            matching_records.append(record)
                
                if not matching_records:
                    logger.warning(
                        f"No purchase tracker record found for order {cancellation_data.order_number}, "
                        f"unique_id {item.unique_id}, size {item.size}"
                    )
                    continue
                
                cancel_qty = item.quantity if item.quantity > 0 else 1  # Qty 0 = treat as 1 (like Finish Line)
                for record in matching_records:
                    current_final = record.final_qty or 0
                    effective = min(cancel_qty, current_final)  # Don't deduct more than current
                    record.final_qty = max(0, current_final - effective)
                    current_cancelled = record.cancelled_qty or 0
                    record.cancelled_qty = current_cancelled + effective
                    self._recalculate_status_and_location(record)
                    logger.info(
                        f"Updated Revolve cancellation ID {record.id}: "
                        f"order={cancellation_data.order_number}, unique_id={item.unique_id}, size={item.size}, "
                        f"final_qty {current_final} -> {record.final_qty}, cancelled_qty {current_cancelled} -> {record.cancelled_qty}"
                    )
                    items_updated += 1
            
            self.db.commit()
            logger.info(f"Successfully updated {items_updated} Revolve purchase tracker records for cancellation")
            return (True, None)
        
        except Exception as e:
            self.db.rollback()
            error_msg = f"Error processing Revolve cancellation update: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return (False, error_msg)
    
    def _process_finishline_cancellation_update(self, cancellation_data: FinishLineCancellationData) -> Tuple[bool, Optional[str]]:
        """
        Process Finish Line cancellation update: Deduct quantity from 'final_qty' and update 'cancelled_qty'.
        
        Full cancellation (is_full_cancellation=True):
        - All items in the order are cancelled: final_qty=0, cancelled_qty=og_qty for each record.
        
        Partial cancellation:
        - Sum cancelled quantities by (unique_id, size) - supports multiple emails for same order.
        - For each item: deduct from final_qty, add to cancelled_qty (cumulative across emails).
        - Quantity 0 in email = treat as 1 cancelled unit.
        
        Args:
            cancellation_data: FinishLineCancellationData object
        
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            logger.info(f"Processing Finish Line cancellation update for order {cancellation_data.order_number} (full={cancellation_data.is_full_cancellation})")
            
            items_updated = 0
            
            if cancellation_data.is_full_cancellation:
                # Full order cancellation: set final_qty=0, cancelled_qty=og_qty for ALL order items
                all_records = self.db.query(PurchaseTracker).outerjoin(
                    AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                ).filter(PurchaseTracker.order_number == cancellation_data.order_number).all()
                
                for record in all_records:
                    og_qty = max(0, record.og_qty or 0)
                    record.final_qty = 0
                    record.cancelled_qty = og_qty
                    self._recalculate_status_and_location(record)
                    items_updated += 1
                    logger.info(
                        f"Full cancellation: Updated purchase tracker ID {record.id}: "
                        f"order={cancellation_data.order_number}, "
                        f"final_qty -> 0, cancelled_qty -> {og_qty}"
                    )
                self.db.commit()
                logger.info(f"Successfully updated {items_updated} purchase tracker records for Finish Line full cancellation")
                return (True, None)
            
            # Finish Line partial: each email shows CUMULATIVE cancelled state. Sum by (unique_id, size).
            cancel_totals: dict = {}
            for item in cancellation_data.items:
                key = (item.unique_id, self._normalize_size(item.size))
                cancel_totals[key] = cancel_totals.get(key, 0) + max(0, item.quantity or 0)
            
            for (item_uid, item_size), total_cancelled in cancel_totals.items():
                if total_cancelled <= 0:
                    continue
                normalized_cancel_size = self._normalize_size(item_size)
                
                # Find matching purchase tracker record(s)
                matching_records = self.db.query(PurchaseTracker).join(
                    OASourcing, PurchaseTracker.oa_sourcing_id == OASourcing.id
                ).outerjoin(
                    AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                ).filter(
                    and_(
                        PurchaseTracker.order_number == cancellation_data.order_number,
                        OASourcing.unique_id == item_uid
                    )
                ).all()
                
                if not matching_records:
                    matching_records = self.db.query(PurchaseTracker).join(
                        AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                    ).filter(
                        and_(
                            PurchaseTracker.order_number == cancellation_data.order_number,
                            or_(
                                AsinBank.size == item_size,
                                AsinBank.size == normalized_cancel_size
                            )
                        )
                    ).all()
                
                if not matching_records:
                    all_order_records = self.db.query(PurchaseTracker).join(
                        AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                    ).filter(
                        PurchaseTracker.order_number == cancellation_data.order_number
                    ).all()
                    for record in all_order_records:
                        db_size = record.asin_bank_ref.size if record.asin_bank_ref else None
                        if db_size and self._normalize_size(db_size) == normalized_cancel_size:
                            matching_records.append(record)
                
                if not matching_records:
                    logger.warning(
                        f"No purchase tracker record found for order {cancellation_data.order_number}, "
                        f"unique_id {item_uid}, size {item_size} (normalized: {normalized_cancel_size})"
                    )
                    continue
                
                # Each email shows cumulative state: SET cancelled_qty = total from email
                # Use max() to handle out-of-order email delivery
                for record in matching_records:
                    og_qty = max(0, record.og_qty or 0)
                    current_cancelled = record.cancelled_qty or 0
                    # Email shows cumulative cancelled; take max for out-of-order safety
                    new_cancelled = min(og_qty, max(current_cancelled, total_cancelled))
                    record.cancelled_qty = new_cancelled
                    record.final_qty = max(0, og_qty - new_cancelled)
                    self._recalculate_status_and_location(record)
                    logger.info(
                        f"Updated purchase tracker ID {record.id}: order={cancellation_data.order_number}, "
                        f"unique_id={item_uid}, size={item_size} (matched: {record.asin_bank_ref.size if record.asin_bank_ref else 'N/A'}), "
                        f"final_qty -> {record.final_qty}, cancelled_qty -> {record.cancelled_qty} (total from email: {total_cancelled})"
                    )
                    items_updated += 1
            
            # Commit changes
            self.db.commit()
            
            logger.info(f"Successfully updated {items_updated} purchase tracker records for Finish Line cancellation")
            return (True, None)
        
        except Exception as e:
            self.db.rollback()
            error_msg = f"Error processing Finish Line cancellation update: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return (False, error_msg)
    
    def _add_processed_label(self, message_id: str, email_type: str = 'shipping') -> None:
        """Add type-specific Processed label and remove Error/Manual-Review if present.
        
        Args:
            message_id: Gmail message ID
            email_type: 'shipping' or 'cancellation'
        """
        if email_type == 'cancellation':
            label = self.cancel_processed_label
            error_label = self.cancel_error_label
            manual_label = self.cancel_manual_review_label
            label_name = self.CANCEL_PROCESSED_LABEL
        else:
            label = self.shipping_processed_label
            error_label = self.shipping_error_label
            manual_label = self.shipping_manual_review_label
            label_name = self.SHIPPING_PROCESSED_LABEL
        try:
            self.gmail_service.add_label_to_message(message_id, label['id'])
            logger.debug(f"Added {label_name} label to message {message_id}")
            # Remove error/manual-review labels if present
            if error_label:
                self.gmail_service.remove_label_from_message(message_id, error_label['id'])
            if manual_label:
                self.gmail_service.remove_label_from_message(message_id, manual_label['id'])
        except Exception as e:
            logger.error(f"Failed to add processed label to message {message_id}: {e}")
    
    def _add_error_label(self, message_id: str, email_type: str = 'shipping') -> None:
        """Add type-specific Error label.
        
        Args:
            message_id: Gmail message ID
            email_type: 'shipping' or 'cancellation'
        """
        if email_type == 'cancellation':
            label = self.cancel_error_label
            label_name = self.CANCEL_ERROR_LABEL
        else:
            label = self.shipping_error_label
            label_name = self.SHIPPING_ERROR_LABEL
        try:
            self.gmail_service.add_label_to_message(message_id, label['id'])
            logger.debug(f"Added {label_name} label to message {message_id}")
        except Exception as e:
            logger.error(f"Failed to add error label to message {message_id}: {e}")
    
    def _add_manual_review_label(self, message_id: str, email_type: str = 'shipping') -> None:
        """Add type-specific Manual-Review label and remove Error if present.
        
        Args:
            message_id: Gmail message ID
            email_type: 'shipping' or 'cancellation'
        """
        if email_type == 'cancellation':
            label = self.cancel_manual_review_label
            error_label = self.cancel_error_label
            label_name = self.CANCEL_MANUAL_REVIEW_LABEL
        else:
            label = self.shipping_manual_review_label
            error_label = self.shipping_error_label
            label_name = self.SHIPPING_MANUAL_REVIEW_LABEL
        try:
            self.gmail_service.add_label_to_message(message_id, label['id'])
            logger.debug(f"Added {label_name} label to message {message_id}")
            if error_label:
                self.gmail_service.remove_label_from_message(message_id, error_label['id'])
        except Exception as e:
            logger.error(f"Failed to add manual review label to message {message_id}: {e}")
    
    def _check_and_notify_gift_card_cancellation(self, order_number: str) -> None:
        """
        Check if order was paid with gift card and send notification to sourcing team.
        
        Args:
            order_number: Order number to check
        """
        try:
            # Get all purchase tracker records for this order
            order_records = self.db.query(PurchaseTracker).filter(
                PurchaseTracker.order_number == order_number
            ).all()
            
            if not order_records:
                logger.debug(f"No purchase tracker records found for order {order_number} to check gift card status")
                return
            
            # Check if any record indicates gift card payment
            has_gift_card_payment = False
            total_gift_card_amount = 0.0
            
            for record in order_records:
                # Check if refund_method indicates gift card
                if record.refund_method and 'gift' in record.refund_method.lower():
                    has_gift_card_payment = True
                    if record.amt_of_cancelled_qty_gift_card:
                        total_gift_card_amount += record.amt_of_cancelled_qty_gift_card
                
                # Check if amt_of_cancelled_qty_gift_card is set (indicates gift card was used)
                if record.amt_of_cancelled_qty_gift_card and record.amt_of_cancelled_qty_gift_card > 0:
                    has_gift_card_payment = True
                    total_gift_card_amount += record.amt_of_cancelled_qty_gift_card
            
            # If gift card payment detected, send notification
            if has_gift_card_payment:
                notification_message = (
                    f"\n{'='*80}\n"
                    f"🔔 GIFT CARD CANCELLATION NOTIFICATION 🔔\n"
                    f"{'='*80}\n"
                    f"Order Number: {order_number}\n"
                    f"Status: Order was cancelled and was paid with gift card\n"
                    f"Total Gift Card Amount: ${total_gift_card_amount:.2f}\n"
                    f"Action Required: Sourcing team needs to add back balance to the gift card\n"
                    f"{'='*80}\n"
                )
                logger.warning(notification_message)
            else:
                logger.debug(f"Order {order_number} was not paid with gift card, no notification needed")
        
        except Exception as e:
            logger.error(f"Error checking gift card status for order {order_number}: {e}", exc_info=True)

