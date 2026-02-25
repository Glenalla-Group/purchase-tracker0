"""
Dick's Sporting Goods Email Parser
Parses order confirmation and shipping emails from Dick's Sporting Goods using BeautifulSoup
"""

import logging
import re
from typing import List, Optional
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from app.models.email import EmailData
from app.utils.address_utils import normalize_shipping_address

logger = logging.getLogger(__name__)


class DicksOrderItem:
    """Represents a single item from a Dick's Sporting Goods order"""
    
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
        return f"<DicksOrderItem(unique_id={self.unique_id}, size={self.size}, qty={self.quantity}, product={product_display})>"


class DicksOrderData:
    """Represents a complete Dick's Sporting Goods order"""
    
    def __init__(self, order_number: str, items: List[DicksOrderItem], shipping_address: str = None):
        self.order_number = order_number
        self.items = items
        self.shipping_address = shipping_address or ""
    
    def __repr__(self):
        return f"<DicksOrderData(order_number={self.order_number}, items_count={len(self.items)}, address={self.shipping_address})>"


class DicksShippingOrderItem(BaseModel):
    """Represents a single item from a Dick's shipping notification"""
    unique_id: str = Field(..., description="Unique identifier for the product (from image URL)")
    size: Optional[str] = Field(None, description="Size of the product (may not be present in shipping emails)")
    quantity: int = Field(..., description="Quantity of the product")
    product_name: Optional[str] = Field(None, description="Name of the product")
    color: Optional[str] = Field(None, description="Color of the product")
    price: Optional[float] = Field(None, description="Price per unit")


class DicksShippingData(BaseModel):
    """Represents Dick's shipping notification data"""
    order_number: str = Field(..., description="Order number")
    items: List[DicksShippingOrderItem] = Field(..., description="List of shipped items")
    
    def __repr__(self):
        return f"<DicksShippingData(order={self.order_number}, items={len(self.items)})>"


class DicksCancellationOrderItem(BaseModel):
    """Represents a single item from a Dick's cancellation notification"""
    unique_id: str = Field(..., description="Unique identifier for the product (from image URL)")
    size: Optional[str] = Field(None, description="Size of the product")
    quantity: int = Field(..., description="Quantity of the cancelled product")
    product_name: Optional[str] = Field(None, description="Name of the product")
    product_number: Optional[str] = Field(None, description="Product number/SKU")
    color: Optional[str] = Field(None, description="Color of the product")


class DicksCancellationData(BaseModel):
    """Represents Dick's cancellation notification data"""
    order_number: str = Field(..., description="Order number")
    items: List[DicksCancellationOrderItem] = Field(..., description="List of cancelled items")
    
    def __repr__(self):
        return f"<DicksCancellationData(order={self.order_number}, items={len(self.items)})>"


