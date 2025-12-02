"""
Dick's Sporting Goods Email Parser
Parses order confirmation emails from Dick's Sporting Goods using BeautifulSoup
"""

import logging
import re
from typing import List, Optional
from bs4 import BeautifulSoup

from app.models.email import EmailData

logger = logging.getLogger(__name__)


class DicksOrderItem:
    """Represents a single item from a Dick's Sporting Goods order"""
    
    def __init__(self, unique_id: str, size: str, quantity: int, product_name: str = None):
        self.unique_id = unique_id    # Unique ID from image URL or product code
        self.size = size
        self.quantity = quantity
        self.product_name = product_name or "Unknown Product"
    
    def __repr__(self):
        return f"<DicksOrderItem(unique_id={self.unique_id}, size={self.size}, qty={self.quantity})>"


class DicksOrderData:
    """Represents a complete Dick's Sporting Goods order"""
    
    def __init__(self, order_number: str, items: List[DicksOrderItem]):
        self.order_number = order_number
        self.items = items
    
    def __repr__(self):
        return f"<DicksOrderData(order_number={self.order_number}, items_count={len(self.items)})>"


class DicksEmailParser:
    """
    Parser for Dick's Sporting Goods order confirmation emails using BeautifulSoup.
    
    Handles email formats like:
    From: from@notifications.dcsg.com
    Subject: "Thank you for your order!"
    """
    
    # Email identification patterns
    DICKS_FROM_EMAIL = "from@notifications.dcsg.com"
    DICKS_FROM_PATTERN = r"dicks|dcsg"
    SUBJECT_ORDER_PATTERN = r"Thank you for your order"
    
    def __init__(self):
        """Initialize the Dick's email parser."""
        pass
    
    def is_dicks_email(self, email_data: EmailData) -> bool:
        """Check if email is from Dick's Sporting Goods"""
        sender_lower = email_data.sender.lower()
        
        if self.DICKS_FROM_EMAIL.lower() in sender_lower:
            return True
        
        if re.search(self.DICKS_FROM_PATTERN, sender_lower, re.IGNORECASE):
            return True
        
        return False
    
    def is_order_confirmation_email(self, email_data: EmailData) -> bool:
        """Check if email is an order confirmation"""
        subject_lower = email_data.subject.lower()
        
        if re.search(self.SUBJECT_ORDER_PATTERN, subject_lower, re.IGNORECASE):
            return True
        
        return False
    
    def parse_email(self, email_data: EmailData) -> Optional[DicksOrderData]:
        """
        Parse Dick's Sporting Goods order confirmation email.
        
        Args:
            email_data: EmailData object containing email information
        
        Returns:
            DicksOrderData object or None if parsing fails
        """
        try:
            html_content = email_data.html_content
            
            if not html_content:
                logger.error("No HTML content in Dick's email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extract order number
            order_number = self._extract_order_number(soup)
            if not order_number:
                logger.error("Failed to extract order number from Dick's email")
                return None
            
            logger.info(f"Extracted Dick's Sporting Goods order number: {order_number}")
            
            # Extract items using BeautifulSoup
            items = self._extract_items(soup)
            
            if not items:
                logger.error("Failed to extract any items from Dick's Sporting Goods email")
                return None
            
            logger.info(f"Successfully extracted {len(items)} items from Dick's Sporting Goods order {order_number}")
            for item in items:
                logger.debug(f"  - {item}")
            
            return DicksOrderData(order_number=order_number, items=items)
        
        except Exception as e:
            logger.error(f"Error parsing Dick's order: {e}", exc_info=True)
            return None
    
    def _extract_order_number(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract order number from Dick's email using BeautifulSoup.
        
        Dick's structure: Order number is in a link within the order summary section.
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            Order number or None
        """
        try:
            # Method 1: Look for the order number in the order summary section
            # The order number appears in a link with specific styling
            order_links = soup.find_all('a', href=re.compile(r'notifications\.dcsg\.com'))
            
            for link in order_links:
                link_text = link.get_text(strip=True)
                # Check if this looks like an order number (numeric, 8+ digits)
                if re.match(r'^\d{8,15}$', link_text):
                    logger.debug(f"Found order number in link: {link_text}")
                    return link_text
            
            # Method 2: Look for text that matches order number pattern
            # Dick's order numbers are typically 10-11 digits
            text = soup.get_text()
            order_match = re.search(r'\b(\d{8,15})\b', text)
            if order_match:
                potential_order = order_match.group(1)
                # Additional validation - make sure it's not a date or other number
                if len(potential_order) >= 8 and not re.match(r'^\d{4}$', potential_order):
                    logger.debug(f"Found order number in text: {potential_order}")
                    return potential_order
            
            logger.warning("Order number not found in Dick's email")
            return None
        
        except Exception as e:
            logger.error(f"Error extracting order number: {e}")
            return None
    
    def _extract_items(self, soup: BeautifulSoup) -> List[DicksOrderItem]:
        """
        Extract order items from Dick's Sporting Goods email.
        
        Dick's structure analysis:
        - Product names: In <a> tags with bold text
        - Unique IDs: In image URLs like dks.scene7.com/is/image/dkscdn/22MAZWCLDMNSTRCLVFTW
        - Sizes: In <p> tags with "Shoe Size" label
        - Quantities: Default to 1 if not specified
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            List of DicksOrderItem objects
        """
        items = []
        
        try:
            # Find all product images with Dick's specific pattern
            product_images = soup.find_all('img', src=re.compile(r'dks\.scene7\.com/is/image/dkscdn/'))
            logger.debug(f"Found {len(product_images)} Dick's product images")
            
            for img in product_images:
                try:
                    # Extract unique ID from image URL
                    img_src = img.get('src', '')
                    unique_id = self._extract_unique_id_from_dicks_image(img_src)
                    
                    if not unique_id:
                        logger.warning(f"Could not extract unique ID from image: {img_src}")
                        continue
                    
                    # Find the product container (table row containing this image)
                    product_container = self._find_product_container(img)
                    if not product_container:
                        logger.warning(f"Could not find product container for image: {img_src}")
                        continue
                    
                    # Extract product name from the container
                    product_name = self._extract_product_name_from_container(product_container)
                    
                    # Extract size from the container
                    size = self._extract_size_from_container(product_container)
                    
                    # Default quantity to 1 (Dick's doesn't always show quantity)
                    quantity = 1
                    
                    # Validate and create item
                    if size and self._is_valid_size(size):
                        items.append(DicksOrderItem(
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
    
    def _extract_unique_id_from_dicks_image(self, img_src: str) -> Optional[str]:
        """Extract unique ID from Dick's image URL"""
        try:
            # Dick's pattern: dks.scene7.com/is/image/dkscdn/22MAZWCLDMNSTRCLVFTW_White_Flame
            match = re.search(r'dkscdn/([A-Z0-9]+)_', img_src)
            if match:
                return match.group(1)
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting unique ID from Dick's image: {e}")
            return None
    
    def _find_product_container(self, img) -> Optional[BeautifulSoup]:
        """Find the product container (table row) for a given image"""
        try:
            # Navigate up to find the table row containing this image
            current = img.parent
            while current:
                if current.name == 'tr':
                    return current
                current = current.parent
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding product container: {e}")
            return None
    
    def _extract_product_name_from_container(self, container) -> str:
        """Extract product name from the product container"""
        try:
            # Look for bold text in links within the container
            links = container.find_all('a')
            for link in links:
                bold_text = link.find('b')
                if bold_text:
                    # Clean up the text by removing extra whitespace and newlines
                    product_name = bold_text.get_text(strip=True)
                    # Replace multiple whitespace/newlines with single space
                    product_name = re.sub(r'\s+', ' ', product_name)
                    return product_name.strip()
            
            # Fallback: look for any bold text in the container
            bold_elements = container.find_all('b')
            for bold in bold_elements:
                text = bold.get_text(strip=True)
                if text and len(text) > 5:  # Filter out short text
                    # Clean up the text by removing extra whitespace and newlines
                    product_name = re.sub(r'\s+', ' ', text)
                    return product_name.strip()
            
            return "Unknown Product"
            
        except Exception as e:
            logger.error(f"Error extracting product name: {e}")
            return "Unknown Product"
    
    def _extract_size_from_container(self, container) -> Optional[str]:
        """Extract size from the product container"""
        try:
            # Look for "Shoe Size" text in the container
            # The size might be split across multiple elements
            container_text = container.get_text()
            
            # Look for pattern like "Shoe Size: 8.0" or "Shoe Size 8.0"
            match = re.search(r'Shoe\s+Size[:\s]+([\d.]+)', container_text)
            if match:
                return match.group(1)
            
            # Alternative: look for size patterns in individual elements
            size_elements = container.find_all('p')
            for p in size_elements:
                text = p.get_text(strip=True)
                if 'Shoe Size' in text:
                    # Extract the size value (e.g., "Shoe Size: 8.0" -> "8.0")
                    match = re.search(r'Shoe\s+Size[:\s]+([\d.]+)', text)
                    if match:
                        return match.group(1)
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting size: {e}")
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
    
    def _clean_size(self, size: str) -> str:
        """Clean up size format (remove trailing .0 if it's a whole number)"""
        # Convert "06.0" to "6", "10.5" to "10.5", "14.0" to "14", etc.
        if re.match(r'^\d{1,2}\.\d$', size):
            num = float(size)
            # Remove .0 if it's a whole number
            return str(int(num)) if num % 1 == 0 else str(num)
        
        return size
