"""
Anthropologie Email Parser
Parses order confirmation emails from Anthropologie using BeautifulSoup

Email Format:
- From: anthropologie@st.anthropologie.com (production)
- From: glenallagroupc@gmail.com (dev - forwarded emails)
- Subject: "We Like Your Style" or similar
- Order Number: Extract from HTML (e.g., "AN23865003")

HTML Structure:
- Products are listed in table rows with class containing "item-table-container"
- Each product has:
  - Image URL: https://images.urbndata.com/is/image/Anthropologie/90093667_029_a
  - Product name: <h4>UGG® Tasman Caspian Slippers</h4>
  - Style No.: <span>90093667</span>
  - Color: <span>Burnt Cedar</span>
  - Size: <span>8</span>
  - Quantity: In <td> with style="text-align:center"

Unique ID Extraction:
- Format: {product-slug}
- Product slug: Convert product name to lowercase, replace spaces/special chars with hyphens
- Example: "UGG® Tasman Caspian Slippers" -> "ugg-tasman-caspian-slippers"
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


class AnthropologieOrderItem(BaseModel):
    unique_id: str = Field(..., description="Unique identifier for the product (e.g., ugg-tasman-caspian-slippers)")
    size: str = Field(..., description="Size of the product")
    quantity: int = Field(..., description="Quantity of the product")
    product_name: Optional[str] = Field(None, description="Name of the product")
    style_number: Optional[str] = Field(None, description="Style number")
    color: Optional[str] = Field(None, description="Color name")
    
    def __repr__(self):
        if self.product_name and len(self.product_name) > 50:
            product_display = self.product_name[:50] + "..."
        else:
            product_display = self.product_name or "Unknown"
        return f"<AnthropologieOrderItem(unique_id={self.unique_id}, size={self.size}, qty={self.quantity}, product={product_display})>"


class AnthropologieOrderData(BaseModel):
    order_number: str = Field(..., description="The order number")
    items: List[AnthropologieOrderItem] = Field(..., description="List of items in the order")
    items_count: int = Field(0, description="Total number of items in the order")
    shipping_address: str = Field("", description="Normalized shipping address")

    def __init__(self, **data):
        super().__init__(**data)
        self.items_count = len(self.items)


class AnthropologieEmailParser:
    # Email identification - Order Confirmation (Production)
    ANTHROPOLOGIE_FROM_EMAIL = "anthropologie@st.anthropologie.com"
    SUBJECT_ORDER_PATTERN = r"we\s+like\s+your\s+style"
    
    # Email identification - Development (forwarded emails)
    DEV_ANTHROPOLOGIE_ORDER_FROM_EMAIL = "glenallagroupc@gmail.com"
    DEV_SUBJECT_ORDER_PATTERN = r"(?:Fwd:\s*)?(?:we\s+like\s+your\s+style|thank\s+you\s+for\s+your\s+order)"

    def __init__(self):
        """Initialize the Anthropologie email parser."""
        self.settings = get_settings()
    
    @property
    def order_from_email(self) -> str:
        """Get the appropriate from email address based on environment."""
        if self.settings.is_development:
            return self.DEV_ANTHROPOLOGIE_ORDER_FROM_EMAIL
        return self.ANTHROPOLOGIE_FROM_EMAIL
    
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
            return "We Like Your Style"
        return "We Like Your Style"

    def is_anthropologie_email(self, email_data: EmailData) -> bool:
        """Check if email is from Anthropologie"""
        sender_lower = email_data.sender.lower()
        
        # In development, check for forwarded emails from dev email address
        if self.settings.is_development:
            if self.DEV_ANTHROPOLOGIE_ORDER_FROM_EMAIL.lower() in sender_lower:
                return True
        
        # In production, check for Anthropologie email
        return self.ANTHROPOLOGIE_FROM_EMAIL.lower() in sender_lower

    def is_order_confirmation_email(self, email_data: EmailData) -> bool:
        """Check if email is an order confirmation"""
        subject_lower = email_data.subject.lower()
        pattern = self.order_subject_pattern
        
        # Use regex matching for subject pattern
        if re.search(pattern, subject_lower, re.IGNORECASE):
            return True
        
        # For forwarded emails in dev mode, also check HTML content for Anthropologie confirmation indicators
        if self.settings.is_development and email_data.html_content:
            html_lower = email_data.html_content.lower()
            # Check for "We Like Your Style" heading or order confirmation indicators
            has_confirmation_text = (
                'we like your style' in html_lower or
                'order number:' in html_lower or
                ('anthropologie' in html_lower and 'order' in html_lower)
            )
            if has_confirmation_text:
                return True
        
        return False

    def parse_email(self, email_data: EmailData) -> Optional[AnthropologieOrderData]:
        """
        Parse Anthropologie order confirmation email.
        
        Args:
            email_data: EmailData object containing email information
        
        Returns:
            AnthropologieOrderData object or None if parsing fails
        """
        try:
            html_content = email_data.html_content
            
            if not html_content:
                logger.error("No HTML content in Anthropologie email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extract order number from HTML
            order_number = self._extract_order_number(soup)
            if not order_number:
                logger.error("Failed to extract order number from Anthropologie email")
                return None
            
            logger.info(f"Extracted Anthropologie order number: {order_number}")
            
            # Extract items using BeautifulSoup
            items = self._extract_items(soup)
            
            if not items:
                logger.error("Failed to extract any items from Anthropologie email")
                return None
            
            logger.info(f"Successfully extracted {len(items)} items from Anthropologie order {order_number}")
            for item in items:
                logger.debug(f"  - {item}")
            
            # Extract shipping address
            shipping_address = self._extract_shipping_address(soup)
            if shipping_address:
                logger.info(f"Extracted shipping address: {shipping_address}")
            
            return AnthropologieOrderData(order_number=order_number, items=items, shipping_address=shipping_address)
        
        except Exception as e:
            logger.error(f"Error parsing Anthropologie email: {e}", exc_info=True)
            return None

    def _extract_order_number(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract order number from Anthropologie email HTML.
        
        HTML format: <h4> Order Number: <a href="...">AN23865003</a></h4>
        Extract: AN23865003
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            Order number or None
        """
        try:
            # Look for "Order Number:" text
            order_number_pattern = re.compile(r'Order\s+Number:', re.IGNORECASE)
            order_number_header = soup.find(string=order_number_pattern)
            
            if order_number_header:
                # Get the parent h4 element and find the link
                h4_element = order_number_header.find_parent('h4')
                if h4_element:
                    link = h4_element.find('a')
                    if link:
                        order_number = link.get_text(strip=True)
                        if order_number:
                            logger.debug(f"Found Anthropologie order number: {order_number}")
                            return order_number
            
            # Fallback: search for pattern in text
            text_content = soup.get_text()
            match = re.search(r'Order\s+Number:\s*([A-Z0-9]+)', text_content, re.IGNORECASE)
            if match:
                order_number = match.group(1)
                logger.debug(f"Found Anthropologie order number (fallback): {order_number}")
                return order_number
            
            logger.warning("Order number not found in Anthropologie email")
            return None
        
        except Exception as e:
            logger.error(f"Error extracting Anthropologie order number: {e}")
            return None

    def _extract_items(self, soup: BeautifulSoup) -> List[AnthropologieOrderItem]:
        """
        Extract order items from Anthropologie email.
        
        Anthropologie email structure:
        - Products are in table rows with class containing "item-table-container"
        - Each product row contains:
          - Image with URL: https://images.urbndata.com/is/image/Anthropologie/90093667_029_a
          - Product name in <h4> tag
          - Style No. in <span>
          - Color in <span>
          - Size in <span>
          - Quantity in <td> with style="text-align:center"
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            List of AnthropologieOrderItem objects
        """
        items = []
        
        try:
            # Find all product containers - look for tables with item-table-container class
            product_containers = soup.find_all('td', class_=lambda x: x and 'item-table-container' in str(x))
            
            for container in product_containers:
                try:
                    product_details = self._extract_anthropologie_product_details(container)
                    
                    if product_details:
                        items.append(product_details)
                
                except Exception as e:
                    logger.error(f"Error processing Anthropologie product container: {e}")
                    continue
            
            # Log items with ID, size, and quantity
            if items:
                items_summary = [f"(ID: {item.unique_id}, Size: {item.size}, Qty: {item.quantity})" for item in items]
                logger.info(f"[Anthropologie] Extracted {len(items)} items: {', '.join(items_summary)}")
            
            return items
        
        except Exception as e:
            logger.error(f"Error extracting Anthropologie items: {e}", exc_info=True)
            return []

    def _extract_anthropologie_product_details(self, container) -> Optional[AnthropologieOrderItem]:
        """
        Extract product details from an Anthropologie product container.
        
        Returns:
            AnthropologieOrderItem object or None
        """
        try:
            details = {}
            container_text = container.get_text()
            
            # Extract product name - look for <h4> tag
            product_name_tag = container.find('h4')
            if product_name_tag:
                product_name = product_name_tag.get_text(strip=True)
                details['product_name'] = product_name
                logger.debug(f"Found product name: {product_name}")
            else:
                logger.warning("Product name not found in Anthropologie container")
                return None
            
            # Extract style number - look for "Style No." followed by <span>
            style_number_tag = container.find(string=re.compile(r'Style\s+No\.', re.IGNORECASE))
            if style_number_tag:
                style_span = style_number_tag.find_next('span')
                if style_span:
                    style_number = style_span.get_text(strip=True)
                    details['style_number'] = style_number
                    logger.debug(f"Found style number: {style_number}")
            
            # Extract color - look for "Color:" followed by <span>
            color_tag = container.find(string=re.compile(r'Color:', re.IGNORECASE))
            if color_tag:
                color_span = color_tag.find_next('span')
                if color_span:
                    color = color_span.get_text(strip=True)
                    details['color'] = color
                    logger.debug(f"Found color: {color}")
            
            # Extract size - look for "Size:" followed by <span>
            size_tag = container.find(string=re.compile(r'Size:', re.IGNORECASE))
            if size_tag:
                size_span = size_tag.find_next('span')
                if size_span:
                    size = size_span.get_text(strip=True)
                    details['size'] = size
                    logger.debug(f"Found size: {size}")
            
            if not details.get('size'):
                # Try regex fallback - look for "Size:" followed by text in span
                size_match = re.search(r'Size:\s*<span>([^<]+)</span>', str(container), re.IGNORECASE)
                if size_match:
                    size = size_match.group(1).strip()
                    details['size'] = size
                    logger.debug(f"Found size (regex span): {size}")
            
            if not details.get('size'):
                # Try regex fallback - look for "Size:" followed by any text
                size_match = re.search(r'Size:\s*([^\n<]+)', container_text, re.IGNORECASE)
                if size_match:
                    size = size_match.group(1).strip()
                    # Clean up any HTML entities or extra whitespace
                    size = re.sub(r'<[^>]+>', '', size).strip()
                    details['size'] = size
                    logger.debug(f"Found size (regex fallback): {size}")
            
            if not details.get('size'):
                logger.warning("Size not found in Anthropologie container")
                return None
            
            # Extract quantity - look for <td> with style="text-align:center" containing a number
            quantity_td = container.find('td', style=re.compile(r'text-align:\s*center', re.IGNORECASE))
            
            if quantity_td:
                quantity_text = quantity_td.get_text(strip=True)
                # Try to extract number
                qty_match = re.search(r'(\d+)', quantity_text)
                if qty_match:
                    quantity = int(qty_match.group(1))
                    details['quantity'] = quantity
                    logger.debug(f"Found quantity: {quantity}")
                else:
                    # Default to 1 if not found
                    details['quantity'] = 1
                    logger.debug("Quantity not found, defaulting to 1")
            else:
                # Also check for "Qty:" label pattern
                qty_tag = container.find(string=re.compile(r'Qty:', re.IGNORECASE))
                if qty_tag:
                    # Get the text after "Qty:"
                    qty_text = qty_tag.find_next(string=True)
                    if qty_text:
                        qty_match = re.search(r'(\d+)', qty_text)
                        if qty_match:
                            quantity = int(qty_match.group(1))
                            details['quantity'] = quantity
                            logger.debug(f"Found quantity (Qty label): {quantity}")
                        else:
                            details['quantity'] = 1
                    else:
                        details['quantity'] = 1
                else:
                    # Default to 1 if quantity td not found
                    details['quantity'] = 1
                    logger.debug("Quantity td not found, defaulting to 1")
            
            # Generate unique ID from product name: convert to slug
            # Example: "UGG® Tasman Caspian Slippers" -> "ugg-tasman-caspian-slippers"
            product_slug = self._product_name_to_slug(product_name)
            unique_id = product_slug
            details['unique_id'] = unique_id
            logger.debug(f"Generated unique ID: {unique_id}")
            
            # Return only if we have the essential fields
            if details.get('unique_id') and details.get('size'):
                return AnthropologieOrderItem(
                    unique_id=details['unique_id'],
                    size=details['size'],
                    quantity=details.get('quantity', 1),
                    product_name=details.get('product_name'),
                    style_number=details.get('style_number'),
                    color=details.get('color')
                )
            
            logger.warning(f"Missing essential fields: {details}")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting Anthropologie product details: {e}", exc_info=True)
            return None
    
    def _product_name_to_slug(self, product_name: str) -> str:
        """
        Convert product name to URL-friendly slug.
        
        Example: "UGG® Tasman Caspian Slippers" -> "ugg-tasman-caspian-slippers"
        
        Args:
            product_name: Product name string
        
        Returns:
            Slug string
        """
        # Convert to lowercase
        slug = product_name.lower()
        
        # Replace apostrophes and other special characters with spaces
        slug = re.sub(r"[''`®©™]", '', slug)
        
        # Replace non-alphanumeric characters (except hyphens) with hyphens
        slug = re.sub(r'[^a-z0-9-]+', '-', slug)
        
        # Remove leading/trailing hyphens and collapse multiple hyphens
        slug = re.sub(r'-+', '-', slug).strip('-')
        
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
            # Look for "Shipping Address" header
            shipping_header = soup.find('h3', string=re.compile(r'Shipping\s+Address', re.IGNORECASE))
            
            if shipping_header:
                # Find the address text in the parent table
                address_table = shipping_header.find_parent('table')
                if address_table:
                    # Find the td with class containing "address"
                    address_element = address_table.find('td', class_=lambda x: x and 'address' in str(x))
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
