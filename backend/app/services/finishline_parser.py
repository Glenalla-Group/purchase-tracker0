"""
Finish Line Email Parser
Parses order confirmation emails from Finish Line using BeautifulSoup

Email Format:
- From: finishline@notifications.finishline.com
- Subject: "Your Order is Official!"
- Order Number: Extracted from <a class="link"> tag in email body

HTML Structure:
- Products are in separate tables with product images
- Product image URL contains SKU: media.finishline.com/s/finishline/DM4044_108
- Product name in <td class="orderDetails bold">
- Size in <td class="orderDetails"> containing "Size: 12.0"
- Quantity in <td class="orderDetails"> containing "Quantity: 2"

Parsing Method:
- Uses BeautifulSoup to find and parse HTML elements
- Finds <td> tags with specific classes
- Extracts text by splitting on colon separator
- No regex pattern matching on text content

Example Extraction:
- Order: 60010107385
- Product: Men's Nike Cortez Casual Shoes
- SKU: DM4044_108
- Size: 12.0 → 12 (cleaned)
- Quantity: 2
"""

import re
import logging
from typing import List, Optional
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from app.models.email import EmailData
from app.utils.address_utils import normalize_shipping_address
from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class FinishLineOrderItem(BaseModel):
    unique_id: str = Field(..., description="Unique identifier for the product (e.g., SKU, style code)")
    size: str = Field(..., description="Size of the product")
    quantity: int = Field(..., description="Quantity of the product")
    product_name: Optional[str] = Field(None, description="Name of the product")
    
    def __repr__(self):
        if self.product_name and len(self.product_name) > 50:
            product_display = self.product_name[:50] + "..."
        else:
            product_display = self.product_name or "Unknown"
        return f"<FinishLineOrderItem(unique_id={self.unique_id}, size={self.size}, qty={self.quantity}, product={product_display})>"


class FinishLineOrderData(BaseModel):
    order_number: str = Field(..., description="The order number")
    items: List[FinishLineOrderItem] = Field(..., description="List of items in the order")
    items_count: int = Field(0, description="Total number of items in the order")
    shipping_address: str = Field("", description="Normalized shipping address")

    def __init__(self, **data):
        super().__init__(**data)
        self.items_count = len(self.items)


class FinishLineCancellationData(BaseModel):
    order_number: str = Field(..., description="The order number")
    items: List[FinishLineOrderItem] = Field(..., description="List of cancelled items")
    is_full_cancellation: bool = Field(False, description="Whether this is a full order cancellation")


class FinishLineShippingOrderItem(BaseModel):
    """Item from Finish Line shipping notification - quantity is aggregated by (unique_id, size)"""
    unique_id: str = Field(..., description="Unique identifier for the product (SKU)")
    size: str = Field(..., description="Size of the product")
    quantity: int = Field(..., description="Shipped quantity (aggregated if same product+size)")
    tracking: Optional[str] = Field(None, description="Tracking number for this shipment")
    product_name: Optional[str] = Field(None, description="Name of the product")


class FinishLineShippingData(BaseModel):
    """Represents Finish Line shipping/order update notification data"""
    order_number: str = Field(..., description="The order number")
    items: List[FinishLineShippingOrderItem] = Field(..., description="Shipped items (aggregated by unique_id+size)")
    shipping_address: str = Field("", description="Normalized shipping address")
    cancellation_items: Optional[List[FinishLineOrderItem]] = Field(
        None,
        description="Cancelled items (from partial update emails). Qty 0 = cancel all for that product+size."
    )


