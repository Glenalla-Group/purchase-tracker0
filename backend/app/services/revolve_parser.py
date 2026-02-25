"""
Revolve Email Parser
Parses order confirmation emails from Revolve using BeautifulSoup

Email Format:
- From: revolve@mt.revolve.com
- Subject: "Your order #341221096 has been processed"
- Order Number: Extract from subject line (e.g., "341221096")

HTML Structure:
- Products are listed individually in table rows
- Each product has:
  - Image URL: https://is4.revolveassets.com/images/p4/ip2/pl2/ONF-MZ454_V1.jpg
    Unique ID: ONF-MZ454 (extract from filename before _V1.jpg)
  - Product link: ...code=ONF-MZ454... (unique ID in code parameter)
  - Product name: <div style="font-weight:bold">Cloudswift 4 in Black & Eclipse</div>
  - Size: <div>Size: 11</div>
  - Quantity: In <td> with align="center" (numeric value)

Important: Revolve lists products individually. If you order 3 units of the same product
in the same size, they appear as 3 separate items. We need to:
- Group items by unique_id + size
- Sum quantities for identical items
- Return consolidated items

Example:
  Input: 2 items of ONF-MZ454, Size 11, Qty 1 each
  Output: 1 item of ONF-MZ454, Size 11, Qty 2
"""

import re
import logging
from typing import List, Optional, Dict
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from app.models.email import EmailData
from app.utils.address_utils import normalize_shipping_address
from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class RevolveOrderItem(BaseModel):
    unique_id: str = Field(..., description="Unique identifier for the product (e.g., ONF-MZ454)")
    size: str = Field(..., description="Size of the product")
    quantity: int = Field(..., description="Quantity of the product (summed for identical items)")
    product_name: Optional[str] = Field(None, description="Name of the product")
    
    def __repr__(self):
        if self.product_name and len(self.product_name) > 50:
            product_display = self.product_name[:50] + "..."
        else:
            product_display = self.product_name or "Unknown"
        return f"<RevolveOrderItem(unique_id={self.unique_id}, size={self.size}, qty={self.quantity}, product={product_display})>"


class RevolveOrderData(BaseModel):
    order_number: str = Field(..., description="The order number")
    items: List[RevolveOrderItem] = Field(..., description="List of items in the order (consolidated)")
    items_count: int = Field(0, description="Total number of items in the order")
    shipping_address: str = Field("", description="Normalized shipping address")

    def __init__(self, **data):
        super().__init__(**data)
        self.items_count = len(self.items)


class RevolveShippingData(BaseModel):
    """Represents Revolve shipping notification data (full or partial ship)."""
    order_number: str = Field(..., description="The order number")
    items: List[RevolveOrderItem] = Field(..., description="List of shipped items (consolidated by unique_id + size)")
    tracking_number: str = Field("", description="Tracking number(s), comma-separated for partial with multiple packages")

    def __repr__(self):
        tk = (self.tracking_number[:20] + "...") if len(self.tracking_number) > 20 else self.tracking_number
        return f"<RevolveShippingData(order={self.order_number}, items={len(self.items)}, tracking={tk})>"


class RevolveCancellationData(BaseModel):
    """Represents Revolve cancellation notification data."""
    order_number: str = Field(..., description="The order number")
    items: List[RevolveOrderItem] = Field(..., description="List of cancelled items (consolidated by unique_id + size)")

    def __repr__(self):
        return f"<RevolveCancellationData(order={self.order_number}, items={len(self.items)})>"


