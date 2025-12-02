"""
Finish Line Email Parser
Parses order confirmation emails from Finish Line using BeautifulSoup

Email Format:
- From: finishline@notifications.finishline.com
- Subject: "Your Order is Official!"
- Order Number: Extracted from <a class="link"> tag in email body

HTML Structure:
- Products are in separate tables with product images
- Product image URL contains SKU: media.finishline.com/s/finishline/DM4044_108
- Product name in <td class="orderDetails bold">
- Size in <td class="orderDetails"> containing "Size: 12.0"
- Quantity in <td class="orderDetails"> containing "Quantity: 2"

Parsing Method:
- Uses BeautifulSoup to find and parse HTML elements
- Finds <td> tags with specific classes
- Extracts text by splitting on colon separator
- No regex pattern matching on text content

Example Extraction:
- Order: 60010107385
- Product: Men's Nike Cortez Casual Shoes
- SKU: DM4044_108
- Size: 12.0 → 12 (cleaned)
- Quantity: 2
"""

import re
import logging
from typing import List, Optional
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from app.models.email import EmailData

logger = logging.getLogger(__name__)


class FinishLineOrderItem(BaseModel):
    unique_id: str = Field(..., description="Unique identifier for the product (e.g., SKU, style code)")
    size: str = Field(..., description="Size of the product")
    quantity: int = Field(..., description="Quantity of the product")
    product_name: Optional[str] = Field(None, description="Name of the product")


class FinishLineOrderData(BaseModel):
    order_number: str = Field(..., description="The order number")
    items: List[FinishLineOrderItem] = Field(..., description="List of items in the order")
    items_count: int = Field(0, description="Total number of items in the order")

    def __init__(self, **data):
        super().__init__(**data)
        self.items_count = len(self.items)


