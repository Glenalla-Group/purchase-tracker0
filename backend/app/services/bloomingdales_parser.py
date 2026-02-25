"""
Bloomingdale's Email Parser
Parses order confirmation emails from Bloomingdale's using BeautifulSoup

Email Format:
- From: CustomerService@oes.bloomingdales.com (production)
- From: glenallagroupc@gmail.com (dev - forwarded emails)
- Subject: "We received your order, [name]!"
- Order Number: Extract from HTML (e.g., "770138915")

HTML Structure:
- Products are listed in table rows
- Each product has:
  - Product name: <a href="...">On Men's Cloudrunner 2 Running Sneakers</a>
  - Size/Color: In <p> tag like "13, Frost White" or "7.5, Frost/Wash"
  - Quantity: "Qty: 6"
  - UPC: "UPC: 7630867894905"
  - Product link: Tracking link (emails.bloomingdales.com/pub/cc) that may contain product URL

Unique ID Extraction:
- Format: {color}-{id}
- Color: Extract from product URL slug (last word before ?ID=)
- ID: Extract from ?ID= parameter in product URL
- Example: URL "on-womens-cloudmonster-road-running-sneakers-in-frost?ID=5492261" -> "frost-5492261"
- Fallback: If URL not available, use UPC as ID part and extract color from size/color text
"""

import re
import logging
from typing import List, Optional, Dict
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field
from urllib.parse import urlparse, parse_qs, unquote

from app.models.email import EmailData
from app.utils.address_utils import normalize_shipping_address
from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class BloomingdalesOrderItem(BaseModel):
    unique_id: str = Field(..., description="Unique identifier for the product (e.g., frost-5492261)")
    size: str = Field(..., description="Size of the product")
    quantity: int = Field(..., description="Quantity of the product")
    product_name: Optional[str] = Field(None, description="Name of the product")
    upc: Optional[str] = Field(None, description="UPC code")
    color: Optional[str] = Field(None, description="Color name")
    
    def __repr__(self):
        if self.product_name and len(self.product_name) > 50:
            product_display = self.product_name[:50] + "..."
        else:
            product_display = self.product_name or "Unknown"
        return f"<BloomingdalesOrderItem(unique_id={self.unique_id}, size={self.size}, qty={self.quantity}, product={product_display})>"


class BloomingdalesOrderData(BaseModel):
    order_number: str = Field(..., description="The order number")
    items: List[BloomingdalesOrderItem] = Field(..., description="List of items in the order")
    items_count: int = Field(0, description="Total number of items in the order")
    shipping_address: str = Field("", description="Normalized shipping address")

    def __init__(self, **data):
        super().__init__(**data)
        self.items_count = len(self.items)


