"""
Sneaker Politics Email Parser
Parses order confirmation emails from Sneaker Politics using BeautifulSoup

Email Format:
- From: store+2147974@t.shopifyemail.com (production)
- From: glenallagroupc@gmail.com (dev - forwarded emails)
- Subject: "Order confirmation" or similar
- Order Number: Extract from HTML (e.g., "536510")

HTML Structure:
- Products are listed in tables
- Each product has:
  - Product image: <img src="https://cdn.shopify.com/.../files/AURORA_HV0826-247_PHSLH000-2000_compact_cropped.jpg">
  - Product name: "Nike Killshot 2 - Black/White × 2"
  - Size: "9" or "9.5" in a span with color:#999
  - Quantity: Embedded in product name as "× 2" or "× 1"

Unique ID Extraction:
- Format: Extract from product image URL filename (e.g., "HV0826-247")
- Pattern: Look for pattern like "AURORA_HV0826-247_PHSLH000-2000_compact_cropped.jpg"
- Extract the middle part between underscores: "HV0826-247"
- Pattern: _([A-Z]{2}\d+-\d+)_
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


class SneakerOrderItem(BaseModel):
    unique_id: str = Field(..., description="Unique identifier for the product (e.g., HV0826-247)")
    size: str = Field(..., description="Size of the product")
    quantity: int = Field(..., description="Quantity of the product")
    product_name: Optional[str] = Field(None, description="Name of the product")
    
    def __repr__(self):
        if self.product_name and len(self.product_name) > 50:
            product_display = self.product_name[:50] + "..."
        else:
            product_display = self.product_name or "Unknown"
        return f"<SneakerOrderItem(unique_id={self.unique_id}, size={self.size}, qty={self.quantity}, product={product_display})>"


class SneakerOrderData(BaseModel):
    order_number: str = Field(..., description="The order number")
    items: List[SneakerOrderItem] = Field(..., description="List of items in the order")
    items_count: int = Field(0, description="Total number of items in the order")
    shipping_address: str = Field("", description="Normalized shipping address")

    def __init__(self, **data):
        super().__init__(**data)
        self.items_count = len(self.items)


class SneakerPoliticsEmailParser:
    # Email identification - Order Confirmation (Production)
    SNEAKER_FROM_EMAIL = "store+2147974@t.shopifyemail.com"
    SUBJECT_ORDER_PATTERN = r"order\s+confirmation|thank\s+you\s+for\s+your\s+purchase"
    
    # Email identification - Development (forwarded emails)
    DEV_SNEAKER_ORDER_FROM_EMAIL = "glenallagroupc@gmail.com"
    DEV_SUBJECT_ORDER_PATTERN = r"(?:Fwd:\s*)?(?:order\s+confirmation|order|sneaker\s+politics|sneaker)"

    def __init__(self):
        """Initialize the Sneaker Politics email parser."""
        self.settings = get_settings()
    
    @property
    def order_from_email(self) -> str:
        """Get the appropriate from email address based on environment."""
        if self.settings.is_development:
            return self.DEV_SNEAKER_ORDER_FROM_EMAIL
        return self.SNEAKER_FROM_EMAIL
    
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
            return "sneaker politics order"
        return "order confirmation"
    
    def is_sneaker_email(self, email_data: EmailData) -> bool:
        """
        Check if the email is from Sneaker Politics.
        
        Args:
            email_data: Email data to check
        
        Returns:
            True if the email is from Sneaker Politics, False otherwise
        """
        sender_lower = email_data.sender.lower()
        subject = email_data.subject.lower() if email_data.subject else ""
        
        # Check production email
        if self.SNEAKER_FROM_EMAIL.lower() in sender_lower:
            return True
        
        # Check dev email with subject pattern
        if self.DEV_SNEAKER_ORDER_FROM_EMAIL.lower() in sender_lower:
            if re.search(self.DEV_SUBJECT_ORDER_PATTERN, subject, re.IGNORECASE):
                return True
        
        return False
    
    def is_order_confirmation_email(self, email_data: EmailData) -> bool:
        """
        Check if the email is an order confirmation email from Sneaker Politics.
        
        Args:
            email_data: Email data to check
        
        Returns:
            True if the email is an order confirmation, False otherwise
        """
        if not self.is_sneaker_email(email_data):
            return False
        
        subject = email_data.subject.lower() if email_data.subject else ""
        
        # Check subject pattern
        if re.search(self.order_subject_pattern, subject, re.IGNORECASE):
            return True
        
        # Also check HTML content for order confirmation indicators
        if email_data.html_content:
            html_lower = email_data.html_content.lower()
            if "order confirmation" in html_lower or "order #" in html_lower or "sneaker politics" in html_lower:
                return True
        
        return False
    
    def _extract_unique_id_from_image_url(self, img_url: str) -> Optional[str]:
        """
        Extract unique ID from Sneaker Politics product image URL.
        
        Pattern: Look for pattern like "AURORA_HV0826-247_PHSLH000-2000_compact_cropped.jpg"
        Extract the middle part between underscores: "HV0826-247"
        Pattern: _([A-Z]{2}\d+-\d+)_
        
        Args:
            img_url: Image URL (may contain Gmail proxy URL)
        
        Returns:
            Unique ID string or None if not found
        """
        try:
            # Handle Gmail proxy URLs - extract actual URL after #
            if "#" in img_url:
                parts = img_url.split("#")
                if len(parts) > 1:
                    img_url = parts[-1]
            
            # Extract filename from URL
            filename = img_url.split("/")[-1].split("?")[0]  # Remove query params
            
            # Pattern 1: Look for _[A-Z]{2}\d+-\d+_ in filename
            # Examples: AURORA_HV0826-247_PHSLH000-2000_compact_cropped.jpg -> HV0826-247
            # Pattern: _([A-Z]{2}\d+-\d+)_
            pattern1 = r'_([A-Z]{2}\d+-\d+)_'
            match = re.search(pattern1, filename)
            
            if match:
                unique_id = match.group(1)
                logger.debug(f"Extracted unique ID '{unique_id}' from image URL (pattern 1): {filename}")
                return unique_id
            
            # Pattern 2: Look for -\d+-\d+- pattern (digits-dash-digits between dashes)
            # Examples: Sneaker-Politics-OC-CloudSurferFrost-131-113610-WB-1_compact_cropped.jpg -> 131-113610
            # Pattern: -(\d+-\d+)-
            pattern2 = r'-(\d+-\d+)-'
            match = re.search(pattern2, filename)
            
            if match:
                unique_id = match.group(1)
                logger.debug(f"Extracted unique ID '{unique_id}' from image URL (pattern 2): {filename}")
                return unique_id
            
            logger.warning(f"Could not extract unique ID from image URL: {filename}")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting unique ID from image URL: {e}", exc_info=True)
            return None
    
    def _extract_sneaker_product_details(self, product_row) -> Optional[SneakerOrderItem]:
        """
        Extract product details from a Sneaker Politics product row.
        
        Args:
            product_row: BeautifulSoup element containing product information
        
        Returns:
            SneakerOrderItem object or None
        """
        try:
            # Find product image
            img = product_row.find('img', src=re.compile(r'cdn\.shopify\.com'))
            
            if not img:
                logger.warning("Could not find product image")
                return None
            
            img_src = img.get('src', '')
            
            # Extract unique ID from image URL
            unique_id = self._extract_unique_id_from_image_url(img_src)
            
            if not unique_id:
                logger.warning(f"Could not extract unique ID from image: {img_src[:100]}")
                return None
            
            # Find product name - look for span with font-size:16px and font-weight:600
            # The style can be in any order: "font-size:16px;font-weight:600" or "font-weight:600;font-size:16px"
            product_name = None
            product_name_span = None
            
            # Try multiple patterns to find product name span
            spans = product_row.find_all('span')
            for span in spans:
                style = span.get('style', '')
                if 'font-size:16px' in style and 'font-weight:600' in style:
                    span_text = span.get_text(strip=True)
                    # Check if it contains the product name pattern (has × symbol)
                    if '×' in span_text:
                        product_name_span = span
                        break
            
            if product_name_span:
                raw_product_name = product_name_span.get_text(strip=True)
                # Extract product name and quantity
                # Format: "Nike Killshot 2 - Black/White × 2"
                # Remove quantity part (× 2 or × 1)
                product_name = re.sub(r'\s*×\s*\d+\s*$', '', raw_product_name).strip()
            
            # Find size - look for span with color:#999
            size = None
            size_spans = product_row.find_all('span', style=re.compile(r'color:#999'))
            for span in size_spans:
                span_text = span.get_text(strip=True)
                # Size is typically a number or number with decimal (e.g., "9", "9.5", "W8")
                # Exclude discount/spacer text
                if re.match(r'^[WM]?\d+(?:\.\d+)?$', span_text) and len(span_text) < 10:
                    size = span_text
                    break
            
            if not size:
                size = "Unknown"
            
            # Find quantity - extract from product name if available, otherwise default to 1
            quantity = 1
            if product_name_span:
                raw_product_name = product_name_span.get_text(strip=True)
                qty_match = re.search(r'×\s*(\d+)', raw_product_name)
                if qty_match:
                    quantity = int(qty_match.group(1))
            
            return SneakerOrderItem(
                unique_id=unique_id,
                size=size,
                quantity=quantity,
                product_name=product_name
            )
            
        except Exception as e:
            logger.error(f"Error extracting Sneaker Politics product details: {e}", exc_info=True)
            return None
    
    def _extract_order_number(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract order number from HTML.
        
        Args:
            soup: BeautifulSoup object
        
        Returns:
            Order number string or None
        """
        try:
            # Look for "Order #" followed by number
            # Format: <span style="font-size:16px"> Order #536510 </span>
            order_spans = soup.find_all('span', string=re.compile(r'Order\s+#\s*\d+', re.IGNORECASE))
            
            for span in order_spans:
                text = span.get_text()
                match = re.search(r'Order\s+#\s*(\d+)', text, re.IGNORECASE)
                if match:
                    order_number = match.group(1)
                    logger.debug(f"Extracted order number: {order_number}")
                    return order_number
            
            # Fallback: Look for text containing "Order #"
            order_text = soup.find(string=re.compile(r'Order\s+#', re.IGNORECASE))
            if order_text:
                match = re.search(r'Order\s+#\s*(\d+)', order_text, re.IGNORECASE)
                if match:
                    order_number = match.group(1)
                    logger.debug(f"Extracted order number (fallback): {order_number}")
                    return order_number
            
            logger.warning("Could not extract order number")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting order number: {e}", exc_info=True)
            return None
    
    def _extract_products(self, soup: BeautifulSoup) -> List[SneakerOrderItem]:
        """
        Extract products from HTML.
        
        Args:
            soup: BeautifulSoup object
        
        Returns:
            List of SneakerOrderItem objects
        """
        items = []
        
        try:
            # Find all product images from shopify
            product_images = soup.find_all('img', src=re.compile(r'cdn\.shopify\.com.*(?:files|products)'))
            
            logger.debug(f"Found {len(product_images)} Shopify images")
            
            seen_products = set()
            
            for img in product_images:
                # Exclude non-product images
                img_src = img.get('src', '')
                if any(exclude in img_src.lower() for exclude in ['logo', 'spacer', 'icon', 'arrow', 'facebook', 'twitter', 'instagram', 'discounttag']):
                    logger.debug(f"Skipping non-product image: {img_src[:100]}")
                    continue
                
                # Check if this is a product image (has product name nearby)
                parent = img.find_parent(['td', 'tr'])
                if not parent:
                    logger.debug(f"No parent found for image: {img_src[:100]}")
                    continue
                
                # Find the containing table row
                product_row = img.find_parent('tr')
                if not product_row:
                    product_row = parent.find_parent('tr')
                if not product_row:
                    product_row = parent
                
                # Check if this row contains product information
                # Look for product name span with × symbol or size span
                row_text = product_row.get_text()
                has_product_name = bool(re.search(r'×\s*\d+', row_text))
                has_size = bool(re.search(r'\b[WM]?\d+(?:\.\d+)?\b', row_text))
                
                if not (has_product_name or has_size):
                    logger.debug(f"No product indicators found in row text for image: {img_src[:100]}")
                    continue
                
                logger.debug(f"Processing product image: {img_src[:100]}")
                
                # Try to extract size from nearby spans for uniqueness
                size_key = "unknown"
                size_spans = product_row.find_all('span', style=re.compile(r'color:#999'))
                for span in size_spans:
                    span_text = span.get_text(strip=True)
                    if re.match(r'^[WM]?\d+(?:\.\d+)?$', span_text) and len(span_text) < 10:
                        size_key = span_text
                        break
                
                product_id = f"{img_src}_{size_key}"
                
                if product_id in seen_products:
                    continue
                seen_products.add(product_id)
                
                try:
                    # Extract product details from the product row
                    product_details = self._extract_sneaker_product_details(product_row)
                    
                    if product_details:
                        items.append(product_details)
                        logger.debug(f"Successfully extracted product: {product_details.product_name}, unique_id: {product_details.unique_id}")
                    else:
                        logger.debug(f"Failed to extract product details from row")
                
                except Exception as e:
                    logger.error(f"Error extracting product details: {e}", exc_info=True)
                    import traceback
                    logger.debug(traceback.format_exc())
                    continue
            
            logger.info(f"Extracted {len(items)} products from Sneaker Politics email")
            return items
            
        except Exception as e:
            logger.error(f"Error extracting Sneaker Politics products: {e}", exc_info=True)
            return []
    
    def _extract_shipping_address(self, soup: BeautifulSoup) -> str:
        """
        Extract shipping address from HTML.
        
        Args:
            soup: BeautifulSoup object
        
        Returns:
            Normalized shipping address string
        """
        try:
            # Look for "Shipping address" heading
            shipping_heading = soup.find('h4', string=re.compile(r'Shipping\s+address', re.IGNORECASE))
            
            if shipping_heading:
                # Find the parent table/row
                parent = shipping_heading.find_parent(['td', 'tr'])
                
                if parent:
                    # Look for paragraph containing address information
                    address_p = parent.find('p')
                    
                    if address_p:
                        # Get text and clean it up
                        address_text = address_p.get_text(separator=' ', strip=True)
                        
                        # Normalize the address
                        normalized = normalize_shipping_address(address_text)
                        logger.debug(f"Extracted shipping address: {normalized}")
                        return normalized
            
            logger.warning("Could not extract shipping address")
            return ""
            
        except Exception as e:
            logger.error(f"Error extracting shipping address: {e}", exc_info=True)
            return ""
    
    def parse_email(self, email_data: EmailData) -> Optional[SneakerOrderData]:
        """
        Parse a Sneaker Politics order confirmation email.
        
        Args:
            email_data: Email data to parse
        
        Returns:
            SneakerOrderData object or None if parsing fails
        """
        try:
            html_content = email_data.html_content
            
            if not html_content:
                logger.warning("No HTML content found in email")
                return None
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract order number
            order_number = self._extract_order_number(soup)
            if not order_number:
                logger.warning("Could not extract order number")
                return None
            
            # Extract products
            items = self._extract_products(soup)
            if not items:
                logger.warning("Could not extract any products")
                return None
            
            # Extract shipping address
            shipping_address = self._extract_shipping_address(soup)
            
            return SneakerOrderData(
                order_number=order_number,
                items=items,
                shipping_address=shipping_address
            )
            
        except Exception as e:
            logger.error(f"Error parsing Sneaker Politics order email: {e}", exc_info=True)
            return None