class RevolveEmailParser:
    # Email identification - Order Confirmation (Production)
    REVOLVE_FROM_EMAIL = "revolve@mt.revolve.com"
    SUBJECT_ORDER_PATTERN = r"your order\s+#(\d+)\s+has been processed"
    
    # Shipping - Full: "Your order #341221096 has been shipped"
    # Partial: "Part of Order #340541171 has shipped from REVOLVE" or "Part of Order #340541171 has been shipped."
    SUBJECT_SHIPPING_FULL_PATTERN = r"your order\s+#\d+\s+has been shipped"
    SUBJECT_SHIPPING_PARTIAL_PATTERN = r"part of order\s+#\d+\s+has (?:been )?shipped"
    
    # Cancellation - Type 1: "An item from your order was cancelled" (from revolve@mt.revolve.com)
    # Type 2: "An item in your order is out of stock" (from sales@t.revolve.com)
    REVOLVE_CANCEL_FROM_EMAIL = "revolve@mt.revolve.com"
    REVOLVE_CANCEL_OUTOFSTOCK_FROM = "sales@t.revolve.com"
    SUBJECT_CANCEL_PATTERN = r"an item from your order was cancelled"
    SUBJECT_CANCEL_OUTOFSTOCK_PATTERN = r"an item in your order is out of stock"
    
    # Email identification - Development (forwarded emails)
    DEV_REVOLVE_ORDER_FROM_EMAIL = "glenallagroupc@gmail.com"
    DEV_SUBJECT_ORDER_PATTERN = r"Fwd:\s*Your order\s+#(\d+)\s+has been processed"
    DEV_SUBJECT_SHIPPING_FULL_PATTERN = r"(?:Fwd:\s*)?Your order\s+#\d+\s+has been shipped"
    DEV_SUBJECT_SHIPPING_PARTIAL_PATTERN = r"(?:Fwd:\s*)?Part of Order\s+#\d+\s+has (?:been )?shipped"

    def __init__(self):
        """Initialize the Revolve email parser."""
        self.settings = get_settings()
    
    @property
    def order_from_email(self) -> str:
        """Get the appropriate from email address based on environment."""
        if self.settings.is_development:
            return self.DEV_REVOLVE_ORDER_FROM_EMAIL
        return self.REVOLVE_FROM_EMAIL
    
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
            return "Fwd: Your order"
        return "Your order"

    @property
    def update_from_email(self) -> str:
        """From address for shipping updates (same as order)."""
        if self.settings.is_development:
            return self.DEV_REVOLVE_ORDER_FROM_EMAIL
        return self.REVOLVE_FROM_EMAIL

    @property
    def shipping_subject_query(self) -> str:
        """Gmail subject query for shipping emails (matches both full and partial)."""
        return 'subject:("has been shipped" OR "has shipped")'

    @property
    def cancellation_subject_query(self) -> str:
        """Gmail subject query for cancellation emails (both types)."""
        return 'subject:("was cancelled" OR "is out of stock")'

    @property
    def cancellation_from_query(self) -> str:
        """Gmail from query for cancellation (type 1 + type 2 from different senders)."""
        if self.settings.is_development:
            return f'from:{self.DEV_REVOLVE_ORDER_FROM_EMAIL}'
        return f'(from:{self.REVOLVE_CANCEL_FROM_EMAIL} OR from:{self.REVOLVE_CANCEL_OUTOFSTOCK_FROM})'

    def is_revolve_email(self, email_data: EmailData) -> bool:
        """Check if email is from Revolve (order, shipping, or cancellation)."""
        sender_lower = email_data.sender.lower()
        
        # In development, check for forwarded emails from dev email address
        if self.settings.is_development:
            if self.DEV_REVOLVE_ORDER_FROM_EMAIL.lower() in sender_lower:
                return True
        
        # Production: revolve@mt.revolve.com (order, shipping, cancel type 1)
        if self.REVOLVE_FROM_EMAIL.lower() in sender_lower:
            return True
        # Production: sales@t.revolve.com (cancel type 2 - out of stock)
        if self.REVOLVE_CANCEL_OUTOFSTOCK_FROM.lower() in sender_lower:
            return True
        return False

    def is_order_confirmation_email(self, email_data: EmailData) -> bool:
        """Check if email is an order confirmation"""
        subject_lower = email_data.subject.lower()
        pattern = self.order_subject_pattern
        
        # Use regex matching for subject pattern
        return bool(re.search(pattern, subject_lower, re.IGNORECASE))

    def is_shipping_email(self, email_data: EmailData) -> bool:
        """Check if email is a shipping notification (full or partial)."""
        if not self.is_revolve_email(email_data):
            return False
        subject_lower = email_data.subject.lower()
        # Full: "Your order #XXX has been shipped"
        if re.search(self.SUBJECT_SHIPPING_FULL_PATTERN, subject_lower, re.IGNORECASE):
            return True
        # Partial: "Part of Order #XXX has shipped" or "has been shipped"
        if re.search(self.SUBJECT_SHIPPING_PARTIAL_PATTERN, subject_lower, re.IGNORECASE):
            return True
        if self.settings.is_development:
            if re.search(self.DEV_SUBJECT_SHIPPING_FULL_PATTERN, subject_lower, re.IGNORECASE):
                return True
            if re.search(self.DEV_SUBJECT_SHIPPING_PARTIAL_PATTERN, subject_lower, re.IGNORECASE):
                return True
        return False

    def is_cancellation_email(self, email_data: EmailData) -> bool:
        """Check if email is a cancellation notification (type 1 or 2)."""
        if not self.is_revolve_email(email_data):
            return False
        subject_lower = email_data.subject.lower()
        if re.search(self.SUBJECT_CANCEL_PATTERN, subject_lower, re.IGNORECASE):
            return True
        if re.search(self.SUBJECT_CANCEL_OUTOFSTOCK_PATTERN, subject_lower, re.IGNORECASE):
            return True
        return False

    def parse_email(self, email_data: EmailData) -> Optional[RevolveOrderData]:
        """
        Parse Revolve order confirmation email.
        
        Args:
            email_data: EmailData object containing email information
        
        Returns:
            RevolveOrderData object or None if parsing fails
        """
        try:
            html_content = email_data.html_content
            
            if not html_content:
                logger.error("No HTML content in Revolve email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extract order number from subject
            order_number = self._extract_order_number(email_data.subject)
            if not order_number:
                logger.error("Failed to extract order number from Revolve email")
                return None
            
            logger.info(f"Extracted Revolve order number: {order_number}")
            
            # Extract items using BeautifulSoup
            items = self._extract_items(soup)
            
            if not items:
                logger.error("Failed to extract any items from Revolve email")
                return None
            
            logger.info(f"Successfully extracted {len(items)} consolidated items from Revolve order {order_number}")
            for item in items:
                logger.debug(f"  - {item}")
            
            # Extract shipping address
            shipping_address = self._extract_shipping_address(soup)
            if shipping_address:
                logger.info(f"Extracted shipping address: {shipping_address}")
            
            return RevolveOrderData(order_number=order_number, items=items, shipping_address=shipping_address)
        
        except Exception as e:
            logger.error(f"Error parsing Revolve email: {e}", exc_info=True)
            return None

    def parse_shipping_email(self, email_data: EmailData) -> Optional[RevolveShippingData]:
        """
        Parse Revolve shipping email (full or partial).
        
        Full: "Your order #341221096 has been shipped"
        Partial: "Part of Order #340541171 has shipped from REVOLVE" or "Part of Order #340541171 has been shipped."
        
        Items use same extraction as order confirmation, with consolidation by unique_id + size.
        
        Args:
            email_data: EmailData object
        
        Returns:
            RevolveShippingData or None
        """
        try:
            html_content = email_data.html_content
            if not html_content:
                logger.error("No HTML content in Revolve shipping email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Order number from subject
            order_number = self._extract_order_number(email_data.subject)
            if not order_number:
                logger.error("Failed to extract order number from Revolve shipping email")
                return None
            
            # Tracking - full has single, partial may have multiple
            tracking_number = self._extract_shipping_tracking(soup)
            
            # Items - same structure as order confirmation, reuse _extract_items with consolidation
            items = self._extract_items(soup)
            if not items:
                logger.error("Failed to extract any items from Revolve shipping email")
                return None
            
            logger.info(
                f"Extracted Revolve shipping - Order: {order_number}, "
                f"Tracking: {tracking_number or 'N/A'}, Items: {len(items)}"
            )
            for item in items:
                logger.debug(f"  - {item}")
            
            return RevolveShippingData(
                order_number=order_number,
                items=items,
                tracking_number=tracking_number or ""
            )
        
        except Exception as e:
            logger.error(f"Error parsing Revolve shipping email: {e}", exc_info=True)
            return None

    def parse_cancellation_email(self, email_data: EmailData) -> Optional[RevolveCancellationData]:
        """
        Parse Revolve cancellation email (type 1 or 2).
        
        Type 1: "An item from your order was cancelled" (from revolve@mt.revolve.com)
        - Order number in body: "order #341221096"
        Type 2: "An item in your order is out of stock" (from sales@t.revolve.com)
        - Order number NOT in email - returns None (user to verify source later)
        
        Items use same extraction and consolidation by unique_id + size as shipping.
        
        Args:
            email_data: EmailData object
        
        Returns:
            RevolveCancellationData or None
        """
        try:
            html_content = email_data.html_content
            if not html_content:
                logger.error("No HTML content in Revolve cancellation email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Order number from body (type 1 has "order #341221096"; type 2 does not)
            order_number = self._extract_order_number_from_html(soup)
            if not order_number:
                logger.warning(
                    "Order number not found in Revolve cancellation email - "
                    "cannot process (out-of-stock type may lack order #)"
                )
                return None
            
            items = self._extract_items(soup)
            if not items:
                logger.error("Failed to extract any items from Revolve cancellation email")
                return None
            
            logger.info(f"Extracted Revolve cancellation - Order: {order_number}, Items: {len(items)}")
            for item in items:
                logger.debug(f"  - {item}")
            
            return RevolveCancellationData(order_number=order_number, items=items)
        
        except Exception as e:
            logger.error(f"Error parsing Revolve cancellation email: {e}", exc_info=True)
            return None

    def _extract_order_number_from_html(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract order number from email body (e.g. 'order #341221096')."""
        try:
            text = soup.get_text()
            match = re.search(r'order\s*#\s*(\d+)', text, re.IGNORECASE)
            if match:
                return match.group(1)
            # Also try mailtrk path format: 341221096-20251230102331
            match = re.search(r'/(\d{9,})-\d{14}/', text)
            if match:
                return match.group(1)
            return None
        except Exception as e:
            logger.error(f"Error extracting order number from HTML: {e}")
            return None

    def _extract_shipping_tracking(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract tracking number(s) from Revolve shipping email. Comma-joins multiple."""
        try:
            html_text = soup.get_text()
            # UPS: 1Z followed by 16 alphanumeric
            matches = re.findall(r'1Z[A-Z0-9]{16}', html_text, re.IGNORECASE)
            if matches:
                # Deduplicate while preserving order
                seen = set()
                unique = []
                for m in matches:
                    m_upper = m.upper()
                    if m_upper not in seen:
                        seen.add(m_upper)
                        unique.append(m_upper)
                return ", ".join(unique)
            return None
        except Exception as e:
            logger.error(f"Error extracting Revolve tracking: {e}")
            return None

    def _extract_order_number(self, subject: str) -> Optional[str]:
        """
        Extract order number from Revolve email subject.
        
        Subject format: Your order #341221096 has been processed
        Extract: 341221096
        
        Args:
            subject: Email subject string
        
        Returns:
            Order number or None
        """
        try:
            # Pattern: Your order #341221096 has been processed
            match = re.search(r'order\s+#(\d+)', subject, re.IGNORECASE)
            if match:
                order_number = match.group(1)
                logger.debug(f"Found Revolve order number in subject: {order_number}")
                return order_number
            
            logger.warning("Order number not found in Revolve email subject")
            return None
        
        except Exception as e:
            logger.error(f"Error extracting Revolve order number: {e}")
            return None

    def _extract_items(self, soup: BeautifulSoup) -> List[RevolveOrderItem]:
        """
        Extract order items from Revolve email and consolidate duplicates.
        
        Revolve email structure:
        - Products are in table rows (<tr>)
        - Each product row contains:
          - Image with URL: https://is4.revolveassets.com/images/p4/ip2/pl2/ONF-MZ454_V1.jpg
          - Product link with code parameter: ...code=ONF-MZ454...
          - Product name in <div style="font-weight:bold">
          - Size in <div>Size: 11</div>
          - Quantity in <td> with align="center"
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            List of RevolveOrderItem objects (consolidated by unique_id + size)
        """
        # First, extract all raw items
        raw_items = []
        
        try:
            # Find all product rows - look for rows with product images
            # Product images are in <a> tags with revolveassets.com URLs that contain product images
            # Product images have revolveassets.com/images URLs
            product_links = soup.find_all('a', href=lambda x: x and 'revolve.com' in str(x))
            
            for link in product_links:
                try:
                    # Check if this link contains a product image
                    img = link.find('img')
                    if not img:
                        continue
                    
                    img_src = img.get('src', '')
                    # Product images are from revolveassets.com/images
                    if 'revolveassets.com/images' not in img_src:
                        continue
                    
                    # Find the parent row
                    parent_row = link.find_parent('tr')
                    if not parent_row:
                        continue
                    
                    # Check if this row contains product information (Size: pattern)
                    row_text = parent_row.get_text()
                    if 'Size:' not in row_text:
                        continue
                    
                    # Extract product details from this row
                    product_details = self._extract_revolve_product_details(parent_row, link)
                    
                    if product_details:
                        raw_items.append(product_details)
                
                except Exception as e:
                    logger.error(f"Error processing Revolve product row: {e}")
                    continue
            
            # Consolidate items by unique_id + size
            consolidated_items = self._consolidate_items(raw_items)
            
            # Log items with ID, size, and quantity
            if consolidated_items:
                items_summary = [f"(ID: {item.unique_id}, Size: {item.size}, Qty: {item.quantity})" for item in consolidated_items]
                logger.info(f"[Revolve] Extracted {len(consolidated_items)} consolidated items: {', '.join(items_summary)}")
            
            return consolidated_items
        
        except Exception as e:
            logger.error(f"Error extracting Revolve items: {e}", exc_info=True)
            return []

    def _extract_revolve_product_details(self, row, link) -> Optional[Dict]:
        """
        Extract product details from a Revolve product row.
        
        Returns:
            Dictionary with unique_id, size, quantity, product_name or None
        """
        try:
            details = {}
            row_text = row.get_text()
            
            # Extract unique_id from product link URL (code parameter)
            href = link.get('href', '')
            code_match = re.search(r'code=([A-Z0-9\-]+)', href, re.IGNORECASE)
            if code_match:
                details['unique_id'] = code_match.group(1).upper()
            else:
                # Fallback: extract from image URL
                img = link.find('img')
                if img:
                    img_src = img.get('src', '')
                    # Pattern: ONF-MZ454_V1.jpg -> ONF-MZ454
                    img_match = re.search(r'/([A-Z0-9\-]+)_V\d+\.jpg', img_src, re.IGNORECASE)
                    if img_match:
                        details['unique_id'] = img_match.group(1).upper()
            
            if not details.get('unique_id'):
                logger.warning("Unique ID not found in Revolve product row")
                return None
            
            # Extract product name - look for <div> with font-weight:bold
            product_name_tag = row.find('div', style=lambda x: x and 'font-weight:bold' in str(x))
            if product_name_tag:
                product_name = product_name_tag.get_text(strip=True)
                details['product_name'] = product_name
                logger.debug(f"Found product name: {product_name}")
            
            # Extract size - look for "Size: 11" pattern
            size_match = re.search(r'Size:\s*([^\n<]+)', row_text, re.IGNORECASE)
            if size_match:
                size = size_match.group(1).strip()
                details['size'] = size
                logger.debug(f"Found size: {size}")
            else:
                logger.warning("Size not found in Revolve row")
                return None
            
            # Extract quantity - look for <td> with align="center" containing a number
            quantity_td = row.find('td', align='center')
            if quantity_td:
                quantity_text = quantity_td.get_text(strip=True)
                # Try to extract number
                qty_match = re.search(r'(\d+)', quantity_text)
                if qty_match:
                    quantity = int(qty_match.group(1))
                    details['quantity'] = quantity
                    logger.debug(f"Found quantity: {quantity}")
                else:
                    # Default to 1 if not found
                    details['quantity'] = 1
                    logger.debug("Quantity not found, defaulting to 1")
            else:
                # Default to 1 if quantity td not found
                details['quantity'] = 1
                logger.debug("Quantity td not found, defaulting to 1")
            
            # Return only if we have the essential fields
            if details.get('unique_id') and details.get('size'):
                return details
            
            logger.warning(f"Missing essential fields: {details}")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting Revolve product details: {e}", exc_info=True)
            return None

    def _consolidate_items(self, raw_items: List[Dict]) -> List[RevolveOrderItem]:
        """
        Consolidate items by unique_id + size, summing quantities.
        
        Args:
            raw_items: List of raw item dictionaries
        
        Returns:
            List of consolidated RevolveOrderItem objects
        """
        # Group items by unique_id + size
        grouped: Dict[str, Dict] = {}
        
        for item in raw_items:
            unique_id = item.get('unique_id')
            size = item.get('size')
            quantity = item.get('quantity', 1)
            product_name = item.get('product_name')
            
            if not unique_id or not size:
                continue
            
            # Create key for grouping
            key = f"{unique_id}_{size}"
            
            if key in grouped:
                # Add quantity to existing item
                grouped[key]['quantity'] += quantity
                logger.debug(f"Consolidating {unique_id} size {size}: adding qty {quantity}, total now {grouped[key]['quantity']}")
            else:
                # Create new grouped item
                grouped[key] = {
                    'unique_id': unique_id,
                    'size': size,
                    'quantity': quantity,
                    'product_name': product_name
                }
        
        # Convert to RevolveOrderItem objects
        consolidated = []
        for key, item_data in grouped.items():
            consolidated.append(RevolveOrderItem(
                unique_id=item_data['unique_id'],
                size=item_data['size'],
                quantity=item_data['quantity'],
                product_name=item_data.get('product_name')
            ))
        
        logger.info(f"Consolidated {len(raw_items)} raw items into {len(consolidated)} unique items")
        return consolidated
    
    def _extract_shipping_address(self, soup: BeautifulSoup) -> str:
        """
        Extract shipping address from email and normalize it.
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            Normalized shipping address or empty string
        """
        try:
            # Look for "Shipping To" header
            shipping_header = soup.find('th', string=re.compile(r'Shipping\s+To', re.IGNORECASE))
            
            if shipping_header:
                # Find the parent table and get the address
                address_td = shipping_header.find_parent('table')
                if address_td:
                    # Get all text from the address section
                    address_text = address_td.get_text(separator='\n', strip=True)
                    
                    # Extract address lines - skip name and phone
                    lines = [line.strip() for line in address_text.split('\n') if line.strip()]
                    
                    address_lines = []
                    for line in lines:
                        # Skip header, name, and phone
                        if 'Shipping To' in line or 'Phone' in line or re.match(r'^\+?1?[\s\-\(\)]?\d{3}[\s\-\(\)]?\d{3}[\s\-\(\)]?\d{4}', line):
                            continue
                        # Collect address lines (street, city/state/zip)
                        if re.search(r'\d+', line) or re.search(r',\s*[A-Z]{2}\s+\d{5}', line):
                            address_lines.append(line)
                    
                    if address_lines:
                        # Join address lines, handling <br> tags
                        address_combined = ', '.join(address_lines)
                        # Clean up any remaining HTML entities
                        address_combined = address_combined.replace('<br>', ' ').replace('<br/>', ' ')
                        normalized = normalize_shipping_address(address_combined)
                        logger.debug(f"Extracted shipping address: {normalized}")
                        return normalized
            
            return ""
        
        except Exception as e:
            logger.error(f"Error extracting shipping address: {e}", exc_info=True)
            return ""
