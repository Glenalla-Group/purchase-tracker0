"""
Hibbett Email Parser
Parses order confirmation, shipping, and cancellation emails from Hibbett
"""

import re
import logging
from typing import List, Optional
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from app.models.email import EmailData
from app.utils.address_utils import normalize_shipping_address

logger = logging.getLogger(__name__)


class HibbettOrderItem(BaseModel):
    unique_id: str = Field(..., description="Unique identifier for the product (e.g., SKU, style code)")
    size: str = Field(..., description="Size of the product")
    quantity: int = Field(..., description="Quantity of the product")
    product_name: Optional[str] = Field(None, description="Name of the product")
    product_number: Optional[str] = Field(None, description="Product number/SKU")
    color: Optional[str] = Field(None, description="Color of the product")
    price: Optional[float] = Field(None, description="Price per unit")
    
    def __repr__(self):
        if self.product_name and len(self.product_name) > 50:
            product_display = self.product_name[:50] + "..."
        else:
            product_display = self.product_name or "Unknown"
        return f"<HibbettOrderItem(unique_id={self.unique_id}, size={self.size}, qty={self.quantity}, product={product_display})>"


class HibbettOrderData(BaseModel):
    order_number: str = Field(..., description="The order number")
    items: List[HibbettOrderItem] = Field(..., description="List of items in the order")
    items_count: int = Field(0, description="Total number of items in the order")
    shipping_address: str = Field("", description="Normalized shipping address")

    def __init__(self, **data):
        super().__init__(**data)
        self.items_count = len(self.items)


class HibbettShippingData(BaseModel):
    """Represents Hibbett shipping notification data"""
    order_number: str = Field(..., description="Order number")
    items: List[HibbettOrderItem] = Field(..., description="List of shipped items")
    
    def __repr__(self):
        return f"<HibbettShippingData(order={self.order_number}, items={len(self.items)})>"


class HibbettCancellationData(BaseModel):
    """Represents Hibbett cancellation notification data"""
    order_number: str = Field(..., description="Order number")
    items: List[HibbettOrderItem] = Field(..., description="List of cancelled items")
    
    def __repr__(self):
        return f"<HibbettCancellationData(order={self.order_number}, items={len(self.items)})>"


