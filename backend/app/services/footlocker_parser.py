"""
Footlocker Order Confirmation Email Parser
Extracts order details from Footlocker confirmation emails using BeautifulSoup
"""

import logging
import re
from datetime import datetime
from typing import List, Optional
from bs4 import BeautifulSoup, Tag

from app.models.email import EmailData
from app.utils.address_utils import normalize_shipping_address
from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class FootlockerOrderItem:
    """Represents a single item from a Footlocker order"""
    
    def __init__(self, unique_id: str, size: str, quantity: int, product_name: str = None):
        self.unique_id = unique_id    # Unique ID from image URL (e.g., 64033WWH, 6197725)
        self.size = size
        self.quantity = quantity
        self.product_name = product_name or "Unknown Product"
    
    def __repr__(self):
        if self.product_name and len(self.product_name) > 50:
            product_display = self.product_name[:50] + "..."
        else:
            product_display = self.product_name or "Unknown"
        return f"<FootlockerOrderItem(unique_id={self.unique_id}, size={self.size}, qty={self.quantity}, product={product_display})>"


class FootlockerOrderData:
    """Represents complete Footlocker order data"""
    
    def __init__(self, order_number: str, items: List[FootlockerOrderItem], shipping_address: str = None, order_datetime: Optional[datetime] = None):
        self.order_number = order_number
        self.items = items
        self.shipping_address = shipping_address or ""
        self.order_datetime = order_datetime  # Purchase date/time from email
    
    def __repr__(self):
        return f"<FootlockerOrderData(order={self.order_number}, items={len(self.items)}, address={self.shipping_address})>"


class FootlockerShippingData:
    """Represents Footlocker shipping notification data"""
    
    def __init__(self, order_number: str, tracking_number: str, items: List[FootlockerOrderItem]):
        self.order_number = order_number
        self.tracking_number = tracking_number
        self.items = items
    
    def __repr__(self):
        return f"<FootlockerShippingData(order={self.order_number}, tracking={self.tracking_number}, items={len(self.items)})>"


class FootlockerCancellationData:
    """Represents Footlocker cancellation notification data"""
    
    def __init__(self, order_number: str, items: List[FootlockerOrderItem]):
        self.order_number = order_number
        self.items = items
    
    def __repr__(self):
        return f"<FootlockerCancellationData(order={self.order_number}, items={len(self.items)})>"


