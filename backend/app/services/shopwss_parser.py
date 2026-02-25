"""
ShopWSS Email Parser
Parses order confirmation emails from ShopWSS
"""

import re
import logging
from typing import List, Optional
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from app.models.email import EmailData

logger = logging.getLogger(__name__)


class ShopWSSOrderItem(BaseModel):
    """Represents a single item from a ShopWSS order"""
    unique_id: str = Field(..., description="Unique identifier for the product (extracted from image URL)")
    size: str = Field(..., description="Size of the product")
    quantity: int = Field(..., description="Quantity of the product")
    product_name: str = Field(..., description="Name of the product")
    
    def __repr__(self):
        if self.product_name and len(self.product_name) > 50:
            product_display = self.product_name[:50] + "..."
        else:
            product_display = self.product_name or "Unknown"
        return f"<ShopWSSOrderItem(unique_id={self.unique_id}, size={self.size}, qty={self.quantity}, product={product_display})>"


class ShopWSSOrderData(BaseModel):
    """Represents ShopWSS order data"""
    order_number: str = Field(..., description="The order number")
    items: List[ShopWSSOrderItem] = Field(..., description="List of items in the order")
    items_count: int = Field(0, description="Total number of items in the order")
    shipping_address: str = Field("", description="Normalized shipping address")

    def __init__(self, **data):
        super().__init__(**data)
        self.items_count = len(self.items)
    
    def __repr__(self):
        return f"<ShopWSSOrderData(order={self.order_number}, items={len(self.items)})>"


class ShopWSSShippingOrderItem(BaseModel):
    """Represents a shipped item - size comes from purchase record (not in shipping email)."""
    unique_id: str = Field(..., description="Unique identifier (e.g. fq8714_004 from image URL)")
    quantity: int = Field(..., description="Quantity shipped")
    product_name: Optional[str] = Field(None, description="Product name")
    size: Optional[str] = Field(None, description="Size - not in email, resolved from purchase record")


class ShopWSSShippingData(BaseModel):
    """Represents ShopWSS shipping notification data."""
    order_number: str = Field(..., description="The order number")
    tracking_number: str = Field("", description="Tracking number if available")
    items: List[ShopWSSShippingOrderItem] = Field(..., description="Shipped items (Item Details section only)")


class ShopWSSCancellationOrderItem(BaseModel):
    """Cancelled item - unique_id from image, size from text (e.g. 13.0 / White/...)."""
    unique_id: str = Field(..., description="Unique identifier (e.g. dv1308_104 from image URL)")
    size: str = Field(..., description="Size (e.g. 13.0)")
    quantity: int = Field(..., description="Quantity cancelled")
    product_name: Optional[str] = Field(None, description="Product name")


class ShopWSSCancellationData(BaseModel):
    """ShopWSS cancellation notification - Order X has been canceled.
    items=[] means full order cancellation (cancel all for order_number)."""
    order_number: str = Field(..., description="The order number")
    items: List[ShopWSSCancellationOrderItem] = Field(default_factory=list, description="Refunded items; empty = cancel all for order")


