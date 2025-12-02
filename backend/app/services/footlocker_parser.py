"""
Footlocker Order Confirmation Email Parser
Extracts order details from Footlocker confirmation emails using BeautifulSoup
"""

import logging
import re
from typing import List, Optional
from bs4 import BeautifulSoup, Tag

from app.models.email import EmailData

logger = logging.getLogger(__name__)


class FootlockerOrderItem:
    """Represents a single item from a Footlocker order"""
    
    def __init__(self, unique_id: str, size: str, quantity: int, product_name: str = None):
        self.unique_id = unique_id    # Unique ID from image URL (e.g., 64033WWH, 6197725)
        self.size = size
        self.quantity = quantity
        self.product_name = product_name or "Unknown Product"
    
    def __repr__(self):
        return f"<FootlockerOrderItem(unique_id={self.unique_id}, size={self.size}, qty={self.quantity})>"


class FootlockerOrderData:
    """Represents complete Footlocker order data"""
    
    def __init__(self, order_number: str, items: List[FootlockerOrderItem]):
        self.order_number = order_number
        self.items = items
    
    def __repr__(self):
        return f"<FootlockerOrderData(order={self.order_number}, items={len(self.items)})>"


class FootlockerEmailParser:
    """
    Parser for Footlocker order confirmation emails using BeautifulSoup.
    
    Handles email formats like:
    From: accountservices@em.footlocker.com
    Subject: "Thank you for your order, [name]"
    Content: Contains order number, product info with images, sizes, and quantities
    """
    
    # Email identification
    FOOTLOCKER_FROM_EMAIL = "accountservices@em.footlocker.com"
    FOOTLOCKER_FROM_PATTERN = r"footlocker"
    SUBJECT_ORDER_PATTERN = r"Thank you for your order"
    
    def __init__(self):
        """Initialize the Footlocker email parser."""
        pass
    
    def is_footlocker_email(self, email_data: EmailData) -> bool:
        """
        Check if email is from Footlocker.
        
        Args:
            email_data: EmailData object
        
        Returns:
            True if email is from Footlocker, False otherwise
        """
        sender_lower = email_data.sender.lower()
        
        # Check for direct email or "Footlocker" in sender name
        if self.FOOTLOCKER_FROM_EMAIL.lower() in sender_lower:
            return True
        
        if re.search(self.FOOTLOCKER_FROM_PATTERN, sender_lower, re.IGNORECASE):
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
        
        if re.search(self.SUBJECT_ORDER_PATTERN, subject_lower, re.IGNORECASE):
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
            
            return FootlockerOrderData(order_number=order_number, items=items)
        
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
            
            # Extract all size and quantity data from the document first
            size_quantity_data = self._extract_all_size_quantity_data(soup)
            logger.debug(f"Found {len(size_quantity_data)} size/quantity entries")
            
            # Create a better matching system - match products with their specific size/quantity
            used_size_quantity = set()  # Track which size/quantity pairs we've used
            
            for img in product_images:
                try:
                    # Extract unique ID from image URL
                    img_src = img.get('src', '')
                    unique_id_match = re.search(r'/EBFL2/([A-Z0-9]+)', img_src)
                    
                    if not unique_id_match:
                        logger.warning(f"Could not extract unique ID from image: {img_src}")
                        continue
                    
                    unique_id = unique_id_match.group(1)
                    
                    # Extract product name from the image's container
                    product_name = self._extract_product_name_from_image(img)
                    
                    # Find matching size and quantity data (avoid reusing the same pair)
                    size, quantity = self._find_matching_size_quantity_advanced(
                        unique_id, size_quantity_data, used_size_quantity
                    )
                    
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
        
        logger.info(f"Items: {items}")
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
        """Extract product name from the image's container"""
        try:
            # Find the container of the image
            container = img.find_parent()
            if not container:
                return "Unknown Product"
            
            # Look for links with target="_blank" in the container
            links = container.find_all('a', target="_blank")
            for link in links:
                link_text = link.get_text(strip=True)
                if link_text and len(link_text) > 5:  # Filter out short text
                    return link_text
            
            return "Unknown Product"
            
        except Exception as e:
            logger.error(f"Error extracting product name: {e}")
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
    
    def _is_valid_size(self, size: str) -> bool:
        """Check if a value looks like a valid shoe size"""
        # Decimal sizes like "06.0", "10.5", "14.0"
        if re.match(r'^\d{1,2}\.\d$', size):
            return True
        
        # Single digit sizes like "8", "9"
        if re.match(r'^\d{1,2}$', size):
            num = int(size)
            return 4 <= num <= 18
        
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

