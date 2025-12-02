"""
Retailer Order Processor Service
Processes order confirmation emails from retailers and creates purchase tracker records
"""

import logging
from datetime import date, datetime
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session

from app.services.gmail_service import GmailService
from app.services.footlocker_parser import FootlockerEmailParser, FootlockerOrderData, FootlockerOrderItem
from app.services.champs_parser import ChampsEmailParser, ChampsOrderData, ChampsOrderItem
from app.services.dicks_parser import DicksEmailParser, DicksOrderData, DicksOrderItem
from app.services.hibbett_parser import HibbettEmailParser, HibbettOrderData, HibbettOrderItem
from app.services.shoepalace_parser import ShoepalaceEmailParser, ShoepalaceOrderData, ShoepalaceOrderItem
from app.services.snipes_parser import SnipesEmailParser, SnipesOrderData, SnipesOrderItem
from app.services.finishline_parser import FinishLineEmailParser, FinishLineOrderData, FinishLineOrderItem
from app.services.shopsimon_parser import ShopSimonEmailParser, ShopSimonOrderData, ShopSimonOrderItem
from app.models.database import AsinBank, OASourcing, PurchaseTracker, Retailer
from app.models.email import EmailData

logger = logging.getLogger(__name__)


class RetailerOrderProcessor:
    """Service for processing retailer order confirmation emails"""
    
    # Gmail labels for tracking processed emails
    PROCESSED_LABEL = "Retailer-Orders/Processed"
    ERROR_LABEL = "Retailer-Orders/Error"
    
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
        self.dicks_parser = DicksEmailParser()
        self.hibbett_parser = HibbettEmailParser()
        self.shoepalace_parser = ShoepalaceEmailParser()
        self.snipes_parser = SnipesEmailParser()
        self.finishline_parser = FinishLineEmailParser()
        self.shopsimon_parser = ShopSimonEmailParser()
        
        # Ensure labels exist
        self.processed_label = self.gmail_service.get_or_create_label(self.PROCESSED_LABEL)
        self.error_label = self.gmail_service.get_or_create_label(self.ERROR_LABEL)
    
    def process_footlocker_emails(self, max_emails: int = 20) -> dict:
        """
        Process Footlocker order confirmation emails.
        
        Args:
            max_emails: Maximum number of emails to process
        
        Returns:
            Dictionary with processing results
        """
        logger.info(f"Starting Foot Locker email processing (max {max_emails} emails)")
        
        results = {
            'total_emails': 0,
            'processed': 0,
            'skipped_duplicate': 0,
            'errors': 0,
            'error_messages': []
        }
        
        try:
            # Search for Footlocker order confirmation emails
            # Exclude already processed emails
            query = f'from:{FootlockerEmailParser.FOOTLOCKER_FROM_EMAIL} subject:"{FootlockerEmailParser.SUBJECT_ORDER_PATTERN}" -label:{self.PROCESSED_LABEL}'
            
            message_ids = self.gmail_service.list_messages_with_query(
                query=query,
                max_results=max_emails
            )
            
            results['total_emails'] = len(message_ids)
            logger.info(f"Found {len(message_ids)} unprocessed Footlocker emails")
            
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
                    
                    if not self.footlocker_parser.is_order_confirmation_email(email_data):
                        logger.warning(f"Email {message_id} is not an order confirmation")
                        continue
                    
                    # Parse order details
                    order_data = self.footlocker_parser.parse_email(email_data)
                    if not order_data:
                        error_msg = f"Failed to parse order from email {message_id}"
                        logger.error(error_msg)
                        results['errors'] += 1
                        results['error_messages'].append(error_msg)
                        self._add_error_label(message_id)
                        continue
                    
                    # Check for duplicate order
                    if self._is_order_duplicate(order_data.order_number):
                        logger.info(f"Order {order_data.order_number} already exists - skipping")
                        results['skipped_duplicate'] += 1
                        self._add_processed_label(message_id)
                        continue
                    
                    # Process the order and create purchase tracker records
                    success, error_msg = self._process_order(order_data)
                    
                    if success:
                        logger.info(f"Successfully processed order {order_data.order_number}")
                        results['processed'] += 1
                        self._add_processed_label(message_id)
                    else:
                        logger.error(f"Failed to process order {order_data.order_number}: {error_msg}")
                        results['errors'] += 1
                        results['error_messages'].append(error_msg)
                        self._add_error_label(message_id)
                
                except Exception as e:
                    error_msg = f"Error processing message {message_id}: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    results['errors'] += 1
                    results['error_messages'].append(error_msg)
                    self._add_error_label(message_id)
        
        except Exception as e:
            error_msg = f"Fatal error in Footlocker email processing: {str(e)}"
            logger.error(error_msg, exc_info=True)
            results['error_messages'].append(error_msg)
        
        logger.info(f"Foot Locker processing complete: {results}")
        return results
    
    def process_champs_emails(self, max_emails: int = 20) -> dict:
        """
        Process Champs Sports order confirmation emails.
        
        Args:
            max_emails: Maximum number of emails to process
        
        Returns:
            Dictionary with processing results
        """
        logger.info(f"Starting Champs Sports email processing (max {max_emails} emails)")
        
        results = {
            'total_emails': 0,
            'processed': 0,
            'skipped_duplicate': 0,
            'errors': 0,
            'error_messages': []
        }
        
        try:
            # Search for Champs Sports order confirmation emails
            # Exclude already processed emails
            query = f'from:{ChampsEmailParser.CHAMPS_FROM_EMAIL} subject:"{ChampsEmailParser.SUBJECT_ORDER_PATTERN}" -label:{self.PROCESSED_LABEL}'
            
            message_ids = self.gmail_service.list_messages_with_query(
                query=query,
                max_results=max_emails
            )
            
            results['total_emails'] = len(message_ids)
            logger.info(f"Found {len(message_ids)} unprocessed Champs emails")
            
            for message_id in message_ids:
                try:
                    # Get full message
                    message = self.gmail_service.get_message(message_id)
                    if not message:
                        logger.warning(f"Could not retrieve message {message_id}")
                        continue
                    
                    # Parse to EmailData
                    email_data = self.gmail_service.parse_message_to_email_data(message)
                    
                    # Verify it's a Champs email
                    if not self.champs_parser.is_champs_email(email_data):
                        logger.warning(f"Email {message_id} is not from Champs Sports")
                        continue
                    
                    if not self.champs_parser.is_order_confirmation_email(email_data):
                        logger.warning(f"Email {message_id} is not an order confirmation")
                        continue
                    
                    # Parse order details
                    order_data = self.champs_parser.parse_email(email_data)
                    if not order_data:
                        error_msg = f"Failed to parse order from email {message_id}"
                        logger.error(error_msg)
                        results['errors'] += 1
                        results['error_messages'].append(error_msg)
                        self._add_error_label(message_id)
                        continue
                    
                    # Check for duplicate order
                    if self._is_order_duplicate(order_data.order_number):
                        logger.info(f"Order {order_data.order_number} already exists - skipping")
                        results['skipped_duplicate'] += 1
                        self._add_processed_label(message_id)
                        continue
                    
                    # Process the order and create purchase tracker records
                    success, error_msg = self._process_champs_order(order_data)
                    
                    if success:
                        logger.info(f"Successfully processed order {order_data.order_number}")
                        results['processed'] += 1
                        self._add_processed_label(message_id)
                    else:
                        logger.error(f"Failed to process order {order_data.order_number}: {error_msg}")
                        results['errors'] += 1
                        results['error_messages'].append(error_msg)
                        self._add_error_label(message_id)
                
                except Exception as e:
                    error_msg = f"Error processing message {message_id}: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    results['errors'] += 1
                    results['error_messages'].append(error_msg)
                    self._add_error_label(message_id)
        
        except Exception as e:
            error_msg = f"Fatal error in Champs email processing: {str(e)}"
            logger.error(error_msg, exc_info=True)
            results['error_messages'].append(error_msg)
        
        logger.info(f"Champs Sports processing complete: {results}")
        return results
    
    def process_dicks_emails(self, max_emails: int = 20) -> dict:
        """
        Process Dick's Sporting Goods order confirmation emails.
        
        Args:
            max_emails: Maximum number of emails to process
        
        Returns:
            Dictionary with processing results
        """
        logger.info(f"Starting Dick's Sporting Goods email processing (max {max_emails} emails)")
        
        results = {
            'total_emails': 0,
            'processed': 0,
            'skipped_duplicate': 0,
            'errors': 0,
            'error_messages': []
        }
        
        try:
            # Search for Dick's Sporting Goods order confirmation emails
            # Exclude already processed emails
            query = f'from:{DicksEmailParser.DICKS_FROM_EMAIL} subject:"{DicksEmailParser.SUBJECT_ORDER_PATTERN}" -label:{self.PROCESSED_LABEL}'
            
            message_ids = self.gmail_service.list_messages_with_query(
                query=query,
                max_results=max_emails
            )
            
            results['total_emails'] = len(message_ids)
            logger.info(f"Found {len(message_ids)} unprocessed Dick's emails")
            
            for message_id in message_ids:
                try:
                    # Get full message
                    message = self.gmail_service.get_message(message_id)
                    if not message:
                        logger.warning(f"Could not retrieve message {message_id}")
                        continue
                    
                    # Parse to EmailData
                    email_data = self.gmail_service.parse_message_to_email_data(message)
                    
                    # Verify it's a Dick's email
                    if not self.dicks_parser.is_dicks_email(email_data):
                        logger.warning(f"Email {message_id} is not from Dick's Sporting Goods")
                        continue
                    
                    if not self.dicks_parser.is_order_confirmation_email(email_data):
                        logger.warning(f"Email {message_id} is not an order confirmation")
                        continue
                    
                    # Parse order details
                    order_data = self.dicks_parser.parse_email(email_data)
                    if not order_data:
                        error_msg = f"Failed to parse order from email {message_id}"
                        logger.error(error_msg)
                        results['errors'] += 1
                        results['error_messages'].append(error_msg)
                        self._add_error_label(message_id)
                        continue
                    
                    # Check for duplicate order
                    if self._is_order_duplicate(order_data.order_number):
                        logger.info(f"Order {order_data.order_number} already exists - skipping")
                        results['skipped_duplicate'] += 1
                        self._add_processed_label(message_id)
                        continue
                    
                    # Process the order and create purchase tracker records
                    success, error_msg = self._process_dicks_order(order_data)
                    
                    if success:
                        logger.info(f"Successfully processed order {order_data.order_number}")
                        results['processed'] += 1
                        self._add_processed_label(message_id)
                    else:
                        logger.error(f"Failed to process order {order_data.order_number}: {error_msg}")
                        results['errors'] += 1
                        results['error_messages'].append(error_msg)
                        self._add_error_label(message_id)
                
                except Exception as e:
                    error_msg = f"Error processing message {message_id}: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    results['errors'] += 1
                    results['error_messages'].append(error_msg)
                    self._add_error_label(message_id)
        
        except Exception as e:
            error_msg = f"Fatal error in Dick's email processing: {str(e)}"
            logger.error(error_msg, exc_info=True)
            results['error_messages'].append(error_msg)
        
        logger.info(f"Dick's Sporting Goods processing complete: {results}")
        return results
    
    def process_hibbett_emails(self, max_emails: int = 20) -> dict:
        """
        Process Hibbett order confirmation emails.
        
        Args:
            max_emails: Maximum number of emails to process
        
        Returns:
            Dictionary with processing results
        """
        logger.info(f"Starting Hibbett email processing (max {max_emails} emails)")
        
        results = {
            'total_emails': 0,
            'processed': 0,
            'skipped_duplicate': 0,
            'errors': 0,
            'error_messages': []
        }
        
        try:
            # Search for Hibbett order confirmation emails
            # Exclude already processed emails
            query = f'from:{HibbettEmailParser.HIBBETT_FROM_EMAIL} subject:"{HibbettEmailParser.SUBJECT_ORDER_PATTERN}" -label:{self.PROCESSED_LABEL}'
            
            message_ids = self.gmail_service.list_messages_with_query(
                query=query,
                max_results=max_emails
            )
            
            results['total_emails'] = len(message_ids)
            logger.info(f"Found {len(message_ids)} unprocessed Hibbett emails")
            
            for message_id in message_ids:
                try:
                    # Get full message
                    message = self.gmail_service.get_message(message_id)
                    if not message:
                        logger.warning(f"Could not retrieve message {message_id}")
                        continue
                    
                    # Parse to EmailData
                    email_data = self.gmail_service.parse_message_to_email_data(message)
                    
                    # Verify it's a Hibbett email
                    if not self.hibbett_parser.is_hibbett_email(email_data):
                        logger.warning(f"Email {message_id} is not from Hibbett")
                        continue
                    
                    if not self.hibbett_parser.is_order_confirmation_email(email_data):
                        logger.warning(f"Email {message_id} is not an order confirmation")
                        continue
                    
                    # Parse order details
                    order_data = self.hibbett_parser.parse_email(email_data)
                    if not order_data:
                        error_msg = f"Failed to parse order from email {message_id}"
                        logger.error(error_msg)
                        results['errors'] += 1
                        results['error_messages'].append(error_msg)
                        self._add_error_label(message_id)
                        continue
                    
                    # Check for duplicate order
                    if self._is_order_duplicate(order_data.order_number):
                        logger.info(f"Order {order_data.order_number} already exists - skipping")
                        results['skipped_duplicate'] += 1
                        self._add_processed_label(message_id)
                        continue
                    
                    # Process the order and create purchase tracker records
                    success, error_msg = self._process_hibbett_order(order_data)
                    
                    if success:
                        logger.info(f"Successfully processed order {order_data.order_number}")
                        results['processed'] += 1
                        self._add_processed_label(message_id)
                    else:
                        logger.error(f"Failed to process order {order_data.order_number}: {error_msg}")
                        results['errors'] += 1
                        results['error_messages'].append(error_msg)
                        self._add_error_label(message_id)
                
                except Exception as e:
                    error_msg = f"Error processing message {message_id}: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    results['errors'] += 1
                    results['error_messages'].append(error_msg)
                    self._add_error_label(message_id)
        
        except Exception as e:
            error_msg = f"Fatal error in Hibbett email processing: {str(e)}"
            logger.error(error_msg, exc_info=True)
            results['error_messages'].append(error_msg)
        
        logger.info(f"Hibbett processing complete: {results}")
        return results
    
    def process_shoepalace_emails(self, max_emails: int = 20) -> dict:
        """
        Process Shoe Palace order confirmation emails.
        
        Args:
            max_emails: Maximum number of emails to process
        
        Returns:
            Dictionary with processing results
        """
        logger.info(f"Starting Shoe Palace email processing (max {max_emails} emails)")
        
        results = {
            'total_emails': 0,
            'processed': 0,
            'skipped_duplicate': 0,
            'errors': 0,
            'error_messages': []
        }
        
        try:
            # Search for Shoe Palace order confirmation emails
            # Exclude already processed emails
            query = f'from:{ShoepalaceEmailParser.SHOEPALACE_FROM_EMAIL} subject:"{ShoepalaceEmailParser.SUBJECT_ORDER_PATTERN}" -label:{self.PROCESSED_LABEL}'
            
            message_ids = self.gmail_service.list_messages_with_query(
                query=query,
                max_results=max_emails
            )
            
            results['total_emails'] = len(message_ids)
            logger.info(f"Found {len(message_ids)} unprocessed Shoe Palace emails")
            
            for message_id in message_ids:
                try:
                    # Get full message
                    message = self.gmail_service.get_message(message_id)
                    if not message:
                        logger.warning(f"Could not retrieve message {message_id}")
                        continue
                    
                    # Parse to EmailData
                    email_data = self.gmail_service.parse_message_to_email_data(message)
                    
                    # Verify it's a Shoe Palace email
                    if not self.shoepalace_parser.is_shoepalace_email(email_data):
                        logger.warning(f"Email {message_id} is not from Shoe Palace")
                        continue
                    
                    if not self.shoepalace_parser.is_order_confirmation_email(email_data):
                        logger.warning(f"Email {message_id} is not an order confirmation")
                        continue
                    
                    # Parse order details
                    order_data = self.shoepalace_parser.parse_email(email_data)
                    if not order_data:
                        error_msg = f"Failed to parse order from email {message_id}"
                        logger.error(error_msg)
                        results['errors'] += 1
                        results['error_messages'].append(error_msg)
                        self._add_error_label(message_id)
                        continue
                    
                    # Check for duplicate order
                    if self._is_order_duplicate(order_data.order_number):
                        logger.info(f"Order {order_data.order_number} already exists - skipping")
                        results['skipped_duplicate'] += 1
                        self._add_processed_label(message_id)
                        continue
                    
                    # Process the order and create purchase tracker records
                    success, error_msg = self._process_shoepalace_order(order_data)
                    
                    if success:
                        logger.info(f"Successfully processed order {order_data.order_number}")
                        results['processed'] += 1
                        self._add_processed_label(message_id)
                    else:
                        logger.error(f"Failed to process order {order_data.order_number}: {error_msg}")
                        results['errors'] += 1
                        results['error_messages'].append(error_msg)
                        self._add_error_label(message_id)
                
                except Exception as e:
                    error_msg = f"Error processing message {message_id}: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    results['errors'] += 1
                    results['error_messages'].append(error_msg)
                    self._add_error_label(message_id)
        
        except Exception as e:
            error_msg = f"Fatal error in Shoe Palace email processing: {str(e)}"
            logger.error(error_msg, exc_info=True)
            results['error_messages'].append(error_msg)
        
        logger.info(f"Shoe Palace processing complete: {results}")
        return results
    
    def process_snipes_emails(self, max_emails: int = 20) -> dict:
        """
        Process Snipes order confirmation emails.
        
        Args:
            max_emails: Maximum number of emails to process
        
        Returns:
            Dictionary with processing results
        """
        logger.info(f"Starting Snipes email processing (max {max_emails} emails)")
        
        results = {
            'total_emails': 0,
            'processed': 0,
            'skipped_duplicate': 0,
            'errors': 0,
            'error_messages': []
        }
        
        try:
            # Search for Snipes order confirmation emails
            # Exclude already processed emails
            query = f'from:{SnipesEmailParser.SNIPES_FROM_EMAIL} subject:"{SnipesEmailParser.SUBJECT_ORDER_PATTERN}" -label:{self.PROCESSED_LABEL}'
            
            message_ids = self.gmail_service.list_messages_with_query(
                query=query,
                max_results=max_emails
            )
            
            results['total_emails'] = len(message_ids)
            logger.info(f"Found {len(message_ids)} unprocessed Snipes emails")
            
            for message_id in message_ids:
                try:
                    # Get full message
                    message = self.gmail_service.get_message(message_id)
                    if not message:
                        logger.warning(f"Could not retrieve message {message_id}")
                        continue
                    
                    # Parse to EmailData
                    email_data = self.gmail_service.parse_message_to_email_data(message)

                    # Verify it's a Snipes email
                    if not self.snipes_parser.is_snipes_email(email_data):
                        logger.warning(f"Email {message_id} is not from Snipes")
                        continue
                    
                    if not self.snipes_parser.is_order_confirmation_email(email_data):
                        logger.warning(f"Email {message_id} is not an order confirmation")
                        continue
                    
                    # Parse the email
                    order_data = self.snipes_parser.parse_email(email_data)
                    
                    if not order_data:
                        error_msg = f"Failed to parse Snipes email {message_id}"
                        logger.error(error_msg)
                        results['errors'] += 1
                        results['error_messages'].append(error_msg)
                        self._add_error_label(message_id)
                        continue
                    
                    # Check for duplicate order
                    if self._is_order_duplicate(order_data.order_number):
                        logger.info(f"Order {order_data.order_number} already exists, skipping")
                        results['skipped_duplicate'] += 1
                        self._add_processed_label(message_id)
                        continue
                    
                    # Process the order
                    success, error = self._process_snipes_order(order_data)
                    
                    if success:
                        results['processed'] += 1
                        self._add_processed_label(message_id)
                        logger.info(f"Successfully processed Snipes order {order_data.order_number}")
                    else:
                        results['errors'] += 1
                        error_msg = f"Failed to process Snipes order {order_data.order_number}: {error}"
                        logger.error(error_msg)
                        results['error_messages'].append(error_msg)
                        self._add_error_label(message_id)
                
                except Exception as e:
                    results['errors'] += 1
                    error_msg = f"Error processing Snipes email {message_id}: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    results['error_messages'].append(error_msg)
                    self._add_error_label(message_id)
        
        except Exception as e:
            error_msg = f"Fatal error in Snipes email processing: {str(e)}"
            logger.error(error_msg, exc_info=True)
            results['error_messages'].append(error_msg)
        
        logger.info(f"Snipes processing complete: {results}")
        return results
    
    def process_finishline_emails(self, max_emails: int = 20) -> dict:
        """
        Process Finish Line order confirmation emails.
        
        Args:
            max_emails: Maximum number of emails to process
        
        Returns:
            Dictionary with processing results
        """
        logger.info(f"Starting Finish Line email processing (max {max_emails} emails)")
        
        results = {
            'total_emails': 0,
            'processed': 0,
            'skipped_duplicate': 0,
            'errors': 0,
            'error_messages': []
        }
        
        try:
            # Search for Finish Line order confirmation emails
            # Exclude already processed emails
            query = f'from:{FinishLineEmailParser.FINISHLINE_FROM_EMAIL} subject:"{FinishLineEmailParser.SUBJECT_ORDER_PATTERN}" -label:{self.PROCESSED_LABEL}'
            
            message_ids = self.gmail_service.list_messages_with_query(
                query=query,
                max_results=max_emails
            )
            
            results['total_emails'] = len(message_ids)
            logger.info(f"Found {len(message_ids)} unprocessed Finish Line emails")
            
            for message_id in message_ids:
                try:
                    # Get full message
                    message = self.gmail_service.get_message(message_id)
                    if not message:
                        logger.warning(f"Could not retrieve message {message_id}")
                        continue
                    
                    # Parse to EmailData
                    email_data = self.gmail_service.parse_message_to_email_data(message)

                    # Verify it's a Finish Line email
                    if not self.finishline_parser.is_finishline_email(email_data):
                        logger.warning(f"Email {message_id} is not from Finish Line")
                        continue
                    
                    if not self.finishline_parser.is_order_confirmation_email(email_data):
                        logger.warning(f"Email {message_id} is not an order confirmation")
                        continue
                    
                    # Parse the email
                    order_data = self.finishline_parser.parse_email(email_data)
                    
                    if not order_data:
                        error_msg = f"Failed to parse Finish Line email {message_id}"
                        logger.error(error_msg)
                        results['errors'] += 1
                        results['error_messages'].append(error_msg)
                        self._add_error_label(message_id)
                        continue
                    
                    # Check for duplicate order
                    if self._is_order_duplicate(order_data.order_number):
                        logger.info(f"Order {order_data.order_number} already exists, skipping")
                        results['skipped_duplicate'] += 1
                        self._add_processed_label(message_id)
                        continue
                    
                    # Process the order
                    success, error = self._process_finishline_order(order_data)
                    
                    if success:
                        results['processed'] += 1
                        self._add_processed_label(message_id)
                        logger.info(f"Successfully processed Finish Line order {order_data.order_number}")
                    else:
                        results['errors'] += 1
                        error_msg = f"Failed to process Finish Line order {order_data.order_number}: {error}"
                        logger.error(error_msg)
                        results['error_messages'].append(error_msg)
                        self._add_error_label(message_id)
                
                except Exception as e:
                    results['errors'] += 1
                    error_msg = f"Error processing Finish Line email {message_id}: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    results['error_messages'].append(error_msg)
                    self._add_error_label(message_id)
        
        except Exception as e:
            error_msg = f"Fatal error in Finish Line email processing: {str(e)}"
            logger.error(error_msg, exc_info=True)
            results['error_messages'].append(error_msg)
        
        logger.info(f"Finish Line processing complete: {results}")
        return results
    
    def process_shopsimon_emails(self, max_emails: int = 20) -> dict:
        """
        Process ShopSimon order confirmation emails.
        
        Args:
            max_emails: Maximum number of emails to process
        
        Returns:
            Dictionary with processing results
        """
        logger.info(f"Starting ShopSimon email processing (max {max_emails} emails)")
        
        results = {
            'total_emails': 0,
            'processed': 0,
            'skipped_duplicate': 0,
            'errors': 0,
            'error_messages': []
        }
        
        try:
            # Search for ShopSimon order confirmation emails
            # Exclude already processed emails
            query = f'from:{ShopSimonEmailParser.SHOPSIMON_FROM_EMAIL} subject:"{ShopSimonEmailParser.SUBJECT_ORDER_PATTERN}" -label:{self.PROCESSED_LABEL}'
            
            message_ids = self.gmail_service.list_messages_with_query(
                query=query,
                max_results=max_emails
            )
            
            results['total_emails'] = len(message_ids)
            logger.info(f"Found {len(message_ids)} unprocessed ShopSimon emails")
            
            for message_id in message_ids:
                try:
                    # Get full message
                    message = self.gmail_service.get_message(message_id)
                    if not message:
                        logger.warning(f"Could not retrieve message {message_id}")
                        continue
                    
                    # Parse to EmailData
                    email_data = self.gmail_service.parse_message_to_email_data(message)

                    # Verify it's a ShopSimon email
                    if not self.shopsimon_parser.is_shopsimon_email(email_data):
                        logger.warning(f"Email {message_id} is not from ShopSimon")
                        continue
                    
                    if not self.shopsimon_parser.is_order_confirmation_email(email_data):
                        logger.warning(f"Email {message_id} is not an order confirmation")
                        continue
                    
                    # Parse the email
                    order_data = self.shopsimon_parser.parse_email(email_data)
                    
                    if not order_data:
                        error_msg = f"Failed to parse ShopSimon email {message_id}"
                        logger.error(error_msg)
                        results['errors'] += 1
                        results['error_messages'].append(error_msg)
                        self._add_error_label(message_id)
                        continue
                    
                    # Check for duplicate order
                    if self._is_order_duplicate(order_data.order_number):
                        logger.info(f"Order {order_data.order_number} already exists, skipping")
                        results['skipped_duplicate'] += 1
                        self._add_processed_label(message_id)
                        continue
                    
                    # Process the order
                    success, error = self._process_shopsimon_order(order_data)
                    
                    if success:
                        results['processed'] += 1
                        self._add_processed_label(message_id)
                        logger.info(f"Successfully processed ShopSimon order {order_data.order_number}")
                    else:
                        results['errors'] += 1
                        error_msg = f"Failed to process ShopSimon order {order_data.order_number}: {error}"
                        logger.error(error_msg)
                        results['error_messages'].append(error_msg)
                        self._add_error_label(message_id)
                
                except Exception as e:
                    results['errors'] += 1
                    error_msg = f"Error processing ShopSimon email {message_id}: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    results['error_messages'].append(error_msg)
                    self._add_error_label(message_id)
        
        except Exception as e:
            error_msg = f"Fatal error in ShopSimon email processing: {str(e)}"
            logger.error(error_msg, exc_info=True)
            results['error_messages'].append(error_msg)
        
        logger.info(f"ShopSimon processing complete: {results}")
        return results
    
    def _is_order_duplicate(self, order_number: str) -> bool:
        """
        Check if order number already exists in purchase_tracker.
        
        Args:
            order_number: Order number to check
        
        Returns:
            True if order already exists
        """
        exists = self.db.query(PurchaseTracker).filter(
            PurchaseTracker.order_number == order_number
        ).first()
        
        return exists is not None
    
    def _process_order(self, order_data: FootlockerOrderData) -> Tuple[bool, Optional[str]]:
        """
        Process a Footlocker order and create purchase tracker records.
        
        Args:
            order_data: Parsed order data
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Get Footlocker retailer (try both "Footlocker" and "Foot Locker")
            footlocker_retailer = self.db.query(Retailer).filter(
                Retailer.name.ilike('%Footlocker%') | Retailer.name.ilike('%Foot Locker%')
            ).first()
            
            if not footlocker_retailer:
                return False, "Footlocker retailer not found in database"
            
            created_count = 0
            skipped_count = 0
            
            for item in order_data.items:
                success, error = self._create_purchase_tracker_record(
                    order_number=order_data.order_number,
                    item=item,
                    retailer=footlocker_retailer
                )
                
                if success:
                    created_count += 1
                else:
                    logger.warning(f"Could not create record for item {item.unique_id}: {error}")
                    skipped_count += 1
            
            # Commit all changes
            self.db.commit()
            
            if created_count == 0:
                return False, f"No purchase tracker records created (skipped: {skipped_count})"
            
            logger.info(f"Created {created_count} purchase tracker records for order {order_data.order_number}")
            
            if skipped_count > 0:
                logger.warning(f"Skipped {skipped_count} items (no matching OA sourcing lead)")
            
            return True, None
        
        except Exception as e:
            self.db.rollback()
            error_msg = f"Error processing order {order_data.order_number}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
    
    def _process_champs_order(self, order_data: ChampsOrderData) -> Tuple[bool, Optional[str]]:
        """
        Process a Champs Sports order and create purchase tracker records.
        
        Args:
            order_data: Parsed order data
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Get Champs Sports retailer
            champs_retailer = self.db.query(Retailer).filter(
                Retailer.name.ilike('%Champs%') | Retailer.name.ilike('%Champs Sports%')
            ).first()
            
            if not champs_retailer:
                return False, "Champs Sports retailer not found in database"
            
            created_count = 0
            skipped_count = 0
            
            for item in order_data.items:
                success, error = self._create_purchase_tracker_record_champs(
                    order_number=order_data.order_number,
                    item=item,
                    retailer=champs_retailer
                )
                
                if success:
                    created_count += 1
                else:
                    logger.warning(f"Could not create record for item {item.unique_id}: {error}")
                    skipped_count += 1
            
            # Commit all changes
            self.db.commit()
            
            if created_count == 0:
                return False, f"No purchase tracker records created (skipped: {skipped_count})"
            
            logger.info(f"Created {created_count} purchase tracker records for order {order_data.order_number}")
            
            if skipped_count > 0:
                logger.warning(f"Skipped {skipped_count} items (no matching OA sourcing lead)")
            
            return True, None
        
        except Exception as e:
            self.db.rollback()
            error_msg = f"Error processing order {order_data.order_number}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
    
    def _process_dicks_order(self, order_data: DicksOrderData) -> Tuple[bool, Optional[str]]:
        """
        Process a Dick's Sporting Goods order and create purchase tracker records.
        
        Args:
            order_data: Parsed order data
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Get Dick's Sporting Goods retailer
            dicks_retailer = self.db.query(Retailer).filter(
                Retailer.name.ilike('%Dick%') | Retailer.name.ilike('%Dicks%')
            ).first()
            
            if not dicks_retailer:
                return False, "Dick's Sporting Goods retailer not found in database"
            
            created_count = 0
            skipped_count = 0
            
            for item in order_data.items:
                success, error = self._create_purchase_tracker_record_dicks(
                    order_number=order_data.order_number,
                    item=item,
                    retailer=dicks_retailer
                )
                
                if success:
                    created_count += 1
                else:
                    logger.warning(f"Could not create record for item {item.unique_id}: {error}")
                    skipped_count += 1
            
            # Commit all changes
            self.db.commit()
            
            if created_count == 0:
                return False, f"No purchase tracker records created (skipped: {skipped_count})"
            
            logger.info(f"Created {created_count} purchase tracker records for order {order_data.order_number}")
            
            if skipped_count > 0:
                logger.warning(f"Skipped {skipped_count} items (no matching OA sourcing lead)")
            
            return True, None
        
        except Exception as e:
            self.db.rollback()
            error_msg = f"Error processing order {order_data.order_number}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
    
    def _create_purchase_tracker_record(
        self,
        order_number: str,
        item: FootlockerOrderItem,
        retailer: Retailer
    ) -> Tuple[bool, Optional[str]]:
        """
        Create a purchase tracker record for a single item.
        
        Args:
            order_number: Order number
            item: Order item data
            retailer: Retailer object
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Look up OA sourcing by unique_id
            oa_sourcing = self.db.query(OASourcing).filter(
                OASourcing.unique_id == item.unique_id
            ).first()
            
            if not oa_sourcing:
                return False, f"No OA sourcing lead found for unique_id: {item.unique_id}"
            
            # Look up ASIN from asin_bank by lead_id and size
            asin_record = self.db.query(AsinBank).filter(
                AsinBank.lead_id == oa_sourcing.lead_id,
                AsinBank.size == item.size
            ).first()
            
            if not asin_record:
                logger.warning(
                    f"No ASIN found for lead_id={oa_sourcing.lead_id}, size={item.size}. "
                    f"Creating record without ASIN."
                )
            
            # Calculate FBA MSKU: {size}-{sku_upc}-{order_number}
            sku_upc = oa_sourcing.product_sku or "UNKNOWN"
            fba_msku = f"{item.size}-{sku_upc}-{order_number}"
            
            # Create purchase tracker record
            purchase_record = PurchaseTracker(
                # Foreign keys
                oa_sourcing_id=oa_sourcing.id,
                asin_bank_id=asin_record.id if asin_record else None,
                
                # Denormalized for performance
                lead_id=oa_sourcing.lead_id,
                
                # Purchase metadata
                date=date.today(),
                platform="AMZ",  # Selling platform (Amazon)
                order_number=order_number,
                
                # Quantities
                og_qty=item.quantity,
                final_qty=item.quantity,
                
                # Pricing - use from oa_sourcing
                rsp=oa_sourcing.rsp,
                
                # FBA fields
                fba_msku=fba_msku,
                
                # Status
                status="Ordered",
                
                # Audit
                audited=False
            )
            
            self.db.add(purchase_record)
            
            logger.info(
                f"Created purchase tracker record: "
                f"lead_id={oa_sourcing.lead_id}, "
                f"product={oa_sourcing.product_name}, "
                f"size={item.size}, "
                f"qty={item.quantity}, "
                f"asin={asin_record.asin if asin_record else 'N/A'}, "
                f"msku={fba_msku}"
            )
            
            return True, None
        
        except Exception as e:
            error_msg = f"Error creating purchase tracker record: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
    
    def _process_shoepalace_order(self, order_data: ShoepalaceOrderData) -> Tuple[bool, Optional[str]]:
        """
        Process a Shoe Palace order and create purchase tracker records.
        
        Args:
            order_data: Parsed order data
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Get Shoe Palace retailer
            shoepalace_retailer = self.db.query(Retailer).filter(
                Retailer.name.ilike('%Shoe Palace%') | Retailer.name.ilike('%Shoepalace%')
            ).first()
            
            if not shoepalace_retailer:
                return False, "Shoe Palace retailer not found in database"
            
            created_count = 0
            skipped_count = 0
            
            for item in order_data.items:
                success, error = self._create_purchase_tracker_record_shoepalace(
                    order_number=order_data.order_number,
                    item=item,
                    retailer=shoepalace_retailer
                )
                
                if success:
                    created_count += 1
                else:
                    logger.warning(f"Could not create record for item {item.unique_id}: {error}")
                    skipped_count += 1
            
            # Commit all changes
            self.db.commit()
            
            if created_count == 0:
                return False, f"No purchase tracker records created (skipped: {skipped_count})"
            
            logger.info(f"Created {created_count} purchase tracker records for order {order_data.order_number}")
            
            if skipped_count > 0:
                logger.warning(f"Skipped {skipped_count} items (no matching OA sourcing lead)")
            
            return True, None
        
        except Exception as e:
            self.db.rollback()
            error_msg = f"Error processing order {order_data.order_number}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
    
    def _create_purchase_tracker_record_shoepalace(
        self,
        order_number: str,
        item: ShoepalaceOrderItem,
        retailer: Retailer
    ) -> Tuple[bool, Optional[str]]:
        """
        Create a purchase tracker record for a single Shoe Palace item.
        
        Args:
            order_number: Order number
            item: Order item data
            retailer: Retailer object
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Look up OA sourcing by unique_id
            oa_sourcing = self.db.query(OASourcing).filter(
                OASourcing.unique_id == item.unique_id
            ).first()
            
            if not oa_sourcing:
                return False, f"No OA sourcing lead found for unique_id: {item.unique_id}"
            
            # Look up ASIN from asin_bank by lead_id and size
            asin_record = self.db.query(AsinBank).filter(
                AsinBank.lead_id == oa_sourcing.lead_id,
                AsinBank.size == item.size
            ).first()
            
            if not asin_record:
                logger.warning(
                    f"No ASIN found for lead_id={oa_sourcing.lead_id}, size={item.size}. "
                    f"Creating record without ASIN."
                )
            
            # Calculate FBA MSKU: {size}-{sku_upc}-{order_number}
            sku_upc = oa_sourcing.product_sku or "UNKNOWN"
            fba_msku = f"{item.size}-{sku_upc}-{order_number}"
            
            # Create purchase tracker record
            purchase_record = PurchaseTracker(
                # Foreign keys
                oa_sourcing_id=oa_sourcing.id,
                asin_bank_id=asin_record.id if asin_record else None,
                
                # Denormalized for performance
                lead_id=oa_sourcing.lead_id,
                
                # Purchase metadata
                date=date.today(),
                platform="AMZ",  # Selling platform (Amazon)
                order_number=order_number,
                
                # Quantities
                og_qty=item.quantity,
                final_qty=item.quantity,
                
                # Pricing - use from oa_sourcing
                rsp=oa_sourcing.rsp,
                
                # FBA fields
                fba_msku=fba_msku,
                
                # Status
                status="Ordered",
                
                # Audit
                audited=False
            )
            
            self.db.add(purchase_record)
            
            logger.info(
                f"Created purchase tracker record: "
                f"lead_id={oa_sourcing.lead_id}, "
                f"product={oa_sourcing.product_name}, "
                f"size={item.size}, "
                f"qty={item.quantity}, "
                f"asin={asin_record.asin if asin_record else 'N/A'}, "
                f"msku={fba_msku}"
            )
            
            return True, None
        
        except Exception as e:
            error_msg = f"Error creating purchase tracker record: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
    
    def _create_purchase_tracker_record_champs(
        self,
        order_number: str,
        item: ChampsOrderItem,
        retailer: Retailer
    ) -> Tuple[bool, Optional[str]]:
        """
        Create a purchase tracker record for a single Champs Sports item.
        
        Args:
            order_number: Order number
            item: Order item data
            retailer: Retailer object
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Look up OA sourcing by unique_id
            oa_sourcing = self.db.query(OASourcing).filter(
                OASourcing.unique_id == item.unique_id
            ).first()
            
            if not oa_sourcing:
                return False, f"No OA sourcing lead found for unique_id: {item.unique_id}"
            
            # Look up ASIN from asin_bank by lead_id and size
            asin_record = self.db.query(AsinBank).filter(
                AsinBank.lead_id == oa_sourcing.lead_id,
                AsinBank.size == item.size
            ).first()
            
            if not asin_record:
                logger.warning(
                    f"No ASIN found for lead_id={oa_sourcing.lead_id}, size={item.size}. "
                    f"Creating record without ASIN."
                )
            
            # Calculate FBA MSKU: {size}-{sku_upc}-{order_number}
            sku_upc = oa_sourcing.product_sku or "UNKNOWN"
            fba_msku = f"{item.size}-{sku_upc}-{order_number}"
            
            # Create purchase tracker record
            purchase_record = PurchaseTracker(
                # Foreign keys
                oa_sourcing_id=oa_sourcing.id,
                asin_bank_id=asin_record.id if asin_record else None,
                
                # Denormalized for performance
                lead_id=oa_sourcing.lead_id,
                
                # Purchase metadata
                date=date.today(),
                platform="AMZ",  # Selling platform (Amazon)
                order_number=order_number,
                
                # Quantities
                og_qty=item.quantity,
                final_qty=item.quantity,
                
                # Pricing - use from oa_sourcing
                rsp=oa_sourcing.rsp,
                
                # FBA fields
                fba_msku=fba_msku,
                
                # Status
                status="Ordered",
                
                # Audit
                audited=False
            )
            
            self.db.add(purchase_record)
            
            logger.info(
                f"Created purchase tracker record: "
                f"lead_id={oa_sourcing.lead_id}, "
                f"product={oa_sourcing.product_name}, "
                f"size={item.size}, "
                f"qty={item.quantity}, "
                f"asin={asin_record.asin if asin_record else 'N/A'}, "
                f"msku={fba_msku}"
            )
            
            return True, None
        
        except Exception as e:
            error_msg = f"Error creating purchase tracker record: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
    
    def _process_shoepalace_order(self, order_data: ShoepalaceOrderData) -> Tuple[bool, Optional[str]]:
        """
        Process a Shoe Palace order and create purchase tracker records.
        
        Args:
            order_data: Parsed order data
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Get Shoe Palace retailer
            shoepalace_retailer = self.db.query(Retailer).filter(
                Retailer.name.ilike('%Shoe Palace%') | Retailer.name.ilike('%Shoepalace%')
            ).first()
            
            if not shoepalace_retailer:
                return False, "Shoe Palace retailer not found in database"
            
            created_count = 0
            skipped_count = 0
            
            for item in order_data.items:
                success, error = self._create_purchase_tracker_record_shoepalace(
                    order_number=order_data.order_number,
                    item=item,
                    retailer=shoepalace_retailer
                )
                
                if success:
                    created_count += 1
                else:
                    logger.warning(f"Could not create record for item {item.unique_id}: {error}")
                    skipped_count += 1
            
            # Commit all changes
            self.db.commit()
            
            if created_count == 0:
                return False, f"No purchase tracker records created (skipped: {skipped_count})"
            
            logger.info(f"Created {created_count} purchase tracker records for order {order_data.order_number}")
            
            if skipped_count > 0:
                logger.warning(f"Skipped {skipped_count} items (no matching OA sourcing lead)")
            
            return True, None
        
        except Exception as e:
            self.db.rollback()
            error_msg = f"Error processing order {order_data.order_number}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
    
    def _create_purchase_tracker_record_shoepalace(
        self,
        order_number: str,
        item: ShoepalaceOrderItem,
        retailer: Retailer
    ) -> Tuple[bool, Optional[str]]:
        """
        Create a purchase tracker record for a single Shoe Palace item.
        
        Args:
            order_number: Order number
            item: Order item data
            retailer: Retailer object
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Look up OA sourcing by unique_id
            oa_sourcing = self.db.query(OASourcing).filter(
                OASourcing.unique_id == item.unique_id
            ).first()
            
            if not oa_sourcing:
                return False, f"No OA sourcing lead found for unique_id: {item.unique_id}"
            
            # Look up ASIN from asin_bank by lead_id and size
            asin_record = self.db.query(AsinBank).filter(
                AsinBank.lead_id == oa_sourcing.lead_id,
                AsinBank.size == item.size
            ).first()
            
            if not asin_record:
                logger.warning(
                    f"No ASIN found for lead_id={oa_sourcing.lead_id}, size={item.size}. "
                    f"Creating record without ASIN."
                )
            
            # Calculate FBA MSKU: {size}-{sku_upc}-{order_number}
            sku_upc = oa_sourcing.product_sku or "UNKNOWN"
            fba_msku = f"{item.size}-{sku_upc}-{order_number}"
            
            # Create purchase tracker record
            purchase_record = PurchaseTracker(
                # Foreign keys
                oa_sourcing_id=oa_sourcing.id,
                asin_bank_id=asin_record.id if asin_record else None,
                
                # Denormalized for performance
                lead_id=oa_sourcing.lead_id,
                
                # Purchase metadata
                date=date.today(),
                platform="AMZ",  # Selling platform (Amazon)
                order_number=order_number,
                
                # Quantities
                og_qty=item.quantity,
                final_qty=item.quantity,
                
                # Pricing - use from oa_sourcing
                rsp=oa_sourcing.rsp,
                
                # FBA fields
                fba_msku=fba_msku,
                
                # Status
                status="Ordered",
                
                # Audit
                audited=False
            )
            
            self.db.add(purchase_record)
            
            logger.info(
                f"Created purchase tracker record: "
                f"lead_id={oa_sourcing.lead_id}, "
                f"product={oa_sourcing.product_name}, "
                f"size={item.size}, "
                f"qty={item.quantity}, "
                f"asin={asin_record.asin if asin_record else 'N/A'}, "
                f"msku={fba_msku}"
            )
            
            return True, None
        
        except Exception as e:
            error_msg = f"Error creating purchase tracker record: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
    
    def _create_purchase_tracker_record_dicks(
        self,
        order_number: str,
        item: DicksOrderItem,
        retailer: Retailer
    ) -> Tuple[bool, Optional[str]]:
        """
        Create a purchase tracker record for a single Dick's Sporting Goods item.
        
        Args:
            order_number: Order number
            item: Order item data
            retailer: Retailer object
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Look up OA sourcing by unique_id
            oa_sourcing = self.db.query(OASourcing).filter(
                OASourcing.unique_id == item.unique_id
            ).first()
            
            if not oa_sourcing:
                return False, f"No OA sourcing lead found for unique_id: {item.unique_id}"
            
            # Look up ASIN from asin_bank by lead_id and size
            asin_record = self.db.query(AsinBank).filter(
                AsinBank.lead_id == oa_sourcing.lead_id,
                AsinBank.size == item.size
            ).first()
            
            if not asin_record:
                logger.warning(
                    f"No ASIN found for lead_id={oa_sourcing.lead_id}, size={item.size}. "
                    f"Creating record without ASIN."
                )
            
            # Calculate FBA MSKU: {size}-{sku_upc}-{order_number}
            sku_upc = oa_sourcing.product_sku or "UNKNOWN"
            fba_msku = f"{item.size}-{sku_upc}-{order_number}"
            
            # Create purchase tracker record
            purchase_record = PurchaseTracker(
                # Foreign keys
                oa_sourcing_id=oa_sourcing.id,
                asin_bank_id=asin_record.id if asin_record else None,
                
                # Denormalized for performance
                lead_id=oa_sourcing.lead_id,
                
                # Purchase metadata
                date=date.today(),
                platform="AMZ",  # Selling platform (Amazon)
                order_number=order_number,
                
                # Quantities
                og_qty=item.quantity,
                final_qty=item.quantity,
                
                # Pricing - use from oa_sourcing
                rsp=oa_sourcing.rsp,
                
                # FBA fields
                fba_msku=fba_msku,
                
                # Status
                status="Ordered",
                
                # Audit
                audited=False
            )
            
            self.db.add(purchase_record)
            
            logger.info(
                f"Created purchase tracker record: "
                f"lead_id={oa_sourcing.lead_id}, "
                f"product={oa_sourcing.product_name}, "
                f"size={item.size}, "
                f"qty={item.quantity}, "
                f"asin={asin_record.asin if asin_record else 'N/A'}, "
                f"msku={fba_msku}"
            )
            
            return True, None
        
        except Exception as e:
            error_msg = f"Error creating purchase tracker record: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
    
    def _process_shoepalace_order(self, order_data: ShoepalaceOrderData) -> Tuple[bool, Optional[str]]:
        """
        Process a Shoe Palace order and create purchase tracker records.
        
        Args:
            order_data: Parsed order data
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Get Shoe Palace retailer
            shoepalace_retailer = self.db.query(Retailer).filter(
                Retailer.name.ilike('%Shoe Palace%') | Retailer.name.ilike('%Shoepalace%')
            ).first()
            
            if not shoepalace_retailer:
                return False, "Shoe Palace retailer not found in database"
            
            created_count = 0
            skipped_count = 0
            
            for item in order_data.items:
                success, error = self._create_purchase_tracker_record_shoepalace(
                    order_number=order_data.order_number,
                    item=item,
                    retailer=shoepalace_retailer
                )
                
                if success:
                    created_count += 1
                else:
                    logger.warning(f"Could not create record for item {item.unique_id}: {error}")
                    skipped_count += 1
            
            # Commit all changes
            self.db.commit()
            
            if created_count == 0:
                return False, f"No purchase tracker records created (skipped: {skipped_count})"
            
            logger.info(f"Created {created_count} purchase tracker records for order {order_data.order_number}")
            
            if skipped_count > 0:
                logger.warning(f"Skipped {skipped_count} items (no matching OA sourcing lead)")
            
            return True, None
        
        except Exception as e:
            self.db.rollback()
            error_msg = f"Error processing order {order_data.order_number}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
    
    def _create_purchase_tracker_record_shoepalace(
        self,
        order_number: str,
        item: ShoepalaceOrderItem,
        retailer: Retailer
    ) -> Tuple[bool, Optional[str]]:
        """
        Create a purchase tracker record for a single Shoe Palace item.
        
        Args:
            order_number: Order number
            item: Order item data
            retailer: Retailer object
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Look up OA sourcing by unique_id
            oa_sourcing = self.db.query(OASourcing).filter(
                OASourcing.unique_id == item.unique_id
            ).first()
            
            if not oa_sourcing:
                return False, f"No OA sourcing lead found for unique_id: {item.unique_id}"
            
            # Look up ASIN from asin_bank by lead_id and size
            asin_record = self.db.query(AsinBank).filter(
                AsinBank.lead_id == oa_sourcing.lead_id,
                AsinBank.size == item.size
            ).first()
            
            if not asin_record:
                logger.warning(
                    f"No ASIN found for lead_id={oa_sourcing.lead_id}, size={item.size}. "
                    f"Creating record without ASIN."
                )
            
            # Calculate FBA MSKU: {size}-{sku_upc}-{order_number}
            sku_upc = oa_sourcing.product_sku or "UNKNOWN"
            fba_msku = f"{item.size}-{sku_upc}-{order_number}"
            
            # Create purchase tracker record
            purchase_record = PurchaseTracker(
                # Foreign keys
                oa_sourcing_id=oa_sourcing.id,
                asin_bank_id=asin_record.id if asin_record else None,
                
                # Denormalized for performance
                lead_id=oa_sourcing.lead_id,
                
                # Purchase metadata
                date=date.today(),
                platform="AMZ",  # Selling platform (Amazon)
                order_number=order_number,
                
                # Quantities
                og_qty=item.quantity,
                final_qty=item.quantity,
                
                # Pricing - use from oa_sourcing
                rsp=oa_sourcing.rsp,
                
                # FBA fields
                fba_msku=fba_msku,
                
                # Status
                status="Ordered",
                
                # Audit
                audited=False
            )
            
            self.db.add(purchase_record)
            
            logger.info(
                f"Created purchase tracker record: "
                f"lead_id={oa_sourcing.lead_id}, "
                f"product={oa_sourcing.product_name}, "
                f"size={item.size}, "
                f"qty={item.quantity}, "
                f"asin={asin_record.asin if asin_record else 'N/A'}, "
                f"msku={fba_msku}"
            )
            
            return True, None
        
        except Exception as e:
            error_msg = f"Error creating purchase tracker record: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
    
    def _add_processed_label(self, message_id: str) -> None:
        """Add 'Processed' label to a message"""
        if self.processed_label:
            self.gmail_service.add_label_to_message(message_id, self.processed_label['id'])
    
    def _add_error_label(self, message_id: str) -> None:
        """Add 'Error' label to a message"""
        if self.error_label:
            self.gmail_service.add_label_to_message(message_id, self.error_label['id'])
    
    def _process_hibbett_order(self, order_data: HibbettOrderData) -> Tuple[bool, Optional[str]]:
        """
        Process a Hibbett order and create purchase tracker records.
        
        Args:
            order_data: Parsed order data
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Get Hibbett retailer
            hibbett_retailer = self.db.query(Retailer).filter(
                Retailer.name.ilike('%Hibbett%')
            ).first()
            
            if not hibbett_retailer:
                return False, "Hibbett retailer not found in database"
            
            created_count = 0
            skipped_count = 0
            
            for item in order_data.items:
                success, error = self._create_purchase_tracker_record_hibbett(
                    order_number=order_data.order_number,
                    item=item,
                    retailer=hibbett_retailer
                )
                
                if success:
                    created_count += 1
                else:
                    logger.warning(f"Could not create record for item {item.unique_id}: {error}")
                    skipped_count += 1
            
            # Commit all changes
            self.db.commit()
            
            if created_count == 0:
                return False, f"No purchase tracker records created (skipped: {skipped_count})"
            
            logger.info(f"Created {created_count} purchase tracker records for order {order_data.order_number}")
            
            if skipped_count > 0:
                logger.warning(f"Skipped {skipped_count} items (no matching OA sourcing lead)")
            
            return True, None
        
        except Exception as e:
            self.db.rollback()
            error_msg = f"Error processing order {order_data.order_number}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
    
    def _create_purchase_tracker_record_hibbett(
        self,
        order_number: str,
        item: HibbettOrderItem,
        retailer: Retailer
    ) -> Tuple[bool, Optional[str]]:
        """
        Create a purchase tracker record for a single Hibbett item.
        
        Args:
            order_number: Order number
            item: Order item data
            retailer: Retailer object
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Look up OA sourcing by unique_id
            oa_sourcing = self.db.query(OASourcing).filter(
                OASourcing.unique_id == item.unique_id
            ).first()
            
            if not oa_sourcing:
                return False, f"No OA sourcing lead found for unique_id: {item.unique_id}"
            
            # Look up ASIN from asin_bank by lead_id and size
            asin_record = self.db.query(AsinBank).filter(
                AsinBank.lead_id == oa_sourcing.lead_id,
                AsinBank.size == item.size
            ).first()
            
            if not asin_record:
                logger.warning(
                    f"No ASIN found for lead_id={oa_sourcing.lead_id}, size={item.size}. "
                    f"Creating record without ASIN."
                )
            
            # Calculate FBA MSKU: {size}-{sku_upc}-{order_number}
            sku_upc = oa_sourcing.product_sku or "UNKNOWN"
            fba_msku = f"{item.size}-{sku_upc}-{order_number}"
            
            # Create purchase tracker record
            purchase_record = PurchaseTracker(
                # Foreign keys
                oa_sourcing_id=oa_sourcing.id,
                asin_bank_id=asin_record.id if asin_record else None,
                
                # Denormalized for performance
                lead_id=oa_sourcing.lead_id,
                
                # Purchase metadata
                date=date.today(),
                platform="AMZ",  # Selling platform (Amazon)
                order_number=order_number,
                
                # Quantities
                og_qty=item.quantity,
                final_qty=item.quantity,
                
                # Pricing - use from oa_sourcing
                rsp=oa_sourcing.rsp,
                
                # FBA fields
                fba_msku=fba_msku,
                
                # Status
                status="Ordered",
                
                # Audit
                audited=False
            )
            
            self.db.add(purchase_record)
            
            logger.info(
                f"Created purchase tracker record: "
                f"lead_id={oa_sourcing.lead_id}, "
                f"product={oa_sourcing.product_name}, "
                f"size={item.size}, "
                f"qty={item.quantity}, "
                f"asin={asin_record.asin if asin_record else 'N/A'}, "
                f"msku={fba_msku}"
            )
            
            return True, None
        
        except Exception as e:
            error_msg = f"Error creating purchase tracker record: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
    
    def _process_shoepalace_order(self, order_data: ShoepalaceOrderData) -> Tuple[bool, Optional[str]]:
        """
        Process a Shoe Palace order and create purchase tracker records.
        
        Args:
            order_data: Parsed order data
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Get Shoe Palace retailer
            shoepalace_retailer = self.db.query(Retailer).filter(
                Retailer.name.ilike('%Shoe Palace%') | Retailer.name.ilike('%Shoepalace%')
            ).first()
            
            if not shoepalace_retailer:
                return False, "Shoe Palace retailer not found in database"
            
            created_count = 0
            skipped_count = 0
            
            for item in order_data.items:
                success, error = self._create_purchase_tracker_record_shoepalace(
                    order_number=order_data.order_number,
                    item=item,
                    retailer=shoepalace_retailer
                )
                
                if success:
                    created_count += 1
                else:
                    logger.warning(f"Could not create record for item {item.unique_id}: {error}")
                    skipped_count += 1
            
            # Commit all changes
            self.db.commit()
            
            if created_count == 0:
                return False, f"No purchase tracker records created (skipped: {skipped_count})"
            
            logger.info(f"Created {created_count} purchase tracker records for order {order_data.order_number}")
            
            if skipped_count > 0:
                logger.warning(f"Skipped {skipped_count} items (no matching OA sourcing lead)")
            
            return True, None
        
        except Exception as e:
            self.db.rollback()
            error_msg = f"Error processing order {order_data.order_number}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
    
    def _create_purchase_tracker_record_shoepalace(
        self,
        order_number: str,
        item: ShoepalaceOrderItem,
        retailer: Retailer
    ) -> Tuple[bool, Optional[str]]:
        """
        Create a purchase tracker record for a single Shoe Palace item.
        
        Args:
            order_number: Order number
            item: Order item data
            retailer: Retailer object
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Look up OA sourcing by unique_id
            oa_sourcing = self.db.query(OASourcing).filter(
                OASourcing.unique_id == item.unique_id
            ).first()
            
            if not oa_sourcing:
                return False, f"No OA sourcing lead found for unique_id: {item.unique_id}"
            
            # Look up ASIN from asin_bank by lead_id and size
            asin_record = self.db.query(AsinBank).filter(
                AsinBank.lead_id == oa_sourcing.lead_id,
                AsinBank.size == item.size
            ).first()
            
            if not asin_record:
                logger.warning(
                    f"No ASIN found for lead_id={oa_sourcing.lead_id}, size={item.size}. "
                    f"Creating record without ASIN."
                )
            
            # Calculate FBA MSKU: {size}-{sku_upc}-{order_number}
            sku_upc = oa_sourcing.product_sku or "UNKNOWN"
            fba_msku = f"{item.size}-{sku_upc}-{order_number}"
            
            # Create purchase tracker record
            purchase_record = PurchaseTracker(
                # Foreign keys
                oa_sourcing_id=oa_sourcing.id,
                asin_bank_id=asin_record.id if asin_record else None,
                
                # Denormalized for performance
                lead_id=oa_sourcing.lead_id,
                
                # Purchase metadata
                date=date.today(),
                platform="AMZ",  # Selling platform (Amazon)
                order_number=order_number,
                
                # Quantities
                og_qty=item.quantity,
                final_qty=item.quantity,
                
                # Pricing - use from oa_sourcing
                rsp=oa_sourcing.rsp,
                
                # FBA fields
                fba_msku=fba_msku,
                
                # Status
                status="Ordered",
                
                # Audit
                audited=False
            )
            
            self.db.add(purchase_record)
            
            logger.info(
                f"Created purchase tracker record: "
                f"lead_id={oa_sourcing.lead_id}, "
                f"product={oa_sourcing.product_name}, "
                f"size={item.size}, "
                f"qty={item.quantity}, "
                f"asin={asin_record.asin if asin_record else 'N/A'}, "
                f"msku={fba_msku}"
            )
            
            return True, None
        
        except Exception as e:
            error_msg = f"Error creating purchase tracker record: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
    
    def _process_snipes_order(self, order_data: SnipesOrderData) -> Tuple[bool, Optional[str]]:
        """
        Process a Snipes order and create purchase tracker records.
        
        Args:
            order_data: Parsed order data
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Get Snipes retailer
            snipes_retailer = self.db.query(Retailer).filter(
                Retailer.name.ilike('%Snipes%')
            ).first()
            
            if not snipes_retailer:
                return False, "Snipes retailer not found in database"
            
            created_count = 0
            skipped_count = 0
            
            for item in order_data.items:
                success, error = self._create_purchase_tracker_record_snipes(
                    order_number=order_data.order_number,
                    item=item,
                    retailer=snipes_retailer
                )
                
                if success:
                    created_count += 1
                else:
                    logger.warning(f"Could not create record for item {item.unique_id}: {error}")
                    skipped_count += 1
            
            # Commit all changes
            self.db.commit()
            
            if created_count == 0:
                return False, f"No purchase tracker records created (skipped: {skipped_count})"
            
            logger.info(f"Created {created_count} purchase tracker records for order {order_data.order_number}")
            
            if skipped_count > 0:
                logger.warning(f"Skipped {skipped_count} items (no matching OA sourcing lead)")
            
            return True, None
        
        except Exception as e:
            self.db.rollback()
            error_msg = f"Error processing order {order_data.order_number}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
    
    def _create_purchase_tracker_record_snipes(
        self,
        order_number: str,
        item: SnipesOrderItem,
        retailer: Retailer
    ) -> Tuple[bool, Optional[str]]:
        """
        Create a purchase tracker record for a Snipes order item.
        
        Args:
            order_number: Order number
            item: Snipes order item
            retailer: Snipes retailer record
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Find matching OA Sourcing lead by unique_id and size
            oa_sourcing = self.db.query(OASourcing).filter(
                OASourcing.unique_id == item.unique_id,
                OASourcing.size == item.size
            ).first()
            
            if not oa_sourcing:
                return False, f"No matching OA sourcing lead found for unique_id={item.unique_id}, size={item.size}"
            
            # Get ASIN if available
            asin_record = self.db.query(AsinBank).filter(
                AsinBank.lead_id == oa_sourcing.lead_id
            ).first()
            
            # Generate FBA MSKU
            fba_msku = f"{oa_sourcing.lead_id}-FBA"
            
            # Create purchase tracker record
            purchase_record = PurchaseTracker(
                lead_id=oa_sourcing.lead_id,
                unique_id=item.unique_id,
                product_name=item.product_name or oa_sourcing.product_name,
                size=item.size,
                retailer_id=retailer.retailer_id,
                order_number=order_number,
                order_date=date.today(),
                purchase_quantity=item.quantity,
                asin=asin_record.asin if asin_record else None,
                fba_msku=fba_msku,
                platform="AMZ"  # Selling platform (Amazon)
            )
            
            self.db.add(purchase_record)
            
            logger.info(
                f"Created Snipes purchase tracker record: "
                f"lead_id={oa_sourcing.lead_id}, "
                f"product={oa_sourcing.product_name}, "
                f"size={item.size}, "
                f"qty={item.quantity}, "
                f"asin={asin_record.asin if asin_record else 'N/A'}, "
                f"msku={fba_msku}"
            )
            
            return True, None
        
        except Exception as e:
            error_msg = f"Error creating purchase tracker record: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
    
    def _process_finishline_order(self, order_data: FinishLineOrderData) -> Tuple[bool, Optional[str]]:
        """
        Process a Finish Line order and create purchase tracker records.
        
        Args:
            order_data: Parsed order data
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Get Finish Line retailer
            finishline_retailer = self.db.query(Retailer).filter(
                Retailer.name.ilike('%Finish Line%') | Retailer.name.ilike('%Finishline%')
            ).first()
            
            if not finishline_retailer:
                return False, "Finish Line retailer not found in database"
            
            created_count = 0
            skipped_count = 0
            
            for item in order_data.items:
                success, error = self._create_purchase_tracker_record_finishline(
                    order_number=order_data.order_number,
                    item=item,
                    retailer=finishline_retailer
                )
                
                if success:
                    created_count += 1
                else:
                    logger.warning(f"Could not create record for item {item.unique_id}: {error}")
                    skipped_count += 1
            
            # Commit all changes
            self.db.commit()
            
            if created_count == 0:
                return False, f"No purchase tracker records created (skipped: {skipped_count})"
            
            logger.info(f"Created {created_count} purchase tracker records for order {order_data.order_number}")
            
            if skipped_count > 0:
                logger.warning(f"Skipped {skipped_count} items (no matching OA sourcing lead)")
            
            return True, None
        
        except Exception as e:
            self.db.rollback()
            error_msg = f"Error processing order {order_data.order_number}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
    
    def _create_purchase_tracker_record_finishline(
        self,
        order_number: str,
        item: FinishLineOrderItem,
        retailer: Retailer
    ) -> Tuple[bool, Optional[str]]:
        """
        Create a purchase tracker record for a Finish Line order item.
        
        Args:
            order_number: Order number
            item: Finish Line order item
            retailer: Finish Line retailer record
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Look up OA sourcing by unique_id only
            oa_sourcing = self.db.query(OASourcing).filter(
                OASourcing.unique_id == item.unique_id
            ).first()
            
            if not oa_sourcing:
                return False, f"No OA sourcing lead found for unique_id: {item.unique_id}"
            
            # Look up ASIN from asin_bank by lead_id and size
            asin_record = self.db.query(AsinBank).filter(
                AsinBank.lead_id == oa_sourcing.lead_id,
                AsinBank.size == item.size
            ).first()
            
            if not asin_record:
                logger.warning(
                    f"No ASIN found for lead_id={oa_sourcing.lead_id}, size={item.size}. "
                    f"Creating record without ASIN."
                )
            
            # Calculate FBA MSKU: {size}-{sku_upc}-{order_number}
            sku_upc = oa_sourcing.product_sku or "UNKNOWN"
            fba_msku = f"{item.size}-{sku_upc}-{order_number}"
            
            # Create purchase tracker record
            purchase_record = PurchaseTracker(
                # Foreign keys
                oa_sourcing_id=oa_sourcing.id,
                asin_bank_id=asin_record.id if asin_record else None,
                
                # Denormalized for performance
                lead_id=oa_sourcing.lead_id,
                unique_id=item.unique_id,
                product_name=item.product_name or oa_sourcing.product_name,
                size=item.size,
                retailer_id=retailer.id,
                order_number=order_number,
                order_date=date.today(),
                purchase_quantity=item.quantity,
                asin=asin_record.asin if asin_record else None,
                fba_msku=fba_msku,
                platform="AMZ"  # Selling platform (Amazon)
            )
            
            self.db.add(purchase_record)
            
            logger.info(
                f"Created Finish Line purchase tracker record: "
                f"lead_id={oa_sourcing.lead_id}, "
                f"product={oa_sourcing.product_name}, "
                f"size={item.size}, "
                f"qty={item.quantity}, "
                f"asin={asin_record.asin if asin_record else 'N/A'}, "
                f"msku={fba_msku}"
            )
            
            return True, None
        
        except Exception as e:
            error_msg = f"Error creating purchase tracker record: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
    
    def _process_shopsimon_order(self, order_data: ShopSimonOrderData) -> Tuple[bool, Optional[str]]:
        """
        Process a ShopSimon order and create purchase tracker records.
        
        Args:
            order_data: Parsed order data
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Get ShopSimon retailer
            shopsimon_retailer = self.db.query(Retailer).filter(
                Retailer.name.ilike('%ShopSimon%') | Retailer.name.ilike('%Shop Simon%')
            ).first()
            
            if not shopsimon_retailer:
                return False, "ShopSimon retailer not found in database"
            
            created_count = 0
            skipped_count = 0
            
            for item in order_data.items:
                success, error = self._create_purchase_tracker_record_shopsimon(
                    order_number=order_data.order_number,
                    item=item,
                    retailer=shopsimon_retailer
                )
                
                if success:
                    created_count += 1
                else:
                    logger.warning(f"Could not create record for item {item.unique_id}: {error}")
                    skipped_count += 1
            
            # Commit all changes
            self.db.commit()
            
            if created_count == 0:
                return False, f"No purchase tracker records created (skipped: {skipped_count})"
            
            logger.info(f"Created {created_count} purchase tracker records for order {order_data.order_number}")
            
            if skipped_count > 0:
                logger.warning(f"Skipped {skipped_count} items (no matching OA sourcing lead)")
            
            return True, None
        
        except Exception as e:
            self.db.rollback()
            error_msg = f"Error processing order {order_data.order_number}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
    
    def _create_purchase_tracker_record_shopsimon(
        self,
        order_number: str,
        item: ShopSimonOrderItem,
        retailer: Retailer
    ) -> Tuple[bool, Optional[str]]:
        """
        Create a purchase tracker record for a ShopSimon order item.
        
        Args:
            order_number: Order number
            item: ShopSimon order item
            retailer: ShopSimon retailer record
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Look up OA sourcing by unique_id only
            oa_sourcing = self.db.query(OASourcing).filter(
                OASourcing.unique_id == item.unique_id
            ).first()
            
            if not oa_sourcing:
                return False, f"No OA sourcing lead found for unique_id: {item.unique_id}"
            
            # Look up ASIN from asin_bank by lead_id and size
            asin_record = self.db.query(AsinBank).filter(
                AsinBank.lead_id == oa_sourcing.lead_id,
                AsinBank.size == item.size
            ).first()
            
            if not asin_record:
                logger.warning(
                    f"No ASIN found for lead_id={oa_sourcing.lead_id}, size={item.size}. "
                    f"Creating record without ASIN."
                )
            
            # Calculate FBA MSKU: {size}-{sku_upc}-{order_number}
            sku_upc = oa_sourcing.product_sku or "UNKNOWN"
            fba_msku = f"{item.size}-{sku_upc}-{order_number}"
            
            # Create purchase tracker record
            purchase_record = PurchaseTracker(
                # Foreign keys
                oa_sourcing_id=oa_sourcing.id,
                asin_bank_id=asin_record.id if asin_record else None,
                
                # Denormalized for performance
                lead_id=oa_sourcing.lead_id,
                unique_id=item.unique_id,
                product_name=item.product_name or oa_sourcing.product_name,
                size=item.size,
                retailer_id=retailer.id,
                order_number=order_number,
                order_date=date.today(),
                purchase_quantity=item.quantity,
                asin=asin_record.asin if asin_record else None,
                fba_msku=fba_msku,
                platform="AMZ"  # Selling platform (Amazon)
            )
            
            self.db.add(purchase_record)
            
            logger.info(
                f"Created ShopSimon purchase tracker record: "
                f"lead_id={oa_sourcing.lead_id}, "
                f"product={oa_sourcing.product_name}, "
                f"size={item.size}, "
                f"qty={item.quantity}, "
                f"asin={asin_record.asin if asin_record else 'N/A'}, "
                f"msku={fba_msku}"
            )
            
            return True, None
        
        except Exception as e:
            error_msg = f"Error creating purchase tracker record: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
    
    def process_single_email(
        self,
        email_data: EmailData,
        message_id: str,
        retailer_name: str
    ) -> dict:
        """
        Process a single retailer order confirmation email.
        Used by the webhook for automatic processing.
        
        Args:
            email_data: EmailData object containing email information
            message_id: Gmail message ID
            retailer_name: Name of the retailer (footlocker, champs, dicks, etc.)
        
        Returns:
            Dictionary with processing results:
            {
                'success': bool,
                'order_number': str,
                'items_count': int,
                'error': str (if failed)
            }
        """
        try:
            # Map retailer name to parser and processor
            retailer_map = {
                'footlocker': {
                    'parser': self.footlocker_parser,
                    'processor': self._process_order
                },
                'champs': {
                    'parser': self.champs_parser,
                    'processor': self._process_champs_order
                },
                'dicks': {
                    'parser': self.dicks_parser,
                    'processor': self._process_dicks_order
                },
                'hibbett': {
                    'parser': self.hibbett_parser,
                    'processor': self._process_hibbett_order
                },
                'shoepalace': {
                    'parser': self.shoepalace_parser,
                    'processor': self._process_shoepalace_order
                },
                'snipes': {
                    'parser': self.snipes_parser,
                    'processor': self._process_snipes_order
                },
                'finishline': {
                    'parser': self.finishline_parser,
                    'processor': self._process_finishline_order
                },
                'shopsimon': {
                    'parser': self.shopsimon_parser,
                    'processor': self._process_shopsimon_order
                }
            }
            
            retailer_config = retailer_map.get(retailer_name)
            if not retailer_config:
                return {
                    'success': False,
                    'error': f"Unknown retailer: {retailer_name}"
                }
            
            parser = retailer_config['parser']
            processor = retailer_config['processor']
            
            # Parse order details
            order_data = parser.parse_email(email_data)
            if not order_data:
                self._add_error_label(message_id)
                return {
                    'success': False,
                    'error': f"Failed to parse {retailer_name} order from email"
                }
            
            # Check for duplicate order
            if self._is_order_duplicate(order_data.order_number):
                logger.info(f"Order {order_data.order_number} already exists - skipping")
                self._add_processed_label(message_id)
                return {
                    'success': True,
                    'order_number': order_data.order_number,
                    'items_count': len(order_data.items),
                    'duplicate': True
                }
            
            # Process the order and create purchase tracker records
            success, error_msg = processor(order_data)
            
            if success:
                self.db.commit()
                self._add_processed_label(message_id)
                return {
                    'success': True,
                    'order_number': order_data.order_number,
                    'items_count': len(order_data.items)
                }
            else:
                self.db.rollback()
                self._add_error_label(message_id)
                return {
                    'success': False,
                    'order_number': order_data.order_number,
                    'error': error_msg
                }
        
        except Exception as e:
            error_msg = f"Error processing {retailer_name} email {message_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.db.rollback()
            self._add_error_label(message_id)
            return {
                'success': False,
                'error': error_msg
            }