class FinishLineEmailParser:
    FINISHLINE_FROM_EMAIL = "finishline@notifications.finishline.com"
    SUBJECT_ORDER_PATTERN = "your order is official!"

    def is_finishline_email(self, email_data: EmailData) -> bool:
        """Check if email is from Finish Line"""
        return self.FINISHLINE_FROM_EMAIL in email_data.sender.lower()

    def is_order_confirmation_email(self, email_data: EmailData) -> bool:
        """Check if email is an order confirmation"""
        return self.SUBJECT_ORDER_PATTERN in email_data.subject.lower()

    def parse_email(self, email_data: EmailData) -> Optional[FinishLineOrderData]:
        """
        Parse Finish Line order confirmation email.
        
        Args:
            email_data: EmailData object containing email information
        
        Returns:
            FinishLineOrderData object or None if parsing fails
        """
        try:
            html_content = email_data.html_content
            
            if not html_content:
                logger.error("No HTML content in Finish Line email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extract order number from email content
            order_number = self._extract_order_number(soup, email_data.subject)
            if not order_number:
                logger.error("Failed to extract order number from Finish Line email")
                return None
            
            logger.info(f"Extracted Finish Line order number: {order_number}")
            
            # Extract items using BeautifulSoup
            items = self._extract_items(soup)
            
            if not items:
                logger.error("Failed to extract any items from Finish Line email")
                return None
            
            logger.info(f"Successfully extracted {len(items)} items from Finish Line order {order_number}")
            for item in items:
                logger.debug(f"  - {item}")
            
            return FinishLineOrderData(order_number=order_number, items=items)
        
        except Exception as e:
            logger.error(f"Error parsing Finish Line email: {e}", exc_info=True)
            return None

    def _extract_order_number(self, soup: BeautifulSoup, subject: str) -> Optional[str]:
        """
        Extract order number from Finish Line email.
        
        Format: Order Number: 60010107385
        Located in the email body with link
        
        Args:
            soup: BeautifulSoup object of email HTML
            subject: Email subject string
        
        Returns:
            Order number or None
        """
        try:
            # Look for the specific pattern in Finish Line emails
            # Pattern: "Order Number: <a>60010107385</a>"
            order_number_tag = soup.find('a', class_='link')
            if order_number_tag:
                order_number = order_number_tag.get_text(strip=True)
                if order_number and order_number.isdigit() and len(order_number) >= 8:
                    logger.debug(f"Found Finish Line order number from link: {order_number}")
                    return order_number
            
            # Fallback: Search in text
            email_text = soup.get_text()
            
            # Pattern 1: "Order Number: 60010107385"
            match = re.search(r'Order\s+Number\s*:?\s*(\d{8,})', email_text, re.IGNORECASE)
            if match:
                order_number = match.group(1).strip()
                logger.debug(f"Found Finish Line order number: {order_number}")
                return order_number
            
            # Pattern 2: "Order #: 123456789"
            match = re.search(r'Order\s*#\s*:?\s*([A-Z0-9-]+)', email_text, re.IGNORECASE)
            if match:
                order_number = match.group(1).strip()
                logger.debug(f"Found Finish Line order number (alt): {order_number}")
                return order_number
            
            logger.warning("Order number not found in Finish Line email")
            return None
        
        except Exception as e:
            logger.error(f"Error extracting Finish Line order number: {e}")
            return None

    def _extract_items(self, soup: BeautifulSoup) -> List[FinishLineOrderItem]:
        """
        Extract order items from Finish Line email.
        
        Finish Line email structure will vary, but typically includes:
        - Product name
        - SKU/Style code
        - Size
        - Quantity
        - Product images
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            List of FinishLineOrderItem objects
        """
        items = []
        processed_products = set()  # Track processed products to avoid duplicates
        
        try:
            # Strategy 1: Look for product tables or rows
            # Common in retail confirmation emails
            product_rows = self._find_product_rows(soup)
            
            logger.info(f"Found {len(product_rows)} potential product rows")
            
            for row in product_rows:
                try:
                    # Extract product details from this row
                    product_details = self._extract_finishline_product_details(row)
                    
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
                            items.append(FinishLineOrderItem(
                                unique_id=unique_id,
                                size=self._clean_size(size),
                                quantity=quantity,
                                product_name=product_name
                            ))
                            processed_products.add(product_key)
                            logger.info(
                                f"Extracted Finish Line item: {product_name} | "
                                f"unique_id={unique_id}, Size={size}, Qty={quantity}"
                            )
                        else:
                            logger.warning(
                                f"Invalid or missing data: "
                                f"unique_id={unique_id}, size={size}, product_name={product_name}"
                            )
                
                except Exception as e:
                    logger.error(f"Error processing Finish Line product row: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error extracting Finish Line items: {e}", exc_info=True)
        
        logger.info(f"Finish Line extracted {len(items)} items total")
        return items

    def _find_product_rows(self, soup: BeautifulSoup) -> List:
        """
        Find product rows in the email HTML.
        
        Finish Line structure:
        - Product images with URL pattern: media.finishline.com/s/finishline/{SKU}
        - Product details in td with class "orderDetails"
        
        Returns:
            List of BeautifulSoup elements containing product information
        """
        product_rows = []
        
        # Look for product images from Finish Line CDN
        img_tags = soup.find_all('img')
        for img in img_tags:
            src = img.get('src', '')
            
            # Check if this is a Finish Line product image
            if 'media.finishline.com/s/finishline/' in src and '?$default$' in src:
                logger.debug(f"Found Finish Line product image: {src}")
                # Find the parent table that contains both image and details
                parent_table = img.find_parent('table')
                if parent_table and parent_table not in product_rows:
                    product_rows.append(parent_table)
        
        return product_rows

    def _extract_finishline_product_details(self, element) -> Optional[dict]:
        """
        Extract product details from a Finish Line product element using BeautifulSoup.
        
        HTML Structure:
        - Product image URL contains SKU: media.finishline.com/s/finishline/DM4044_108
        - Product name in <td> with class "orderDetails bold"
        - Size in <td> with class "orderDetails" containing "Size: 12.0"
        - Quantity in <td> with class "orderDetails" containing "Quantity: 2"
        
        Extraction Method:
        - Uses BeautifulSoup to find specific <td> elements
        - Parses text by splitting on colon (":")
        - No regex pattern matching on text
        
        Returns:
            Dictionary with unique_id, size, quantity, product_name or None
        """
        try:
            details = {}
            
            # Extract SKU from product image URL
            img_tag = element.find('img', src=re.compile(r'media\.finishline\.com/s/finishline/'))
            if img_tag:
                src = img_tag.get('src', '')
                # Extract SKU from URL: media.finishline.com/s/finishline/DM4044_108?$default$
                sku_match = re.search(r'/finishline/([A-Z0-9_-]+)\?', src)
                if sku_match:
                    sku = sku_match.group(1)
                    details['unique_id'] = sku
                    logger.debug(f"Found SKU from image URL: {sku}")
            
            # Extract product name - look for bold orderDetails
            product_name_tag = element.find('td', class_=re.compile(r'orderDetails.*bold'))
            if product_name_tag:
                product_name = product_name_tag.get_text(strip=True)
                if product_name:
                    details['product_name'] = product_name
                    logger.debug(f"Found product name: {product_name}")
            
            # Find all <td> tags with class "orderDetails" to extract size and quantity
            order_detail_tds = element.find_all('td', class_=re.compile(r'orderDetails'))
            
            for td in order_detail_tds:
                td_text = td.get_text(strip=True)
                
                # Extract size - Format: "Size: 12.0"
                if td_text.lower().startswith('size:'):
                    size = td_text.split(':', 1)[1].strip()
                    if size:
                        details['size'] = size
                        logger.debug(f"Found size: {size}")
                
                # Extract quantity - Format: "Quantity: 2"
                elif td_text.lower().startswith('quantity:'):
                    quantity_str = td_text.split(':', 1)[1].strip()
                    try:
                        quantity = int(quantity_str)
                        details['quantity'] = quantity
                        logger.debug(f"Found quantity: {quantity}")
                    except ValueError:
                        logger.warning(f"Could not parse quantity: {quantity_str}")
            
            # Default quantity to 1 if not found
            if 'quantity' not in details:
                details['quantity'] = 1
                logger.debug("Quantity not found, defaulting to 1")
            
            # Return only if we have the essential fields
            if details.get('unique_id') and details.get('size'):
                logger.info(f"Successfully extracted Finish Line product: {details}")
                return details
            
            logger.warning(f"Missing essential fields: unique_id={details.get('unique_id')}, size={details.get('size')}")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting Finish Line product details: {e}", exc_info=True)
            return None

    def _is_valid_size(self, size: str) -> bool:
        """Validate if size is valid"""
        if not size:
            return False
        # Accept numeric sizes (10, 10.5), youth sizes (4.5Y), letter sizes (M, XL), or special sizes (OS)
        return bool(
            re.match(r'^\d+(\.\d+)?Y?$', size) or  # Numeric: 10, 10.5, 4.5Y
            re.match(r'^[A-Z]{1,3}$', size.upper()) or  # Letter: M, XL, XXL
            size.upper() == 'OS'  # One Size
        )

    def _clean_size(self, size: str) -> str:
        """Clean size string"""
        size = size.strip()
        # Remove .0 from numeric sizes
        if size.endswith('.0'):
            return size[:-2]
        return size