class HibbettEmailParser:
    # Email identification - Order Confirmation (Production)
    HIBBETT_FROM_EMAIL = "hibbett@email.hibbett.com"
    SUBJECT_ORDER_PATTERN = "Confirmation of your Order"
    
    # Email identification - Development (forwarded emails)
    DEV_HIBBETT_ORDER_FROM_EMAIL = "glenallagroupc@gmail.com"
    DEV_SUBJECT_ORDER_PATTERN = r"Fwd:\s*Confirmation of your Order"
    
    # Email identification - Shipping & Cancellation
    SUBJECT_SHIPPING_PATTERN = "Your order has shipped!"
    DEV_SUBJECT_SHIPPING_PATTERN = r"Fwd:\s*Your order has shipped!"
    SUBJECT_CANCELLATION_PATTERN = "Your recent order has been cancelled"
    
    # Development cancellation subject patterns (for forwarded emails)
    DEV_SUBJECT_CANCELLATION_PATTERN = r"(Fwd:\s*)?(Your\s+recent\s+order\s+has\s+been\s+cancell?ed|Your\s+order\s+has\s+been\s+cancel(?:l)?ed)"
    
    def __init__(self):
        """Initialize the Hibbett email parser."""
        from app.config.settings import get_settings
        self.settings = get_settings()
    
    @property
    def order_from_email(self) -> str:
        """Get the appropriate from email address based on environment."""
        if self.settings.is_development:
            return self.DEV_HIBBETT_ORDER_FROM_EMAIL
        return self.HIBBETT_FROM_EMAIL
    
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
            return "Fwd: Confirmation of your Order"
        return "Confirmation of your Order"
    
    @property
    def update_from_email(self) -> str:
        """Get the appropriate from email address for updates (shipping/cancellation) based on environment."""
        if self.settings.is_development:
            return self.DEV_HIBBETT_ORDER_FROM_EMAIL
        return self.HIBBETT_FROM_EMAIL
    
    @property
    def shipping_subject_query(self) -> str:
        """Get the appropriate subject pattern for Gmail shipping queries based on environment."""
        if self.settings.is_development:
            return 'subject:"Fwd: Your order has shipped!"'
        return 'subject:"Your order has shipped!"'
    
    @property
    def cancellation_subject_query(self) -> str:
        """Get the appropriate subject pattern for Gmail cancellation queries based on environment."""
        if self.settings.is_development:
            return 'subject:"Fwd: Your recent order has been cancelled" OR subject:"Fwd: Your order has been cancelled"'
        return 'subject:"Your recent order has been cancelled" OR subject:"Your order has been cancelled"'

    def is_hibbett_email(self, email_data: EmailData) -> bool:
        """Check if email is from Hibbett"""
        sender_lower = email_data.sender.lower()
        
        # In development, check for forwarded emails from dev email address
        # Must also verify content to avoid misclassifying other retailers' forwarded emails
        if self.settings.is_development:
            if self.DEV_HIBBETT_ORDER_FROM_EMAIL.lower() in sender_lower:
                html = (email_data.html_content or "").lower()
                if "hibbett" in html:
                    return True
                return False
        
        # Check for production email address
        if self.HIBBETT_FROM_EMAIL.lower() in sender_lower:
            return True
        
        return False

    def is_order_confirmation_email(self, email_data: EmailData) -> bool:
        """Check if email is an order confirmation"""
        subject_lower = email_data.subject.lower()
        
        # Use environment-aware subject pattern
        if re.search(self.order_subject_pattern, subject_lower, re.IGNORECASE):
            return True
        
        # Also check for the base pattern (for forwarded emails that might have variations)
        if self.SUBJECT_ORDER_PATTERN.lower() in subject_lower:
            return True
        
        return False

    def is_shipping_email(self, email_data: EmailData) -> bool:
        """Check if email is a shipping notification (handles dev Fwd: prefix)"""
        subject_lower = (email_data.subject or "").lower()
        if self.settings.is_development and re.search(self.DEV_SUBJECT_SHIPPING_PATTERN, subject_lower, re.IGNORECASE):
            return True
        return self.SUBJECT_SHIPPING_PATTERN.lower() in subject_lower

    def is_cancellation_email(self, email_data: EmailData) -> bool:
        """Check if email is a cancellation notification"""
        subject_lower = email_data.subject.lower()
        
        # Check subject patterns (handle both "cancelled" and "canceled" spellings)
        cancellation_patterns = [
            "your recent order has been cancelled",
            "your recent order has been canceled",
            "your order has been cancelled",
            "your order has been canceled",
            "order has been cancelled",
            "order has been canceled"
        ]
        
        # Check if subject matches any cancellation pattern
        for pattern in cancellation_patterns:
            if pattern in subject_lower:
                return True
        
        # Check development pattern (for forwarded emails)
        if self.settings.is_development:
            if re.search(self.DEV_SUBJECT_CANCELLATION_PATTERN, subject_lower, re.IGNORECASE):
                return True
        
        # Also check email body content for cancellation indicators
        # This helps when the subject might be different (e.g., forwarded emails)
        if email_data.html_content:
            html_lower = email_data.html_content.lower()
            cancellation_indicators = [
                "your recent order has been cancelled",
                "your order has been cancelled",
                "order has been cancelled",
                "item(s) canceled",
                "item(s) cancelled",
                "we regret to inform you that your order",
                "has been cancelled and you have not been charged"
            ]
            
            for indicator in cancellation_indicators:
                if indicator in html_lower:
                    logger.debug(f"Found cancellation indicator in email body: {indicator}")
                    return True
        
        return False

    def parse_email(self, email_data: EmailData) -> Optional[HibbettOrderData]:
        """
        Parse Hibbett order confirmation email.
        
        Args:
            email_data: EmailData object containing email information
        
        Returns:
            HibbettOrderData object or None if parsing fails
        """
        try:
            html_content = email_data.html_content
            
            if not html_content:
                logger.error("No HTML content in Hibbett email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extract order number
            order_number = self._extract_order_number(soup)
            if not order_number:
                logger.error("Failed to extract order number from Hibbett email")
                return None
            
            logger.info(f"Extracted Hibbett order number: {order_number}")
            
            # Extract items using BeautifulSoup
            items = self._extract_items(soup)
            
            if not items:
                logger.error("Failed to extract any items from Hibbett email")
                return None
            
            logger.info(f"Successfully extracted {len(items)} items from Hibbett order {order_number}")
            for item in items:
                logger.debug(f"  - {item}")
            
            # Extract shipping address
            shipping_address = self._extract_shipping_address(soup)
            if shipping_address:
                logger.info(f"Extracted shipping address: {shipping_address}")
            
            return HibbettOrderData(order_number=order_number, items=items, shipping_address=shipping_address)
        
        except Exception as e:
            logger.error(f"Error parsing Hibbett email: {e}", exc_info=True)
            return None

    def _extract_order_number(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract order number from Hibbett email using BeautifulSoup.
        
        Hibbett structure: Order number is in the subject and also in the email content.
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            Order number or None
        """
        try:
            # Method 1: Look for order number in the email content
            text = soup.get_text()
            # Hibbett order numbers: #0017328512104 or "Order Number: 0017329490547"
            order_match = re.search(r'#(\d{13,15})', text)
            if order_match:
                logger.debug(f"Found Hibbett order number in content: {order_match.group(1)}")
                return order_match.group(1)
            order_match = re.search(r'Order\s+Number[:\s]+(\d{13,15})', text, re.IGNORECASE)
            if order_match:
                logger.debug(f"Found Hibbett order number (Order Number: format): {order_match.group(1)}")
                return order_match.group(1)
            
            # Method 2: Look for order number in links or specific elements
            order_links = soup.find_all('a', href=re.compile(r'hibbett\.com'))
            for link in order_links:
                link_text = link.get_text(strip=True)
                # Check if this looks like an order number (13-15 digits)
                if re.match(r'^\d{13,15}$', link_text):
                    logger.debug(f"Found Hibbett order number in link: {link_text}")
                    return link_text
            
            # Method 3: Look for order number in specific text patterns
            order_elements = soup.find_all(text=re.compile(r'Order\s*#?\s*(\d{13,15})'))
            for element in order_elements:
                match = re.search(r'Order\s*#?\s*(\d{13,15})', element)
                if match:
                    logger.debug(f"Found Hibbett order number in text: {match.group(1)}")
                    return match.group(1)
            
            logger.warning("Order number not found in Hibbett email")
            return None
        
        except Exception as e:
            logger.error(f"Error extracting Hibbett order number: {e}")
            return None

    def _extract_items(self, soup: BeautifulSoup) -> List[HibbettOrderItem]:
        """
        Extract order items from Hibbett email.
        
        Hibbett structure analysis:
        - Product images: classic.cdn.media.amplience.net/i/hibbett/G4461_9107_right/
        - Product names: In table cells with product descriptions
        - Sizes: In <b>SIZE</b>: 13 format
        - Quantities: In <b>QTY</b>: 4 format or table cells
        - Unique IDs: From image URLs (G4461 pattern)
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            List of HibbettOrderItem objects
        """
        items = []
        
        try:
            # Find all product images with Hibbett's specific pattern
            product_images = soup.find_all('img', src=re.compile(r'classic\.cdn\.media\.amplience\.net/i/hibbett/'))
            logger.debug(f"Found {len(product_images)} Hibbett product images")
            
            for img in product_images:
                try:
                    # Extract unique ID from image URL
                    img_src = img.get('src', '')
                    unique_id = self._extract_unique_id_from_hibbett_image(img_src)
                    
                    if not unique_id:
                        logger.warning(f"Could not extract unique ID from image: {img_src}")
                        continue
                    
                    # Find the product container (table row containing this image)
                    product_container = self._find_hibbett_product_container(img)
                    if not product_container:
                        logger.warning(f"Could not find product container for image: {img_src}")
                        continue
                    
                    # Extract product details from the container
                    product_name = self._extract_product_name_from_hibbett_container(product_container)
                    size = self._extract_size_from_hibbett_container(product_container)
                    quantity = self._extract_quantity_from_hibbett_container(product_container)
                    
                    # Validate and create item
                    if size and self._is_valid_size(size):
                        items.append(HibbettOrderItem(
                            unique_id=unique_id,
                            size=self._clean_size(size),
                            quantity=quantity,
                            product_name=product_name
                        ))
                        logger.debug(
                            f"Extracted: {product_name} (unique_id={unique_id}), "
                            f"Size: {size}, Qty: {quantity}"
                        )
                    else:
                        logger.warning(
                            f"Invalid or missing data for {unique_id}: "
                            f"size={size}, product_name={product_name}"
                        )
                
                except Exception as e:
                    logger.error(f"Error processing Hibbett product image: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error extracting Hibbett items: {e}", exc_info=True)
        
        # Log items with ID, size, and quantity (product names come from OA Sourcing table)
        if items:
            items_summary = [f"(ID: {item.unique_id}, Size: {item.size}, Qty: {item.quantity})" for item in items]
            logger.info(f"[Hibbett Sports] Extracted {len(items)} items: {', '.join(items_summary)}")
        return items

    def _extract_unique_id_from_hibbett_image(self, img_src: str) -> Optional[str]:
        """Extract unique ID from Hibbett image URL"""
        try:
            # Hibbett pattern: classic.cdn.media.amplience.net/i/hibbett/G4461_9107_right/
            match = re.search(r'hibbett/([A-Z0-9]+)_', img_src)
            if match:
                return match.group(1)
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting unique ID from Hibbett image: {e}")
            return None

    def _find_hibbett_product_container(self, img) -> Optional[BeautifulSoup]:
        """Find the product container for a given Hibbett image"""
        try:
            # Navigate up to find the table row containing this image
            current = img.parent
            while current:
                if current.name == 'tr':
                    return current
                current = current.parent
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding Hibbett product container: {e}")
            return None

    def _extract_product_name_from_hibbett_container(self, container) -> str:
        """Extract product name from the Hibbett product container - improved version"""
        try:
            # Method 1: Look for links first (usually most reliable)
            links = container.find_all('a')
            for link in links:
                link_text = link.get_text(strip=True)
                if link_text and len(link_text) > 10 and len(link_text) < 200:
                    # Filter out common non-product text
                    skip_texts = ['view', 'details', 'shop now', 'buy now', 'add to cart', 
                                 'track order', 'return', 'exchange', 'view order']
                    if link_text.lower() not in skip_texts:
                        product_name = re.sub(r'\s+', ' ', link_text).strip()
                        # Clean up metadata
                        if 'Product #' in product_name:
                            product_name = product_name.split('Product #')[0].strip()
                        elif 'COLOR:' in product_name:
                            product_name = product_name.split('COLOR:')[0].strip()
                        elif 'Size:' in product_name:
                            product_name = product_name.split('Size:')[0].strip()
                        logger.debug(f"[Hibbett] Found product name from link: {product_name[:50]}")
                        return product_name
            
            # Method 2: Look for product name in table cells
            cells = container.find_all('td')
            for cell in cells:
                text = cell.get_text(strip=True)
                # Look for substantial text (relaxed keyword check)
                if text and len(text) > 15 and len(text) < 300:
                    # Skip obvious non-product text
                    if not re.search(r'^(Size|Qty|Quantity|Price|Total|Subtotal|Order|Shipping|\$)', text, re.IGNORECASE):
                        # Clean up the text
                        product_name = re.sub(r'\s+', ' ', text).strip()
                        
                        # Try to extract just the main product name (before Product # or other metadata)
                        if 'Product #' in product_name:
                            product_name = product_name.split('Product #')[0].strip()
                        elif 'COLOR:' in product_name:
                            product_name = product_name.split('COLOR:')[0].strip()
                        elif 'SIZE:' in product_name:
                            product_name = product_name.split('SIZE:')[0].strip()
                        elif 'QTY:' in product_name:
                            product_name = product_name.split('QTY:')[0].strip()
                        
                        # After cleanup, check if it's still substantial
                        if len(product_name) > 15:
                            logger.debug(f"[Hibbett] Found product name from cell: {product_name[:50]}")
                            return product_name
            
            # Method 3: Look for text in any child elements
            for elem in container.find_all(['span', 'div', 'p', 'td']):
                text = elem.get_text(strip=True)
                if text and 15 < len(text) < 200:
                    # Skip if it looks like size/quantity/price
                    if not re.search(r'^(Size|Qty|Quantity|Price|Total|\$|\d+\.\d+)', text, re.IGNORECASE):
                        product_name = re.sub(r'\s+', ' ', text).strip()
                        # Clean metadata
                        if 'Product #' in product_name:
                            product_name = product_name.split('Product #')[0].strip()
                        if len(product_name) > 15:
                            logger.debug(f"[Hibbett] Found product name from text element: {product_name[:50]}")
                            return product_name
            
            logger.debug(f"[Hibbett] Could not extract product name from container")
            return "Unknown Product"
            
        except Exception as e:
            logger.warning(f"[Hibbett] Error extracting product name: {e}")
            return "Unknown Product"

    def _extract_size_from_hibbett_container(self, container) -> Optional[str]:
        """Extract size from the Hibbett product container"""
        try:
            # Look for SIZE: pattern in the container
            container_text = container.get_text()
            
            # Pattern: SIZE: 13 or <b>SIZE</b>: 13
            match = re.search(r'SIZE[:\s]+(\d+(?:\.\d+)?)', container_text)
            if match:
                return match.group(1)
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting Hibbett size: {e}")
            return None

    def _extract_quantity_from_hibbett_container(self, container) -> int:
        """Extract quantity from the Hibbett product container"""
        try:
            container_text = container.get_text()
            
            # Pattern: QTY: 4 or <b>QTY</b>: 4
            match = re.search(r'QTY[:\s]+(\d+)', container_text)
            if match:
                return int(match.group(1))
            
            # Default to 1 if not specified
            return 1
            
        except Exception as e:
            logger.error(f"Error extracting Hibbett quantity: {e}")
            return 1


    def _is_valid_size(self, size: str) -> bool:
        """Validate if size is valid"""
        return bool(re.match(r'^\d+(\.\d+)?$', size))

    def _is_valid_quantity(self, quantity: str) -> bool:
        """Validate if quantity is valid"""
        return quantity.isdigit() and int(quantity) > 0

    def _clean_size(self, size: str) -> str:
        """Clean size string"""
        return size.replace('.0', '') if size.endswith('.0') else size

    def parse_shipping_email(self, email_data: EmailData) -> Optional[HibbettShippingData]:
        """
        Parse Hibbett shipping notification email.
        
        IMPORTANT: Hibbett shipping emails show incorrect quantities - they display
        the order total quantity but only ship 1 item. We determine actual quantity
        by comparing Cost Summary subtotal to price per unit.
        
        Args:
            email_data: EmailData object containing email information
        
        Returns:
            HibbettShippingData object or None if parsing fails
        """
        try:
            html_content = email_data.html_content
            
            if not html_content:
                logger.error("No HTML content in Hibbett shipping email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extract order number
            order_number = self._extract_order_number(soup)
            if not order_number:
                logger.error("Failed to extract order number from Hibbett shipping email")
                return None
            
            logger.info(f"Extracted Hibbett shipping - Order: {order_number}")
            
            # Extract items (with quantity correction for shipping emails)
            items = self._extract_shipping_items(soup)
            
            if not items:
                logger.error("Failed to extract any items from Hibbett shipping email")
                return None
            
            logger.info(f"Successfully extracted {len(items)} items from Hibbett shipping notification")
            for item in items:
                logger.debug(f"  - {item}")
            
            return HibbettShippingData(
                order_number=order_number,
                items=items
            )
        
        except Exception as e:
            logger.error(f"Error parsing Hibbett shipping email: {e}", exc_info=True)
            return None

    def parse_shipping_email_partial(self, email_data: EmailData) -> Optional[dict]:
        """
        Best-effort parse for Hibbett shipping when full parse fails or when email lacks
        unique_id/size (no product images with style code in shipping emails).
        Returns partial data for manual review queue.
        Shipping emails have Product #, product name, color, quantity - but NO Size, NO unique_id.
        """
        try:
            html_content = email_data.html_content
            if not html_content:
                return None
            soup = BeautifulSoup(html_content, 'lxml')
            order_number = self._extract_order_number(soup)
            if not order_number:
                return None
            items = self._extract_shipping_items_partial(soup)
            if not items:
                return None
            return {
                'order_number': order_number,
                'items': items,
                'missing_fields': ['unique_id', 'size'],
                'subject': email_data.subject or '',
            }
        except Exception as e:
            logger.error(f"Error in parse_shipping_email_partial: {e}", exc_info=True)
            return None

    def _extract_shipping_items_partial(self, soup: BeautifulSoup) -> List[dict]:
        """
        Extract shipping items without unique_id/size for manual review.
        Uses Cost Summary subtotal and PRICE to calculate actual quantity (displayed qty may be wrong).
        """
        items = []
        try:
            subtotal = self._extract_cost_summary_subtotal(soup)
            sections = self._find_shipping_product_sections(soup)
            for section in sections:
                try:
                    product_name = self._extract_product_name_from_shipping_section(section)
                    product_number = self._extract_product_number_from_shipping_section(section)
                    color = self._extract_color_from_shipping_section(section)
                    price_per_unit = self._extract_price_from_shipping_section(section)
                    displayed_quantity = self._extract_quantity_from_shipping_section(section)
                    if not price_per_unit and subtotal:
                        price_per_unit = subtotal
                    actual_quantity = 1
                    if price_per_unit and subtotal:
                        calculated_qty = round(subtotal / price_per_unit)
                        if calculated_qty > 0:
                            actual_quantity = calculated_qty
                    elif subtotal:
                        actual_quantity = 1
                    else:
                        actual_quantity = displayed_quantity
                    if product_name and product_name != "Unknown Product":
                        items.append({
                            'product_name': product_name,
                            'product_number': product_number,
                            'color': color,
                            'quantity': actual_quantity,
                        })
                except Exception as e:
                    logger.debug(f"Skip section in partial extract: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error in _extract_shipping_items_partial: {e}")
        return items

    def parse_cancellation_email(self, email_data: EmailData) -> Optional[HibbettCancellationData]:
        """
        Parse Hibbett cancellation notification email.
        
        Args:
            email_data: EmailData object containing email information
        
        Returns:
            HibbettCancellationData object or None if parsing fails
        """
        try:
            html_content = email_data.html_content
            
            if not html_content:
                logger.error("No HTML content in Hibbett cancellation email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extract order number
            order_number = self._extract_order_number(soup)
            if not order_number:
                logger.error("Failed to extract order number from Hibbett cancellation email")
                return None
            
            logger.info(f"Extracted Hibbett cancellation - Order: {order_number}")
            
            # Extract items using cancellation-specific extraction
            items = self._extract_cancellation_items(soup)
            
            if not items:
                logger.error("Failed to extract any items from Hibbett cancellation email")
                return None
            
            logger.info(f"Successfully extracted {len(items)} items from Hibbett cancellation notification")
            for item in items:
                logger.debug(f"  - {item}")
            
            return HibbettCancellationData(
                order_number=order_number,
                items=items
            )
        
        except Exception as e:
            logger.error(f"Error parsing Hibbett cancellation email: {e}", exc_info=True)
            return None

    def _extract_shipping_items(self, soup: BeautifulSoup) -> List[HibbettOrderItem]:
        """
        Extract shipping items from Hibbett shipping email.
        
        IMPORTANT: Hibbett shipping emails show incorrect quantities. We need to:
        1. Extract displayed quantity (may be wrong)
        2. Extract Cost Summary subtotal
        3. Extract price per unit from product details
        4. Calculate actual quantity: subtotal / price_per_unit
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            List of HibbettOrderItem objects with corrected quantities
        """
        items = []
        
        try:
            # Extract Cost Summary subtotal first
            subtotal = self._extract_cost_summary_subtotal(soup)
            logger.debug(f"Extracted Cost Summary subtotal: ${subtotal}")
            
            # Find product description section (PRODUCT DESCRIPTION column)
            # Look for the table structure with product details
            product_sections = self._find_shipping_product_sections(soup)
            
            for section in product_sections:
                try:
                    # Extract product details
                    product_name = self._extract_product_name_from_shipping_section(section)
                    product_number = self._extract_product_number_from_shipping_section(section)
                    color = self._extract_color_from_shipping_section(section)
                    size = self._extract_size_from_shipping_section(section)
                    displayed_quantity = self._extract_quantity_from_shipping_section(section)
                    price_per_unit = self._extract_price_from_shipping_section(section)
                    
                    # If we couldn't extract price from PRICE column, use subtotal as PPU
                    # (This handles the case where only 1 item is shipped)
                    if not price_per_unit and subtotal:
                        price_per_unit = subtotal
                        logger.debug(f"Using subtotal ${subtotal} as price per unit (only 1 item shipped)")
                    
                    # Calculate actual quantity from Cost Summary
                    # If subtotal matches price_per_unit, actual quantity is 1
                    actual_quantity = 1
                    if price_per_unit and subtotal:
                        # Calculate quantity: subtotal / price_per_unit
                        calculated_qty = round(subtotal / price_per_unit)
                        if calculated_qty > 0:
                            actual_quantity = calculated_qty
                        logger.debug(
                            f"Quantity correction: Displayed={displayed_quantity}, "
                            f"Actual={actual_quantity} (Subtotal=${subtotal}, PPU=${price_per_unit})"
                        )
                    elif subtotal:
                        # If we have subtotal but no PPU, assume quantity is 1
                        logger.debug(f"Using default quantity=1 (Subtotal=${subtotal}, no PPU found)")
                    
                    # Extract unique ID from product number or generate from product name
                    unique_id = product_number or self._generate_unique_id_from_product_name(product_name)
                    
                    # Size is required for matching - use placeholder when missing (processor will match by unique_id)
                    if not size or not self._is_valid_size(size):
                        if product_number and product_name != "Unknown Product":
                            size = "0"  # Placeholder when missing; processor matches by order_number + unique_id
                            logger.debug(
                                f"Size missing in shipping email, using placeholder for matching by unique_id: {unique_id}"
                            )
                        else:
                            logger.warning(
                                f"Invalid or missing data: size={size}, product_name={product_name}"
                            )
                            continue
                    
                    if size and self._is_valid_size(size):
                        items.append(HibbettOrderItem(
                            unique_id=unique_id,
                            size=self._clean_size(size),
                            quantity=actual_quantity,
                            product_name=product_name,
                            product_number=product_number,
                            color=color,
                            price=price_per_unit
                        ))
                        logger.debug(
                            f"Extracted shipping item: {product_name} (unique_id={unique_id}), "
                            f"Size: {size}, Qty: {actual_quantity} (was {displayed_quantity})"
                        )
                
                except Exception as e:
                    logger.error(f"Error processing shipping product section: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error extracting shipping items: {e}", exc_info=True)
        
        # Deduplicate by unique_id + size (same product can appear in multiple section matches)
        seen = set()
        deduped = []
        for item in items:
            key = (item.unique_id, item.size)
            if key not in seen:
                seen.add(key)
                deduped.append(item)
            else:
                logger.debug(f"Skipping duplicate shipping item: {item.unique_id} size={item.size}")
        
        return deduped

    def _extract_cancellation_items(self, soup: BeautifulSoup) -> List[HibbettOrderItem]:
        """
        Extract cancellation items from Hibbett cancellation email.
        
        Cancellation emails have a table structure with PRODUCT, QTY, and PRICE columns.
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            List of HibbettOrderItem objects
        """
        items = []
        
        try:
            # Find the cancellation items table
            # Look for table rows with product information
            # The structure has PRODUCT, QTY, PRICE columns
            
            # Find all product rows in the cancellation table
            product_rows = self._find_cancellation_product_rows(soup)
            
            for row in product_rows:
                try:
                    # Extract product details from the row
                    product_name = self._extract_product_name_from_cancellation_row(row)
                    product_number = self._extract_product_number_from_cancellation_row(row)
                    color = self._extract_color_from_cancellation_row(row)
                    size = self._extract_size_from_cancellation_row(row)
                    quantity = self._extract_quantity_from_cancellation_row(row)
                    price = self._extract_price_from_cancellation_row(row)
                    
                    # Extract unique ID from image link only (same as order confirmation)
                    unique_id = self._extract_unique_id_from_cancellation_row(row)
                    if not unique_id:
                        logger.warning(
                            f"Skipping cancellation item: no unique_id from image "
                            f"(product_name={product_name}, size={size})"
                        )
                        continue
                    
                    if size and self._is_valid_size(size) and quantity:
                        items.append(HibbettOrderItem(
                            unique_id=unique_id,
                            size=self._clean_size(size),
                            quantity=quantity,
                            product_name=product_name,
                            product_number=product_number,
                            color=color,
                            price=price
                        ))
                        logger.debug(
                            f"Extracted cancellation item: {product_name} (unique_id={unique_id}), "
                            f"Size: {size}, Qty: {quantity}"
                        )
                    else:
                        logger.warning(
                            f"Invalid or missing data: size={size}, qty={quantity}, "
                            f"product_name={product_name}"
                        )
                
                except Exception as e:
                    logger.error(f"Error processing cancellation product row: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error extracting cancellation items: {e}", exc_info=True)
        
        return items

    def _extract_cost_summary_subtotal(self, soup: BeautifulSoup) -> Optional[float]:
        """Extract subtotal from Cost Summary section"""
        try:
            # Look for "COST SUMMARY" section
            # Then find "Subtotal: $XX.XX" pattern
            text = soup.get_text()
            
            # Pattern: "Subtotal: $40.49" or "Subtotal:$40.49"
            match = re.search(r'Subtotal[:\s]+\$?([\d,]+\.?\d*)', text, re.IGNORECASE)
            if match:
                subtotal_str = match.group(1).replace(',', '')
                return float(subtotal_str)
            
            return None
        
        except Exception as e:
            logger.error(f"Error extracting Cost Summary subtotal: {e}")
            return None

    def _find_shipping_product_sections(self, soup: BeautifulSoup) -> List:
        """Find product description sections in shipping email"""
        sections = []
        
        try:
            # Look for "PRODUCT DESCRIPTION" header
            # Then find the table cells containing product information
            product_desc_headers = soup.find_all(string=re.compile(r'PRODUCT\s+DESCRIPTION', re.IGNORECASE))
            
            for header in product_desc_headers:
                # Find the parent table structure
                parent_table = header.find_parent('table')
                if parent_table:
                    # Find all product rows (skip header row)
                    rows = parent_table.find_all('tr')
                    for row in rows:
                        # Check if this row contains product information
                        if self._is_shipping_product_row(row):
                            sections.append(row)
            
            # Fallback: Look for product information directly
            if not sections:
                # Look for cells containing product names and details
                cells = soup.find_all('td')
                for cell in cells:
                    cell_text = cell.get_text()
                    if 'Product #' in cell_text and 'Quantity:' in cell_text:
                        sections.append(cell)
        
        except Exception as e:
            logger.error(f"Error finding shipping product sections: {e}")
        
        return sections

    def _is_shipping_product_row(self, row) -> bool:
        """Check if a table row contains product information"""
        try:
            text = row.get_text()
            return 'Product #' in text and ('Quantity:' in text or 'Size' in text)
        except:
            return False

    def _extract_product_name_from_shipping_section(self, section) -> str:
        """Extract product name from shipping section"""
        try:
            text = section.get_text()
            # Product name is usually before "Product #"
            if 'Product #' in text:
                parts = text.split('Product #')
                if parts and parts[0].strip():
                    name = parts[0].strip()
                    # Skip header/generic text - must be substantial product name
                    skip_patterns = ['PRODUCT DESCRIPTION', 'Thank you for your order', 'View in']
                    if any(name.upper().startswith(p.upper()) for p in skip_patterns):
                        return "Unknown Product"
                    if len(name) > 10 and 'browser' not in name.lower():
                        return name
            return "Unknown Product"
        except Exception:
            return "Unknown Product"

    def _extract_product_number_from_shipping_section(self, section) -> Optional[str]:
        """Extract product number from shipping section"""
        try:
            text = section.get_text()
            match = re.search(r'Product\s*#\s*:?\s*(\d+)', text, re.IGNORECASE)
            if match:
                return match.group(1)
            return None
        except:
            return None

    def _extract_color_from_shipping_section(self, section) -> Optional[str]:
        """Extract color from shipping section"""
        try:
            text = section.get_text()
            match = re.search(r'Color[:\s]+([^\n\r]+)', text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
            return None
        except:
            return None

    def _extract_size_from_shipping_section(self, section) -> Optional[str]:
        """Extract size from shipping section"""
        try:
            text = section.get_text()
            # Primary pattern: Size: 10 or SIZE: 10.5
            match = re.search(r'Size[:\s]+(\d+(?:\.\d+)?)', text, re.IGNORECASE)
            if match:
                return match.group(1)
            # Fallback: Size may appear in product context e.g. "Men's 10" or "Size 10"
            match = re.search(r'(?:Size|Men\'?s?|Women\'?s?|Youth)\s+(?:Shoe\s+)?(\d+(?:\.\d+)?)\b', text, re.IGNORECASE)
            if match:
                return match.group(1)
            # Fallback: Look in parent row for Size (some layouts put it in sibling cell)
            parent_row = section if section.name == 'tr' else section.find_parent('tr')
            if parent_row:
                row_text = parent_row.get_text()
                match = re.search(r'Size[:\s]+(\d+(?:\.\d+)?)', row_text, re.IGNORECASE)
                if match:
                    return match.group(1)
            return None
        except Exception:
            return None

    def _extract_quantity_from_shipping_section(self, section) -> int:
        """Extract displayed quantity from shipping section (may be incorrect)"""
        try:
            text = section.get_text()
            match = re.search(r'Quantity[:\s]+(\d+)', text, re.IGNORECASE)
            if match:
                return int(match.group(1))
            return 1
        except:
            return 1

    def _extract_price_from_shipping_section(self, section) -> Optional[float]:
        """Extract price per unit from shipping section"""
        try:
            # Look for price in the PRICE column
            # The price is typically in a separate cell or table structure
            # Try to find the PRICE column value
            
            # Method 1: Look for price in the same row structure
            # Find parent table and look for PRICE column
            parent_table = section.find_parent('table')
            if parent_table:
                # Look for cells containing price values
                cells = parent_table.find_all(['td', 'th'])
                for cell in cells:
                    cell_text = cell.get_text(strip=True)
                    # Look for price pattern: "$40.49"
                    match = re.search(r'^\$?\s*([\d,]+\.?\d*)$', cell_text)
                    if match:
                        price_str = match.group(1).replace(',', '')
                        try:
                            price = float(price_str)
                            # Validate it's a reasonable price (not too high)
                            if 10 <= price <= 1000:
                                return price
                        except:
                            pass
            
            # Method 2: Extract from text directly
            text = section.get_text()
            # Look for price patterns, but be more specific
            # Pattern: "$40.49" (standalone price, not part of subtotal)
            matches = re.findall(r'\$?\s*([\d,]+\.?\d*)', text)
            for match_str in matches:
                try:
                    price_str = match_str.replace(',', '')
                    price = float(price_str)
                    # Validate it's a reasonable price (not too high)
                    if 10 <= price <= 1000:
                        return price
                except:
                    continue
            
            return None
        except:
            return None

    def _find_cancellation_product_rows(self, soup: BeautifulSoup) -> List:
        """Find product rows in cancellation email"""
        rows = []
        
        try:
            # Look for "ITEM(S) CANCELED" header
            # Then find the table with product information
            canceled_headers = soup.find_all(string=re.compile(r'ITEM\(S\)\s+CANCELED', re.IGNORECASE))
            
            for header in canceled_headers:
                # Find the parent table
                parent_table = header.find_parent('table')
                if parent_table:
                    # Find all rows with product information
                    all_rows = parent_table.find_all('tr')
                    for row in all_rows:
                        # Check if this row contains product information (has product image or product name)
                        if self._is_cancellation_product_row(row):
                            rows.append(row)
            
            # Fallback: Look for rows with product images
            if not rows:
                product_images = soup.find_all('img', src=re.compile(r'classic\.cdn\.media\.amplience\.net/i/hibbett/'))
                for img in product_images:
                    row = img.find_parent('tr')
                    if row and row not in rows:
                        rows.append(row)
        
        except Exception as e:
            logger.error(f"Error finding cancellation product rows: {e}")
        
        return rows

    def _is_cancellation_product_row(self, row) -> bool:
        """Check if a table row contains cancellation product information"""
        try:
            # Check if row has product image or product name
            has_image = row.find('img', src=re.compile(r'classic\.cdn\.media\.amplience\.net/i/hibbett/'))
            text = row.get_text()
            has_product_info = 'Product #' in text and ('SIZE' in text or 'Size' in text)
            return bool(has_image or has_product_info)
        except:
            return False

    def _extract_unique_id_from_cancellation_row(self, row) -> Optional[str]:
        """Extract unique ID from Hibbett product image in cancellation row (same as order confirmation)"""
        try:
            img = row.find('img', src=re.compile(r'classic\.cdn\.media\.amplience\.net/i/hibbett/'))
            if img:
                img_src = img.get('src', '')
                return self._extract_unique_id_from_hibbett_image(img_src)
            return None
        except Exception as e:
            logger.debug(f"Error extracting unique ID from cancellation row image: {e}")
            return None

    def _extract_product_name_from_cancellation_row(self, row) -> str:
        """Extract product name from cancellation row"""
        try:
            # Product name is in the first <td> (PRODUCT column) in a nested table
            # The structure: <td width="400"> contains nested table with product details
            cells = row.find_all('td')
            
            # The first <td> contains the product details in a nested table
            if cells:
                first_cell = cells[0]
                
                # Look for product name in nested table cells
                nested_cells = first_cell.find_all('td')
                for cell in nested_cells:
                    text = cell.get_text(strip=True)
                    # Product name is the first substantial text that's not metadata
                    if text and len(text) > 15:
                        text_lower = text.lower()
                        # Skip metadata keywords
                        metadata_keywords = ['product #', 'size', 'color', 'qty', 'quantity', 'price', '$']
                        if not any(keyword in text_lower for keyword in metadata_keywords):
                            # Skip if it's just a number
                            if not re.match(r'^[\d.,$]+$', text):
                                # This looks like a product name
                                logger.debug(f"Found product name: {text[:50]}")
                                return text
            
            # Fallback: Look for product name in any cell that contains "Product #"
            for cell in cells:
                text = cell.get_text(strip=True)
                if text and len(text) > 10 and 'Product #' in text:
                    # Extract product name (before "Product #")
                    parts = text.split('Product #')
                    if parts and parts[0].strip():
                        product_name = parts[0].strip()
                        logger.debug(f"Found product name from Product # cell: {product_name[:50]}")
                        return product_name
            
            logger.warning("Could not extract product name from cancellation row")
            return "Unknown Product"
        except Exception as e:
            logger.error(f"Error extracting product name: {e}")
            return "Unknown Product"

    def _extract_product_number_from_cancellation_row(self, row) -> Optional[str]:
        """Extract product number from cancellation row"""
        try:
            text = row.get_text()
            match = re.search(r'Product\s*#\s*(\d+)', text, re.IGNORECASE)
            if match:
                return match.group(1)
            return None
        except:
            return None

    def _extract_color_from_cancellation_row(self, row) -> Optional[str]:
        """Extract color from cancellation row"""
        try:
            text = row.get_text()
            match = re.search(r'COLOR[:\s]+([^\n\r]+)', text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
            return None
        except:
            return None

    def _extract_size_from_cancellation_row(self, row) -> Optional[str]:
        """Extract size from cancellation row"""
        try:
            text = row.get_text()
            match = re.search(r'SIZE[:\s]+(\d+(?:\.\d+)?)', text, re.IGNORECASE)
            if match:
                return match.group(1)
            return None
        except:
            return None

    def _extract_quantity_from_cancellation_row(self, row) -> int:
        """Extract quantity from cancellation row"""
        try:
            # Quantity is in the QTY column (second <td> in the row)
            # The structure is: PRODUCT <td> | QTY <td> | PRICE <td>
            cells = row.find_all('td')
            
            # Method 1: Look for the QTY column (width="90" or contains class with "s_desk_h_mob")
            # The QTY column is typically the second <td> or one with width="90"
            for cell in cells:
                cell_width = cell.get('width', '')
                cell_class = cell.get('class', [])
                cell_text = cell.get_text(strip=True)
                
                # Check if this is the QTY column (width="90" or second cell)
                if cell_width == '90' or (len(cells) >= 2 and cell == cells[1]):
                    # Check if it contains just a number (quantity)
                    if cell_text.isdigit():
                        quantity = int(cell_text)
                        logger.debug(f"Found quantity in QTY column: {quantity}")
                        return quantity
            
            # Method 2: Look for "QTY:" in text (fallback for hidden QTY cells)
            text = row.get_text()
            match = re.search(r'QTY[:\s]+(\d+)', text, re.IGNORECASE)
            if match:
                quantity = int(match.group(1))
                logger.debug(f"Found quantity from QTY: text: {quantity}")
                return quantity
            
            # Default to 1 if not found
            logger.warning("Quantity not found, defaulting to 1")
            return 1
        except Exception as e:
            logger.error(f"Error extracting quantity: {e}")
            return 1

    def _extract_price_from_cancellation_row(self, row) -> Optional[float]:
        """Extract price from cancellation row"""
        try:
            # Price is in the PRICE column
            text = row.get_text()
            match = re.search(r'\$?\s*([\d,]+\.?\d*)', text)
            if match:
                price_str = match.group(1).replace(',', '')
                return float(price_str)
            return None
        except:
            return None

    def _generate_unique_id_from_product_name(self, product_name: str) -> str:
        """Generate a unique ID from product name if product number is not available"""
        try:
            # Use first few words of product name, uppercase, no spaces
            words = product_name.split()[:3]
            return ''.join(word.upper() for word in words if word)
        except:
            return "UNKNOWN"
    
    def _extract_shipping_address(self, soup: BeautifulSoup) -> str:
        """
        Extract shipping address from email and normalize it.
        
        Hibbett email structure:
        - "Ship to Home" header
        - Name (e.g., "Griffin Myers")
        - Street address (e.g., "595 Lloyd Ln Ste D,")
        - City, State, ZIP (e.g., "Independence, OR, 97351-2125")
        - Phone number
        
        We want to extract just the street address line and normalize it.
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            Normalized shipping address or empty string
        """
        try:
            text = soup.get_text()
            
            # Method 1: Look for "Ship to Home" section and extract street address
            # Find the section after "Ship to Home"
            ship_to_match = re.search(
                r'Ship\s+to\s+Home\s*(.*?)(?:Billing|Payment|Order\s+Summary|$)',
                text,
                re.IGNORECASE | re.DOTALL
            )
            
            if ship_to_match:
                address_section = ship_to_match.group(1).strip()
                # Split into lines
                lines = [line.strip() for line in address_section.split('\n') if line.strip()]
                
                # Look for street address pattern (number + street name)
                # Pattern: starts with number, contains street name (Lloyd, Vista, etc.)
                for line in lines:
                    # Skip name lines (usually don't start with numbers)
                    # Skip phone lines (contain phone pattern)
                    # Skip city/state/zip lines (contain comma and state abbreviation)
                    if re.match(r'^\d+', line):  # Starts with number
                        if not re.search(r'\d{3}-\d{3}-\d{4}', line):  # Not a phone number
                            if not re.search(r',\s*[A-Z]{2}\s*,', line):  # Not city, state, zip
                                # This looks like a street address
                                normalized = normalize_shipping_address(line)
                                if normalized:
                                    logger.debug(f"Extracted Hibbett shipping address: {line} -> {normalized}")
                                    return normalized
            
            # Method 2: Direct pattern matching for known addresses
            # Look for "595 Lloyd" pattern
            lloyd_match = re.search(r'(595\s+Lloyd\s+Ln[^,\n]*)', text, re.IGNORECASE)
            if lloyd_match:
                street_line = lloyd_match.group(1).strip()
                normalized = normalize_shipping_address(street_line)
                if normalized:
                    logger.debug(f"Extracted Hibbett shipping address (pattern): {street_line} -> {normalized}")
                    return normalized
            
            # Method 3: Look for "2025 Vista" pattern
            vista_match = re.search(r'(2025\s+Vista\s+Ave[^,\n]*)', text, re.IGNORECASE)
            if vista_match:
                street_line = vista_match.group(1).strip()
                normalized = normalize_shipping_address(street_line)
                if normalized:
                    logger.debug(f"Extracted Hibbett shipping address (pattern): {street_line} -> {normalized}")
                    return normalized
            
            # Fallback: Try the old method but extract just street address
            shipping_match = re.search(
                r'(?:Shipping|Ship\s+to|Delivery)\s*(?:Address|to)?:?\s*(.*?)(?:Billing|Payment|Order|$)',
                text,
                re.IGNORECASE | re.DOTALL
            )
            
            if shipping_match:
                address_text = shipping_match.group(1).strip()
                lines = [line.strip() for line in address_text.split('\n') if line.strip()]
                
                # Find the street address line (starts with number, not phone, not city/state)
                for line in lines:
                    if re.match(r'^\d+', line):
                        if not re.search(r'\d{3}-\d{3}-\d{4}', line):
                            if not re.search(r',\s*[A-Z]{2}\s*,', line):
                                normalized = normalize_shipping_address(line)
                                if normalized:
                                    return normalized
            
            return ""
        
        except Exception as e:
            logger.error(f"Error extracting shipping address: {e}")
            return ""
