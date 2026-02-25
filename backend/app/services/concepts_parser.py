"""
CNCPTS (Concepts) Email Parser
Parses order confirmation emails from CNCPTS using BeautifulSoup

Email Format:
- From: cs@cncpts.com (production)
- From: glenallagroupc@gmail.com (dev - forwarded emails)
- Subject: "Order confirmation" or similar
- Order Number: Extract from HTML (e.g., "342893")

HTML Structure:
- Products are listed in tables
- Each product has:
  - Product image: <img src="https://cdn.shopify.com/.../products/Nike_WDunkLowWhitePhotonDust_DD1503-103_01.jpg">
  - Product name: "On Cloud 5 (White)" or "Nike Womens Dunk Low (White/Photon Dust)"
  - Size: "10.5" or "10" in a span
  - Quantity: "x 1" or "x 2"

Unique ID Extraction:
- Format: Extract from product image URL (e.g., "dd1503-103")
- Pattern: Look for pattern like "_DD1503-103_" or "_dd1503-103_" in image filename
- The unique ID appears between underscores before "_01.jpg" or similar
- Convert to lowercase
- Example: "Nike_WDunkLowWhitePhotonDust_DD1503-103_01.jpg" -> "dd1503-103"
- Example: "Nike_WDunkLowWhitePhotonDust_dd1503-103_01.jpg" -> "dd1503-103"
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


class ConceptsOrderItem(BaseModel):
    unique_id: str = Field(..., description="Unique identifier for the product (e.g., dd1503-103)")
    size: str = Field(..., description="Size of the product")
    quantity: int = Field(..., description="Quantity of the product")
    product_name: Optional[str] = Field(None, description="Name of the product")
    
    def __repr__(self):
        if self.product_name and len(self.product_name) > 50:
            product_display = self.product_name[:50] + "..."
        else:
            product_display = self.product_name or "Unknown"
        return f"<ConceptsOrderItem(unique_id={self.unique_id}, size={self.size}, qty={self.quantity}, product={product_display})>"


class ConceptsOrderData(BaseModel):
    order_number: str = Field(..., description="The order number")
    items: List[ConceptsOrderItem] = Field(..., description="List of items in the order")
    items_count: int = Field(0, description="Total number of items in the order")
    shipping_address: str = Field("", description="Normalized shipping address")

    def __init__(self, **data):
        super().__init__(**data)
        self.items_count = len(self.items)


class ConceptsEmailParser:
    # Email identification - Order Confirmation (Production)
    CONCEPTS_FROM_EMAIL = "cs@cncpts.com"
    SUBJECT_ORDER_PATTERN = r"order\s+confirmation"
    
    # Email identification - Development (forwarded emails)
    DEV_CONCEPTS_ORDER_FROM_EMAIL = "glenallagroupc@gmail.com"
    DEV_SUBJECT_ORDER_PATTERN = r"(?:Fwd:\s*)?(?:order\s+confirmation|order|concepts|cncpts)"

    def __init__(self):
        """Initialize the CNCPTS email parser."""
        self.settings = get_settings()
    
    @property
    def order_from_email(self) -> str:
        """Get the appropriate from email address based on environment."""
        if self.settings.is_development:
            return self.DEV_CONCEPTS_ORDER_FROM_EMAIL
        return self.CONCEPTS_FROM_EMAIL
    
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
            return "concepts order"
        return "order confirmation"
    
    def is_concepts_email(self, email_data: EmailData) -> bool:
        """
        Check if the email is from CNCPTS.
        
        Args:
            email_data: Email data to check
        
        Returns:
            True if the email is from CNCPTS, False otherwise
        """
        sender_lower = email_data.sender.lower()
        subject = email_data.subject.lower() if email_data.subject else ""
        
        # Check production email
        if self.CONCEPTS_FROM_EMAIL.lower() in sender_lower:
            return True
        
        # Check dev email with subject pattern
        if self.DEV_CONCEPTS_ORDER_FROM_EMAIL.lower() in sender_lower:
            if re.search(self.DEV_SUBJECT_ORDER_PATTERN, subject, re.IGNORECASE):
                return True
        
        return False
    
    def is_order_confirmation_email(self, email_data: EmailData) -> bool:
        """
        Check if the email is an order confirmation email from CNCPTS.
        
        Args:
            email_data: Email data to check
        
        Returns:
            True if the email is an order confirmation, False otherwise
        """
        if not self.is_concepts_email(email_data):
            return False
        
        subject = email_data.subject.lower() if email_data.subject else ""
        
        # Check subject pattern
        if re.search(self.order_subject_pattern, subject, re.IGNORECASE):
            return True
        
        # Also check HTML content for order confirmation indicators
        if email_data.html_content:
            html_lower = email_data.html_content.lower()
            if "order confirmation" in html_lower or "order no" in html_lower:
                return True
        
        return False
    
    def _extract_unique_id_from_image_url(self, img_url: str, product_link_url: Optional[str] = None) -> Optional[str]:
        """
        Extract unique ID from CNCPTS product image URL or product link URL.
        
        Patterns:
        1. Look for pattern like "_DD1503-103_" or "_dd1503-103_" in filename
           The unique ID appears between underscores before "_01.jpg" or similar
           Example: Nike_WDunkLowWhitePhotonDust_DD1503-103_01.jpg -> dd1503-103
        2. For numeric filenames like "7630440669579-1.jpg", extract the numeric part
           Example: 7630440669579-1.jpg -> 7630440669579
        3. Fallback to product link URL if available
        
        Args:
            img_url: Image URL (may contain Gmail proxy URL)
            product_link_url: Optional product link URL to check as fallback
        
        Returns:
            Unique ID string (lowercase for alphanumeric, as-is for numeric) or None if not found
        """
        try:
            # Handle Gmail proxy URLs - extract actual URL after #
            if "#" in img_url:
                parts = img_url.split("#")
                if len(parts) > 1:
                    img_url = parts[-1]
            
            # Extract filename from URL
            filename = img_url.split("/")[-1].split("?")[0]  # Remove query params
            
            # Pattern 1: Look for _[A-Z]{2}\d+-\d+_ before _01.jpg or similar
            # Examples: Nike_WDunkLowWhitePhotonDust_DD1503-103_01.jpg -> dd1503-103
            # Pattern: _([A-Z]{2}\d+-\d+)_ or _([a-z]{2}\d+-\d+)_
            pattern = r'_([A-Za-z]{2}\d+-\d+)_'
            match = re.search(pattern, filename)
            
            if match:
                unique_id = match.group(1).lower()
                logger.debug(f"Extracted unique ID '{unique_id}' from image URL: {filename}")
                return unique_id
            
            # Fallback 1: Try to find any pattern with letters, digits, dash, digits
            pattern_fallback = r'_([A-Za-z]{2,}\d+-\d+)_'
            match_fallback = re.search(pattern_fallback, filename)
            if match_fallback:
                unique_id = match_fallback.group(1).lower()
                logger.debug(f"Extracted unique ID '{unique_id}' from image URL (fallback): {filename}")
                return unique_id
            
            # Fallback 2: For numeric filenames like "7630440669579-1.jpg"
            # Extract the numeric part before the dash and number suffix
            # Pattern: (\d+)-(\d+)\.jpg or (\d+)-(\d+)\.(jpg|png|webp)
            numeric_pattern = r'^(\d+)-(\d+)\.(jpg|png|webp|jpeg)$'
            numeric_match = re.search(numeric_pattern, filename, re.IGNORECASE)
            if numeric_match:
                unique_id = numeric_match.group(1)  # First numeric part
                logger.debug(f"Extracted unique ID '{unique_id}' from numeric filename: {filename}")
                return unique_id
            
            # Try product link URL as fallback
            if product_link_url:
                # Extract from URL path like /products/nike-w-dunk-low-dd1503-103-white-photon-dust-white
                # Pattern: /products/.*-([a-z]{2}\d+-\d+)-
                link_pattern = r'/products/.*-([a-z]{2}\d+-\d+)(?:-|$)'
                link_match = re.search(link_pattern, product_link_url.lower())
                if link_match:
                    unique_id = link_match.group(1)
                    logger.debug(f"Extracted unique ID '{unique_id}' from product link URL: {product_link_url}")
                    return unique_id
                
                # Also try to decode URL-encoded tracking links - they might contain the product URL
                # Check if URL contains encoded product path
                try:
                    from urllib.parse import unquote
                    decoded_url = unquote(product_link_url)
                    # Look for product URL pattern in decoded URL
                    decoded_match = re.search(r'/products/[^/?]+-([a-z]{2}\d+-\d+)(?:-|/|\?|$)', decoded_url.lower())
                    if decoded_match:
                        unique_id = decoded_match.group(1)
                        logger.debug(f"Extracted unique ID '{unique_id}' from decoded product link URL")
                        return unique_id
                except Exception:
                    pass
            
            logger.warning(f"Could not extract unique ID from image URL: {filename}")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting unique ID from image URL: {e}", exc_info=True)
            return None
    
    def _extract_concepts_product_details(self, product_row) -> Optional[ConceptsOrderItem]:
        """
        Extract product details from a CNCPTS product row.
        
        Args:
            product_row: BeautifulSoup element containing product information
        
        Returns:
            ConceptsOrderItem object or None
        """
        try:
            # Find product image
            img = product_row.find('img', src=re.compile(r'cdn\.shopify\.com'))
            
            if not img:
                logger.warning("Could not find product image")
                return None
            
            img_src = img.get('src', '')
            
            # Find product name and link - look for link with product name
            product_name = None
            product_link_url = None
            
            # Find all links with conceptsintl.myshopify.com href
            all_links = product_row.find_all('a', href=re.compile(r'conceptsintl\.myshopify\.com'))
            
            # Find the link that contains product name text (not the image link)
            product_link = None
            for link in all_links:
                # Skip image links (they contain img tags)
                if link.find('img'):
                    continue
                
                # Product name links have text content
                link_text = link.get_text(strip=True)
                if link_text and len(link_text) > 2:
                    product_link = link
                    break
            
            if product_link:
                raw_product_name = product_link.get_text(strip=True)
                product_link_url = product_link.get('href', '')
                
                # Clean up product name: remove color variants in parentheses and trailing size numbers
                # Example: "Nike Womens Air Jordan 1 Mid (Black/Gym Red/College Grey/Sail) 9" 
                # -> "Nike Womens Air Jordan 1 Mid"
                # Example: "On Cloud 5 (White)" -> "On Cloud 5"
                product_name = raw_product_name
                
                # Remove color/variant info in parentheses: (Black/Gym Red/College Grey/Sail) or (White)
                product_name = re.sub(r'\s*\([^)]+\)\s*', ' ', product_name)
                
                # Remove trailing size numbers (single digits or decimal numbers)
                # Pattern: space followed by a number at the end
                product_name = re.sub(r'\s+\d+(?:\.\d+)?\s*$', '', product_name)
                
                # Clean up extra whitespace
                product_name = product_name.strip()
                
                logger.debug(f"Extracted product name: '{product_name}' from raw text: '{raw_product_name}'")
            else:
                # Fallback: Try to extract from image alt text
                img_alt = img.get('alt', '')
                if img_alt:
                    # Alt text format: "On Cloud 5 (White) - 10.5"
                    # Extract product name part (before the dash and size)
                    alt_match = re.match(r'^(.+?)\s*-\s*\d', img_alt)
                    if alt_match:
                        raw_product_name = alt_match.group(1).strip()
                        product_name = re.sub(r'\s*\([^)]+\)\s*', ' ', raw_product_name).strip()
                        logger.debug(f"Extracted product name from alt text: '{product_name}'")
            
            unique_id = self._extract_unique_id_from_image_url(img_src, product_link_url)
            
            # Note: If unique ID cannot be extracted, we skip this product
            # The unique ID is required for matching with OA sourcing records
            # However, some emails may use generic Shopify file URLs that don't contain the product code
            # In production, the image URLs should contain the product code pattern
            if not unique_id:
                logger.warning(f"Could not extract unique ID from image URL: {img_src[:150]}")
                if product_link_url:
                    logger.warning(f"  Product link URL: {product_link_url[:150]}")
                if product_name:
                    logger.warning(f"  Product name: {product_name}")
                # Continue to extract other details, but we'll return None if unique_id is still missing
            
            # Find size - look for span with color #767676 (gray text)
            size = None
            size_span = product_row.find('span', style=re.compile(r'color:#767676'))
            if size_span:
                size = size_span.get_text(strip=True)
            
            if not size:
                # Fallback: look for size in alt text of image
                img_alt = img.get('alt', '')
                size_match = re.search(r'-\s*(\d+(?:\.\d+)?)\s*["\']?$', img_alt)
                if size_match:
                    size = size_match.group(1)
            
            if not size:
                size = "Unknown"
            
            # Find quantity - look for text containing "x " followed by number
            quantity = 1
            quantity_text = product_row.find(string=re.compile(r'x\s*\d+'))
            if quantity_text:
                qty_match = re.search(r'x\s*(\d+)', quantity_text)
                if qty_match:
                    quantity = int(qty_match.group(1))
            
            if not unique_id:
                logger.warning("Could not extract unique ID")
                return None
            
            return ConceptsOrderItem(
                unique_id=unique_id,
                size=size,
                quantity=quantity,
                product_name=product_name
            )
            
        except Exception as e:
            logger.error(f"Error extracting CNCPTS product details: {e}", exc_info=True)
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
            # Look for h2 that contains "Order No." - the structure is:
            # <h2><span>Order No.</span> #342893</h2>
            order_headings = soup.find_all('h2')
            for h2 in order_headings:
                text = h2.get_text()
                if re.search(r'Order\s+No\.', text, re.IGNORECASE):
                    # Extract number after #
                    match = re.search(r'#\s*(\d+)', text)
                    if match:
                        order_number = match.group(1)
                        logger.debug(f"Extracted order number: {order_number}")
                        return order_number
            
            # Fallback: Look for text containing "Order No." and extract from parent
            order_text = soup.find(string=re.compile(r'Order\s+No\.', re.IGNORECASE))
            if order_text:
                # Find the h2 parent
                h2_parent = order_text.find_parent('h2')
                if h2_parent:
                    text = h2_parent.get_text()
                    match = re.search(r'#\s*(\d+)', text)
                    if match:
                        order_number = match.group(1)
                        logger.debug(f"Extracted order number (fallback): {order_number}")
                        return order_number
            
            logger.warning("Could not extract order number")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting order number: {e}", exc_info=True)
            return None
    
    def _extract_products(self, soup: BeautifulSoup) -> List[ConceptsOrderItem]:
        """
        Extract products from HTML.
        
        Args:
            soup: BeautifulSoup object
        
        Returns:
            List of ConceptsOrderItem objects
        """
        items = []
        
        try:
            # Find all product images from shopify
            product_images = soup.find_all('img', src=re.compile(r'cdn\.shopify\.com.*(?:products|files)'))
            
            logger.debug(f"Found {len(product_images)} Shopify images")
            
            seen_products = set()
            
            for img in product_images:
                # Exclude non-product images
                img_src = img.get('src', '')
                if any(exclude in img_src.lower() for exclude in ['logo', 'spacer', 'icon', 'arrow', 'facebook', 'twitter', 'instagram']):
                    logger.debug(f"Skipping non-product image: {img_src[:100]}")
                    continue
                
                # Check if this is a product image (has product name link nearby)
                parent = img.find_parent(['th', 'td', 'tr'])
                if not parent:
                    logger.debug(f"No parent found for image: {img_src[:100]}")
                    continue
                
                # Check if this row contains product information (has size and quantity)
                # Look for quantity pattern in parent or nearby elements
                parent_text = parent.get_text()
                # Also check parent's parent (table row) for quantity
                grandparent = parent.find_parent('tr')
                grandparent_text = grandparent.get_text() if grandparent else ""
                
                has_qty = bool(re.search(r'x\s*\d+', parent_text)) or bool(re.search(r'x\s*\d+', grandparent_text))
                if not has_qty:
                    logger.debug(f"No quantity pattern found in parent text for image: {img_src[:100]}")
                    continue
                
                logger.debug(f"Processing product image: {img_src[:100]}")
                
                # Create a unique identifier for this product (image src + size)
                img_src = img.get('src', '')
                alt_text = img.get('alt', '')
                
                # Try to extract size from alt text for uniqueness
                size_match = re.search(r'-\s*(\d+(?:\.\d+)?)', alt_text)
                size_key = size_match.group(1) if size_match else "unknown"
                
                product_id = f"{img_src}_{size_key}"
                
                if product_id in seen_products:
                    continue
                seen_products.add(product_id)
                
                try:
                    # Find the table row containing this product
                    # The structure is: <tr> -> <th> (image) -> <th> (product info with nested table)
                    product_row = img.find_parent('tr')
                    if not product_row:
                        # Fallback: use parent and look for the containing row
                        product_row = parent.find_parent('tr') or parent
                    
                    product_details = self._extract_concepts_product_details(product_row)
                    
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
            
            logger.info(f"Extracted {len(items)} products from CNCPTS email")
            return items
            
        except Exception as e:
            logger.error(f"Error extracting CNCPTS products: {e}", exc_info=True)
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
            # Look for "Shipping Address" heading
            shipping_heading = soup.find('h3', string=re.compile(r'Shipping\s+Address', re.IGNORECASE))
            
            if shipping_heading:
                # Find the parent table/row
                parent = shipping_heading.find_parent(['th', 'td', 'tr'])
                
                if parent:
                    # Look for paragraph containing address information
                    address_p = parent.find('p')
                    
                    if address_p:
                        # Get text and clean it up
                        address_text = address_p.get_text(separator=' ', strip=True)
                        
                        # Remove phone number if present
                        address_text = re.sub(r'Tel\.\s*\+?\d[\d\s\-\(\)]+', '', address_text)
                        
                        # Normalize the address
                        normalized = normalize_shipping_address(address_text)
                        logger.debug(f"Extracted shipping address: {normalized}")
                        return normalized
            
            logger.warning("Could not extract shipping address")
            return ""
            
        except Exception as e:
            logger.error(f"Error extracting shipping address: {e}", exc_info=True)
            return ""
    
    def parse_email(self, email_data: EmailData) -> Optional[ConceptsOrderData]:
        """
        Parse a CNCPTS order confirmation email.
        
        Args:
            email_data: Email data to parse
        
        Returns:
            ConceptsOrderData object or None if parsing fails
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
            
            return ConceptsOrderData(
                order_number=order_number,
                items=items,
                shipping_address=shipping_address
            )
            
        except Exception as e:
            logger.error(f"Error parsing CNCPTS order email: {e}", exc_info=True)
            return None
