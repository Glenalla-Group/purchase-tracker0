"""
Gazelle Sports Email Parser
Parses order confirmation emails from Gazelle Sports using BeautifulSoup

Email Format:
- From: customercare@gazellesports.com (production)
- From: glenallagroupc@gmail.com (dev - forwarded emails)
- Subject: "Thank you for shopping with us!" or similar
- Order Number: Extract from HTML (e.g., "GS169837")

HTML Structure:
- Products are listed in tables
- Each product has:
  - Product image: <img src="https://cdn.shopify.com/.../products/110395_405_L_Levitate_6_compact_cropped.jpg">
  - Product name: <span>Men's Levitate 6 Running Shoe - Classic Blue/Orange - Regular (D) × 1</span>
  - Size: <span style="font-size:14px;color:#999;font-weight:400">11.5</span>
  - Quantity: Extracted from product name (× 1, × 4, etc.)

Unique ID Extraction:
- Format: {product_id}_{variant_id} (e.g., "110395_405")
- Extract from product image URL: https://cdn.shopify.com/.../products/{product_id}_{variant_id}_...
- Pattern: products/(\d+)_(\d+)_
- Example: "110395_405_L_Levitate_6_compact_cropped.jpg" -> "110395_405"
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


class GazelleOrderItem(BaseModel):
    unique_id: str = Field(..., description="Unique identifier for the product (e.g., 110395_405)")
    size: str = Field(..., description="Size of the product")
    quantity: int = Field(..., description="Quantity of the product")
    product_name: Optional[str] = Field(None, description="Name of the product")
    
    def __repr__(self):
        if self.product_name and len(self.product_name) > 50:
            product_display = self.product_name[:50] + "..."
        else:
            product_display = self.product_name or "Unknown"
        return f"<GazelleOrderItem(unique_id={self.unique_id}, size={self.size}, qty={self.quantity}, product={product_display})>"


class GazelleOrderData(BaseModel):
    order_number: str = Field(..., description="The order number")
    items: List[GazelleOrderItem] = Field(..., description="List of items in the order")
    items_count: int = Field(0, description="Total number of items in the order")
    shipping_address: str = Field("", description="Normalized shipping address")

    def __init__(self, **data):
        super().__init__(**data)
        self.items_count = len(self.items)


class GazelleEmailParser:
    # Email identification - Order Confirmation (Production)
    GAZELLE_FROM_EMAIL = "customercare@gazellesports.com"
    SUBJECT_ORDER_PATTERN = r"thank\s+you\s+for\s+shopping"
    
    # Email identification - Development (forwarded emails)
    DEV_GAZELLE_ORDER_FROM_EMAIL = "glenallagroupc@gmail.com"
    # Must match Gazelle-specific - avoid broad "order" which matches ASOS shipping, etc.
    DEV_SUBJECT_ORDER_PATTERN = r"(?:Fwd:\s*)?(?:thank\s+you\s+for\s+shopping|gazelle)"

    def __init__(self):
        """Initialize the Gazelle email parser."""
        self.settings = get_settings()
    
    @property
    def order_from_email(self) -> str:
        """Get the appropriate from email address based on environment."""
        if self.settings.is_development:
            return self.DEV_GAZELLE_ORDER_FROM_EMAIL
        return self.GAZELLE_FROM_EMAIL
    
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
        return "Thank you for shopping"

    def is_gazelle_email(self, email_data: EmailData) -> bool:
        """Check if email is from Gazelle Sports. Exclude ASOS shipping (subject "on its way")."""
        sender_lower = email_data.sender.lower()
        subject_lower = (email_data.subject or "").lower()
        if "on its way" in subject_lower:
            return False
        
        # In development, check for forwarded emails from dev email address
        if self.settings.is_development:
            if self.DEV_GAZELLE_ORDER_FROM_EMAIL.lower() in sender_lower:
                return True
        
        # In production, check for Gazelle email
        return self.GAZELLE_FROM_EMAIL.lower() in sender_lower

    def is_order_confirmation_email(self, email_data: EmailData) -> bool:
        """Check if email is an order confirmation"""
        subject_lower = email_data.subject.lower()
        pattern = self.order_subject_pattern
        
        # Use regex matching for subject pattern
        if re.search(pattern, subject_lower, re.IGNORECASE):
            return True
        
        # For forwarded emails in dev mode, also check HTML content for Gazelle confirmation indicators
        if self.settings.is_development and email_data.html_content:
            html_lower = email_data.html_content.lower()
            # Check for "Thank you for shopping" or order confirmation indicators
            has_confirmation_text = (
                'thank you for shopping' in html_lower or
                'order summary' in html_lower or
                ('gazelle' in html_lower and 'order' in html_lower) or
                'gs' in html_lower and re.search(r'gs\d+', html_lower)
            )
            if has_confirmation_text:
                return True
        
        return False

    def parse_email(self, email_data: EmailData) -> Optional[GazelleOrderData]:
        """
        Parse Gazelle Sports order confirmation email.
        
        Args:
            email_data: EmailData object containing email information
        
        Returns:
            GazelleOrderData object or None if parsing fails
        """
        try:
            html_content = email_data.html_content
            
            if not html_content:
                logger.error("No HTML content in Gazelle email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extract order number from HTML
            order_number = self._extract_order_number(soup)
            if not order_number:
                logger.error("Failed to extract order number from Gazelle email")
                return None
            
            logger.info(f"Extracted Gazelle order number: {order_number}")
            
            # Extract items using BeautifulSoup
            items = self._extract_items(soup)
            
            if not items:
                logger.error("Failed to extract any items from Gazelle email")
                return None
            
            logger.info(f"Successfully extracted {len(items)} items from Gazelle order {order_number}")
            for item in items:
                logger.debug(f"  - {item}")
            
            # Extract shipping address
            shipping_address = self._extract_shipping_address(soup)
            if shipping_address:
                logger.info(f"Extracted shipping address: {shipping_address}")
            
            return GazelleOrderData(order_number=order_number, items=items, shipping_address=shipping_address)
        
        except Exception as e:
            logger.error(f"Error parsing Gazelle email: {e}", exc_info=True)
            return None

    def _extract_order_number(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract order number from Gazelle email HTML.
        
        HTML format: 
        - <span style="font-size:16px"> Order GS169837 </span>
        
        Extract: GS169837
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            Order number or None
        """
        try:
            # Method 1: Look for "Order GS" pattern
            text_content = soup.get_text()
            match = re.search(r'Order\s+(GS\d+)', text_content, re.IGNORECASE)
            if match:
                order_number = match.group(1).upper()
                logger.debug(f"Found Gazelle order number: {order_number}")
                return order_number
            
            # Method 2: Look for GS pattern directly
            match = re.search(r'(GS\d+)', text_content, re.IGNORECASE)
            if match:
                order_number = match.group(1).upper()
                logger.debug(f"Found Gazelle order number (fallback): {order_number}")
                return order_number
            
            logger.warning("Order number not found in Gazelle email")
            return None
        
        except Exception as e:
            logger.error(f"Error extracting Gazelle order number: {e}")
            return None

    def _extract_items(self, soup: BeautifulSoup) -> List[GazelleOrderItem]:
        """
        Extract order items from Gazelle email.
        
        Gazelle email structure:
        - Products are in table rows within "Order summary" section
        - Each product row has:
          - Image with product ID in URL
          - Product name with quantity (× 1, × 4, etc.)
          - Size in a span tag
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            List of GazelleOrderItem objects
        """
        items = []
        
        try:
            # Find the "Order summary" section
            order_summary_header = soup.find('h3', string=re.compile(r'Order\s+summary', re.IGNORECASE))
            
            if not order_summary_header:
                logger.warning("Order summary section not found")
                return []
            
            # Find all product rows - look for table rows with images
            # Product rows are in tables with product images
            product_rows = []
            
            # Find all images with Shopify CDN URLs (product images)
            product_images = soup.find_all('img', src=re.compile(r'cdn\.shopify\.com.*products/'))
            
            for img in product_images:
                # Find the parent row (tr) that contains this image
                row = img.find_parent('tr')
                if row:
                    product_rows.append((row, img))
            
            # Process each product row
            for row, img in product_rows:
                try:
                    product_details = self._extract_gazelle_product_details(row, img)
                    
                    if product_details:
                        items.append(product_details)
                
                except Exception as e:
                    logger.error(f"Error processing Gazelle product row: {e}")
                    continue
            
            # Log items with ID, size, and quantity
            if items:
                items_summary = [f"(ID: {item.unique_id}, Size: {item.size}, Qty: {item.quantity})" for item in items]
                logger.info(f"[Gazelle] Extracted {len(items)} items: {', '.join(items_summary)}")
            
            return items
        
        except Exception as e:
            logger.error(f"Error extracting Gazelle items: {e}", exc_info=True)
            return []

    def _extract_gazelle_product_details(self, row, img) -> Optional[GazelleOrderItem]:
        """
        Extract product details from a Gazelle product row.
        
        Returns:
            GazelleOrderItem object or None
        """
        try:
            details = {}
            
            # Extract unique ID from image URL
            # Pattern: .../products/110395_405_L_Levitate_6_compact_cropped.jpg
            # Extract: 110395_405
            img_src = img.get('src', '')
            unique_id = self._extract_unique_id_from_image(img_src)
            
            if not unique_id:
                logger.warning(f"Unique ID not found in image URL: {img_src[:100]}")
                return None
            
            details['unique_id'] = unique_id
            logger.debug(f"Found unique ID: {unique_id}")
            
            # Extract product name and quantity
            # Product name format: "Men's Levitate 6 Running Shoe - Classic Blue/Orange - Regular (D) × 1"
            row_text = row.get_text()
            
            # Find product name span (font-size:16px, font-weight:600)
            product_name_span = row.find('span', style=lambda x: x and 'font-size:16px' in str(x) and 'font-weight:600' in str(x))
            if product_name_span:
                product_name_with_qty = product_name_span.get_text(strip=True)
                
                # Extract quantity from product name (× 1, × 4, etc.)
                qty_match = re.search(r'×\s*(\d+)', product_name_with_qty)
                if qty_match:
                    quantity = int(qty_match.group(1))
                else:
                    quantity = 1
                    logger.debug("Quantity not found in product name, defaulting to 1")
                
                # Remove quantity from product name
                product_name = re.sub(r'\s*×\s*\d+\s*$', '', product_name_with_qty).strip()
                details['product_name'] = product_name
                details['quantity'] = quantity
                logger.debug(f"Found product name: {product_name}, quantity: {quantity}")
            else:
                logger.warning("Product name not found in row")
                return None
            
            # Extract size
            # Size is in a span with font-size:14px and color:#999
            size_span = row.find('span', style=lambda x: x and 'font-size:14px' in str(x) and 'color:#999' in str(x))
            if size_span:
                size = size_span.get_text(strip=True)
                details['size'] = size
                logger.debug(f"Found size: {size}")
            else:
                logger.warning("Size not found in row")
                return None
            
            return GazelleOrderItem(
                unique_id=details['unique_id'],
                size=details['size'],
                quantity=details['quantity'],
                product_name=details['product_name']
            )
            
        except Exception as e:
            logger.error(f"Error extracting Gazelle product details: {e}", exc_info=True)
            return None
    
    def _extract_unique_id_from_image(self, img_src: str) -> Optional[str]:
        """
        Extract unique ID from Gazelle product image URL.
        
        URL format: 
        https://cdn.shopify.com/s/files/1/2621/5296/products/110395_405_L_Levitate_6_compact_cropped.jpg?v=1669069158
        
        Extract: 110395_405
        
        Args:
            img_src: Image source URL
        
        Returns:
            Unique ID or None
        """
        try:
            # Pattern: products/(\d+)_(\d+)_
            # Extract the first two numeric parts separated by underscore
            match = re.search(r'products/(\d+)_(\d+)_', img_src)
            if match:
                product_id = match.group(1)
                variant_id = match.group(2)
                unique_id = f"{product_id}_{variant_id}"
                logger.debug(f"Extracted unique ID from URL: {unique_id}")
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
            # Look for "Shipping address" header
            shipping_header = soup.find('h4', string=re.compile(r'Shipping\s+address', re.IGNORECASE))
            
            if shipping_header:
                # Find the address text in the next p tag
                address_p = shipping_header.find_next('p')
                if address_p:
                    # Get address text, handling <br> tags
                    address_text = address_p.get_text(separator=' ', strip=True)
                    
                    if address_text:
                        normalized = normalize_shipping_address(address_text)
                        logger.debug(f"Extracted shipping address: {normalized}")
                        return normalized
            
            return ""
        
        except Exception as e:
            logger.error(f"Error extracting shipping address: {e}", exc_info=True)
            return ""
