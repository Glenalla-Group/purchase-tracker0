"""
On (On Running) Email Parser
Parses order confirmation emails from On
"""

import re
import base64
import logging
from typing import List, Optional
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from app.models.email import EmailData

logger = logging.getLogger(__name__)


class OnOrderItem(BaseModel):
    """Represents a single item from an On order"""
    unique_id: str = Field(..., description="Unique identifier for the product (extracted from redirect URL)")
    size: str = Field(..., description="Size of the product")
    quantity: int = Field(..., description="Quantity of the product")
    product_name: str = Field(..., description="Name of the product")
    
    def __repr__(self):
        if self.product_name and len(self.product_name) > 50:
            product_display = self.product_name[:50] + "..."
        else:
            product_display = self.product_name or "Unknown"
        return f"<OnOrderItem(unique_id={self.unique_id}, size={self.size}, qty={self.quantity}, product={product_display})>"


class OnOrderData(BaseModel):
    """Represents On order data"""
    order_number: str = Field(..., description="The order number")
    items: List[OnOrderItem] = Field(..., description="List of items in the order")
    items_count: int = Field(0, description="Total number of items in the order")
    shipping_address: str = Field("", description="Normalized shipping address")

    def __init__(self, **data):
        super().__init__(**data)
        self.items_count = len(self.items)
    
    def __repr__(self):
        return f"<OnOrderData(order={self.order_number}, items={len(self.items)})>"


