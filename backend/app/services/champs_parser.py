"""
Champs Sports Email Parser
Parses order confirmation emails from Champs Sports using BeautifulSoup
"""

import logging
import re
from datetime import datetime
from typing import List, Optional
from bs4 import BeautifulSoup

from app.models.email import EmailData
from app.utils.address_utils import normalize_shipping_address

logger = logging.getLogger(__name__)


class ChampsOrderItem:
    """Represents a single item from a Champs Sports order"""
    
    def __init__(self, unique_id: str, size: str, quantity: int, product_name: str = None):
        self.unique_id = unique_id    # Unique ID from image URL or product code
        self.size = size
        self.quantity = quantity
        self.product_name = product_name or "Unknown Product"
    
    def __repr__(self):
        if self.product_name and len(self.product_name) > 50:
            product_display = self.product_name[:50] + "..."
        else:
            product_display = self.product_name or "Unknown"
        return f"<ChampsOrderItem(unique_id={self.unique_id}, size={self.size}, qty={self.quantity}, product={product_display})>"


class ChampsOrderData:
    """Represents a complete Champs Sports order"""
    
    def __init__(self, order_number: str, items: List[ChampsOrderItem], shipping_address: str = None, order_datetime: Optional[datetime] = None):
        self.order_number = order_number
        self.items = items
        self.shipping_address = shipping_address or ""
        self.order_datetime = order_datetime  # Purchase date/time from email
    
    def __repr__(self):
        return f"<ChampsOrderData(order_number={self.order_number}, items_count={len(self.items)}, address={self.shipping_address})>"


class ChampsShippingData:
    """Represents Champs Sports shipping notification data"""
    
    def __init__(self, order_number: str, tracking_number: str, items: List[ChampsOrderItem]):
        self.order_number = order_number
        self.tracking_number = tracking_number
        self.items = items
    
    def __repr__(self):
        return f"<ChampsShippingData(order={self.order_number}, tracking={self.tracking_number}, items={len(self.items)})>"


class ChampsCancellationData:
    """Represents Champs Sports cancellation notification data"""
    
    def __init__(self, order_number: str, items: List[ChampsOrderItem]):
        self.order_number = order_number
        self.items = items
    
    def __repr__(self):
        return f"<ChampsCancellationData(order={self.order_number}, items={len(self.items)})>"


