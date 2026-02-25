"""
DTLR Email Parser
Parses shipping order emails from DTLR
"""

import re
import logging
from typing import List, Optional, Tuple
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from app.models.email import EmailData

logger = logging.getLogger(__name__)


class DTLRShippingOrderItem(BaseModel):
    """Represents a single item from a DTLR shipping notification"""
    unique_id: str = Field(..., description="Unique identifier for the product (product name + color + size)")
    size: Optional[str] = Field(None, description="Size of the product")
    quantity: int = Field(..., description="Quantity of the product")
    product_name: Optional[str] = Field(None, description="Name of the product")
    color: Optional[str] = Field(None, description="Color of the product")
    tracking_number: Optional[str] = Field(None, description="Tracking number for this shipment")


class DTLRShippingData(BaseModel):
    """Represents DTLR shipping notification data"""
    order_number: str = Field(..., description="Order number")
    items: List[DTLRShippingOrderItem] = Field(..., description="List of shipped items")
    
    def __repr__(self):
        return f"<DTLRShippingData(order={self.order_number}, items={len(self.items)})>"


class DTLRCancellationOrderItem(BaseModel):
    """Represents a single item from a DTLR cancellation notification"""
    unique_id: str = Field(..., description="Unique identifier for the product (from image URL or product name)")
    size: Optional[str] = Field(None, description="Size of the product")
    quantity: int = Field(..., description="Quantity of the cancelled product")
    product_name: Optional[str] = Field(None, description="Name of the product")


class DTLRCancellationData(BaseModel):
    """Represents DTLR cancellation notification data"""
    order_number: str = Field(..., description="Order number")
    items: List[DTLRCancellationOrderItem] = Field(..., description="List of cancelled items")
    
    def __repr__(self):
        return f"<DTLRCancellationData(order={self.order_number}, items={len(self.items)})>"


class DTLROrderItem(BaseModel):
    """Represents a single item from a DTLR order confirmation"""
    unique_id: Optional[str] = Field(None, description="Unique identifier for the product (extracted for HOKA, empty for Nike/Jordan/Adidas)")
    size: str = Field(..., description="Size of the product")
    quantity: int = Field(..., description="Quantity of the product")
    product_name: str = Field(..., description="Name of the product")
    
    def __repr__(self):
        if self.product_name and len(self.product_name) > 50:
            product_display = self.product_name[:50] + "..."
        else:
            product_display = self.product_name or "Unknown"
        unique_id_display = self.unique_id if self.unique_id else "None"
        return f"<DTLROrderItem(unique_id={unique_id_display}, size={self.size}, qty={self.quantity}, product={product_display})>"


class DTLROrderData(BaseModel):
    """Represents DTLR order confirmation data"""
    order_number: str = Field(..., description="The order number")
    items: List[DTLROrderItem] = Field(..., description="List of items in the order")
    items_count: int = Field(0, description="Total number of items in the order")
    shipping_address: str = Field("", description="Normalized shipping address")

    def __init__(self, **data):
        super().__init__(**data)
        self.items_count = len(self.items)
    
    def __repr__(self):
        return f"<DTLROrderData(order={self.order_number}, items={len(self.items)})>"


