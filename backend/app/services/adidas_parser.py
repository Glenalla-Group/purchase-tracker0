"""
Adidas Email Parser
Parses order confirmation emails from Adidas using BeautifulSoup

Email Format:
- From: adidas@us-info.adidas.com (production)
- From: glenallagroupc@gmail.com (dev - forwarded emails)
- Subject: "Thanks for your order" or similar
- Order Number: Extract from HTML (e.g., "AD947010173")

HTML Structure:
- Products are listed in tables
- Each product has:
  - Product image: <img src="https://assets.adidas.com/images/.../Samba_OG_Shoes_JR0035_00_plp_standard.jpg">
  - Product name: "Samba Og Shoes"
  - Size/Quantity: "Size: M 8 / W 9 / Quantity: 4"
  - Color: "Color: Silver Metallic / Cloud White / Core White"

Unique ID Extraction:
- Format: Extract from product image URL (e.g., "JR0035", "JR1402")
- Pattern: Look for pattern like "_JR0035_" or "_JR1402_" in image filename
- The unique ID appears between underscores before "_00_plp_standard.jpg"
- Example: "Samba_OG_Shoes_JR0035_00_plp_standard.jpg" -> "JR0035"
- Example: "Samba_Jane_Shoes_JR1402_00_plp_standard.jpg" -> "JR1402"
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


class AdidasOrderItem(BaseModel):
    unique_id: str = Field(..., description="Unique identifier for the product (e.g., JR0035)")
    size: str = Field(..., description="Size of the product")
    quantity: int = Field(..., description="Quantity of the product")
    product_name: Optional[str] = Field(None, description="Name of the product")
    
    def __repr__(self):
        if self.product_name and len(self.product_name) > 50:
            product_display = self.product_name[:50] + "..."
        else:
            product_display = self.product_name or "Unknown"
        return f"<AdidasOrderItem(unique_id={self.unique_id}, size={self.size}, qty={self.quantity}, product={product_display})>"


class AdidasOrderData(BaseModel):
    order_number: str = Field(..., description="The order number")
    items: List[AdidasOrderItem] = Field(..., description="List of items in the order")
    items_count: int = Field(0, description="Total number of items in the order")
    shipping_address: str = Field("", description="Normalized shipping address")

    def __init__(self, **data):
        super().__init__(**data)
        self.items_count = len(self.items)


class AdidasEmailParser:
    # Email identification - Order Confirmation (Production)
    ADIDAS_FROM_EMAIL = "adidas@us-info.adidas.com"
    SUBJECT_ORDER_PATTERN = r"thanks?\s+for\s+your\s+order|order\s+confirmation"
    
    # Email identification - Development (forwarded emails)
    DEV_ADIDAS_ORDER_FROM_EMAIL = "glenallagroupc@gmail.com"
    DEV_SUBJECT_ORDER_PATTERN = r"(?:Fwd:\s*)?(?:thanks?\s+for\s+your\s+order|order|adidas)"

    def __init__(self):
        """Initialize the Adidas email parser."""
        self.settings = get_settings()
    
    @property
    def order_from_email(self) -> str:
        """Get the appropriate from email address based on environment."""
        if self.settings.is_development:
            return self.DEV_ADIDAS_ORDER_FROM_EMAIL
        return self.ADIDAS_FROM_EMAIL
    
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
            return "adidas order"
        return "thanks for your order"
    
    def is_adidas_email(self, email_data: EmailData) -> bool:
        """
        Check if the email is from Adidas.
        
        Args:
            email_data: Email data to check
        
        Returns:
            True if the email is from Adidas, False otherwise
        """
        sender_lower = email_data.sender.lower()
        subject = email_data.subject.lower() if email_data.subject else ""
        
        # Check production email
        if self.ADIDAS_FROM_EMAIL.lower() in sender_lower:
            return True
        
        # Check dev email with subject pattern
        if self.DEV_ADIDAS_ORDER_FROM_EMAIL.lower() in sender_lower:
            if re.search(self.DEV_SUBJECT_ORDER_PATTERN, subject, re.IGNORECASE):
                return True
        
        return False
    
    def is_order_confirmation_email(self, email_data: EmailData) -> bool:
        """
        Check if the email is an order confirmation email from Adidas.
        
        Args:
            email_data: Email data to check
        
        Returns:
            True if the email is an order confirmation, False otherwise
        """
        if not self.is_adidas_email(email_data):
            return False
        
        subject = email_data.subject.lower() if email_data.subject else ""
        
        # Check subject pattern
        if re.search(self.order_subject_pattern, subject, re.IGNORECASE):
            return True
        
        # Also check HTML content for order confirmation indicators
        if email_data.html_content:
            html_lower = email_data.html_content.lower()
            if "order number" in html_lower or "thanks for your order" in html_lower:
                return True
        
        return False
    
    def _extract_unique_id_from_image_url(self, img_url: str) -> Optional[str]:
        """
        Extract unique ID from Adidas product image URL.
        
        Pattern: Look for pattern like "_JR0035_" or "_JR1402_" in filename
        The unique ID appears between underscores before "_00_plp_standard.jpg"
        
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
            filename = img_url.split("/")[-1]
            
            # Pattern: Look for _[A-Z0-9]+_00_plp_standard.jpg
            # Examples: Samba_OG_Shoes_JR0035_00_plp_standard.jpg -> JR0035
            #           Samba_Jane_Shoes_JR1402_00_plp_standard.jpg -> JR1402
            pattern = r'_([A-Z0-9]+)_00_plp_standard'
            match = re.search(pattern, filename)
            
            if match:
                unique_id = match.group(1)
                logger.debug(f"Extracted unique ID '{unique_id}' from image URL: {filename}")
                return unique_id
            
            # Fallback: Try to find any pattern like _[A-Z][A-Z]\d+_ before _00_
            pattern_fallback = r'_([A-Z][A-Z]\d+)_00_'
            match_fallback = re.search(pattern_fallback, filename)
            if match_fallback:
                unique_id = match_fallback.group(1)
                logger.debug(f"Extracted unique ID '{unique_id}' from image URL (fallback): {filename}")
                return unique_id
            
            logger.warning(f"Could not extract unique ID from image URL: {filename}")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting unique ID from image URL: {e}", exc_info=True)
            return None
    
    def _extract_adidas_product_details(self, product_section) -> Optional[AdidasOrderItem]:
        """
        Extract product details from an Adidas product section.
        
        Args:
            product_section: BeautifulSoup element containing product information
        
        Returns:
            AdidasOrderItem object or None
        """
        try:
            # Find product image
            img = product_section.find('img', {'name': re.compile(r'product-item-image'), 'id': re.compile(r'product-item-image')})
            if not img:
                img = product_section.find('img', src=re.compile(r'assets\.adidas\.com'))
            
            if not img:
                logger.warning("Could not find product image")
                return None
            
            img_src = img.get('src', '')
            unique_id = self._extract_unique_id_from_image_url(img_src)
            
            if not unique_id:
                logger.warning(f"Could not extract unique ID from image: {img_src}")
                return None
            
            # Find product name - look for td with product name text
            product_name = None
            name_elem = product_section.find('td', style=re.compile(r'font-weight:700'))
            if name_elem:
                product_name = name_elem.get_text(strip=True)
            
            # Find size and quantity - look for td with id="product-size-text"
            size_text = None
            quantity = 1
            
            size_elem = product_section.find('td', {'id': re.compile(r'product-size-text'), 'name': re.compile(r'product-size-text')})
            if size_elem:
                size_text = size_elem.get_text(strip=True)
            else:
                # Fallback: search for text containing "Size:" and "Quantity:"
                size_elem = product_section.find(string=re.compile(r'Size:'))
                if size_elem:
                    size_text = size_elem.parent.get_text(strip=True) if size_elem.parent else None
            
            if size_text:
                # Parse "Size: M 8 / W 9 / Quantity: 4"
                # Extract size part (everything before "Quantity:")
                size_match = re.search(r'Size:\s*(.+?)(?:\s*/\s*Quantity:|$)', size_text, re.IGNORECASE)
                if size_match:
                    size = size_match.group(1).strip()
                else:
                    # Fallback: just take everything before "Quantity:"
                    size = size_text.split('Quantity:')[0].replace('Size:', '').strip()
                
                # Extract quantity
                qty_match = re.search(r'Quantity:\s*(\d+)', size_text, re.IGNORECASE)
                if qty_match:
                    quantity = int(qty_match.group(1))
            else:
                size = "Unknown"
            
            if not unique_id:
                logger.warning("Could not extract unique ID")
                return None
            
            return AdidasOrderItem(
                unique_id=unique_id,
                size=size,
                quantity=quantity,
                product_name=product_name
            )
            
        except Exception as e:
            logger.error(f"Error extracting Adidas product details: {e}", exc_info=True)
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
            # Look for link with id="body-order-number-link"
            order_link = soup.find('a', {'id': re.compile(r'body-order-number-link'), 'name': re.compile(r'body-order-number-link')})
            if order_link:
                order_number = order_link.get_text(strip=True)
                if order_number:
                    logger.debug(f"Extracted order number from link: {order_number}")
                    return order_number
            
            # Fallback: Look for text containing "Order number" followed by order number
            order_text = soup.find(string=re.compile(r'Order\s+number', re.IGNORECASE))
            if order_text:
                # Find the next sibling or parent that contains the order number
                parent = order_text.parent
                if parent:
                    # Look for link or text in the same row/table
                    order_elem = parent.find_next('a') or parent.find_next(string=re.compile(r'[A-Z]{2}\d+'))
                    if order_elem:
                        if isinstance(order_elem, str):
                            order_number = order_elem.strip()
                        else:
                            order_number = order_elem.get_text(strip=True)
                        if order_number and re.match(r'^[A-Z]{2}\d+$', order_number):
                            logger.debug(f"Extracted order number from text: {order_number}")
                            return order_number
            
            logger.warning("Could not extract order number")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting order number: {e}", exc_info=True)
            return None
    
    def _extract_products(self, soup: BeautifulSoup) -> List[AdidasOrderItem]:
        """
        Extract products from HTML.
        
        Args:
            soup: BeautifulSoup object
        
        Returns:
            List of AdidasOrderItem objects
        """
        items = []
        
        try:
            # Find all product images from adidas.com
            product_images = soup.find_all('img', src=re.compile(r'assets\.adidas\.com.*images'))
            
            seen_products = set()
            
            for img in product_images:
                # Exclude non-product images
                img_src = img.get('src', '')
                if any(exclude in img_src.lower() for exclude in ['logo', 'spacer', 'icon', 'arrow', 'nps', 'vot']):
                    continue
                
                # Check if this is a product image (has product-item-image in name/id)
                img_name = img.get('name', '')
                img_id = img.get('id', '')
                if 'product-item-image' not in img_name.lower() and 'product-item-image' not in img_id.lower():
                    # Check if it's in a product section by looking for size/quantity text nearby
                    parent = img.find_parent(['table', 'td', 'tr'])
                    if parent:
                        parent_text = parent.get_text()
                        if 'Size:' not in parent_text and 'Quantity:' not in parent_text:
                            continue
                
                # Find the parent table/row that contains this product
                # Walk up to find the table row that contains both image and product details
                current = img
                product_row = None
                
                # Look for the table row that contains both image and product-size-text
                for _ in range(10):  # Limit depth
                    parent_tr = current.find_parent('tr')
                    if not parent_tr:
                        break
                    
                    # Check if this row contains product-size-text
                    if parent_tr.find('td', {'id': re.compile(r'product-size-text')}):
                        product_row = parent_tr
                        break
                    
                    current = parent_tr
                
                if not product_row:
                    # Fallback: use the table containing the image
                    product_row = img.find_parent('table')
                
                if not product_row:
                    continue
                
                # Create a unique identifier for this product
                img_src = img.get('src', '')
                product_id = f"{img_src}"
                
                if product_id in seen_products:
                    continue
                seen_products.add(product_id)
                
                try:
                    product_details = self._extract_adidas_product_details(product_row)
                    
                    if product_details:
                        items.append(product_details)
                
                except Exception as e:
                    logger.error(f"Error extracting product details: {e}", exc_info=True)
                    continue
            
            logger.info(f"Extracted {len(items)} products from Adidas email")
            return items
            
        except Exception as e:
            logger.error(f"Error extracting Adidas products: {e}", exc_info=True)
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
            shipping_heading = soup.find(string=re.compile(r'Shipping\s+address', re.IGNORECASE))
            
            if shipping_heading:
                # Find the parent table/row
                parent = shipping_heading.find_parent(['td', 'tr', 'table'])
                
                if parent:
                    # Look for spans or text containing address information
                    # Address appears in spans after the heading
                    address_spans = parent.find_all('span', style=re.compile(r'font-family:AdihausDIN'))
                    
                    address_parts = []
                    for span in address_spans:
                        text = span.get_text(strip=True)
                        if text and len(text) > 5:  # Filter out very short text
                            address_parts.append(text)
                    
                    if address_parts:
                        # Join address parts
                        address = " ".join(address_parts)
                        
                        # Normalize the address
                        normalized = normalize_shipping_address(address)
                        logger.debug(f"Extracted shipping address: {normalized}")
                        return normalized
            
            logger.warning("Could not extract shipping address")
            return ""
            
        except Exception as e:
            logger.error(f"Error extracting shipping address: {e}", exc_info=True)
            return ""
    
    def parse_email(self, email_data: EmailData) -> Optional[AdidasOrderData]:
        """
        Parse an Adidas order confirmation email.
        
        Args:
            email_data: Email data to parse
        
        Returns:
            AdidasOrderData object or None if parsing fails
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
            
            return AdidasOrderData(
                order_number=order_number,
                items=items,
                shipping_address=shipping_address
            )
            
        except Exception as e:
            logger.error(f"Error parsing Adidas order email: {e}", exc_info=True)
            return None
