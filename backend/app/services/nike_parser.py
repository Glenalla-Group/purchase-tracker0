"""
Nike Email Parser
Parses order confirmation emails from Nike using BeautifulSoup

Email Format:
- From: nike@official.nike.com (production)
- From: glenallagroupc@gmail.com (dev - forwarded emails)
- Subject: "Thanks for your order" or similar
- Order Number: Extract from HTML (e.g., "C01540217327")

HTML Structure:
- Products are listed in tables with class "dynamicProductContainer__link"
- Each product has:
  - Product link: href contains URL-encoded nike.com/t/{product-slug}
  - Product name: <div>Nike Shox R4</div>
  - Category: <div>Men's Shoes</div>
  - Size: <div>Size: M 10.5 / W 12</div>
  - Quantity: <div>Qty: 2</div>
  - Price: <div>$100.46</div>

Unique ID Extraction:
- Format: {product-slug}
- Extract from product link URL: https://www.nike.com/t/{product-slug}
- Example: "shox-r4-mens-shoes-0PISn0m1"
"""

import re
import logging
import urllib.parse
from typing import List, Optional
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from app.models.email import EmailData
from app.utils.address_utils import normalize_shipping_address
from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class NikeOrderItem(BaseModel):
    unique_id: str = Field(..., description="Unique identifier for the product (e.g., shox-r4-mens-shoes-0PISn0m1)")
    size: str = Field(..., description="Size of the product (extracted from M size)")
    quantity: int = Field(..., description="Quantity of the product")
    product_name: Optional[str] = Field(None, description="Name of the product")
    category: Optional[str] = Field(None, description="Product category")
    
    def __repr__(self):
        if self.product_name and len(self.product_name) > 50:
            product_display = self.product_name[:50] + "..."
        else:
            product_display = self.product_name or "Unknown"
        return f"<NikeOrderItem(unique_id={self.unique_id}, size={self.size}, qty={self.quantity}, product={product_display})>"


class NikeOrderData(BaseModel):
    order_number: str = Field(..., description="The order number")
    items: List[NikeOrderItem] = Field(..., description="List of items in the order")
    items_count: int = Field(0, description="Total number of items in the order")
    shipping_address: str = Field("", description="Normalized shipping address")

    def __init__(self, **data):
        super().__init__(**data)
        self.items_count = len(self.items)


