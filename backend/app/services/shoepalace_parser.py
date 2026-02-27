"""
Shoe Palace Email Parser
Parses order confirmation and cancellation emails from Shoe Palace
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


class ShoepalaceOrderItem(BaseModel):
    unique_id: str = Field(..., description="Unique identifier for the product (e.g., SKU, style code)")
    size: str = Field(..., description="Size of the product")
    quantity: int = Field(..., description="Quantity of the product")
    product_name: Optional[str] = Field(None, description="Name of the product")
    
    def __repr__(self):
        if self.product_name and len(self.product_name) > 50:
            product_display = self.product_name[:50] + "..."
        else:
            product_display = self.product_name or "Unknown"
        return f"<ShoepalaceOrderItem(unique_id={self.unique_id}, size={self.size}, qty={self.quantity}, product={product_display})>"


class ShoepalaceOrderData(BaseModel):
    order_number: str = Field(..., description="The order number")
    items: List[ShoepalaceOrderItem] = Field(..., description="List of items in the order")
    items_count: int = Field(0, description="Total number of items in the order")
    shipping_address: str = Field("", description="Normalized shipping address")

    def __init__(self, **data):
        super().__init__(**data)
        self.items_count = len(self.items)


class ShoepalaceShippingData(BaseModel):
    """Represents Shoe Palace shipping notification data - same structure as Footlocker for processing."""
    order_number: str = Field(..., description="The order number")
    tracking_number: str = Field("", description="Tracking number if available")
    items: List[ShoepalaceOrderItem] = Field(..., description="List of shipped items")


class ShoepalaceCancellationData(BaseModel):
    """Represents Shoe Palace cancellation notification data"""
    order_number: str = Field(..., description="The order number")
    items: List[ShoepalaceOrderItem] = Field(..., description="List of cancelled items")
    
    def __repr__(self):
        return f"<ShoepalaceCancellationData(order={self.order_number}, items={len(self.items)})>"


class ShoepalaceEmailParser:
    # Email identification - Order Confirmation (Production)
    SHOEPALACE_FROM_EMAIL = "store+8523376@t.shopifyemail.com"
    SUBJECT_ORDER_PATTERN = r"confirmed"
    
    # Email identification - Shipping (Production: same from as order - Shopify)
    SUBJECT_SHIPPING_PATTERN = r"shipment.*order.*(#?SP?\d+).*on the way|shipment.*on the way"
    DEV_SUBJECT_SHIPPING_PATTERN = r"(?:Fwd:\s*)?A shipment from order #SP\d+ is on the way"
    
    # Email identification - Cancellation (Production)
    SHOEPALACE_CANCELLATION_FROM_EMAIL = "customerservice@shoepalace.com"
    SUBJECT_CANCELLATION_PATTERN = r"order.*cancel|cancel.*notification|cancellation"
    # "Order Cancelation Notification: Items cancelled for Order SP2020112" - items table, no unique_id in email
    SUBJECT_CANCELLATION_ITEMS_PATTERN = r"order\s+cancelation\s+notification|items\s+cancelled\s+for\s+order"
    
    # Email identification - Development (forwarded emails)
    DEV_SHOEPALACE_ORDER_FROM_EMAIL = "glenallagroupc@gmail.com"
    DEV_SUBJECT_ORDER_PATTERN = r"Fwd:.*confirmed"

    def __init__(self):
        """Initialize the Shoe Palace email parser."""
        self.settings = get_settings()
    
    @property
    def order_from_email(self) -> str:
        """Get the appropriate from email address based on environment."""
        if self.settings.is_development:
            return self.DEV_SHOEPALACE_ORDER_FROM_EMAIL
        return self.SHOEPALACE_FROM_EMAIL
    
    @property
    def order_subject_pattern(self) -> str:
        """Get the appropriate subject pattern (regex) for matching based on environment."""
        if self.settings.is_development:
            return self.DEV_SUBJECT_ORDER_PATTERN
        return self.SUBJECT_ORDER_PATTERN
    
    @property
    def order_subject_query(self) -> str:
        """Get the appropriate subject pattern for Gmail queries (non-regex) based on environment."""
        # Return just "confirmed" - the background scheduler/API will add "shopifyemail" to the query
        return "confirmed"
    
    @property
    def update_from_email(self) -> str:
        """From address for shipping emails (same as order - Shopify for prod, glenallagroupc for dev)."""
        return self.order_from_email
    
    @property
    def shipping_subject_query(self) -> str:
        """Subject query for Gmail shipping search."""
        if self.settings.is_development:
            return 'subject:"A shipment from order"'
        return 'subject:"A shipment from order"'

    @property
    def cancellation_from_query(self) -> str:
        """Gmail from query for cancellation emails."""
        if self.settings.is_development:
            return f'from:{self.DEV_SHOEPALACE_ORDER_FROM_EMAIL}'
        return f'from:{self.SHOEPALACE_CANCELLATION_FROM_EMAIL}'

    @property
    def cancellation_subject_query(self) -> str:
        """Subject query for Gmail cancellation search."""
        return 'subject:("Order Cancelation Notification" OR "Items cancelled for Order")'

    def is_shoepalace_email(self, email_data: EmailData) -> bool:
        """
        Check if email is from Shoe Palace.
        
        In dev mode, multiple retailers forward from glenallagroupc. Require HTML
        to contain "shoepalace" or "shopifyemail" to avoid claiming other retailers'
        forwarded emails (Footlocker, Champs, Snipes, etc.).
        """
        sender_lower = email_data.sender.lower()
        
        # In development, check for forwarded emails from dev email address
        if self.settings.is_development:
            if self.DEV_SHOEPALACE_ORDER_FROM_EMAIL.lower() in sender_lower:
                html = (email_data.html_content or "").lower()
                # Shoe Palace uses Shopify (shopifyemail) and has shoepalace branding
                if "shoepalace" in html or "shopifyemail" in html:
                    return True
                return False
        
        # In production, check for Shoe Palace emails (order confirmation or cancellation)
        if self.SHOEPALACE_FROM_EMAIL.lower() in sender_lower:
            return True
        
        if self.SHOEPALACE_CANCELLATION_FROM_EMAIL.lower() in sender_lower:
            return True
        
        # Also check for "shoepalace" in sender name
        if 'shoepalace' in sender_lower or 'shoe palace' in sender_lower:
            return True
        
        return False

    def is_shipping_email(self, email_data: EmailData) -> bool:
        """Check if email is a Shoe Palace shipping notification."""
        if not self.is_shoepalace_email(email_data):
            return False
        subject_lower = (email_data.subject or "").lower()
        if re.search(r"shipment.*on the way", subject_lower, re.IGNORECASE):
            return True
        if self.settings.is_development and re.search(self.DEV_SUBJECT_SHIPPING_PATTERN, subject_lower, re.IGNORECASE):
            return True
        return False

    def is_order_confirmation_email(self, email_data: EmailData) -> bool:
        """Check if email is an order confirmation"""
        # Check if sender matches Shoe Palace
        if not self.is_shoepalace_email(email_data):
            return False
        
        subject_lower = email_data.subject.lower()
        pattern = self.order_subject_pattern
        
        # Use regex matching for subject pattern
        if re.search(pattern, subject_lower, re.IGNORECASE):
            # Make sure it's not a cancellation email
            if not self.is_cancellation_email(email_data):
                return True
        
        return False
    
    def is_cancellation_email(self, email_data: EmailData) -> bool:
        """
        Check if email is a cancellation notification.
        
        Args:
            email_data: EmailData object
        
        Returns:
            True if this is a cancellation notification email
        """
        # Check if sender matches Shoe Palace
        if not self.is_shoepalace_email(email_data):
            return False
        
        subject_lower = email_data.subject.lower()
        
        # Check subject pattern
        if re.search(self.SUBJECT_CANCELLATION_PATTERN, subject_lower, re.IGNORECASE):
            return True
        
        # Also check body text for cancellation indicators
        if email_data.html_content:
            html_lower = email_data.html_content.lower()
            if any(phrase in html_lower for phrase in [
                "order cancelation notification",
                "order cancellation notification",
                "order cancelation",
                "order cancellation",
                "has been cancelled",
                "has been canceled",
                "cancel reason"
            ]):
                return True
        
        return False

    def parse_email(self, email_data: EmailData):
        """
        Generic parse method that routes to the appropriate parser based on email type.
        
        Args:
            email_data: EmailData object containing email information
        
        Returns:
            ShoepalaceOrderData or ShoepalaceCancellationData depending on email type
        """
        if self.is_cancellation_email(email_data):
            return self.parse_cancellation_email(email_data)
        elif self.is_shipping_email(email_data):
            return self.parse_shipping_email(email_data)
        elif self.is_order_confirmation_email(email_data):
            return self.parse_order_confirmation_email(email_data)
        else:
            logger.warning(f"Unknown Shoe Palace email type: {email_data.subject}")
            return None
    
    def parse_order_confirmation_email(self, email_data: EmailData) -> Optional[ShoepalaceOrderData]:
        """
        Parse Shoe Palace order confirmation email.
        
        Args:
            email_data: EmailData object containing email information
        
        Returns:
            ShoepalaceOrderData object or None if parsing fails
        """
        try:
            html_content = email_data.html_content
            
            if not html_content:
                logger.error("No HTML content in Shoe Palace email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extract order number from subject first, then try body as fallback
            order_number = self._extract_order_number(email_data.subject)
            if not order_number:
                # Try extracting from email body as fallback
                order_number = self._extract_order_number_from_body(soup)
            
            if not order_number:
                logger.error("Failed to extract order number from Shoe Palace email")
                return None
            
            logger.info(f"Extracted Shoe Palace order number: {order_number}")
            
            # Extract items using BeautifulSoup
            items = self._extract_items(soup)
            
            if not items:
                logger.error("Failed to extract any items from Shoe Palace email")
                return None
            
            logger.info(f"Successfully extracted {len(items)} items from Shoe Palace order {order_number}")
            for item in items:
                logger.debug(f"  - {item}")
            
            # Extract shipping address
            shipping_address = self._extract_shipping_address(soup)
            if shipping_address:
                logger.info(f"Extracted shipping address: {shipping_address}")
            
            return ShoepalaceOrderData(order_number=order_number, items=items, shipping_address=shipping_address)
        
        except Exception as e:
            logger.error(f"Error parsing Shoe Palace email: {e}", exc_info=True)
            return None
    
    def parse_shipping_email(self, email_data: EmailData) -> Optional["ShoepalaceShippingData"]:
        """
        Parse Shoe Palace shipping notification email.
        
        Subject: "A shipment from order #SP1881155 is on the way"
        Order: SP1881155 (normalized to 1881155 for matching with order confirmation)
        Items: Same structure as order confirmation - unique_id from product name slug
        (e.g. "Pegasus 41 Road Womens Running Shoes (Photon Dust/...)" -> pegasus-41-road-womens-running-shoes-photon-dust-metallic-pewter-sail-echo-pink)
        """
        try:
            html_content = email_data.html_content
            if not html_content:
                logger.error("No HTML content in Shoe Palace shipping email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            order_number = self._extract_shipping_order_number(email_data.subject)
            if not order_number:
                order_number = self._extract_shipping_order_number_from_body(soup)
            if not order_number:
                logger.error("Failed to extract order number from Shoe Palace shipping email")
                return None
            
            tracking_number = self._extract_shipping_tracking_number(soup)
            if not tracking_number:
                tracking_number = "Unknown"
            
            items = self._extract_items(soup)  # Same HTML structure as order confirmation
            if not items:
                logger.error("Failed to extract items from Shoe Palace shipping email")
                return None
            
            logger.info(
                f"Parsed Shoe Palace shipping: order={order_number}, tracking={tracking_number}, items={len(items)}"
            )
            return ShoepalaceShippingData(
                order_number=order_number,
                tracking_number=tracking_number or "",
                items=items
            )
        except Exception as e:
            logger.error(f"Error parsing Shoe Palace shipping email: {e}", exc_info=True)
            return None
    
    def parse_cancellation_email(self, email_data: EmailData) -> Optional[ShoepalaceCancellationData]:
        """
        Parse Shoe Palace cancellation notification email.
        For "Order Cancelation Notification: Items cancelled for Order" format, returns None
        (use parse_cancellation_email_partial - unique_id from email doesn't match purchase tracker).
        """
        try:
            subject = (email_data.subject or "").lower()
            if re.search(self.SUBJECT_CANCELLATION_ITEMS_PATTERN, subject):
                return None  # Use parse_cancellation_email_partial - no usable unique_id in email
            html_content = email_data.html_content
            if not html_content:
                logger.error("No HTML content in Shoe Palace cancellation email")
                return None
            soup = BeautifulSoup(html_content, 'lxml')
            order_number = self._extract_cancellation_order_number(soup)
            if not order_number:
                logger.error("Failed to extract order number from Shoe Palace cancellation email")
                return None
            logger.info(f"Extracted Shoe Palace cancellation order number: {order_number}")
            items = self._extract_cancellation_items(soup)
            if not items:
                logger.warning(f"No cancelled items found in Shoe Palace cancellation email for order {order_number}")
                return None
            logger.info(f"Successfully extracted {len(items)} cancelled items from Shoe Palace cancellation order {order_number}")
            return ShoepalaceCancellationData(order_number=order_number, items=items)
        except Exception as e:
            logger.error(f"Error parsing Shoe Palace cancellation email: {e}", exc_info=True)
            return None

    def parse_cancellation_email_partial(self, email_data: EmailData) -> Optional[dict]:
        """
        Parse Shoe Palace "Order Cancelation Notification: Items cancelled for Order" email.
        Extracts order_number + items with product_name, size, quantity. No unique_id in email.
        Returns dict for manual review: {order_number, items, subject, missing_fields}.
        """
        try:
            html_content = email_data.html_content
            subject = email_data.subject or ""
            if not html_content:
                return None
            soup = BeautifulSoup(html_content, "lxml")
            order_number = self._extract_cancellation_order_number(soup)
            if not order_number:
                return None
            items = self._extract_partial_cancellation_items(soup)
            if not items:
                return None
            return {
                "order_number": order_number,
                "subject": subject,
                "items": items,
                "missing_fields": ["unique_id"],
            }
        except Exception as e:
            logger.error(f"Error parsing Shoe Palace partial cancellation: {e}", exc_info=True)
            return None

    def _extract_partial_cancellation_items(self, soup: BeautifulSoup) -> List[dict]:
        """Extract items from Order Cancelation Notification table. Returns [{product_name, size, quantity}].
        Sums quantities for same product_name+size (e.g. 3 rows of CLIFTON Size=10 Qty=1 -> 1 item Qty=3)."""
        raw_items: List[dict] = []
        try:
            header_row = soup.find('tr', string=re.compile(r'ITEM\s+DESCRIPTION', re.IGNORECASE))
            if not header_row:
                header_tds = soup.find_all('td', string=re.compile(r'ITEM\s+DESCRIPTION', re.IGNORECASE))
                if header_tds:
                    header_row = header_tds[0].find_parent('tr')
            if not header_row:
                return []
            for row in header_row.find_all_next('tr'):
                row_text = row.get_text(strip=True)
                if not row_text or 'ITEM DESCRIPTION' in row_text or 'ITEM PRICE' in row_text or 'QTY' in row_text:
                    continue
                if not re.search(r'\d+-[A-Z]+', row_text):
                    continue
                tds = row.find_all('td')
                if len(tds) < 3:
                    continue
                product_lines = [l.strip() for l in tds[0].get_text().split('\n') if l.strip()]
                product_name = product_lines[0] if product_lines else ""
                size = ""
                for line in product_lines:
                    m = re.search(r'Size\s*=\s*([^\s]+)', line, re.IGNORECASE)
                    if m:
                        size = m.group(1).strip()
                        break
                quantity = 1
                qty_m = re.search(r'(\d+)', tds[2].get_text(strip=True))
                if qty_m:
                    quantity = int(qty_m.group(1))
                if product_name and size:
                    raw_items.append({"product_name": product_name, "size": size, "quantity": quantity})
            # Sum quantities for same product_name+size
            summed: dict = {}
            for it in raw_items:
                key = (it["product_name"], it["size"])
                if key not in summed:
                    summed[key] = {**it}
                else:
                    summed[key]["quantity"] += it["quantity"]
            return list(summed.values())
        except Exception as e:
            logger.error(f"Error extracting partial cancellation items: {e}", exc_info=True)
            return []

    def _extract_shipping_order_number(self, subject: str) -> Optional[str]:
        """
        Extract order number from Shoe Palace shipping email subject.
        
        Subject format: "A shipment from order #SP1881155 is on the way"
        Extract: 1881155 (without SP prefix, for matching with order confirmation)
        """
        if not subject:
            return None
        try:
            match = re.search(r'order\s+#SP?(\d+)', subject, re.IGNORECASE)
            if match:
                return match.group(1)
            return None
        except Exception as e:
            logger.error(f"Error extracting Shoe Palace shipping order number: {e}")
            return None
    
    def _extract_shipping_order_number_from_body(self, soup: BeautifulSoup) -> Optional[str]:
        """Fallback: extract order number from shipping email body (Order Number #1234567)."""
        try:
            text = soup.get_text()
            match = re.search(r'Order\s+Number\s*#\s*(?:SP)?(\d+)', text, re.IGNORECASE)
            if match:
                return match.group(1)
            return None
        except Exception as e:
            logger.error(f"Error extracting Shoe Palace shipping order number from body: {e}")
            return None
    
    def _extract_shipping_tracking_number(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract tracking number from Shoe Palace shipping email if present."""
        try:
            text = soup.get_text().upper()
            # UPS
            match = re.search(r'\b1Z[A-Z0-9]{16}\b', text)
            if match:
                return match.group(0)
            # FedEx / USPS
            match = re.search(r'\b\d{12,22}\b', text)
            if match:
                return match.group(0)
            return None
        except Exception as e:
            logger.debug(f"Could not extract tracking from Shoe Palace shipping: {e}")
            return None
    
    def _extract_order_number(self, subject: str) -> Optional[str]:
        """
        Extract order number from Shoe Palace email subject.
        
        Subject format: Order #SP1909467 confirmed or Fwd: Order #SP1879967 confirmed
        Extract: 1909467 (without SP prefix)
        
        Args:
            subject: Email subject string
        
        Returns:
            Order number or None
        """
        try:
            # Pattern: Order #SP1909467 confirmed (with or without Fwd: prefix)
            match = re.search(r'Order\s+#SP(\d+)', subject, re.IGNORECASE)
            if match:
                order_number = match.group(1)
                logger.debug(f"Found Shoe Palace order number in subject: {order_number}")
                return order_number
            
            return None
        
        except Exception as e:
            logger.error(f"Error extracting Shoe Palace order number: {e}")
            return None
    
    def _extract_order_number_from_body(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract order number from Shoe Palace email body as fallback.
        
        Body format: Order Number #1879967
        Extract: 1879967
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            Order number or None
        """
        try:
            text = soup.get_text()
            
            # Pattern: Order Number #1879967 (without SP prefix in body)
            match = re.search(r'Order\s+Number\s+#(\d+)', text, re.IGNORECASE)
            if match:
                order_number = match.group(1)
                logger.debug(f"Found Shoe Palace order number in body: {order_number}")
                return order_number
            
            return None
        
        except Exception as e:
            logger.error(f"Error extracting Shoe Palace order number from body: {e}")
            return None
    
    def _extract_cancellation_order_number(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract order number from Shoe Palace cancellation email.
        
        Format: "Order #: SP1893166" (with SP prefix)
        Extract: SP1893166 (keep SP prefix for cancellation emails)
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            Order number with SP prefix or None
        """
        try:
            text = soup.get_text()
            
            # Pattern: Order #: SP1893166 (with SP prefix)
            match = re.search(r'Order\s+#:\s*(SP\d+)', text, re.IGNORECASE)
            if match:
                order_number = match.group(1).upper()  # Ensure SP is uppercase
                logger.debug(f"Found Shoe Palace cancellation order number: {order_number}")
                return order_number
            
            # Fallback: Look for SP followed by digits anywhere
            match = re.search(r'\b(SP\d+)\b', text, re.IGNORECASE)
            if match:
                order_number = match.group(1).upper()
                logger.debug(f"Found Shoe Palace cancellation order number (fallback): {order_number}")
                return order_number
            
            return None
        
        except Exception as e:
            logger.error(f"Error extracting Shoe Palace cancellation order number: {e}")
            return None

    def _extract_items(self, soup: BeautifulSoup) -> List[ShoepalaceOrderItem]:
        """
        Extract order items from Shoe Palace email.
        
        Shoe Palace email structure:
        - Product name with color and size: "Air Jordan Collectors Duffle Bag Mens Bag (Black) - OS"
        - Quantity: "Quantitiy : 5"
        - Product image from Shopify CDN (e.g., 28e1a2ea4696547d42555eb7e9f28109_1024x1024.jpg)
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            List of ShoepalaceOrderItem objects
        """
        items = []
        processed_products = set()  # Track processed products to avoid duplicates
        
        try:
            # Find all product images first
            all_imgs = soup.find_all('img')
            
            for img in all_imgs:
                try:
                    src = img.get('src', '')
                    
                    # Check if this is a product image (not logo, banner, or social icons)
                    if not ('cdn.shopify.com/s/files/1/0852/3376/files/' in src):
                        continue
                    
                    # Exclude non-product images
                    if any(x in src.lower() for x in ['logo', 'icon', 'fb.png', 'tw.png', 'in.png', 'pi.png', 'preview-full', 'sp_stacked']):
                        continue
                    
                    # Must be a product image (has hash-like filename with _1024x1024.jpg)
                    if '_1024x1024.jpg' not in src:
                        continue
                    
                    logger.debug(f"Found product image: {src}")
                    
                    # Find the parent row containing this image
                    current = img
                    product_row = None
                    while current:
                        if current.name == 'tr':
                            product_row = current
                            break
                        current = current.parent
                    
                    if not product_row:
                        logger.warning(f"Could not find parent row for image: {src}")
                        continue
                    
                    # Extract product details from this row
                    product_details = self._extract_shoepalace_product_details(product_row)
                    
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
                            items.append(ShoepalaceOrderItem(
                                unique_id=unique_id,
                                size=self._clean_size(size),
                                quantity=quantity,
                                product_name=product_name
                            ))
                            processed_products.add(product_key)
                            logger.info(
                                f"Extracted Shoe Palace item: {product_name} | "
                                f"unique_id={unique_id}, Size={size}, Qty={quantity}"
                            )
                        else:
                            logger.warning(
                                f"Invalid or missing data: "
                                f"unique_id={unique_id}, size={size}, product_name={product_name}"
                            )
                
                except Exception as e:
                    logger.error(f"Error processing Shoe Palace product image: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error extracting Shoe Palace items: {e}", exc_info=True)
        
        # Log items with ID, size, and quantity (product names come from OA Sourcing table)
        if items:
            items_summary = [f"(ID: {item.unique_id}, Size: {item.size}, Qty: {item.quantity})" for item in items]
            logger.info(f"[Shoe Palace] Extracted {len(items)} items: {', '.join(items_summary)}")
        return items

    def _extract_shoepalace_product_details(self, row) -> Optional[dict]:
        """
        Extract product details from a Shoe Palace product row.
        
        Expected format:
        - Product name: "Air Jordan Collectors Duffle Bag Mens Bag (Black) - OS"
        - Quantity: "Quantitiy : 5"
        
        Returns:
            Dictionary with unique_id, size, quantity, product_name or None
        """
        try:
            details = {}
            row_text = row.get_text()
            
            # Find product name - look for td with Josefin Sans font, size 18px
            # Handle variations: "font-size:18px" (no space) or "font-size: 18px" (with space)
            product_cells = row.find_all('td', style=lambda x: x and 'Josefin Sans' in x and ('font-size:18px' in x or 'font-size: 18px' in x))
            
            if product_cells:
                product_name_td = product_cells[0]
                full_product_name = product_name_td.get_text(strip=True)
                # Clean up extra whitespace and newlines
                full_product_name = re.sub(r'\s+', ' ', full_product_name).strip()
                logger.debug(f"Found product name: {full_product_name}")
                
                # Parse product name to extract size and create unique_id
                # Format: "Product Name (Color) - Size" or "Product Name - Size"
                # Examples:
                # - "Air Jordan Collectors Duffle Bag Mens Bag (Black) - OS"
                # - "Clifton 9 Mens Running Shoes (Black) Final Sale - 10"
                
                size = None
                product_base_name = full_product_name
                
                # Extract size (after the last dash)
                if ' - ' in full_product_name:
                    parts = full_product_name.rsplit(' - ', 1)
                    if len(parts) == 2:
                        product_base_name = parts[0].strip()
                        size = parts[1].strip()
                        logger.debug(f"Extracted size: {size}")
                
                # Create unique_id from product name by slugifying
                # Format: "Samba OG Mens Lifestyle Shoes (Shadow Green/White/Gold)" 
                # -> "samba-og-mens-lifestyle-shoes-shadow-green-white-gold"
                
                # Start with the base product name
                product_for_slug = product_base_name
                
                # Remove "Final Sale" text
                product_for_slug = product_for_slug.replace(' Final Sale', '').strip()
                
                # Extract and append color if present in parentheses
                # Format: "Product Name (Color)" -> "Product Name Color"
                if '(' in product_for_slug and ')' in product_for_slug:
                    # Extract the part before parentheses and the color inside
                    match = re.match(r'(.*?)\s*\(([^)]+)\)\s*$', product_for_slug)
                    if match:
                        base_part = match.group(1).strip()
                        color_part = match.group(2).strip()
                        # Replace / with spaces in color, then combine
                        color_part = color_part.replace('/', ' ')
                        product_for_slug = f"{base_part} {color_part}"
                
                # Convert to slug: lowercase, replace spaces with hyphens, remove special chars
                unique_id = product_for_slug.lower()
                unique_id = re.sub(r'[^\w\s-]', '', unique_id)  # Remove special chars except hyphen
                unique_id = re.sub(r'\s+', '-', unique_id)  # Replace spaces with hyphens
                unique_id = re.sub(r'-+', '-', unique_id)  # Replace multiple hyphens with single
                unique_id = unique_id.strip('-')  # Remove leading/trailing hyphens
                
                logger.debug(f"Created unique_id: {unique_id}")
                
                details['product_name'] = product_base_name
                details['unique_id'] = unique_id
                details['size'] = size
                
                # Extract quantity from the same nested table that contains the product name
                # The quantity is in a sibling <tr> within the nested table
                # Structure: <td width="250"> -> <table> -> <tr> (product name) -> <tr> (quantity)
                # Find the parent <tr> of the product name td, then find the table that contains it
                product_name_tr = product_name_td.find_parent('tr')
                if product_name_tr:
                    # Find the parent <td> (should be width="250"), then find the table within it
                    # This ensures we get the correct nested table
                    parent_td = product_name_tr.find_parent('td')
                    if parent_td:
                        # Find the table within this td (the nested table)
                        product_table = parent_td.find('table')
                    else:
                        # Fallback: find parent table directly
                        product_table = product_name_tr.find_parent('table')
                    
                    if product_table:
                        # Look for the quantity td in a sibling <tr> within this table
                        # Find all <tr> elements in this table
                        table_rows = product_table.find_all('tr')
                        quantity_found = False
                        for tr in table_rows:
                            # Skip the row containing the product name
                            if tr == product_name_tr:
                                continue
                            # Check if this row contains the quantity
                            quantity_tds = tr.find_all('td')
                            for td in quantity_tds:
                                td_text = td.get_text(strip=True)
                                quantity_match = re.search(r'Quantit[iy]\s*:\s*(\d+)', td_text, re.IGNORECASE)
                                if quantity_match:
                                    quantity = int(quantity_match.group(1))
                                    details['quantity'] = quantity
                                    logger.debug(f"Found quantity in product table: {quantity}")
                                    quantity_found = True
                                    break
                            if quantity_found:
                                break
                        
                        # If quantity not found in the nested table, try searching table text
                        if not quantity_found:
                            table_text = product_table.get_text()
                            quantity_match = re.search(r'Quantit[iy]\s*:\s*(\d+)', table_text, re.IGNORECASE)
                            if quantity_match:
                                quantity = int(quantity_match.group(1))
                                details['quantity'] = quantity
                                logger.debug(f"Found quantity in product table text: {quantity}")
                            else:
                                # Fallback: search in the entire row
                                quantity_match = re.search(r'Quantit[iy]\s*:\s*(\d+)', row_text, re.IGNORECASE)
                                if quantity_match:
                                    quantity = int(quantity_match.group(1))
                                    details['quantity'] = quantity
                                    logger.debug(f"Found quantity in row: {quantity}")
                                else:
                                    details['quantity'] = 1
                                    logger.debug("Quantity not found, defaulting to 1")
                    else:
                        # Fallback: search in the entire row
                        quantity_match = re.search(r'Quantit[iy]\s*:\s*(\d+)', row_text, re.IGNORECASE)
                        if quantity_match:
                            quantity = int(quantity_match.group(1))
                            details['quantity'] = quantity
                            logger.debug(f"Found quantity in row: {quantity}")
                        else:
                            details['quantity'] = 1
                            logger.debug("Quantity not found, defaulting to 1")
                else:
                    # Fallback: search in the entire row
                    quantity_match = re.search(r'Quantit[iy]\s*:\s*(\d+)', row_text, re.IGNORECASE)
                    if quantity_match:
                        quantity = int(quantity_match.group(1))
                        details['quantity'] = quantity
                        logger.debug(f"Found quantity in row: {quantity}")
                    else:
                        details['quantity'] = 1
                        logger.debug("Quantity not found, defaulting to 1")
            else:
                # No product name found, can't extract
                return None
            
            # Return only if we have the essential fields
            if details.get('unique_id') and details.get('size'):
                return details
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting Shoe Palace product details: {e}", exc_info=True)
            return None

    def _is_valid_size(self, size: str) -> bool:
        """Validate if size is valid"""
        if not size:
            return False
        # Accept numeric sizes (10, 10.5), letter sizes (M, XL), or special sizes (OS)
        return bool(
            re.match(r'^\d+(\.\d+)?$', size) or  # Numeric: 10, 10.5
            re.match(r'^[A-Z]{1,3}$', size.upper()) or  # Letter: M, XL
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
        
        Shoe Palace email structure:
        - "Shipping Address" header
        - Street address (e.g., "595 Lloyd Ln")
        - City, state, zip
        
        We want to extract just the street address part and normalize it.
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            Normalized shipping address or empty string
        """
        try:
            text = soup.get_text()
            
            # Method 1: Look for "Shipping Address" section and extract street address
            shipping_match = re.search(
                r'Shipping\s+Address\s*(.*?)(?:Shipping\s+Method|Billing|Payment|Order|$)',
                text,
                re.IGNORECASE | re.DOTALL
            )
            
            if shipping_match:
                address_section = shipping_match.group(1).strip()
                # Split into lines
                lines = [line.strip() for line in address_section.split('\n') if line.strip()]
                
                # Look for street address pattern (number + street name)
                for line in lines:
                    # Skip name lines, phone lines, and price lines
                    if re.match(r'^\d+', line):  # Starts with number
                        if not re.search(r'\d{3}-\d{3}-\d{4}', line):  # Not a phone number
                            if not re.search(r'\$\d+', line):  # Not a price
                                # Check if it contains street indicators
                                if re.search(r'\b(LN|Lane|AVE|Ave|Avenue|Street|St|Road|Rd|Drive|Dr|Boulevard|Blvd)\b', line, re.IGNORECASE):
                                    # Extract just the street address part (before city/state/zip)
                                    parts = line.split(',')
                                    street_line = parts[0].strip() if parts else line.strip()
                                    
                                    # Remove city/state/zip pattern if present
                                    city_state_match = re.search(r',\s*[A-Z][A-Z\s]+,?\s*[A-Z]{2}\s*\d{5}', line)
                                    if city_state_match:
                                        street_line = line[:city_state_match.start()].strip()
                                    
                                    normalized = normalize_shipping_address(street_line)
                                    if normalized:
                                        logger.debug(f"Extracted Shoe Palace shipping address: {line} -> {street_line} -> {normalized}")
                                        return normalized
            
            # Method 2: Direct pattern matching for known addresses
            lloyd_match = re.search(r'(595\s+Lloyd\s+Ln[^,\n]*(?:,\s*[A-Z\s]+)?)', text, re.IGNORECASE)
            if lloyd_match:
                street_line = lloyd_match.group(1).strip()
                street_line = re.sub(r',\s*[A-Z][A-Z\s]+,?\s*[A-Z]{2}\s*\d{5}.*$', '', street_line).strip()
                normalized = normalize_shipping_address(street_line)
                if normalized:
                    logger.debug(f"Extracted Shoe Palace shipping address (pattern): {street_line} -> {normalized}")
                    return normalized
            
            # Method 3: Look for "2025 Vista" pattern
            vista_match = re.search(r'(2025\s+Vista\s+Ave[^,\n]*(?:,\s*[A-Z\s]+)?)', text, re.IGNORECASE)
            if vista_match:
                street_line = vista_match.group(1).strip()
                street_line = re.sub(r',\s*[A-Z][A-Z\s]+,?\s*[A-Z]{2}\s*\d{5}.*$', '', street_line).strip()
                normalized = normalize_shipping_address(street_line)
                if normalized:
                    logger.debug(f"Extracted Shoe Palace shipping address (pattern): {street_line} -> {normalized}")
                    return normalized
            
            return ""
        
        except Exception as e:
            logger.error(f"Error extracting shipping address: {e}")
            return ""
    
    def _extract_cancellation_items(self, soup: BeautifulSoup) -> List[ShoepalaceOrderItem]:
        """
        Extract cancelled items from Shoe Palace cancellation email.
        
        Cancellation email structure:
        - Products are in table rows with ITEM DESCRIPTION, ITEM PRICE, QTY, TOTAL columns
        - Product name format: "1127895-BBLC - CLIFTON 9 BLK/BLK"
        - Size format: "Color=BLK Size=10" (on a new line)
        - QTY column: "1"
        - Unique ID: Extract first part before dash from product name: "1127895"
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            List of ShoepalaceOrderItem objects
        """
        items = []
        
        try:
            # Find the table with ITEM DESCRIPTION header
            # Look for table row with "ITEM DESCRIPTION" text
            header_row = soup.find('tr', string=re.compile(r'ITEM\s+DESCRIPTION', re.IGNORECASE))
            if not header_row:
                # Try finding by td with "ITEM DESCRIPTION"
                header_tds = soup.find_all('td', string=re.compile(r'ITEM\s+DESCRIPTION', re.IGNORECASE))
                if header_tds:
                    header_row = header_tds[0].find_parent('tr')
            
            if not header_row:
                logger.warning("Could not find ITEM DESCRIPTION header in cancellation email")
                # Fallback: find all table rows and look for product patterns
                all_rows = soup.find_all('tr')
                for row in all_rows:
                    row_text = row.get_text()
                    # Check if row contains product name pattern (numbers-dash pattern)
                    if re.search(r'\d+-[A-Z]+', row_text):
                        item = self._extract_cancellation_item_from_row(row)
                        if item:
                            items.append(item)
                # Sum quantities for same unique_id+size
                summed: dict = {}
                for item in items:
                    key = (item.unique_id, item.size)
                    if key not in summed:
                        summed[key] = item
                    else:
                        summed[key].quantity += item.quantity
                return list(summed.values())
            
            # Get all rows after the header row
            all_rows = header_row.find_all_next('tr')
            
            for row in all_rows:
                try:
                    # Skip header rows and separator rows
                    row_text = row.get_text(strip=True)
                    if not row_text or 'ITEM DESCRIPTION' in row_text or 'ITEM PRICE' in row_text or 'QTY' in row_text:
                        continue
                    
                    # Check if this row contains a product (has product name pattern)
                    if not re.search(r'\d+-[A-Z]+', row_text):
                        continue
                    
                    item = self._extract_cancellation_item_from_row(row)
                    if item:
                        items.append(item)
                
                except Exception as e:
                    logger.error(f"Error processing cancellation row: {e}")
                    continue
            
            # Sum quantities for same unique_id+size
            summed: dict = {}
            for item in items:
                key = (item.unique_id, item.size)
                if key not in summed:
                    summed[key] = item
                else:
                    summed[key].quantity += item.quantity
            items = list(summed.values())
            
            # Log items with ID, size, and quantity
            if items:
                items_summary = [f"(ID: {item.unique_id}, Size: {item.size}, Qty: {item.quantity})" for item in items]
                logger.info(f"[Shoe Palace] Extracted {len(items)} cancelled items: {', '.join(items_summary)}")
            
            return items
        
        except Exception as e:
            logger.error(f"Error extracting Shoe Palace cancellation items: {e}", exc_info=True)
            return []
    
    def _extract_cancellation_item_from_row(self, row) -> Optional[ShoepalaceOrderItem]:
        """
        Extract product details from a cancellation email table row.
        
        Row structure:
        - First td (width="400"): Product name "1127895-BBLC - CLIFTON 9 BLK/BLK" and "Color=BLK Size=10"
        - QTY td (width="100"): "1"
        
        Returns:
            ShoepalaceOrderItem object or None
        """
        try:
            # Get all td elements in the row
            tds = row.find_all('td')
            if len(tds) < 3:
                return None
            
            # First td contains product name and size info
            product_td = tds[0]
            product_text = product_td.get_text()
            
            # Extract product name (first line, before <br>)
            product_name = None
            product_lines = [line.strip() for line in product_text.split('\n') if line.strip()]
            
            if product_lines:
                # First line is product name: "1127895-BBLC - CLIFTON 9 BLK/BLK"
                product_name = product_lines[0].strip()
            
            if not product_name:
                return None
            
            # Extract unique ID: first part before dash
            # "1127895-BBLC - CLIFTON 9 BLK/BLK" -> "1127895"
            unique_id = None
            if '-' in product_name:
                unique_id = product_name.split('-')[0].strip()
            else:
                # Fallback: try to extract numbers at the start
                match = re.match(r'^(\d+)', product_name)
                if match:
                    unique_id = match.group(1)
            
            if not unique_id:
                logger.warning(f"Could not extract unique ID from product name: {product_name}")
                return None
            
            # Extract size from "Color=BLK Size=10" pattern
            size = None
            for line in product_lines:
                # Look for "Size=X" pattern
                size_match = re.search(r'Size\s*=\s*([^\s]+)', line, re.IGNORECASE)
                if size_match:
                    size = size_match.group(1).strip()
                    break
            
            if not size:
                logger.warning(f"Could not extract size from: {product_text}")
                return None
            
            # Extract quantity from QTY column (usually 3rd td)
            quantity = 1
            if len(tds) >= 3:
                qty_td = tds[2]  # QTY is typically the 3rd column
                qty_text = qty_td.get_text(strip=True)
                qty_match = re.search(r'(\d+)', qty_text)
                if qty_match:
                    quantity = int(qty_match.group(1))
            
            # Validate size
            if not self._is_valid_size(size):
                logger.warning(f"Invalid size: {size}")
                return None
            
            logger.debug(
                f"Extracted Shoe Palace cancellation item: {product_name} | "
                f"unique_id={unique_id}, Size={size}, Qty={quantity}"
            )
            
            return ShoepalaceOrderItem(
                unique_id=unique_id,
                size=self._clean_size(size),
                quantity=quantity,
                product_name=product_name
            )
        
        except Exception as e:
            logger.error(f"Error extracting cancellation item from row: {e}", exc_info=True)
            return None