class FootlockerEmailParser:
    """
    Parser for Footlocker order confirmation emails using BeautifulSoup.
    
    Handles email formats like:
    From: accountservices@em.footlocker.com
    Subject: "Thank you for your order, [name]"
    Content: Contains order number, product info with images, sizes, and quantities
    """
    
    # Email identification - Order Confirmation (Production)
    FOOTLOCKER_ORDER_FROM_EMAIL = "accountservices@em.footlocker.com"
    KIDS_FOOTLOCKER_ORDER_FROM_EMAIL = "accountservices@em.kidsfootlocker.com"
    FOOTLOCKER_FROM_PATTERN = r"footlocker"
    KIDS_FOOTLOCKER_FROM_PATTERN = r"kidsfootlocker"
    SUBJECT_ORDER_PATTERN = r"Thank you for your order"
    
    # Email identification - Development (forwarded emails)
    DEV_FOOTLOCKER_ORDER_FROM_EMAIL = "glenallagroupc@gmail.com"
    DEV_SUBJECT_ORDER_PATTERN = r"Fwd:\s*Thank you for your order"
    
    # Email identification - Shipping & Cancellation Updates
    FOOTLOCKER_UPDATE_FROM_EMAIL = "accountservices@em.footlocker.com" # "accountservices@em.footlocker.com"  # Same as order for Footlocker
    KIDS_FOOTLOCKER_UPDATE_FROM_EMAIL = "accountservices@em.kidsfootlocker.com"  # Same as order for Kids Foot Locker
    SUBJECT_SHIPPING_PATTERN = r"Your order is ready to go"
    SUBJECT_CANCELLATION_PATTERN = r"An item is no longer available"
    
    # Email identification - Development (forwarded emails for updates)
    DEV_SUBJECT_SHIPPING_PATTERN = r"Fwd:\s*Your order is ready to go"
    DEV_SUBJECT_CANCELLATION_PATTERN = r"Fwd:\s*An item is no longer available"
    
    def __init__(self):
        """Initialize the Footlocker email parser."""
        self.settings = get_settings()
    
    @property
    def order_from_email(self) -> str:
        """Get the appropriate from email address based on environment."""
        if self.settings.is_development:
            return self.DEV_FOOTLOCKER_ORDER_FROM_EMAIL
        return self.FOOTLOCKER_ORDER_FROM_EMAIL
    
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
            return self.DEV_FOOTLOCKER_ORDER_FROM_EMAIL
        return self.FOOTLOCKER_UPDATE_FROM_EMAIL
    
    @property
    def kids_update_from_email(self) -> str:
        """Get the appropriate from email address for Kids Foot Locker updates based on environment."""
        if self.settings.is_development:
            return self.DEV_FOOTLOCKER_ORDER_FROM_EMAIL
        return self.KIDS_FOOTLOCKER_UPDATE_FROM_EMAIL
    
    @property
    def shipping_subject_query(self) -> str:
        """Get the appropriate subject pattern for Gmail shipping queries based on environment."""
        if self.settings.is_development:
            return 'subject:"Fwd: Your order is ready to go"'
        return 'subject:"Your order is ready to go"'
    
    @property
    def cancellation_subject_query(self) -> str:
        """Get the appropriate subject pattern for Gmail cancellation queries based on environment."""
        if self.settings.is_development:
            return 'subject:"Fwd: An item is no longer available"'
        return 'subject:"An item is no longer available"'
    
    def is_footlocker_email(self, email_data: EmailData) -> bool:
        """
        Check if email is from Footlocker or Kids Foot Locker (any type).
        
        In dev mode, Champs uses same dev email and subjects - differentiate via HTML content.
        
        Args:
            email_data: EmailData object
        
        Returns:
            True if email is from Footlocker or Kids Foot Locker, False otherwise
        """
        sender_lower = email_data.sender.lower()
        
        # In development, both Footlocker and Champs forward from glenallagroupc - check HTML content
        if self.settings.is_development:
            if self.DEV_FOOTLOCKER_ORDER_FROM_EMAIL.lower() in sender_lower:
                html = (email_data.html_content or "").lower()
                # Champs has champssports in HTML; Footlocker has footlocker
                if "champssports" in html:
                    return False  # This is Champs, not Footlocker
                return True
        
        # Check for Footlocker direct email addresses (order or update)
        if self.FOOTLOCKER_ORDER_FROM_EMAIL.lower() in sender_lower:
            return True
        
        if self.FOOTLOCKER_UPDATE_FROM_EMAIL.lower() in sender_lower:
            return True
        
        # Check for Kids Foot Locker direct email addresses (order or update)
        if self.KIDS_FOOTLOCKER_ORDER_FROM_EMAIL.lower() in sender_lower:
            return True
        
        if self.KIDS_FOOTLOCKER_UPDATE_FROM_EMAIL.lower() in sender_lower:
            return True
        
        # Check for "Footlocker" or "kidsfootlocker" in sender name
        if re.search(self.FOOTLOCKER_FROM_PATTERN, sender_lower, re.IGNORECASE):
            return True
        
        if re.search(self.KIDS_FOOTLOCKER_FROM_PATTERN, sender_lower, re.IGNORECASE):
            return True
        
        return False
    
    def is_kids_footlocker_email(self, email_data: EmailData) -> bool:
        """
        Check if email is specifically from Kids Foot Locker.
        
        Args:
            email_data: EmailData object
        
        Returns:
            True if email is from Kids Foot Locker, False otherwise
        """
        sender_lower = email_data.sender.lower()
        
        # Check for Kids Foot Locker direct email addresses
        if self.KIDS_FOOTLOCKER_ORDER_FROM_EMAIL.lower() in sender_lower:
            return True
        
        if self.KIDS_FOOTLOCKER_UPDATE_FROM_EMAIL.lower() in sender_lower:
            return True
        
        # Check for "kidsfootlocker" in sender name
        if re.search(self.KIDS_FOOTLOCKER_FROM_PATTERN, sender_lower, re.IGNORECASE):
            return True
        
        return False
    
    def is_order_confirmation_email(self, email_data: EmailData) -> bool:
        """
        Check if email is an order confirmation.
        
        Args:
            email_data: EmailData object
        
        Returns:
            True if this is an order confirmation email
        """
        subject_lower = email_data.subject.lower()
        
        # Use environment-aware subject pattern
        if re.search(self.order_subject_pattern, subject_lower, re.IGNORECASE):
            return True
        
        # Also check for the base pattern (for forwarded emails that might have variations)
        if re.search(self.SUBJECT_ORDER_PATTERN, subject_lower, re.IGNORECASE):
            return True
        
        return False
    
    def is_shipping_email(self, email_data: EmailData) -> bool:
        """
        Check if email is a shipping notification.
        
        Args:
            email_data: EmailData object
        
        Returns:
            True if this is a shipping notification email
        """
        subject_lower = email_data.subject.lower()
        
        # Check for production shipping pattern
        if re.search(self.SUBJECT_SHIPPING_PATTERN, subject_lower, re.IGNORECASE):
            return True
        
        # Check for development shipping pattern (forwarded emails)
        if self.settings.is_development:
            if re.search(self.DEV_SUBJECT_SHIPPING_PATTERN, subject_lower, re.IGNORECASE):
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
        subject_lower = email_data.subject.lower()
        
        # Check for production cancellation pattern
        if re.search(self.SUBJECT_CANCELLATION_PATTERN, subject_lower, re.IGNORECASE):
            return True
        
        # Check for development cancellation pattern (forwarded emails)
        if self.settings.is_development:
            if re.search(self.DEV_SUBJECT_CANCELLATION_PATTERN, subject_lower, re.IGNORECASE):
                return True
        
        return False
    
    def parse_email(self, email_data: EmailData) -> Optional[FootlockerOrderData]:
        """
        Parse Footlocker order confirmation email.
        
        Args:
            email_data: EmailData object containing email information
        
        Returns:
            FootlockerOrderData object or None if parsing fails
        """
        try:
            html_content = email_data.html_content
            
            if not html_content:
                logger.error("No HTML content in email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extract order number
            order_number = self._extract_order_number(soup)
            if not order_number:
                logger.error("Failed to extract order number from Foot Locker email")
                return None
            
            logger.info(f"Extracted Foot Locker order number: {order_number}")
            
            # Extract items using BeautifulSoup
            items = self._extract_items(soup)
            
            if not items:
                logger.error("Failed to extract any items from Foot Locker email")
                return None
            
            logger.info(f"Successfully extracted {len(items)} items from Foot Locker order {order_number}")
            for item in items:
                logger.debug(f"  - {item}")
            
            # Extract shipping address
            shipping_address = self._extract_shipping_address(soup)
            if shipping_address:
                logger.info(f"Extracted shipping address: {shipping_address}")

            # Extract purchase date/time (e.g. "Purchase date: December 29, 2025")
            order_datetime = self._extract_purchase_datetime(soup)
            if order_datetime:
                logger.info(f"Extracted purchase datetime: {order_datetime}")
            
            return FootlockerOrderData(order_number=order_number, items=items, shipping_address=shipping_address, order_datetime=order_datetime)
        
        except Exception as e:
            logger.error(f"Error parsing Footlocker order: {e}", exc_info=True)
            return None
    
    def _extract_order_number(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract order number from email using BeautifulSoup.
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            Order number (e.g., P1234567890123456789) or None
        """
        try:
            # Method 1: Look for spans or elements containing "Order:" text
            order_elements = soup.find_all(string=re.compile(r'Order[:\s]+', re.IGNORECASE))
            
            for element in order_elements:
                # Get the parent element to see the full context
                parent = element.parent
                if parent:
                    parent_text = parent.get_text()
                    # Look for the order number pattern in the parent text
                    match = re.search(r'Order[:\s]+([P]\d{19})', parent_text, re.IGNORECASE)
                    if match:
                        return match.group(1)
            
            # Method 2: Look for spans that might contain the order number
            spans = soup.find_all('span')
            for span in spans:
                span_text = span.get_text(strip=True)
                # Check if this span contains an order number pattern
                if re.match(r'^P\d{19}$', span_text):
                    return span_text
            
            # Method 3: Fallback to regex on full text (as last resort)
            text = soup.get_text()
            match = re.search(r'Order[:\s]+([P]\d{19})', text, re.IGNORECASE)
            if match:
                return match.group(1)
            
            logger.warning("Order number not found in email")
            return None
        
        except Exception as e:
            logger.error(f"Error extracting order number: {e}")
            return None

    def _extract_purchase_datetime(self, soup: BeautifulSoup) -> Optional[datetime]:
        """
        Extract purchase date from email (e.g. "Purchase date: December 29, 2025").
        Returns datetime at noon to avoid timezone edge cases when only date is available.
        """
        try:
            text = soup.get_text()
            # Pattern: "Purchase date: December 29, 2025" or "Purchase date: November 13, 2025"
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
    
    def _extract_items(self, soup: BeautifulSoup) -> List[FootlockerOrderItem]:
        """
        Extract order items using BeautifulSoup.
        
        BEST PRACTICE: Based on actual HTML structure analysis:
        - Product images are in separate containers
        - Size/quantity data is in the main document with patterns like "Size07.0" and "Qty1"
        - Product names are in links with target="_blank"
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            List of FootlockerOrderItem objects
        """
        items = []
        
        try:
            # Find all images with EBFL2 in the src (product images)
            product_images = soup.find_all('img', src=re.compile(r'/EBFL2/'))
            
            logger.debug(f"Found {len(product_images)} product images")
            
            # Track which size/quantity pairs we've used to avoid duplicates
            used_size_quantity = set()
            
            for img in product_images:
                try:
                    # Extract unique ID from image URL
                    img_src = img.get('src', '')
                    
                    # Handle Gmail proxy URLs - extract actual URL after #
                    if "#" in img_src:
                        parts = img_src.split("#")
                        if len(parts) > 1:
                            img_src = parts[-1]
                    
                    # Try to extract from image URL pattern: /EBFL2/Z5916400 or /is/image/EBFL2/Z5916400
                    unique_id_match = re.search(r'(?:/EBFL2/|/is/image/EBFL2/)([A-Z0-9]+)', img_src)
                    
                    unique_id = None
                    if unique_id_match:
                        unique_id = unique_id_match.group(1)
                    else:
                        # Fallback: Try to extract from product link URL if available
                        # Find product link near the image
                        product_link = self._find_product_link_near_image(img)
                        if product_link:
                            # Extract from URL pattern: /product/.../Z5916400.html
                            link_match = re.search(r'/product/[^/]+/([A-Z0-9]+)\.html', product_link)
                            if link_match:
                                unique_id = link_match.group(1)
                                logger.debug(f"Extracted unique ID from product link: {unique_id}")
                    
                    if not unique_id:
                        logger.warning(f"Could not extract unique ID from image: {img_src}")
                        continue
                    
                    # Extract product name from the image's container
                    product_name = self._extract_product_name_from_image(img)
                    
                    # Find matching size and quantity based on DOM structure (same product container)
                    size, quantity = self._find_size_quantity_for_image(img, used_size_quantity)
                    
                    # Mark this size/quantity pair as used
                    if size and quantity:
                        used_size_quantity.add((size, quantity))
                    
                    # Validate and create item
                    if size and quantity and self._is_valid_size(size) and self._is_valid_quantity(quantity):
                        items.append(FootlockerOrderItem(
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
        
        # Log items with ID, size, and quantity (product names come from OA Sourcing table)
        if items:
            items_summary = [f"(ID: {item.unique_id}, Size: {item.size}, Qty: {item.quantity})" for item in items]
            logger.info(f"[Footlocker] Extracted {len(items)} items: {', '.join(items_summary)}")
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
                    
                    # Check for quantity pattern: "Qty1" -> extract "1"
                    if 'Qty' in parent_text and self._is_valid_quantity(span_text):
                        size_quantity_data.append({
                            'type': 'quantity',
                            'value': span_text,
                            'context': parent_text,
                            'element': span
                        })
                        logger.debug(f"Found quantity: {span_text}")
            
            return size_quantity_data
            
        except Exception as e:
            logger.error(f"Error extracting size/quantity data: {e}")
            return []
    
    def _extract_product_name_from_image(self, img) -> str:
        """Extract product name from the image's container - improved version"""
        try:
            # Method 0: Check image alt text first (often contains product name)
            img_alt = img.get('alt', '').strip()
            if img_alt and len(img_alt) > 10 and len(img_alt) < 200:
                # Skip if alt text is generic
                skip_alts = ['product image', 'image', 'photo', 'picture']
                if img_alt.lower() not in skip_alts:
                    logger.debug(f"[Footlocker] Found product name from image alt: {img_alt[:50]}")
                    return img_alt
            
            # Find the container of the image - go up multiple levels
            containers_to_check = []
            
            # Try immediate parent first
            parent = img.find_parent()
            if parent:
                containers_to_check.append(parent)
            
            # Try td/tr/table ancestors (Footlocker uses tables)
            for tag in ['td', 'tr', 'table', 'div']:
                ancestor = img.find_parent(tag)
                if ancestor and ancestor not in containers_to_check:
                    containers_to_check.append(ancestor)
            
            # Method 1: Look for links with text longer than 10 characters
            # But prioritize links that are AFTER the image in the DOM
            for container in containers_to_check:
                links = container.find_all('a')
                for link in links:
                    link_text = link.get_text(strip=True)
                    # Product names are usually substantial text
                    if link_text and len(link_text) > 10 and len(link_text) < 200:
                        # Skip common link text that isn't product names
                        skip_texts = ['view', 'details', 'shop now', 'buy now', 'add to cart', 
                                     'track order', 'return', 'exchange', 'view order', 
                                     'check order status', 'order status', 'track your order']
                        link_lower = link_text.lower()
                        if link_lower not in skip_texts:
                            # Check if this link comes after the image in the DOM
                            # (product name links are usually after the image)
                            img_pos = None
                            link_pos = None
                            for i, elem in enumerate(container.find_all(['img', 'a'])):
                                if elem == img:
                                    img_pos = i
                                if elem == link:
                                    link_pos = i
                            
                            # Prefer links that come after the image
                            if link_pos is not None and (img_pos is None or link_pos > img_pos):
                                logger.debug(f"[Footlocker] Found product name from link (after image): {link_text[:50]}")
                                return link_text
                            elif img_pos is None:  # If we can't determine position, still use it
                                logger.debug(f"[Footlocker] Found product name from link: {link_text[:50]}")
                                return link_text
            
            # Method 2: Look for text in <td> or <div> elements containing the image
            # Focus on elements that come after the image
            for container in containers_to_check[:3]:  # Check first 3 ancestors
                # Find all text elements in the container
                all_elems = container.find_all(['td', 'div', 'span', 'p', 'a'])
                img_found = False
                
                for elem in all_elems:
                    # Check if we've passed the image
                    if img in elem.find_all('img'):
                        img_found = True
                        continue
                    
                    # After finding the image, look for product name text
                    if img_found:
                        text = elem.get_text(strip=True)
                        # Look for substantial text that looks like a product name
                        if text and 15 < len(text) < 200:
                            # Skip if it looks like size/quantity/price/generic text
                            if not re.search(r'^(Size|Qty|Quantity|Price|Total|Subtotal|Order|Shipping|Check)', text, re.IGNORECASE):
                                # Skip if it's mostly numbers or currency
                                if not re.search(r'^\$[\d,]+\.?\d*$', text):
                                    # Skip if it contains only size/qty patterns
                                    if not re.match(r'^(Size\s*\d+|Qty\s*\d+)$', text, re.IGNORECASE):
                                        logger.debug(f"[Footlocker] Found product name from text (after image): {text[:50]}")
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
                        # Skip "CHECK ORDER STATUS" and similar
                        if not re.search(r'^(Size|Qty|Quantity|Price|\$|Order|Check|Shipping)', part, re.IGNORECASE):
                            if not re.match(r'^[\d,]+\.?\d*$', part):
                                # Check if it looks like a product name (contains brand/model info)
                                if re.search(r'(Nike|Adidas|Jordan|Puma|Reebok|New Balance|Men|Women|Kids|Boys|Girls)', part, re.IGNORECASE):
                                    logger.debug(f"[Footlocker] Found product name from table row: {part[:50]}")
                                    return part
            
            logger.debug(f"[Footlocker] Could not extract product name from image: {img.get('src', '')[:50]}")
            return "Unknown Product"
            
        except Exception as e:
            logger.warning(f"[Footlocker] Error extracting product name from image: {e}")
            return "Unknown Product"
    
    def _find_matching_size_quantity(self, unique_id: str, size_quantity_data: List[dict]) -> tuple:
        """
        Find matching size and quantity data for a product.
        
        Args:
            unique_id: The unique ID of the product
            size_quantity_data: List of size/quantity data from the document
        
        Returns:
            Tuple of (size, quantity) or (None, None) if not found
        """
        try:
            # BEST PRACTICE: Match size and quantity based on their proximity in the HTML
            # Find pairs of size and quantity that are close to each other
            
            size = None
            quantity = None
            
            # Group size and quantity data by their proximity
            size_quantity_pairs = []
            
            for i, item in enumerate(size_quantity_data):
                if item['type'] == 'size':
                    # Look for a nearby quantity
                    for j, other_item in enumerate(size_quantity_data):
                        if (other_item['type'] == 'quantity' and 
                            abs(i - j) <= 2):  # Within 2 positions
                            size_quantity_pairs.append({
                                'size': item['value'],
                                'quantity': other_item['value'],
                                'distance': abs(i - j)
                            })
                            break
            
            # If we found pairs, use the first one (closest match)
            if size_quantity_pairs:
                # Sort by distance to get the closest match
                size_quantity_pairs.sort(key=lambda x: x['distance'])
                pair = size_quantity_pairs[0]
                size = pair['size']
                quantity = pair['quantity']
                logger.debug(f"Matched size {size} and quantity {quantity} for {unique_id}")
            else:
                # Fallback: use first available size and quantity
                for item in size_quantity_data:
                    if item['type'] == 'size' and not size:
                        size = item['value']
                    if item['type'] == 'quantity' and not quantity:
                        quantity = item['value']
            
            return size, quantity
            
        except Exception as e:
            logger.error(f"Error finding matching size/quantity: {e}")
            return None, None
    
    def _find_size_quantity_for_image(self, img, used_size_quantity: set) -> tuple:
        """
        Find size and quantity for a product image based on DOM structure.
        
        Each product is in a 'fluid-row' table container. The Size and Qty
        for that product are in the same container, in separate table blocks
        that come after the product name.
        
        Args:
            img: BeautifulSoup img element
            used_size_quantity: Set of already used (size, quantity) pairs
        
        Returns:
            Tuple of (size, quantity) or (None, None) if not found
        """
        try:
            # Find the parent 'fluid-row' table that contains this product
            # This is the container for each product item
            # Note: The class name may have a prefix like "m_6874873034578858600fluid-row"
            fluid_row = img.find_parent('table', class_=re.compile(r'fluid-row'))
            
            if not fluid_row:
                # Fallback: try to find any table ancestor that contains both image and product details
                # Look for parent table that contains both col-3 (image) and col-9 (product details)
                parent_table = img.find_parent('table')
                if parent_table:
                    # Check if this table or its parent contains product details
                    parent_tables = [parent_table]
                    grandparent = parent_table.find_parent('table')
                    if grandparent:
                        parent_tables.append(grandparent)
                    
                    for table in parent_tables:
                        # Check if this table contains both image and size/qty info
                        has_image = bool(table.find('img', src=re.compile(r'/EBFL2/')))
                        has_size_qty = bool(re.search(r'Size|Qty', table.get_text(), re.IGNORECASE))
                        if has_image and has_size_qty:
                            fluid_row = table
                            break
            
            # If still not found, look for table containing col-3 and col-9
            if not fluid_row:
                # Find the col-3 table (image container)
                col3_table = img.find_parent('table', class_=re.compile(r'col-3'))
                if col3_table:
                    # Find the parent that contains both col-3 and col-9
                    parent = col3_table.find_parent('table')
                    if parent:
                        # Check if this parent contains col-9 (product details)
                        col9_table = parent.find('table', class_=re.compile(r'col-9'))
                        if col9_table:
                            fluid_row = parent
            
            if not fluid_row:
                logger.warning("Could not find product container for image")
                return None, None
            
            logger.debug(f"Found product container: {fluid_row.get('class', [])}")
            
            # Within this product container, find Size and Qty
            # They are in spans with parent text containing "Size" or "Qty"
            size = None
            quantity = None
            
            # Find all spans in this container
            # In cancellation emails, size and quantity are in spans within td elements
            # Structure: <td> Size <span> 10.0</span> </td> and <td> Qty <span> 2</span> </td>
            spans = fluid_row.find_all('span')
            
            logger.debug(f"Searching {len(spans)} spans in container for size/quantity")
            
            for span in spans:
                span_text = span.get_text(strip=True)
                
                # Skip empty spans
                if not span_text:
                    continue
                
                # Check if this span contains a valid size or quantity value
                is_size = self._is_valid_size(span_text)
                is_quantity = self._is_valid_quantity(span_text)
                
                if not (is_size or is_quantity):
                    continue
                
                # Check parent elements (td, tr, etc.) for "Size" or "Qty" text
                # The structure is: <td> Size <span> 10.0</span> </td>
                # So the parent <td> contains "Size" text and the span contains "10.0"
                parent = span.parent
                parent_text = ""
                
                # Walk up the DOM tree to find context (check up to 5 levels)
                current = parent
                for level in range(5):
                    if current:
                        current_text = current.get_text(strip=True)
                        current_text_upper = current_text.upper()
                        # Check case-insensitively: some emails use "QTY" vs "Qty"
                        if 'SIZE' in current_text_upper or 'QTY' in current_text_upper:
                            parent_text = current_text
                            logger.debug(f"Found context at level {level} for span '{span_text}': {parent_text[:60]}")
                            break
                        # Move up to next parent element
                        current = current.find_parent(['td', 'tr', 'table', 'div'])
                    else:
                        break
                
                # If we didn't find context, check the immediate parent
                if not parent_text and parent:
                    parent_text = parent.get_text(strip=True)
                
                parent_text_upper = parent_text.upper()
                # Check for size - must be valid and parent should contain "Size" (case-insensitive)
                if is_size and 'SIZE' in parent_text_upper:
                    size = span_text
                    logger.debug(f"Found size: {size} (from parent: {parent_text[:50]})")
                
                # Check for quantity - must be valid and parent should contain "Qty"/"QTY" (case-insensitive)
                if is_quantity and 'QTY' in parent_text_upper:
                    quantity = span_text
                    logger.debug(f"Found quantity: {quantity} (from parent: {parent_text[:50]})")
            
            # If we found both, check if this pair is already used
            if size and quantity:
                pair = (size, quantity)
                if pair in used_size_quantity:
                    logger.debug(f"Size/quantity pair ({size}, {quantity}) already used, skipping")
                    return None, None
                logger.debug(f"Matched size {size} and quantity {quantity} for image")
                return size, quantity
            
            # If we only found one, return what we have (might be incomplete)
            if size or quantity:
                logger.warning(f"Found incomplete data: size={size}, quantity={quantity}")
            
            return size, quantity
            
        except Exception as e:
            logger.error(f"Error finding size/quantity for image: {e}")
            return None, None
    
    def _find_matching_size_quantity_advanced(
        self, 
        unique_id: str, 
        size_quantity_data: List[dict], 
        used_size_quantity: set
    ) -> tuple:
        """
        DEPRECATED: Use _find_size_quantity_for_image instead.
        Kept for backward compatibility but should not be used.
        
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
    
    def _extract_size_and_quantity(self, detail_section: BeautifulSoup) -> tuple:
        """
        Extract size and quantity using BeautifulSoup DOM traversal.
        Based on actual HTML structure analysis.
        
        Args:
            detail_section: BeautifulSoup object containing the product details
        
        Returns:
            Tuple of (size, quantity) or (None, None) if not found
        """
        size = None
        quantity = None
        
        try:
            # BEST PRACTICE: Use the actual HTML structure we discovered
            # The data is in spans with "Size" and "Qty" text in parent elements
            
            # Method 1: Find all spans and check their parent context
            spans = detail_section.find_all('span')
            
            for span in spans:
                span_text = span.get_text(strip=True)
                parent = span.parent
                
                if parent:
                    parent_text = parent.get_text(strip=True)
                    
                    # Check for size pattern: "Size07.0" -> extract "07.0"
                    if 'Size' in parent_text and self._is_valid_size(span_text):
                        size = span_text
                        logger.debug(f"Found size: {size} in parent: {parent_text[:50]}...")
                    
                    # Check for quantity pattern: "Qty1" -> extract "1"
                    if 'Qty' in parent_text and self._is_valid_quantity(span_text):
                        quantity = span_text
                        logger.debug(f"Found quantity: {quantity} in parent: {parent_text[:50]}...")
            
            # Method 2: If not found, look for text patterns in the entire section
            if not size or not quantity:
                section_text = detail_section.get_text()
                
                # Look for size pattern like "Size07.0" or "Size 7.0"
                size_match = re.search(r'Size\s*(\d+(?:\.\d+)?)', section_text, re.IGNORECASE)
                if size_match:
                    size = size_match.group(1)
                    logger.debug(f"Found size via regex: {size}")
                
                # Look for quantity pattern like "Qty1" or "Qty 1"
                qty_match = re.search(r'Qty\s*(\d+)', section_text, re.IGNORECASE)
                if qty_match:
                    quantity = qty_match.group(1)
                    logger.debug(f"Found quantity via regex: {quantity}")
            
            logger.debug(f"Final extracted - size: {size}, quantity: {quantity}")
            return size, quantity
            
        except Exception as e:
            logger.error(f"Error extracting size and quantity: {e}")
            return None, None
    
    def parse_shipping_email(self, email_data: EmailData) -> Optional[FootlockerShippingData]:
        """
        Parse Footlocker shipping notification email.
        
        Args:
            email_data: EmailData object containing email information
        
        Returns:
            FootlockerShippingData object or None if parsing fails
        """
        try:
            html_content = email_data.html_content
            
            if not html_content:
                logger.error("No HTML content in email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extract order number
            order_number = self._extract_order_number(soup)
            if not order_number:
                logger.error("Failed to extract order number from Footlocker shipping email")
                return None
            
            # Extract tracking number
            tracking_number = self._extract_tracking_number(soup)
            if not tracking_number:
                logger.warning("Failed to extract tracking number from Footlocker shipping email")
                tracking_number = "Unknown"
            
            logger.info(f"Extracted Footlocker shipping - Order: {order_number}, Tracking: {tracking_number}")
            
            # Extract items using BeautifulSoup
            items = self._extract_items(soup)
            
            if not items:
                logger.error("Failed to extract any items from Footlocker shipping email")
                return None
            
            logger.info(f"Successfully extracted {len(items)} items from Footlocker shipping notification")
            for item in items:
                logger.debug(f"  - {item}")
            
            return FootlockerShippingData(
                order_number=order_number,
                tracking_number=tracking_number,
                items=items
            )
        
        except Exception as e:
            logger.error(f"Error parsing Footlocker shipping email: {e}", exc_info=True)
            return None
    
    def parse_cancellation_email(self, email_data: EmailData) -> Optional[FootlockerCancellationData]:
        """
        Parse Footlocker cancellation notification email.
        
        Args:
            email_data: EmailData object containing email information
        
        Returns:
            FootlockerCancellationData object or None if parsing fails
        """
        try:
            html_content = email_data.html_content
            
            if not html_content:
                logger.error("No HTML content in email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extract order number
            order_number = self._extract_order_number(soup)
            if not order_number:
                logger.error("Failed to extract order number from Footlocker cancellation email")
                return None
            
            logger.info(f"Extracted Footlocker cancellation - Order: {order_number}")
            
            # Extract items using BeautifulSoup
            items = self._extract_items(soup)
            
            if not items:
                logger.error("Failed to extract any items from Footlocker cancellation email")
                return None
            
            logger.info(f"Successfully extracted {len(items)} items from Footlocker cancellation notification")
            for item in items:
                logger.debug(f"  - {item}")
            
            return FootlockerCancellationData(
                order_number=order_number,
                items=items
            )
        
        except Exception as e:
            logger.error(f"Error parsing Footlocker cancellation email: {e}", exc_info=True)
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
                    # UPS: 1Z...
                    match = re.search(r'1Z[A-Z0-9]{16}', parent_text, re.IGNORECASE)
                    if match:
                        return match.group(0)
                    
                    # FedEx: 12-14 digits
                    match = re.search(r'\b\d{12,14}\b', parent_text)
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
            
            logger.warning("Tracking number not found in email")
            return None
        
        except Exception as e:
            logger.error(f"Error extracting tracking number: {e}")
            return None
    
    def _is_valid_size(self, size: str) -> bool:
        """Check if a value looks like a valid shoe size"""
        # Decimal sizes like "06.0", "10.5", "14.0"
        if re.match(r'^\d{1,2}\.\d$', size):
            return True
        
        # Single digit sizes like "8", "9"
        if re.match(r'^\d{1,2}$', size):
            num = int(size)
            return num > 0
        
        # Youth sizes like "5Y", "12Y", "13.5Y"
        if re.match(r'^\d{1,2}(\.\d)?Y$', size, re.IGNORECASE):
            return True
        
        # Toddler sizes like "5T", "10T"
        if re.match(r'^\d{1,2}T$', size, re.IGNORECASE):
            return True
        
        # Infant sizes like "5C", "10C"
        if re.match(r'^\d{1,2}C$', size, re.IGNORECASE):
            return True
        
        # Wide sizes like "10W", "11.5W"
        if re.match(r'^\d{1,2}(\.\d)?W$', size, re.IGNORECASE):
            return True
        
        # Letter sizes
        if re.match(r'^[SMLX]+$', size, re.IGNORECASE):
            return True
        
        # OS (One Size)
        if re.match(r'^OS(FM)?$', size, re.IGNORECASE):
            return True
        
        return False
    
    def _is_valid_quantity(self, quantity: str) -> bool:
        """Check if a value looks like a valid quantity"""
        if not re.match(r'^\d+$', quantity):
            return False
        
        num = int(quantity)
        return 1 <= num <= 20  # Reasonable quantity range
    
    def _clean_size(self, size: str) -> str:
        """Clean up size format (remove leading zeros)"""
        # Convert "06.0" to "6", "09.5" to "9.5", "14.0" to "14", etc.
        if re.match(r'^\d{1,2}\.\d$', size):
            num = float(size)
            # Remove .0 if it's a whole number
            return str(int(num)) if num % 1 == 0 else str(num)
        
        return size
    
    def _extract_shipping_address(self, soup: BeautifulSoup) -> str:
        """
        Extract shipping address from email and normalize it.
        
        Footlocker email structure:
        - "SHIPPING TO:" header
        - Name (e.g., "Griffin Myers")
        - Street address + city/state/zip (e.g., "595 LLOYD LN STE D Ste D, INDEPENDENCE, OR 97351-2125")
        
        We want to extract just the street address part and normalize it.
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            Normalized shipping address or empty string
        """
        try:
            text = soup.get_text()
            
            # Method 1: Look for "SHIPPING TO:" section and extract street address
            shipping_match = re.search(
                r'SHIPPING\s+TO:?\s*(.*?)(?:ORDER\s+SUMMARY|PAYMENT|$)',
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
                                # Footlocker format: "595 LLOYD LN STE D Ste D, INDEPENDENCE, OR 97351-2125"
                                # We want: "595 LLOYD LN STE D Ste D" -> normalized to "595 Lloyd Lane"
                                
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
                                    logger.debug(f"Extracted Footlocker shipping address: {line} -> {street_line} -> {normalized}")
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
                    logger.debug(f"Extracted Footlocker shipping address (pattern): {street_line} -> {normalized}")
                    return normalized
            
            # Method 3: Look for "2025 Vista" pattern
            vista_match = re.search(r'(2025\s+Vista\s+Ave[^,\n]*(?:,\s*[A-Z\s]+)?)', text, re.IGNORECASE)
            if vista_match:
                street_line = vista_match.group(1).strip()
                # Remove city/state/zip if present
                street_line = re.sub(r',\s*[A-Z][A-Z\s]+,?\s*[A-Z]{2}\s*\d{5}.*$', '', street_line).strip()
                normalized = normalize_shipping_address(street_line)
                if normalized:
                    logger.debug(f"Extracted Footlocker shipping address (pattern): {street_line} -> {normalized}")
                    return normalized
            
            return ""
        
        except Exception as e:
            logger.error(f"Error extracting shipping address: {e}")
            return ""
    
    def _find_product_link_near_image(self, img) -> Optional[str]:
        """
        Find product link URL near an image element.
        
        Args:
            img: BeautifulSoup img element
        
        Returns:
            Product link URL or None
        """
        try:
            # Find the parent container (table row or div)
            parent = img.find_parent(['tr', 'td', 'div', 'table'])
            
            if not parent:
                return None
            
            # Look for links with footlocker.com/product in the same container
            links = parent.find_all('a', href=re.compile(r'footlocker\.com.*product'))
            
            for link in links:
                href = link.get('href', '')
                # Handle Gmail proxy URLs
                if "#" in href:
                    parts = href.split("#")
                    if len(parts) > 1:
                        href = parts[-1]
                
                # Check if this looks like a product link
                if '/product/' in href and '.html' in href:
                    return href
            
            return None
            
        except Exception as e:
            logger.debug(f"Error finding product link near image: {e}")
            return None

