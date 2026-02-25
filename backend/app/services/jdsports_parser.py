"""
JD Sports Email Parser
Parses order confirmation emails from JD Sports using BeautifulSoup

Email Format:
- From: jdsports@notifications.jdsports.com
- Subject: "Thank you for your order: #60011000606"
- Order Number: In email body and subject

HTML Structure:
- Products are in tables with product images
- Product image URL contains SKU: media.jdsports.com/s/jdsports/JH6365_100
- Product name in <td> with specific font styling
- Size in <td>: "Size: 7"
- Quantity in <td>: "Quantity: 4"

Parsing Method:
- Uses BeautifulSoup to find and parse HTML elements
- Extracts unique_id from image URL pattern
- Extracts size and quantity from text content

Example Extraction:
- Order: 5571219432
- Product: Women's adidas Originals Handball Spezial Casual Shoes
- SKU: JH6365_100
- Size: 7
- Quantity: 4
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


class JDSportsOrderItem(BaseModel):
    unique_id: str = Field(..., description="Unique identifier for the product (e.g., SKU, style code)")
    size: str = Field(..., description="Size of the product")
    quantity: int = Field(..., description="Quantity of the product")
    product_name: Optional[str] = Field(None, description="Name of the product")
    
    def __repr__(self):
        if self.product_name and len(self.product_name) > 50:
            product_display = self.product_name[:50] + "..."
        else:
            product_display = self.product_name or "Unknown"
        return f"<JDSportsOrderItem(unique_id={self.unique_id}, size={self.size}, qty={self.quantity}, product={product_display})>"


class JDSportsOrderData(BaseModel):
    order_number: str = Field(..., description="The order number")
    items: List[JDSportsOrderItem] = Field(..., description="List of items in the order")
    items_count: int = Field(0, description="Total number of items in the order")
    shipping_address: str = Field("", description="Normalized shipping address")

    def __init__(self, **data):
        super().__init__(**data)
        self.items_count = len(self.items)


class JDSportsEmailParser:
    # Email identification - Order Confirmation (Production)
    JDSPORTS_FROM_EMAIL = "jdsports@notifications.jdsports.com"
    SUBJECT_ORDER_PATTERN = r"thank you for your order"
    
    # Email identification - Development (forwarded emails)
    DEV_JDSPORTS_ORDER_FROM_EMAIL = "glenallagroupc@gmail.com"
    DEV_SUBJECT_ORDER_PATTERN = r"Fwd:\s*Thank you for your order"
    
    # Email identification - Shipping / Update (same HTML template as Finish Line)
    SUBJECT_SHIPPING_PATTERN = r"we've got the scoop"
    DEV_SUBJECT_SHIPPING_PATTERN = r"(?:Fwd:\s*)?.*we've got the scoop"
    
    # Email identification - Full Cancellation (same as Finish Line)
    SUBJECT_CANCELLATION_PATTERN = r"sorry.*had to cancel your order"
    DEV_SUBJECT_CANCELLATION_PATTERN = r"(?:Fwd:\s*)?.*sorry.*had to cancel your order"

    def __init__(self):
        """Initialize the JD Sports email parser."""
        self.settings = get_settings()
    
    @property
    def order_from_email(self) -> str:
        """Get the appropriate from email address based on environment."""
        if self.settings.is_development:
            return self.DEV_JDSPORTS_ORDER_FROM_EMAIL
        return self.JDSPORTS_FROM_EMAIL
    
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
            return "Thank you for your order"
        return "Thank you for your order"

    @property
    def update_from_email(self) -> str:
        """From email for shipping/update emails (same as order for JD Sports)."""
        if self.settings.is_development:
            return self.DEV_JDSPORTS_ORDER_FROM_EMAIL
        return self.JDSPORTS_FROM_EMAIL

    @property
    def shipping_subject_query(self) -> str:
        """Gmail query for shipping/update emails (same template as Finish Line)."""
        if self.settings.is_development:
            return 'subject:"Fwd: Your order. We\'ve got the scoop on it."'
        return 'subject:"Your order. We\'ve got the scoop on it."'

    @property
    def cancellation_subject_query(self) -> str:
        """Gmail query for full cancellation emails."""
        if self.settings.is_development:
            return 'subject:"Fwd: Sorry, but we had to cancel your order."'
        return 'subject:"Sorry, but we had to cancel your order."'

    def is_jdsports_email(self, email_data: EmailData) -> bool:
        """Check if email is from JD Sports"""
        sender_lower = email_data.sender.lower()
        
        # In development, check for forwarded emails from dev email address
        if self.settings.is_development:
            if self.DEV_JDSPORTS_ORDER_FROM_EMAIL.lower() in sender_lower:
                return True
        
        # In production, check for JD Sports email
        return self.JDSPORTS_FROM_EMAIL.lower() in sender_lower

    def is_order_confirmation_email(self, email_data: EmailData) -> bool:
        """Check if email is an order confirmation"""
        if self.is_shipping_email(email_data) or self.is_cancellation_email(email_data):
            return False
        subject_lower = email_data.subject.lower()
        return bool(re.search(self.order_subject_pattern, subject_lower, re.IGNORECASE))

    def is_shipping_email(self, email_data: EmailData) -> bool:
        """Check if email is a shipping/order update (same template as Finish Line)."""
        if not self.is_jdsports_email(email_data):
            return False
        subject_lower = email_data.subject.lower()
        if self.settings.is_development:
            return bool(re.search(self.DEV_SUBJECT_SHIPPING_PATTERN, subject_lower, re.IGNORECASE))
        return bool(re.search(self.SUBJECT_SHIPPING_PATTERN, subject_lower, re.IGNORECASE))

    def is_cancellation_email(self, email_data: EmailData) -> bool:
        """Check if email is a full cancellation (same template as Finish Line)."""
        if not self.is_jdsports_email(email_data):
            return False
        if self.is_shipping_email(email_data):
            return False
        subject_lower = email_data.subject.lower()
        if self.settings.is_development:
            return bool(re.search(self.DEV_SUBJECT_CANCELLATION_PATTERN, subject_lower, re.IGNORECASE))
        return bool(re.search(self.SUBJECT_CANCELLATION_PATTERN, subject_lower, re.IGNORECASE))

    def parse_shipping_email(self, email_data: EmailData):
        """
        Parse JD Sports shipping/update email. Same HTML template as Finish Line - delegate.
        Returns FinishLineShippingData (same structure).
        """
        from app.services.finishline_parser import FinishLineEmailParser
        return FinishLineEmailParser().parse_shipping_email(email_data)

    def parse_cancellation_email(self, email_data: EmailData):
        """
        Parse JD Sports full cancellation email. Same HTML template as Finish Line - delegate.
        Returns FinishLineCancellationData (same structure).
        """
        from app.services.finishline_parser import FinishLineEmailParser
        return FinishLineEmailParser().parse_cancellation_email(email_data)

    def parse_email(self, email_data: EmailData) -> Optional[JDSportsOrderData]:
        """
        Parse JD Sports order confirmation email.
        
        Args:
            email_data: EmailData object containing email information
        
        Returns:
            JDSportsOrderData object or None if parsing fails
        """
        try:
            html_content = email_data.html_content
            
            if not html_content:
                logger.error("No HTML content in JD Sports email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extract order number from email content
            order_number = self._extract_order_number(soup, email_data.subject)
            if not order_number:
                logger.error("Failed to extract order number from JD Sports email")
                return None
            
            logger.info(f"Extracted JD Sports order number: {order_number}")
            
            # Extract items using BeautifulSoup
            items = self._extract_items(soup)
            
            if not items:
                logger.error("Failed to extract any items from JD Sports email")
                return None
            
            logger.info(f"Successfully extracted {len(items)} items from JD Sports order {order_number}")
            for item in items:
                logger.debug(f"  - {item}")
            
            # Extract shipping address
            shipping_address = self._extract_shipping_address(soup)
            if shipping_address:
                logger.info(f"Extracted shipping address: {shipping_address}")
            
            return JDSportsOrderData(order_number=order_number, items=items, shipping_address=shipping_address)
        
        except Exception as e:
            logger.error(f"Error parsing JD Sports email: {e}", exc_info=True)
            return None

    def _extract_order_number(self, soup: BeautifulSoup, subject: str) -> Optional[str]:
        """
        Extract order number from JD Sports email.
        
        The order number can be found in:
        1. Subject line: "Thank you for your order: #60011000606"
        2. Email body: "Order Number: 5571219432"
        
        Args:
            soup: BeautifulSoup object of email HTML
            subject: Email subject string
        
        Returns:
            Order number or None
        """
        try:
            # Method 1: Try to extract from subject
            # Pattern: "Thank you for your order: #60011000606"
            subject_match = re.search(r'#(\d+)', subject)
            if subject_match:
                order_number = subject_match.group(1)
                logger.debug(f"Found JD Sports order number in subject: {order_number}")
                return order_number
            
            # Method 2: Extract from email body
            # Pattern: "Order Number: 5571219432" or similar
            text = soup.get_text()
            
            # Look for "Order Number:" followed by digits
            body_match = re.search(r'Order\s+Number[:\s]+(\d+)', text, re.IGNORECASE)
            if body_match:
                order_number = body_match.group(1)
                logger.debug(f"Found JD Sports order number in body: {order_number}")
                return order_number
            
            # Method 3: Look for standalone number in link
            # The order number appears as a clickable link in the email
            links = soup.find_all('a')
            for link in links:
                link_text = link.get_text(strip=True)
                if link_text and link_text.isdigit() and len(link_text) >= 8:
                    logger.debug(f"Found JD Sports order number in link: {link_text}")
                    return link_text
            
            logger.warning("Order number not found in JD Sports email")
            return None
        
        except Exception as e:
            logger.error(f"Error extracting JD Sports order number: {e}")
            return None

    def _extract_items(self, soup: BeautifulSoup) -> List[JDSportsOrderItem]:
        """
        Extract order items from JD Sports email.
        
        JD Sports email structure:
        - Product image URL: media.jdsports.com/s/jdsports/JH6365_100
        - Product name in <td> with font styling
        - Size in <td>: "Size: 7"
        - Quantity in <td>: "Quantity: 4"
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            List of JDSportsOrderItem objects
        """
        items = []
        processed_products = set()  # Track processed products to avoid duplicates
        
        try:
            # Find all product images from JD Sports CDN
            product_images = soup.find_all('img', src=re.compile(r'media\.jdsports\.com/s/jdsports/'))
            logger.debug(f"Found {len(product_images)} potential product images")
            
            for img in product_images:
                try:
                    src = img.get('src', '')
                    
                    # Skip logos and other non-product images
                    if 'logo' in src.lower() or 'icon' in src.lower():
                        continue
                    
                    # Extract product details from this image's container
                    product_details = self._extract_jdsports_product_details(img)
                    
                    if product_details:
                        unique_id = product_details.get('unique_id')
                        size = product_details.get('size')
                        quantity = product_details.get('quantity', 1)
                        product_name = product_details.get('product_name', 'Unknown Product')
                        
                        # Create a unique key to avoid duplicates
                        product_key = f"{unique_id}_{size}"
                        
                        if product_key in processed_products:
                            logger.debug(f"Skipping duplicate: {product_key}")
                            continue
                        
                        # Validate and create item
                        if unique_id and size:
                            items.append(JDSportsOrderItem(
                                unique_id=unique_id,
                                size=self._clean_size(size),
                                quantity=quantity,
                                product_name=product_name
                            ))
                            processed_products.add(product_key)
                            logger.info(
                                f"Extracted JD Sports item: {product_name} | "
                                f"unique_id={unique_id}, Size={size}, Qty={quantity}"
                            )
                        else:
                            logger.warning(
                                f"Invalid or missing data: "
                                f"unique_id={unique_id}, size={size}, product_name={product_name}"
                            )
                
                except Exception as e:
                    logger.error(f"Error processing JD Sports product image: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error extracting JD Sports items: {e}", exc_info=True)
        
        # Log items with ID, size, and quantity
        if items:
            items_summary = [f"(ID: {item.unique_id}, Size: {item.size}, Qty: {item.quantity})" for item in items]
            logger.info(f"[JD Sports] Extracted {len(items)} items: {', '.join(items_summary)}")
        return items

    def _extract_jdsports_product_details(self, img) -> Optional[dict]:
        """
        Extract product details from a JD Sports product image container.
        
        JD Sports structure:
        - Product image URL: media.jdsports.com/s/jdsports/JH6365_100?$default$&hei=170&wid=170
        - Product name in sibling <td> with font styling
        - Size: "Size: 7"
        - Quantity: "Quantity: 4"
        
        Returns:
            Dictionary with unique_id, size, quantity, product_name or None
        """
        try:
            details = {}
            
            # Extract SKU from image URL
            # Pattern: media.jdsports.com/s/jdsports/JH6365_100?$default$
            src = img.get('src', '')
            sku_match = re.search(r'/jdsports/([A-Z0-9_]+)', src)
            if sku_match:
                sku = sku_match.group(1).split('?')[0]  # Remove query parameters
                details['unique_id'] = sku
                logger.debug(f"Found SKU from image URL: {sku}")
            else:
                logger.warning(f"Could not extract SKU from image URL: {src}")
                return None
            
            # Find the parent row containing this image
            parent_row = img.find_parent('tr')
            if not parent_row:
                logger.warning("Could not find parent row for product image")
                return None
            
            # Find all <td> elements in this row
            all_tds = parent_row.find_all('td')
            
            # Extract product name - look for bold text with font styling
            for td in all_tds:
                style = td.get('style', '')
                if 'font-weight:bold' in style or 'font-weight: bold' in style:
                    product_name = td.get_text(strip=True)
                    if product_name and len(product_name) > 10 and 'size' not in product_name.lower():
                        # Clean up extra whitespace
                        product_name = re.sub(r'\s+', ' ', product_name).strip()
                        details['product_name'] = product_name
                        logger.debug(f"Found product name: {product_name}")
                        break
            
            # Extract size and quantity from text
            row_text = parent_row.get_text()
            
            # Extract size - pattern: "Size: 7"
            size_match = re.search(r'Size:\s*([0-9.]+)', row_text, re.IGNORECASE)
            if size_match:
                size = size_match.group(1)
                details['size'] = size
                logger.debug(f"Found size: {size}")
            
            # Extract quantity - pattern: "Quantity: 4"
            quantity_match = re.search(r'Quantity:\s*(\d+)', row_text, re.IGNORECASE)
            if quantity_match:
                quantity = int(quantity_match.group(1))
                details['quantity'] = quantity
                logger.debug(f"Found quantity: {quantity}")
            else:
                details['quantity'] = 1  # Default to 1 if not found
            
            # Return only if we have the essential fields
            if details.get('unique_id') and details.get('size'):
                logger.info(f"Successfully extracted JD Sports product: {details}")
                return details
            
            logger.warning(f"Missing essential fields: unique_id={details.get('unique_id')}, size={details.get('size')}")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting JD Sports product details: {e}", exc_info=True)
            return None

    def _is_valid_size(self, size: str) -> bool:
        """Validate if size is valid"""
        if not size:
            return False
        # Accept numeric sizes (10, 10.5), letter sizes (M, XL), or special sizes (OS)
        return bool(
            re.match(r'^\d+(\.\d+)?$', size) or  # Numeric: 10, 10.5
            re.match(r'^[A-Z]{1,3}$', size.upper()) or  # Letter: M, XL
            size.upper() == 'OS'  # One Size
        )

    def _clean_size(self, size: str) -> str:
        """Clean size string"""
        size = size.strip()
        # Remove .0 from numeric sizes
        if size.endswith('.0'):
            return size[:-2]
        return size
    
    def _extract_shipping_address(self, soup: BeautifulSoup) -> str:
        """
        Extract shipping address from email and normalize it.
        
        JD Sports email structure:
        - "Shipping to:" header
        - Street address (e.g., "595 Lloyd lane")
        - Suite/Unit (e.g., "Ste D")
        - City, State ZIP
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            Normalized shipping address or empty string
        """
        try:
            text = soup.get_text()
            
            # Method 1: Look for "Shipping to:" section
            shipping_match = re.search(
                r'Shipping\s+to:\s*(.*?)(?:Payment|Billing|Order\s+Summary|$)',
                text,
                re.IGNORECASE | re.DOTALL
            )
            
            if shipping_match:
                address_section = shipping_match.group(1).strip()
                # Split into lines
                lines = [line.strip() for line in address_section.split('\n') if line.strip()]
                
                # Look for street address pattern (number + street name)
                for line in lines:
                    # Skip commas at the beginning
                    line = line.lstrip(',').strip()
                    # Check if line starts with a number (likely street address)
                    if re.match(r'^\d+', line):
                        # This is likely the street address
                        # Extract just the street address part (before city/state/zip)
                        parts = line.split(',')
                        street_line = parts[0].strip() if parts else line.strip()
                        
                        normalized = normalize_shipping_address(street_line)
                        if normalized:
                            logger.debug(f"Extracted JD Sports shipping address: {line} -> {street_line} -> {normalized}")
                            return normalized
            
            # Method 2: Direct pattern matching for known addresses
            lloyd_match = re.search(r'(595\s+Lloyd\s+[Ll]ane?)', text, re.IGNORECASE)
            if lloyd_match:
                street_line = lloyd_match.group(1).strip()
                normalized = normalize_shipping_address(street_line)
                if normalized:
                    logger.debug(f"Extracted JD Sports shipping address (pattern): {street_line} -> {normalized}")
                    return normalized
            
            return ""
        
        except Exception as e:
            logger.error(f"Error extracting shipping address: {e}")
            return ""