class DTLREmailParser:
    """
    Parser for DTLR order emails.
    
    Handles email formats like:
    - Order Confirmation: Subject "Order #{order_number} confirmed"
    - Shipping: Subject "Order {order_number} Has Been Fulfilled"
    - Cancellation: Subject "There has been a change to your order"
    
    Structure: 
    - Order confirmations: Initial confirmation of order placement
    - Shipping: Multiple shipping confirmation emails per order (sent AS products ship)
    - Cancellation: Notification of cancelled items
    """
    
    # Email identification - Production
    DTLR_FROM_EMAIL = "custserv@dtlr.com"
    SUBJECT_ORDER_PATTERN = r"order\s+#(\d+)\s+confirmed"
    SUBJECT_SHIPPING_PATTERN = r"order\s+\d+\s+has\s+been\s+fulfilled|order\s+\d+\s+fulfilled"
    SUBJECT_CANCELLATION_PATTERN = r"there\s+has\s+been\s+a\s+change\s+to\s+your\s+order|change\s+to\s+your\s+order"
    
    # Email identification - Development (forwarded emails)
    DEV_DTLR_ORDER_FROM_EMAIL = "glenallagroupc@gmail.com"
    DEV_SUBJECT_ORDER_PATTERN = r"Fwd:\s*Order\s+#(\d+)\s+confirmed"
    
    def __init__(self):
        """Initialize the DTLR email parser."""
        from app.config.settings import get_settings
        self.settings = get_settings()
    
    @property
    def order_from_email(self) -> str:
        """Get the appropriate from email address based on environment."""
        if self.settings.is_development:
            return self.DEV_DTLR_ORDER_FROM_EMAIL
        return self.DTLR_FROM_EMAIL
    
    @property
    def order_subject_pattern(self) -> str:
        """Get the appropriate subject pattern (regex) for matching based on environment."""
        if self.settings.is_development:
            return self.DEV_SUBJECT_ORDER_PATTERN
        return self.SUBJECT_ORDER_PATTERN
    
    @property
    def order_subject_query(self) -> str:
        """Get the appropriate subject pattern for Gmail queries (non-regex) based on environment."""
        if self.settings.is_development:
            # For Gmail queries, use a simpler pattern that Gmail can understand
            # Gmail search will find "Fwd: Order #4594105 confirmed" with this pattern
            return "confirmed"
        return "confirmed"
    
    @property
    def update_from_email(self) -> str:
        """Get the appropriate from email address for updates (shipping/cancellation) based on environment."""
        if self.settings.is_development:
            return self.DEV_DTLR_ORDER_FROM_EMAIL
        return self.DTLR_FROM_EMAIL
    
    @property
    def shipping_subject_query(self) -> str:
        """Get the appropriate subject pattern for Gmail shipping queries based on environment."""
        if self.settings.is_development:
            return 'subject:"Fwd: Has Been Fulfilled"'
        return 'subject:"Has Been Fulfilled"'
    
    @property
    def cancellation_subject_query(self) -> str:
        """Get the appropriate subject pattern for Gmail cancellation queries based on environment."""
        if self.settings.is_development:
            return 'subject:"Fwd: There has been a change to your order"'
        return 'subject:"There has been a change to your order"'
    
    def is_dtlr_email(self, email_data: EmailData) -> bool:
        """Check if email is from DTLR"""
        sender_lower = email_data.sender.lower()
        
        # In development, check for forwarded emails from dev email address
        # Must also verify content to avoid misclassifying other retailers' forwarded emails
        if self.settings.is_development:
            if self.DEV_DTLR_ORDER_FROM_EMAIL.lower() in sender_lower:
                html = (email_data.html_content or "").lower()
                if "dtlr" in html:
                    return True
                return False
        
        # In production, check for DTLR email
        return self.DTLR_FROM_EMAIL.lower() in sender_lower
    
    def is_order_confirmation_email(self, email_data: EmailData) -> bool:
        """Check if email is an order confirmation"""
        if not self.is_dtlr_email(email_data):
            return False
        subject_pattern = self.order_subject_pattern
        return bool(re.search(subject_pattern, email_data.subject, re.IGNORECASE))
    
    def parse_email(self, email_data: EmailData):
        """
        Generic parse method that routes to the appropriate parser based on email type.
        
        Args:
            email_data: EmailData object containing email information
        
        Returns:
            DTLROrderData, DTLRShippingData, or DTLRCancellationData depending on email type
        """
        if self.is_order_confirmation_email(email_data):
            return self.parse_order_confirmation_email(email_data)
        elif self.is_shipping_email(email_data):
            return self.parse_shipping_email(email_data)
        elif self.is_cancellation_email(email_data):
            return self.parse_cancellation_email(email_data)
        else:
            logger.warning(f"Unknown DTLR email type: {email_data.subject}")
            return None
    
    def parse_order_confirmation_email(self, email_data: EmailData) -> Optional[DTLROrderData]:
        """
        Parse DTLR order confirmation email.
        
        Args:
            email_data: EmailData object containing email information
        
        Returns:
            DTLROrderData object or None if parsing fails
        """
        try:
            html_content = email_data.html_content
            
            if not html_content:
                logger.error("No HTML content in DTLR email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extract order number from subject or HTML
            order_number = self._extract_order_number_from_subject(email_data.subject, soup)
            if not order_number:
                logger.error("Failed to extract order number from DTLR email subject or HTML")
                return None
            
            logger.info(f"Extracted DTLR order number: {order_number}")
            
            # Extract items
            items = self._extract_order_items(soup)
            
            if not items:
                logger.error("Failed to extract any items from DTLR email")
                return None
            
            logger.info(f"Successfully extracted {len(items)} items from DTLR order {order_number}")
            for item in items:
                logger.debug(f"  - {item}")
            
            # Extract shipping address
            from app.utils.address_utils import normalize_shipping_address
            shipping_address = self._extract_shipping_address_from_order(soup)
            if shipping_address:
                normalized = normalize_shipping_address(shipping_address)
                logger.info(f"Extracted shipping address: {normalized}")
                shipping_address = normalized
            
            return DTLROrderData(order_number=order_number, items=items, shipping_address=shipping_address)
        
        except Exception as e:
            logger.error(f"Error parsing DTLR order confirmation email: {e}", exc_info=True)
            return None
    
    def _extract_order_items(self, soup: BeautifulSoup) -> List[DTLROrderItem]:
        """
        Extract order items from DTLR order confirmation email.
        
        DTLR email structure:
        - Products in table rows with images
        - Product name with quantity: "Jordan Air Jordan 1 Mid Toddler × 3"
        - Size: "5" (in separate span)
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            List of DTLROrderItem objects
        """
        items = []
        
        try:
            # Find all product images (look for cdn.shopify.com images in product rows)
            product_images = soup.find_all('img', src=lambda x: x and 'cdn.shopify.com' in str(x) and 'files' in str(x))
            
            logger.info(f"Found {len(product_images)} potential product images")
            
            for img in product_images:
                try:
                    # Get the parent row
                    parent_row = img.find_parent('tr')
                    if not parent_row:
                        continue
                    
                    # Extract product details from this row
                    product_details = self._extract_dtlr_product_details(parent_row, img)
                    
                    if product_details:
                        items.append(DTLROrderItem(
                            unique_id=product_details.get('unique_id'),
                            size=product_details['size'],
                            quantity=product_details['quantity'],
                            product_name=product_details['product_name']
                        ))
                        logger.info(
                            f"Extracted DTLR item: {product_details['product_name']} | "
                            f"unique_id={product_details.get('unique_id') or 'None'}, "
                            f"Size={product_details['size']}, "
                            f"Qty={product_details['quantity']}"
                        )
                
                except Exception as e:
                    logger.error(f"Error processing DTLR product row: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error extracting DTLR items: {e}", exc_info=True)
        
        # Log items with ID, size, and quantity
        if items:
            items_summary = [
                f"(ID: {item.unique_id or 'None'}, Size: {item.size}, Qty: {item.quantity})" 
                for item in items
            ]
            logger.info(f"[DTLR] Extracted {len(items)} items: {', '.join(items_summary)}")
        
        return items
    
    def _extract_dtlr_product_details(self, row, img) -> Optional[dict]:
        """
        Extract product details from a DTLR product row.
        
        Expected format:
        - Product name with quantity: "Jordan Air Jordan 1 Mid Toddler × 3"
        - Size in separate span: "5"
        - Image URL for HOKA: Hoka_1127895NCSW_M037...jpg
        
        Returns:
            Dictionary with unique_id, size, quantity, product_name or None
        """
        try:
            details = {}
            row_text = row.get_text()
            
            # Find product name span (contains × for quantity)
            product_span = row.find('span', style=lambda x: x and 'font-weight:600' in str(x))
            if not product_span:
                logger.warning("Product name span not found in DTLR row")
                return None
            
            product_text = product_span.get_text(strip=True)
            # Normalize whitespace (replace multiple spaces/newlines with single space)
            product_text = ' '.join(product_text.split())
            
            # Extract product name and quantity
            # Format: "Jordan Air Jordan 1 Mid Toddler × 3"
            if ' × ' in product_text:
                parts = product_text.rsplit(' × ', 1)
                product_name = parts[0].strip()
                quantity = int(parts[1].strip())
                details['product_name'] = product_name
                details['quantity'] = quantity
                logger.debug(f"Found product name: {product_name}, quantity: {quantity}")
            else:
                logger.warning(f"Product text doesn't contain × separator: {product_text}")
                return None
            
            # Extract size - find span with color #999
            size_span = row.find('span', style=lambda x: x and 'color:#999' in str(x))
            if size_span:
                size = size_span.get_text(strip=True)
                details['size'] = size
                logger.debug(f"Found size: {size}")
            else:
                logger.warning("Size not found in DTLR row")
                return None
            
            # Extract unique ID based on product brand
            unique_id = self._extract_unique_id_for_product(product_name, img)
            details['unique_id'] = unique_id
            if unique_id:
                logger.debug(f"Found unique ID: {unique_id}")
            else:
                logger.debug(f"No unique ID for {product_name} (Nike/Jordan/Adidas)")
            
            # Return only if we have the essential fields
            if details.get('product_name') and details.get('size') and details.get('quantity'):
                return details
            
            logger.warning(f"Missing essential fields: {details}")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting DTLR product details: {e}", exc_info=True)
            return None
    
    def _extract_unique_id_for_product(self, product_name: str, img) -> Optional[str]:
        """
        Extract unique ID based on product brand.
        
        Rules:
        - Nike/Jordan/Adidas: Return None (skip unique ID)
        - HOKA: Extract from image filename and format with dash
          Example: Hoka_1127895NCSW_M037...jpg -> 1127895-ncsw
        
        Args:
            product_name: Product name string
            img: Image BeautifulSoup tag
        
        Returns:
            Unique ID string or None
        """
        try:
            product_name_lower = product_name.lower()
            
            # Check if product is Nike, Jordan, or Adidas - skip unique ID
            if any(brand in product_name_lower for brand in ['nike', 'jordan', 'adidas']):
                logger.debug(f"Skipping unique ID for Nike/Jordan/Adidas product: {product_name}")
                return None
            
            # Check if product is HOKA - extract and format unique ID
            if 'hoka' in product_name_lower:
                img_src = img.get('src', '')
                # Pattern: Hoka_1127895NCSW_M037_compact_cropped.jpg
                # Extract: 1127895NCSW -> format as 1127895-ncsw
                match = re.search(r'Hoka_(\d+)([A-Z]+)_', img_src, re.IGNORECASE)
                if match:
                    numeric_part = match.group(1)
                    letter_part = match.group(2).lower()
                    unique_id = f"{numeric_part}-{letter_part}"
                    logger.debug(f"Extracted HOKA unique ID: {unique_id}")
                    return unique_id
                else:
                    logger.warning(f"Could not extract HOKA unique ID from image: {img_src}")
                    return None
            
            # For other brands, return None
            logger.debug(f"No unique ID extraction rule for product: {product_name}")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting unique ID: {e}")
            return None
    
    def _extract_shipping_address_from_order(self, soup: BeautifulSoup) -> str:
        """
        Extract shipping address from DTLR order confirmation email.
        
        DTLR structure:
        <h4>Shipping address</h4>
        <p>Griffin Myers<br>595 Lloyd Ln<br>STE D<br>Independence OR 97351<br>United States</p>
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            Shipping address or empty string
        """
        try:
            # Look for h4 with "Shipping address" text
            h4_tags = soup.find_all('h4')
            
            for header in h4_tags:
                # Normalize whitespace in header text
                header_text = ' '.join(header.get_text(strip=True).split())
                
                if 'shipping' in header_text.lower() and 'address' in header_text.lower():
                    # Find the next <p> tag which contains the address
                    address_p = header.find_next_sibling('p')
                    if address_p:
                        # Replace <br> tags with newlines before extracting text
                        for br in address_p.find_all('br'):
                            br.replace_with('\n')
                        
                        # Get address text with line breaks preserved
                        address_text = address_p.get_text()
                        
                        # Parse address lines
                        lines = [line.strip() for line in address_text.split('\n') if line.strip()]
                        
                        address_lines = []
                        for line in lines:
                            # Skip name (first line typically)
                            if re.match(r'^[A-Z][a-z]+\s+[A-Z][a-z]+$', line):
                                logger.debug(f"Skipping name line: {line}")
                                continue
                            
                            # Skip "United States"
                            if line.lower() in ['united states', 'usa', 'us']:
                                logger.debug(f"Skipping country line: {line}")
                                continue
                            
                            # Collect address lines (street, suite, city/state/zip)
                            address_lines.append(line)
                        
                        if address_lines:
                            # Join address lines with commas
                            address_combined = ', '.join(address_lines)
                            logger.debug(f"Extracted shipping address (raw): {address_combined}")
                            return address_combined
            
            logger.warning("Shipping address section not found in DTLR email")
            return ""
        
        except Exception as e:
            logger.error(f"Error extracting shipping address: {e}", exc_info=True)
            return ""
    
    def is_shipping_email(self, email_data: EmailData) -> bool:
        """Check if email is a shipping notification"""
        if not self.is_dtlr_email(email_data):
            return False
        return bool(re.search(self.SUBJECT_SHIPPING_PATTERN, email_data.subject, re.IGNORECASE))
    
    def is_cancellation_email(self, email_data: EmailData) -> bool:
        """Check if email is a cancellation notification"""
        if not self.is_dtlr_email(email_data):
            return False
        # Check subject pattern
        if re.search(self.SUBJECT_CANCELLATION_PATTERN, email_data.subject, re.IGNORECASE):
            return True
        # Also check for "change to your order" in body text
        if email_data.html_content and "change to your order" in email_data.html_content.lower():
            return True
        return False
    
    def parse_shipping_email(self, email_data: EmailData) -> Optional[DTLRShippingData]:
        """
        Parse DTLR shipping notification email.
        
        Only processes items where:
        - Ord Qty == Fulfilled Qty (item has been shipped)
        - Tracking column contains a tracking number (not "Shipping Separately -")
        
        Args:
            email_data: EmailData object containing email information
        
        Returns:
            DTLRShippingData object or None if parsing fails
        """
        try:
            html_content = email_data.html_content
            
            if not html_content:
                logger.error("No HTML content in DTLR shipping email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extract order number (try HTML first, then subject as fallback)
            order_number = self._extract_order_number(soup)
            if not order_number:
                # Fallback: try extracting from subject line
                order_number = self._extract_order_number_from_subject(email_data.subject)
            
            if not order_number:
                logger.error("Failed to extract order number from DTLR shipping email")
                return None
            
            logger.info(f"Extracted DTLR shipping order number: {order_number}")
            
            # Extract items from Order Details table
            items = self._extract_shipping_items(soup)
            
            if not items:
                logger.warning(f"No shipped items found in DTLR shipping email for order {order_number}")
                return None
            
            logger.info(f"Successfully extracted {len(items)} shipped items from DTLR shipping order {order_number}")
            for item in items:
                logger.debug(f"  - {item}")
            
            return DTLRShippingData(order_number=order_number, items=items)
        
        except Exception as e:
            logger.error(f"Error parsing DTLR shipping email: {e}", exc_info=True)
            return None
    
    def _extract_order_number(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract order number from DTLR shipping email HTML.
        
        Pattern: "Order #4794342" or "Order #: 4794342"
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            Order number or None
        """
        try:
            # Look for "Order #" pattern in text
            text = soup.get_text()
            match = re.search(r'Order\s*#\s*:?\s*(\d+)', text, re.IGNORECASE)
            if match:
                order_number = match.group(1)
                logger.debug(f"Found DTLR order number in HTML: {order_number}")
                return order_number
            
            return None
        
        except Exception as e:
            logger.error(f"Error extracting order number from DTLR shipping email HTML: {e}")
            return None
    
    def _extract_order_number_from_subject(self, subject: str, soup: BeautifulSoup = None) -> Optional[str]:
        """
        Extract order number from email subject line or HTML.
        
        Patterns:
        - Order confirmation: "Order #4594105 confirmed"
        - Shipping: "Order 4794342 Has Been Fulfilled"
        
        Args:
            subject: Email subject line
            soup: BeautifulSoup object (optional, for HTML fallback)
        
        Returns:
            Order number or None
        """
        try:
            # Try order confirmation pattern first: Order #4594105 confirmed
            match = re.search(r'Order\s+#(\d+)', subject, re.IGNORECASE)
            if match:
                order_number = match.group(1)
                logger.debug(f"Found DTLR order number in subject (confirmation): {order_number}")
                return order_number
            
            # Try shipping pattern: Order 4794342 Has Been Fulfilled
            match = re.search(r'Order\s+(\d+)\s+Has\s+Been\s+Fulfilled', subject, re.IGNORECASE)
            if match:
                order_number = match.group(1)
                logger.debug(f"Found DTLR order number in subject (shipping): {order_number}")
                return order_number
            
            # Fallback: extract from HTML if soup is provided
            if soup:
                # Look for order number in header
                # Pattern: <span>Order #4594105</span>
                order_span = soup.find('span', string=lambda x: x and 'Order #' in str(x))
                if order_span:
                    span_text = order_span.get_text(strip=True)
                    match = re.search(r'Order\s+#(\d+)', span_text, re.IGNORECASE)
                    if match:
                        order_number = match.group(1)
                        logger.debug(f"Found DTLR order number in HTML: {order_number}")
                        return order_number
            
            return None
        
        except Exception as e:
            logger.error(f"Error extracting order number from subject: {e}")
            return None
    
    def _extract_shipping_items(self, soup: BeautifulSoup) -> List[DTLRShippingOrderItem]:
        """
        Extract shipped items from Order Details table.
        
        Only includes items where:
        - Ord Qty == Fulfilled Qty (item has been shipped)
        - Tracking column contains a tracking number
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            List of DTLRShippingOrderItem objects
        """
        items = []
        
        try:
            # Find the Order Details table
            # Look for table with "Order Details" header
            order_details_table = self._find_order_details_table(soup)
            if not order_details_table:
                logger.warning("Could not find Order Details table in DTLR shipping email")
                return items
            
            # Find all data rows (skip header row)
            rows = order_details_table.find_all('tr')
            if len(rows) < 2:  # Need at least header + 1 data row
                logger.warning("Order Details table has no data rows")
                return items
            
            # Process each data row (skip header row at index 0)
            for row in rows[1:]:
                try:
                    cells = row.find_all('td')
                    if len(cells) < 4:
                        continue
                    
                    # Extract data from each column
                    description_cell = cells[0]  # Description column
                    ord_qty_cell = cells[1]      # Ord Qty column
                    fulfilled_qty_cell = cells[2]  # Fulfilled Qty column
                    tracking_cell = cells[3]     # Tracking column
                    
                    # Parse quantities
                    ord_qty = self._parse_quantity(ord_qty_cell.get_text(strip=True))
                    fulfilled_qty = self._parse_quantity(fulfilled_qty_cell.get_text(strip=True))
                    
                    # Only process items that have been shipped (Ord Qty == Fulfilled Qty)
                    if ord_qty is None or fulfilled_qty is None or ord_qty != fulfilled_qty:
                        logger.debug(f"Skipping item: Ord Qty={ord_qty}, Fulfilled Qty={fulfilled_qty} (not fully shipped)")
                        continue
                    
                    # Extract tracking number
                    tracking_text = tracking_cell.get_text(strip=True)
                    tracking_number = self._extract_tracking_number(tracking_text)
                    
                    # Skip if no tracking number (item says "Shipping Separately")
                    if not tracking_number:
                        logger.debug(f"Skipping item: No tracking number found (text: {tracking_text})")
                        continue
                    
                    # Parse description to extract product name, color, and size
                    description_text = description_cell.get_text(strip=True)
                    product_name, color, size = self._parse_description(description_text)
                    
                    # Create unique_id from product name, color, and size
                    unique_id = self._create_unique_id(product_name, color, size)
                    
                    items.append(DTLRShippingOrderItem(
                        unique_id=unique_id,
                        size=size,
                        quantity=fulfilled_qty,
                        product_name=product_name,
                        color=color,
                        tracking_number=tracking_number
                    ))
                    
                    logger.debug(
                        f"Extracted shipped item: {product_name} "
                        f"(Color={color}, Size={size}, Qty={fulfilled_qty}, "
                        f"Tracking={tracking_number})"
                    )
                
                except Exception as e:
                    logger.error(f"Error processing row in Order Details table: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error extracting shipping items: {e}", exc_info=True)
        
        return items
    
    def _find_order_details_table(self, soup: BeautifulSoup) -> Optional[BeautifulSoup]:
        """
        Find the Order Details table in the email.
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            BeautifulSoup table element or None
        """
        try:
            # Look for table with "Order Details" header
            # The header is in a row with colspan="4" and contains "Order Details"
            all_tables = soup.find_all('table')
            
            for table in all_tables:
                # Check if this table has "Order Details" header
                header_rows = table.find_all('tr')
                for row in header_rows:
                    header_cells = row.find_all('td', colspan='4')
                    for cell in header_cells:
                        if 'Order Details' in cell.get_text():
                            logger.debug("Found Order Details table")
                            return table
                
                # Also check for header row with "Order Details" text
                for row in header_rows:
                    row_text = row.get_text()
                    if 'Order Details' in row_text and 'Description' in row_text:
                        logger.debug("Found Order Details table by text match")
                        return table
            
            return None
        
        except Exception as e:
            logger.error(f"Error finding Order Details table: {e}")
            return None
    
    def _parse_quantity(self, qty_text: str) -> Optional[int]:
        """Parse quantity from text"""
        try:
            qty_text = qty_text.strip()
            if not qty_text:
                return None
            return int(qty_text)
        except (ValueError, AttributeError):
            return None
    
    def _extract_tracking_number(self, tracking_text: str) -> Optional[str]:
        """
        Extract tracking number from tracking column text.
        
        Examples:
        - "FedEx Economy - 395458965257" -> "395458965257"
        - "Shipping Separately - " -> None
        
        Args:
            tracking_text: Text from tracking column
        
        Returns:
            Tracking number or None
        """
        try:
            # Skip if it says "Shipping Separately"
            if 'Shipping Separately' in tracking_text:
                return None
            
            # Look for tracking number pattern (digits, typically 10-20 digits)
            match = re.search(r'(\d{10,20})', tracking_text)
            if match:
                return match.group(1)
            
            return None
        
        except Exception as e:
            logger.error(f"Error extracting tracking number: {e}")
            return None
    
    def _parse_description(self, description_text: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Parse product name, color, and size from description text.
        
        Format examples:
        - "AJ1 MID WHT/ LEGEND BLU 4-7Color=WHITE;Size=6"
        - "DUNK LOW DUSTY CACTUS/THUNDER BLUE-WHITEColor=BLUE;Size=12"
        
        Args:
            description_text: Text from Description column
        
        Returns:
            Tuple of (product_name, color, size)
        """
        try:
            product_name = None
            color = None
            size = None
            
            # Extract Color and Size using pattern matching
            # Pattern: Color=COLOR;Size=SIZE
            color_match = re.search(r'Color=([^;]+)', description_text, re.IGNORECASE)
            if color_match:
                color = color_match.group(1).strip()
            
            size_match = re.search(r'Size=([^\s;]+)', description_text, re.IGNORECASE)
            if size_match:
                size = size_match.group(1).strip()
            
            # Extract product name (everything before "Color=")
            color_pos = description_text.find('Color=')
            if color_pos > 0:
                product_name = description_text[:color_pos].strip()
            else:
                # Fallback: use entire description if no Color= found
                product_name = description_text.strip()
            
            # Clean up product name (remove extra whitespace)
            if product_name:
                product_name = re.sub(r'\s+', ' ', product_name).strip()
            
            return (product_name, color, size)
        
        except Exception as e:
            logger.error(f"Error parsing description: {e}")
            return (None, None, None)
    
    def _create_unique_id(self, product_name: Optional[str], color: Optional[str], size: Optional[str]) -> str:
        """
        Create a unique identifier for the product.
        
        Args:
            product_name: Product name
            color: Color
            size: Size
        
        Returns:
            Unique ID string
        """
        parts = []
        if product_name:
            parts.append(product_name)
        if color:
            parts.append(color)
        if size:
            parts.append(size)
        
        return "|".join(parts) if parts else "unknown"
    
    def parse_cancellation_email(self, email_data: EmailData) -> Optional[DTLRCancellationData]:
        """
        Parse DTLR cancellation notification email.
        
        Args:
            email_data: EmailData object containing email information
        
        Returns:
            DTLRCancellationData object or None if parsing fails
        """
        try:
            html_content = email_data.html_content
            
            if not html_content:
                logger.error("No HTML content in DTLR cancellation email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extract order number
            order_number = self._extract_order_number_from_cancellation_email(soup)
            if not order_number:
                logger.error("Failed to extract order number from DTLR cancellation email")
                return None
            
            logger.info(f"Extracted DTLR cancellation order number: {order_number}")
            
            # Extract cancelled items
            items = self._extract_cancellation_items(soup)
            
            if not items:
                logger.warning(f"No cancelled items found in DTLR cancellation email for order {order_number}")
                return None
            
            logger.info(f"Successfully extracted {len(items)} cancelled items from DTLR cancellation order {order_number}")
            for item in items:
                logger.debug(f"  - {item}")
            
            return DTLRCancellationData(order_number=order_number, items=items)
        
        except Exception as e:
            logger.error(f"Error parsing DTLR cancellation email: {e}", exc_info=True)
            return None
    
    def _extract_order_number_from_cancellation_email(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract order number from DTLR cancellation email.
        
        Pattern: "your order 4780694" or "order 4780694"
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            Order number or None
        """
        try:
            # Look for order number in text (pattern: "your order 4780694")
            text = soup.get_text()
            match = re.search(r'(?:your\s+)?order\s+(\d+)', text, re.IGNORECASE)
            if match:
                order_number = match.group(1)
                logger.debug(f"Found DTLR cancellation order number: {order_number}")
                return order_number
            
            # Also check for order number in bold tags (it's in <b>4780694</b>)
            bold_tags = soup.find_all('b')
            for bold in bold_tags:
                bold_text = bold.get_text(strip=True)
                if bold_text.isdigit() and len(bold_text) >= 6:  # Order numbers are typically 7+ digits
                    logger.debug(f"Found DTLR cancellation order number in bold: {bold_text}")
                    return bold_text
            
            logger.warning("Order number not found in DTLR cancellation email")
            return None
        
        except Exception as e:
            logger.error(f"Error extracting order number from DTLR cancellation email: {e}")
            return None
    
    def _extract_cancellation_items(self, soup: BeautifulSoup) -> List[DTLRCancellationOrderItem]:
        """
        Extract cancelled items from DTLR cancellation email.
        
        Structure: Table with "Product" and "Cancelled" columns
        - Product column contains image and product name
        - Cancelled column contains quantity
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            List of DTLRCancellationOrderItem objects
        """
        items = []
        
        try:
            # Find the product table (has "Product" and "Cancelled" headers)
            product_table = self._find_cancellation_product_table(soup)
            if not product_table:
                logger.warning("Could not find product table in DTLR cancellation email")
                return items
            
            # Find all data rows (skip header row)
            rows = product_table.find_all('tr')
            if len(rows) < 2:  # Need at least header + 1 data row
                logger.warning("Product table has no data rows")
                return items
            
            # Process each data row (skip header row)
            for row in rows[1:]:
                try:
                    cells = row.find_all('td')
                    if len(cells) < 3:
                        continue
                    
                    # Extract data from cells
                    # Cell 0: Image (optional)
                    # Cell 1: Product name
                    # Cell 2: Cancelled quantity
                    
                    # Get product name from second cell (or first if no image)
                    product_name_cell = cells[1] if len(cells) >= 3 else cells[0]
                    product_name = product_name_cell.get_text(strip=True)
                    
                    # Get cancelled quantity from last cell
                    cancelled_qty_cell = cells[-1]
                    cancelled_qty_text = cancelled_qty_cell.get_text(strip=True)
                    cancelled_qty = self._parse_quantity(cancelled_qty_text)
                    
                    if not product_name or cancelled_qty is None:
                        logger.debug(f"Skipping row: product_name={product_name}, qty={cancelled_qty}")
                        continue
                    
                    # Try to extract unique ID from image URL if available
                    unique_id = None
                    if len(cells) >= 1:
                        img = cells[0].find('img')
                        if img and img.get('src'):
                            img_src = img.get('src')
                            # Extract product code from Shopify CDN URL
                            # Example: adidas_JP5482_GS020.jpg -> JP5482
                            match = re.search(r'/([A-Z0-9_]+)\.(jpg|png|jpeg)', img_src, re.IGNORECASE)
                            if match:
                                unique_id = match.group(1)
                    
                    # Fallback: use product name as unique_id
                    if not unique_id:
                        unique_id = product_name
                    
                    items.append(DTLRCancellationOrderItem(
                        unique_id=unique_id,
                        size=None,  # Size not available in cancellation emails
                        quantity=cancelled_qty,
                        product_name=product_name
                    ))
                    
                    logger.debug(
                        f"Extracted cancelled item: {product_name} "
                        f"(Qty={cancelled_qty}, unique_id={unique_id})"
                    )
                
                except Exception as e:
                    logger.error(f"Error processing row in cancellation table: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error extracting cancellation items: {e}", exc_info=True)
        
        return items
    
    def _find_cancellation_product_table(self, soup: BeautifulSoup) -> Optional[BeautifulSoup]:
        """
        Find the product table in cancellation email.
        
        The table has headers "Product" and "Cancelled"
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            BeautifulSoup table element or None
        """
        try:
            # Look for table with "Product" and "Cancelled" headers
            all_tables = soup.find_all('table')
            
            for table in all_tables:
                # Check if this table has "Product" and "Cancelled" headers
                header_rows = table.find_all('tr')
                for row in header_rows:
                    row_text = row.get_text()
                    if 'Product' in row_text and 'Cancelled' in row_text:
                        logger.debug("Found cancellation product table")
                        return table
            
            return None
        
        except Exception as e:
            logger.error(f"Error finding cancellation product table: {e}")
            return None

