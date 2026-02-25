"""
END Clothing Email Parser
Parses order confirmation emails from END Clothing
"""

import re
import logging
from typing import List, Optional
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from app.models.email import EmailData

logger = logging.getLogger(__name__)


class ENDClothingOrderItem(BaseModel):
    """Represents a single item from an END Clothing order"""
    unique_id: str = Field(..., description="Unique identifier for the product (extracted from image URL)")
    size: str = Field(..., description="Converted size based on brand and gender")
    quantity: int = Field(..., description="Quantity of the product")
    product_name: str = Field(..., description="Name of the product")
    original_size: str = Field(..., description="Original size from email (e.g., 'UK 7.5')")
    
    def __repr__(self):
        if self.product_name and len(self.product_name) > 50:
            product_display = self.product_name[:50] + "..."
        else:
            product_display = self.product_name or "Unknown"
        return f"<ENDClothingOrderItem(unique_id={self.unique_id}, size={self.size}, qty={self.quantity}, product={product_display})>"


class ENDClothingOrderData(BaseModel):
    """Represents END Clothing order data"""
    order_number: str = Field(..., description="The order number")
    items: List[ENDClothingOrderItem] = Field(..., description="List of items in the order")
    items_count: int = Field(0, description="Total number of items in the order")
    shipping_address: str = Field("", description="Normalized shipping address")

    def __init__(self, **data):
        super().__init__(**data)
        self.items_count = len(self.items)
    
    def __repr__(self):
        return f"<ENDClothingOrderData(order={self.order_number}, items={len(self.items)})>"


class ENDClothingShippingData(BaseModel):
    """Represents END Clothing shipping notification data - same structure as Footlocker for processing."""
    order_number: str = Field(..., description="The order number")
    tracking_number: str = Field("", description="Tracking number if available")
    items: List[ENDClothingOrderItem] = Field(..., description="List of shipped items")


