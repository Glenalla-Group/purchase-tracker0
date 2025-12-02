"""
Champs Sports Email Parser
Parses order confirmation emails from Champs Sports using BeautifulSoup
"""

import logging
import re
from typing import List, Optional
from bs4 import BeautifulSoup

from app.models.email import EmailData

logger = logging.getLogger(__name__)


class ChampsOrderItem:
    """Represents a single item from a Champs Sports order"""
    
    def __init__(self, unique_id: str, size: str, quantity: int, product_name: str = None):
        self.unique_id = unique_id    # Unique ID from image URL or product code
        self.size = size
        self.quantity = quantity
        self.product_name = product_name or "Unknown Product"
    
    def __repr__(self):
        return f"<ChampsOrderItem(unique_id={self.unique_id}, size={self.size}, qty={self.quantity})>"


class ChampsOrderData:
    """Represents a complete Champs Sports order"""
    
    def __init__(self, order_number: str, items: List[ChampsOrderItem]):
        self.order_number = order_number
        self.items = items
    
    def __repr__(self):
        return f"<ChampsOrderData(order_number={self.order_number}, items_count={len(self.items)})>"


class ChampsEmailParser:
    """
    Parser for Champs Sports order confirmation emails using BeautifulSoup.
    
    Handles email formats like:
    From: accountservices@em.champssports.com
    Subject: "Thank you for your order, [name]"
    """
    
    # Email identification patterns
    CHAMPS_FROM_EMAIL = "accountservices@em.champssports.com"
    CHAMPS_FROM_PATTERN = r"champs"
    SUBJECT_ORDER_PATTERN = r"Thank you for your order"
    
    def __init__(self):
        """Initialize the Champs email parser."""
        pass
    
    def is_champs_email(self, email_data: EmailData) -> bool:
        """Check if email is from Champs Sports"""
        sender_lower = email_data.sender.lower()
        
        if self.CHAMPS_FROM_EMAIL.lower() in sender_lower:
            return True
        
        if re.search(self.CHAMPS_FROM_PATTERN, sender_lower, re.IGNORECASE):
            return True
        
        return False
    
    def is_order_confirmation_email(self, email_data: EmailData) -> bool:
        """Check if email is an order confirmation"""
        subject_lower = email_data.subject.lower()
        
        if re.search(self.SUBJECT_ORDER_PATTERN, subject_lower, re.IGNORECASE):
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
            
            return ChampsOrderData(order_number=order_number, items=items)
        
        except Exception as e:
            logger.error(f"Error parsing Champs order: {e}", exc_info=True)
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
                    # Look for order number patterns in the parent text
                    match = re.search(r'Order[:\s]+([A-Z0-9]+)', parent_text, re.IGNORECASE)
                    if match:
                        return match.group(1)
            
            # Method 2: Look for spans that might contain the order number
            spans = soup.find_all('span')
            for span in spans:
                span_text = span.get_text(strip=True)
                # Check if this span contains an order number pattern
                if re.match(r'^[A-Z0-9]{8,20}$', span_text):
                    return span_text
            
            # Method 3: Fallback to regex on full text (as last resort)
            text = soup.get_text()
            match = re.search(r'Order[:\s]+([A-Z0-9]+)', text, re.IGNORECASE)
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
        
        Champs Sports structure analysis:
        - Product names: "Brooks Ghost 16 - Men's" in links
        - Unique IDs: "4181D090" in image URLs (https://images.footlocker.com/is/image/EBFL2/4181D090)
        - Sizes: "08.5", "09.0" in spans
        - Quantities: "1" in spans
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            List of ChampsOrderItem objects
        """
        items = []
        
        try:
            # Find all product images with unique IDs
            product_images = soup.find_all('img', src=re.compile(r'/EBFL2/([A-Z0-9]+)'))
            logger.debug(f"Found {len(product_images)} product images with unique IDs")
            
            # Extract all size and quantity data from the document
            size_quantity_data = self._extract_all_size_quantity_data(soup)
            logger.debug(f"Found {len(size_quantity_data)} size/quantity entries")
            
            # Track used size/quantity pairs to avoid duplicates
            used_size_quantity = set()
            
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
            
            # Also look for alt text on the image itself
            alt_text = img.get('alt', '')
            if alt_text and len(alt_text) > 5:
                return alt_text
            
            return "Unknown Product"
            
        except Exception as e:
            logger.error(f"Error extracting product name: {e}")
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
        """Check if size is valid (numeric with optional decimal)"""
        try:
            # Remove any non-numeric characters except decimal point
            clean_size = re.sub(r'[^\d.]', '', size)
            if not clean_size:
                return False
            
            # Convert to float and check range
            size_num = float(clean_size)
            return 2.0 <= size_num <= 20.0  # Reasonable shoe size range
            
        except (ValueError, TypeError):
            return False
    
    def _is_valid_quantity(self, quantity: str) -> bool:
        """Check if quantity is valid (positive integer)"""
        try:
            qty = int(quantity)
            return 1 <= qty <= 10  # Reasonable quantity range
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