class OnEmailParser:
    """
    Parser for On (On Running) order confirmation emails.
    
    Handles email formats like:
    From: no-reply@on.com
    Subject: "Thanks for your order"
    """
    
    # Email identification - Production
    ON_FROM_EMAIL = "no-reply@on.com"
    SUBJECT_ORDER_PATTERN = r"thanks\s+for\s+your\s+order"
    
    # Email identification - Development (forwarded emails)
    DEV_ON_ORDER_FROM_EMAIL = "glenallagroupc@gmail.com"
    DEV_SUBJECT_ORDER_PATTERN = r"Fwd:.*thanks\s+for\s+your\s+order"
    
    def __init__(self):
        """Initialize the On email parser."""
        from app.config.settings import get_settings
        self.settings = get_settings()
    
    @property
    def order_from_email(self) -> str:
        """Get the appropriate from email address based on environment."""
        if self.settings.is_development:
            return self.DEV_ON_ORDER_FROM_EMAIL
        return self.ON_FROM_EMAIL
    
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
            return "Thanks for your order"
        return "Thanks for your order"
    
    def is_on_email(self, email_data: EmailData) -> bool:
        """Check if email is from On"""
        sender_lower = email_data.sender.lower()
        
        # In development, check for forwarded emails from dev email address
        if self.settings.is_development:
            if self.DEV_ON_ORDER_FROM_EMAIL.lower() in sender_lower:
                return True
        
        # In production, check for On email
        return self.ON_FROM_EMAIL.lower() in sender_lower
    
    def is_order_confirmation_email(self, email_data: EmailData) -> bool:
        """Check if email is an order confirmation"""
        if not self.is_on_email(email_data):
            return False
        subject_pattern = self.order_subject_pattern
        return bool(re.search(subject_pattern, email_data.subject, re.IGNORECASE))
    
    def parse_email(self, email_data: EmailData) -> Optional[OnOrderData]:
        """
        Parse On order confirmation email.
        
        Args:
            email_data: EmailData object containing email information
        
        Returns:
            OnOrderData object or None if parsing fails
        """
        try:
            html_content = email_data.html_content
            
            if not html_content:
                logger.error("No HTML content in On email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extract order number
            order_number = self._extract_order_number(soup)
            if not order_number:
                logger.error("Failed to extract order number from On email")
                return None
            
            logger.info(f"Extracted On order number: {order_number}")
            
            # Extract items
            items = self._extract_items(soup)
            
            if not items:
                logger.error("Failed to extract any items from On email")
                return None
            
            logger.info(f"Successfully extracted {len(items)} items from On order {order_number}")
            for item in items:
                logger.debug(f"  - {item}")
            
            # Extract shipping address
            from app.utils.address_utils import normalize_shipping_address
            shipping_address = self._extract_shipping_address(soup)
            if shipping_address:
                normalized = normalize_shipping_address(shipping_address)
                logger.info(f"Extracted shipping address: {normalized}")
                shipping_address = normalized
            
            return OnOrderData(order_number=order_number, items=items, shipping_address=shipping_address)
        
        except Exception as e:
            logger.error(f"Error parsing On email: {e}", exc_info=True)
            return None
    
    def _extract_order_number(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract order number from On email.
        
        Pattern: "ON233599054053" or "R803996852" (in td after "ORDER NUMBER")
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            Order number or None
        """
        try:
            # Look for "ORDER NUMBER" text, then get the next td
            order_number_tds = soup.find_all('td', string=lambda x: x and 'ORDER NUMBER' in str(x))
            
            for td in order_number_tds:
                # Find the parent table row
                parent_tr = td.find_parent('tr')
                if parent_tr:
                    # Find the next tr sibling
                    next_tr = parent_tr.find_next_sibling('tr')
                    if next_tr:
                        # Get the order number from the td
                        order_td = next_tr.find('td')
                        if order_td:
                            order_number = order_td.get_text(strip=True)
                            # Order number can be various formats: ON233599054053, R803996852, etc.
                            # Just return any non-empty value found after "ORDER NUMBER"
                            if order_number:
                                logger.debug(f"Found On order number: {order_number}")
                                return order_number
            
            logger.warning("Order number not found in On email")
            return None
        
        except Exception as e:
            logger.error(f"Error extracting On order number: {e}")
            return None
    
    def _extract_items(self, soup: BeautifulSoup) -> List[OnOrderItem]:
        """
        Extract order items from On email.
        
        Structure:
        - Product image with link containing base64-encoded URL
        - Product name: "Cloudsurfer Next"
        - Size: "Size: 6.5"
        - Quantity: "Qty: 1"
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            List of OnOrderItem objects
        """
        items = []
        
        try:
            # Find all product links (link.on.com redirect links)
            product_links = soup.find_all('a', href=lambda x: x and 'link.on.com/click' in str(x))
            
            logger.info(f"Found {len(product_links)} potential product links")
            
            # Filter to only product links (not header/navigation links)
            # Product links are typically around product images in product rows
            for link in product_links:
                try:
                    # Find the parent table row (tr) that contains this link
                    parent_tr = link.find_parent('tr')
                    if not parent_tr:
                        continue
                    
                    # Check if this row contains product information
                    row_text = parent_tr.get_text()
                    if 'Size:' not in row_text or 'Qty:' not in row_text:
                        continue
                    
                    # Extract product details from this row
                    product_details = self._extract_product_details(parent_tr, link)
                    
                    if product_details:
                        items.append(OnOrderItem(
                            unique_id=product_details['unique_id'],
                            size=product_details['size'],
                            quantity=product_details['quantity'],
                            product_name=product_details['product_name']
                        ))
                        logger.info(
                            f"Extracted On item: {product_details['product_name']} | "
                            f"unique_id={product_details['unique_id']}, "
                            f"Size={product_details['size']}, "
                            f"Qty={product_details['quantity']}"
                        )
                
                except Exception as e:
                    logger.error(f"Error processing On product: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error extracting On items: {e}", exc_info=True)
        
        return items
    
    def _extract_product_details(self, row, link) -> Optional[dict]:
        """
        Extract product details from a product row.
        
        Returns:
            Dictionary with unique_id, size, quantity, product_name or None
        """
        try:
            details = {}
            
            # Extract unique ID from redirect link
            # Pattern: https://link.on.com/click/.../aHR0cHM6Ly93d3cub24uY29tL2VuLXVzL3Byb2R1Y3RzL2Nsb3Vkc3VyZmVyLW5leHQtM3dlMzAwNS93b21lbnMvd2hpdGUtZmxhbWUtc2hvZXMtM1dFMzAwNTAyNTY_YnhpZD0...
            # Decode base64 URL and extract unique ID
            href = link.get('href', '')
            
            # Extract the base64-encoded part from the URL
            # Pattern: link.on.com/click/.../BASE64_ENCODED_URL/...
            match = re.search(r'link\.on\.com/click/[^/]+/([A-Za-z0-9_-]+)/', href)
            if match:
                encoded_url = match.group(1)
                
                # Decode base64 URL
                try:
                    # Try with padding
                    padding = 4 - len(encoded_url) % 4
                    if padding != 4:
                        encoded_url_padded = encoded_url + '=' * padding
                    else:
                        encoded_url_padded = encoded_url
                    
                    # Try standard base64 first
                    try:
                        decoded_bytes = base64.b64decode(encoded_url_padded)
                    except:
                        # Try urlsafe base64
                        decoded_bytes = base64.urlsafe_b64decode(encoded_url_padded)
                    
                    decoded_url = decoded_bytes.decode('utf-8')
                    
                    # Extract unique ID from decoded URL
                    # Patterns:
                    # - .../white-flame-shoes-3WE30050256?bxid=... (alphanumeric, 10-12 chars)
                    # - .../black-eclipse-shoes-55.98626?bxid=... (alphanumeric with dot)
                    # Extract the last part after the final dash before query params
                    unique_id_match = re.search(r'-([A-Z0-9.]+)(?:\?|$)', decoded_url, re.IGNORECASE)
                    if unique_id_match:
                        unique_id = unique_id_match.group(1)
                        details['unique_id'] = unique_id
                        logger.debug(f"Found unique ID: {unique_id} (from decoded URL: {decoded_url[:100]}...)")
                    else:
                        logger.warning(f"Could not extract unique ID from decoded URL: {decoded_url}")
                        return None
                
                except Exception as e:
                    logger.warning(f"Could not decode base64 URL: {e}, href: {href[:100]}")
                    return None
            else:
                logger.warning(f"Could not extract base64 part from link: {href[:100]}")
                return None
            
            # Extract product name
            # Look for td with font-size:28px (product name) in the row
            product_name_td = row.find('td', style=lambda x: x and 'font-size:28px' in str(x))
            if product_name_td:
                product_name = product_name_td.get_text(strip=True)
                details['product_name'] = product_name
                logger.debug(f"Found product name: {product_name}")
            else:
                logger.warning("Product name not found")
                return None
            
            # Extract size and quantity from row text
            row_text = row.get_text()
            
            # Extract size
            # Format: "Size: 6.5"
            size_match = re.search(r'Size:\s*([\d.]+)', row_text, re.IGNORECASE)
            if size_match:
                size = size_match.group(1)
                details['size'] = size
                logger.debug(f"Found size: {size}")
            else:
                logger.warning("Size not found")
                return None
            
            # Extract quantity
            # Format: "Qty: 1"
            qty_match = re.search(r'Qty:\s*(\d+)', row_text, re.IGNORECASE)
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
        Extract shipping address from On email.
        
        Look for "SHIPPING ADDRESS" header and extract address below it.
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            Shipping address or empty string
        """
        try:
            # Look for "SHIPPING ADDRESS" text
            shipping_tds = soup.find_all('td', string=lambda x: x and 'SHIPPING ADDRESS' in str(x))
            
            for shipping_td in shipping_tds:
                # Find the parent table row
                parent_tr = shipping_td.find_parent('tr')
                if parent_tr:
                    # Find all following tr siblings and collect address lines
                    address_lines = []
                    current_tr = parent_tr.find_next_sibling('tr')
                    
                    while current_tr and len(address_lines) < 3:
                        address_td = current_tr.find('td')
                        if address_td:
                            address_text = address_td.get_text(strip=True)
                            
                            # Skip empty lines
                            if not address_text:
                                current_tr = current_tr.find_next_sibling('tr')
                                continue
                            
                            # Skip name lines
                            if re.match(r'^[A-Z][a-z]+\s+[A-Z][a-z]+$', address_text):
                                current_tr = current_tr.find_next_sibling('tr')
                                continue
                            
                            # Stop at next section (empty td or new header)
                            if any(keyword in address_text.lower() for keyword in ['billing', 'payment', 'subtotal', 'total']):
                                break
                            
                            # Collect address lines
                            if re.search(r'\d+', address_text) or any(keyword in address_text.lower() for keyword in ['lane', 'street', 'ave', 'road', 'suite', 'ste', 'ln', 'independence', 'or']):
                                address_lines.append(address_text)
                        
                        current_tr = current_tr.find_next_sibling('tr')
                    
                    if address_lines:
                        address_combined = ', '.join(address_lines)
                        logger.debug(f"Extracted shipping address (raw): {address_combined}")
                        return address_combined
            
            logger.warning("Shipping address not found in On email")
            return ""
        
        except Exception as e:
            logger.error(f"Error extracting shipping address: {e}", exc_info=True)
            return ""