class ChampsEmailParser:
    """
    Parser for Champs Sports order confirmation emails using BeautifulSoup.
    
    Handles email formats like:
    From: accountservices@em.champssports.com
    Subject: "Thank you for your order, [name]"
    """
    
    # Email identification - Order Confirmation (Production)
    CHAMPS_FROM_EMAIL = "accountservices@em.champssports.com"
    CHAMPS_FROM_PATTERN = r"champs"
    SUBJECT_ORDER_PATTERN = r"Thank you for your order"
    
    # Email identification - Development (forwarded emails)
    DEV_CHAMPS_ORDER_FROM_EMAIL = "glenallagroupc@gmail.com"
    DEV_SUBJECT_ORDER_PATTERN = r"Fwd:\s*Thank you for your order"
    
    # Email identification - Shipping & Cancellation Updates (same as Footlocker)
    CHAMPS_UPDATE_FROM_EMAIL = "accountservices@em.champssports.com"
    SUBJECT_SHIPPING_PATTERN = r"Your order is ready to go"
    SUBJECT_CANCELLATION_PATTERN = r"An item is no longer available"
    DEV_SUBJECT_SHIPPING_PATTERN = r"Fwd:\s*Your order is ready to go"
    DEV_SUBJECT_CANCELLATION_PATTERN = r"Fwd:\s*An item is no longer available"
    
    def __init__(self):
        """Initialize the Champs email parser."""
        from app.config.settings import get_settings
        self.settings = get_settings()
    
    @property
    def order_from_email(self) -> str:
        """Get the appropriate from email address based on environment."""
        if self.settings.is_development:
            return self.DEV_CHAMPS_ORDER_FROM_EMAIL
        return self.CHAMPS_FROM_EMAIL
    
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
            return "Fwd: Thank you for your order"
        return "Thank you for your order"
    
    @property
    def update_from_email(self) -> str:
        """Get the appropriate from email address for updates (shipping/cancellation) based on environment."""
        if self.settings.is_development:
            return self.DEV_CHAMPS_ORDER_FROM_EMAIL
        return self.CHAMPS_UPDATE_FROM_EMAIL
    
    @property
    def shipping_subject_query(self) -> str:
        """Get the appropriate subject pattern for Gmail shipping queries. Same as Footlocker."""
        if self.settings.is_development:
            return 'subject:"Fwd: Your order is ready to go"'
        return 'subject:"Your order is ready to go"'
    
    @property
    def cancellation_subject_query(self) -> str:
        """Get the appropriate subject pattern for Gmail cancellation queries. Same as Footlocker."""
        if self.settings.is_development:
            return 'subject:"Fwd: An item is no longer available"'
        return 'subject:"An item is no longer available"'
    
    def is_champs_email(self, email_data: EmailData) -> bool:
        """
        Check if email is from Champs Sports.
        
        In dev mode, Champs and Footlocker both forward from glenallagroupc with same subjects.
        Differentiate via HTML content (champssports vs footlocker).
        """
        sender_lower = email_data.sender.lower()
        
        # In development, both use same dev email - require champssports in HTML
        if self.settings.is_development:
            if self.DEV_CHAMPS_ORDER_FROM_EMAIL.lower() in sender_lower:
                html = (email_data.html_content or "").lower()
                if "champssports" in html:
                    return True
                return False
        
        # Check for production email address
        if self.CHAMPS_FROM_EMAIL.lower() in sender_lower:
            return True
        
        if re.search(self.CHAMPS_FROM_PATTERN, sender_lower, re.IGNORECASE):
            return True
        
        return False
    
    def is_order_confirmation_email(self, email_data: EmailData) -> bool:
        """Check if email is an order confirmation"""
        subject_lower = email_data.subject.lower()
        
        # Use environment-aware subject pattern
        if re.search(self.order_subject_pattern, subject_lower, re.IGNORECASE):
            return True
        
        # Also check for the base pattern (for forwarded emails that might have variations)
        if re.search(self.SUBJECT_ORDER_PATTERN, subject_lower, re.IGNORECASE):
            return True
        
        return False
    
    def is_shipping_email(self, email_data: EmailData) -> bool:
        """Check if email is a shipping notification"""
        subject_lower = email_data.subject.lower()
        
        if re.search(self.SUBJECT_SHIPPING_PATTERN, subject_lower, re.IGNORECASE):
            return True
        if self.settings.is_development and re.search(self.DEV_SUBJECT_SHIPPING_PATTERN, subject_lower, re.IGNORECASE):
            return True
        return False
    
    def is_cancellation_email(self, email_data: EmailData) -> bool:
        """Check if email is a cancellation notification"""
        subject_lower = email_data.subject.lower()
        
        if re.search(self.SUBJECT_CANCELLATION_PATTERN, subject_lower, re.IGNORECASE):
            return True
        if self.settings.is_development and re.search(self.DEV_SUBJECT_CANCELLATION_PATTERN, subject_lower, re.IGNORECASE):
            return True
        return False
    
    def parse_email(self, email_data: EmailData) -> Optional[ChampsOrderData]:
        """
        Parse Champs Sports order confirmation email.
        
        Args:
            email_data: EmailData object containing email information
        
        Returns:
            ChampsOrderData object or None if parsing fails
        """
        try:
            html_content = email_data.html_content
            
            if not html_content:
                logger.error("No HTML content in Champs email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extract order number
            order_number = self._extract_order_number(soup)
            if not order_number:
                logger.error("Failed to extract order number from Champs Sports email")
                return None
            
            logger.info(f"Extracted Champs Sports order number: {order_number}")
            
            # Extract items using BeautifulSoup
            items = self._extract_items(soup)
            
            if not items:
                logger.error("Failed to extract any items from Champs Sports email")
                return None
            
            logger.info(f"Successfully extracted {len(items)} items from Champs Sports order {order_number}")
            for item in items:
                logger.debug(f"  - {item}")
            
            # Extract shipping address
            shipping_address = self._extract_shipping_address(soup)
            if shipping_address:
                logger.info(f"Extracted shipping address: {shipping_address}")

            # Extract purchase date/time (e.g. "Purchase date: November 13, 2025")
            order_datetime = self._extract_purchase_datetime(soup)
            if order_datetime:
                logger.info(f"Extracted purchase datetime: {order_datetime}")
            
            return ChampsOrderData(order_number=order_number, items=items, shipping_address=shipping_address, order_datetime=order_datetime)
        
        except Exception as e:
            logger.error(f"Error parsing Champs order: {e}", exc_info=True)
            return None

    def _extract_purchase_datetime(self, soup: BeautifulSoup) -> Optional[datetime]:
        """Extract purchase date from email (e.g. 'Purchase date: November 13, 2025')."""
        try:
            text = soup.get_text()
            match = re.search(r'Purchase\s+date:\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4})\s*', text, re.IGNORECASE)
            if match:
                date_str = match.group(1).strip().replace(',', '')
                try:
                    dt = datetime.strptime(date_str, '%B %d %Y')
                    return dt.replace(hour=12, minute=0, second=0, microsecond=0)
                except ValueError:
                    pass
            return None
        except Exception as e:
            logger.debug(f"Could not extract purchase datetime: {e}")
            return None
    
    def _extract_order_number(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract order number from email using BeautifulSoup.
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            Order number or None
        """
        try:
            # Method 1: Look for spans or elements containing "Order:" text
            order_elements = soup.find_all(string=re.compile(r'Order[:\s]+', re.IGNORECASE))
            
            for element in order_elements:
                # Get the parent element to see the full context
                parent = element.parent
                if parent:
                    parent_text = parent.get_text()
                    # Champs uses same order format as Footlocker: P + 19 digits
                    match = re.search(r'Order[:\s]+([P]\d{19})', parent_text, re.IGNORECASE)
                    if match:
                        return match.group(1)
            
            # Method 2: Look for spans with P + 19 digits pattern
            spans = soup.find_all('span')
            for span in spans:
                span_text = span.get_text(strip=True)
                if re.match(r'^P\d{19}$', span_text):
                    return span_text
            
            # Method 3: Fallback to regex on full text
            text = soup.get_text()
            match = re.search(r'Order[:\s]+([P]\d{19})', text, re.IGNORECASE)
            if match:
                return match.group(1)
            
            logger.warning("Order number not found in Champs email")
            return None
        
        except Exception as e:
            logger.error(f"Error extracting order number: {e}")
            return None
    
    def _extract_items(self, soup: BeautifulSoup) -> List[ChampsOrderItem]:
        """
        Extract order items using BeautifulSoup.
        
        Champs Sports uses the SAME HTML structure as Footlocker (same parent company):
        - fluid-row, col-3, col-9 table layout
        - Product images: images.footlocker.com/is/image/EBFL2/{unique_id}
        - Size/Qty in spans within same product container
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            List of ChampsOrderItem objects
        """
        items = []
        
        try:
            # Find all images with EBFL2 in the src (product images) - same as Footlocker
            product_images = soup.find_all('img', src=re.compile(r'/EBFL2/'))
            logger.debug(f"Found {len(product_images)} product images")
            
            used_size_quantity = set()
            
            for img in product_images:
                try:
                    img_src = img.get('src', '')
                    # Handle Gmail proxy URLs
                    if "#" in img_src:
                        parts = img_src.split("#")
                        if len(parts) > 1:
                            img_src = parts[-1]
                    
                    unique_id_match = re.search(r'(?:/EBFL2/|/is/image/EBFL2/)([A-Z0-9]+)', img_src)
                    if not unique_id_match:
                        logger.warning(f"Could not extract unique ID from image: {img_src}")
                        continue
                    
                    unique_id = unique_id_match.group(1)
                    product_name = self._extract_product_name_from_image(img)
                    size, quantity = self._find_size_quantity_for_image(img, used_size_quantity)
                    
                    if size and quantity:
                        used_size_quantity.add((size, quantity))
                    
                    if size and quantity and self._is_valid_size(size) and self._is_valid_quantity(quantity):
                        items.append(ChampsOrderItem(
                            unique_id=unique_id,
                            size=self._clean_size(size),
                            quantity=int(quantity),
                            product_name=product_name
                        ))
                        logger.debug(
                            f"Extracted: {product_name} (unique_id={unique_id}), "
                            f"Size: {size}, Qty: {quantity}"
                        )
                    else:
                        logger.warning(
                            f"Invalid or missing data for {unique_id}: "
                            f"size={size}, qty={quantity}"
                        )
                
                except Exception as e:
                    logger.error(f"Error processing product image: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error extracting items: {e}", exc_info=True)
        
        if items:
            items_summary = [f"(ID: {item.unique_id}, Size: {item.size}, Qty: {item.quantity})" for item in items]
            logger.info(f"[Champs Sports] Extracted {len(items)} items: {', '.join(items_summary)}")
        return items
    
    def _extract_all_size_quantity_data(self, soup: BeautifulSoup) -> List[dict]:
        """
        Extract all size and quantity data from the document.
        
        Returns:
            List of dicts with size, quantity, and context info
        """
        size_quantity_data = []
        
        try:
            # Find all spans that contain size/quantity data
            spans = soup.find_all('span')
            
            for span in spans:
                span_text = span.get_text(strip=True)
                parent = span.parent
                
                if parent:
                    parent_text = parent.get_text(strip=True)
                    
                    # Check for size pattern: "Size07.0" -> extract "07.0"
                    if 'Size' in parent_text and self._is_valid_size(span_text):
                        size_quantity_data.append({
                            'type': 'size',
                            'value': span_text,
                            'context': parent_text,
                            'element': span
                        })
                        logger.debug(f"Found size: {span_text}")
                    
                    # Check for quantity pattern: "Qty1" or "QTY1" -> extract "1"
                    if ('Qty' in parent_text or 'QTY' in parent_text) and self._is_valid_quantity(span_text):
                        size_quantity_data.append({
                            'type': 'quantity',
                            'value': span_text,
                            'context': parent_text,
                            'element': span
                        })
                        logger.debug(f"Found quantity: {span_text}")
                    
                    # Also check if the span text itself is just a number (likely quantity)
                    if self._is_valid_quantity(span_text) and span_text in ['1', '2', '3', '4', '5']:
                        size_quantity_data.append({
                            'type': 'quantity',
                            'value': span_text,
                            'context': parent_text,
                            'element': span
                        })
                        logger.debug(f"Found standalone quantity: {span_text}")
            
            return size_quantity_data
            
        except Exception as e:
            logger.error(f"Error extracting size/quantity data: {e}")
            return []
    
    def _find_size_quantity_for_image(self, img, used_size_quantity: set) -> tuple:
        """
        Find size and quantity for a product image based on DOM structure.
        
        Champs uses the SAME structure as Footlocker: fluid-row table with col-3 (image)
        and col-9 (product details). Size and Qty are in spans within the same container.
        
        Args:
            img: BeautifulSoup img element
            used_size_quantity: Set of already used (size, quantity) pairs
        
        Returns:
            Tuple of (size, quantity) or (None, None) if not found
        """
        try:
            fluid_row = img.find_parent('table', class_=re.compile(r'fluid-row'))
            if not fluid_row:
                parent_table = img.find_parent('table')
                if parent_table:
                    parent_tables = [parent_table]
                    grandparent = parent_table.find_parent('table')
                    if grandparent:
                        parent_tables.append(grandparent)
                    for table in parent_tables:
                        has_image = bool(table.find('img', src=re.compile(r'/EBFL2/')))
                        has_size_qty = bool(re.search(r'Size|Qty', table.get_text(), re.IGNORECASE))
                        if has_image and has_size_qty:
                            fluid_row = table
                            break
            if not fluid_row:
                col3_table = img.find_parent('table', class_=re.compile(r'col-3'))
                if col3_table:
                    parent = col3_table.find_parent('table')
                    if parent and parent.find('table', class_=re.compile(r'col-9')):
                        fluid_row = parent
            if not fluid_row:
                return None, None
            
            size = None
            quantity = None
            spans = fluid_row.find_all('span')
            
            for span in spans:
                span_text = span.get_text(strip=True)
                if not span_text:
                    continue
                is_size = self._is_valid_size(span_text)
                is_quantity = self._is_valid_quantity(span_text)
                if not (is_size or is_quantity):
                    continue
                
                parent_text = ""
                current = span.parent
                for _ in range(5):
                    if current:
                        current_text = current.get_text(strip=True)
                        current_text_upper = current_text.upper()
                        # Check case-insensitively: order confirmations use "QTY", cancellations use "Qty"
                        if 'SIZE' in current_text_upper or 'QTY' in current_text_upper:
                            parent_text = current_text
                            break
                        current = current.find_parent(['td', 'tr', 'table', 'div'])
                    else:
                        break
                if not parent_text and span.parent:
                    parent_text = span.parent.get_text(strip=True)
                
                parent_text_upper = parent_text.upper()
                if is_size and 'SIZE' in parent_text_upper:
                    size = span_text
                if is_quantity and 'QTY' in parent_text_upper:
                    quantity = span_text
            
            if size and quantity:
                pair = (size, quantity)
                if pair in used_size_quantity:
                    return None, None
                return size, quantity
            return size, quantity
        except Exception as e:
            logger.error(f"Error finding size/quantity for image: {e}")
            return None, None
    
    def _extract_product_name_from_image(self, img) -> str:
        """Extract product name from the image's container - improved version"""
        try:
            # Find the container of the image - go up multiple levels
            containers_to_check = []
            
            # Try immediate parent first
            parent = img.find_parent()
            if parent:
                containers_to_check.append(parent)
            
            # Try td/tr/table ancestors (Champs uses tables)
            for tag in ['td', 'tr', 'table', 'div']:
                ancestor = img.find_parent(tag)
                if ancestor and ancestor not in containers_to_check:
                    containers_to_check.append(ancestor)
            
            # Method 0: Check alt text on the image first
            alt_text = img.get('alt', '')
            if alt_text and len(alt_text) > 10 and len(alt_text) < 200:
                logger.debug(f"[Champs] Found product name from alt text: {alt_text[:50]}")
                return alt_text
            
            # Method 1: Look for links with text longer than 10 characters
            for container in containers_to_check:
                links = container.find_all('a')
                for link in links:
                    link_text = link.get_text(strip=True)
                    # Product names are usually substantial text
                    if link_text and len(link_text) > 10 and len(link_text) < 200:
                        # Skip common link text that isn't product names
                        skip_texts = ['view', 'details', 'shop now', 'buy now', 'add to cart', 
                                     'track order', 'return', 'exchange', 'view order']
                        if link_text.lower() not in skip_texts:
                            logger.debug(f"[Champs] Found product name from link: {link_text[:50]}")
                            return link_text
            
            # Method 2: Look for text in <td> or <div> elements containing the image
            for container in containers_to_check[:3]:  # Check first 3 ancestors
                # Find all text in the container
                for elem in container.find_all(['td', 'div', 'span', 'p']):
                    text = elem.get_text(strip=True)
                    # Look for substantial text that looks like a product name
                    if text and 15 < len(text) < 200:
                        # Skip if it looks like size/quantity/price/generic text
                        if not re.search(r'^(Size|Qty|Quantity|Price|Total|Subtotal|Order|Shipping)', text, re.IGNORECASE):
                            # Skip if it's mostly numbers or currency
                            if not re.search(r'^\$[\d,]+\.?\d*$', text):
                                # Skip if it contains only size/qty patterns
                                if not re.match(r'^(Size\s*\d+|Qty\s*\d+)$', text, re.IGNORECASE):
                                    logger.debug(f"[Champs] Found product name from text: {text[:50]}")
                                    return text
            
            # Method 3: Look in the entire table row if image is in a table
            tr = img.find_parent('tr')
            if tr:
                # Get all text from the row, split by common separators
                row_text = tr.get_text(separator='|', strip=True)
                # Split and look for product-like text
                parts = [p.strip() for p in row_text.split('|')]
                for part in parts:
                    if 15 < len(part) < 200:
                        # Look for text that might be a product name
                        if not re.search(r'^(Size|Qty|Quantity|Price|\$|Order)', part, re.IGNORECASE):
                            if not re.match(r'^[\d,]+\.?\d*$', part):
                                logger.debug(f"[Champs] Found product name from table row: {part[:50]}")
                                return part
            
            logger.debug(f"[Champs] Could not extract product name from image: {img.get('src', '')[:50]}")
            return "Unknown Product"
            
        except Exception as e:
            logger.warning(f"[Champs] Error extracting product name from image: {e}")
            return "Unknown Product"
    
    def _extract_unique_id_from_image(self, img_src: str, img_alt: str) -> Optional[str]:
        """Extract unique ID from image source or alt text"""
        try:
            # Try to extract from image source URL
            if img_src:
                # Look for patterns like /product/ABC123 or /images/ABC123
                match = re.search(r'/(?:product|item|images?)/([A-Z0-9]+)', img_src, re.IGNORECASE)
                if match:
                    return match.group(1)
            
            # Try to extract from alt text
            if img_alt:
                # Look for product codes in alt text
                match = re.search(r'([A-Z0-9]{6,12})', img_alt)
                if match:
                    return match.group(1)
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting unique ID: {e}")
            return None
    
    def _find_matching_size_quantity_advanced(
        self, 
        unique_id: str, 
        size_quantity_data: List[dict], 
        used_size_quantity: set
    ) -> tuple:
        """
        Advanced matching algorithm that avoids reusing the same size/quantity pairs.
        
        Args:
            unique_id: The unique ID of the product
            size_quantity_data: List of size/quantity data from the document
            used_size_quantity: Set of already used (size, quantity) pairs
        
        Returns:
            Tuple of (size, quantity) or (None, None) if not found
        """
        try:
            # Find all available size/quantity pairs
            available_pairs = []
            
            for i, item in enumerate(size_quantity_data):
                if item['type'] == 'size':
                    # Look for nearby quantity
                    for j, other_item in enumerate(size_quantity_data):
                        if (other_item['type'] == 'quantity' and 
                            abs(i - j) <= 3):  # Within 3 positions
                            pair = (item['value'], other_item['value'])
                            if pair not in used_size_quantity:
                                available_pairs.append({
                                    'size': item['value'],
                                    'quantity': other_item['value'],
                                    'distance': abs(i - j)
                                })
                            break
            
            # Sort by distance to get the closest match
            if available_pairs:
                available_pairs.sort(key=lambda x: x['distance'])
                pair = available_pairs[0]
                logger.debug(f"Matched size {pair['size']} and quantity {pair['quantity']} for {unique_id}")
                return pair['size'], pair['quantity']
            
            # If no pairs found, try to find any unused size and quantity
            size = None
            quantity = None
            
            for item in size_quantity_data:
                if item['type'] == 'size' and not size:
                    size = item['value']
                if item['type'] == 'quantity' and not quantity:
                    quantity = item['value']
            
            return size, quantity
            
        except Exception as e:
            logger.error(f"Error in advanced matching: {e}")
            return None, None
    
    def _is_valid_size(self, size: str) -> bool:
        """Check if a value looks like a valid shoe size (same as Footlocker)"""
        # Decimal sizes like "06.0", "10.5", "14.0", "12.0"
        if re.match(r'^\d{1,2}\.\d$', size):
            return True
        if re.match(r'^\d{1,2}$', size):
            num = int(size)
            return num > 0
        if re.match(r'^\d{1,2}(\.\d)?Y$', size, re.IGNORECASE):
            return True
        if re.match(r'^\d{1,2}T$', size, re.IGNORECASE):
            return True
        if re.match(r'^\d{1,2}C$', size, re.IGNORECASE):
            return True
        if re.match(r'^\d{1,2}(\.\d)?W$', size, re.IGNORECASE):
            return True
        if re.match(r'^[SMLX]+$', size, re.IGNORECASE):
            return True
        if re.match(r'^OS(FM)?$', size, re.IGNORECASE):
            return True
        return False
    
    def _is_valid_quantity(self, quantity: str) -> bool:
        """Check if quantity is valid (positive integer)"""
        try:
            if not re.match(r'^\d+$', quantity):
                return False
            qty = int(quantity)
            return 1 <= qty <= 20  # Same range as Footlocker
        except (ValueError, TypeError):
            return False
    
    def _extract_product_data_from_text(self, soup: BeautifulSoup) -> List[dict]:
        """
        Extract product data from Champs Sports emails.
        
        Since the text pattern matching is complex, we'll use a simpler approach:
        1. Find spans that contain product information
        2. Extract product names and match them with size/quantity data
        
        Returns:
            List of dicts with product information
        """
        product_data = []
        
        try:
            # Find spans that contain product information
            spans = soup.find_all('span')
            
            for span in spans:
                span_text = span.get_text(strip=True)
                
                # Look for spans that contain product names (like "Brooks Ghost")
                if 'Brooks' in span_text and 'Size' in span_text:
                    logger.debug(f"Found product span: {span_text[:100]}...")
                    
                    # Extract product name (everything before "Size")
                    size_pos = span_text.find('Size')
                    if size_pos > 0:
                        product_name = span_text[:size_pos].strip()
                        
                        # Clean up product name - extract just the product part
                        # Look for "Brooks Ghost 16 - Men's" pattern
                        brooks_match = re.search(r'(Brooks[^S]+)', product_name)
                        if brooks_match:
                            product_name = brooks_match.group(1).strip()
                        else:
                            # Fallback: clean up the product name
                            product_name = re.sub(r'\s+', ' ', product_name).strip()
                        
                        if product_name and len(product_name) > 5:
                            # Extract size and quantity from the same span
                            size_match = re.search(r'Size\s*([0-9.]+)', span_text)
                            qty_match = re.search(r'QTY\s*([0-9]+)', span_text)
                            
                            if size_match and qty_match:
                                size = size_match.group(1)
                                quantity = qty_match.group(1)
                                
                                product_data.append({
                                    'name': product_name,
                                    'size': size,
                                    'quantity': quantity
                                })
                                logger.debug(f"Found product: {product_name}, Size: {size}, Qty: {quantity}")
            
            return product_data
            
        except Exception as e:
            logger.error(f"Error extracting product data from text: {e}")
            return []
    
    def _generate_unique_id_from_product(self, product_name: str) -> str:
        """
        Generate a unique ID from product name for Champs Sports items.
        
        Since Champs Sports doesn't have clear unique IDs like Footlocker,
        we'll create one from the product name.
        
        Args:
            product_name: Product name string
        
        Returns:
            Unique ID string
        """
        try:
            # Extract key words from product name
            words = re.findall(r'[A-Za-z]+', product_name)
            if len(words) >= 2:
                # Use first two words + length as unique ID
                unique_id = f"{words[0][:3]}{words[1][:3]}{len(product_name)}"
            else:
                # Fallback to hash of product name
                unique_id = f"CH{hash(product_name) % 10000:04d}"
            
            return unique_id.upper()
            
        except Exception as e:
            logger.error(f"Error generating unique ID: {e}")
            return f"CH{hash(product_name) % 10000:04d}".upper()
    
    def _clean_size(self, size: str) -> str:
        """Clean up size format (remove trailing .0 if it's a whole number)"""
        # Convert "06.0" to "6", "10.5" to "10.5", "14.0" to "14", etc.
        if re.match(r'^\d{1,2}\.\d$', size):
            num = float(size)
            # Remove .0 if it's a whole number
            return str(int(num)) if num % 1 == 0 else str(num)
        
        return size
    
    def parse_shipping_email(self, email_data: EmailData) -> Optional[ChampsShippingData]:
        """
        Parse Champs Sports shipping notification email.
        
        Args:
            email_data: EmailData object containing email information
        
        Returns:
            ChampsShippingData object or None if parsing fails
        """
        try:
            html_content = email_data.html_content
            
            if not html_content:
                logger.error("No HTML content in Champs shipping email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extract order number
            order_number = self._extract_order_number(soup)
            if not order_number:
                logger.error("Failed to extract order number from Champs shipping email")
                return None
            
            # Extract tracking number
            tracking_number = self._extract_tracking_number(soup)
            if not tracking_number:
                logger.warning("Failed to extract tracking number from Champs shipping email")
                tracking_number = "Unknown"
            
            logger.info(f"Extracted Champs shipping - Order: {order_number}, Tracking: {tracking_number}")
            
            # Extract items using BeautifulSoup
            items = self._extract_items(soup)
            
            if not items:
                logger.error("Failed to extract any items from Champs shipping email")
                return None
            
            logger.info(f"Successfully extracted {len(items)} items from Champs shipping notification")
            for item in items:
                logger.debug(f"  - {item}")
            
            return ChampsShippingData(
                order_number=order_number,
                tracking_number=tracking_number,
                items=items
            )
        
        except Exception as e:
            logger.error(f"Error parsing Champs shipping email: {e}", exc_info=True)
            return None
    
    def parse_cancellation_email(self, email_data: EmailData) -> Optional[ChampsCancellationData]:
        """
        Parse Champs Sports cancellation notification email.
        
        Args:
            email_data: EmailData object containing email information
        
        Returns:
            ChampsCancellationData object or None if parsing fails
        """
        try:
            html_content = email_data.html_content
            
            if not html_content:
                logger.error("No HTML content in Champs cancellation email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extract order number
            order_number = self._extract_order_number(soup)
            if not order_number:
                logger.error("Failed to extract order number from Champs cancellation email")
                return None
            
            logger.info(f"Extracted Champs cancellation - Order: {order_number}")
            
            # Extract items using BeautifulSoup
            items = self._extract_items(soup)
            
            if not items:
                logger.error("Failed to extract any items from Champs cancellation email")
                return None
            
            logger.info(f"Successfully extracted {len(items)} items from Champs cancellation notification")
            for item in items:
                logger.debug(f"  - {item}")
            
            return ChampsCancellationData(
                order_number=order_number,
                items=items
            )
        
        except Exception as e:
            logger.error(f"Error parsing Champs cancellation email: {e}", exc_info=True)
            return None
    
    def _extract_tracking_number(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract tracking number from shipping email.
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            Tracking number or None
        """
        try:
            # Method 1: Look for "tracking" keyword and nearby numbers
            tracking_elements = soup.find_all(string=re.compile(r'tracking', re.IGNORECASE))
            
            for element in tracking_elements:
                parent = element.parent
                if parent:
                    parent_text = parent.get_text()
                    # Look for tracking number patterns (various carriers)
                    # FEDEX: 12 digits (e.g., 394651080864)
                    match = re.search(r'FEDEX\s+tracking[:\s]+(\d{12})', parent_text, re.IGNORECASE)
                    if match:
                        return match.group(1)
                    
                    # Generic tracking number patterns
                    match = re.search(r'tracking[:\s]+(\d{9,20})', parent_text, re.IGNORECASE)
                    if match:
                        return match.group(1)
                    
                    # UPS: 1Z...
                    match = re.search(r'1Z[A-Z0-9]{16}', parent_text, re.IGNORECASE)
                    if match:
                        return match.group(0)
                    
                    # USPS: 20-22 digits
                    match = re.search(r'\b\d{20,22}\b', parent_text)
                    if match:
                        return match.group(0)
            
            # Method 2: Look for links with tracking URLs
            links = soup.find_all('a', href=re.compile(r'track', re.IGNORECASE))
            for link in links:
                href = link.get('href', '')
                # Extract tracking number from URL
                match = re.search(r'tracking[=/#]([A-Z0-9]+)', href, re.IGNORECASE)
                if match:
                    return match.group(1)
            
            logger.warning("Tracking number not found in Champs shipping email")
            return None
        
        except Exception as e:
            logger.error(f"Error extracting tracking number: {e}")
            return None
    
    def _extract_shipping_address(self, soup: BeautifulSoup) -> str:
        """
        Extract shipping address from email and normalize it.
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            Normalized shipping address or empty string
        """
        try:
            text = soup.get_text()
            
            # Find the shipping section
            shipping_match = re.search(
                r'SHIPPING\s+TO:?\s*(.*?)(?:ORDER\s+SUMMARY|PAYMENT|$)',
                text,
                re.IGNORECASE | re.DOTALL
            )
            
            if shipping_match:
                address_text = shipping_match.group(1).strip()
                address_lines = [line.strip() for line in address_text.split('\n') if line.strip()][:5]
                address_combined = ' '.join(address_lines)
                
                normalized = normalize_shipping_address(address_combined)
                return normalized
            
            return ""
        
        except Exception as e:
            logger.error(f"Error extracting shipping address: {e}")
            return ""
