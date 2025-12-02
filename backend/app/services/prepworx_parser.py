"""
PrepWorx Email Parser Service
Specialized parser for PrepWorx "Inbound processed" emails using BeautifulSoup
Extracts shipment data and stores to checkin table automatically
"""

import logging
import re
from typing import List, Optional, Dict, Any
from datetime import datetime
from bs4 import BeautifulSoup

from app.models.email import EmailData

logger = logging.getLogger(__name__)


class PrepWorxItem:
    """Data class for a single PrepWorx item"""
    
    def __init__(
        self,
        item_name: str,
        asin: str,
        quantity: int,
        size: Optional[str] = None
    ):
        self.item_name = item_name
        self.asin = asin
        self.quantity = quantity
        self.size = size
    
    def __repr__(self):
        return f"<PrepWorxItem(name={self.item_name}, asin={self.asin}, size={self.size}, qty={self.quantity})>"


class PrepWorxShipmentData:
    """Data class for extracted PrepWorx shipment data"""
    
    def __init__(
        self,
        shipment_number: str,
        order_number: str,
        date_time: Optional[str] = None,
        secondary_code: Optional[str] = None,
        items: Optional[List[PrepWorxItem]] = None,
        email_date: Optional[datetime] = None
    ):
        self.shipment_number = shipment_number
        self.order_number = order_number  # Same as shipment_number (from subject)
        self.date_time = date_time
        self.secondary_code = secondary_code  # Optional code from email body
        self.items = items or []
        self.email_date = email_date
    
    def __repr__(self):
        return (
            f"<PrepWorxShipmentData("
            f"order={self.order_number}, "
            f"items_count={len(self.items)})>"
        )


