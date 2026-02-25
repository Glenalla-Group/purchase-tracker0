"""
Carbon38 Email Parser
Parses order confirmation emails from Carbon38 using BeautifulSoup

Email Format:
- From: customercare@carbon38.com (production)
- From: glenallagroupc@gmail.com (dev - forwarded emails)
- Subject: "Looking good" or similar
- Order Number: Extract from HTML (e.g., "C38-1603992")

HTML Structure:
- Products are listed in tables
- Each product has:
  - Product name: <h4>Nike V2k Run - Summit White/Metallic Silver</h4>
  - Size: <strong>Size: <span>5.5</span></strong>
  - Quantity: <strong>Quantity: <span>1</span></strong>
  - Total: <strong>Total:</strong> $106.00

Unique ID Extraction:
- Format: {product-slug} (e.g., "cloudvista-glacier-eclipse")
- Extract from product URL if available: https://carbon38.com/products/{product-slug}
- If URL not available, generate from product name by converting to slug format
- Remove numbers and extra hyphens to simplify (e.g., "cloudvista-2-glacier-eclipse" -> "cloudvista-glacier-eclipse")
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


class Carbon38OrderItem(BaseModel):
    unique_id: str = Field(..., description="Unique identifier for the product (e.g., cloudvista-glacier-eclipse)")
    size: str = Field(..., description="Size of the product")
    quantity: int = Field(..., description="Quantity of the product")
    product_name: Optional[str] = Field(None, description="Name of the product")
    
    def __repr__(self):
        if self.product_name and len(self.product_name) > 50:
            product_display = self.product_name[:50] + "..."
        else:
            product_display = self.product_name or "Unknown"
        return f"<Carbon38OrderItem(unique_id={self.unique_id}, size={self.size}, qty={self.quantity}, product={product_display})>"


class Carbon38OrderData(BaseModel):
    order_number: str = Field(..., description="The order number")
    items: List[Carbon38OrderItem] = Field(..., description="List of items in the order")
    items_count: int = Field(0, description="Total number of items in the order")
    shipping_address: str = Field("", description="Normalized shipping address")

    def __init__(self, **data):
        super().__init__(**data)
        self.items_count = len(self.items)


class Carbon38EmailParser:
    # Email identification - Order Confirmation (Production)
    CARBON38_FROM_EMAIL = "customercare@carbon38.com"
    SUBJECT_ORDER_PATTERN = r"looking\s+good"
    
    # Email identification - Development (forwarded emails)
    DEV_CARBON38_ORDER_FROM_EMAIL = "glenallagroupc@gmail.com"
    # Must match "Looking good" or "carbon38" - avoid broad "order" which matches ASOS shipping, Nike, etc.
    DEV_SUBJECT_ORDER_PATTERN = r"(?:Fwd:\s*)?(?:looking\s+good|carbon38)"

    def __init__(self):
        """Initialize the Carbon38 email parser."""
        self.settings = get_settings()
    
    @property
    def order_from_email(self) -> str:
        """Get the appropriate from email address based on environment."""
        if self.settings.is_development:
            return self.DEV_CARBON38_ORDER_FROM_EMAIL
        return self.CARBON38_FROM_EMAIL
    
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
            return "Looking good"
        return "Looking good"

    def is_carbon38_email(self, email_data: EmailData) -> bool:
        """
        Check if email is from Carbon38.
        
        In dev mode, both Carbon38 and ASOS/Nike forward from glenallagroupc.
        Differentiate: Carbon38 has "carbon38" or "looking good" in subject/HTML.
        If subject is "Your order's on its way!" -> ASOS shipping, not Carbon38.
        """
        sender_lower = email_data.sender.lower()
        
        # ASOS shipping subject is unique - don't claim it's Carbon38
        subject_lower = (email_data.subject or "").lower()
        if re.search(r"your order'?s?\s+on its way", subject_lower):
            return False
        
        # In development, check for forwarded emails from dev email address
        if self.settings.is_development:
            if self.DEV_CARBON38_ORDER_FROM_EMAIL.lower() in sender_lower:
                html = (email_data.html_content or "").lower()
                # Require carbon38 or "looking good" in content - avoid claiming ASOS/Nike forwards
                if "carbon38" in html or "looking good" in html or "c38-" in html:
                    return True
                return False
        
        # In production, check for Carbon38 email
        return self.CARBON38_FROM_EMAIL.lower() in sender_lower

    def is_order_confirmation_email(self, email_data: EmailData) -> bool:
        """Check if email is an order confirmation"""
        subject_lower = email_data.subject.lower()
        pattern = self.order_subject_pattern
        
        # Use regex matching for subject pattern
        if re.search(pattern, subject_lower, re.IGNORECASE):
            return True
        
        # For forwarded emails in dev mode, also check HTML content for Carbon38 confirmation indicators
        if self.settings.is_development and email_data.html_content:
            html_lower = email_data.html_content.lower()
            # Check for "Thanks for your order" or order confirmation indicators
            has_confirmation_text = (
                'thanks for your order' in html_lower or
                'order number' in html_lower or
                ('carbon38' in html_lower and 'order' in html_lower) or
                'c38-' in html_lower
            )
            if has_confirmation_text:
                return True
        
        return False

    def parse_email(self, email_data: EmailData) -> Optional[Carbon38OrderData]:
        """
        Parse Carbon38 order confirmation email.
        
        Args:
            email_data: EmailData object containing email information
        
        Returns:
            Carbon38OrderData object or None if parsing fails
        """
        try:
            html_content = email_data.html_content
            
            if not html_content:
                logger.error("No HTML content in Carbon38 email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extract order number from HTML
            order_number = self._extract_order_number(soup)
            if not order_number:
                logger.error("Failed to extract order number from Carbon38 email")
                return None
            
            logger.info(f"Extracted Carbon38 order number: {order_number}")
            
            # Extract items using BeautifulSoup
            items = self._extract_items(soup)
            
            if not items:
                logger.error("Failed to extract any items from Carbon38 email")
                return None
            
            logger.info(f"Successfully extracted {len(items)} items from Carbon38 order {order_number}")
            for item in items:
                logger.debug(f"  - {item}")
            
            # Extract shipping address
            shipping_address = self._extract_shipping_address(soup)
            if shipping_address:
                logger.info(f"Extracted shipping address: {shipping_address}")
            
            return Carbon38OrderData(order_number=order_number, items=items, shipping_address=shipping_address)
        
        except Exception as e:
            logger.error(f"Error parsing Carbon38 email: {e}", exc_info=True)
            return None

    def _extract_order_number(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract order number from Carbon38 email HTML.
        
        HTML format: 
        - "Thanks for your order! Your order number is <br><span style="font-weight:bold">C38-1603992</span>."
        
        Extract: C38-1603992
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            Order number or None
        """
        try:
            # Method 1: Look for "order number is" text followed by C38- pattern
            text_content = soup.get_text()
            match = re.search(r'order\s+number\s+is.*?(C38-\d+)', text_content, re.IGNORECASE | re.DOTALL)
            if match:
                order_number = match.group(1)
                logger.debug(f"Found Carbon38 order number: {order_number}")
                return order_number
            
            # Method 2: Look for C38- pattern directly
            match = re.search(r'(C38-\d+)', text_content, re.IGNORECASE)
            if match:
                order_number = match.group(1)
                logger.debug(f"Found Carbon38 order number (fallback): {order_number}")
                return order_number
            
            logger.warning("Order number not found in Carbon38 email")
            return None
        
        except Exception as e:
            logger.error(f"Error extracting Carbon38 order number: {e}")
            return None

    def _extract_items(self, soup: BeautifulSoup) -> List[Carbon38OrderItem]:
        """
        Extract order items from Carbon38 email.
        
        Carbon38 email structure:
        - Products are in table rows with product details
        - Each product has:
          - Product name in <h4> tag
          - Size in <strong>Size: <span>X</span></strong>
          - Quantity in <strong>Quantity: <span>N</span></strong>
          - Total price
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            List of Carbon38OrderItem objects
        """
        items = []
        
        try:
            # Find all h4 tags that contain product names (they're in the order summary section)
            # Look for the "Order Summary:" header first
            order_summary_header = soup.find('h3', string=re.compile(r'Order\s+Summary', re.IGNORECASE))
            
            if not order_summary_header:
                # Try alternative: look for all h4 tags that might be product names
                product_h4s = soup.find_all('h4')
            else:
                # Find all h4 tags after the Order Summary header
                order_summary_section = order_summary_header.find_parent()
                if order_summary_section:
                    product_h4s = order_summary_section.find_all_next('h4', limit=20)
                else:
                    product_h4s = soup.find_all('h4')
            
            for h4 in product_h4s:
                try:
                    product_name = h4.get_text(strip=True)
                    
                    # Skip if it's not a product name (too short or looks like a header)
                    if len(product_name) < 5 or product_name.lower() in ['billing address:', 'shipping address:']:
                        continue
                    
                    # Find the parent container (td) that contains this product's details
                    product_container = h4.find_parent('td')
                    if not product_container:
                        product_container = h4.find_parent('div')
                    
                    if not product_container:
                        continue
                    
                    product_details = self._extract_carbon38_product_details(product_container, product_name)
                    
                    if product_details:
                        items.append(product_details)
                
                except Exception as e:
                    logger.error(f"Error processing Carbon38 product: {e}")
                    continue
            
            # Log items with ID, size, and quantity
            if items:
                items_summary = [f"(ID: {item.unique_id}, Size: {item.size}, Qty: {item.quantity})" for item in items]
                logger.info(f"[Carbon38] Extracted {len(items)} items: {', '.join(items_summary)}")
            
            return items
        
        except Exception as e:
            logger.error(f"Error extracting Carbon38 items: {e}", exc_info=True)
            return []

    def _extract_carbon38_product_details(self, container, product_name: str) -> Optional[Carbon38OrderItem]:
        """
        Extract product details from a Carbon38 product container.
        
        Returns:
            Carbon38OrderItem object or None
        """
        try:
            container_text = container.get_text()
            
            # Extract size - look for "Size: X" pattern
            # Find all strong tags and check their text content
            size = None
            strong_tags = container.find_all('strong')
            for strong in strong_tags:
                strong_text = strong.get_text()
                if 'Size:' in strong_text:
                    # Find the span inside the strong tag
                    size_span = strong.find('span')
                    if size_span:
                        size = size_span.get_text(strip=True)
                        break
                    else:
                        # Extract from strong tag text directly
                        size_match = re.search(r'Size:\s*([^\s<]+)', strong_text, re.IGNORECASE)
                        if size_match:
                            size = size_match.group(1).strip()
                            break
            
            if not size:
                # Fallback: search in container text
                size_match = re.search(r'Size:\s*([^\s<]+)', container_text, re.IGNORECASE)
                if size_match:
                    size = size_match.group(1).strip()
                else:
                    logger.warning(f"Size not found for product: {product_name}")
                    return None
            
            # Extract quantity - look for "Quantity: N" pattern
            quantity = None
            for strong in strong_tags:
                strong_text = strong.get_text()
                if 'Quantity:' in strong_text:
                    # Find the span inside the strong tag
                    qty_span = strong.find('span')
                    if qty_span:
                        quantity = int(qty_span.get_text(strip=True))
                        break
                    else:
                        # Extract from strong tag text directly
                        qty_match = re.search(r'Quantity:\s*(\d+)', strong_text, re.IGNORECASE)
                        if qty_match:
                            quantity = int(qty_match.group(1))
                            break
            
            if quantity is None:
                # Fallback: search in container text
                qty_match = re.search(r'Quantity:\s*(\d+)', container_text, re.IGNORECASE)
                if qty_match:
                    quantity = int(qty_match.group(1))
                else:
                    quantity = 1
                    logger.debug(f"Quantity not found for product {product_name}, defaulting to 1")
            
            # Extract unique ID from product name or URL
            unique_id = self._extract_unique_id(container, product_name)
            
            if not unique_id:
                logger.warning(f"Could not generate unique ID for product: {product_name}")
                return None
            
            return Carbon38OrderItem(
                unique_id=unique_id,
                size=size,
                quantity=quantity,
                product_name=product_name
            )
            
        except Exception as e:
            logger.error(f"Error extracting Carbon38 product details: {e}", exc_info=True)
            return None
    
    def _extract_unique_id(self, container, product_name: str) -> Optional[str]:
        """
        Extract unique ID from product URL or generate from product name.
        
        Priority:
        1. Extract from product URL if available: https://carbon38.com/products/{product-slug}
        2. Generate from product name by converting to slug format
        
        Format: Remove numbers and extra hyphens
        Example: "cloudvista-2-glacier-eclipse" -> "cloudvista-glacier-eclipse"
        
        Args:
            container: BeautifulSoup element containing product details
            product_name: Product name string
        
        Returns:
            Unique ID or None
        """
        try:
            # Method 1: Try to extract from product URL
            # Look for links in the container
            links = container.find_all('a', href=True)
            for link in links:
                href = link.get('href', '')
                # Decode URL if it's encoded
                try:
                    decoded_url = urllib.parse.unquote(href)
                except:
                    decoded_url = href
                
                # Look for carbon38.com/products/{product-slug} pattern
                match = re.search(r'carbon38\.com/products/([a-z0-9-]+)', decoded_url, re.IGNORECASE)
                if match:
                    product_slug = match.group(1).lower()
                    # Simplify: remove numbers and extra hyphens
                    unique_id = self._simplify_slug(product_slug)
                    logger.debug(f"Extracted unique ID from URL: {unique_id}")
                    return unique_id
            
            # Method 2: Generate from product name
            # Convert product name to slug format
            slug = self._product_name_to_slug(product_name)
            if slug:
                unique_id = self._simplify_slug(slug)
                logger.debug(f"Generated unique ID from product name: {unique_id}")
                return unique_id
            
            return None
        
        except Exception as e:
            logger.error(f"Error extracting unique ID: {e}")
            return None
    
    def _product_name_to_slug(self, product_name: str) -> str:
        """
        Convert product name to slug format.
        
        Example: "Nike V2k Run - Summit White/Metallic Silver" -> "nike-v2k-run-summit-white-metallic-silver"
        
        Args:
            product_name: Product name string
        
        Returns:
            Slug string
        """
        # Convert to lowercase
        slug = product_name.lower()
        
        # Replace special characters with hyphens
        slug = re.sub(r'[^\w\s-]', '-', slug)
        
        # Replace spaces and multiple hyphens with single hyphen
        slug = re.sub(r'[\s-]+', '-', slug)
        
        # Remove leading/trailing hyphens
        slug = slug.strip('-')
        
        return slug
    
    def _simplify_slug(self, slug: str) -> str:
        """
        Simplify slug by removing numbers and extra hyphens.
        
        Example: "cloudvista-2-glacier-eclipse" -> "cloudvista-glacier-eclipse"
        
        Args:
            slug: Slug string
        
        Returns:
            Simplified slug string
        """
        # Remove standalone numbers (not part of words)
        # This regex removes numbers that are surrounded by hyphens or at start/end
        slug = re.sub(r'-?\d+-?', '-', slug)
        
        # Replace multiple consecutive hyphens with single hyphen
        slug = re.sub(r'-+', '-', slug)
        
        # Remove leading/trailing hyphens
        slug = slug.strip('-')
        
        return slug
    
    def _extract_shipping_address(self, soup: BeautifulSoup) -> str:
        """
        Extract shipping address from email and normalize it.
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            Normalized shipping address or empty string
        """
        try:
            # Look for "Shipping Address:" header
            shipping_header = soup.find('h4', string=re.compile(r'Shipping\s+Address', re.IGNORECASE))
            
            if shipping_header:
                # Find the address text in the next p or div
                address_element = shipping_header.find_next(['p', 'div'])
                if address_element:
                    # Get address text, handling <br> tags
                    address_text = address_element.get_text(separator=' ', strip=True)
                    
                    if address_text:
                        normalized = normalize_shipping_address(address_text)
                        logger.debug(f"Extracted shipping address: {normalized}")
                        return normalized
            
            return ""
        
        except Exception as e:
            logger.error(f"Error extracting shipping address: {e}", exc_info=True)
            return ""