class BloomingdalesEmailParser:
    # Email identification - Order Confirmation (Production)
    BLOOMINGDALES_FROM_EMAIL = "CustomerService@oes.bloomingdales.com"
    SUBJECT_ORDER_PATTERN = r"we\s+received\s+your\s+order"
    
    # Email identification - Development (forwarded emails)
    DEV_BLOOMINGDALES_ORDER_FROM_EMAIL = "glenallagroupc@gmail.com"
    DEV_SUBJECT_ORDER_PATTERN = r"(?:Fwd:\s*)?we\s+received\s+your\s+order"

    def __init__(self):
        """Initialize the Bloomingdale's email parser."""
        self.settings = get_settings()
    
    @property
    def order_from_email(self) -> str:
        """Get the appropriate from email address based on environment."""
        if self.settings.is_development:
            return self.DEV_BLOOMINGDALES_ORDER_FROM_EMAIL
        return self.BLOOMINGDALES_FROM_EMAIL
    
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
            # Forwarded emails might have "Fwd:" prefix, so use a flexible pattern
            return "received your order"
        return "We received your order"

    def is_bloomingdales_email(self, email_data: EmailData) -> bool:
        """Check if email is from Bloomingdale's"""
        sender_lower = email_data.sender.lower()
        
        # In development, check for forwarded emails from dev email address
        if self.settings.is_development:
            if self.DEV_BLOOMINGDALES_ORDER_FROM_EMAIL.lower() in sender_lower:
                # Also check HTML content for Bloomingdale's indicators
                if email_data.html_content:
                    html_lower = email_data.html_content.lower()
                    # Check for Bloomingdale's-specific content
                    if ('bloomingdale' in html_lower or 
                        'emails.bloomingdales.com' in html_lower or
                        'we received your order' in html_lower):
                        return True
                return True
        
        # In production, check for Bloomingdale's email
        if self.BLOOMINGDALES_FROM_EMAIL.lower() in sender_lower:
            return True
        
        # Fallback: check HTML content for Bloomingdale's indicators
        if email_data.html_content:
            html_lower = email_data.html_content.lower()
            if ('bloomingdale' in html_lower and 
                'emails.bloomingdales.com' in html_lower):
                return True
        
        return False

    def is_order_confirmation_email(self, email_data: EmailData) -> bool:
        """Check if email is an order confirmation"""
        subject_lower = email_data.subject.lower()
        pattern = self.order_subject_pattern
        
        # Check subject pattern
        if re.search(pattern, subject_lower, re.IGNORECASE):
            return True
        
        # Also check HTML content for order confirmation indicators
        if email_data.html_content:
            html_lower = email_data.html_content.lower()
            # Check for "We received your order" text in HTML
            if re.search(r'we\s+received\s+your\s+order', html_lower, re.IGNORECASE):
                # Also check for order number pattern (Order #: followed by digits)
                if re.search(r'order\s*#?\s*:?\s*\d+', html_lower, re.IGNORECASE):
                    return True
        
        return False

    def parse_email(self, email_data: EmailData) -> Optional[BloomingdalesOrderData]:
        """
        Parse Bloomingdale's order confirmation email.
        
        Args:
            email_data: EmailData object containing email information
        
        Returns:
            BloomingdalesOrderData object or None if parsing fails
        """
        try:
            html_content = email_data.html_content
            
            if not html_content:
                logger.error("No HTML content in Bloomingdale's email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extract order number from HTML
            order_number = self._extract_order_number(soup)
            if not order_number:
                logger.error("Failed to extract order number from Bloomingdale's email")
                return None
            
            logger.info(f"Extracted Bloomingdale's order number: {order_number}")
            
            # Extract items using BeautifulSoup
            items = self._extract_items(soup)
            
            if not items:
                logger.error("Failed to extract any items from Bloomingdale's email")
                return None
            
            logger.info(f"Successfully extracted {len(items)} items from Bloomingdale's order {order_number}")
            for item in items:
                logger.debug(f"  - {item}")
            
            # Extract shipping address
            shipping_address = self._extract_shipping_address(soup)
            if shipping_address:
                logger.info(f"Extracted shipping address: {shipping_address}")
            
            return BloomingdalesOrderData(order_number=order_number, items=items, shipping_address=shipping_address)
        
        except Exception as e:
            logger.error(f"Error parsing Bloomingdale's email: {e}", exc_info=True)
            return None

    def _extract_order_number(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract order number from Bloomingdale's email HTML.
        
        HTML format: <span style="font-weight:700">Order #:</span> 770138915
        Extract: 770138915
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            Order number or None
        """
        try:
            # Look for "Order #:" text
            order_number_pattern = re.compile(r'Order\s+#:', re.IGNORECASE)
            order_number_text = soup.find(string=order_number_pattern)
            
            if order_number_text:
                # Get the parent element and find the order number after the span
                parent = order_number_text.find_parent()
                if parent:
                    # Get all text from parent and extract number
                    text = parent.get_text()
                    match = re.search(r'Order\s+#:\s*(\d+)', text, re.IGNORECASE)
                    if match:
                        order_number = match.group(1)
                        logger.debug(f"Found Bloomingdale's order number: {order_number}")
                        return order_number
            
            # Fallback: search for pattern in text
            text_content = soup.get_text()
            match = re.search(r'Order\s+#:\s*(\d+)', text_content, re.IGNORECASE)
            if match:
                order_number = match.group(1)
                logger.debug(f"Found Bloomingdale's order number (fallback): {order_number}")
                return order_number
            
            logger.warning("Order number not found in Bloomingdale's email")
            return None
        
        except Exception as e:
            logger.error(f"Error extracting Bloomingdale's order number: {e}")
            return None

    def _extract_items(self, soup: BeautifulSoup) -> List[BloomingdalesOrderItem]:
        """
        Extract order items from Bloomingdale's email.
        
        Bloomingdale's email structure:
        - Products are in table rows with product images and details
        - Each product row contains:
          - Product name in <a> tag
          - Size/Color in <p> tag like "13, Frost White" or "7.5, Frost/Wash"
          - Quantity: "Qty: 6"
          - UPC: "UPC: 7630867894905"
          - Product link (may be tracking link)
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            List of BloomingdalesOrderItem objects
        """
        items = []
        
        try:
            # Find all product containers - look for tables with product images
            # Product images are from images.bloomingdales.com
            product_images = soup.find_all('img', src=lambda x: x and 'images.bloomingdales.com' in str(x))
            
            for img in product_images:
                try:
                    # Find the parent table row or container
                    product_container = img.find_parent('table')
                    if not product_container:
                        continue
                    
                    # Find the parent td that contains this product
                    product_td = img.find_parent('td')
                    if not product_td:
                        continue
                    
                    # Find the sibling td that contains product details
                    parent_row = product_td.find_parent('tr')
                    if not parent_row:
                        continue
                    
                    # Get all tds in this row
                    tds = parent_row.find_all('td')
                    if len(tds) < 2:
                        continue
                    
                    # The product details are usually in the second td
                    details_td = tds[1] if len(tds) > 1 else tds[0]
                    
                    product_details = self._extract_bloomingdales_product_details(details_td, parent_row)
                    
                    if product_details:
                        items.append(product_details)
                
                except Exception as e:
                    logger.error(f"Error processing Bloomingdale's product: {e}")
                    continue
            
            # Log items with ID, size, and quantity
            if items:
                items_summary = [f"(ID: {item.unique_id}, Size: {item.size}, Qty: {item.quantity})" for item in items]
                logger.info(f"[Bloomingdale's] Extracted {len(items)} items: {', '.join(items_summary)}")
            
            return items
        
        except Exception as e:
            logger.error(f"Error extracting Bloomingdale's items: {e}", exc_info=True)
            return []

    def _extract_bloomingdales_product_details(self, details_td, row) -> Optional[BloomingdalesOrderItem]:
        """
        Extract product details from a Bloomingdale's product container.
        
        Returns:
            BloomingdalesOrderItem object or None
        """
        try:
            details = {}
            container_text = details_td.get_text()
            
            # Extract product name - look for <a> tag with product name
            product_link = details_td.find('a', href=lambda x: x and 'bloomingdales.com' in str(x))
            if product_link:
                product_name = product_link.get_text(strip=True)
                details['product_name'] = product_name
                logger.debug(f"Found product name: {product_name}")
            else:
                logger.warning("Product name not found in Bloomingdale's container")
                return None
            
            # Extract size and color - look for pattern like "13, Frost White" or "7.5, Frost/Wash"
            size_color_match = re.search(r'(\d+(?:\.\d+)?)\s*,\s*([^<\n]+?)(?:\s*<br>|\s*Qty:|$)', container_text, re.IGNORECASE)
            if size_color_match:
                size = size_color_match.group(1).strip()
                color_text = size_color_match.group(2).strip()
                details['size'] = size
                details['color'] = color_text
                logger.debug(f"Found size: {size}, color: {color_text}")
            else:
                # Try alternative pattern
                size_match = re.search(r'(\d+(?:\.\d+)?)\s*,', container_text)
                if size_match:
                    size = size_match.group(1).strip()
                    details['size'] = size
                    logger.debug(f"Found size (fallback): {size}")
                else:
                    logger.warning("Size not found in Bloomingdale's container")
                    return None
            
            if not details.get('size'):
                logger.warning("Size not found in Bloomingdale's container")
                return None
            
            # Extract quantity - look for "Qty: 6"
            qty_match = re.search(r'Qty:\s*(\d+)', container_text, re.IGNORECASE)
            if qty_match:
                quantity = int(qty_match.group(1))
                details['quantity'] = quantity
                logger.debug(f"Found quantity: {quantity}")
            else:
                # Default to 1 if not found
                details['quantity'] = 1
                logger.debug("Quantity not found, defaulting to 1")
            
            # Extract UPC - look for "UPC: 7630867894905"
            upc_match = re.search(r'UPC:\s*(\d+)', container_text, re.IGNORECASE)
            if upc_match:
                upc = upc_match.group(1)
                details['upc'] = upc
                logger.debug(f"Found UPC: {upc}")
            
            # Extract unique ID: {color}-{id}
            # Since email only has tracking links, we'll extract color from size/color text
            # and use UPC as the ID part (or try to extract from product name/URL if possible)
            color_name = None
            product_id = None
            
            # Extract color from size/color text
            # Pattern: "13, Frost White" -> "frost", "7.5, Frost/Wash" -> "frost"
            if details.get('color'):
                color_text = details['color']
                # Extract first color word (e.g., "Frost White" -> "frost", "Fade/Desert" -> "fade")
                # Handle cases like "Frost/Wash" -> "frost"
                color_match = re.search(r'([A-Za-z]+)', color_text)
                if color_match:
                    color_name = color_match.group(1).lower()
                    logger.debug(f"Extracted color from text: {color_name}")
            
            # Try to extract product ID from product URL if available
            # Check if product link contains actual product URL (not just tracking link)
            if product_link:
                href = product_link.get('href', '')
                # Check if it's a direct product URL
                if 'bloomingdales.com/shop/product' in href:
                    try:
                        parsed_url = urlparse(href)
                        query_params = parse_qs(parsed_url.query)
                        
                        # Get ID from query parameter
                        if 'ID' in query_params:
                            product_id = query_params['ID'][0]
                            logger.debug(f"Found product ID from URL: {product_id}")
                        
                        # Extract color from URL path if not already found
                        if not color_name:
                            path = parsed_url.path
                            if path:
                                # Pattern: /shop/product/on-womens-cloudmonster-road-running-sneakers-in-frost
                                # Extract last word: "frost"
                                path_parts = path.split('/')
                                if path_parts:
                                    last_part = path_parts[-1]
                                    slug_parts = last_part.split('-')
                                    if slug_parts:
                                        color_name = slug_parts[-1].lower()
                                        logger.debug(f"Extracted color from URL: {color_name}")
                    except Exception as e:
                        logger.debug(f"Could not parse product URL: {e}")
            
            # Fallback: use UPC as ID if product ID not found
            if not product_id and details.get('upc'):
                product_id = details['upc']
                logger.debug(f"Using UPC as product ID: {product_id}")
            
            if not color_name:
                logger.warning("Color not found for unique ID generation")
                return None
            
            if not product_id:
                logger.warning("Product ID not found for unique ID generation")
                return None
            
            # Generate unique ID: {color}-{id}
            unique_id = f"{color_name}-{product_id}"
            details['unique_id'] = unique_id
            logger.debug(f"Generated unique ID: {unique_id}")
            
            # Return only if we have the essential fields
            if details.get('unique_id') and details.get('size'):
                return BloomingdalesOrderItem(
                    unique_id=details['unique_id'],
                    size=details['size'],
                    quantity=details.get('quantity', 1),
                    product_name=details.get('product_name'),
                    upc=details.get('upc'),
                    color=details.get('color')
                )
            
            logger.warning(f"Missing essential fields: {details}")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting Bloomingdale's product details: {e}", exc_info=True)
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
            # Look for "Delivery address:" text
            address_pattern = re.compile(r'Delivery\s+address:', re.IGNORECASE)
            address_text_node = soup.find(string=address_pattern)
            
            if address_text_node:
                # Get the parent element
                parent = address_text_node.find_parent()
                if parent:
                    # Get address text after "Delivery address:"
                    address_text = parent.get_text()
                    # Extract address part after "Delivery address:"
                    match = re.search(r'Delivery\s+address:\s*(.+)', address_text, re.IGNORECASE | re.DOTALL)
                    if match:
                        address = match.group(1).strip()
                        # Clean up any HTML entities or extra whitespace
                        address = re.sub(r'\s+', ' ', address)
                        normalized = normalize_shipping_address(address)
                        logger.debug(f"Extracted shipping address: {normalized}")
                        return normalized
            
            return ""
        
        except Exception as e:
            logger.error(f"Error extracting shipping address: {e}", exc_info=True)
            return ""