class ShopWSSEmailParser:
    """
    Parser for ShopWSS order confirmation emails.
    
    Handles email formats like:
    From: help@shopwss.com
    Subject: "Order #1361825686 was received!"
    """
    
    # Email identification - Production
    SHOPWSS_FROM_EMAIL = "help@shopwss.com"
    SUBJECT_ORDER_PATTERN = r"order\s+#(\d+)\s+was\s+received"
    
    # Shipping - same from as order
    SUBJECT_SHIPPING_PATTERN = r"order\s+#(\d+)\s+is\s+about\s+to\s+ship|order\s+.*\s+shipped|partially\s+shipped"
    DEV_SUBJECT_SHIPPING_PATTERN = r"(?:Fwd:\s*)?Order\s+#\d+\s+is\s+about\s+to\s+ship"
    
    # Cancellation - same from as order
    SUBJECT_CANCELLATION_PATTERN = r"order\s+#?\s*(\d+)\s+has\s+been\s+cancel(?:l)?ed"
    
    # Email identification - Development (forwarded emails)
    DEV_SHOPWSS_ORDER_FROM_EMAIL = "glenallagroupc@gmail.com"
    DEV_SUBJECT_ORDER_PATTERN = r"Fwd:.*order\s+#(\d+)\s+was\s+received"
    
    def __init__(self):
        """Initialize the ShopWSS email parser."""
        from app.config.settings import get_settings
        self.settings = get_settings()
    
    @property
    def order_from_email(self) -> str:
        """Get the appropriate from email address based on environment."""
        if self.settings.is_development:
            return self.DEV_SHOPWSS_ORDER_FROM_EMAIL
        return self.SHOPWSS_FROM_EMAIL
    
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
            return "was received"
        return "was received"
    
    @property
    def update_from_email(self) -> str:
        """From address for shipping emails (same as order confirmation)."""
        return self.order_from_email
    
    @property
    def shipping_subject_query(self) -> str:
        """Subject query for Gmail shipping search."""
        return 'subject:("is about to ship" OR "partially shipped")'
    
    @property
    def cancellation_subject_query(self) -> str:
        """Subject query for Gmail cancellation search."""
        return 'subject:"has been canceled"'
    
    def is_shopwss_email(self, email_data: EmailData) -> bool:
        """
        Check if email is from ShopWSS.
        
        In dev mode, multiple retailers forward from glenallagroupc. Require HTML
        to contain "shopwss" to uniquely filter ShopWSS and avoid claiming other
        retailers' forwarded emails.
        """
        sender_lower = email_data.sender.lower()
        
        # In development, check for forwarded emails from dev email address
        if self.settings.is_development:
            if self.DEV_SHOPWSS_ORDER_FROM_EMAIL.lower() in sender_lower:
                html = (email_data.html_content or "").lower()
                if "shopwss" in html:
                    return True
                return False
        
        # In production, check for ShopWSS email
        return self.SHOPWSS_FROM_EMAIL.lower() in sender_lower
    
    def is_shipping_email(self, email_data: EmailData) -> bool:
        """Check if email is a ShopWSS shipping notification."""
        if not self.is_shopwss_email(email_data):
            return False
        subject_lower = (email_data.subject or "").lower()
        if re.search(r"is\s+about\s+to\s+ship", subject_lower, re.IGNORECASE):
            return True
        if re.search(r"partially\s+shipped|order\s+.*\s+shipped", subject_lower, re.IGNORECASE):
            return True
        if self.settings.is_development and re.search(self.DEV_SUBJECT_SHIPPING_PATTERN, subject_lower, re.IGNORECASE):
            return True
        return False
    
    def is_cancellation_email(self, email_data: EmailData) -> bool:
        """Check if email is a ShopWSS cancellation notification."""
        if not self.is_shopwss_email(email_data):
            return False
        subject_lower = (email_data.subject or "").lower()
        return bool(re.search(r"has\s+been\s+cancel(?:l)?ed", subject_lower, re.IGNORECASE))
    
    def is_order_confirmation_email(self, email_data: EmailData) -> bool:
        """Check if email is an order confirmation"""
        if not self.is_shopwss_email(email_data):
            return False
        subject_pattern = self.order_subject_pattern
        return bool(re.search(subject_pattern, email_data.subject, re.IGNORECASE))
    
    def parse_email(self, email_data: EmailData) -> Optional[ShopWSSOrderData]:
        """
        Parse ShopWSS order confirmation email.
        
        Args:
            email_data: EmailData object containing email information
        
        Returns:
            ShopWSSOrderData object or None if parsing fails
        """
        try:
            html_content = email_data.html_content
            
            if not html_content:
                logger.error("No HTML content in ShopWSS email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extract order number from subject or HTML
            order_number = self._extract_order_number(email_data.subject, soup)
            if not order_number:
                logger.error("Failed to extract order number from ShopWSS email")
                return None
            
            logger.info(f"Extracted ShopWSS order number: {order_number}")
            
            # Extract items
            items = self._extract_items(soup)
            
            if not items:
                logger.error("Failed to extract any items from ShopWSS email")
                return None
            
            logger.info(f"Successfully extracted {len(items)} items from ShopWSS order {order_number}")
            for item in items:
                logger.debug(f"  - {item}")
            
            # Extract shipping address
            from app.utils.address_utils import normalize_shipping_address
            shipping_address = self._extract_shipping_address(soup)
            if shipping_address:
                normalized = normalize_shipping_address(shipping_address)
                logger.info(f"Extracted shipping address: {normalized}")
                shipping_address = normalized
            
            return ShopWSSOrderData(order_number=order_number, items=items, shipping_address=shipping_address)
        
        except Exception as e:
            logger.error(f"Error parsing ShopWSS email: {e}", exc_info=True)
            return None
    
    def parse_shipping_email(self, email_data: EmailData) -> Optional["ShopWSSShippingData"]:
        """
        Parse ShopWSS shipping notification email.
        
        Subject: "Order #1361825686 is about to ship!" or "partially shipped"
        ONLY extract items from "Item Details" section - NOT "Other items in your order".
        Size not in email - resolved from purchase tracker by order_number + unique_id.
        unique_id from image: FQ8714004_1.jpg -> fq8714_004
        """
        try:
            html_content = email_data.html_content
            if not html_content:
                logger.error("No HTML content in ShopWSS shipping email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            order_number = self._extract_shipping_order_number(email_data.subject, soup)
            if not order_number:
                logger.error("Failed to extract order number from ShopWSS shipping email")
                return None
            
            tracking_number = self._extract_shipping_tracking_number(soup)
            if not tracking_number:
                tracking_number = "Unknown"
            
            items = self._extract_shipping_items(soup)
            if not items:
                logger.error("Failed to extract items from ShopWSS shipping email (Item Details section)")
                return None
            
            logger.info(
                f"Parsed ShopWSS shipping: order={order_number}, tracking={tracking_number}, items={len(items)}"
            )
            return ShopWSSShippingData(
                order_number=order_number,
                tracking_number=tracking_number or "",
                items=items
            )
        except Exception as e:
            logger.error(f"Error parsing ShopWSS shipping email: {e}", exc_info=True)
            return None
    
    def parse_cancellation_email(self, email_data: EmailData) -> Optional["ShopWSSCancellationData"]:
        """
        Parse ShopWSS full order cancellation email.
        Subject: "Order 1354722058 has been canceled" or "Order #1354722058 has been canceled"
        Returns order_number only - items=[] means cancel ALL products for this order.
        """
        try:
            html_content = email_data.html_content
            subject = email_data.subject or ""
            soup = BeautifulSoup(html_content or "", "lxml")
            
            order_number = None
            if subject:
                match = re.search(r"Order\s+#?\s*(\d+)\s+has\s+been\s+cancel(?:l)?ed", subject, re.IGNORECASE)
                if match:
                    order_number = match.group(1)
            if not order_number and soup:
                text = soup.get_text()
                match = re.search(r"Order\s+#?\s*(\d+)\s+Order\s+Date", text, re.IGNORECASE)
                if match:
                    order_number = match.group(1)
            
            if not order_number:
                logger.error("Failed to extract order number from ShopWSS cancellation email")
                return None
            
            logger.info(f"Parsed ShopWSS full cancellation: order={order_number} (cancel all items)")
            return ShopWSSCancellationData(order_number=order_number, items=[])
        except Exception as e:
            logger.error(f"Error parsing ShopWSS cancellation email: {e}", exc_info=True)
            return None
    
    def _extract_shipping_order_number(self, subject: str, soup: BeautifulSoup = None) -> Optional[str]:
        """Extract order number from shipping subject: 'Order #1361825686 is about to ship!'"""
        if subject:
            match = re.search(r'Order\s+#(\d+)\s+is\s+about\s+to\s+ship', subject, re.IGNORECASE)
            if match:
                return match.group(1)
            match = re.search(r'Order\s+#(\d+)', subject, re.IGNORECASE)
            if match:
                return match.group(1)
        if soup:
            text = soup.get_text()
            match = re.search(r'Order\s+Number\s*[:\s]*(\d+)', text, re.IGNORECASE)
            if match:
                return match.group(1)
        return None
    
    def _extract_shipping_tracking_number(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract tracking number from ShopWSS shipping email."""
        try:
            text = soup.get_text().upper()
            match = re.search(r'\b1Z[A-Z0-9]{16}\b', text)
            if match:
                return match.group(0)
            match = re.search(r'\b\d{12,22}\b', text)
            if match:
                return match.group(0)
            return None
        except Exception:
            return None
    
    def _extract_shipping_items(self, soup: BeautifulSoup) -> List["ShopWSSShippingOrderItem"]:
        """
        Extract shipped items ONLY from "Item Details" section.
        EXCLUDE "Other items in your order" (Status: Ordered) - those have NOT shipped.
        Size not in email - match by order_number + unique_id to get size from purchase record.
        
        Filtering: Single pass through document order. Only images that appear
        BEFORE "Other items in your order" text are included. Images under
        "Other items" (e.g. FQ8714400) are excluded.
        
        unique_id: From image URL files/FQ8714004_1.jpg or _1_compact_cropped.jpg -> fq8714_004
        """
        items = []
        try:
            other_items_el = soup.find(string=re.compile(r'Other\s+items\s+in\s+your\s+order', re.IGNORECASE))
            if not other_items_el:
                logger.warning("Could not find 'Other items in your order' - cannot reliably filter Item Details")
            
            # Product image pattern: cdn.shopify.com + files + FQ8714004_1.jpg or _1_compact_cropped.jpg
            product_img_pattern = re.compile(
                r'files/([A-Z]{2}\d{7})_\d+(?:_compact_cropped)?\.(jpg|jpeg|png)',
                re.IGNORECASE
            )
            
            # Single pass: collect product images that appear BEFORE "Other items in your order"
            item_details_imgs = []
            past_other_items = False
            
            for el in soup.descendants:
                if el is other_items_el:
                    past_other_items = True
                    continue
                if past_other_items:
                    continue
                if getattr(el, 'name', None) != 'img':
                    continue
                src = el.get('src', '') or ''
                # Gmail proxy: actual URL after # (e.g. ci3.googleusercontent.com/...#https://cdn.shopify.com/...)
                if '#' in src:
                    parts = src.split('#')
                    if len(parts) > 1:
                        src = parts[-1]
                if 'cdn.shopify.com' not in src or 'files' not in src:
                    continue
                if product_img_pattern.search(src):
                    item_details_imgs.append(el)
            
            seen_unique_ids = set()
            for img in item_details_imgs:
                img_src = img.get('src', '') or ''
                if '#' in img_src:
                    img_src = img_src.split('#')[-1]
                match = re.search(r'files/([A-Z]{2}\d{7})_', img_src, re.IGNORECASE)
                if not match:
                    continue
                unique_id_raw = match.group(1).upper()
                if len(unique_id_raw) == 9:
                    prefix = unique_id_raw[:-3].lower()
                    suffix = unique_id_raw[-3:].lower()
                    unique_id = f"{prefix}_{suffix}"
                else:
                    unique_id = unique_id_raw.lower()
                
                if unique_id in seen_unique_ids:
                    continue
                seen_unique_ids.add(unique_id)
                
                # Extract quantity from the row containing this image
                row = img.find_parent('tr') or img.find_parent('td')
                if row and getattr(row, 'name', None) != 'tr':
                    row = row.find_parent('tr')
                row_text = (row.get_text() if row else '') or ''
                qty_match = re.search(r'Quantity\s*:\s*(\d+)', row_text, re.IGNORECASE)
                quantity = int(qty_match.group(1)) if qty_match else 1
                
                product_name = None
                if row:
                    name_td = row.find('td', style=lambda x: x and 'font-size:18px' in str(x))
                    if name_td:
                        product_name = name_td.get_text(strip=True)
                if not product_name and img.get('alt'):
                    product_name = img.get('alt', '').strip()
                
                items.append(ShopWSSShippingOrderItem(
                    unique_id=unique_id,
                    quantity=quantity,
                    product_name=product_name or "Unknown",
                    size=None
                ))
                logger.info(f"Extracted ShopWSS shipped item (Item Details): unique_id={unique_id}, qty={quantity}")
            
            return items
        except Exception as e:
            logger.error(f"Error extracting ShopWSS shipping items: {e}", exc_info=True)
            return []
    
    def _extract_order_number(self, subject: str, soup: BeautifulSoup = None) -> Optional[str]:
        """
        Extract order number from ShopWSS email subject or HTML.
        
        Subject format: "Order #1361825686 was received!"
        HTML format: Order number in td
        
        Args:
            subject: Email subject string
            soup: BeautifulSoup object (optional, for fallback)
        
        Returns:
            Order number or None
        """
        try:
            # First try to extract from subject
            match = re.search(r'Order\s+#(\d+)\s+was\s+received', subject, re.IGNORECASE)
            if match:
                order_number = match.group(1)
                logger.debug(f"Found ShopWSS order number in subject: {order_number}")
                return order_number
            
            # Fallback: extract from HTML if soup is provided
            if soup:
                # Look for order number in td (usually just the number)
                text = soup.get_text()
                # Look for a standalone number that could be an order number
                # Order numbers are typically 10 digits
                match = re.search(r'\b(\d{8,12})\b', text)
                if match:
                    order_number = match.group(1)
                    logger.debug(f"Found ShopWSS order number in HTML: {order_number}")
                    return order_number
            
            logger.warning("Order number not found in ShopWSS email subject or HTML")
            return None
        
        except Exception as e:
            logger.error(f"Error extracting ShopWSS order number: {e}")
            return None
    
    def _extract_items(self, soup: BeautifulSoup) -> List[ShopWSSOrderItem]:
        """
        Extract order items from ShopWSS email.
        
        Structure:
        - Product image with unique ID in filename
        - Product name: "Air Force 1 Low 07 LV8 - Mens"
        - Size and color: "09.0 / Black/Summit White/Gum/Light Brown"
        - Quantity: "Quantity: 2"
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            List of ShopWSSOrderItem objects
        """
        items = []
        
        try:
            # Find all product images (from Shopify CDN)
            product_images = soup.find_all('img', src=lambda x: x and 'cdn.shopify.com' in str(x) and 'files' in str(x) and '_compact_cropped.jpg' in str(x))
            
            logger.info(f"Found {len(product_images)} potential product images")
            
            for img in product_images:
                try:
                    # Get the parent container for this product
                    # Find the parent table row that contains this image
                    product_row = img.find_parent('tr')
                    if not product_row:
                        continue
                    
                    # Extract product details from this row
                    product_details = self._extract_product_details(product_row, img)
                    
                    if product_details:
                        items.append(ShopWSSOrderItem(
                            unique_id=product_details['unique_id'],
                            size=product_details['size'],
                            quantity=product_details['quantity'],
                            product_name=product_details['product_name']
                        ))
                        logger.info(
                            f"Extracted ShopWSS item: {product_details['product_name']} | "
                            f"unique_id={product_details['unique_id']}, "
                            f"Size={product_details['size']}, "
                            f"Qty={product_details['quantity']}"
                        )
                
                except Exception as e:
                    logger.error(f"Error processing ShopWSS product: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error extracting ShopWSS items: {e}", exc_info=True)
        
        return items
    
    def _extract_product_details(self, row, img) -> Optional[dict]:
        """
        Extract product details from a product row.
        
        Returns:
            Dictionary with unique_id, size, quantity, product_name or None
        """
        try:
            details = {}
            
            # Extract unique ID from image URL
            # Pattern: .../files/FQ8714004_1_compact_cropped.jpg
            # Extract: FQ8714004 -> convert to fq8714_004
            img_src = img.get('src', '')
            # Look for pattern: files/letters+numbers_ in filename
            # Match: FQ8714004 (2 letters + 7 digits)
            match = re.search(r'files/([A-Z]{2}\d{7})_', img_src, re.IGNORECASE)
            if match:
                unique_id_raw = match.group(1).upper()
                # Convert to lowercase and add underscore before last 3 digits
                # FQ8714004 -> fq8714_004
                if len(unique_id_raw) == 9:  # 2 letters + 7 digits
                    # Extract prefix (2 letters + first 4 digits)
                    prefix = unique_id_raw[:-3].lower()
                    # Extract last 3 digits
                    suffix = unique_id_raw[-3:].lower()
                    unique_id = f"{prefix}_{suffix}"
                else:
                    unique_id = unique_id_raw.lower()
                
                details['unique_id'] = unique_id
                logger.debug(f"Found unique ID: {unique_id} (from {unique_id_raw})")
            else:
                logger.warning(f"Could not extract unique ID from image URL: {img_src}")
                return None
            
            # Extract product name
            # Look for td with font-size:18px (product name)
            product_name_td = row.find('td', style=lambda x: x and 'font-size:18px' in str(x))
            if product_name_td:
                product_name = product_name_td.get_text(strip=True)
                # Clean up extra whitespace
                product_name = re.sub(r'\s+', ' ', product_name).strip()
                details['product_name'] = product_name
                logger.debug(f"Found product name: {product_name}")
            else:
                logger.warning("Product name not found")
                return None
            
            # Extract size and quantity
            # Size format: "09.0 / Black/Summit White/Gum/Light Brown"
            # Quantity format: "Quantity: 2"
            row_text = row.get_text()
            
            # Extract size (format: XX.X /)
            size_match = re.search(r'(\d+\.\d+)\s*/\s*', row_text)
            if size_match:
                size_value = size_match.group(1)
                # Remove decimal: 09.0 -> 9
                size_float = float(size_value)
                if size_float == int(size_float):
                    size = str(int(size_float))
                else:
                    size = str(size_float)
                details['size'] = size
                logger.debug(f"Found size: {size}")
            else:
                logger.warning("Size not found")
                return None
            
            # Extract quantity
            qty_match = re.search(r'Quantity:\s*(\d+)', row_text, re.IGNORECASE)
            if qty_match:
                quantity = int(qty_match.group(1))
                details['quantity'] = quantity
                logger.debug(f"Found quantity: {quantity}")
            else:
                logger.warning("Quantity not found")
                return None
            
            return details
            
        except Exception as e:
            logger.error(f"Error extracting product details: {e}", exc_info=True)
            return None
    
    def _extract_shipping_address(self, soup: BeautifulSoup) -> str:
        """
        Extract shipping address from ShopWSS email.
        
        Look for "Delivery Address" header and extract address lines below it.
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            Shipping address or empty string
        """
        try:
            # Look for "Delivery Address" td element
            delivery_tds = soup.find_all('td', string=lambda x: x and 'Delivery Address' in str(x))
            
            for delivery_td in delivery_tds:
                # Find the parent table
                parent_table = delivery_td.find_parent('table')
                if parent_table:
                    # Get all text from the table
                    table_text = parent_table.get_text(separator='\n', strip=True)
                    lines = [line.strip() for line in table_text.split('\n') if line.strip()]
                    
                    address_lines = []
                    found_delivery = False
                    
                    for line in lines:
                        if 'delivery address' in line.lower():
                            found_delivery = True
                            continue
                        
                        if found_delivery:
                            # Stop at next section
                            if any(keyword in line.lower() for keyword in ['billing', 'payment', 'subtotal', 'total', 'order #']):
                                break
                            
                            # Skip name lines (simple heuristic)
                            if re.match(r'^[A-Z][a-z]+\s+[A-Z][a-z]+$', line):
                                continue
                            
                            # Collect address lines that contain numbers or common address components
                            if re.search(r'\d+', line) or any(keyword in line.lower() for keyword in ['lane', 'street', 'ave', 'road', 'suite', 'ste', 'ln', 'independence', 'or']):
                                address_lines.append(line)
                                # Typically we want 1-3 lines
                                if len(address_lines) >= 3:
                                    break
                    
                    if address_lines:
                        address_combined = ', '.join(address_lines)
                        logger.debug(f"Extracted shipping address (raw): {address_combined}")
                        return address_combined
            
            logger.warning("Shipping address not found in ShopWSS email")
            return ""
        
        except Exception as e:
            logger.error(f"Error extracting shipping address: {e}", exc_info=True)
            return ""