class NikeEmailParser:
    # Email identification - Order Confirmation (Production)
    NIKE_FROM_EMAIL = "nike@official.nike.com"
    SUBJECT_ORDER_PATTERN = r"thanks\s+for\s+your\s+order"
    
    # Email identification - Development (forwarded emails)
    DEV_NIKE_ORDER_FROM_EMAIL = "glenallagroupc@gmail.com"
    # Require "thanks for your order" - avoid matching generic "order" (e.g. Footlocker "Your order is ready to go")
    DEV_SUBJECT_ORDER_PATTERN = r"(?:Fwd:\s*)?thanks\s+for\s+your\s+order"

    def __init__(self):
        """Initialize the Nike email parser."""
        self.settings = get_settings()
    
    @property
    def order_from_email(self) -> str:
        """Get the appropriate from email address based on environment."""
        if self.settings.is_development:
            return self.DEV_NIKE_ORDER_FROM_EMAIL
        return self.NIKE_FROM_EMAIL
    
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

    def is_nike_email(self, email_data: EmailData) -> bool:
        """
        Check if email is from Nike.
        
        In dev mode, both ASOS and Nike forward from glenallagroupc with "Thanks for your order".
        Differentiate via HTML: Nike has nike.com; ASOS has asos.com or images.asos-media.com.
        """
        sender_lower = email_data.sender.lower()
        
        # In development, both ASOS and Nike forward from glenallagroupc - check HTML content
        if self.settings.is_development:
            if self.DEV_NIKE_ORDER_FROM_EMAIL.lower() in sender_lower:
                html = (email_data.html_content or "").lower()
                # ASOS has asos.com or asos-media - don't claim it's Nike
                if "asos.com" in html or "images.asos-media.com" in html:
                    return False
                return True
        
        # In production, check for Nike email
        return self.NIKE_FROM_EMAIL.lower() in sender_lower

    def is_order_confirmation_email(self, email_data: EmailData) -> bool:
        """Check if email is an order confirmation"""
        subject_lower = email_data.subject.lower()
        pattern = self.order_subject_pattern
        
        # Use regex matching for subject pattern
        if re.search(pattern, subject_lower, re.IGNORECASE):
            return True
        
        # For forwarded emails in dev mode, also check HTML content for Nike confirmation indicators
        if self.settings.is_development and email_data.html_content:
            html_lower = email_data.html_content.lower()
            # Check for "Thanks for your order" or order confirmation indicators
            has_confirmation_text = (
                'thanks for your order' in html_lower or
                'order number' in html_lower or
                ('nike.com' in html_lower and 'order' in html_lower)
            )
            if has_confirmation_text:
                return True
        
        return False

    def parse_email(self, email_data: EmailData) -> Optional[NikeOrderData]:
        """
        Parse Nike order confirmation email.
        
        Args:
            email_data: EmailData object containing email information
        
        Returns:
            NikeOrderData object or None if parsing fails
        """
        try:
            html_content = email_data.html_content
            
            if not html_content:
                logger.error("No HTML content in Nike email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extract order number from HTML
            order_number = self._extract_order_number(soup)
            if not order_number:
                logger.error("Failed to extract order number from Nike email")
                return None
            
            logger.info(f"Extracted Nike order number: {order_number}")
            
            # Extract items using BeautifulSoup
            items = self._extract_items(soup)
            
            if not items:
                logger.error("Failed to extract any items from Nike email")
                return None
            
            logger.info(f"Successfully extracted {len(items)} items from Nike order {order_number}")
            for item in items:
                logger.debug(f"  - {item}")
            
            # Extract shipping address
            shipping_address = self._extract_shipping_address(soup)
            if shipping_address:
                logger.info(f"Extracted shipping address: {shipping_address}")
            
            return NikeOrderData(order_number=order_number, items=items, shipping_address=shipping_address)
        
        except Exception as e:
            logger.error(f"Error parsing Nike email: {e}", exc_info=True)
            return None

    def _extract_order_number(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract order number from Nike email HTML.
        
        HTML format: 
        - Line 8: <div>Order #: C01540217327</div>
        - Line 607: <p>C01540217327</p> (in Order Number section)
        
        Extract: C01540217327
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            Order number or None
        """
        try:
            # Method 1: Look for "Order #:" text
            order_pattern = re.compile(r'Order\s*#?\s*:?\s*', re.IGNORECASE)
            order_elements = soup.find_all(string=order_pattern)
            
            for element in order_elements:
                # Get parent element
                parent = element.parent if hasattr(element, 'parent') else element.find_parent()
                if parent:
                    parent_text = parent.get_text()
                    # Look for order number pattern (C followed by digits)
                    match = re.search(r'Order\s*#?\s*:?\s*(C\d+)', parent_text, re.IGNORECASE)
                    if match:
                        order_number = match.group(1)
                        logger.debug(f"Found Nike order number: {order_number}")
                        return order_number
            
            # Method 2: Look for "Order Number" header followed by the number
            order_number_header = soup.find('p', string=re.compile(r'Order\s+Number', re.IGNORECASE))
            if order_number_header:
                # Find the next <p> tag with the order number
                next_p = order_number_header.find_next_sibling('p')
                if not next_p:
                    # Try finding in parent's next sibling
                    parent = order_number_header.find_parent()
                    if parent:
                        next_p = parent.find_next('p')
                
                if next_p:
                    order_text = next_p.get_text(strip=True)
                    # Check if it matches order number pattern
                    if re.match(r'^C\d+$', order_text):
                        logger.debug(f"Found Nike order number (Order Number section): {order_text}")
                        return order_text
            
            # Method 3: Search for pattern in text
            text_content = soup.get_text()
            match = re.search(r'Order\s*#?\s*:?\s*(C\d+)', text_content, re.IGNORECASE)
            if match:
                order_number = match.group(1)
                logger.debug(f"Found Nike order number (fallback): {order_number}")
                return order_number
            
            logger.warning("Order number not found in Nike email")
            return None
        
        except Exception as e:
            logger.error(f"Error extracting Nike order number: {e}")
            return None

    def _extract_items(self, soup: BeautifulSoup) -> List[NikeOrderItem]:
        """
        Extract order items from Nike email.
        
        Nike email structure:
        - Products are in links with class "dynamicProductContainer__link"
        - Each product container has:
          - Link with href containing URL-encoded nike.com/t/{product-slug}
          - Product name in <div> with font-weight:500
          - Category in <div> with color:#757575
          - Size in <div> with "Size: M X / W Y" format
          - Quantity in <div> with "Qty: N"
          - Price in <div> with font-weight:500 and color:#111111
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            List of NikeOrderItem objects
        """
        items = []
        
        try:
            # Find all product links with class "dynamicProductContainer__link"
            product_links = soup.find_all('a', class_=lambda x: x and 'dynamicProductContainer__link' in str(x))
            
            for link in product_links:
                try:
                    product_details = self._extract_nike_product_details(link)
                    
                    if product_details:
                        items.append(product_details)
                
                except Exception as e:
                    logger.error(f"Error processing Nike product link: {e}")
                    continue
            
            # Log items with ID, size, and quantity
            if items:
                items_summary = [f"(ID: {item.unique_id}, Size: {item.size}, Qty: {item.quantity})" for item in items]
                logger.info(f"[Nike] Extracted {len(items)} items: {', '.join(items_summary)}")
            
            return items
        
        except Exception as e:
            logger.error(f"Error extracting Nike items: {e}", exc_info=True)
            return []

    def _extract_nike_product_details(self, link) -> Optional[NikeOrderItem]:
        """
        Extract product details from a Nike product link.
        
        Returns:
            NikeOrderItem object or None
        """
        try:
            details = {}
            
            # Extract unique ID from product link URL
            # URL is URL-encoded in href: https://www.nike.com/t/shox-r4-mens-shoes-0PISn0m1
            href = link.get('href', '')
            unique_id = self._extract_unique_id_from_url(href)
            
            if not unique_id:
                logger.warning("Unique ID not found in Nike product link")
                return None
            
            details['unique_id'] = unique_id
            logger.debug(f"Found unique ID: {unique_id}")
            
            # Find the parent container (table) that contains all product details
            product_container = link.find_parent('table')
            if not product_container:
                # Try finding parent td or div
                product_container = link.find_parent(['td', 'div'])
            
            if not product_container:
                logger.warning("Product container not found")
                return None
            
            container_text = product_container.get_text()
            
            # Extract product name - look for <div> with font-weight:500 and color:#111111
            product_name_div = product_container.find('div', style=lambda x: x and 'font-weight:500' in str(x) and 'color:#111111' in str(x))
            if product_name_div:
                product_name = product_name_div.get_text(strip=True)
                details['product_name'] = product_name
                logger.debug(f"Found product name: {product_name}")
            
            # Extract category - look for <div> with color:#757575 (usually after product name)
            category_divs = product_container.find_all('div', style=lambda x: x and 'color:#757575' in str(x))
            for div in category_divs:
                div_text = div.get_text(strip=True)
                # Category is usually something like "Men's Shoes", "Women's Shoes", etc.
                if div_text and not div_text.startswith('Size:') and not div_text.startswith('Qty:'):
                    if not re.match(r'^\$[\d,]+\.?\d*$', div_text):  # Not a price
                        details['category'] = div_text
                        logger.debug(f"Found category: {div_text}")
                        break
            
            # Extract size - look for "Size: M X / W Y" pattern
            size_match = re.search(r'Size:\s*(M\s+[\d.]+(?:\s*/\s*W\s+[\d.]+)?)', container_text, re.IGNORECASE)
            if size_match:
                size_text = size_match.group(1)
                # Extract just the men's size (M X)
                men_size_match = re.search(r'M\s+([\d.]+)', size_text, re.IGNORECASE)
                if men_size_match:
                    size = men_size_match.group(1)
                    details['size'] = size
                    logger.debug(f"Found size: {size}")
                else:
                    # Fallback: use the full size text
                    details['size'] = size_text.strip()
                    logger.debug(f"Found size (full): {size_text}")
            else:
                logger.warning("Size not found in Nike product container")
                return None
            
            # Extract quantity - look for "Qty: N" pattern
            qty_match = re.search(r'Qty:\s*(\d+)', container_text, re.IGNORECASE)
            if qty_match:
                quantity = int(qty_match.group(1))
                details['quantity'] = quantity
                logger.debug(f"Found quantity: {quantity}")
            else:
                # Default to 1 if not found
                details['quantity'] = 1
                logger.debug("Quantity not found, defaulting to 1")
            
            # Return only if we have the essential fields
            if details.get('unique_id') and details.get('size'):
                return NikeOrderItem(
                    unique_id=details['unique_id'],
                    size=details['size'],
                    quantity=details.get('quantity', 1),
                    product_name=details.get('product_name'),
                    category=details.get('category')
                )
            
            logger.warning(f"Missing essential fields: {details}")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting Nike product details: {e}", exc_info=True)
            return None
    
    def _extract_unique_id_from_url(self, href: str) -> Optional[str]:
        """
        Extract unique ID from Nike product URL.
        
        URL format (URL-encoded): 
        https://www.nike.com/t/shox-r4-mens-shoes-0PISn0m1
        
        Extract: shox-r4-mens-shoes-0PISn0m1
        
        Args:
            href: URL string (may be URL-encoded)
        
        Returns:
            Unique ID (product slug) or None
        """
        try:
            # Decode URL if it's encoded
            try:
                decoded_url = urllib.parse.unquote(href)
            except:
                decoded_url = href
            
            # Look for pattern: nike.com/t/{product-slug}
            # The slug can contain letters, numbers, hyphens
            match = re.search(r'nike\.com/t/([a-z0-9-]+)', decoded_url, re.IGNORECASE)
            if match:
                unique_id = match.group(1)
                logger.debug(f"Extracted unique ID from URL: {unique_id}")
                return unique_id
            
            logger.warning(f"Could not extract unique ID from URL: {href[:100]}")
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
            # Look for "Shipping Address" header
            shipping_header = soup.find('p', string=re.compile(r'Shipping\s+Address', re.IGNORECASE))
            
            if shipping_header:
                # Find the address text in the next div or p
                address_div = shipping_header.find_next('div')
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