class PrepWorxEmailParser:
    """
    Specialized parser for PrepWorx "Inbound processed" emails.
    
    Handles email formats like:
    Subject: "Inbound [SHIPMENT_NUMBER] has been processed"
    Content: Contains shipment details, items with ASINs, and quantities
    """
    
    # Email identification patterns
    PREPWORX_FROM_EMAIL = "beta@prepworx.io"
    PREPWORX_FROM_PATTERN = r"prepworx"
    SUBJECT_INBOUND_PATTERN = r"Inbound.*has been processed"
    
    def __init__(self):
        """Initialize the PrepWorx email parser."""
        pass
    
    @staticmethod
    def extract_size_from_item_name(item_name: str) -> Optional[str]:
        """
        Extract shoe size from item name.
        
        Sizes are typically:
        - Between 2 and 15
        - Can be decimal (e.g., 2.5, 8.5, 10.5)
        - Located near the end of the item name, before the product code
        
        Example: "Brooks Glycerin GTS 21 Blue Opal Black Nasturtium 13 110420-474"
        Returns: "13"
        
        Args:
            item_name: Full item name string
        
        Returns:
            Size as string, or None if not found
        """
        try:
            # Split by spaces and dashes to get tokens
            tokens = re.split(r'[\s\-]+', item_name.strip())
            
            # Look for size patterns (2-15, including decimals like 2.5, 8.5)
            size_pattern = r'^(\d{1,2}(?:\.\d{1,2})?)$'
            
            # Search from the end, but skip the last token (usually product code)
            # Size is typically 2nd or 3rd from the end
            for i in range(len(tokens) - 1, max(0, len(tokens) - 5), -1):
                token = tokens[i]
                match = re.match(size_pattern, token)
                if match:
                    size_val = float(match.group(1))
                    # Validate it's in the shoe size range (2-15)
                    if 2.0 <= size_val <= 15.0:
                        logger.debug(f"Extracted size '{match.group(1)}' from item: {item_name}")
                        return match.group(1)
            
            logger.debug(f"No size found in item name: {item_name}")
            return None
        
        except Exception as e:
            logger.warning(f"Error extracting size from '{item_name}': {e}")
            return None
    
    def is_prepworx_email(self, email_data: EmailData) -> bool:
        """
        Check if email is from PrepWorx.
        
        Args:
            email_data: EmailData object
        
        Returns:
            True if email is from PrepWorx, False otherwise
        """
        sender_lower = email_data.sender.lower()
        
        # Check for direct email or "PrepWorx" in sender name
        if self.PREPWORX_FROM_EMAIL.lower() in sender_lower:
            return True
        
        if re.search(self.PREPWORX_FROM_PATTERN, sender_lower, re.IGNORECASE):
            return True
        
        return False
    
    def is_inbound_processed_email(self, email_data: EmailData) -> bool:
        """
        Check if email is an "Inbound processed" notification.
        
        Args:
            email_data: EmailData object
        
        Returns:
            True if email is an inbound processed notification
        """
        if not email_data.subject:
            return False
        
        # Check subject for "Inbound" and "has been processed"
        return bool(re.search(self.SUBJECT_INBOUND_PATTERN, email_data.subject, re.IGNORECASE))
    
    def can_parse(self, email_data: EmailData) -> bool:
        """
        Check if this parser can handle the given email.
        
        Args:
            email_data: EmailData object
        
        Returns:
            True if parser can handle this email
        """
        return (
            self.is_prepworx_email(email_data) and 
            self.is_inbound_processed_email(email_data)
        )
    
    def parse_email(self, email_data: EmailData) -> Optional[PrepWorxShipmentData]:
        """
        Parse PrepWorx email and extract shipment data.
        
        Args:
            email_data: EmailData object containing email information
        
        Returns:
            PrepWorxShipmentData object with extracted data, or None if parsing fails
        """
        try:
            logger.info(f"Parsing PrepWorx email: {email_data.subject}")
            
            # Extract shipment number from subject
            shipment_number = self._extract_shipment_number_from_subject(email_data.subject)
            if not shipment_number:
                logger.warning("Could not extract shipment number from subject")
                return None
            
            logger.info(f"Extracted shipment number: {shipment_number}")
            
            # Use HTML content if available, otherwise use text
            content = email_data.html_content or email_data.text_content
            
            if not content:
                logger.warning("No content available for parsing")
                return None
            
            # Parse HTML or text content
            if email_data.html_content:
                shipment_data = self._parse_html_content(
                    email_data.html_content,
                    shipment_number,
                    email_data.date
                )
            else:
                shipment_data = self._parse_text_content(
                    email_data.text_content,
                    shipment_number,
                    email_data.date
                )
            
            if shipment_data and shipment_data.items:
                logger.info(
                    f"✓ Successfully parsed PrepWorx shipment: "
                    f"{shipment_data.shipment_number} with {len(shipment_data.items)} items"
                )
                return shipment_data
            else:
                logger.warning("Failed to extract items from email")
                return None
        
        except Exception as e:
            logger.error(f"Error parsing PrepWorx email: {e}", exc_info=True)
            return None
    
    def _extract_shipment_number_from_subject(self, subject: str) -> Optional[str]:
        """
        Extract shipment number from email subject.
        
        Handles patterns like:
        - "Inbound P0017327917518 has been processed"
        - "Inbound SNP 20046045 has been processed"
        - "Inbound Test-123 has been processed"
        
        Args:
            subject: Email subject line
        
        Returns:
            Shipment number or None
        """
        patterns = [
            # Full pattern with spaces and hyphens until "has been processed"
            r'Inbound\s+([A-Z0-9\s\-]+?)\s+has\s+been\s+processed',
            # Pattern with spaces and hyphens
            r'Inbound\s+([A-Z0-9\s\-]+)',
            # Standard alphanumeric pattern
            r'Inbound\s+([A-Z0-9]+)',
            # Pure numbers pattern
            r'Inbound\s+(\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, subject, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _parse_html_content(
        self,
        html_content: str,
        shipment_number: str,
        email_date: Optional[datetime]
    ) -> Optional[PrepWorxShipmentData]:
        """
        Parse HTML email content to extract shipment data.
        
        Args:
            html_content: HTML email body
            shipment_number: Shipment number from subject
            email_date: Email received date
        
        Returns:
            PrepWorxShipmentData object or None
        """
        try:
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extract text for pattern matching
            text = soup.get_text()
            
            # Extract secondary code (the identifier between shipment number and date)
            secondary_code = self._extract_secondary_code(text)
            
            # Extract date and time
            date_time = self._extract_datetime(text)
            
            # Extract items from HTML tables first, then fall back to text parsing
            items = self._extract_items_from_html(soup)
            
            if not items:
                # Fall back to text parsing
                items = self._extract_items_from_text(text)
            
            if not items:
                logger.warning("No items found in HTML content")
                return None
            
            # Order number is the shipment number from subject (e.g., P7375222977685635072)
            order_number = shipment_number
            
            return PrepWorxShipmentData(
                shipment_number=shipment_number,
                order_number=order_number,
                date_time=date_time,
                secondary_code=secondary_code,
                items=items,
                email_date=email_date
            )
        
        except Exception as e:
            logger.error(f"Error parsing HTML content: {e}", exc_info=True)
            return None
    
    def _parse_text_content(
        self,
        text_content: str,
        shipment_number: str,
        email_date: Optional[datetime]
    ) -> Optional[PrepWorxShipmentData]:
        """
        Parse plain text email content to extract shipment data.
        
        Args:
            text_content: Plain text email body
            shipment_number: Shipment number from subject
            email_date: Email received date
        
        Returns:
            PrepWorxShipmentData object or None
        """
        try:
            # Extract secondary code
            secondary_code = self._extract_secondary_code(text_content)
            
            # Extract date and time
            date_time = self._extract_datetime(text_content)
            
            # Extract items from text
            items = self._extract_items_from_text(text_content)
            
            if not items:
                logger.warning("No items found in text content")
                return None
            
            # Order number is the shipment number from subject (e.g., P7375222977685635072)
            order_number = shipment_number
            
            return PrepWorxShipmentData(
                shipment_number=shipment_number,
                order_number=order_number,
                date_time=date_time,
                secondary_code=secondary_code,
                items=items,
                email_date=email_date
            )
        
        except Exception as e:
            logger.error(f"Error parsing text content: {e}", exc_info=True)
            return None
    
    def _extract_secondary_code(self, content: str) -> Optional[str]:
        """
        Extract secondary order code from email content.
        
        This is typically a unique identifier that appears between
        the shipment number and the date.
        
        Args:
            content: Email content (text)
        
        Returns:
            Secondary code or None
        """
        patterns = [
            # Exact 20 character alphanumeric on its own line
            r'\n([A-Za-z0-9]{20})\n',
            # 15-25 chars before date
            r'\b([A-Za-z0-9]{15,25})\b(?=\s*\d+/\d+/\d+)',
            # Pattern before date line
            r'([A-Za-z0-9]{15,25})\s*\n\s*\d+/\d+/\d+',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                candidate = match.group(1).strip()
                # Validate it's not a shipment number (which typically starts with P followed by digits)
                if not re.match(r'^P\d+$', candidate):
                    return candidate
        
        return None
    
    def _extract_datetime(self, content: str) -> Optional[str]:
        """
        Extract date and time from email content.
        
        Handles patterns like:
        - "8/19/2025, 5:20:54 PM +00:00"
        - "8/19/2025 5:20:54 PM"
        
        Args:
            content: Email content (text)
        
        Returns:
            Date/time string or None
        """
        patterns = [
            # Full pattern with timezone
            r'(\d{1,2}/\d{1,2}/\d{4},\s+\d{1,2}:\d{2}:\d{2}\s+(?:AM|PM)\s+[+-]\d{2}:\d{2})',
            # Pattern without timezone
            r'(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}:\d{2}\s+(?:AM|PM))',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_items_from_html(self, soup: BeautifulSoup) -> List[PrepWorxItem]:
        """
        Extract items from HTML tables.
        
        Handles PrepWorx email format with table structure:
        <table>
          <tr><th>Item</th><th>Amount</th></tr>
          <tr>
            <td>Nike Air Max 270 GS Black/Orange/Red 6.5 943345-037 - B0DJDXB819</td>
            <td>2</td>
          </tr>
        </table>
        
        Args:
            soup: BeautifulSoup object
        
        Returns:
            List of PrepWorxItem objects
        """
        items = []
        
        try:
            # Find tables with class="purchase_content" which contain the item data
            # Use recursive=True to find all, then filter by checking for the header
            tables = soup.find_all('table')
            
            for table in tables:
                # Only process tables that have the "Item" and "Amount" header
                # This avoids processing parent tables that contain the same rows
                rows = table.find_all('tr', recursive=False)  # Only direct children, not nested
                
                # Check if this table has the Item/Amount header
                has_item_header = False
                for row in rows:
                    headers = row.find_all('th', recursive=False)
                    if len(headers) >= 2:
                        header_text = ' '.join(h.get_text(strip=True) for h in headers).lower()
                        if 'item' in header_text and 'amount' in header_text:
                            has_item_header = True
                            logger.debug(f"Found table with Item/Amount header")
                            break
                
                # Skip tables without the header
                if not has_item_header:
                    continue
                
                # Now process rows in this table only
                header_found = False
                for row in rows:
                    # Check if this is the header row
                    headers = row.find_all('th', recursive=False)
                    if len(headers) >= 2:
                        header_text = ' '.join(h.get_text(strip=True) for h in headers).lower()
                        if 'item' in header_text and 'amount' in header_text:
                            header_found = True
                            continue  # Skip the header row itself
                    
                    # Only process data rows AFTER finding the header
                    if not header_found:
                        continue
                    
                    # Get all cells in the row
                    cells = row.find_all('td', recursive=False)
                    
                    # Check if we have exactly 2 cells (Item and Amount columns)
                    if len(cells) == 2:
                        # This is an item row with item name and quantity
                        item_text = cells[0].get_text(strip=True)
                        quantity_text = cells[1].get_text(strip=True)
                        
                        # Skip empty rows
                        if not item_text or not quantity_text:
                            continue
                        
                        logger.debug(f"Attempting to parse row: [{item_text[:50]}...] | [{quantity_text}]")
                        
                        # Parse using table cell parser
                        item = self._parse_item_from_table_cells(item_text, quantity_text)
                        if item:
                            items.append(item)
                            logger.debug(f"✓ Parsed item: {item.item_name}, ASIN: {item.asin}, Qty: {item.quantity}")
                        else:
                            logger.debug(f"✗ Failed to parse row (no ASIN found)")
        
        except Exception as e:
            logger.error(f"Error extracting items from HTML: {e}")
        
        logger.info(f"📋 Total items extracted from HTML: {len(items)}")
        for idx, item in enumerate(items, 1):
            logger.info(f"  [{idx}] {item.item_name[:50]}... | ASIN: {item.asin} | Qty: {item.quantity}")
        
        return items
    
    def _extract_items_from_text(self, content: str) -> List[PrepWorxItem]:
        """
        Extract items from plain text content.
        
        Args:
            content: Text content
        
        Returns:
            List of PrepWorxItem objects
        """
        items = []
        
        try:
            lines = content.split('\n')
            
            for line in lines:
                trimmed_line = line.strip()
                
                # Skip empty lines and headers
                if not trimmed_line or len(trimmed_line) < 10:
                    continue
                
                if re.search(r'\b(item|amount|quantity)\b', trimmed_line, re.IGNORECASE):
                    continue
                
                # Try to parse as item
                item = self._parse_item_from_text(trimmed_line)
                if item:
                    items.append(item)
        
        except Exception as e:
            logger.error(f"Error extracting items from text: {e}")
        
        return items
    
    def _parse_item_from_table_cells(self, item_text: str, quantity_text: str) -> Optional[PrepWorxItem]:
        """
        Parse item from table cells (PrepWorx HTML format).
        
        Args:
            item_text: Item cell text (e.g., "Nike Air Max 270 GS Black/Orange/Red 6.5 943345-037 - B0DJDXB819")
            quantity_text: Quantity cell text (e.g., "2")
        
        Returns:
            PrepWorxItem object or None
        """
        try:
            # Clean text
            clean_item = item_text.strip()
            clean_qty = quantity_text.strip()
            
            # Extract ASIN (10 characters starting with B at the end after " - ")
            # Format: "... - B0DJDXB819"
            asin_match = re.search(r'-\s*([B][A-Z0-9]{9})\s*$', clean_item)
            if not asin_match:
                logger.warning(f"No ASIN found in item text: {clean_item[:50]}...")
                return None
            
            asin = asin_match.group(1)
            
            # Extract item name (everything before " - ASIN")
            asin_position = clean_item.rfind(' - ' + asin)
            if asin_position == -1:
                return None
            
            item_name = clean_item[:asin_position].strip()
            
            if not item_name:
                return None
            
            # Parse quantity
            try:
                quantity = int(clean_qty)
            except ValueError:
                logger.warning(f"Invalid quantity: {clean_qty}")
                return None
            
            # Extract size from item name
            size = self.extract_size_from_item_name(item_name)
            
            logger.debug(f"✓ Parsed from table: '{item_name}', ASIN: {asin}, Size: {size}, Quantity: {quantity}")
            
            return PrepWorxItem(
                item_name=item_name,
                asin=asin,
                quantity=quantity,
                size=size
            )
        
        except Exception as e:
            logger.error(f"Error parsing item from table cells: {e}")
            return None
    
    def _parse_item_from_text(self, text: str) -> Optional[PrepWorxItem]:
        """
        Parse individual item from text line.
        
        Handles patterns like:
        - "Adidas Gazelle Bold Mint Rush Impact Orange Women's 9 IG4386 - B0DDXBXNSP	2"
        - "Nike P-6000 White Gold Red Women's 7.5 BV1021-101 - B07PH4JSPN	2"
        - "On Running Cloudgo Black Eclipse 8.5 55.98635 - B09NM2VXF8	0"
        - "On Running Cloudmonster Frost Acacia 10.5 61.97786 - B0C5QGLQBN	-4"
        
        Args:
            text: Text line containing item data
        
        Returns:
            PrepWorxItem object or None
        """
        try:
            # Decode HTML entities
            clean_text = (
                text.replace('&#39;', "'")
                .replace('&quot;', '"')
                .replace('&amp;', '&')
            )
            
            # Extract ASIN (exactly 10 characters: B followed by 9 alphanumeric)
            asin_match = re.search(r'-\s*([B][A-Z0-9]{9})', clean_text)
            if not asin_match:
                return None
            
            asin = asin_match.group(1)
            
            # Extract quantity - try multiple patterns (including negative values)
            quantity = 1  # default
            quantity_found = False
            
            # Pattern 1: Tab-separated quantity at the end
            tab_qty_match = re.search(r'\t\s*(-?\d+)\s*$', clean_text)
            if tab_qty_match:
                quantity = int(tab_qty_match.group(1))
                quantity_found = True
            
            # Pattern 2: Space after ASIN (if tab pattern didn't match)
            if not quantity_found:
                after_asin_pattern = re.compile(asin + r'\s+(-?\d+)')
                qty_match = after_asin_pattern.search(clean_text)
                if qty_match:
                    quantity = int(qty_match.group(1))
                    quantity_found = True
            
            # Pattern 3: Any number at the end of the line
            if not quantity_found:
                end_qty_match = re.search(r'\s(-?\d+)\s*$', clean_text)
                if end_qty_match:
                    quantity = int(end_qty_match.group(1))
                    quantity_found = True
            
            # Extract item name (everything before " - ASIN")
            asin_position = clean_text.find(' - ' + asin)
            if asin_position == -1:
                return None
            
            item_name = clean_text[:asin_position].strip()
            
            if not item_name:
                return None
            
            # Extract size from item name
            size = self.extract_size_from_item_name(item_name)
            
            logger.debug(
                f"✓ Parsed item: '{item_name}', ASIN: {asin}, Size: {size}, Quantity: {quantity}"
            )
            
            return PrepWorxItem(
                item_name=item_name,
                asin=asin,
                quantity=quantity,
                size=size
            )
        
        except Exception as e:
            logger.error(f"Error parsing item from text: {e}")
            return None


class PrepWorxCheckinProcessor:
    """
    Processor for storing PrepWorx shipment data to the checkin table.
    """
    
    # Gmail label for processed emails
    PREPWORX_LABEL = "PrepWorx/Processed"
    
    def __init__(self, db_session, gmail_service=None):
        """
        Initialize the processor.
        
        Args:
            db_session: SQLAlchemy database session
            gmail_service: Optional Gmail service for labeling emails
        """
        self.db = db_session
        self.gmail_service = gmail_service
    
    def apply_gmail_label(self, message_id: str) -> bool:
        """
        Apply Gmail label to processed email.
        
        Args:
            message_id: Gmail message ID
        
        Returns:
            True if label was applied successfully
        """
        if not self.gmail_service:
            logger.debug("Gmail service not provided, skipping label")
            return False
        
        try:
            # Get or create label
            label = self.gmail_service.get_or_create_label(self.PREPWORX_LABEL)
            if not label:
                logger.warning(f"Could not create/get label: {self.PREPWORX_LABEL}")
                return False
            
            # Apply label to message
            self.gmail_service.add_label_to_message(message_id, label['id'])
            logger.info(f"Applied label '{self.PREPWORX_LABEL}' to message {message_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error applying Gmail label: {e}")
            return False
    
    def process_and_store(self, shipment_data: PrepWorxShipmentData, message_id: str = None) -> Dict[str, Any]:
        """
        Process PrepWorx shipment data and store to checkin table.
        
        Args:
            shipment_data: PrepWorxShipmentData object
        
        Returns:
            Dictionary with processing results
        """
        from app.models.database import Checkin, AsinBank
        
        try:
            stored_count = 0
            skipped_count = 0
            errors = []
            
            # Track items in current batch to avoid duplicates within the same email
            processed_in_batch = set()
            
            for item in shipment_data.items:
                try:
                    # Find or create ASIN in asin_bank
                    asin_record = self.db.query(AsinBank).filter(
                        AsinBank.asin == item.asin
                    ).first()
                    
                    if not asin_record:
                        # Create new ASIN bank entry with size
                        asin_record = AsinBank(
                            lead_id=shipment_data.order_number or "PREPWORX",
                            asin=item.asin,
                            size=item.size  # Size extracted from item name
                        )
                        self.db.add(asin_record)
                        self.db.flush()
                        logger.info(f"Created new ASIN bank entry: {item.asin} (size: {item.size})")
                    else:
                        # Update size if not set and we have it from the item
                        if not asin_record.size and item.size:
                            asin_record.size = item.size
                            logger.info(f"Updated ASIN bank {item.asin} with size: {item.size}")
                    
                    # Create unique key for this item in current batch
                    batch_key = (
                        shipment_data.order_number,
                        asin_record.id,
                        item.item_name,
                        item.quantity
                    )
                    
                    # Check if already processed in this batch
                    if batch_key in processed_in_batch:
                        logger.info(
                            f"Skipping duplicate in batch: Order {shipment_data.order_number}, "
                            f"ASIN {item.asin}, Qty {item.quantity}"
                        )
                        skipped_count += 1
                        continue
                    
                    # Check for duplicate entry in database
                    existing = self.db.query(Checkin).filter(
                        Checkin.order_number == shipment_data.order_number,
                        Checkin.asin_bank_id == asin_record.id,
                        Checkin.item_name == item.item_name,
                        Checkin.quantity == item.quantity
                    ).first()
                    
                    if existing:
                        # Skip duplicate entries from previous processing
                        logger.info(
                            f"Skipping duplicate in database: Order {shipment_data.order_number}, "
                            f"ASIN {item.asin}, Qty {item.quantity}"
                        )
                        skipped_count += 1
                        continue
                    
                    # Mark as processed in this batch
                    processed_in_batch.add(batch_key)
                    
                    # Create checkin record
                    checkin = Checkin(
                        order_number=shipment_data.order_number,
                        item_name=item.item_name,
                        asin_bank_id=asin_record.id,
                        quantity=item.quantity,
                        checked_in_at=datetime.utcnow()
                    )
                    
                    self.db.add(checkin)
                    stored_count += 1
                    
                    logger.info(
                        f"✓ Stored check-in: Order {shipment_data.order_number}, "
                        f"Item: {item.item_name}, ASIN: {item.asin}, Qty: {item.quantity}"
                    )
                
                except Exception as e:
                    error_msg = f"Error storing item {item.asin}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            
            # Commit all changes
            self.db.commit()
            
            result = {
                "success": True,
                "shipment_number": shipment_data.shipment_number,
                "order_number": shipment_data.order_number,
                "total_items": len(shipment_data.items),
                "stored_count": stored_count,
                "skipped_count": skipped_count,
                "errors": errors
            }
            
            logger.info(
                f"✅ PrepWorx checkin processing complete: "
                f"Shipment {shipment_data.shipment_number} - "
                f"Stored {stored_count}, Skipped {skipped_count}, Errors {len(errors)}"
            )
            
            # Apply Gmail label if message_id provided
            if message_id and stored_count > 0:
                label_applied = self.apply_gmail_label(message_id)
                result['label_applied'] = label_applied
            
            return result
        
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error processing PrepWorx shipment data: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "shipment_number": shipment_data.shipment_number
            }

