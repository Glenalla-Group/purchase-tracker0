"""
Retailer Order Processor Service
Processes order confirmation emails from retailers and creates purchase tracker records
"""

import logging
import re
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.services.gmail_service import GmailService
from app.services.footlocker_parser import FootlockerEmailParser, FootlockerOrderData, FootlockerOrderItem
from app.services.champs_parser import ChampsEmailParser, ChampsOrderData, ChampsOrderItem
from app.services.dicks_parser import DicksEmailParser, DicksOrderData, DicksOrderItem
from app.services.hibbett_parser import HibbettEmailParser, HibbettOrderData, HibbettOrderItem
from app.services.shoepalace_parser import ShoepalaceEmailParser, ShoepalaceOrderData, ShoepalaceOrderItem
from app.services.snipes_parser import SnipesEmailParser, SnipesOrderData, SnipesOrderItem
from app.services.finishline_parser import FinishLineEmailParser, FinishLineOrderData, FinishLineOrderItem
from app.services.shopsimon_parser import ShopSimonEmailParser, ShopSimonOrderData, ShopSimonOrderItem
from app.services.jdsports_parser import JDSportsEmailParser, JDSportsOrderData, JDSportsOrderItem
from app.services.revolve_parser import RevolveEmailParser, RevolveOrderData, RevolveOrderItem
from app.services.asos_parser import ASOSEmailParser, ASOSOrderData, ASOSOrderItem
from app.services.dtlr_parser import DTLREmailParser, DTLROrderData, DTLROrderItem
from app.services.endclothing_parser import ENDClothingEmailParser, ENDClothingOrderData, ENDClothingOrderItem
from app.services.shopwss_parser import ShopWSSEmailParser, ShopWSSOrderData, ShopWSSOrderItem
from app.services.on_parser import OnEmailParser, OnOrderData, OnOrderItem
from app.services.urban_parser import UrbanOutfittersEmailParser, UrbanOrderData, UrbanOrderItem
from app.services.bloomingdales_parser import BloomingdalesEmailParser, BloomingdalesOrderData, BloomingdalesOrderItem
from app.services.anthropologie_parser import AnthropologieEmailParser, AnthropologieOrderData, AnthropologieOrderItem
from app.services.nike_parser import NikeEmailParser, NikeOrderData, NikeOrderItem
from app.services.carbon38_parser import Carbon38EmailParser, Carbon38OrderData, Carbon38OrderItem
from app.services.gazelle_parser import GazelleEmailParser, GazelleOrderData, GazelleOrderItem
from app.services.netaporter_parser import NetAPorterEmailParser, NetAPorterOrderData, NetAPorterOrderItem
from app.services.fit2run_parser import Fit2RunEmailParser, Fit2RunOrderData, Fit2RunOrderItem
from app.services.sns_parser import SNSEmailParser, SNSOrderData, SNSOrderItem
from app.services.adidas_parser import AdidasEmailParser, AdidasOrderData, AdidasOrderItem
from app.services.concepts_parser import ConceptsEmailParser, ConceptsOrderData, ConceptsOrderItem
from app.services.sneaker_parser import SneakerPoliticsEmailParser, SneakerOrderData, SneakerOrderItem
from app.services.orleans_parser import OrleansEmailParser, OrleansOrderData, OrleansOrderItem
from app.models.database import AsinBank, OASourcing, PurchaseTracker, Retailer
from app.models.email import EmailData
from app.utils.purchase_status import calculate_status_and_location

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
        self.jdsports_parser = JDSportsEmailParser()
        self.revolve_parser = RevolveEmailParser()
        self.asos_parser = ASOSEmailParser()
        self.dtlr_parser = DTLREmailParser()
        self.endclothing_parser = ENDClothingEmailParser()
        self.shopwss_parser = ShopWSSEmailParser()
        self.on_parser = OnEmailParser()
        self.urban_parser = UrbanOutfittersEmailParser()
        self.bloomingdales_parser = BloomingdalesEmailParser()
        self.anthropologie_parser = AnthropologieEmailParser()
        self.nike_parser = NikeEmailParser()
        self.carbon38_parser = Carbon38EmailParser()
        self.gazelle_parser = GazelleEmailParser()
        self.netaporter_parser = NetAPorterEmailParser()
        self.fit2run_parser = Fit2RunEmailParser()
        self.sns_parser = SNSEmailParser()
        self.adidas_parser = AdidasEmailParser()
        self.concepts_parser = ConceptsEmailParser()
        self.sneaker_parser = SneakerPoliticsEmailParser()
        self.orleans_parser = OrleansEmailParser()
        
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
            # Use environment-aware email address and subject pattern
            from_email = self.footlocker_parser.order_from_email
            subject_query = self.footlocker_parser.order_subject_query
            query = f'from:{from_email} subject:"{subject_query}" -label:{self.PROCESSED_LABEL}'
            
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
                    
                    # Process the order: upsert (create or update) purchase tracker records
                    # For existing orders, we update og_qty and final_qty from the confirmation email
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
            # Use environment-aware email address and subject pattern
            from_email = self.champs_parser.order_from_email
            subject_query = self.champs_parser.order_subject_query
            query = f'from:{from_email} subject:"{subject_query}" -label:{self.PROCESSED_LABEL}'
            
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
            # Use environment-aware email address and subject pattern
            from_email = self.dicks_parser.order_from_email
            subject_query = self.dicks_parser.order_subject_query
            query = f'from:{from_email} subject:"{subject_query}" -label:{self.PROCESSED_LABEL}'
            
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
            # Use environment-aware email address and subject pattern
            from_email = self.hibbett_parser.order_from_email
            subject_query = self.hibbett_parser.order_subject_query
            query = f'from:{from_email} subject:"{subject_query}" -label:{self.PROCESSED_LABEL}'
            
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
            # Use environment-aware email address and subject pattern
            from_email = self.shoepalace_parser.order_from_email
            subject_query = self.shoepalace_parser.order_subject_query
            query = f'from:{from_email} subject:"{subject_query}" -label:{self.PROCESSED_LABEL}'
            
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
            # Use environment-aware email address and subject pattern
            from_email = self.snipes_parser.order_from_email
            subject_query = self.snipes_parser.order_subject_query
            query = f'from:{from_email} subject:"{subject_query}" -label:{self.PROCESSED_LABEL}'
            
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
            # Use environment-aware email address and subject pattern
            from_email = self.finishline_parser.order_from_email
            subject_query = self.finishline_parser.order_subject_query
            query = f'from:{from_email} subject:"{subject_query}" -label:{self.PROCESSED_LABEL}'
            
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
        Process a Footlocker order: upsert purchase tracker records.
        
        For each product (unique_id + size):
        - If record exists: update og_qty and final_qty from confirmation email
        - If not exists: create new record with og_qty and final_qty from email
        
        Product matching: order_number + unique_id + size
        
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
            updated_count = 0
            skipped_count = 0
            
            for item in order_data.items:
                success, action = self._create_or_update_purchase_tracker_record(
                    order_number=order_data.order_number,
                    item=item,
                    retailer=footlocker_retailer,
                    shipping_address=order_data.shipping_address,
                    order_datetime=getattr(order_data, 'order_datetime', None)
                )
                
                if success and action == 'created':
                    created_count += 1
                elif success and action == 'updated':
                    updated_count += 1
                elif not success:
                    logger.warning(f"Could not process item {item.unique_id} size {item.size}: {action}")
                    skipped_count += 1
            
            # Commit all changes
            self.db.commit()
            
            if created_count == 0 and updated_count == 0:
                return False, f"No purchase tracker records created or updated (skipped: {skipped_count})"
            
            logger.info(
                f"Processed order {order_data.order_number}: "
                f"created {created_count}, updated {updated_count}, skipped {skipped_count}"
            )
            
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
                    retailer=champs_retailer,
                    shipping_address=order_data.shipping_address,
                    order_datetime=getattr(order_data, 'order_datetime', None)
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
                    retailer=dicks_retailer,
                    shipping_address=order_data.shipping_address
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
    
    def _normalize_size(self, size: str) -> str:
        """
        Normalize size for comparison (handles "11.0" vs "11" etc.)
        
        Args:
            size: Size string (e.g., "11.0", "11", "9.5")
        
        Returns:
            Normalized size string
        """
        if size is None:
            return ""
        size = str(size).strip()
        if not size:
            return size
        
        # Convert "11.0" to "11", "09.5" to "9.5", etc.
        if re.match(r'^\d{1,2}\.\d$', size):
            num = float(size)
            return str(int(num)) if num % 1 == 0 else str(num)
        # Strip leading zeros from whole numbers: "09" -> "9"
        if re.match(r'^\d{1,2}$', size):
            return str(int(size))
        
        return size
    
    def _get_asin_for_lead_and_size(self, lead_id: str, size: str, oa_sourcing=None):
        """
        Look up AsinBank record by lead_id and size, using normalized size comparison.
        Handles format mismatches (e.g., "9" vs "9.0", "09" vs "9").
        
        Lookup order (prioritize OASourcing link - source of truth for "this lead uses these ASINs"):
        1. OASourcing's linked asin1_id..asin15_id: query by id, match size (covers reused ASINs
           from create_lead which keep original lead_id, and "Add ASIN to lead")
        2. AsinBank by lead_id + size (exact then normalized)
        
        Returns:
            AsinBank record or None
        """
        normalized_input = self._normalize_size(str(size) if size is not None else "")
        
        # 1. OASourcing's linked ASINs - canonical link (covers reused ASINs with different lead_id)
        if oa_sourcing:
            for i in range(1, 16):
                asin_id = getattr(oa_sourcing, f'asin{i}_id', None)
                if asin_id:
                    asin_rec = self.db.query(AsinBank).filter(AsinBank.id == asin_id).first()
                    if asin_rec and asin_rec.size:
                        if self._normalize_size(str(asin_rec.size)) == normalized_input:
                            return asin_rec
        
        # 2. AsinBank by lead_id (exact match)
        asin_record = self.db.query(AsinBank).filter(
            AsinBank.lead_id == lead_id,
            AsinBank.size == str(size) if size is not None else None
        ).first()
        if asin_record:
            return asin_record
        
        # 3. AsinBank by lead_id + normalized size match
        records = self.db.query(AsinBank).filter(AsinBank.lead_id == lead_id).all()
        for r in records:
            if r.size and self._normalize_size(str(r.size)) == normalized_input:
                return r
        
        return None
    
    def _create_or_update_purchase_tracker_record(
        self,
        order_number: str,
        item: FootlockerOrderItem,
        retailer: Retailer,
        shipping_address: str = "",
        order_datetime: Optional[datetime] = None
    ) -> Tuple[bool, str]:
        """
        Create or update purchase tracker record for a single item.
        
        Match by order_number + unique_id + size. If exists, update og_qty and final_qty.
        If not exists, create new record.
        
        Returns:
            Tuple of (success, action) where action is 'created', 'updated', or error message
        """
        normalized_size = self._normalize_size(item.size)
        
        # Find existing record by order_number, unique_id (via OASourcing), and size
        existing = self.db.query(PurchaseTracker).join(
            OASourcing, PurchaseTracker.oa_sourcing_id == OASourcing.id
        ).outerjoin(
            AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
        ).filter(
            and_(
                PurchaseTracker.order_number == order_number,
                OASourcing.unique_id == item.unique_id,
                or_(
                    AsinBank.size == item.size,
                    AsinBank.size == normalized_size
                )
            )
        ).first()
        
        # Fallback: manual size normalization for DB records with different format
        if not existing:
            all_for_order = self.db.query(PurchaseTracker).join(
                OASourcing, PurchaseTracker.oa_sourcing_id == OASourcing.id
            ).outerjoin(
                AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
            ).filter(
                and_(
                    PurchaseTracker.order_number == order_number,
                    OASourcing.unique_id == item.unique_id
                )
            ).all()
            
            for record in all_for_order:
                db_size = record.asin_bank_ref.size if record.asin_bank_ref else None
                if db_size and self._normalize_size(db_size) == normalized_size:
                    existing = record
                    break
        
        if existing:
            # Update og_qty and final_qty from confirmation email
            existing.og_qty = item.quantity
            existing.final_qty = item.quantity
            logger.info(
                f"Updated purchase tracker ID {existing.id}: "
                f"order={order_number}, unique_id={item.unique_id}, size={item.size}, "
                f"og_qty={item.quantity}, final_qty={item.quantity}"
            )
            return (True, 'updated')
        
        # Create new record
        success, error = self._create_purchase_tracker_record(
            order_number=order_number,
            item=item,
            retailer=retailer,
            shipping_address=shipping_address,
            order_datetime=order_datetime
        )
        return (success, 'created') if success else (False, error or 'Create failed')
    
    def _create_purchase_tracker_record(
        self,
        order_number: str,
        item: FootlockerOrderItem,
        retailer: Retailer,
        shipping_address: str = "",
        order_datetime: Optional[datetime] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Create a purchase tracker record for a single item.
        
        Args:
            order_number: Order number
            item: Order item data
            retailer: Retailer object
            shipping_address: Normalized shipping address
        
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
            
            # Look up ASIN from asin_bank by lead_id and size (with size normalization + OASourcing fallback)
            asin_record = self._get_asin_for_lead_and_size(oa_sourcing.lead_id, item.size, oa_sourcing=oa_sourcing)
            
            if not asin_record:
                asin_count = self.db.query(AsinBank).filter(AsinBank.lead_id == oa_sourcing.lead_id).count()
                logger.warning(
                    f"No ASIN found for lead_id={oa_sourcing.lead_id}, size={item.size}. "
                    f"Creating record without ASIN. (AsinBank has {asin_count} records for this lead. "
                    f"Add via: POST /leads/{{lead_id}}/asins or POST /asin-bank)"
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
                date=order_datetime or datetime.utcnow(),
                platform="AMZ",  # Selling platform (Amazon)
                order_number=order_number,
                address=shipping_address,
                # Quantities
                og_qty=item.quantity,
                final_qty=item.quantity,
                
                # Pricing - use from oa_sourcing
                rsp=oa_sourcing.rsp,
                
                # FBA fields
                fba_msku=fba_msku,
                
                # Status and Location - set to Pending/Retailer for new purchases
                status="Pending",
                location="Retailer",
                
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
                    retailer=shoepalace_retailer,
                    shipping_address=order_data.shipping_address
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
        retailer: Retailer,
        shipping_address: str = ""
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
            
            # Look up ASIN from asin_bank by lead_id and size (with size normalization + OASourcing fallback)
            asin_record = self._get_asin_for_lead_and_size(oa_sourcing.lead_id, item.size, oa_sourcing=oa_sourcing)
            
            if not asin_record:
                asin_count = self.db.query(AsinBank).filter(AsinBank.lead_id == oa_sourcing.lead_id).count()
                logger.warning(
                    f"No ASIN found for lead_id={oa_sourcing.lead_id}, size={item.size}. "
                    f"Creating record without ASIN. (AsinBank has {asin_count} records for this lead. "
                    f"Add via: POST /leads/{{lead_id}}/asins or POST /asin-bank)"
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
                date=datetime.utcnow(),
                platform="AMZ",  # Selling platform (Amazon)
                order_number=order_number,
                address=shipping_address,
                # Quantities
                og_qty=item.quantity,
                final_qty=item.quantity,
                
                # Pricing - use from oa_sourcing
                rsp=oa_sourcing.rsp,
                
                # FBA fields
                fba_msku=fba_msku,
                
                # Status and Location - set to Pending/Retailer for new purchases
                status="Pending",
                location="Retailer",
                
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
        retailer: Retailer,
        shipping_address: str = "",
        order_datetime: Optional[datetime] = None
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
            
            # Look up ASIN from asin_bank by lead_id and size (with size normalization + OASourcing fallback)
            asin_record = self._get_asin_for_lead_and_size(oa_sourcing.lead_id, item.size, oa_sourcing=oa_sourcing)
            
            if not asin_record:
                asin_count = self.db.query(AsinBank).filter(AsinBank.lead_id == oa_sourcing.lead_id).count()
                logger.warning(
                    f"No ASIN found for lead_id={oa_sourcing.lead_id}, size={item.size}. "
                    f"Creating record without ASIN. (AsinBank has {asin_count} records for this lead. "
                    f"Add via: POST /leads/{{lead_id}}/asins or POST /asin-bank)"
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
                
                # Purchase metadata (use order_datetime when available)
                date=order_datetime or datetime.utcnow(),
                platform="AMZ",  # Selling platform (Amazon)
                order_number=order_number,
                address=shipping_address,
                # Quantities
                og_qty=item.quantity,
                final_qty=item.quantity,
                
                # Pricing - use from oa_sourcing
                rsp=oa_sourcing.rsp,
                
                # FBA fields
                fba_msku=fba_msku,
                
                # Status and Location - set to Pending/Retailer for new purchases
                status="Pending",
                location="Retailer",
                
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
                    retailer=shoepalace_retailer,
                    shipping_address=order_data.shipping_address
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
        retailer: Retailer,
        shipping_address: str = ""
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
            
            # Look up ASIN from asin_bank by lead_id and size (with size normalization + OASourcing fallback)
            asin_record = self._get_asin_for_lead_and_size(oa_sourcing.lead_id, item.size, oa_sourcing=oa_sourcing)
            
            if not asin_record:
                asin_count = self.db.query(AsinBank).filter(AsinBank.lead_id == oa_sourcing.lead_id).count()
                logger.warning(
                    f"No ASIN found for lead_id={oa_sourcing.lead_id}, size={item.size}. "
                    f"Creating record without ASIN. (AsinBank has {asin_count} records for this lead. "
                    f"Add via: POST /leads/{{lead_id}}/asins or POST /asin-bank)"
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
                date=datetime.utcnow(),
                platform="AMZ",  # Selling platform (Amazon)
                order_number=order_number,
                address=shipping_address,
                # Quantities
                og_qty=item.quantity,
                final_qty=item.quantity,
                
                # Pricing - use from oa_sourcing
                rsp=oa_sourcing.rsp,
                
                # FBA fields
                fba_msku=fba_msku,
                
                # Status and Location - set to Pending/Retailer for new purchases
                status="Pending",
                location="Retailer",
                
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
        retailer: Retailer,
        shipping_address: str = ""
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
            
            # Look up ASIN from asin_bank by lead_id and size (with size normalization + OASourcing fallback)
            asin_record = self._get_asin_for_lead_and_size(oa_sourcing.lead_id, item.size, oa_sourcing=oa_sourcing)
            
            if not asin_record:
                asin_count = self.db.query(AsinBank).filter(AsinBank.lead_id == oa_sourcing.lead_id).count()
                logger.warning(
                    f"No ASIN found for lead_id={oa_sourcing.lead_id}, size={item.size}. "
                    f"Creating record without ASIN. (AsinBank has {asin_count} records for this lead. "
                    f"Add via: POST /leads/{{lead_id}}/asins or POST /asin-bank)"
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
                date=datetime.utcnow(),
                platform="AMZ",  # Selling platform (Amazon)
                order_number=order_number,
                address=shipping_address,
                # Quantities
                og_qty=item.quantity,
                final_qty=item.quantity,
                
                # Pricing - use from oa_sourcing
                rsp=oa_sourcing.rsp,
                
                # FBA fields
                fba_msku=fba_msku,
                
                # Status and Location - set to Pending/Retailer for new purchases
                status="Pending",
                location="Retailer",
                
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
                    retailer=shoepalace_retailer,
                    shipping_address=order_data.shipping_address
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
        retailer: Retailer,
        shipping_address: str = ""
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
            
            # Look up ASIN from asin_bank by lead_id and size (with size normalization + OASourcing fallback)
            asin_record = self._get_asin_for_lead_and_size(oa_sourcing.lead_id, item.size, oa_sourcing=oa_sourcing)
            
            if not asin_record:
                asin_count = self.db.query(AsinBank).filter(AsinBank.lead_id == oa_sourcing.lead_id).count()
                logger.warning(
                    f"No ASIN found for lead_id={oa_sourcing.lead_id}, size={item.size}. "
                    f"Creating record without ASIN. (AsinBank has {asin_count} records for this lead. "
                    f"Add via: POST /leads/{{lead_id}}/asins or POST /asin-bank)"
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
                date=datetime.utcnow(),
                platform="AMZ",  # Selling platform (Amazon)
                order_number=order_number,
                address=shipping_address,
                # Quantities
                og_qty=item.quantity,
                final_qty=item.quantity,
                
                # Pricing - use from oa_sourcing
                rsp=oa_sourcing.rsp,
                
                # FBA fields
                fba_msku=fba_msku,
                
                # Status and Location - set to Pending/Retailer for new purchases
                status="Pending",
                location="Retailer",
                
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
    
    def _process_jdsports_order(self, order_data: JDSportsOrderData) -> Tuple[bool, Optional[str]]:
        """
        Process a JD Sports order and create purchase tracker records.
        
        Args:
            order_data: Parsed order data
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Get JD Sports retailer
            jdsports_retailer = self.db.query(Retailer).filter(
                Retailer.name.ilike('%JD Sports%') | Retailer.name.ilike('%JDSports%')
            ).first()
            
            if not jdsports_retailer:
                return False, "JD Sports retailer not found in database"
            
            created_count = 0
            skipped_count = 0
            
            for item in order_data.items:
                success, error = self._create_purchase_tracker_record_jdsports(
                    order_number=order_data.order_number,
                    item=item,
                    retailer=jdsports_retailer,
                    shipping_address=order_data.shipping_address
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
    
    def _create_purchase_tracker_record_jdsports(
        self,
        order_number: str,
        item: JDSportsOrderItem,
        retailer: Retailer,
        shipping_address: str = ""
    ) -> Tuple[bool, Optional[str]]:
        """
        Create a purchase tracker record for a JD Sports order item.
        
        Args:
            order_number: Order number
            item: JD Sports order item
            retailer: JD Sports retailer record
        
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
            
            # Look up ASIN from asin_bank by lead_id and size (with size normalization + OASourcing fallback)
            asin_record = self._get_asin_for_lead_and_size(oa_sourcing.lead_id, item.size, oa_sourcing=oa_sourcing)
            
            if not asin_record:
                asin_count = self.db.query(AsinBank).filter(AsinBank.lead_id == oa_sourcing.lead_id).count()
                logger.warning(
                    f"No ASIN found for lead_id={oa_sourcing.lead_id}, size={item.size}. "
                    f"Creating record without ASIN. (AsinBank has {asin_count} records for this lead. "
                    f"Add via: POST /leads/{{lead_id}}/asins or POST /asin-bank)"
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
                date=datetime.utcnow(),
                platform="AMZ",  # Selling platform (Amazon)
                order_number=order_number,
                address=shipping_address,
                
                # Quantities
                og_qty=item.quantity,
                final_qty=item.quantity,
                
                # Pricing - use from oa_sourcing
                rsp=oa_sourcing.rsp,
                
                # FBA fields
                fba_msku=fba_msku,
                
                # Status and Location - set to Pending/Retailer for new purchases
                status="Pending",
                location="Retailer",
                
                # Audit
                audited=False
            )
            
            self.db.add(purchase_record)
            
            logger.info(
                f"Created JD Sports purchase tracker record: "
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
    
    def _process_revolve_order(self, order_data: RevolveOrderData) -> Tuple[bool, Optional[str]]:
        """
        Process a Revolve order and create purchase tracker records.
        
        Args:
            order_data: Parsed order data
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Get Revolve retailer
            revolve_retailer = self.db.query(Retailer).filter(
                Retailer.name.ilike('%Revolve%')
            ).first()
            
            if not revolve_retailer:
                return False, "Revolve retailer not found in database"
            
            created_count = 0
            skipped_count = 0
            
            for item in order_data.items:
                success, error = self._create_purchase_tracker_record_revolve(
                    order_number=order_data.order_number,
                    item=item,
                    retailer=revolve_retailer,
                    shipping_address=order_data.shipping_address
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
    
    def _create_purchase_tracker_record_revolve(
        self,
        order_number: str,
        item: RevolveOrderItem,
        retailer: Retailer,
        shipping_address: str = ""
    ) -> Tuple[bool, Optional[str]]:
        """
        Create a purchase tracker record for a Revolve order item.
        
        Args:
            order_number: Order number
            item: Revolve order item
            retailer: Revolve retailer record
        
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
            
            # Look up ASIN from asin_bank by lead_id and size (with size normalization + OASourcing fallback)
            asin_record = self._get_asin_for_lead_and_size(oa_sourcing.lead_id, item.size, oa_sourcing=oa_sourcing)
            
            if not asin_record:
                asin_count = self.db.query(AsinBank).filter(AsinBank.lead_id == oa_sourcing.lead_id).count()
                logger.warning(
                    f"No ASIN found for lead_id={oa_sourcing.lead_id}, size={item.size}. "
                    f"Creating record without ASIN. (AsinBank has {asin_count} records for this lead. "
                    f"Add via: POST /leads/{{lead_id}}/asins or POST /asin-bank)"
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
                date=datetime.utcnow(),
                platform="AMZ",  # Selling platform (Amazon)
                order_number=order_number,
                address=shipping_address,
                
                # Quantities
                og_qty=item.quantity,
                final_qty=item.quantity,
                
                # Pricing - use from oa_sourcing
                rsp=oa_sourcing.rsp,
                
                # FBA fields
                fba_msku=fba_msku,
                
                # Status and Location - set to Pending/Retailer for new purchases
                status="Pending",
                location="Retailer",
                
                # Audit
                audited=False
            )
            
            self.db.add(purchase_record)
            
            logger.info(
                f"Created Revolve purchase tracker record: "
                f"lead_id={oa_sourcing.lead_id}, "
                f"product={oa_sourcing.product_name}, "
                f"size={item.size}, "
                f"qty={item.quantity}, "
                f"asin={asin_record.asin if asin_record else 'N/A'}, "
                f"msku={fba_msku}"
            )
            
            return True, None
        
        except Exception as e:
            error_msg = f"Error creating Revolve purchase tracker record: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
    
    def _process_asos_order(self, order_data: ASOSOrderData) -> Tuple[bool, Optional[str]]:
        """
        Process an ASOS order and create purchase tracker records.
        Same unique_id logic as order confirmation (from image URL).
        """
        try:
            asos_retailer = self.db.query(Retailer).filter(
                Retailer.name.ilike('%ASOS%')
            ).first()
            
            if not asos_retailer:
                return False, "ASOS retailer not found in database"
            
            created_count = 0
            skipped_count = 0
            
            for item in order_data.items:
                success, error = self._create_purchase_tracker_record_asos(
                    order_number=order_data.order_number,
                    item=item,
                    retailer=asos_retailer,
                    shipping_address=order_data.shipping_address
                )
                
                if success:
                    created_count += 1
                else:
                    logger.warning(f"Could not create ASOS record for item {item.unique_id}: {error}")
                    skipped_count += 1
            
            self.db.commit()
            
            if created_count == 0:
                return False, f"No purchase tracker records created (skipped: {skipped_count})"
            
            logger.info(f"Created {created_count} ASOS purchase tracker records for order {order_data.order_number}")
            if skipped_count > 0:
                logger.warning(f"Skipped {skipped_count} ASOS items (no matching OA sourcing lead)")
            
            return True, None
        
        except Exception as e:
            self.db.rollback()
            error_msg = f"Error processing ASOS order {order_data.order_number}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
    
    def _create_purchase_tracker_record_asos(
        self,
        order_number: str,
        item: ASOSOrderItem,
        retailer: Retailer,
        shipping_address: str = ""
    ) -> Tuple[bool, Optional[str]]:
        """Create a purchase tracker record for an ASOS order item. Same unique_id logic as Revolve."""
        try:
            oa_sourcing = self.db.query(OASourcing).filter(
                OASourcing.unique_id == item.unique_id
            ).first()
            
            if not oa_sourcing:
                return False, f"No OA sourcing lead found for unique_id: {item.unique_id}"
            
            asin_record = self._get_asin_for_lead_and_size(oa_sourcing.lead_id, item.size, oa_sourcing=oa_sourcing)
            
            if not asin_record:
                asin_count = self.db.query(AsinBank).filter(AsinBank.lead_id == oa_sourcing.lead_id).count()
                logger.warning(
                    f"No ASIN found for lead_id={oa_sourcing.lead_id}, size={item.size}. "
                    f"Creating ASOS record without ASIN. (AsinBank has {asin_count} records for this lead.)"
                )
            
            sku_upc = oa_sourcing.product_sku or "UNKNOWN"
            fba_msku = f"{item.size}-{sku_upc}-{order_number}"
            
            purchase_record = PurchaseTracker(
                oa_sourcing_id=oa_sourcing.id,
                asin_bank_id=asin_record.id if asin_record else None,
                lead_id=oa_sourcing.lead_id,
                date=datetime.utcnow(),
                platform="AMZ",
                order_number=order_number,
                address=shipping_address,
                og_qty=item.quantity,
                final_qty=item.quantity,
                rsp=oa_sourcing.rsp,
                fba_msku=fba_msku,
                status="Pending",
                location="Retailer",
                audited=False
            )
            
            self.db.add(purchase_record)
            
            logger.info(
                f"Created ASOS purchase tracker record: "
                f"lead_id={oa_sourcing.lead_id}, unique_id={item.unique_id}, "
                f"size={item.size}, qty={item.quantity}"
            )
            
            return True, None
        
        except Exception as e:
            error_msg = f"Error creating ASOS purchase tracker record: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
    
    def _process_dtlr_order(self, order_data: DTLROrderData) -> Tuple[bool, Optional[str]]:
        """
        Process a DTLR order and create purchase tracker records.
        
        Args:
            order_data: Parsed order data
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Get DTLR retailer
            dtlr_retailer = self.db.query(Retailer).filter(
                Retailer.name.ilike('%DTLR%')
            ).first()
            
            if not dtlr_retailer:
                return False, "DTLR retailer not found in database"
            
            created_count = 0
            skipped_count = 0
            
            for item in order_data.items:
                success, error = self._create_purchase_tracker_record_dtlr(
                    order_number=order_data.order_number,
                    item=item,
                    retailer=dtlr_retailer,
                    shipping_address=order_data.shipping_address
                )
                
                if success:
                    created_count += 1
                else:
                    logger.warning(f"Could not create record for item {item.product_name}: {error}")
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
    
    def _create_purchase_tracker_record_dtlr(
        self,
        order_number: str,
        item: DTLROrderItem,
        retailer: Retailer,
        shipping_address: str = ""
    ) -> Tuple[bool, Optional[str]]:
        """
        Create a purchase tracker record for a DTLR order item.
        
        Args:
            order_number: Order number
            item: DTLR order item
            retailer: DTLR retailer record
            shipping_address: Normalized shipping address
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # For Nike/Jordan/Adidas: unique_id is None, need to match by product name + size
            # For HOKA: unique_id is populated, match by unique_id only
            
            if item.unique_id:
                # Look up OA sourcing by unique_id only (for HOKA)
                oa_sourcing = self.db.query(OASourcing).filter(
                    OASourcing.unique_id == item.unique_id
                ).first()
            else:
                # For Nike/Jordan/Adidas: skip unique ID lookup
                # Try to match by product name (fuzzy match) - but for now, just log and skip
                logger.info(f"Skipping Nike/Jordan/Adidas product (no unique ID): {item.product_name}")
                return False, f"Nike/Jordan/Adidas product with no unique ID: {item.product_name}"
            
            if not oa_sourcing:
                return False, f"No OA sourcing lead found for unique_id: {item.unique_id}"
            
            # Look up ASIN from asin_bank by lead_id and size (with size normalization + OASourcing fallback)
            asin_record = self._get_asin_for_lead_and_size(oa_sourcing.lead_id, item.size, oa_sourcing=oa_sourcing)
            
            if not asin_record:
                asin_count = self.db.query(AsinBank).filter(AsinBank.lead_id == oa_sourcing.lead_id).count()
                logger.warning(
                    f"No ASIN found for lead_id={oa_sourcing.lead_id}, size={item.size}. "
                    f"Creating record without ASIN. (AsinBank has {asin_count} records for this lead. "
                    f"Add via: POST /leads/{{lead_id}}/asins or POST /asin-bank)"
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
                date=datetime.utcnow(),
                platform="AMZ",  # Selling platform (Amazon)
                order_number=order_number,
                address=shipping_address,
                
                # Quantities
                og_qty=item.quantity,
                final_qty=item.quantity,
                
                # Pricing - use from oa_sourcing
                rsp=oa_sourcing.rsp,
                
                # FBA fields
                fba_msku=fba_msku,
                
                # Status and Location - set to Pending/Retailer for new purchases
                status="Pending",
                location="Retailer",
                
                # Audit
                audited=False
            )
            
            self.db.add(purchase_record)
            
            logger.info(
                f"Created DTLR purchase tracker record: "
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
    
    def _process_endclothing_order(self, order_data: ENDClothingOrderData) -> Tuple[bool, Optional[str]]:
        """
        Process an END Clothing order and create purchase tracker records.
        
        Args:
            order_data: Parsed order data
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Get END Clothing retailer
            endclothing_retailer = self.db.query(Retailer).filter(
                Retailer.name.ilike('%END%') | Retailer.name.ilike('%END Clothing%')
            ).first()
            
            if not endclothing_retailer:
                return False, "END Clothing retailer not found in database"
            
            created_count = 0
            skipped_count = 0
            
            for item in order_data.items:
                success, error = self._create_purchase_tracker_record_endclothing(
                    order_number=order_data.order_number,
                    item=item,
                    retailer=endclothing_retailer,
                    shipping_address=order_data.shipping_address
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
    
    def _create_purchase_tracker_record_endclothing(
        self,
        order_number: str,
        item: ENDClothingOrderItem,
        retailer: Retailer,
        shipping_address: str = ""
    ) -> Tuple[bool, Optional[str]]:
        """
        Create a purchase tracker record for an END Clothing order item.
        
        Args:
            order_number: Order number
            item: END Clothing order item
            retailer: END Clothing retailer record
            shipping_address: Normalized shipping address
        
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
            
            # Look up ASIN from asin_bank by lead_id and size (with size normalization + OASourcing fallback)
            asin_record = self._get_asin_for_lead_and_size(oa_sourcing.lead_id, item.size, oa_sourcing=oa_sourcing)
            
            if not asin_record:
                asin_count = self.db.query(AsinBank).filter(AsinBank.lead_id == oa_sourcing.lead_id).count()
                logger.warning(
                    f"No ASIN found for lead_id={oa_sourcing.lead_id}, size={item.size}. "
                    f"Creating record without ASIN. (AsinBank has {asin_count} records for this lead. "
                    f"Add via: POST /leads/{{lead_id}}/asins or POST /asin-bank)"
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
                date=datetime.utcnow(),
                platform="AMZ",  # Selling platform (Amazon)
                order_number=order_number,
                address=shipping_address,
                
                # Quantities
                og_qty=item.quantity,
                final_qty=item.quantity,
                
                # Pricing - use from oa_sourcing
                rsp=oa_sourcing.rsp,
                
                # FBA fields
                fba_msku=fba_msku,
                
                # Status and Location - set to Pending/Retailer for new purchases
                status="Pending",
                location="Retailer",
                
                # Audit
                audited=False
            )
            
            self.db.add(purchase_record)
            
            logger.info(
                f"Created END Clothing purchase tracker record: "
                f"lead_id={oa_sourcing.lead_id}, "
                f"product={oa_sourcing.product_name}, "
                f"size={item.size} (original: {item.original_size}), "
                f"qty={item.quantity}, "
                f"asin={asin_record.asin if asin_record else 'N/A'}, "
                f"msku={fba_msku}"
            )
            
            return True, None
        
        except Exception as e:
            error_msg = f"Error creating purchase tracker record: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
    
    def _process_shopwss_order(self, order_data: ShopWSSOrderData) -> Tuple[bool, Optional[str]]:
        """
        Process a ShopWSS order and create purchase tracker records.
        
        Args:
            order_data: Parsed order data
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Get ShopWSS retailer
            shopwss_retailer = self.db.query(Retailer).filter(
                Retailer.name.ilike('%ShopWSS%') | Retailer.name.ilike('%WSS%')
            ).first()
            
            if not shopwss_retailer:
                return False, "ShopWSS retailer not found in database"
            
            created_count = 0
            skipped_count = 0
            
            for item in order_data.items:
                success, error = self._create_purchase_tracker_record_shopwss(
                    order_number=order_data.order_number,
                    item=item,
                    retailer=shopwss_retailer,
                    shipping_address=order_data.shipping_address
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
    
    def _create_purchase_tracker_record_shopwss(
        self,
        order_number: str,
        item: ShopWSSOrderItem,
        retailer: Retailer,
        shipping_address: str = ""
    ) -> Tuple[bool, Optional[str]]:
        """
        Create a purchase tracker record for a ShopWSS order item.
        
        Args:
            order_number: Order number
            item: ShopWSS order item
            retailer: ShopWSS retailer record
            shipping_address: Normalized shipping address
        
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
            
            # Look up ASIN from asin_bank by lead_id and size (with size normalization + OASourcing fallback)
            asin_record = self._get_asin_for_lead_and_size(oa_sourcing.lead_id, item.size, oa_sourcing=oa_sourcing)
            
            if not asin_record:
                asin_count = self.db.query(AsinBank).filter(AsinBank.lead_id == oa_sourcing.lead_id).count()
                logger.warning(
                    f"No ASIN found for lead_id={oa_sourcing.lead_id}, size={item.size}. "
                    f"Creating record without ASIN. (AsinBank has {asin_count} records for this lead. "
                    f"Add via: POST /leads/{{lead_id}}/asins or POST /asin-bank)"
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
                date=datetime.utcnow(),
                platform="AMZ",  # Selling platform (Amazon)
                order_number=order_number,
                address=shipping_address,
                
                # Quantities
                og_qty=item.quantity,
                final_qty=item.quantity,
                
                # Pricing - use from oa_sourcing
                rsp=oa_sourcing.rsp,
                
                # FBA fields
                fba_msku=fba_msku,
                
                # Status and Location - set to Pending/Retailer for new purchases
                status="Pending",
                location="Retailer",
                
                # Audit
                audited=False
            )
            
            self.db.add(purchase_record)
            
            logger.info(
                f"Created ShopWSS purchase tracker record: "
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
        """Add 'Processed' label to a message and remove 'Error' label if present"""
        if self.processed_label:
            self.gmail_service.add_label_to_message(message_id, self.processed_label['id'])
            
            # Remove error label if present (in case this is a reprocessed email that previously failed)
            if self.error_label:
                self.gmail_service.remove_label_from_message(message_id, self.error_label['id'])
    
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
                    retailer=hibbett_retailer,
                    shipping_address=order_data.shipping_address
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
        retailer: Retailer,
        shipping_address: str = ""
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
            
            # Look up ASIN from asin_bank by lead_id and size (with size normalization + OASourcing fallback)
            asin_record = self._get_asin_for_lead_and_size(oa_sourcing.lead_id, item.size, oa_sourcing=oa_sourcing)
            
            if not asin_record:
                asin_count = self.db.query(AsinBank).filter(AsinBank.lead_id == oa_sourcing.lead_id).count()
                logger.warning(
                    f"No ASIN found for lead_id={oa_sourcing.lead_id}, size={item.size}. "
                    f"Creating record without ASIN. (AsinBank has {asin_count} records for this lead. "
                    f"Add via: POST /leads/{{lead_id}}/asins or POST /asin-bank)"
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
                date=datetime.utcnow(),
                platform="AMZ",  # Selling platform (Amazon)
                order_number=order_number,
                address=shipping_address,
                # Quantities
                og_qty=item.quantity,
                final_qty=item.quantity,
                
                # Pricing - use from oa_sourcing
                rsp=oa_sourcing.rsp,
                
                # FBA fields
                fba_msku=fba_msku,
                
                # Status and Location - set to Pending/Retailer for new purchases
                status="Pending",
                location="Retailer",
                
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
                    retailer=shoepalace_retailer,
                    shipping_address=order_data.shipping_address
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
        retailer: Retailer,
        shipping_address: str = ""
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
            
            # Look up ASIN from asin_bank by lead_id and size (with size normalization + OASourcing fallback)
            asin_record = self._get_asin_for_lead_and_size(oa_sourcing.lead_id, item.size, oa_sourcing=oa_sourcing)
            
            if not asin_record:
                asin_count = self.db.query(AsinBank).filter(AsinBank.lead_id == oa_sourcing.lead_id).count()
                logger.warning(
                    f"No ASIN found for lead_id={oa_sourcing.lead_id}, size={item.size}. "
                    f"Creating record without ASIN. (AsinBank has {asin_count} records for this lead. "
                    f"Add via: POST /leads/{{lead_id}}/asins or POST /asin-bank)"
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
                date=datetime.utcnow(),
                platform="AMZ",  # Selling platform (Amazon)
                order_number=order_number,
                address=shipping_address,
                # Quantities
                og_qty=item.quantity,
                final_qty=item.quantity,
                
                # Pricing - use from oa_sourcing
                rsp=oa_sourcing.rsp,
                
                # FBA fields
                fba_msku=fba_msku,
                
                # Status and Location - set to Pending/Retailer for new purchases
                status="Pending",
                location="Retailer",
                
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
                    retailer=snipes_retailer,
                    shipping_address=order_data.shipping_address
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
        retailer: Retailer,
        shipping_address: str = ""
    ) -> Tuple[bool, Optional[str]]:
        """
        Create a purchase tracker record for a Snipes order item.
        
        Match by unique_id only (OASourcing has no size). Use AsinBank for size.
        Same schema as ASOS/Footlocker.
        """
        try:
            # Find OASourcing by unique_id only (OASourcing has no size column - size is in AsinBank)
            oa_sourcing = self.db.query(OASourcing).filter(
                OASourcing.unique_id == item.unique_id
            ).first()
            
            if not oa_sourcing:
                return False, f"No OA sourcing lead found for unique_id: {item.unique_id}"
            
            # Get AsinBank by lead_id + size (size is in AsinBank)
            asin_record = self._get_asin_for_lead_and_size(oa_sourcing.lead_id, item.size, oa_sourcing=oa_sourcing)
            
            if not asin_record:
                asin_count = self.db.query(AsinBank).filter(AsinBank.lead_id == oa_sourcing.lead_id).count()
                logger.warning(
                    f"No ASIN found for lead_id={oa_sourcing.lead_id}, size={item.size}. "
                    f"Creating Snipes record without ASIN. (AsinBank has {asin_count} records for this lead.)"
                )
            
            sku_upc = oa_sourcing.product_sku or "UNKNOWN"
            fba_msku = f"{item.size}-{sku_upc}-{order_number}"
            
            purchase_record = PurchaseTracker(
                oa_sourcing_id=oa_sourcing.id,
                asin_bank_id=asin_record.id if asin_record else None,
                lead_id=oa_sourcing.lead_id,
                date=datetime.utcnow(),
                platform="AMZ",
                order_number=order_number,
                address=shipping_address,
                og_qty=item.quantity,
                final_qty=item.quantity,
                rsp=oa_sourcing.rsp,
                fba_msku=fba_msku,
                status="Pending",
                location="Retailer",
                audited=False
            )
            
            self.db.add(purchase_record)
            
            logger.info(
                f"Created Snipes purchase tracker record: "
                f"lead_id={oa_sourcing.lead_id}, unique_id={item.unique_id}, "
                f"size={item.size}, qty={item.quantity}"
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
                    retailer=finishline_retailer,
                    shipping_address=order_data.shipping_address
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
        retailer: Retailer,
        shipping_address: str = ""
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
            # Look up OA sourcing by unique_id (exact match first)
            oa_sourcing = self.db.query(OASourcing).filter(
                OASourcing.unique_id == item.unique_id
            ).first()
            
            # Fallback: Finish Line emails use SKU_color (e.g. 1104451D_175);
            # user may add base SKU (1104451D) in OA sourcing
            if not oa_sourcing and '_' in item.unique_id:
                base_sku = item.unique_id.rsplit('_', 1)[0]
                oa_sourcing = self.db.query(OASourcing).filter(
                    OASourcing.unique_id == base_sku
                ).first()
            
            if not oa_sourcing:
                return False, f"No OA sourcing lead found for unique_id: {item.unique_id}"
            
            # Look up ASIN from asin_bank by lead_id and size (with size normalization + OASourcing fallback)
            asin_record = self._get_asin_for_lead_and_size(oa_sourcing.lead_id, item.size, oa_sourcing=oa_sourcing)
            
            if not asin_record:
                asin_count = self.db.query(AsinBank).filter(AsinBank.lead_id == oa_sourcing.lead_id).count()
                logger.warning(
                    f"No ASIN found for lead_id={oa_sourcing.lead_id}, size={item.size}. "
                    f"Creating record without ASIN. (AsinBank has {asin_count} records for this lead. "
                    f"Add via: POST /leads/{{lead_id}}/asins or POST /asin-bank)"
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
                date=datetime.utcnow(),
                platform="AMZ",  # Selling platform (Amazon)
                order_number=order_number,
                address=shipping_address,
                
                # Quantities
                og_qty=item.quantity,
                final_qty=item.quantity,
                
                # Pricing - use from oa_sourcing
                rsp=oa_sourcing.rsp,
                
                # FBA fields
                fba_msku=fba_msku,
                
                # Status and Location - set to Pending/Retailer for new purchases
                status="Pending",
                location="Retailer",
                
                # Audit
                audited=False
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
                    retailer=shopsimon_retailer,
                    shipping_address=order_data.shipping_address
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
        retailer: Retailer,
        shipping_address: str = ""
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
            
            # Look up ASIN from asin_bank by lead_id and size (with size normalization + OASourcing fallback)
            asin_record = self._get_asin_for_lead_and_size(oa_sourcing.lead_id, item.size, oa_sourcing=oa_sourcing)
            
            if not asin_record:
                asin_count = self.db.query(AsinBank).filter(AsinBank.lead_id == oa_sourcing.lead_id).count()
                logger.warning(
                    f"No ASIN found for lead_id={oa_sourcing.lead_id}, size={item.size}. "
                    f"Creating record without ASIN. (AsinBank has {asin_count} records for this lead. "
                    f"Add via: POST /leads/{{lead_id}}/asins or POST /asin-bank)"
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
                date=datetime.utcnow(),
                platform="AMZ",  # Selling platform (Amazon)
                order_number=order_number,
                address=shipping_address,
                
                # Quantities
                og_qty=item.quantity,
                final_qty=item.quantity,
                
                # Pricing - use from oa_sourcing
                rsp=oa_sourcing.rsp,
                
                # FBA fields
                fba_msku=fba_msku,
                
                # Status and Location - set to Pending/Retailer for new purchases
                status="Pending",
                location="Retailer",
                
                # Audit
                audited=False
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
    
    def _process_urban_order(self, order_data: UrbanOrderData) -> Tuple[bool, Optional[str]]:
        """
        Process an Urban Outfitters order and create purchase tracker records.
        
        Args:
            order_data: Parsed order data
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Get Urban Outfitters retailer
            urban_retailer = self.db.query(Retailer).filter(
                Retailer.name.ilike('%Urban Outfitters%')
            ).first()
            
            if not urban_retailer:
                return False, "Urban Outfitters retailer not found in database"
            
            created_count = 0
            skipped_count = 0
            
            for item in order_data.items:
                success, error = self._create_purchase_tracker_record_urban(
                    order_number=order_data.order_number,
                    item=item,
                    retailer=urban_retailer,
                    shipping_address=order_data.shipping_address
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
    
    def _create_purchase_tracker_record_urban(
        self,
        order_number: str,
        item: UrbanOrderItem,
        retailer: Retailer,
        shipping_address: str = ""
    ) -> Tuple[bool, Optional[str]]:
        """
        Create a purchase tracker record for an Urban Outfitters order item.
        
        Args:
            order_number: Order number
            item: Urban Outfitters order item
            retailer: Urban Outfitters retailer record
        
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
            
            # Look up ASIN from asin_bank by lead_id and size (with size normalization + OASourcing fallback)
            asin_record = self._get_asin_for_lead_and_size(oa_sourcing.lead_id, item.size, oa_sourcing=oa_sourcing)
            
            if not asin_record:
                asin_count = self.db.query(AsinBank).filter(AsinBank.lead_id == oa_sourcing.lead_id).count()
                logger.warning(
                    f"No ASIN found for lead_id={oa_sourcing.lead_id}, size={item.size}. "
                    f"Creating record without ASIN. (AsinBank has {asin_count} records for this lead. "
                    f"Add via: POST /leads/{{lead_id}}/asins or POST /asin-bank)"
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
                date=datetime.utcnow(),
                platform="AMZ",  # Selling platform (Amazon)
                order_number=order_number,
                address=shipping_address,
                
                # Quantities
                og_qty=item.quantity,
                final_qty=item.quantity,
                
                # Pricing - use from oa_sourcing
                rsp=oa_sourcing.rsp,
                
                # FBA fields
                fba_msku=fba_msku,
                
                # Status and Location - set to Pending/Retailer for new purchases
                status="Pending",
                location="Retailer",
                
                # Audit
                audited=False
            )
            
            self.db.add(purchase_record)
            
            logger.info(
                f"Created Urban Outfitters purchase tracker record: "
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
    
    def _process_anthropologie_order(self, order_data: AnthropologieOrderData) -> Tuple[bool, Optional[str]]:
        """
        Process an Anthropologie order and create purchase tracker records.
        
        Args:
            order_data: Parsed order data
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Get Anthropologie retailer
            anthropologie_retailer = self.db.query(Retailer).filter(
                Retailer.name.ilike('%Anthropologie%')
            ).first()
            
            if not anthropologie_retailer:
                return False, "Anthropologie retailer not found in database"
            
            created_count = 0
            skipped_count = 0
            
            for item in order_data.items:
                success, error = self._create_purchase_tracker_record_anthropologie(
                    order_number=order_data.order_number,
                    item=item,
                    retailer=anthropologie_retailer,
                    shipping_address=order_data.shipping_address
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
            logger.error(f"Error processing Anthropologie order: {e}", exc_info=True)
            return False, str(e)
    
    def _create_purchase_tracker_record_anthropologie(
        self,
        order_number: str,
        item: AnthropologieOrderItem,
        retailer: Retailer,
        shipping_address: str = ""
    ) -> Tuple[bool, Optional[str]]:
        """
        Create a purchase tracker record for an Anthropologie order item.
        
        Args:
            order_number: Order number
            item: Anthropologie order item
            retailer: Anthropologie retailer record
        
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
            
            # Look up ASIN from asin_bank by lead_id and size (with size normalization + OASourcing fallback)
            asin_record = self._get_asin_for_lead_and_size(oa_sourcing.lead_id, item.size, oa_sourcing=oa_sourcing)
            
            if not asin_record:
                asin_count = self.db.query(AsinBank).filter(AsinBank.lead_id == oa_sourcing.lead_id).count()
                logger.warning(
                    f"No ASIN found for lead_id={oa_sourcing.lead_id}, size={item.size}. "
                    f"Creating record without ASIN. (AsinBank has {asin_count} records for this lead. "
                    f"Add via: POST /leads/{{lead_id}}/asins or POST /asin-bank)"
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
                date=datetime.utcnow(),
                platform="AMZ",  # Selling platform (Amazon)
                order_number=order_number,
                address=shipping_address,
                
                # Quantities
                og_qty=item.quantity,
                final_qty=item.quantity,
                
                # Pricing - use from oa_sourcing
                rsp=oa_sourcing.rsp,
                
                # FBA fields
                fba_msku=fba_msku,
                
                # Status and Location - set to Pending/Retailer for new purchases
                status="Pending",
                location="Retailer",
                
                # Audit
                audited=False
            )
            
            self.db.add(purchase_record)
            
            logger.info(
                f"Created Anthropologie purchase tracker record: "
                f"lead_id={oa_sourcing.lead_id}, "
                f"unique_id={item.unique_id}, "
                f"size={item.size}, "
                f"qty={item.quantity}, "
                f"order={order_number}"
            )
            
            return True, None
        
        except Exception as e:
            logger.error(f"Error creating Anthropologie purchase tracker record: {e}", exc_info=True)
            return False, str(e)
    
    def _process_nike_order(self, order_data: NikeOrderData) -> Tuple[bool, Optional[str]]:
        """
        Process a Nike order and create purchase tracker records.
        
        Args:
            order_data: Parsed order data
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Get Nike retailer
            nike_retailer = self.db.query(Retailer).filter(
                Retailer.name.ilike('%Nike%')
            ).first()
            
            if not nike_retailer:
                return False, "Nike retailer not found in database"
            
            created_count = 0
            skipped_count = 0
            
            for item in order_data.items:
                success, error = self._create_purchase_tracker_record_nike(
                    order_number=order_data.order_number,
                    item=item,
                    retailer=nike_retailer,
                    shipping_address=order_data.shipping_address
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
            logger.error(f"Error processing Nike order: {e}", exc_info=True)
            return False, str(e)
    
    def _create_purchase_tracker_record_nike(
        self,
        order_number: str,
        item: NikeOrderItem,
        retailer: Retailer,
        shipping_address: str = ""
    ) -> Tuple[bool, Optional[str]]:
        """
        Create a purchase tracker record for a Nike order item.
        
        Args:
            order_number: Order number
            item: Nike order item
            retailer: Nike retailer record
        
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
            
            # Look up ASIN from asin_bank by lead_id and size (with size normalization + OASourcing fallback)
            asin_record = self._get_asin_for_lead_and_size(oa_sourcing.lead_id, item.size, oa_sourcing=oa_sourcing)
            
            if not asin_record:
                asin_count = self.db.query(AsinBank).filter(AsinBank.lead_id == oa_sourcing.lead_id).count()
                logger.warning(
                    f"No ASIN found for lead_id={oa_sourcing.lead_id}, size={item.size}. "
                    f"Creating record without ASIN. (AsinBank has {asin_count} records for this lead. "
                    f"Add via: POST /leads/{{lead_id}}/asins or POST /asin-bank)"
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
                date=datetime.utcnow(),
                platform="AMZ",  # Selling platform (Amazon)
                order_number=order_number,
                address=shipping_address,
                
                # Quantities
                og_qty=item.quantity,
                final_qty=item.quantity,
                
                # Pricing - use from oa_sourcing
                rsp=oa_sourcing.rsp,
                
                # FBA fields
                fba_msku=fba_msku,
                
                # Status and Location - set to Pending/Retailer for new purchases
                status="Pending",
                location="Retailer",
                
                # Audit
                audited=False
            )
            
            self.db.add(purchase_record)
            
            logger.info(
                f"Created Nike purchase tracker record: "
                f"lead_id={oa_sourcing.lead_id}, "
                f"unique_id={item.unique_id}, "
                f"size={item.size}, "
                f"qty={item.quantity}, "
                f"order={order_number}"
            )
            
            return True, None
        
        except Exception as e:
            logger.error(f"Error creating Nike purchase tracker record: {e}", exc_info=True)
            return False, str(e)
    
    def _process_carbon38_order(self, order_data: Carbon38OrderData) -> Tuple[bool, Optional[str]]:
        """
        Process a Carbon38 order and create purchase tracker records.
        
        Args:
            order_data: Parsed order data
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Get Carbon38 retailer
            carbon38_retailer = self.db.query(Retailer).filter(
                Retailer.name.ilike('%Carbon38%')
            ).first()
            
            if not carbon38_retailer:
                return False, "Carbon38 retailer not found in database"
            
            created_count = 0
            skipped_count = 0
            
            for item in order_data.items:
                success, error = self._create_purchase_tracker_record_carbon38(
                    order_number=order_data.order_number,
                    item=item,
                    retailer=carbon38_retailer,
                    shipping_address=order_data.shipping_address
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
            logger.error(f"Error processing Carbon38 order: {e}", exc_info=True)
            return False, str(e)
    
    def _create_purchase_tracker_record_carbon38(
        self,
        order_number: str,
        item: Carbon38OrderItem,
        retailer: Retailer,
        shipping_address: str = ""
    ) -> Tuple[bool, Optional[str]]:
        """
        Create a purchase tracker record for a Carbon38 order item.
        
        Args:
            order_number: Order number
            item: Carbon38 order item
            retailer: Carbon38 retailer record
        
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
            
            # Look up ASIN from asin_bank by lead_id and size (with size normalization + OASourcing fallback)
            asin_record = self._get_asin_for_lead_and_size(oa_sourcing.lead_id, item.size, oa_sourcing=oa_sourcing)
            
            if not asin_record:
                asin_count = self.db.query(AsinBank).filter(AsinBank.lead_id == oa_sourcing.lead_id).count()
                logger.warning(
                    f"No ASIN found for lead_id={oa_sourcing.lead_id}, size={item.size}. "
                    f"Creating record without ASIN. (AsinBank has {asin_count} records for this lead. "
                    f"Add via: POST /leads/{{lead_id}}/asins or POST /asin-bank)"
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
                date=datetime.utcnow(),
                platform="AMZ",  # Selling platform (Amazon)
                order_number=order_number,
                address=shipping_address,
                
                # Quantities
                og_qty=item.quantity,
                final_qty=item.quantity,
                
                # Pricing - use from oa_sourcing
                rsp=oa_sourcing.rsp,
                
                # FBA fields
                fba_msku=fba_msku,
                
                # Status and Location - set to Pending/Retailer for new purchases
                status="Pending",
                location="Retailer",
                
                # Audit
                audited=False
            )
            
            self.db.add(purchase_record)
            
            logger.info(
                f"Created Carbon38 purchase tracker record: "
                f"lead_id={oa_sourcing.lead_id}, "
                f"unique_id={item.unique_id}, "
                f"size={item.size}, "
                f"qty={item.quantity}, "
                f"order={order_number}"
            )
            
            return True, None
        
        except Exception as e:
            logger.error(f"Error creating Carbon38 purchase tracker record: {e}", exc_info=True)
            return False, str(e)
    
    def _process_gazelle_order(self, order_data: GazelleOrderData) -> Tuple[bool, Optional[str]]:
        """
        Process a Gazelle Sports order and create purchase tracker records.
        
        Args:
            order_data: Parsed order data
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Get Gazelle Sports retailer
            gazelle_retailer = self.db.query(Retailer).filter(
                Retailer.name.ilike('%Gazelle%')
            ).first()
            
            if not gazelle_retailer:
                return False, "Gazelle Sports retailer not found in database"
            
            created_count = 0
            skipped_count = 0
            
            for item in order_data.items:
                success, error = self._create_purchase_tracker_record_gazelle(
                    order_number=order_data.order_number,
                    item=item,
                    retailer=gazelle_retailer,
                    shipping_address=order_data.shipping_address
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
            logger.error(f"Error processing Gazelle order: {e}", exc_info=True)
            return False, str(e)
    
    def _create_purchase_tracker_record_gazelle(
        self,
        order_number: str,
        item: GazelleOrderItem,
        retailer: Retailer,
        shipping_address: str = ""
    ) -> Tuple[bool, Optional[str]]:
        """
        Create a purchase tracker record for a Gazelle Sports order item.
        
        Args:
            order_number: Order number
            item: Gazelle order item
            retailer: Gazelle Sports retailer record
        
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
            
            # Look up ASIN from asin_bank by lead_id and size (with size normalization + OASourcing fallback)
            asin_record = self._get_asin_for_lead_and_size(oa_sourcing.lead_id, item.size, oa_sourcing=oa_sourcing)
            
            if not asin_record:
                asin_count = self.db.query(AsinBank).filter(AsinBank.lead_id == oa_sourcing.lead_id).count()
                logger.warning(
                    f"No ASIN found for lead_id={oa_sourcing.lead_id}, size={item.size}. "
                    f"Creating record without ASIN. (AsinBank has {asin_count} records for this lead. "
                    f"Add via: POST /leads/{{lead_id}}/asins or POST /asin-bank)"
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
                date=datetime.utcnow(),
                platform="AMZ",  # Selling platform (Amazon)
                order_number=order_number,
                address=shipping_address,
                
                # Quantities
                og_qty=item.quantity,
                final_qty=item.quantity,
                
                # Pricing - use from oa_sourcing
                rsp=oa_sourcing.rsp,
                
                # FBA fields
                fba_msku=fba_msku,
                
                # Status and Location - set to Pending/Retailer for new purchases
                status="Pending",
                location="Retailer",
                
                # Audit
                audited=False
            )
            
            self.db.add(purchase_record)
            
            logger.info(
                f"Created Gazelle purchase tracker record: "
                f"lead_id={oa_sourcing.lead_id}, "
                f"unique_id={item.unique_id}, "
                f"size={item.size}, "
                f"qty={item.quantity}, "
                f"order={order_number}"
            )
            
            return True, None
        
        except Exception as e:
            logger.error(f"Error creating Gazelle purchase tracker record: {e}", exc_info=True)
            return False, str(e)
    
    def _process_netaporter_order(self, order_data: NetAPorterOrderData) -> Tuple[bool, Optional[str]]:
        """
        Process a NET-A-PORTER order and create purchase tracker records.
        
        Args:
            order_data: Parsed order data
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Get NET-A-PORTER retailer
            netaporter_retailer = self.db.query(Retailer).filter(
                Retailer.name.ilike('%NET-A-PORTER%')
            ).first()
            
            if not netaporter_retailer:
                return False, "NET-A-PORTER retailer not found in database"
            
            created_count = 0
            skipped_count = 0
            
            for item in order_data.items:
                success, error = self._create_purchase_tracker_record_netaporter(
                    order_number=order_data.order_number,
                    item=item,
                    retailer=netaporter_retailer,
                    shipping_address=order_data.shipping_address
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
            logger.error(f"Error processing NET-A-PORTER order: {e}", exc_info=True)
            return False, str(e)
    
    def _create_purchase_tracker_record_netaporter(
        self,
        order_number: str,
        item: NetAPorterOrderItem,
        retailer: Retailer,
        shipping_address: str = ""
    ) -> Tuple[bool, Optional[str]]:
        """
        Create a purchase tracker record for a NET-A-PORTER order item.
        
        Args:
            order_number: Order number
            item: NET-A-PORTER order item
            retailer: NET-A-PORTER retailer record
        
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
            
            # Look up ASIN from asin_bank by lead_id and size (with size normalization + OASourcing fallback)
            asin_record = self._get_asin_for_lead_and_size(oa_sourcing.lead_id, item.size, oa_sourcing=oa_sourcing)
            
            if not asin_record:
                asin_count = self.db.query(AsinBank).filter(AsinBank.lead_id == oa_sourcing.lead_id).count()
                logger.warning(
                    f"No ASIN found for lead_id={oa_sourcing.lead_id}, size={item.size}. "
                    f"Creating record without ASIN. (AsinBank has {asin_count} records for this lead. "
                    f"Add via: POST /leads/{{lead_id}}/asins or POST /asin-bank)"
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
                date=datetime.utcnow(),
                platform="AMZ",  # Selling platform (Amazon)
                order_number=order_number,
                address=shipping_address,
                
                # Quantities
                og_qty=item.quantity,
                final_qty=item.quantity,
                
                # Pricing - use from oa_sourcing
                rsp=oa_sourcing.rsp,
                
                # FBA fields
                fba_msku=fba_msku,
                
                # Status and Location - set to Pending/Retailer for new purchases
                status="Pending",
                location="Retailer",
                
                # Audit
                audited=False
            )
            
            self.db.add(purchase_record)
            
            logger.info(
                f"Created NET-A-PORTER purchase tracker record: "
                f"lead_id={oa_sourcing.lead_id}, "
                f"unique_id={item.unique_id}, "
                f"size={item.size}, "
                f"qty={item.quantity}, "
                f"order={order_number}"
            )
            
            return True, None
        
        except Exception as e:
            logger.error(f"Error creating NET-A-PORTER purchase tracker record: {e}", exc_info=True)
            return False, str(e)
    
    def _process_fit2run_order(self, order_data: Fit2RunOrderData) -> Tuple[bool, Optional[str]]:
        """
        Process a Fit2Run order and create purchase tracker records.
        
        Args:
            order_data: Parsed order data
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Get Fit2Run retailer
            fit2run_retailer = self.db.query(Retailer).filter(
                Retailer.name.ilike('%Fit2Run%')
            ).first()
            
            if not fit2run_retailer:
                return False, "Fit2Run retailer not found in database"
            
            created_count = 0
            skipped_count = 0
            
            for item in order_data.items:
                success, error = self._create_purchase_tracker_record_fit2run(
                    order_number=order_data.order_number,
                    item=item,
                    retailer=fit2run_retailer,
                    shipping_address=order_data.shipping_address
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
            logger.error(f"Error processing Fit2Run order: {e}", exc_info=True)
            return False, str(e)
    
    def _create_purchase_tracker_record_fit2run(
        self,
        order_number: str,
        item: Fit2RunOrderItem,
        retailer: Retailer,
        shipping_address: str = ""
    ) -> Tuple[bool, Optional[str]]:
        """
        Create a purchase tracker record for a Fit2Run order item.
        
        Args:
            order_number: Order number
            item: Fit2Run order item
            retailer: Fit2Run retailer record
        
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
            
            # Look up ASIN from asin_bank by lead_id and size (with size normalization + OASourcing fallback)
            asin_record = self._get_asin_for_lead_and_size(oa_sourcing.lead_id, item.size, oa_sourcing=oa_sourcing)
            
            if not asin_record:
                asin_count = self.db.query(AsinBank).filter(AsinBank.lead_id == oa_sourcing.lead_id).count()
                logger.warning(
                    f"No ASIN found for lead_id={oa_sourcing.lead_id}, size={item.size}. "
                    f"Creating record without ASIN. (AsinBank has {asin_count} records for this lead. "
                    f"Add via: POST /leads/{{lead_id}}/asins or POST /asin-bank)"
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
                date=datetime.utcnow(),
                platform="AMZ",  # Selling platform (Amazon)
                order_number=order_number,
                address=shipping_address,
                
                # Quantities
                og_qty=item.quantity,
                final_qty=item.quantity,
                
                # Pricing - use from oa_sourcing
                rsp=oa_sourcing.rsp,
                
                # FBA fields
                fba_msku=fba_msku,
                
                # Status and Location - set to Pending/Retailer for new purchases
                status="Pending",
                location="Retailer",
                
                # Audit
                audited=False
            )
            
            self.db.add(purchase_record)
            
            logger.info(
                f"Created Fit2Run purchase tracker record: "
                f"lead_id={oa_sourcing.lead_id}, "
                f"unique_id={item.unique_id}, "
                f"size={item.size}, "
                f"qty={item.quantity}, "
                f"order={order_number}"
            )
            
            return True, None
        
        except Exception as e:
            logger.error(f"Error creating Fit2Run purchase tracker record: {e}", exc_info=True)
            return False, str(e)
    
    def _process_sns_order(self, order_data: SNSOrderData) -> Tuple[bool, Optional[str]]:
        """
        Process a SNS order and create purchase tracker records.
        
        Args:
            order_data: Parsed order data
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Get SNS retailer
            sns_retailer = self.db.query(Retailer).filter(
                Retailer.name.ilike('%SNS%')
            ).first()
            
            if not sns_retailer:
                return False, "SNS retailer not found in database"
            
            created_count = 0
            skipped_count = 0
            
            for item in order_data.items:
                success, error = self._create_purchase_tracker_record_sns(
                    order_number=order_data.order_number,
                    item=item,
                    retailer=sns_retailer,
                    shipping_address=order_data.shipping_address
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
            logger.error(f"Error processing SNS order: {e}", exc_info=True)
            return False, str(e)
    
    def _create_purchase_tracker_record_sns(
        self,
        order_number: str,
        item: SNSOrderItem,
        retailer: Retailer,
        shipping_address: str = ""
    ) -> Tuple[bool, Optional[str]]:
        """
        Create a purchase tracker record for a SNS order item.
        
        Args:
            order_number: Order number
            item: SNS order item
            retailer: SNS retailer record
        
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
            
            # Look up ASIN from asin_bank by lead_id and size (with size normalization + OASourcing fallback)
            asin_record = self._get_asin_for_lead_and_size(oa_sourcing.lead_id, item.size, oa_sourcing=oa_sourcing)
            
            if not asin_record:
                asin_count = self.db.query(AsinBank).filter(AsinBank.lead_id == oa_sourcing.lead_id).count()
                logger.warning(
                    f"No ASIN found for lead_id={oa_sourcing.lead_id}, size={item.size}. "
                    f"Creating record without ASIN. (AsinBank has {asin_count} records for this lead. "
                    f"Add via: POST /leads/{{lead_id}}/asins or POST /asin-bank)"
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
                date=datetime.utcnow(),
                platform="AMZ",  # Selling platform (Amazon)
                order_number=order_number,
                address=shipping_address,
                
                # Quantities
                og_qty=item.quantity,
                final_qty=item.quantity,
                
                # Pricing - use from oa_sourcing
                rsp=oa_sourcing.rsp,
                
                # FBA fields
                fba_msku=fba_msku,
                
                # Status and Location - set to Pending/Retailer for new purchases
                status="Pending",
                location="Retailer",
                
                # Audit
                audited=False
            )
            
            self.db.add(purchase_record)
            
            logger.info(
                f"Created SNS purchase tracker record: "
                f"lead_id={oa_sourcing.lead_id}, "
                f"unique_id={item.unique_id}, "
                f"size={item.size}, "
                f"qty={item.quantity}, "
                f"order={order_number}"
            )
            
            return True, None
        
        except Exception as e:
            logger.error(f"Error creating SNS purchase tracker record: {e}", exc_info=True)
            return False, str(e)
    
    def _process_adidas_order(self, order_data: AdidasOrderData) -> Tuple[bool, Optional[str]]:
        """
        Process an Adidas order and create purchase tracker records.
        
        Args:
            order_data: Parsed order data
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Get Adidas retailer
            adidas_retailer = self.db.query(Retailer).filter(
                Retailer.name.ilike('%Adidas%')
            ).first()
            
            if not adidas_retailer:
                error_msg = "Adidas retailer not found in database"
                logger.error(error_msg)
                return False, error_msg
            
            order_number = order_data.order_number
            shipping_address = order_data.shipping_address
            
            # Process each item
            for item in order_data.items:
                success, error = self._create_purchase_tracker_record_adidas(
                    order_data=order_data,
                    item=item,
                    retailer=adidas_retailer,
                    order_number=order_number,
                    shipping_address=shipping_address
                )
                
                if not success:
                    logger.error(f"Failed to create purchase tracker record for Adidas item: {error}")
                    return False, error
            
            logger.info(f"Successfully processed Adidas order {order_number} with {len(order_data.items)} items")
            return True, None
            
        except Exception as e:
            logger.error(f"Error processing Adidas order: {e}", exc_info=True)
            return False, str(e)
    
    def _create_purchase_tracker_record_adidas(
        self,
        order_data: AdidasOrderData,
        item: AdidasOrderItem,
        retailer: Retailer,
        order_number: str,
        shipping_address: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Create a purchase tracker record for an Adidas order item.
        
        Args:
            order_data: Parsed order data
            item: Order item
            retailer: Retailer object
            order_number: Order number
            shipping_address: Shipping address
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Find OA sourcing record by unique_id
            oa_sourcing = self.db.query(OASourcing).filter(
                OASourcing.retailer_id == retailer.id,
                OASourcing.unique_id == item.unique_id
            ).first()
            
            if not oa_sourcing:
                error_msg = f"No OA sourcing found for Adidas unique_id={item.unique_id}"
                logger.warning(error_msg)
                return False, error_msg
            
            # Find ASIN record by size (with size normalization + OASourcing fallback)
            asin_record = self._get_asin_for_lead_and_size(oa_sourcing.lead_id, item.size, oa_sourcing=oa_sourcing)
            
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
                date=datetime.utcnow(),
                platform="AMZ",  # Selling platform (Amazon)
                order_number=order_number,
                address=shipping_address,
                
                # Quantities
                og_qty=item.quantity,
                final_qty=item.quantity,
                
                # Pricing - use from oa_sourcing
                rsp=oa_sourcing.rsp,
                
                # FBA fields
                fba_msku=fba_msku,
                
                # Status and Location - set to Pending/Retailer for new purchases
                status="Pending",
                location="Retailer",
                
                # Audit
                audited=False
            )
            
            self.db.add(purchase_record)
            
            logger.info(
                f"Created Adidas purchase tracker record: "
                f"lead_id={oa_sourcing.lead_id}, "
                f"unique_id={item.unique_id}, "
                f"size={item.size}, "
                f"qty={item.quantity}, "
                f"order={order_number}"
            )
            
            return True, None
        
        except Exception as e:
            logger.error(f"Error creating Adidas purchase tracker record: {e}", exc_info=True)
            return False, str(e)
    
    def _process_concepts_order(self, order_data: ConceptsOrderData) -> Tuple[bool, Optional[str]]:
        """
        Process a CNCPTS order and create purchase tracker records.
        
        Args:
            order_data: Parsed order data
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Get CNCPTS retailer
            concepts_retailer = self.db.query(Retailer).filter(
                Retailer.name.ilike('%CNCPTS%')
            ).first()
            
            if not concepts_retailer:
                error_msg = "CNCPTS retailer not found in database"
                logger.error(error_msg)
                return False, error_msg
            
            order_number = order_data.order_number
            shipping_address = order_data.shipping_address
            
            # Process each item
            for item in order_data.items:
                success, error = self._create_purchase_tracker_record_concepts(
                    order_data=order_data,
                    item=item,
                    retailer=concepts_retailer,
                    order_number=order_number,
                    shipping_address=shipping_address
                )
                
                if not success:
                    logger.error(f"Failed to create purchase tracker record for CNCPTS item: {error}")
                    return False, error
            
            logger.info(f"Successfully processed CNCPTS order {order_number} with {len(order_data.items)} items")
            return True, None
            
        except Exception as e:
            logger.error(f"Error processing CNCPTS order: {e}", exc_info=True)
            return False, str(e)
    
    def _create_purchase_tracker_record_concepts(
        self,
        order_data: ConceptsOrderData,
        item: ConceptsOrderItem,
        retailer: Retailer,
        order_number: str,
        shipping_address: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Create a purchase tracker record for a CNCPTS order item.
        
        Args:
            order_data: Parsed order data
            item: Order item
            retailer: Retailer object
            order_number: Order number
            shipping_address: Shipping address
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Find OA sourcing record by unique_id
            oa_sourcing = self.db.query(OASourcing).filter(
                OASourcing.retailer_id == retailer.id,
                OASourcing.unique_id == item.unique_id
            ).first()
            
            if not oa_sourcing:
                error_msg = f"No OA sourcing found for CNCPTS unique_id={item.unique_id}"
                logger.warning(error_msg)
                return False, error_msg
            
            # Find ASIN record by size (with size normalization + OASourcing fallback)
            asin_record = self._get_asin_for_lead_and_size(oa_sourcing.lead_id, item.size, oa_sourcing=oa_sourcing)
            
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
                date=datetime.utcnow(),
                platform="AMZ",  # Selling platform (Amazon)
                order_number=order_number,
                address=shipping_address,
                
                # Quantities
                og_qty=item.quantity,
                final_qty=item.quantity,
                
                # Pricing - use from oa_sourcing
                rsp=oa_sourcing.rsp,
                
                # FBA fields
                fba_msku=fba_msku,
                
                # Status and Location - set to Pending/Retailer for new purchases
                status="Pending",
                location="Retailer",
                
                # Audit
                audited=False
            )
            
            self.db.add(purchase_record)
            
            logger.info(
                f"Created CNCPTS purchase tracker record: "
                f"lead_id={oa_sourcing.lead_id}, "
                f"unique_id={item.unique_id}, "
                f"size={item.size}, "
                f"qty={item.quantity}, "
                f"order={order_number}"
            )
            
            return True, None
        
        except Exception as e:
            logger.error(f"Error creating CNCPTS purchase tracker record: {e}", exc_info=True)
            return False, str(e)
    
    def _process_sneaker_order(self, order_data: SneakerOrderData) -> Tuple[bool, Optional[str]]:
        """
        Process a Sneaker Politics order and create purchase tracker records.
        
        Args:
            order_data: Parsed order data
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Get Sneaker Politics retailer
            sneaker_retailer = self.db.query(Retailer).filter(
                Retailer.name.ilike('%Sneaker Politics%')
            ).first()
            
            if not sneaker_retailer:
                error_msg = "Sneaker Politics retailer not found in database"
                logger.error(error_msg)
                return False, error_msg
            
            order_number = order_data.order_number
            shipping_address = order_data.shipping_address
            
            # Process each item
            for item in order_data.items:
                success, error = self._create_purchase_tracker_record_sneaker(
                    order_data=order_data,
                    item=item,
                    retailer=sneaker_retailer,
                    order_number=order_number,
                    shipping_address=shipping_address
                )
                
                if not success:
                    logger.error(f"Failed to create purchase tracker record for Sneaker Politics item: {error}")
                    return False, error
            
            logger.info(f"Successfully processed Sneaker Politics order {order_number} with {len(order_data.items)} items")
            return True, None
            
        except Exception as e:
            logger.error(f"Error processing Sneaker Politics order: {e}", exc_info=True)
            return False, str(e)
    
    def _create_purchase_tracker_record_sneaker(
        self,
        order_data: SneakerOrderData,
        item: SneakerOrderItem,
        retailer: Retailer,
        order_number: str,
        shipping_address: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Create a purchase tracker record for a Sneaker Politics order item.
        
        Args:
            order_data: Parsed order data
            item: Order item
            retailer: Retailer object
            order_number: Order number
            shipping_address: Shipping address
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Find OA sourcing record by unique_id
            oa_sourcing = self.db.query(OASourcing).filter(
                OASourcing.retailer_id == retailer.id,
                OASourcing.unique_id == item.unique_id
            ).first()
            
            if not oa_sourcing:
                error_msg = f"No OA sourcing found for Sneaker Politics unique_id={item.unique_id}"
                logger.warning(error_msg)
                return False, error_msg
            
            # Get ASIN from OA sourcing
            asin = oa_sourcing.asin
            
            # Check if purchase tracker record already exists
            existing = self.db.query(PurchaseTracker).filter(
                PurchaseTracker.order_number == order_number,
                PurchaseTracker.retailer_id == retailer.id,
                PurchaseTracker.unique_id == item.unique_id,
                PurchaseTracker.size == item.size
            ).first()
            
            if existing:
                logger.info(f"Purchase tracker record already exists for Sneaker Politics order {order_number}, unique_id={item.unique_id}, size={item.size}")
                return True, None
            
            # Create purchase tracker record
            purchase_tracker = PurchaseTracker(
                order_number=order_number,
                retailer_id=retailer.id,
                asin=asin,
                unique_id=item.unique_id,
                size=item.size,
                quantity=item.quantity,
                shipping_address=shipping_address,
                order_date=datetime.now().date()
            )
            
            self.db.add(purchase_tracker)
            self.db.commit()
            
            logger.info(
                f"Created Sneaker Politics purchase tracker record: "
                f"order={order_number}, unique_id={item.unique_id}, size={item.size}, qty={item.quantity}"
            )
            
            return True, None
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating Sneaker Politics purchase tracker record: {e}", exc_info=True)
            return False, str(e)
    
    def _process_orleans_order(self, order_data: OrleansOrderData) -> Tuple[bool, Optional[str]]:
        """
        Process an Orleans Shoe Co order and create purchase tracker records.
        
        Args:
            order_data: Parsed order data
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Get Orleans Shoe Co retailer
            orleans_retailer = self.db.query(Retailer).filter(
                Retailer.name.ilike('%Orleans%')
            ).first()
            
            if not orleans_retailer:
                error_msg = "Orleans Shoe Co retailer not found in database"
                logger.error(error_msg)
                return False, error_msg
            
            order_number = order_data.order_number
            shipping_address = order_data.shipping_address
            
            # Process each item
            for item in order_data.items:
                success, error = self._create_purchase_tracker_record_orleans(
                    order_data=order_data,
                    item=item,
                    retailer=orleans_retailer,
                    order_number=order_number,
                    shipping_address=shipping_address
                )
                
                if not success:
                    logger.error(f"Failed to create purchase tracker record for Orleans item: {error}")
                    return False, error
            
            logger.info(f"Successfully processed Orleans Shoe Co order {order_number} with {len(order_data.items)} items")
            return True, None
            
        except Exception as e:
            logger.error(f"Error processing Orleans Shoe Co order: {e}", exc_info=True)
            return False, str(e)
    
    def _create_purchase_tracker_record_orleans(
        self,
        order_data: OrleansOrderData,
        item: OrleansOrderItem,
        retailer: Retailer,
        order_number: str,
        shipping_address: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Create a purchase tracker record for an Orleans Shoe Co order item.
        
        Args:
            order_data: Parsed order data
            item: Order item
            retailer: Retailer object
            order_number: Order number
            shipping_address: Shipping address
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Find OA sourcing record by unique_id
            oa_sourcing = self.db.query(OASourcing).filter(
                OASourcing.retailer_id == retailer.id,
                OASourcing.unique_id == item.unique_id
            ).first()
            
            if not oa_sourcing:
                error_msg = f"No OA sourcing found for Orleans unique_id={item.unique_id}"
                logger.warning(error_msg)
                return False, error_msg
            
            # Get ASIN from OA sourcing
            asin = oa_sourcing.asin
            
            # Check if purchase tracker record already exists
            existing = self.db.query(PurchaseTracker).filter(
                PurchaseTracker.order_number == order_number,
                PurchaseTracker.retailer_id == retailer.id,
                PurchaseTracker.unique_id == item.unique_id,
                PurchaseTracker.size == item.size
            ).first()
            
            if existing:
                logger.info(f"Purchase tracker record already exists for Orleans order {order_number}, unique_id={item.unique_id}, size={item.size}")
                return True, None
            
            # Create purchase tracker record
            purchase_tracker = PurchaseTracker(
                order_number=order_number,
                retailer_id=retailer.id,
                asin=asin,
                unique_id=item.unique_id,
                size=item.size,
                quantity=item.quantity,
                shipping_address=shipping_address,
                order_date=datetime.now().date()
            )
            
            self.db.add(purchase_tracker)
            self.db.commit()
            
            logger.info(
                f"Created Orleans purchase tracker record: "
                f"order={order_number}, unique_id={item.unique_id}, size={item.size}, qty={item.quantity}"
            )
            
            return True, None
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating Orleans purchase tracker record: {e}", exc_info=True)
            return False, str(e)
    
    def _process_bloomingdales_order(self, order_data: BloomingdalesOrderData) -> Tuple[bool, Optional[str]]:
        """
        Process a Bloomingdale's order and create purchase tracker records.
        
        Args:
            order_data: Parsed order data
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Get Bloomingdale's retailer
            bloomingdales_retailer = self.db.query(Retailer).filter(
                Retailer.name.ilike('%Bloomingdale%')
            ).first()
            
            if not bloomingdales_retailer:
                return False, "Bloomingdale's retailer not found in database"
            
            created_count = 0
            skipped_count = 0
            
            for item in order_data.items:
                success, error = self._create_purchase_tracker_record_bloomingdales(
                    order_number=order_data.order_number,
                    item=item,
                    retailer=bloomingdales_retailer,
                    shipping_address=order_data.shipping_address
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
    
    def _create_purchase_tracker_record_bloomingdales(
        self,
        order_number: str,
        item: BloomingdalesOrderItem,
        retailer: Retailer,
        shipping_address: str = ""
    ) -> Tuple[bool, Optional[str]]:
        """
        Create a purchase tracker record for a Bloomingdale's order item.
        
        Args:
            order_number: Order number
            item: Bloomingdale's order item
            retailer: Bloomingdale's retailer record
        
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
            
            # Look up ASIN from asin_bank by lead_id and size (with size normalization + OASourcing fallback)
            asin_record = self._get_asin_for_lead_and_size(oa_sourcing.lead_id, item.size, oa_sourcing=oa_sourcing)
            
            if not asin_record:
                asin_count = self.db.query(AsinBank).filter(AsinBank.lead_id == oa_sourcing.lead_id).count()
                logger.warning(
                    f"No ASIN found for lead_id={oa_sourcing.lead_id}, size={item.size}. "
                    f"Creating record without ASIN. (AsinBank has {asin_count} records for this lead. "
                    f"Add via: POST /leads/{{lead_id}}/asins or POST /asin-bank)"
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
                date=datetime.utcnow(),
                platform="AMZ",  # Selling platform (Amazon)
                order_number=order_number,
                address=shipping_address,
                
                # Quantities
                og_qty=item.quantity,
                final_qty=item.quantity,
                
                # Pricing - use from oa_sourcing
                rsp=oa_sourcing.rsp,
                
                # FBA fields
                fba_msku=fba_msku,
                
                # Status and Location - set to Pending/Retailer for new purchases
                status="Pending",
                location="Retailer",
                
                # Audit
                audited=False
            )
            
            self.db.add(purchase_record)
            
            logger.info(
                f"Created Bloomingdale's purchase tracker record: "
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
                },
                'jdsports': {
                    'parser': self.jdsports_parser,
                    'processor': self._process_jdsports_order
                },
                'revolve': {
                    'parser': self.revolve_parser,
                    'processor': self._process_revolve_order
                },
                'asos': {
                    'parser': self.asos_parser,
                    'processor': self._process_asos_order
                },
                'dtlr': {
                    'parser': self.dtlr_parser,
                    'processor': self._process_dtlr_order
                },
                'endclothing': {
                    'parser': self.endclothing_parser,
                    'processor': self._process_endclothing_order
                },
                'shopwss': {
                    'parser': self.shopwss_parser,
                    'processor': self._process_shopwss_order
                },
                # 'on': {
                #     'parser': self.on_parser,
                #     'processor': self._process_on_order
                # },
                'urbanoutfitters': {
                    'parser': self.urban_parser,
                    'processor': self._process_urban_order
                },
                'bloomingdales': {
                    'parser': self.bloomingdales_parser,
                    'processor': self._process_bloomingdales_order
                },
                'anthropologie': {
                    'parser': self.anthropologie_parser,
                    'processor': self._process_anthropologie_order
                },
                'nike': {
                    'parser': self.nike_parser,
                    'processor': self._process_nike_order
                },
                'carbon38': {
                    'parser': self.carbon38_parser,
                    'processor': self._process_carbon38_order
                },
                'gazelle': {
                    'parser': self.gazelle_parser,
                    'processor': self._process_gazelle_order
                },
                'netaporter': {
                    'parser': self.netaporter_parser,
                    'processor': self._process_netaporter_order
                },
                'fit2run': {
                    'parser': self.fit2run_parser,
                    'processor': self._process_fit2run_order
                },
                'sns': {
                    'parser': self.sns_parser,
                    'processor': self._process_sns_order
                },
                'adidas': {
                    'parser': self.adidas_parser,
                    'processor': self._process_adidas_order
                },
                'concepts': {
                    'parser': self.concepts_parser,
                    'processor': self._process_concepts_order
                },
                'sneaker': {
                    'parser': self.sneaker_parser,
                    'processor': self._process_sneaker_order
                },
                'orleans': {
                    'parser': self.orleans_parser,
                    'processor': self._process_orleans_order
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

            # Fallback: set order_datetime from email Date header when parser didn't extract it
            if hasattr(order_data, 'order_datetime') and order_data.order_datetime is None and email_data.date:
                try:
                    order_data.order_datetime = parsedate_to_datetime(email_data.date)
                except (ValueError, TypeError):
                    pass

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

