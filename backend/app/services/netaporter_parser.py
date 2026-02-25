"""
NET-A-PORTER Email Parser
Parses order confirmation emails from NET-A-PORTER using BeautifulSoup

Email Format:
- From: customercare@emails.net-a-porter.com (production)
- From: glenallagroupc@gmail.com (dev - forwarded emails)
- Subject: "Thank you for shopping at NET-A-PORTER" or similar
- Order Number: Extract from HTML (e.g., "2411ZRV6V2538M")

HTML Structure:
- Products are listed in tables
- Each product has:
  - Product image: <img src="https://www.net-a-porter.com/variants/images/1647597292414776/in/w96.jpg">
  - Product link: <a href="http://www.net-a-porter.com/shop/product/...">
  - Brand: <a>NIKE</a>
  - Product name: "Dunk Low leather sneakers"
  - Color, Size, Quantity: <span>Black</span> <img> <span>US6</span> <img> <span>Qty: 5</span>

Unique ID Extraction:
- Format: {numeric_id} (e.g., "1647597292414776")
- Extract from product image URL: https://www.net-a-porter.com/variants/images/{numeric_id}/in/w96.jpg
- Pattern: variants/images/(\d+)/in/
- Example: "variants/images/1647597292414776/in/w96.jpg" -> "1647597292414776"
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


class NetAPorterOrderItem(BaseModel):
    unique_id: str = Field(..., description="Unique identifier for the product (e.g., 1647597292414776)")
    size: str = Field(..., description="Size of the product (extracted from US size)")
    quantity: int = Field(..., description="Quantity of the product")
    product_name: Optional[str] = Field(None, description="Name of the product")
    brand: Optional[str] = Field(None, description="Brand name")
    
    def __repr__(self):
        if self.product_name and len(self.product_name) > 50:
            product_display = self.product_name[:50] + "..."
        else:
            product_display = self.product_name or "Unknown"
        return f"<NetAPorterOrderItem(unique_id={self.unique_id}, size={self.size}, qty={self.quantity}, product={product_display})>"


class NetAPorterOrderData(BaseModel):
    order_number: str = Field(..., description="The order number")
    items: List[NetAPorterOrderItem] = Field(..., description="List of items in the order")
    items_count: int = Field(0, description="Total number of items in the order")
    shipping_address: str = Field("", description="Normalized shipping address")

    def __init__(self, **data):
        super().__init__(**data)
        self.items_count = len(self.items)


class NetAPorterEmailParser:
    # Email identification - Order Confirmation (Production)
    NETAPORTER_FROM_EMAIL = "customercare@emails.net-a-porter.com"
    SUBJECT_ORDER_PATTERN = r"thank\s+you\s+for\s+shopping\s+at\s+net-a-porter"
    
    # Email identification - Development (forwarded emails)
    DEV_NETAPORTER_ORDER_FROM_EMAIL = "glenallagroupc@gmail.com"
    DEV_SUBJECT_ORDER_PATTERN = r"(?:Fwd:\s*)?(?:thank\s+you\s+for\s+shopping|order|net-a-porter|netaporter)"

    def __init__(self):
        """Initialize the NET-A-PORTER email parser."""
        self.settings = get_settings()
    
    @property
    def order_from_email(self) -> str:
        """Get the appropriate from email address based on environment."""
        if self.settings.is_development:
            return self.DEV_NETAPORTER_ORDER_FROM_EMAIL
        return self.NETAPORTER_FROM_EMAIL
    
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
            return "Thank you for shopping"
        return "Thank you for shopping at NET-A-PORTER"

    def is_netaporter_email(self, email_data: EmailData) -> bool:
        """Check if email is from NET-A-PORTER"""
        sender_lower = email_data.sender.lower()
        
        # In development, check for forwarded emails from dev email address
        if self.settings.is_development:
            if self.DEV_NETAPORTER_ORDER_FROM_EMAIL.lower() in sender_lower:
                return True
        
        # In production, check for NET-A-PORTER email
        return self.NETAPORTER_FROM_EMAIL.lower() in sender_lower

    def is_order_confirmation_email(self, email_data: EmailData) -> bool:
        """Check if email is an order confirmation"""
        subject_lower = email_data.subject.lower()
        pattern = self.order_subject_pattern
        
        # Use regex matching for subject pattern
        if re.search(pattern, subject_lower, re.IGNORECASE):
            return True
        
        # For forwarded emails in dev mode, also check HTML content for NET-A-PORTER confirmation indicators
        if self.settings.is_development and email_data.html_content:
            html_lower = email_data.html_content.lower()
            # Check for "Thank you for shopping" or order confirmation indicators
            has_confirmation_text = (
                'thank you for shopping' in html_lower or
                'order number' in html_lower or
                ('net-a-porter' in html_lower and 'order' in html_lower) or
                'netaporter' in html_lower
            )
            if has_confirmation_text:
                return True
        
        return False

    def parse_email(self, email_data: EmailData) -> Optional[NetAPorterOrderData]:
        """
        Parse NET-A-PORTER order confirmation email.
        
        Args:
            email_data: EmailData object containing email information
        
        Returns:
            NetAPorterOrderData object or None if parsing fails
        """
        try:
            html_content = email_data.html_content
            
            if not html_content:
                logger.error("No HTML content in NET-A-PORTER email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extract order number from HTML
            order_number = self._extract_order_number(soup)
            if not order_number:
                logger.error("Failed to extract order number from NET-A-PORTER email")
                return None
            
            logger.info(f"Extracted NET-A-PORTER order number: {order_number}")
            
            # Extract items using BeautifulSoup
            items = self._extract_items(soup)
            
            if not items:
                logger.error("Failed to extract any items from NET-A-PORTER email")
                return None
            
            logger.info(f"Successfully extracted {len(items)} items from NET-A-PORTER order {order_number}")
            for item in items:
                logger.debug(f"  - {item}")
            
            # Extract shipping address
            shipping_address = self._extract_shipping_address(soup)
            if shipping_address:
                logger.info(f"Extracted shipping address: {shipping_address}")
            
            return NetAPorterOrderData(order_number=order_number, items=items, shipping_address=shipping_address)
        
        except Exception as e:
            logger.error(f"Error parsing NET-A-PORTER email: {e}", exc_info=True)
            return None

    def _extract_order_number(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract order number from NET-A-PORTER email HTML.
        
        HTML format: 
        - <p style="margin:0"> Order number: <a href="..."> 2411ZRV6V2538M</a></p>
        
        Extract: 2411ZRV6V2538M
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            Order number or None
        """
        try:
            # Method 1: Look for "Order number:" text followed by link
            order_number_p = soup.find('p', string=re.compile(r'Order\s+number:', re.IGNORECASE))
            if order_number_p:
                # Find the link inside this paragraph
                order_link = order_number_p.find('a')
                if order_link:
                    order_number = order_link.get_text(strip=True)
                    logger.debug(f"Found NET-A-PORTER order number: {order_number}")
                    return order_number
            
            # Method 2: Search in text content
            text_content = soup.get_text()
            match = re.search(r'Order\s+number:\s*([A-Z0-9]+)', text_content, re.IGNORECASE)
            if match:
                order_number = match.group(1)
                logger.debug(f"Found NET-A-PORTER order number (fallback): {order_number}")
                return order_number
            
            logger.warning("Order number not found in NET-A-PORTER email")
            return None
        
        except Exception as e:
            logger.error(f"Error extracting NET-A-PORTER order number: {e}")
            return None

    def _extract_items(self, soup: BeautifulSoup) -> List[NetAPorterOrderItem]:
        """
        Extract order items from NET-A-PORTER email.
        
        NET-A-PORTER email structure:
        - Products are in tables with product images and details
        - Each product has:
          - Image with unique ID in URL
          - Brand name in link
          - Product name
          - Color, Size (US format), Quantity separated by diamond images
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            List of NetAPorterOrderItem objects
        """
        items = []
        
        try:
            # Find all product images with NET-A-PORTER variant URLs
            product_images = soup.find_all('img', src=re.compile(r'net-a-porter\.com/variants/images/'))
            
            for img in product_images:
                try:
                    # Find the parent table row that contains this product
                    product_row = img.find_parent('tr')
                    if not product_row:
                        # Try finding parent table
                        product_row = img.find_parent('table')
                    
                    if product_row:
                        product_details = self._extract_netaporter_product_details(product_row, img)
                        
                        if product_details:
                            items.append(product_details)
                
                except Exception as e:
                    logger.error(f"Error processing NET-A-PORTER product: {e}")
                    continue
            
            # Log items with ID, size, and quantity
            if items:
                items_summary = [f"(ID: {item.unique_id}, Size: {item.size}, Qty: {item.quantity})" for item in items]
                logger.info(f"[NET-A-PORTER] Extracted {len(items)} items: {', '.join(items_summary)}")
            
            return items
        
        except Exception as e:
            logger.error(f"Error extracting NET-A-PORTER items: {e}", exc_info=True)
            return []

    def _extract_netaporter_product_details(self, container, img) -> Optional[NetAPorterOrderItem]:
        """
        Extract product details from a NET-A-PORTER product container.
        
        Returns:
            NetAPorterOrderItem object or None
        """
        try:
            details = {}
            
            # Extract unique ID from image URL
            # Pattern: .../variants/images/1647597292414776/in/w96.jpg
            # Extract: 1647597292414776
            img_src = img.get('src', '')
            unique_id = self._extract_unique_id_from_image(img_src)
            
            if not unique_id:
                logger.warning(f"Unique ID not found in image URL: {img_src[:100]}")
                return None
            
            details['unique_id'] = unique_id
            logger.debug(f"Found unique ID: {unique_id}")
            
            # Extract brand - look for link with brand name
            brand_link = container.find('a', href=re.compile(r'net-a-porter\.com/shop/product'))
            if brand_link:
                brand = brand_link.get_text(strip=True)
                details['brand'] = brand
                logger.debug(f"Found brand: {brand}")
            
            # Extract product name - look for td with style="padding:0" that contains product name
            # Or td with class containing "label-1-description"
            product_name_td = container.find('td', style=lambda x: x and 'padding:0' in str(x))
            if not product_name_td:
                product_name_td = container.find('td', class_=lambda x: x and 'label-1-description' in str(x))
            
            if product_name_td:
                product_name = product_name_td.get_text(strip=True)
                details['product_name'] = product_name
                logger.debug(f"Found product name: {product_name}")
            
            # Extract size and quantity from the details row
            # Format: <td style="padding:8px 0"> <span>Black</span> <img> <span>US6</span> <img> <span>Qty: 5</span> </td>
            # Look for td with style="padding:8px 0" or class containing "label-1" and "color-gr-2"
            details_td = container.find('td', style=lambda x: x and 'padding:8px 0' in str(x))
            if not details_td:
                details_td = container.find('td', class_=lambda x: x and 'label-1' in str(x) and 'color-gr-2' in str(x))
            if not details_td:
                details_td = container.find('td', class_=lambda x: x and 'label-1' in str(x))
            
            if details_td:
                # Extract size - look for span that contains US followed by number
                size_spans = details_td.find_all('span')
                size = None
                for span in size_spans:
                    span_text = span.get_text(strip=True)
                    size_match = re.search(r'US(\d+(?:\.\d+)?)', span_text, re.IGNORECASE)
                    if size_match:
                        size = size_match.group(1)
                        logger.debug(f"Found size from span: {size}")
                        break
                
                # If not found in spans, try the td text
                if not size:
                    container_text = details_td.get_text()
                    size_match = re.search(r'US(\d+(?:\.\d+)?)', container_text, re.IGNORECASE)
                    if size_match:
                        size = size_match.group(1)
                        logger.debug(f"Found size from td text: {size}")
                
                if size:
                    details['size'] = size
                else:
                    logger.warning(f"Size not found in product details. Text: {details_td.get_text()[:100]}")
                    return None
                
                # Extract quantity - look for span with "Qty: N"
                quantity = None
                for span in size_spans:
                    span_text = span.get_text(strip=True)
                    qty_match = re.search(r'Qty:\s*(\d+)', span_text, re.IGNORECASE)
                    if qty_match:
                        quantity = int(qty_match.group(1))
                        logger.debug(f"Found quantity from span: {quantity}")
                        break
                
                # If not found in spans, try the td text
                if quantity is None:
                    container_text = details_td.get_text()
                    qty_match = re.search(r'Qty:\s*(\d+)', container_text, re.IGNORECASE)
                    if qty_match:
                        quantity = int(qty_match.group(1))
                        logger.debug(f"Found quantity from td text: {quantity}")
                    else:
                        quantity = 1
                        logger.debug("Quantity not found, defaulting to 1")
                
                details['quantity'] = quantity
            else:
                # Fallback: search in entire container text
                container_text = container.get_text()
                size_match = re.search(r'US(\d+(?:\.\d+)?)', container_text, re.IGNORECASE)
                if size_match:
                    size = size_match.group(1)
                    details['size'] = size
                    logger.debug(f"Found size (fallback): {size}")
                else:
                    logger.warning("Product details row not found and size not found in container")
                    return None
                
                qty_match = re.search(r'Qty:\s*(\d+)', container_text, re.IGNORECASE)
                if qty_match:
                    quantity = int(qty_match.group(1))
                    details['quantity'] = quantity
                else:
                    quantity = 1
                    details['quantity'] = quantity
            
            return NetAPorterOrderItem(
                unique_id=details['unique_id'],
                size=details['size'],
                quantity=details['quantity'],
                product_name=details.get('product_name'),
                brand=details.get('brand')
            )
            
        except Exception as e:
            logger.error(f"Error extracting NET-A-PORTER product details: {e}", exc_info=True)
            return None
    
    def _extract_unique_id_from_image(self, img_src: str) -> Optional[str]:
        """
        Extract unique ID from NET-A-PORTER product image URL.
        
        URL format: 
        https://www.net-a-porter.com/variants/images/1647597292414776/in/w96.jpg
        
        Extract: 1647597292414776
        
        Args:
            img_src: Image source URL
        
        Returns:
            Unique ID or None
        """
        try:
            # Pattern: variants/images/(\d+)/in/
            match = re.search(r'variants/images/(\d+)/in/', img_src)
            if match:
                unique_id = match.group(1)
                logger.debug(f"Extracted unique ID from image URL: {unique_id}")
                return unique_id
            
            logger.warning(f"Could not extract unique ID from URL: {img_src[:100]}")
            return None
        
        except Exception as e:
            logger.error(f"Error extracting unique ID from URL: {e}")
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
            # Look for "SHIP TO" header
            ship_to_p = soup.find('p', string=re.compile(r'SHIP\s+TO', re.IGNORECASE))
            
            if ship_to_p:
                # Find the address div in the next sibling or parent's next sibling
                address_div = ship_to_p.find_next('div')
                if address_div:
                    # Get address text, handling <br> tags
                    address_text = address_div.get_text(separator=' ', strip=True)
                    
                    if address_text:
                        normalized = normalize_shipping_address(address_text)
                        logger.debug(f"Extracted shipping address: {normalized}")
                        return normalized
            
            return ""
        
        except Exception as e:
            logger.error(f"Error extracting shipping address: {e}", exc_info=True)
            return ""