class FinishLineEmailParser:
    # Email identification - Order Confirmation (Production)
    FINISHLINE_FROM_EMAIL = "finishline@notifications.finishline.com"
    SUBJECT_ORDER_PATTERN = r"your order is official!"
    
    # Email identification - Development (forwarded emails)
    DEV_FINISHLINE_ORDER_FROM_EMAIL = "glenallagroupc@gmail.com"
    DEV_SUBJECT_ORDER_PATTERN = r"Fwd:\s*Your Order is Official!"
    
    # Email identification - Cancellation (Production)
    SUBJECT_CANCELLATION_PATTERN = r"sorry.*had to cancel your order"
    
    # Email identification - Cancellation (Development)
    DEV_SUBJECT_CANCELLATION_PATTERN = r"(?:Fwd:\s*)?.*sorry.*had to cancel your order"
    
    # Email identification - Shipping / Order Update (Production)
    SUBJECT_SHIPPING_PATTERN = r"we've got the scoop"
    FINISHLINE_UPDATE_FROM_EMAIL = "finishline@notifications.finishline.com"
    
    # Email identification - Shipping (Development)
    DEV_SUBJECT_SHIPPING_PATTERN = r"(?:Fwd:\s*)?.*we've got the scoop"

    @property
    def update_from_email(self) -> str:
        """Get the from email for shipping/update emails (same as order for Finish Line)."""
        if self.settings.is_development:
            return self.DEV_FINISHLINE_ORDER_FROM_EMAIL
        return self.FINISHLINE_UPDATE_FROM_EMAIL

    @property
    def shipping_subject_query(self) -> str:
        """Gmail query for shipping/update emails."""
        if self.settings.is_development:
            return 'subject:"Fwd: Your order. We\'ve got the scoop on it."'
        return 'subject:"Your order. We\'ve got the scoop on it."'

    @property
    def cancellation_subject_query(self) -> str:
        """Gmail query for full cancellation emails."""
        if self.settings.is_development:
            return 'subject:"Fwd: Sorry, but we had to cancel your order."'
        return 'subject:"Sorry, but we had to cancel your order."'

    def __init__(self):
        """Initialize the Finish Line email parser."""
        self.settings = get_settings()
    
    @property
    def order_from_email(self) -> str:
        """Get the appropriate from email address based on environment."""
        if self.settings.is_development:
            return self.DEV_FINISHLINE_ORDER_FROM_EMAIL
        return self.FINISHLINE_FROM_EMAIL
    
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
            return "Fwd: Your Order is Official!"
        return "Your Order is Official!"

    def is_finishline_email(self, email_data: EmailData) -> bool:
        """Check if email is from Finish Line"""
        sender_lower = email_data.sender.lower()
        
        # In development, check for forwarded emails from dev email address
        if self.settings.is_development:
            if self.DEV_FINISHLINE_ORDER_FROM_EMAIL.lower() in sender_lower:
                return True
        
        # In production, check for Finish Line email
        return self.FINISHLINE_FROM_EMAIL.lower() in sender_lower

    def is_order_confirmation_email(self, email_data: EmailData) -> bool:
        """Check if email is an order confirmation"""
        # Make sure it's not a cancellation or shipping email
        if self.is_cancellation_email(email_data):
            return False
        if self.is_shipping_email(email_data):
            return False
        
        subject_lower = email_data.subject.lower()
        pattern = self.order_subject_pattern
        
        # Use regex matching for subject pattern
        import re
        return bool(re.search(pattern, subject_lower, re.IGNORECASE))
    
    def is_shipping_email(self, email_data: EmailData) -> bool:
        """Check if email is a shipping/order update notification."""
        if not self.is_finishline_email(email_data):
            return False
        subject_lower = email_data.subject.lower()
        if self.settings.is_development:
            return bool(re.search(self.DEV_SUBJECT_SHIPPING_PATTERN, subject_lower, re.IGNORECASE))
        return bool(re.search(self.SUBJECT_SHIPPING_PATTERN, subject_lower, re.IGNORECASE))
    
    def is_cancellation_email(self, email_data: EmailData) -> bool:
        """Check if email is a cancellation notification (full cancellation only).
        Partial shipping+cancel emails use 'We've got the scoop' subject and are handled by shipping parser."""
        if not self.is_finishline_email(email_data):
            return False
        # Shipping/update emails (scoop subject) are handled by parse_shipping_email
        if self.is_shipping_email(email_data):
            return False
        
        subject_lower = email_data.subject.lower()
        body_lower = email_data.html_content.lower() if email_data.html_content else ""
        
        # Check subject for cancellation keywords
        if self.settings.is_development:
            pattern = self.DEV_SUBJECT_CANCELLATION_PATTERN
        else:
            pattern = self.SUBJECT_CANCELLATION_PATTERN
        
        subject_match = bool(re.search(pattern, subject_lower, re.IGNORECASE))
        
        # Check body for cancellation indicators
        has_canceled_image = "order canceled" in body_lower or "alt=\"Order Canceled\"" in body_lower
        has_canceled_section = "canceled" in body_lower and ("#d81e05" in body_lower or "border:1px solid #d81e05" in body_lower)
        has_canceled_text = "your order has been canceled" in body_lower or "this item has been removed" in body_lower
        
        return subject_match or has_canceled_image or has_canceled_section or has_canceled_text

    def parse_email(self, email_data: EmailData):
        """
        Generic parse method that routes to the appropriate parser based on email type.
        
        Args:
            email_data: Email data to parse
        
        Returns:
            FinishLineOrderData, FinishLineCancellationData, or FinishLineShippingData depending on email type
        """
        if self.is_shipping_email(email_data):
            return self.parse_shipping_email(email_data)
        if self.is_cancellation_email(email_data):
            return self.parse_cancellation_email(email_data)
        if self.is_order_confirmation_email(email_data):
            return self.parse_order_confirmation_email(email_data)
        logger.warning(f"Unknown Finish Line email type: {email_data.subject}")
        return None
    
    def parse_order_confirmation_email(self, email_data: EmailData) -> Optional[FinishLineOrderData]:
        """
        Parse Finish Line order confirmation email.
        
        Args:
            email_data: EmailData object containing email information
        
        Returns:
            FinishLineOrderData object or None if parsing fails
        """
        try:
            html_content = email_data.html_content
            
            if not html_content:
                logger.error("No HTML content in Finish Line email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extract order number from email content
            order_number = self._extract_order_number(soup, email_data.subject)
            if not order_number:
                logger.error("Failed to extract order number from Finish Line email")
                return None
            
            logger.info(f"Extracted Finish Line order number: {order_number}")
            
            # Extract items using BeautifulSoup
            items = self._extract_items(soup)
            
            if not items:
                logger.error("Failed to extract any items from Finish Line email")
                return None
            
            logger.info(f"Successfully extracted {len(items)} items from Finish Line order {order_number}")
            for item in items:
                logger.debug(f"  - {item}")
            
            # Extract shipping address
            shipping_address = self._extract_shipping_address(soup)
            if shipping_address:
                logger.info(f"Extracted shipping address: {shipping_address}")
            
            return FinishLineOrderData(order_number=order_number, items=items, shipping_address=shipping_address)
        
        except Exception as e:
            logger.error(f"Error parsing Finish Line email: {e}", exc_info=True)
            return None
    
    def parse_cancellation_email(self, email_data: EmailData) -> Optional[FinishLineCancellationData]:
        """
        Parse Finish Line cancellation notification email.
        
        Args:
            email_data: Email data to parse
        
        Returns:
            FinishLineCancellationData object or None if parsing fails
        """
        try:
            html_content = email_data.html_content
            
            if not html_content:
                logger.warning("No HTML content found in cancellation email")
                return None
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract order number
            order_number = self._extract_order_number(soup, email_data.subject)
            if not order_number:
                logger.warning("Could not extract order number from cancellation email")
                return None
            
            # Detect if it's full or partial cancellation
            # Emails with subject "Sorry, but we had to cancel your order" are always full order cancellation
            # (this is the only subject that triggers the cancellation query)
            subject_lower = (email_data.subject or "").lower()
            if re.search(self.SUBJECT_CANCELLATION_PATTERN, subject_lower) or \
               (self.settings.is_development and re.search(self.DEV_SUBJECT_CANCELLATION_PATTERN, subject_lower)):
                is_full_cancellation = True
            else:
                is_full_cancellation = self._detect_full_cancellation(soup)
            
            # Extract cancelled items
            items = self._extract_cancellation_items(soup, is_full_cancellation)
            if not items:
                logger.warning(f"No cancelled items found in cancellation email for order {order_number}")
                return None
            
            logger.info(f"Successfully extracted {len(items)} cancelled items from Finish Line cancellation order {order_number} (full={is_full_cancellation})")
            for item in items:
                logger.debug(f"  - {item}")
            
            return FinishLineCancellationData(
                order_number=order_number,
                items=items,
                is_full_cancellation=is_full_cancellation
            )
            
        except Exception as e:
            logger.error(f"Error parsing Finish Line cancellation email: {e}", exc_info=True)
            return None

    def parse_shipping_email(self, email_data: EmailData) -> Optional[FinishLineShippingData]:
        """
        Parse Finish Line shipping/order update email.
        
        Handles:
        1. Pure shipping: items with Tracking numbers (aggregate same product+size)
        2. Skip: "Processing - This item will ship soon" blocks
        3. Partial update: Shipping + Canceled sections (Quantity: 0 = cancel all)
        
        Returns:
            FinishLineShippingData with shipping items (and optional cancellation_items for partial updates)
        """
        try:
            html_content = email_data.html_content
            if not html_content:
                logger.error("No HTML content in Finish Line shipping email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            order_number = self._extract_order_number(soup, email_data.subject)
            if not order_number:
                logger.error("Failed to extract order number from Finish Line shipping email")
                return None
            
            shipping_items, cancellation_items = self._extract_shipping_email_blocks(soup)
            
            # Aggregate shipping items by (unique_id, size): sum quantities, keep first tracking
            aggregated = self._aggregate_shipping_items(shipping_items)
            
            if not aggregated and not cancellation_items:
                logger.warning(f"No valid shipping or cancellation items in Finish Line email for order {order_number}")
                return None
            
            shipping_address = self._extract_shipping_address(soup)
            
            return FinishLineShippingData(
                order_number=order_number,
                items=aggregated,
                shipping_address=shipping_address,
                cancellation_items=cancellation_items if cancellation_items else None
            )
        except Exception as e:
            logger.error(f"Error parsing Finish Line shipping email: {e}", exc_info=True)
            return None

    def _build_product_lookup_from_email(self, soup: BeautifulSoup) -> List[dict]:
        """
        Pre-scan email to collect (unique_id, product_name, size) from blocks that have product images.
        Includes Processing and Shipping blocks - used to infer unique_id for Canceled blocks that lack images.
        """
        lookup = []
        all_tables = soup.find_all('table')
        for table in all_tables:
            table_str = str(table)
            table_text = table.get_text()
            is_status_header = (
                ('height:60px' in table_str or 'height="60"' in table_str) and
                ('Shipping' in table_text or 'Processing' in table_text or 'Canceled' in table_text)
            )
            if not is_status_header:
                continue
            next_table = table.find_next('table')
            if not next_table or next_table == table:
                continue
            details = self._extract_shipping_product_details(next_table)
            if details and details.get('unique_id') and details.get('product_name') and details.get('size'):
                lookup.append({
                    'unique_id': details['unique_id'],
                    'product_name': (details['product_name'] or '').strip(),
                    'size': self._clean_size(details['size'])
                })
        return lookup

    def _find_unique_id_by_product_match(
        self,
        product_name: str,
        size: str,
        lookup: List[dict],
        shipping_items: List
    ) -> Optional[str]:
        """Find unique_id by matching product_name + size from lookup or shipping_items."""
        if not product_name or not size:
            return None
        cleaned_size = self._clean_size(size)
        prod_norm = (product_name or '').strip().lower()
        # Check lookup (from Processing/Shipping/Canceled blocks with images)
        for entry in lookup:
            if self._clean_size(entry.get('size', '')) != cleaned_size:
                continue
            entry_name = (entry.get('product_name') or '').strip().lower()
            if not entry_name:
                continue
            if prod_norm in entry_name or entry_name in prod_norm:
                return entry['unique_id']
        # Check preceding shipping items
        for si in shipping_items:
            if si.product_name and self._clean_size(si.size) == cleaned_size:
                si_name = (si.product_name or '').strip().lower()
                if prod_norm in si_name or si_name in prod_norm:
                    return si.unique_id
        return None

    def _find_unique_id_by_size_only(
        self,
        size: str,
        lookup: List[dict],
        shipping_items: List
    ) -> Optional[str]:
        """Find unique_id by size only when exactly one product matches (fallback when product_name missing)."""
        if not size:
            return None
        cleaned_size = self._clean_size(size)
        matches = set()
        for entry in lookup:
            if self._clean_size(entry.get('size', '')) == cleaned_size:
                matches.add(entry['unique_id'])
        for si in shipping_items:
            if self._clean_size(si.size) == cleaned_size:
                matches.add(si.unique_id)
        if len(matches) == 1:
            return next(iter(matches))
        return None

    def _extract_shipping_email_blocks(self, soup: BeautifulSoup) -> tuple:
        """
        Extract shipping and cancellation blocks from Finish Line order update email.
        
        Each block: [header_table (60px)][product_table]
        Header types:
        - Shipping + Tracking <a> -> shipped
        - Processing + "ship soon" -> skip
        - Canceled (red #d81e05) -> cancelled, Quantity: 0 means cancel all
        """
        shipping_items = []
        cancellation_items = []
        # Pre-scan: collect unique_id from Processing/Shipping blocks for Canceled inference
        product_lookup = self._build_product_lookup_from_email(soup)
        
        # Find all header tables (status row: Shipping, Processing, or Canceled)
        # Pattern: tables with height 60px, width 598
        all_tables = soup.find_all('table')
        
        for i, table in enumerate(all_tables):
            table_str = str(table)
            table_text = table.get_text()
            
            # Check if this is a status header table
            is_status_header = (
                'height:60px' in table_str or 'height="60"' in table_str
            ) and (
                'Shipping' in table_text or 'Processing' in table_text or 'Canceled' in table_text
            )
            
            if not is_status_header:
                continue
            
            # Determine block type
            if 'Canceled' in table_text and ('#d81e05' in table_str or 'd81e05' in table_str.lower()):
                block_type = 'canceled'
            elif 'This item will ship soon' in table_text or ('Processing' in table_text and 'ship soon' in table_text.lower()):
                block_type = 'skip'
            elif 'Tracking' in table_text:
                block_type = 'shipped'
            else:
                block_type = 'skip'
            
            if block_type == 'skip':
                continue
            
            # Get tracking from header (for shipped blocks) - text of Tracking <a> link
            tracking = None
            if block_type == 'shipped':
                tracking_link = table.find('a', href=True)
                if tracking_link:
                    tracking = tracking_link.get_text(strip=True)
                    # Validate it looks like a tracking number (10+ alphanumeric)
                    if tracking and not re.match(r'^[\dA-Za-z]{10,}$', tracking.replace(' ', '')):
                        tracking = None
            
            # Find next table (product details) - use find_next for document order
            next_table = table.find_next('table')
            if not next_table or next_table == table:
                continue
            
            # Extract product from next table (canceled blocks may not have product image)
            details = self._extract_shipping_product_details(next_table)
            if not details:
                continue
            
            # Canceled blocks often lack product image - infer unique_id from Processing/Shipping blocks
            # Match by product name + size, or by size only when single product matches
            if block_type == 'canceled' and not details.get('unique_id') and details.get('size'):
                inferred = None
                if details.get('product_name'):
                    inferred = self._find_unique_id_by_product_match(
                        details['product_name'],
                        details['size'],
                        product_lookup,
                        shipping_items
                    )
                if not inferred:
                    inferred = self._find_unique_id_by_size_only(
                        details['size'],
                        product_lookup,
                        shipping_items
                    )
                if inferred:
                    details['unique_id'] = inferred
                    logger.info(
                        f"Inferred unique_id={inferred} for canceled item: "
                        f"{details.get('product_name') or '?'} size {details.get('size')} from Processing/Shipping blocks"
                    )
            
            if block_type == 'shipped':
                if not details.get('unique_id'):
                    continue
                shipping_items.append(FinishLineShippingOrderItem(
                    unique_id=details['unique_id'],
                    size=self._clean_size(details['size']),
                    quantity=details.get('quantity', 1),
                    tracking=tracking,
                    product_name=details.get('product_name')
                ))
            elif block_type == 'canceled':
                # Must have unique_id (from image or inferred) to process cancellation
                if not details.get('unique_id'):
                    logger.warning(f"Skipping canceled item without unique_id: {details.get('product_name')} size {details.get('size')}")
                    continue
                # Partial cancel: Quantity 0 in Canceled block = 1 cancelled unit (each block = 1 unit)
                qty = details.get('quantity', 0)
                if qty == 0:
                    qty = 1
                cancellation_items.append(FinishLineOrderItem(
                    unique_id=details['unique_id'],
                    size=self._clean_size(details['size']),
                    quantity=qty,
                    product_name=details.get('product_name')
                ))
        
        return (shipping_items, cancellation_items)

    def _extract_shipping_product_details(self, table) -> Optional[dict]:
        """Extract product details from a Finish Line shipping/cancel product table."""
        try:
            details = {}
            
            # SKU from image (shipping blocks have this; canceled blocks may not)
            img = table.find('img', src=re.compile(r'media\.(jdsports|finishline)\.com'))
            if img:
                src = img.get('src', '')
                sku_match = re.search(r'/(?:jdsports|finishline)/([A-Z0-9_-]+)(?:\?|$)', src)
                if sku_match:
                    details['unique_id'] = sku_match.group(1)
            
            # Product name from bold span/td or from tr with font-weight:bold (Canceled blocks use tr style)
            bold_elem = table.find(['span', 'td'], style=re.compile(r'font-weight:\s*bold', re.I))
            if bold_elem:
                name = bold_elem.get_text(strip=True)
                if name and not name.lower().startswith(('size:', 'quantity:', '$')):
                    details['product_name'] = name
            if not details.get('product_name'):
                # Fallback: <tr style="font-weight:bold"><td><span>PRODUCT NAME</span></td></tr>
                bold_tr = table.find('tr', style=re.compile(r'font-weight:\s*bold', re.I))
                if bold_tr:
                    name = bold_tr.get_text(strip=True)
                    if name and not name.lower().startswith(('size:', 'quantity:', '$')):
                        details['product_name'] = name
            
            # Size and quantity from td content
            tds = table.find_all('td')
            for td in tds:
                text = td.get_text(strip=True)
                if text.lower().startswith('size:'):
                    size = text.split(':', 1)[1].strip()
                    details['size'] = re.sub(r'\s*(REG|WIDE|NARROW|Y|M|W)$', '', size, flags=re.IGNORECASE).strip()
                elif text.lower().startswith('quantity:'):
                    try:
                        details['quantity'] = int(text.split(':', 1)[1].strip())
                    except (ValueError, IndexError):
                        details['quantity'] = 1
            
            # Must have at least size; unique_id required for shipped, preferred for canceled
            if not details.get('size'):
                return None
            
            if 'quantity' not in details:
                details['quantity'] = 1
            
            return details
        except Exception as e:
            logger.error(f"Error extracting shipping product details: {e}")
            return None

    def _aggregate_shipping_items(self, items: List[FinishLineShippingOrderItem]) -> List[FinishLineShippingOrderItem]:
        """Aggregate shipping items by (unique_id, size): sum quantities, keep first tracking."""
        if not items:
            return []
        
        grouped: dict = {}
        for item in items:
            key = (item.unique_id, item.size)
            if key not in grouped:
                grouped[key] = FinishLineShippingOrderItem(
                    unique_id=item.unique_id,
                    size=item.size,
                    quantity=item.quantity,
                    tracking=item.tracking,
                    product_name=item.product_name
                )
            else:
                grouped[key].quantity += item.quantity
                if not grouped[key].tracking and item.tracking:
                    grouped[key].tracking = item.tracking
        
        return list(grouped.values())

    def _extract_order_number(self, soup: BeautifulSoup, subject: str) -> Optional[str]:
        """
        Extract order number from Finish Line email.
        
        Format: Order Number: 60010107385
        Located in the email body with link
        
        Args:
            soup: BeautifulSoup object of email HTML
            subject: Email subject string
        
        Returns:
            Order number or None
        """
        try:
            # Look for the specific pattern in Finish Line emails
            # Pattern: "Order Number: <a>60010107385</a>"
            order_number_tag = soup.find('a', class_='link')
            if order_number_tag:
                order_number = order_number_tag.get_text(strip=True)
                if order_number and order_number.isdigit() and len(order_number) >= 8:
                    logger.debug(f"Found Finish Line order number from link: {order_number}")
                    return order_number
            
            # Fallback: Search in text
            email_text = soup.get_text()
            
            # Pattern 1: "Order Number: 60010107385"
            match = re.search(r'Order\s+Number\s*:?\s*(\d{8,})', email_text, re.IGNORECASE)
            if match:
                order_number = match.group(1).strip()
                logger.debug(f"Found Finish Line order number: {order_number}")
                return order_number
            
            # Pattern 2: "Order #: 123456789"
            match = re.search(r'Order\s*#\s*:?\s*([A-Z0-9-]+)', email_text, re.IGNORECASE)
            if match:
                order_number = match.group(1).strip()
                logger.debug(f"Found Finish Line order number (alt): {order_number}")
                return order_number
            
            logger.warning("Order number not found in Finish Line email")
            return None
        
        except Exception as e:
            logger.error(f"Error extracting Finish Line order number: {e}")
            return None

    def _extract_items(self, soup: BeautifulSoup) -> List[FinishLineOrderItem]:
        """
        Extract order items from Finish Line email.
        
        Finish Line email structure will vary, but typically includes:
        - Product name
        - SKU/Style code
        - Size
        - Quantity
        - Product images
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            List of FinishLineOrderItem objects
        """
        items = []
        processed_products = set()  # Track processed products to avoid duplicates
        
        try:
            # Strategy 1: Look for product tables or rows
            # Common in retail confirmation emails
            product_rows = self._find_product_rows(soup)
            
            logger.info(f"Found {len(product_rows)} potential product rows")
            
            for row in product_rows:
                try:
                    # Extract product details from this row
                    product_details = self._extract_finishline_product_details(row)
                    
                    if product_details:
                        unique_id = product_details.get('unique_id')
                        size = product_details.get('size')
                        quantity = product_details.get('quantity', 1)
                        product_name = product_details.get('product_name', 'Unknown Product')
                        
                        # Create a unique key to avoid duplicates
                        product_key = f"{unique_id}_{size}"
                        
                        if product_key in processed_products:
                            logger.debug(f"Skipping duplicate: {product_key}")
                            continue
                        
                        # Validate and create item
                        if unique_id and size:
                            items.append(FinishLineOrderItem(
                                unique_id=unique_id,
                                size=self._clean_size(size),
                                quantity=quantity,
                                product_name=product_name
                            ))
                            processed_products.add(product_key)
                            logger.info(
                                f"Extracted Finish Line item: {product_name} | "
                                f"unique_id={unique_id}, Size={size}, Qty={quantity}"
                            )
                        else:
                            logger.warning(
                                f"Invalid or missing data: "
                                f"unique_id={unique_id}, size={size}, product_name={product_name}"
                            )
                
                except Exception as e:
                    logger.error(f"Error processing Finish Line product row: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error extracting Finish Line items: {e}", exc_info=True)
        
        # Log items with ID, size, and quantity (product names come from OA Sourcing table)
        if items:
            items_summary = [f"(ID: {item.unique_id}, Size: {item.size}, Qty: {item.quantity})" for item in items]
            logger.info(f"[Finish Line] Extracted {len(items)} items: {', '.join(items_summary)}")
        return items

    def _find_product_rows(self, soup: BeautifulSoup) -> List:
        """
        Find product rows in the email HTML.
        
        Finish Line structure:
        - Product images with URL pattern: media.finishline.com/s/finishline/{SKU} or media.jdsports.com/s/jdsports/{SKU}
        - Product details in td with class "orderDetails" or in nested tables
        
        Returns:
            List of BeautifulSoup elements containing product information
        """
        product_rows = []
        
        # Look for product images from Finish Line CDN
        img_tags = soup.find_all('img')
        for img in img_tags:
            src = img.get('src', '')
            
            # Check if this is a Finish Line product image
            # Order confirmations: media.finishline.com/s/finishline/{SKU}?$default$
            # Cancellations: media.jdsports.com/s/jdsports/{SKU} or media.finishline.com/s/finishline/{SKU}
            is_finishline_image = (
                ('media.finishline.com/s/finishline/' in src) or
                ('media.jdsports.com/s/jdsports/' in src)
            )
            
            if is_finishline_image:
                # Exclude non-product images (logos, icons, etc.)
                if any(exclude in src.lower() for exclude in ['logo', 'icon', 'spacer', 'arrow', 'social', 'braze']):
                    continue
                
                logger.debug(f"Found Finish Line product image: {src[:100]}")
                # Find the parent table that contains both image and details
                # Look for the table that contains the image and product details
                parent_table = img.find_parent('table')
                if parent_table:
                    # Check if this table contains product details (size, quantity, product name)
                    table_text = parent_table.get_text()
                    has_product_info = (
                        'size:' in table_text.lower() or
                        'quantity:' in table_text.lower() or
                        bool(re.search(r'\b\d+(?:\.\d+)?\s*(?:REG|WIDE|NARROW|Y|M|W)?\b', table_text, re.IGNORECASE))
                    )
                    
                    if has_product_info:
                        # Make sure we get the right table - sometimes need to go up one more level
                        # Look for a table that has width="536px" or similar (product detail tables)
                        current_table = parent_table
                        while current_table:
                            table_style = current_table.get('style', '')
                            table_width = current_table.get('width', '')
                            # Product tables often have width="536px" or similar
                            if ('width:536px' in table_style or 'width="536px"' in str(current_table) or
                                'width:598px' in table_style or 'width="598px"' in str(current_table) or
                                has_product_info):
                                if current_table not in product_rows:
                                    product_rows.append(current_table)
                                    break
                            current_table = current_table.find_parent('table')
                            if not current_table:
                                # Fallback to original parent_table
                                if parent_table not in product_rows:
                                    product_rows.append(parent_table)
                                break
                    elif parent_table not in product_rows:
                        # Even without explicit product info, add it if it's a reasonable table
                        product_rows.append(parent_table)
        
        return product_rows

    def _extract_finishline_product_details(self, element) -> Optional[dict]:
        """
        Extract product details from a Finish Line product element using BeautifulSoup.
        
        HTML Structure (actual format):
        - Product image URL contains SKU: media.finishline.com/s/finishline/IB4437_663
        - Product name in <td> with bold style (font-weight:bold)
        - Size in <td> containing "Size: 6.0"
        - Quantity in <td> containing "Quantity: 2"
        
        The product details are in a nested table structure within the parent table.
        
        Extraction Method:
        - Uses BeautifulSoup to find specific <td> elements
        - Parses text by splitting on colon (":")
        - Searches within the parent table for size and quantity
        
        Returns:
            Dictionary with unique_id, size, quantity, product_name or None
        """
        try:
            details = {}
            
            # Extract SKU from product image URL
            # Try jdsports first (common in cancellation emails)
            img_tag = element.find('img', src=re.compile(r'media\.jdsports\.com/s/jdsports/'))
            if not img_tag:
                # Fallback to finishline
                img_tag = element.find('img', src=re.compile(r'media\.finishline\.com/s/finishline/'))
            
            if img_tag:
                src = img_tag.get('src', '')
                # Extract SKU from URL patterns:
                # - media.jdsports.com/s/jdsports/943345_041
                # - media.finishline.com/s/finishline/IB4437_663?$default$
                sku_match = re.search(r'/(?:jdsports|finishline)/([A-Z0-9_-]+)(?:\?|$)', src)
                if sku_match:
                    sku = sku_match.group(1)
                    details['unique_id'] = sku
                    logger.debug(f"Found SKU from image URL: {sku}")
            
            # Extract product name - look for <td> with bold style (font-weight:bold)
            # Try multiple approaches
            product_name = None
            
            # Method 1: Look for td with bold style
            bold_tds = element.find_all('td', style=re.compile(r'font-weight:\s*bold', re.IGNORECASE))
            for td in bold_tds:
                text = td.get_text(strip=True)
                # Skip if it's "Size:" or "Quantity:" or price
                if text and not text.lower().startswith(('size:', 'quantity:', '$')):
                    product_name = text
                    break
            
            # Method 2: Look for td with class containing "bold" (fallback)
            if not product_name:
                product_name_tag = element.find('td', class_=re.compile(r'.*bold.*', re.IGNORECASE))
                if product_name_tag:
                    product_name = product_name_tag.get_text(strip=True)
            
            if product_name:
                details['product_name'] = product_name
                logger.debug(f"Found product name: {product_name}")
            
            # Find all <td> tags within the element to extract size and quantity
            # The actual HTML doesn't use class="orderDetails", so search all tds
            all_tds = element.find_all('td')
            
            for td in all_tds:
                td_text = td.get_text(strip=True)
                
                # Extract size - Format: "Size: 6.0 REG" or "Size: 11.5 REG"
                if td_text.lower().startswith('size:'):
                    size = td_text.split(':', 1)[1].strip()
                    # Remove "REG", "WIDE", "NARROW", "Y", "M", "W" suffixes
                    size = re.sub(r'\s*(REG|WIDE|NARROW|Y|M|W)$', '', size, flags=re.IGNORECASE).strip()
                    if size:
                        details['size'] = size
                        logger.debug(f"Found size: {size}")
                
                # Extract quantity - Format: "Quantity: 2" or "Quantity: 0"
                elif td_text.lower().startswith('quantity:'):
                    quantity_str = td_text.split(':', 1)[1].strip()
                    try:
                        quantity = int(quantity_str)
                        details['quantity'] = quantity
                        logger.debug(f"Found quantity: {quantity}")
                    except ValueError:
                        logger.warning(f"Could not parse quantity: {quantity_str}")
            
            # Default quantity to 1 if not found
            if 'quantity' not in details:
                details['quantity'] = 1
                logger.debug("Quantity not found, defaulting to 1")
            
            # Return only if we have the essential fields
            if details.get('unique_id') and details.get('size'):
                logger.info(f"Successfully extracted Finish Line product: {details}")
                return details
            
            logger.warning(f"Missing essential fields: unique_id={details.get('unique_id')}, size={details.get('size')}")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting Finish Line product details: {e}", exc_info=True)
            return None

    def _is_valid_size(self, size: str) -> bool:
        """Validate if size is valid"""
        if not size:
            return False
        # Accept numeric sizes (10, 10.5), youth sizes (4.5Y), letter sizes (M, XL), or special sizes (OS)
        return bool(
            re.match(r'^\d+(\.\d+)?Y?$', size) or  # Numeric: 10, 10.5, 4.5Y
            re.match(r'^[A-Z]{1,3}$', size.upper()) or  # Letter: M, XL, XXL
            size.upper() == 'OS'  # One Size
        )

    def _clean_size(self, size: str) -> str:
        """Clean size string"""
        size = size.strip()
        # Remove .0 from numeric sizes
        if size.endswith('.0'):
            return size[:-2]
        return size
    
    def _extract_shipping_address(self, soup: BeautifulSoup) -> str:
        """
        Extract shipping address from email and normalize it.
        
        Finish Line email structure:
        - "Shipping to:" header
        - Name, street address, unit, city/state/zip (e.g., "Griffin Myers,<br> 595 LLOYD LN<br> STE D<br> Independence, OR 97351")
        
        We want to extract just the street address part and normalize it.
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            Normalized shipping address or empty string
        """
        try:
            text = soup.get_text()
            
            # Method 1: Look for "Shipping to:" section and extract street address
            shipping_match = re.search(
                r'Shipping\s+to:?\s*(.*?)(?:Billing|Payment|Order|Gift|$)',
                text,
                re.IGNORECASE | re.DOTALL
            )
            
            if shipping_match:
                address_section = shipping_match.group(1).strip()
                # Split into lines
                lines = [line.strip() for line in address_section.split('\n') if line.strip()]
                
                # Look for street address pattern (number + street name)
                # Pattern: starts with number, contains street name (Lloyd, Vista, etc.)
                for line in lines:
                    # Skip name lines (usually don't start with numbers or are all caps names)
                    # Skip phone lines (contain phone pattern)
                    # Look for lines that start with number and contain street indicators
                    if re.match(r'^\d+', line):  # Starts with number
                        if not re.search(r'\d{3}-\d{3}-\d{4}', line):  # Not a phone number
                            # Check if it contains street indicators (LN, Lane, Ave, Street, etc.)
                            if re.search(r'\b(LN|Lane|AVE|Ave|Avenue|Street|St|Road|Rd|Drive|Dr|Boulevard|Blvd)\b', line, re.IGNORECASE):
                                # Extract just the street address part (before city/state/zip)
                                # Finish Line format: "595 LLOYD LN<br> STE D<br> Independence, OR 97351"
                                # We want: "595 LLOYD LN" -> normalized to "595 Lloyd Lane"
                                
                                # Split by comma and take the first part (street address)
                                # City/state/zip usually comes after a comma
                                parts = line.split(',')
                                street_line = parts[0].strip() if parts else line.strip()
                                
                                # Also check if there's a pattern like ", CITY, STATE" - take everything before that
                                # Pattern: number + street + optional unit, then ", CITY, STATE ZIP"
                                city_state_match = re.search(r',\s*[A-Z][A-Z\s]+,?\s*[A-Z]{2}\s*\d{5}', line)
                                if city_state_match:
                                    # Extract everything before the city/state/zip pattern
                                    street_line = line[:city_state_match.start()].strip()
                                
                                normalized = normalize_shipping_address(street_line)
                                if normalized:
                                    logger.debug(f"Extracted Finish Line shipping address: {line} -> {street_line} -> {normalized}")
                                    return normalized
            
            # Method 2: Direct pattern matching for known addresses
            # Look for "595 Lloyd" pattern
            lloyd_match = re.search(r'(595\s+LLOYD\s+LN[^,\n]*(?:,\s*[A-Z\s]+)?)', text, re.IGNORECASE)
            if lloyd_match:
                street_line = lloyd_match.group(1).strip()
                # Remove city/state/zip if present
                street_line = re.sub(r',\s*[A-Z][A-Z\s]+,?\s*[A-Z]{2}\s*\d{5}.*$', '', street_line).strip()
                normalized = normalize_shipping_address(street_line)
                if normalized:
                    logger.debug(f"Extracted Finish Line shipping address (pattern): {street_line} -> {normalized}")
                    return normalized
            
            # Method 3: Look for "2025 Vista" pattern
            vista_match = re.search(r'(2025\s+Vista\s+Ave[^,\n]*(?:,\s*[A-Z\s]+)?)', text, re.IGNORECASE)
            if vista_match:
                street_line = vista_match.group(1).strip()
                # Remove city/state/zip if present
                street_line = re.sub(r',\s*[A-Z][A-Z\s]+,?\s*[A-Z]{2}\s*\d{5}.*$', '', street_line).strip()
                normalized = normalize_shipping_address(street_line)
                if normalized:
                    logger.debug(f"Extracted Finish Line shipping address (pattern): {street_line} -> {normalized}")
                    return normalized
            
            return ""
        
        except Exception as e:
            logger.error(f"Error extracting shipping address: {e}")
            return ""
    
    def _detect_full_cancellation(self, soup: BeautifulSoup) -> bool:
        """
        Detect if this is a full cancellation or partial cancellation.
        
        Full cancellation indicators:
        - "Order Canceled" image at the top
        - All items show "Quantity: 0"
        - No "Shipping" sections
        
        Partial cancellation indicators:
        - Has "Shipping" sections with items
        - Has "Canceled" sections (red border #d81e05) with items
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            True if full cancellation, False if partial
        """
        try:
            html_text = soup.get_text().lower()
            html_str = str(soup)
            
            # Check for "Order Canceled" image at the top
            canceled_img = soup.find('img', alt=re.compile(r'Order\s+Canceled', re.IGNORECASE))
            if canceled_img:
                logger.debug("Found 'Order Canceled' image - likely full cancellation")
                return True
            
            # Check for "Order Canceled" text in alt attribute
            if 'alt="Order Canceled"' in html_str or "order canceled" in html_text[:500]:
                logger.debug("Found 'Order Canceled' text near top - likely full cancellation")
                return True
            
            # Check if there are any "Shipping" sections
            # Shipping sections have border color #6f6f6f (gray)
            shipping_sections = soup.find_all('table', style=re.compile(r'border.*#6f6f6f', re.IGNORECASE))
            if shipping_sections:
                logger.debug(f"Found {len(shipping_sections)} shipping sections - likely partial cancellation")
                return False
            
            # Check for "Shipping" text with tracking numbers
            if re.search(r'shipping.*tracking', html_text, re.IGNORECASE):
                logger.debug("Found shipping section with tracking - likely partial cancellation")
                return False
            
            # Default to full cancellation if no shipping sections found
            logger.debug("No shipping sections found - assuming full cancellation")
            return True
            
        except Exception as e:
            logger.error(f"Error detecting cancellation type: {e}", exc_info=True)
            # Default to full cancellation on error
            return True
    
    def _extract_cancellation_items(self, soup: BeautifulSoup, is_full_cancellation: bool) -> List[FinishLineOrderItem]:
        """
        Extract cancelled items from Finish Line cancellation email.
        
        For full cancellation:
        - All items in the email show "Quantity: 0"
        - Extract all items
        
        For partial cancellation:
        - Extract items from "Canceled" section (red border #d81e05)
        - Items show "Quantity: 0" but represent 1 unit each
        
        Args:
            soup: BeautifulSoup object of email HTML
            is_full_cancellation: Whether this is a full cancellation
        
        Returns:
            List of FinishLineOrderItem objects
        """
        items = []
        # For partial: aggregate by (unique_id, size) - sum quantities (supports multiple cancelled blocks)
        aggregated: dict = {}  # (unique_id, size) -> (quantity, product_name)
        
        try:
            if is_full_cancellation:
                # For full cancellation, extract all items (they all show Quantity: 0)
                logger.debug("Extracting items from full cancellation email")
                product_rows = self._find_product_rows(soup)
            else:
                # For partial cancellation, extract only from "Canceled" section (skip Processing blocks)
                # Each Canceled block with Qty: 0 represents 1 cancelled unit
                logger.debug("Extracting items from partial cancellation (Canceled section)")
                product_rows = self._find_canceled_section_items(soup)
            
            logger.info(f"Found {len(product_rows)} potential cancelled product rows")
            
            for row in product_rows:
                try:
                    # Extract product details from this row
                    product_details = self._extract_finishline_cancellation_product_details(row)
                    
                    if product_details:
                        unique_id = product_details.get('unique_id')
                        size = product_details.get('size')
                        quantity = product_details.get('quantity', 1)  # Qty 0 -> 1 (see _extract_finishline_cancellation_product_details)
                        product_name = product_details.get('product_name', 'Unknown Product')
                        
                        if not unique_id or not size:
                            logger.warning(
                                f"Invalid or missing data: "
                                f"unique_id={unique_id}, size={size}, product_name={product_name}"
                            )
                            continue
                        
                        cleaned_size = self._clean_size(size)
                        key = (unique_id, cleaned_size)
                        
                        if is_full_cancellation:
                            # Full: one item per row (no aggregation needed for extraction)
                            items.append(FinishLineOrderItem(
                                unique_id=unique_id,
                                size=cleaned_size,
                                quantity=quantity,
                                product_name=product_name
                            ))
                        else:
                            # Partial: SUM quantities for same (unique_id, size) across cancelled blocks
                            if key in aggregated:
                                prev_qty, _ = aggregated[key]
                                aggregated[key] = (prev_qty + quantity, product_name)
                            else:
                                aggregated[key] = (quantity, product_name)
                
                except Exception as e:
                    logger.error(f"Error processing Finish Line cancelled product row: {e}")
                    continue
            
            if not is_full_cancellation and aggregated:
                items = [
                    FinishLineOrderItem(
                        unique_id=uid,
                        size=sz,
                        quantity=qty,
                        product_name=pn
                    )
                    for (uid, sz), (qty, pn) in aggregated.items()
                ]
                for item in items:
                    logger.info(
                        f"Extracted Finish Line cancelled item: {item.product_name} | "
                        f"unique_id={item.unique_id}, Size={item.size}, Qty={item.quantity} (summed)"
                    )
            
            logger.info(f"Extracted {len(items)} cancelled items from Finish Line cancellation email")
            return items
            
        except Exception as e:
            logger.error(f"Error extracting Finish Line cancellation items: {e}", exc_info=True)
            return []
    
    def _find_canceled_section_items(self, soup: BeautifulSoup) -> List:
        """
        Find product rows in the "Canceled" section of a partial cancellation email.
        
        Canceled section indicators:
        - Red border: border:1px solid #d81e05 or bgcolor="#d81e05"
        - Contains "Canceled" text
        - Items show "Quantity: 0"
        
        Returns:
            List of BeautifulSoup elements containing cancelled product information
        """
        product_rows = []
        
        try:
            # Find all tables with red border (#d81e05) - these are Canceled sections
            canceled_tables = soup.find_all('table', style=re.compile(r'border.*#d81e05|#d81e05.*border', re.IGNORECASE))
            
            # Also check for bgcolor="#d81e05" (header row)
            canceled_headers = soup.find_all('tr', bgcolor=re.compile(r'#d81e05', re.IGNORECASE))
            
            # Find tables that contain "Canceled" text
            all_tables = soup.find_all('table')
            for table in all_tables:
                table_text = table.get_text().lower()
                table_style = table.get('style', '')
                
                # Check if this table is in a Canceled section
                if 'canceled' in table_text and ('#d81e05' in table_style or '#d81e05' in str(table)):
                    # Find product images in this table
                    img_tags = table.find_all('img', src=re.compile(r'media\.jdsports\.com|media\.finishline\.com'))
                    for img in img_tags:
                        src = img.get('src', '')
                        # Exclude non-product images
                        if any(exclude in src.lower() for exclude in ['logo', 'icon', 'spacer', 'arrow', 'social']):
                            continue
                        parent_table = img.find_parent('table')
                        if parent_table and parent_table not in product_rows:
                            product_rows.append(parent_table)
            
            # Also check tables that come after Canceled headers
            for header in canceled_headers:
                # Find the next table after this header that contains product info
                next_table = header.find_next('table')
                if next_table:
                    # Check if it contains product images
                    img_tags = next_table.find_all('img', src=re.compile(r'media\.jdsports\.com|media\.finishline\.com'))
                    for img in img_tags:
                        src = img.get('src', '')
                        # Exclude non-product images
                        if any(exclude in src.lower() for exclude in ['logo', 'icon', 'spacer', 'arrow', 'social']):
                            continue
                        if next_table not in product_rows:
                            product_rows.append(next_table)
                            break
            
            return product_rows
            
        except Exception as e:
            logger.error(f"Error finding canceled section items: {e}", exc_info=True)
            return []
    
    def _extract_finishline_cancellation_product_details(self, element) -> Optional[dict]:
        """
        Extract product details from a Finish Line cancellation product element.
        
        For cancellation emails:
        - Product image URL: media.jdsports.com/s/jdsports/{SKU} or media.finishline.com/s/finishline/{SKU}
        - Product name in <td> with bold style
        - Size in <td> containing "Size: 11.5 REG"
        - Quantity in <td> containing "Quantity: 0" (but we'll use 1 per item)
        
        Returns:
            Dictionary with unique_id, size, quantity, product_name or None
        """
        try:
            details = {}
            
            # Extract SKU from product image URL
            # Try jdsports first (common in cancellation emails)
            img_tag = element.find('img', src=re.compile(r'media\.jdsports\.com/s/jdsports/'))
            if not img_tag:
                # Fallback to finishline
                img_tag = element.find('img', src=re.compile(r'media\.finishline\.com/s/finishline/'))
            
            if img_tag:
                src = img_tag.get('src', '')
                # Extract SKU from URL: media.jdsports.com/s/jdsports/HQ2037_100
                # or media.finishline.com/s/finishline/IB4437_663
                sku_match = re.search(r'/(?:jdsports|finishline)/([A-Z0-9_-]+)(?:\?|$)', src)
                if sku_match:
                    sku = sku_match.group(1)
                    details['unique_id'] = sku
                    logger.debug(f"Found SKU from image URL: {sku}")
            
            # Extract product name - look for <td> with bold style or <span> with bold
            product_name = None
            
            # Method 1: Look for td with bold style
            bold_tds = element.find_all(['td', 'span'], style=re.compile(r'font-weight:\s*bold', re.IGNORECASE))
            for td in bold_tds:
                text = td.get_text(strip=True)
                # Skip if it's "Size:", "Quantity:", price, or "Canceled"
                if text and not text.lower().startswith(('size:', 'quantity:', '$', 'canceled')):
                    if len(text) > 2:  # Make sure it's not just a single character
                        product_name = text
                        break
            
            # Method 2: Look for span with bold style
            if not product_name:
                bold_spans = element.find_all('span', style=re.compile(r'font-weight:\s*bold', re.IGNORECASE))
                for span in bold_spans:
                    text = span.get_text(strip=True)
                    if text and not text.lower().startswith(('size:', 'quantity:', '$', 'canceled')):
                        if len(text) > 2:
                            product_name = text
                            break
            
            if product_name:
                details['product_name'] = product_name
                logger.debug(f"Found product name: {product_name}")
            
            # Find all <td> tags within the element to extract size and quantity
            all_tds = element.find_all('td')
            
            for td in all_tds:
                td_text = td.get_text(strip=True)
                
                # Extract size - Format: "Size: 11.5 REG" or "Size: 6.0 REG"
                if td_text.lower().startswith('size:'):
                    size = td_text.split(':', 1)[1].strip()
                    # Remove "REG" or other size type suffixes
                    size = re.sub(r'\s*(REG|WIDE|NARROW|Y|M|W)$', '', size, flags=re.IGNORECASE).strip()
                    if size:
                        details['size'] = size
                        logger.debug(f"Found size: {size}")
                
                # Extract quantity - Format: "Quantity: 0" (but we'll use 1 per item)
                elif td_text.lower().startswith('quantity:'):
                    quantity_str = td_text.split(':', 1)[1].strip()
                    try:
                        quantity = int(quantity_str)
                        # If quantity is 0, default to 1 (each cancelled item represents 1 unit)
                        if quantity == 0:
                            quantity = 1
                        details['quantity'] = quantity
                        logger.debug(f"Found quantity: {quantity}")
                    except ValueError:
                        logger.warning(f"Could not parse quantity: {quantity_str}")
                        details['quantity'] = 1  # Default to 1
            
            # Default quantity to 1 if not found
            if 'quantity' not in details:
                details['quantity'] = 1
                logger.debug("Quantity not found, defaulting to 1")
            
            # Return only if we have the essential fields
            if details.get('unique_id') and details.get('size'):
                logger.info(f"Successfully extracted Finish Line cancelled product: {details}")
                return details
            
            logger.warning(f"Missing essential fields: unique_id={details.get('unique_id')}, size={details.get('size')}")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting Finish Line cancellation product details: {e}", exc_info=True)
            return None

