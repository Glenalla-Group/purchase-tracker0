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

logger = logging.getLogger(__name__)


class ShopSimonOrderItem(BaseModel):
    unique_id: str = Field(..., description="Unique identifier for the product (e.g., SKU, style code)")
    size: str = Field(..., description="Size of the product")
    quantity: int = Field(..., description="Quantity of the product")
    product_name: Optional[str] = Field(None, description="Name of the product")


class ShopSimonOrderData(BaseModel):
    order_number: str = Field(..., description="The order number")
    items: List[ShopSimonOrderItem] = Field(..., description="List of items in the order")
    items_count: int = Field(0, description="Total number of items in the order")

    def __init__(self, **data):
        super().__init__(**data)
        self.items_count = len(self.items)


class ShopSimonEmailParser:
    SHOPSIMON_FROM_EMAIL = "onlinesupport@shopsimon.com"
    SUBJECT_ORDER_PATTERN = "your shopsimon order is confirmed"

    def is_shopsimon_email(self, email_data: EmailData) -> bool:
        """Check if email is from ShopSimon"""
        return self.SHOPSIMON_FROM_EMAIL in email_data.sender.lower()

    def is_order_confirmation_email(self, email_data: EmailData) -> bool:
        """Check if email is an order confirmation"""
        return self.SUBJECT_ORDER_PATTERN in email_data.subject.lower()

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
            
            return ShopSimonOrderData(order_number=order_number, items=items)
        
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
        
        logger.info(f"ShopSimon extracted {len(items)} items total")
        return items

    def _find_product_rows(self, soup: BeautifulSoup) -> List:
        """
        Find product rows in the email HTML.
        
        ShopSimon specific structure:
        - Products are in <tr class="order-list__item">
        - Each row contains product image, title, and price
        
        Returns:
            List of BeautifulSoup elements containing product information
        """
        product_rows = []
        
        # Look for ShopSimon specific product rows
        # Pattern: <tr class="order-list__item">
        product_rows = soup.find_all('tr', class_='order-list__item')
        
        if product_rows:
            logger.debug(f"Found {len(product_rows)} product rows using class 'order-list__item'")
            return product_rows
        
        # Fallback: Look for rows containing order-list__item-title
        rows_with_titles = soup.find_all('span', class_='order-list__item-title')
        for title_span in rows_with_titles:
            parent_row = title_span.find_parent('tr')
            if parent_row and parent_row not in product_rows:
                product_rows.append(parent_row)
        
        logger.debug(f"Found {len(product_rows)} potential product containers")
        return product_rows

    def _extract_shopsimon_product_details(self, element) -> Optional[dict]:
        """
        Extract product details from a ShopSimon product element.
        
        ShopSimon HTML structure:
        - Product title: <span class="order-list__item-title">Men's adidas Adilette 22 Slides - US 7 / crystal white / crystal white / core bla× 3</span>
        - Format: "Product Name - US Size / color / color / color× Multiplier"
        - Size: Extracted from "US 7" part
        - Quantity: Always 1 (ignore × multiplier)
        - Unique ID: Generated from product name + multiplier number
          Example: "Men's adidas Adilette 22 Slides" + "× 3" -> "mens-adidas-adilette-22-slides-3"
        
        Returns:
            Dictionary with unique_id, size, quantity, product_name or None
        """
        try:
            details = {
                'quantity': 1  # Always 1 for ShopSimon
            }
            
            # Find product title span
            title_span = element.find('span', class_='order-list__item-title')
            if not title_span:
                logger.warning("Product title span not found")
                return None
            
            full_title = title_span.get_text(strip=True)
            logger.debug(f"Found full title: {full_title}")
            
            # Parse the title format: "Product Name - US Size / colors× Multiplier"
            # Example: "Men's adidas Adilette 22 Slides - US 7 / crystal white / crystal white / core bla× 3"
            
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
            
            # Extract multiplier number from "× 3" pattern
            multiplier_match = re.search(r'×\s*(\d+)', full_title)
            multiplier = ''
            if multiplier_match:
                multiplier = multiplier_match.group(1)
                logger.debug(f"Extracted multiplier: {multiplier}")
            
            # Generate unique_id from product name + multiplier
            # Format: "mens-adidas-adilette-22-slides-3"
            if details.get('product_name'):
                # Convert product name to slug format
                unique_id = details['product_name'].lower()
                # Remove special characters and replace spaces with hyphens
                unique_id = re.sub(r'[^\w\s-]', '', unique_id)
                unique_id = re.sub(r'[-\s]+', '-', unique_id)
                unique_id = unique_id.strip('-')
                
                # Append multiplier if found
                if multiplier:
                    unique_id = f"{unique_id}-{multiplier}"
                
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