class DicksEmailParser:
    """
    Parser for Dick's Sporting Goods order confirmation emails using BeautifulSoup.
    
    Handles email formats like:
    From: from@notifications.dcsg.com
    Subject: "Thank you for your order!"
    """
    
    # Email identification patterns - Order Confirmation (Production)
    DICKS_FROM_EMAIL = "from@notifications.dcsg.com"
    DICKS_FROM_PATTERN = r"dicks|dcsg"
    SUBJECT_ORDER_PATTERN = r"Thank you for your order"
    
    # Email identification - Development (forwarded emails)
    DEV_DICKS_ORDER_FROM_EMAIL = "glenallagroupc@gmail.com"
    DEV_SUBJECT_ORDER_PATTERN = r"Fwd:\s*Thank you for your order"
    
    # Email identification patterns - Shipping
    DICKS_SHIPPING_FROM_EMAIL = "notifications@delivery.dickssportinggoods.com"
    SUBJECT_SHIPPING_PATTERN = r"your order just shipped|order.*shipped"
    
    # Email identification patterns - Cancellation
    DICKS_CANCELLATION_FROM_EMAIL = "from@notifications.dcsg.com"  # Same as order confirmation
    # Two types of cancellation emails:
    # 1. "All or part of your order has been cancelled" / "We're sorry, One or more items are not available"
    # 2. "Your Product(s) Was Canceled" / "Your order has been canceled"
    SUBJECT_CANCELLATION_PATTERN = (
        r"all or part of your order.*been cancelled|"
        r"your product.*was canceled|"
        r"your order.*been canceled|"
        r"product.*canceled|"
        r"one or more items.*not available"
    )
    
    def __init__(self):
        """Initialize the Dick's email parser."""
        from app.config.settings import get_settings
        self.settings = get_settings()
    
    @property
    def order_from_email(self) -> str:
        """Get the appropriate from email address based on environment."""
        if self.settings.is_development:
            return self.DEV_DICKS_ORDER_FROM_EMAIL
        return self.DICKS_FROM_EMAIL
    
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
    def shipping_from_email(self) -> str:
        """Get the appropriate from email address for shipping notifications based on environment."""
        if self.settings.is_development:
            return self.DEV_DICKS_ORDER_FROM_EMAIL
        return self.DICKS_SHIPPING_FROM_EMAIL
    
    @property
    def cancellation_from_email(self) -> str:
        """Get the appropriate from email address for cancellation notifications based on environment."""
        if self.settings.is_development:
            return self.DEV_DICKS_ORDER_FROM_EMAIL
        return self.DICKS_CANCELLATION_FROM_EMAIL
    
    @property
    def shipping_subject_query(self) -> str:
        """Get the appropriate subject pattern for Gmail shipping queries based on environment."""
        if self.settings.is_development:
            return 'subject:"Fwd: your order just shipped"'
        return 'subject:"your order just shipped" OR subject:shipped'
    
    @property
    def cancellation_subject_query(self) -> str:
        """Get the appropriate subject pattern for Gmail cancellation queries based on environment."""
        if self.settings.is_development:
            return 'subject:"Fwd: Your order has been canceled" OR subject:"Fwd: Your Product(s) Was Canceled" OR subject:"Fwd: All or part of your order has been cancelled"'
        return 'subject:"Your order has been canceled" OR subject:"Your Product(s) Was Canceled" OR subject:"All or part of your order has been cancelled"'
    
    def is_dicks_email(self, email_data: EmailData) -> bool:
        """Check if email is from Dick's Sporting Goods"""
        sender_lower = email_data.sender.lower()
        
        # In development, check for forwarded emails from dev email address
        # Must also verify content to avoid misclassifying other retailers' forwarded emails
        if self.settings.is_development:
            if self.DEV_DICKS_ORDER_FROM_EMAIL.lower() in sender_lower:
                html = (email_data.html_content or "").lower()
                # Dick's emails contain dcsg.com or dickssportinggoods in URLs/content
                if "dcsg" in html or "dickssportinggoods" in html:
                    return True
                return False
        
        # Check for production email address
        if self.DICKS_FROM_EMAIL.lower() in sender_lower:
            return True
        
        if re.search(self.DICKS_FROM_PATTERN, sender_lower, re.IGNORECASE):
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
        
        if re.search(self.SUBJECT_ORDER_PATTERN, subject_lower, re.IGNORECASE):
            return True
        
        return False
    
    def is_shipping_email(self, email_data: EmailData) -> bool:
        """Check if email is a shipping notification"""
        sender_lower = email_data.sender.lower()
        subject_lower = email_data.subject.lower()
        
        # Check if sender matches Dick's shipping email address
        if self.DICKS_SHIPPING_FROM_EMAIL.lower() in sender_lower:
            # Also check subject pattern
            return bool(re.search(self.SUBJECT_SHIPPING_PATTERN, subject_lower, re.IGNORECASE))
        
        # Fallback: check if it's a Dick's email and matches shipping pattern
        if self.is_dicks_email(email_data):
            return bool(re.search(self.SUBJECT_SHIPPING_PATTERN, subject_lower, re.IGNORECASE))
        
        return False
    
    def is_cancellation_email(self, email_data: EmailData) -> bool:
        """Check if email is a cancellation notification"""
        sender_lower = email_data.sender.lower()
        subject_lower = email_data.subject.lower()
        
        # Check if sender matches Dick's cancellation email address
        if self.DICKS_CANCELLATION_FROM_EMAIL.lower() in sender_lower:
            # Check subject pattern (handles both types)
            if re.search(self.SUBJECT_CANCELLATION_PATTERN, subject_lower, re.IGNORECASE):
                return True
            # Also check body text for cancellation indicators
            if email_data.html_content:
                html_lower = email_data.html_content.lower()
                if any(phrase in html_lower for phrase in [
                    "we're sorry, one or more items are not available",
                    "your order has been canceled",
                    "order has been canceled",
                    "item(s) canceled"
                ]):
                    return True
        
        # Fallback: check if it's a Dick's email and matches cancellation pattern
        if self.is_dicks_email(email_data):
            if re.search(self.SUBJECT_CANCELLATION_PATTERN, subject_lower, re.IGNORECASE):
                return True
            # Check body text as fallback
            if email_data.html_content:
                html_lower = email_data.html_content.lower()
                if any(phrase in html_lower for phrase in [
                    "we're sorry, one or more items are not available",
                    "your order has been canceled",
                    "order has been canceled",
                    "item(s) canceled"
                ]):
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
            
            # Extract shipping address
            shipping_address = self._extract_shipping_address(soup)
            if shipping_address:
                logger.info(f"Extracted shipping address: {shipping_address}")
            
            return DicksOrderData(order_number=order_number, items=items, shipping_address=shipping_address)
        
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
        
        # Log items with ID, size, and quantity (product names come from OA Sourcing table)
        if items:
            items_summary = [f"(ID: {item.unique_id}, Size: {item.size}, Qty: {item.quantity})" for item in items]
            logger.info(f"[Dick's Sporting Goods] Extracted {len(items)} items: {', '.join(items_summary)}")
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
        """Extract product name from the image's container - improved version"""
        try:
            # Find the container of the image - go up multiple levels
            containers_to_check = []
            
            # Try immediate parent first
            parent = img.find_parent()
            if parent:
                containers_to_check.append(parent)
            
            # Try td/tr/table ancestors (Dick's uses tables)
            for tag in ['td', 'tr', 'table', 'div']:
                ancestor = img.find_parent(tag)
                if ancestor and ancestor not in containers_to_check:
                    containers_to_check.append(ancestor)
            
            # Method 0: Check alt text on the image first
            alt_text = img.get('alt', '')
            if alt_text and len(alt_text) > 10 and len(alt_text) < 200:
                logger.debug(f"[Dick's] Found product name from alt text: {alt_text[:50]}")
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
                            logger.debug(f"[Dick's] Found product name from link: {link_text[:50]}")
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
                                    logger.debug(f"[Dick's] Found product name from text: {text[:50]}")
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
                                logger.debug(f"[Dick's] Found product name from table row: {part[:50]}")
                                return part
            
            logger.debug(f"[Dick's] Could not extract product name from image: {img.get('src', '')[:50]}")
            return "Unknown Product"
            
        except Exception as e:
            logger.warning(f"[Dick's] Error extracting product name from image: {e}")
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
            # Method 1: Look for bold text in links within the container
            links = container.find_all('a')
            for link in links:
                bold_text = link.find('b')
                if bold_text:
                    # Clean up the text by removing extra whitespace and newlines
                    product_name = bold_text.get_text(strip=True)
                    # Replace multiple whitespace/newlines with single space
                    product_name = re.sub(r'\s+', ' ', product_name)
                    if product_name and len(product_name) > 5:
                        logger.debug(f"Found product name from bold link: {product_name[:50]}")
                        return product_name.strip()
            
            # Method 2: Look for any link text (not just bold)
            for link in links:
                link_text = link.get_text(strip=True)
                if link_text and len(link_text) > 5:
                    # Filter out common non-product text
                    if link_text.lower() not in ['view', 'details', 'shop now', 'buy now', 'add to cart']:
                        product_name = re.sub(r'\s+', ' ', link_text)
                        logger.debug(f"Found product name from link: {product_name[:50]}")
                        return product_name.strip()
            
            # Method 3: Fallback: look for any bold text in the container
            bold_elements = container.find_all('b')
            for bold in bold_elements:
                text = bold.get_text(strip=True)
                if text and len(text) > 5:  # Filter out short text
                    # Clean up the text by removing extra whitespace and newlines
                    product_name = re.sub(r'\s+', ' ', text)
                    logger.debug(f"Found product name from bold: {product_name[:50]}")
                    return product_name.strip()
            
            # Method 4: Look for text in spans, divs, paragraphs
            text_elements = container.find_all(['span', 'div', 'p', 'td'], string=True)
            for elem in text_elements:
                text = elem.get_text(strip=True) if hasattr(elem, 'get_text') else str(elem).strip()
                if text and len(text) > 10 and len(text) < 200:  # Reasonable product name length
                    # Skip if it looks like size/quantity/price
                    if not re.match(r'^(Size|Qty|Quantity|\$|\d+\.\d+)$', text, re.IGNORECASE):
                        product_name = re.sub(r'\s+', ' ', text)
                        logger.debug(f"Found product name from text element: {product_name[:50]}")
                        return product_name.strip()
            
            return "Unknown Product"
            
        except Exception as e:
            logger.warning(f"Error extracting product name from container: {e}")
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
            
            # Convert to float and check it's greater than 0
            size_num = float(clean_size)
            return size_num > 0
            
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
    
    def parse_shipping_email(self, email_data: EmailData) -> Optional[DicksShippingData]:
        """
        Parse Dick's Sporting Goods shipping email.
        
        Focuses only on the "In This Package" section and ignores:
        - "Cancelled Items" section
        - "Additional Packages In Your Order" sections
        
        Args:
            email_data: EmailData object containing email information
        
        Returns:
            DicksShippingData object or None if parsing fails
        """
        try:
            html_content = email_data.html_content
            
            if not html_content:
                logger.error("No HTML content in Dick's shipping email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extract order number
            order_number = self._extract_order_number_from_shipping_email(soup)
            if not order_number:
                logger.error("Failed to extract order number from Dick's shipping email")
                return None
            
            logger.info(f"Extracted Dick's shipping order number: {order_number}")
            
            # Extract items from "In This Package" section only
            items = self._extract_shipping_items(soup)
            
            if not items:
                logger.error("Failed to extract any items from Dick's shipping email")
                return None
            
            logger.info(f"Successfully extracted {len(items)} items from Dick's shipping order {order_number}")
            for item in items:
                logger.debug(f"  - {item}")
            
            return DicksShippingData(order_number=order_number, items=items)
        
        except Exception as e:
            logger.error(f"Error parsing Dick's shipping email: {e}", exc_info=True)
            return None
    
    def _extract_order_number_from_shipping_email(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract order number from Dick's shipping email.
        
        Pattern: "Order #: 40021802072 | Order date: Sep 15, 2025"
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            Order number or None
        """
        try:
            # Look for "Order #:" pattern
            text = soup.get_text()
            match = re.search(r'Order\s*#:\s*(\d{8,15})', text, re.IGNORECASE)
            if match:
                order_number = match.group(1)
                logger.debug(f"Found order number in shipping email: {order_number}")
                return order_number
            
            logger.warning("Order number not found in Dick's shipping email")
            return None
        
        except Exception as e:
            logger.error(f"Error extracting order number from shipping email: {e}")
            return None
    
    def _extract_shipping_items(self, soup: BeautifulSoup) -> List[DicksShippingOrderItem]:
        """
        Extract items from "In This Package" section only.
        
        Ignores:
        - "Cancelled Items" section
        - "Additional Packages In Your Order" sections
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            List of DicksShippingOrderItem objects
        """
        items = []
        
        try:
            # Find the "In This Package" section
            in_this_package_section = self._find_in_this_package_section(soup)
            if not in_this_package_section:
                logger.warning("Could not find 'In This Package' section in Dick's shipping email")
                return items
            
            # Find all product images within this section
            product_images = in_this_package_section.find_all('img', src=re.compile(r'dks\.scene7\.com/is/image/dkscdn/'))
            logger.debug(f"Found {len(product_images)} product images in 'In This Package' section")
            
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
                    
                    # Extract product details
                    product_name = self._extract_product_name_from_shipping_container(product_container)
                    color = self._extract_color_from_shipping_container(product_container)
                    quantity = self._extract_quantity_from_shipping_container(product_container)
                    price = self._extract_price_from_shipping_container(product_container)
                    size = self._extract_size_from_shipping_container(product_container)  # May be None
                    
                    # Validate required fields
                    if not unique_id or quantity is None:
                        logger.warning(
                            f"Missing required fields for {unique_id}: "
                            f"quantity={quantity}"
                        )
                        continue
                    
                    items.append(DicksShippingOrderItem(
                        unique_id=unique_id,
                        size=size,
                        quantity=quantity,
                        product_name=product_name,
                        color=color,
                        price=price
                    ))
                    logger.debug(
                        f"Extracted shipping item: {product_name} (unique_id={unique_id}), "
                        f"Size: {size}, Qty: {quantity}, Color: {color}, Price: {price}"
                    )
                
                except Exception as e:
                    logger.error(f"Error processing product image: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error extracting shipping items: {e}", exc_info=True)
        
        return items
    
    def _find_in_this_package_section(self, soup: BeautifulSoup) -> Optional[BeautifulSoup]:
        """
        Find the "In This Package" section in the email.
        
        This section appears before "Cancelled Items" and "Additional Packages" sections.
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            BeautifulSoup element containing the "In This Package" section, or None
        """
        try:
            # Find the div containing "In This Package" text
            text_elements = soup.find_all(string=re.compile(r'In This Package', re.IGNORECASE))
            
            for text_elem in text_elements:
                # Navigate up to find the parent container
                parent = text_elem.parent
                while parent:
                    # Look for a div with class containing "mobile-padding" or similar container
                    if parent.name == 'div' and parent.get('class'):
                        # Find the next sibling or parent that contains product items
                        # The products are typically in a table structure after this header
                        container = parent.find_parent('div', class_=re.compile(r'mobile-padding'))
                        if container:
                            # Return the parent div that contains both header and products
                            # Stop before "Cancelled Items" section
                            return self._get_section_before_cancelled_items(container)
                    
                    parent = parent.parent
            
            # Alternative: Find by looking for the section structure
            # The "In This Package" section has a specific structure with product images
            all_divs = soup.find_all('div', class_=re.compile(r'mobile-padding'))
            for div in all_divs:
                div_text = div.get_text()
                if 'In This Package' in div_text and 'Cancelled Items' not in div_text:
                    # Check if this div contains product images
                    if div.find('img', src=re.compile(r'dks\.scene7\.com/is/image/dkscdn/')):
                        return self._get_section_before_cancelled_items(div)
            
            return None
        
        except Exception as e:
            logger.error(f"Error finding 'In This Package' section: {e}")
            return None
    
    def _get_section_before_cancelled_items(self, start_element) -> Optional[BeautifulSoup]:
        """
        Get the section content before "Cancelled Items" or "Additional Packages" sections.
        
        Args:
            start_element: Starting element to search from
        
        Returns:
            BeautifulSoup element containing the section, or None
        """
        try:
            # Find the parent container
            container = start_element.find_parent('div', class_=re.compile(r'mobile-padding'))
            if not container:
                container = start_element
            
            # Get all siblings and check for "Cancelled Items" or "Additional Packages"
            parent = container.parent
            if not parent:
                return container
            
            # Collect all child elements until we hit "Cancelled Items" or "Additional Packages"
            result_elements = []
            for child in parent.children:
                if isinstance(child, str):
                    continue
                
                child_text = child.get_text() if hasattr(child, 'get_text') else str(child)
                
                # Stop if we hit cancelled items or additional packages
                if 'Cancelled Items' in child_text or 'Additional Packages' in child_text:
                    break
                
                result_elements.append(child)
            
            # Return the original container if we found it, otherwise return a wrapper
            return container
        
        except Exception as e:
            logger.error(f"Error getting section before cancelled items: {e}")
            return start_element
    
    def _extract_product_name_from_shipping_container(self, container) -> Optional[str]:
        """Extract product name from shipping container"""
        try:
            # Look for bold text or div with product name
            # Pattern: Product name is in a div with font-weight:600
            name_divs = container.find_all('div', style=re.compile(r'font-weight:\s*600'))
            for div in name_divs:
                text = div.get_text(strip=True)
                if text and len(text) > 5 and 'Color:' not in text and 'Quantity:' not in text:
                    return text.strip()
            
            # Fallback: look for any bold text
            bold_elements = container.find_all(['b', 'strong'])
            for bold in bold_elements:
                text = bold.get_text(strip=True)
                if text and len(text) > 5:
                    return text.strip()
            
            return None
        
        except Exception as e:
            logger.error(f"Error extracting product name from shipping container: {e}")
            return None
    
    def _extract_color_from_shipping_container(self, container) -> Optional[str]:
        """Extract color from shipping container"""
        try:
            text = container.get_text()
            match = re.search(r'Color:\s*([^\n\r<]+)', text, re.IGNORECASE)
            if match:
                color = match.group(1).strip()
                # Remove trailing <br> or other HTML artifacts
                color = re.sub(r'\s*<.*?>.*', '', color)
                return color.strip()
            
            return None
        
        except Exception as e:
            logger.error(f"Error extracting color from shipping container: {e}")
            return None
    
    def _extract_quantity_from_shipping_container(self, container) -> Optional[int]:
        """Extract quantity from shipping container"""
        try:
            text = container.get_text()
            match = re.search(r'Quantity:\s*(\d+)', text, re.IGNORECASE)
            if match:
                return int(match.group(1))
            
            # Default to 1 if not found
            return 1
        
        except Exception as e:
            logger.error(f"Error extracting quantity from shipping container: {e}")
            return 1
    
    def _extract_price_from_shipping_container(self, container) -> Optional[float]:
        """Extract price from shipping container"""
        try:
            text = container.get_text()
            match = re.search(r'Price:\s*\$?([\d,]+\.?\d*)', text, re.IGNORECASE)
            if match:
                price_str = match.group(1).replace(',', '')
                return float(price_str)
            
            return None
        
        except Exception as e:
            logger.error(f"Error extracting price from shipping container: {e}")
            return None
    
    def _extract_size_from_shipping_container(self, container) -> Optional[str]:
        """Extract size from shipping container (may not be present)"""
        try:
            text = container.get_text()
            
            # Look for size patterns
            match = re.search(r'Size:\s*([^\n\r<]+)', text, re.IGNORECASE)
            if match:
                size = match.group(1).strip()
                size = re.sub(r'\s*<.*?>.*', '', size)
                if self._is_valid_size(size):
                    return self._clean_size(size)
            
            # Look for shoe size pattern
            match = re.search(r'Shoe\s+Size[:\s]+([\d.]+)', text, re.IGNORECASE)
            if match:
                size = match.group(1)
                if self._is_valid_size(size):
                    return self._clean_size(size)
            
            return None
        
        except Exception as e:
            logger.error(f"Error extracting size from shipping container: {e}")
            return None
    
    def parse_cancellation_email(self, email_data: EmailData) -> Optional[DicksCancellationData]:
        """
        Parse Dick's Sporting Goods cancellation email.
        
        Args:
            email_data: EmailData object containing email information
        
        Returns:
            DicksCancellationData object or None if parsing fails
        """
        try:
            html_content = email_data.html_content
            
            if not html_content:
                logger.error("No HTML content in Dick's cancellation email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extract order number
            order_number = self._extract_order_number_from_cancellation_email(soup)
            if not order_number:
                logger.error("Failed to extract order number from Dick's cancellation email")
                return None
            
            logger.info(f"Extracted Dick's cancellation order number: {order_number}")
            
            # Extract cancelled items
            items = self._extract_cancellation_items(soup)
            
            if not items:
                logger.error("Failed to extract any items from Dick's cancellation email")
                return None
            
            logger.info(f"Successfully extracted {len(items)} items from Dick's cancellation order {order_number}")
            for item in items:
                logger.debug(f"  - {item}")
            
            return DicksCancellationData(order_number=order_number, items=items)
        
        except Exception as e:
            logger.error(f"Error parsing Dick's cancellation email: {e}", exc_info=True)
            return None
    
    def _extract_order_number_from_cancellation_email(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract order number from Dick's cancellation email.
        
        Pattern: "#40021802072" in a link
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            Order number or None
        """
        try:
            # Look for order number in links (pattern: #40021802072)
            links = soup.find_all('a')
            for link in links:
                link_text = link.get_text(strip=True)
                # Check for pattern like #40021802072
                match = re.search(r'#(\d{8,15})', link_text)
                if match:
                    order_number = match.group(1)
                    logger.debug(f"Found order number in cancellation email link: {order_number}")
                    return order_number
            
            # Fallback: search in all text
            text = soup.get_text()
            match = re.search(r'#(\d{8,15})', text)
            if match:
                order_number = match.group(1)
                logger.debug(f"Found order number in cancellation email text: {order_number}")
                return order_number
            
            logger.warning("Order number not found in Dick's cancellation email")
            return None
        
        except Exception as e:
            logger.error(f"Error extracting order number from cancellation email: {e}")
            return None
    
    def _extract_cancellation_items(self, soup: BeautifulSoup) -> List[DicksCancellationOrderItem]:
        """
        Extract cancelled items from Dick's cancellation email.
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            List of DicksCancellationOrderItem objects
        """
        items = []
        
        try:
            # Find all product images (cancelled items)
            product_images = soup.find_all('img', src=re.compile(r'dks\.scene7\.com/is/image/dkscdn/'))
            logger.debug(f"Found {len(product_images)} product images in cancellation email")
            
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
                    
                    # Extract product details
                    product_name = self._extract_product_name_from_cancellation_container(product_container)
                    product_number = self._extract_product_number_from_cancellation_container(product_container)
                    color = self._extract_color_from_cancellation_container(product_container)
                    size = self._extract_size_from_cancellation_container(product_container)
                    quantity = self._extract_quantity_from_cancellation_container(product_container)
                    
                    # Validate required fields
                    if not unique_id or quantity is None:
                        logger.warning(
                            f"Missing required fields for {unique_id}: "
                            f"quantity={quantity}"
                        )
                        continue
                    
                    items.append(DicksCancellationOrderItem(
                        unique_id=unique_id,
                        size=size,
                        quantity=quantity,
                        product_name=product_name,
                        product_number=product_number,
                        color=color
                    ))
                    logger.debug(
                        f"Extracted cancellation item: {product_name} (unique_id={unique_id}), "
                        f"Size: {size}, Qty: {quantity}, Color: {color}, SKU: {product_number}"
                    )
                
                except Exception as e:
                    logger.error(f"Error processing product image: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error extracting cancellation items: {e}", exc_info=True)
        
        return items
    
    def _extract_product_name_from_cancellation_container(self, container) -> Optional[str]:
        """Extract product name from cancellation container (handles both email formats)"""
        try:
            # Format 1: Product name in bold link (e.g., "On Women's Cloudmonster Shoes")
            links = container.find_all('a')
            for link in links:
                bold_text = link.find('b')
                if bold_text:
                    text = bold_text.get_text(strip=True)
                    if text and len(text) > 5:
                        return text.strip()
            
            # Format 2: Product name in paragraph (e.g., "Nike Kids' Grade School Flex Runner 2 Running Shoes")
            paragraphs = container.find_all('p')
            for p in paragraphs:
                text = p.get_text(strip=True)
                # Skip if it contains SKU, Color, Size, Quantity labels
                if any(label in text.lower() for label in ['sku:', 'color:', 'size:', 'quantity:', 'shoe size:', 'shoe width:', 'est. delivery:']):
                    continue
                # Look for product name patterns
                if text and len(text) > 10 and not text.startswith('Quantity:'):
                    # Remove "Quantity: X" if present
                    text = re.sub(r'\s*Quantity:\s*\d+', '', text, flags=re.IGNORECASE)
                    text = text.strip()
                    if text and len(text) > 5:
                        return text
            
            # Fallback: look for any bold text
            bold_elements = container.find_all(['b', 'strong'])
            for bold in bold_elements:
                text = bold.get_text(strip=True)
                if text and len(text) > 5 and 'SKU:' not in text and 'Color' not in text and 'Size' not in text:
                    return text.strip()
            
            return None
        
        except Exception as e:
            logger.error(f"Error extracting product name from cancellation container: {e}")
            return None
    
    def _extract_product_number_from_cancellation_container(self, container) -> Optional[str]:
        """Extract product number/SKU from cancellation container"""
        try:
            text = container.get_text()
            match = re.search(r'SKU:\s*(\d+)', text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
            
            return None
        
        except Exception as e:
            logger.error(f"Error extracting product number from cancellation container: {e}")
            return None
    
    def _extract_color_from_cancellation_container(self, container) -> Optional[str]:
        """Extract color from cancellation container"""
        try:
            text = container.get_text()
            match = re.search(r'Color:\s*([^\n\r<]+)', text, re.IGNORECASE)
            if match:
                color = match.group(1).strip()
                # Remove trailing HTML artifacts
                color = re.sub(r'\s*<.*?>.*', '', color)
                return color.strip()
            
            return None
        
        except Exception as e:
            logger.error(f"Error extracting color from cancellation container: {e}")
            return None
    
    def _extract_size_from_cancellation_container(self, container) -> Optional[str]:
        """Extract size from cancellation container"""
        try:
            text = container.get_text()
            
            # Look for "Shoe Size" pattern
            match = re.search(r'Shoe\s+Size:\s*([\d.]+)', text, re.IGNORECASE)
            if match:
                size = match.group(1)
                if self._is_valid_size(size):
                    return self._clean_size(size)
            
            # Fallback: look for general "Size:" pattern
            match = re.search(r'Size:\s*([^\n\r<]+)', text, re.IGNORECASE)
            if match:
                size = match.group(1).strip()
                size = re.sub(r'\s*<.*?>.*', '', size)
                if self._is_valid_size(size):
                    return self._clean_size(size)
            
            return None
        
        except Exception as e:
            logger.error(f"Error extracting size from cancellation container: {e}")
            return None
    
    def _extract_quantity_from_cancellation_container(self, container) -> Optional[int]:
        """Extract quantity from cancellation container (defaults to 1 if not found)"""
        try:
            text = container.get_text()
            match = re.search(r'Quantity:\s*(\d+)', text, re.IGNORECASE)
            if match:
                return int(match.group(1))
            
            # Default to 1 if not found (cancellation emails typically show 1 item per entry)
            return 1
        
        except Exception as e:
            logger.error(f"Error extracting quantity from cancellation container: {e}")
            return 1
    
    def _extract_shipping_address(self, soup: BeautifulSoup) -> str:
        """
        Extract shipping address from email and normalize it.
        
        Dick's email structure:
        - "Ships to" header
        - Street address + city/state/zip (e.g., "595 Lloyd Ln STE D<br> Independence, OR 97351-2125")
        
        We want to extract just the street address part and normalize it.
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            Normalized shipping address or empty string
        """
        try:
            text = soup.get_text()
            
            # Method 1: Look for "Ships to" section and extract street address
            shipping_match = re.search(
                r'Ships\s+to\s*(.*?)(?:Payment|Order\s+Summary|$)',
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
                                # Dick's format: "595 Lloyd Ln STE D<br> Independence, OR 97351-2125"
                                # We want: "595 Lloyd Ln STE D" -> normalized to "595 Lloyd Lane"
                                
                                # Split by comma and take the first part (street address)
                                # City/state/zip usually comes after a comma or newline
                                parts = line.split(',')
                                street_line = parts[0].strip() if parts else line.strip()
                                
                                # Also check if there's a pattern like ", CITY, STATE" - take everything before that
                                # Pattern: number + street + optional unit, then ", CITY, STATE ZIP"
                                city_state_match = re.search(r',\s*[A-Z][A-Z\s]+,?\s*[A-Z]{2}\s*\d{5}', line)
                                if city_state_match:
                                    # Extract everything before the city/state/zip pattern
                                    street_line = line[:city_state_match.start()].strip()
                                
                                # Remove any HTML tags or newlines that might be in the text
                                street_line = re.sub(r'<[^>]+>', '', street_line).strip()
                                street_line = re.sub(r'\s+', ' ', street_line)  # Normalize whitespace
                                
                                normalized = normalize_shipping_address(street_line)
                                if normalized:
                                    logger.debug(f"Extracted Dicks shipping address: {line} -> {street_line} -> {normalized}")
                                    return normalized
            
            # Method 2: Direct pattern matching for known addresses
            # Look for "595 Lloyd" pattern
            lloyd_match = re.search(r'(595\s+Lloyd\s+Ln[^,\n]*(?:,\s*[A-Z\s]+)?)', text, re.IGNORECASE)
            if lloyd_match:
                street_line = lloyd_match.group(1).strip()
                # Remove city/state/zip if present
                street_line = re.sub(r',\s*[A-Z][A-Z\s]+,?\s*[A-Z]{2}\s*\d{5}.*$', '', street_line).strip()
                # Remove HTML tags
                street_line = re.sub(r'<[^>]+>', '', street_line).strip()
                normalized = normalize_shipping_address(street_line)
                if normalized:
                    logger.debug(f"Extracted Dicks shipping address (pattern): {street_line} -> {normalized}")
                    return normalized
            
            # Method 3: Look for "2025 Vista" pattern
            vista_match = re.search(r'(2025\s+Vista\s+Ave[^,\n]*(?:,\s*[A-Z\s]+)?)', text, re.IGNORECASE)
            if vista_match:
                street_line = vista_match.group(1).strip()
                # Remove city/state/zip if present
                street_line = re.sub(r',\s*[A-Z][A-Z\s]+,?\s*[A-Z]{2}\s*\d{5}.*$', '', street_line).strip()
                # Remove HTML tags
                street_line = re.sub(r'<[^>]+>', '', street_line).strip()
                normalized = normalize_shipping_address(street_line)
                if normalized:
                    logger.debug(f"Extracted Dicks shipping address (pattern): {street_line} -> {normalized}")
                    return normalized
            
            return ""
        
        except Exception as e:
            logger.error(f"Error extracting shipping address: {e}")
            return ""
