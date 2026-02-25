"""
ShopSimon Email Parser
Parses order confirmation emails from ShopSimon

Email Format:
- From: onlinesupport@shopsimon.com
- Subject: "Your ShopSimon Order Is Confirmed - SPO414108538"
- Order Number: SPO + digits (e.g., SPO414108538)

Product Structure:
- Product Name: To be determined from actual email
- SKU/Style Code (unique_id): To be determined from actual email
- Size: To be determined from actual email
- Quantity: To be determined from actual email

Note: This parser will need to be refined once actual email samples are available
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


class ShopSimonOrderItem(BaseModel):
    unique_id: str = Field(..., description="Unique identifier for the product (e.g., SKU, style code)")
    size: str = Field(..., description="Size of the product")
    quantity: int = Field(..., description="Quantity of the product")
    product_name: Optional[str] = Field(None, description="Name of the product")
    
    def __repr__(self):
        if self.product_name and len(self.product_name) > 50:
            product_display = self.product_name[:50] + "..."
        else:
            product_display = self.product_name or "Unknown"
        return f"<ShopSimonOrderItem(unique_id={self.unique_id}, size={self.size}, qty={self.quantity}, product={product_display})>"


class ShopSimonOrderData(BaseModel):
    order_number: str = Field(..., description="The order number")
    items: List[ShopSimonOrderItem] = Field(..., description="List of items in the order")
    items_count: int = Field(0, description="Total number of items in the order")
    shipping_address: str = Field("", description="Normalized shipping address")

    def __init__(self, **data):
        super().__init__(**data)
        self.items_count = len(self.items)


class ShopSimonEmailParser:
    # Email identification - Order Confirmation (Production)
    SHOPSIMON_FROM_EMAIL = "onlinesupport@shopsimon.com"
    SUBJECT_ORDER_PATTERN = r"your shopsimon order is confirmed"
    
    # Email identification - Development (forwarded emails)
    DEV_SHOPSIMON_ORDER_FROM_EMAIL = "glenallagroupc@gmail.com"
    DEV_SUBJECT_ORDER_PATTERN = r"Fwd:\s*your shopsimon order is confirmed"

    def __init__(self):
        """Initialize the ShopSimon email parser."""
        self.settings = get_settings()
    
    @property
    def order_from_email(self) -> str:
        """Get the appropriate from email address based on environment."""
        if self.settings.is_development:
            return self.DEV_SHOPSIMON_ORDER_FROM_EMAIL
        return self.SHOPSIMON_FROM_EMAIL
    
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
            # For Gmail queries, search for "your shopsimon order is confirmed" in forwarded emails
            # The regex pattern will further filter to match "Fwd:\s*your shopsimon order is confirmed"
            return "your shopsimon order is confirmed"
        # For production, use the exact phrase
        return "your shopsimon order is confirmed"

    def is_shopsimon_email(self, email_data: EmailData) -> bool:
        """Check if email is from ShopSimon"""
        sender_lower = email_data.sender.lower()
        
        # In development, check for forwarded emails from dev email address
        if self.settings.is_development:
            if self.DEV_SHOPSIMON_ORDER_FROM_EMAIL.lower() in sender_lower:
                return True
        
        # In production, check for ShopSimon email
        return self.SHOPSIMON_FROM_EMAIL.lower() in sender_lower

    def is_order_confirmation_email(self, email_data: EmailData) -> bool:
        """Check if email is an order confirmation"""
        subject_lower = email_data.subject.lower()
        pattern = self.order_subject_pattern
        
        # Use regex matching for subject pattern
        return bool(re.search(pattern, subject_lower, re.IGNORECASE))

    def parse_email(self, email_data: EmailData) -> Optional[ShopSimonOrderData]:
        """
        Parse ShopSimon order confirmation email.
        
        Args:
            email_data: EmailData object containing email information
        
        Returns:
            ShopSimonOrderData object or None if parsing fails
        """
        try:
            html_content = email_data.html_content
            
            if not html_content:
                logger.error("No HTML content in ShopSimon email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extract order number from subject
            order_number = self._extract_order_number(email_data.subject, soup)
            if not order_number:
                logger.error("Failed to extract order number from ShopSimon email")
                return None
            
            logger.info(f"Extracted ShopSimon order number: {order_number}")
            
            # Extract items using BeautifulSoup
            items = self._extract_items(soup)
            
            if not items:
                logger.error("Failed to extract any items from ShopSimon email")
                return None
            
            logger.info(f"Successfully extracted {len(items)} items from ShopSimon order {order_number}")
            for item in items:
                logger.debug(f"  - {item}")
            
            # Extract shipping address
            shipping_address = self._extract_shipping_address(soup)
            if shipping_address:
                logger.info(f"Extracted shipping address: {shipping_address}")
            
            return ShopSimonOrderData(order_number=order_number, items=items, shipping_address=shipping_address)
        
        except Exception as e:
            logger.error(f"Error parsing ShopSimon email: {e}", exc_info=True)
            return None

    def _extract_order_number(self, subject: str, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract order number from ShopSimon email.
        
        Subject format: Your ShopSimon Order Is Confirmed - SPO414108538
        Extract: SPO414108538
        
        Args:
            subject: Email subject string
            soup: BeautifulSoup object of email HTML (for fallback)
        
        Returns:
            Order number or None
        """
        try:
            # Pattern 1: Extract from subject - "Your ShopSimon Order Is Confirmed - SPO414108538"
            match = re.search(r'-\s*(SPO\d+)', subject, re.IGNORECASE)
            if match:
                order_number = match.group(1)
                logger.debug(f"Found ShopSimon order number in subject: {order_number}")
                return order_number
            
            # Pattern 2: Look for order number in email body
            email_text = soup.get_text()
            match = re.search(r'Order\s+(?:Number|#)\s*:?\s*(SPO\d+)', email_text, re.IGNORECASE)
            if match:
                order_number = match.group(1)
                logger.debug(f"Found ShopSimon order number in body: {order_number}")
                return order_number
            
            # Pattern 3: Generic pattern for SPO followed by numbers
            match = re.search(r'\b(SPO\d{8,})\b', email_text, re.IGNORECASE)
            if match:
                order_number = match.group(1)
                logger.debug(f"Found ShopSimon order number (generic): {order_number}")
                return order_number
            
            logger.warning("Order number not found in ShopSimon email")
            return None
        
        except Exception as e:
            logger.error(f"Error extracting ShopSimon order number: {e}")
            return None

    def _extract_items(self, soup: BeautifulSoup) -> List[ShopSimonOrderItem]:
        """
        Extract order items from ShopSimon email.
        
        ShopSimon email structure (to be refined based on actual emails):
        - Products in table rows or div containers
        - Product name, SKU, size, quantity
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            List of ShopSimonOrderItem objects
        """
        items = []
        processed_products = set()  # Track processed products to avoid duplicates
        
        try:
            # Strategy 1: Look for product tables
            # Most e-commerce emails use tables for product layout
            product_rows = self._find_product_rows(soup)
            
            logger.info(f"Found {len(product_rows)} potential product rows")
            
            for row in product_rows:
                try:
                    # Extract product details from this row
                    product_details = self._extract_shopsimon_product_details(row)
                    
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
                            items.append(ShopSimonOrderItem(
                                unique_id=unique_id,
                                size=self._clean_size(size),
                                quantity=quantity,
                                product_name=product_name
                            ))
                            processed_products.add(product_key)
                            logger.info(
                                f"Extracted ShopSimon item: {product_name} | "
                                f"unique_id={unique_id}, Size={size}, Qty={quantity}"
                            )
                        else:
                            logger.warning(
                                f"Invalid or missing data: "
                                f"unique_id={unique_id}, size={size}, product_name={product_name}"
                            )
                
                except Exception as e:
                    logger.error(f"Error processing ShopSimon product row: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error extracting ShopSimon items: {e}", exc_info=True)
        
        # Log items with ID, size, and quantity (product names come from OA Sourcing table)
        if items:
            items_summary = [f"(ID: {item.unique_id}, Size: {item.size}, Qty: {item.quantity})" for item in items]
            logger.info(f"[ShopSimon] Extracted {len(items)} items: {', '.join(items_summary)}")
        return items

    def _find_product_rows(self, soup: BeautifulSoup) -> List:
        """
        Find product rows in the email HTML.
        
        ShopSimon specific structure:
        - Products are in <span> tags with specific styling:
          style="text-transform:capitalize;font-size:16px;font-weight:600;line-height:1.4;color:#555"
        - Product images from cdn.shopify.com
        
        Returns:
            List of BeautifulSoup elements containing product information
        """
        product_rows = []
        
        # Look for ShopSimon product spans with specific styling
        # Pattern: <span style="...font-size:16px;font-weight:600...">Product Name</span>
        all_spans = soup.find_all('span', style=lambda x: x and 'font-size:16px' in x and 'font-weight:600' in x)
        
        for span in all_spans:
            span_text = span.get_text(strip=True)
            # Check if this looks like a product (contains size pattern)
            if re.search(r'US\s+\d+|×\s*\d+', span_text, re.IGNORECASE):
                # Find the parent row containing this product span
                parent_row = span.find_parent('tr')
                if parent_row and parent_row not in product_rows:
                    product_rows.append(parent_row)
                    logger.debug(f"Found product span: {span_text[:100]}")
        
        logger.debug(f"Found {len(product_rows)} potential product rows")
        return product_rows

    def _extract_shopsimon_product_details(self, element) -> Optional[dict]:
        """
        Extract product details from a ShopSimon product element.
        
        ShopSimon HTML structure:
        - Product title: <span style="...font-size:16px;font-weight:600...">Men's adidas Adilette 22 Slides - US 7 / crystal white / crystal white / core bla× 3</span>
        - Format: "Product Name - US Size / color / color / color× Multiplier"
        - Size: Extracted from "US 7" part
        - Quantity: Extracted from "× 3" multiplier (not always present)
        - Unique ID: Generated from product name
          Example: "Men's adidas Adilette 22 Slides" -> "SS-Mens adidas Adilette 22 Slides"
        - Brand: Extracted from "Brand: adidas" in a div below the product name
        
        Returns:
            Dictionary with unique_id, size, quantity, product_name or None
        """
        try:
            details = {
                'quantity': 1  # Default to 1
            }
            
            # Find product title span (has font-size:16px and font-weight:600)
            title_span = element.find('span', style=lambda x: x and 'font-size:16px' in x and 'font-weight:600' in x)
            if not title_span:
                logger.warning("Product title span not found")
                return None
            
            full_title = title_span.get_text(strip=True)
            # Clean up extra whitespace and newlines
            full_title = re.sub(r'\s+', ' ', full_title).strip()
            logger.debug(f"Found full title: {full_title}")
            
            # Parse the title format: "Product Name - US Size / colors× Multiplier"
            # Example: "Men's adidas Adilette 22 Slides - US 7 / crystal white / crystal white / core bla× 3"
            
            # Extract multiplier/quantity from "× 3" pattern FIRST
            multiplier_match = re.search(r'×\s*(\d+)', full_title)
            if multiplier_match:
                quantity = int(multiplier_match.group(1))
                details['quantity'] = quantity
                logger.debug(f"Extracted quantity: {quantity}")
            
            # Extract product name (everything before " - US")
            product_name_match = re.match(r'^(.+?)\s*-\s*US\s+', full_title)
            if product_name_match:
                product_name = product_name_match.group(1).strip()
                details['product_name'] = product_name
                logger.debug(f"Extracted product name: {product_name}")
            else:
                # Fallback: try to extract product name before first hyphen
                parts = full_title.split(' - ')
                if parts:
                    details['product_name'] = parts[0].strip()
                    logger.debug(f"Extracted product name (fallback): {details['product_name']}")
            
            # Extract size from "US 7" pattern
            size_match = re.search(r'US\s+([0-9.]+(?:\s*[A-Z])?)', full_title, re.IGNORECASE)
            if size_match:
                size = size_match.group(1).strip()
                details['size'] = size
                logger.debug(f"Extracted size: {size}")
            else:
                # Fallback: look for standalone size pattern
                size_match2 = re.search(r'\b([0-9]{1,2}(?:\.[05])?)\b', full_title)
                if size_match2:
                    details['size'] = size_match2.group(1)
                    logger.debug(f"Extracted size (fallback): {details['size']}")
            
            # Try to extract brand from the element
            brand = None
            brand_div = element.find('div', string=lambda x: x and 'Brand:' in x)
            if brand_div:
                brand_text = brand_div.get_text(strip=True)
                brand_match = re.search(r'Brand:\s*(.+)', brand_text)
                if brand_match:
                    brand = brand_match.group(1).strip()
                    logger.debug(f"Extracted brand: {brand}")
            
            # Generate unique_id: SS-{Product Name}
            # Format: "SS-Mens adidas Adilette 22 Slides"
            if details.get('product_name'):
                product_name_clean = details['product_name']
                # Remove possessive apostrophes
                product_name_clean = product_name_clean.replace("'s", "s")
                product_name_clean = product_name_clean.replace("'", "")
                
                unique_id = f"SS-{product_name_clean}"
                details['unique_id'] = unique_id
                logger.debug(f"Generated unique_id: {unique_id}")
            
            # Validate essential fields
            if details.get('unique_id') and details.get('size') and details.get('product_name'):
                logger.info(f"Successfully extracted ShopSimon product: {details}")
                return details
            
            logger.warning(f"Missing essential fields: unique_id={details.get('unique_id')}, size={details.get('size')}, product_name={details.get('product_name')}")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting ShopSimon product details: {e}", exc_info=True)
            return None

    def _is_valid_size(self, size: str) -> bool:
        """Validate if size is valid"""
        if not size:
            return False
        # Accept numeric sizes (10, 10.5), youth sizes (4.5Y), letter sizes (M, XL), or special sizes (OS)
        return bool(
            re.match(r'^\d+(\.\d+)?Y?$', size) or  # Numeric: 10, 10.5, 4.5Y
            re.match(r'^[A-Z]{1,3}$', size.upper()) or  # Letter: M, XL, XXL
            size.upper() == 'OS' or  # One Size
            'one size' in size.lower()
        )

    def _clean_size(self, size: str) -> str:
        """Clean size string"""
        size = size.strip()
        # Remove .0 from numeric sizes
        if size.endswith('.0'):
            return size[:-2]
        # Normalize "One Size" to "OS"
        if 'one size' in size.lower():
            return 'OS'
        return size
    
    def _extract_shipping_address(self, soup: BeautifulSoup) -> str:
        """
        Extract shipping address from email and normalize it.
        
        ShopSimon email structure:
        - <h4>Shipping address</h4>
        - <p>Name<br>Street Address<br>City State ZIP<br>Country</p>
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            Normalized shipping address or empty string
        """
        try:
            # Method 1: Find h4 with "Shipping address" then get the next p tag
            shipping_headers = soup.find_all('h4', string=re.compile(r'Shipping\s+address', re.IGNORECASE))
            
            for header in shipping_headers:
                # Find the next p tag after this h4
                address_p = header.find_next('p')
                if address_p:
                    # Get the text and split by line breaks
                    address_text = address_p.get_text(separator='\n', strip=True)
                    address_lines = [line.strip() for line in address_text.split('\n') if line.strip()]
                    
                    # Skip the name (first line) and look for street address
                    for line in address_lines[1:]:  # Skip first line (name)
                        # Look for street address pattern (starts with number)
                        if re.match(r'^\d+\s+', line):
                            # This looks like a street address
                            normalized = normalize_shipping_address(line)
                            if normalized:
                                logger.debug(f"Extracted ShopSimon shipping address: {line} -> {normalized}")
                                return normalized
            
            # Method 2: Fallback - search text for known address patterns
            text = soup.get_text()
            
            # Look for "595 Lloyd Ln" pattern
            lloyd_match = re.search(r'(595\s+Lloyd\s+Ln)', text, re.IGNORECASE)
            if lloyd_match:
                street_line = lloyd_match.group(1).strip()
                normalized = normalize_shipping_address(street_line)
                if normalized:
                    logger.debug(f"Extracted ShopSimon shipping address (pattern): {street_line} -> {normalized}")
                    return normalized
            
            return ""
        
        except Exception as e:
            logger.error(f"Error extracting shipping address: {e}")
            return ""