class ENDClothingEmailParser:
    """
    Parser for END Clothing order confirmation emails.
    
    Handles email formats like:
    From: info@orders.endclothing.com
    Subject: "Your END. order confirmation"
    
    Features:
    - Brand and gender-based size conversion (Nike, Jordan, Adidas, Hoka, On)
    - Unique ID extraction from image URLs
    """
    
    # Email identification - Production
    ENDCLOTHING_FROM_EMAIL = "info@orders.endclothing.com"
    SUBJECT_ORDER_PATTERN = r"your\s+end\.?\s+order\s+confirmation"
    
    # Email identification - Shipping (same from as order confirmation)
    SUBJECT_SHIPPING_PATTERN = r"your\s+end\.?\s+order\s+has\s+shipped"
    DEV_SUBJECT_SHIPPING_PATTERN = r"(?:Fwd:\s*)?Your\s+END\.?\s+order\s+has\s+shipped"
    
    # Email identification - Development (forwarded emails)
    DEV_ENDCLOTHING_ORDER_FROM_EMAIL = "glenallagroupc@gmail.com"
    DEV_SUBJECT_ORDER_PATTERN = r"Fwd:\s*Your\s+END\.?\s+order\s+confirmation"
    
    def __init__(self):
        """Initialize the END Clothing email parser."""
        from app.config.settings import get_settings
        self.settings = get_settings()
    
    @property
    def order_from_email(self) -> str:
        """Get the appropriate from email address based on environment."""
        if self.settings.is_development:
            return self.DEV_ENDCLOTHING_ORDER_FROM_EMAIL
        return self.ENDCLOTHING_FROM_EMAIL
    
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
            return "END. order confirmation"
        return "END. order confirmation"
    
    @property
    def update_from_email(self) -> str:
        """From address for shipping emails (same as order confirmation)."""
        return self.order_from_email
    
    @property
    def shipping_subject_query(self) -> str:
        """Subject query for Gmail shipping search."""
        return 'subject:"Your END. order has shipped"'
    
    def is_endclothing_email(self, email_data: EmailData) -> bool:
        """
        Check if email is from END Clothing.
        
        In dev mode, multiple retailers forward from glenallagroupc. Require HTML
        to contain "endclothing" or "end." (brand) to uniquely filter END Clothing
        and avoid claiming other retailers' forwarded emails.
        """
        sender_lower = email_data.sender.lower()
        
        # In development, check for forwarded emails from dev email address
        if self.settings.is_development:
            if self.DEV_ENDCLOTHING_ORDER_FROM_EMAIL.lower() in sender_lower:
                html = (email_data.html_content or "").lower()
                # END Clothing branding: media.endclothing.com, email.orders.endclothing.com
                if "endclothing" in html:
                    return True
                return False
        
        # In production, check for END Clothing email
        return self.ENDCLOTHING_FROM_EMAIL.lower() in sender_lower
    
    def is_shipping_email(self, email_data: EmailData) -> bool:
        """Check if email is a END Clothing shipping notification."""
        if not self.is_endclothing_email(email_data):
            return False
        subject_lower = (email_data.subject or "").lower()
        if re.search(self.SUBJECT_SHIPPING_PATTERN, subject_lower, re.IGNORECASE):
            return True
        if self.settings.is_development and re.search(self.DEV_SUBJECT_SHIPPING_PATTERN, subject_lower, re.IGNORECASE):
            return True
        return False

    def is_order_confirmation_email(self, email_data: EmailData) -> bool:
        """Check if email is an order confirmation"""
        if not self.is_endclothing_email(email_data):
            return False
        subject_pattern = self.order_subject_pattern
        return bool(re.search(subject_pattern, email_data.subject, re.IGNORECASE))
    
    def parse_email(self, email_data: EmailData) -> Optional[ENDClothingOrderData]:
        """
        Parse END Clothing order confirmation email.
        
        Args:
            email_data: EmailData object containing email information
        
        Returns:
            ENDClothingOrderData object or None if parsing fails
        """
        try:
            html_content = email_data.html_content
            
            if not html_content:
                logger.error("No HTML content in END Clothing email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extract order number
            order_number = self._extract_order_number(soup)
            if not order_number:
                logger.error("Failed to extract order number from END Clothing email")
                return None
            
            logger.info(f"Extracted END Clothing order number: {order_number}")
            
            # Extract items
            items = self._extract_items(soup)
            
            if not items:
                logger.error("Failed to extract any items from END Clothing email")
                return None
            
            logger.info(f"Successfully extracted {len(items)} items from END Clothing order {order_number}")
            for item in items:
                logger.debug(f"  - {item}")
            
            # Extract shipping address
            from app.utils.address_utils import normalize_shipping_address
            shipping_address = self._extract_shipping_address(soup)
            if shipping_address:
                normalized = normalize_shipping_address(shipping_address)
                logger.info(f"Extracted shipping address: {normalized}")
                shipping_address = normalized
            
            return ENDClothingOrderData(order_number=order_number, items=items, shipping_address=shipping_address)
        
        except Exception as e:
            logger.error(f"Error parsing END Clothing email: {e}", exc_info=True)
            return None
    
    def parse_shipping_email(self, email_data: EmailData) -> Optional["ENDClothingShippingData"]:
        """
        Parse END Clothing shipping notification email.
        
        Subject: "Your END. order has shipped"
        Order: Same extraction as order confirmation (order #2404721277)
        Items: Same structure - UK/US + size + QTY, with brand/gender size conversion
        """
        try:
            html_content = email_data.html_content
            if not html_content:
                logger.error("No HTML content in END Clothing shipping email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            order_number = self._extract_order_number(soup)
            if not order_number:
                logger.error("Failed to extract order number from END Clothing shipping email")
                return None
            
            tracking_number = self._extract_shipping_tracking_number(soup)
            if not tracking_number:
                tracking_number = "Unknown"
            
            items = self._extract_items(soup)  # Same HTML structure as order confirmation
            if not items:
                logger.error("Failed to extract items from END Clothing shipping email")
                return None
            
            logger.info(
                f"Parsed END Clothing shipping: order={order_number}, tracking={tracking_number}, items={len(items)}"
            )
            return ENDClothingShippingData(
                order_number=order_number,
                tracking_number=tracking_number or "",
                items=items
            )
        except Exception as e:
            logger.error(f"Error parsing END Clothing shipping email: {e}", exc_info=True)
            return None
    
    def _extract_shipping_tracking_number(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract tracking number from END Clothing shipping email if present."""
        try:
            text = soup.get_text().upper()
            match = re.search(r'\b1Z[A-Z0-9]{16}\b', text)
            if match:
                return match.group(0)
            match = re.search(r'\b\d{12,22}\b', text)
            if match:
                return match.group(0)
            return None
        except Exception as e:
            logger.debug(f"Could not extract tracking from END Clothing shipping: {e}")
            return None
    
    def _extract_order_number(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract order number from END Clothing email.
        
        Pattern: "Your order #2404720997 will soon be on its way"
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            Order number or None
        """
        try:
            # Look for text containing "order #"
            text = soup.get_text()
            match = re.search(r'order\s+#(\d+)', text, re.IGNORECASE)
            if match:
                order_number = match.group(1)
                logger.debug(f"Found END Clothing order number: {order_number}")
                return order_number
            
            logger.warning("Order number not found in END Clothing email")
            return None
        
        except Exception as e:
            logger.error(f"Error extracting END Clothing order number: {e}")
            return None
    
    def _extract_items(self, soup: BeautifulSoup) -> List[ENDClothingOrderItem]:
        """
        Extract order items from END Clothing email.
        
        Structure:
        - Product image with unique ID in URL
        - Product name (e.g., "Nike W V2K Run Sneaker")
        - Size and quantity: "UK 7.5 QTY 8"
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            List of ENDClothingOrderItem objects
        """
        items = []
        
        try:
            # Find all product images (from END Clothing catalog - exclude wysiwyg/transactional like NeedHelpHighRes)
            product_images = soup.find_all('img', src=lambda x: (
                x and 'media.endclothing.com' in str(x) and 'prodmedia' in str(x)
                and 'catalog/product' in str(x)
            ))
            
            logger.info(f"Found {len(product_images)} potential product images")
            
            for img in product_images:
                try:
                    # Get the parent container for this product
                    # The structure is complex, so we need to navigate up to find the product row
                    product_container = img.find_parent('table')
                    if not product_container:
                        continue
                    
                    # Extract product details from this container
                    product_details = self._extract_product_details(product_container, img)
                    
                    if product_details:
                        items.append(ENDClothingOrderItem(
                            unique_id=product_details['unique_id'],
                            size=product_details['size'],
                            quantity=product_details['quantity'],
                            product_name=product_details['product_name'],
                            original_size=product_details['original_size']
                        ))
                        logger.info(
                            f"Extracted END Clothing item: {product_details['product_name']} | "
                            f"unique_id={product_details['unique_id']}, "
                            f"Size={product_details['original_size']} -> {product_details['size']}, "
                            f"Qty={product_details['quantity']}"
                        )
                
                except Exception as e:
                    logger.error(f"Error processing END Clothing product: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error extracting END Clothing items: {e}", exc_info=True)
        
        return items
    
    def _extract_product_details(self, container, img) -> Optional[dict]:
        """
        Extract product details from a product container.
        
        Returns:
            Dictionary with unique_id, size, quantity, product_name, original_size or None
        """
        try:
            details = {}
            
            # Extract unique ID from image URL
            # Pattern: .../17-06-2024-LB_FD0736-104_2_1.jpg
            # Extract: fd0736-104 (lowercase)
            img_src = img.get('src', '')
            # Look for pattern: letters+numbers-numbers in filename
            match = re.search(r'/([A-Z]{2}\d{4}-\d{3})_', img_src, re.IGNORECASE)
            if not match:
                # Try alternative pattern without underscore
                match = re.search(r'([A-Z]{2}\d{4}-\d{3})', img_src, re.IGNORECASE)
            
            if match:
                unique_id = match.group(1).lower()  # Convert to lowercase
                details['unique_id'] = unique_id
                logger.debug(f"Found unique ID: {unique_id}")
            else:
                logger.warning(f"Could not extract unique ID from image URL: {img_src}")
                return None
            
            # Extract product name
            # Look for <p> tag with product name (not the color description)
            product_p = container.find('p', style=lambda x: x and 'font-size:14px' in str(x) and 'line-height:22px' in str(x))
            if product_p:
                product_text = product_p.get_text(strip=True)
                # Skip if it contains color information (has commas or &)
                if ',' not in product_text and '&' not in product_text and 'QTY' not in product_text:
                    details['product_name'] = product_text
                    logger.debug(f"Found product name: {product_text}")
            
            if 'product_name' not in details:
                logger.warning("Product name not found")
                return None
            
            # Extract size and quantity
            # Pattern: "UK 7.5 QTY 8"
            container_text = container.get_text()
            size_qty_match = re.search(r'(UK|US)\s+(\d+(?:\.\d+)?)\s+QTY\s+(\d+)', container_text, re.IGNORECASE)
            if size_qty_match:
                size_system = size_qty_match.group(1).upper()  # UK or US
                original_size_value = size_qty_match.group(2)  # 7.5
                quantity = int(size_qty_match.group(3))  # 8
                
                details['original_size'] = f"{size_system} {original_size_value}"
                details['quantity'] = quantity
                
                # Convert size based on brand and gender
                converted_size = self._convert_size(
                    product_name=details['product_name'],
                    size_system=size_system,
                    size_value=original_size_value
                )
                details['size'] = converted_size
                
                logger.debug(f"Found size/qty: {size_system} {original_size_value} -> {converted_size}, QTY {quantity}")
            else:
                logger.warning("Size and quantity not found")
                return None
            
            return details
            
        except Exception as e:
            logger.error(f"Error extracting product details: {e}", exc_info=True)
            return None
    
    def _convert_size(self, product_name: str, size_system: str, size_value: str) -> str:
        """
        Convert size based on brand and gender according to the size conversion table.
        
        Rules:
        - Nike/Jordan Men's UK: +0.5
        - Nike/Jordan Women's UK: +2
        - Nike/Jordan US (both genders): no change
        - Hoka UK: +0.5
        - Hoka US: no change
        - On UK: +0.5
        - On US: no change
        - Adidas Men's UK: +0.5
        - Adidas Women's UK: +1.5
        - Adidas US (both genders): no change
        
        Args:
            product_name: Product name (used to determine brand and gender)
            size_system: "UK" or "US"
            size_value: Original size value (e.g., "7.5")
        
        Returns:
            Converted size as string
        """
        try:
            size_float = float(size_value)
            product_lower = product_name.lower()
            
            # Determine brand
            brand = None
            if 'nike' in product_lower or 'jordan' in product_lower:
                brand = 'nike'
            elif 'hoka' in product_lower:
                brand = 'hoka'
            elif 'on' in product_lower or 'on running' in product_lower:
                brand = 'on'
            elif 'adidas' in product_lower:
                brand = 'adidas'
            
            # Determine gender
            # Default is Men's
            # If product name contains "W" (standalone), "Women's", or "Wmns", it's Women's
            # Example: "Nike W V2K Run Sneaker" -> Women's
            is_womens = bool(re.search(r'\bW\b|\bWomen\'?s?\b|\bWmns\b', product_name, re.IGNORECASE))
            
            logger.debug(f"Size conversion: brand={brand}, gender={'Women' if is_womens else 'Men'}, system={size_system}, original={size_value}")
            
            # Apply conversion rules
            if size_system == "UK":
                if brand in ['nike', 'jordan']:
                    if is_womens:
                        converted = size_float + 2.0
                    else:
                        converted = size_float + 0.5
                elif brand in ['hoka', 'on']:
                    converted = size_float + 0.5
                elif brand == 'adidas':
                    if is_womens:
                        converted = size_float + 1.5
                    else:
                        converted = size_float + 0.5
                else:
                    # Unknown brand, no conversion
                    converted = size_float
            else:  # US
                # US sizes: no conversion for any brand
                converted = size_float
            
            # Format the result (remove .0 for whole numbers)
            if converted == int(converted):
                result = str(int(converted))
            else:
                result = str(converted)
            
            logger.debug(f"Size converted: {size_value} -> {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error converting size: {e}")
            return size_value  # Return original on error
    
    def _extract_shipping_address(self, soup: BeautifulSoup) -> str:
        """
        Extract shipping address from END Clothing email.
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            Shipping address or empty string
        """
        try:
            # Look for "Shipping address" or similar text
            # END Clothing emails may have shipping info in various formats
            text = soup.get_text()
            
            # Look for address patterns after "shipping" keyword
            lines = text.split('\n')
            in_shipping_section = False
            address_lines = []
            
            for i, line in enumerate(lines):
                line = line.strip()
                
                if 'shipping address' in line.lower() or 'deliver to' in line.lower():
                    in_shipping_section = True
                    continue
                
                if in_shipping_section:
                    # Stop at next section
                    if any(keyword in line.lower() for keyword in ['billing', 'payment', 'subtotal', 'total', 'need help']):
                        break
                    
                    # Skip empty lines
                    if not line:
                        continue
                    
                    # Skip name lines (simple heuristic)
                    if re.match(r'^[A-Z][a-z]+\s+[A-Z][a-z]+$', line):
                        continue
                    
                    # Collect address lines that contain numbers or common address components
                    if re.search(r'\d+', line) or any(keyword in line.lower() for keyword in ['lane', 'street', 'ave', 'road', 'suite', 'ste']):
                        address_lines.append(line)
                        # Typically we want 1-3 lines
                        if len(address_lines) >= 3:
                            break
            
            if address_lines:
                address_combined = ', '.join(address_lines)
                logger.debug(f"Extracted shipping address (raw): {address_combined}")
                return address_combined
            
            logger.warning("Shipping address not found in END Clothing email")
            return ""
        
        except Exception as e:
            logger.error(f"Error extracting shipping address: {e}", exc_info=True)
            return ""
