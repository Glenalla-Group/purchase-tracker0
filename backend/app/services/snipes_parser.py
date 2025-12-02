"""
Snipes Email Parser
Parses order confirmation emails from Snipes

Email Format:
- From: no-reply@snipesusa.com
- Subject: "Confirmation of Your SNIPES Order #SNP21092730"
- Order Number: SNP + digits (e.g., SNP21092730)

Product Structure:
- Product Name: From <p> with font-weight: bold
- SKU (unique_id): From pattern "SKU: 15408700018"
- Size: From pattern "Unisex / 4.5Y" (after gender indicator)
- Quantity: From pattern "Quantity: 4"

Example:
  Product: Big Kids' Air Jordan 1 Mid SE
  SKU: 15408700018
  Size: 4.5Y
  Quantity: 4
"""

import re
import logging
from typing import List, Optional
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from app.models.email import EmailData

logger = logging.getLogger(__name__)


class SnipesOrderItem(BaseModel):
    unique_id: str = Field(..., description="Unique identifier for the product (e.g., SKU, style code)")
    size: str = Field(..., description="Size of the product")
    quantity: int = Field(..., description="Quantity of the product")
    product_name: Optional[str] = Field(None, description="Name of the product")


class SnipesOrderData(BaseModel):
    order_number: str = Field(..., description="The order number")
    items: List[SnipesOrderItem] = Field(..., description="List of items in the order")
    items_count: int = Field(0, description="Total number of items in the order")

    def __init__(self, **data):
        super().__init__(**data)
        self.items_count = len(self.items)


class SnipesEmailParser:
    SNIPES_FROM_EMAIL = "no-reply@snipesusa.com"
    SUBJECT_ORDER_PATTERN = "confirmation of your snipes order"

    def is_snipes_email(self, email_data: EmailData) -> bool:
        """Check if email is from Snipes"""
        return self.SNIPES_FROM_EMAIL in email_data.sender.lower()

    def is_order_confirmation_email(self, email_data: EmailData) -> bool:
        """Check if email is an order confirmation"""
        return self.SUBJECT_ORDER_PATTERN in email_data.subject.lower()

    def parse_email(self, email_data: EmailData) -> Optional[SnipesOrderData]:
        """
        Parse Snipes order confirmation email.
        
        Args:
            email_data: EmailData object containing email information
        
        Returns:
            SnipesOrderData object or None if parsing fails
        """
        try:
            html_content = email_data.html_content
            
            if not html_content:
                logger.error("No HTML content in Snipes email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extract order number from subject
            order_number = self._extract_order_number(email_data.subject)
            if not order_number:
                logger.error("Failed to extract order number from Snipes email")
                return None
            
            logger.info(f"Extracted Snipes order number: {order_number}")
            
            # Extract items using BeautifulSoup
            items = self._extract_items(soup)
            
            if not items:
                logger.error("Failed to extract any items from Snipes email")
                return None
            
            logger.info(f"Successfully extracted {len(items)} items from Snipes order {order_number}")
            for item in items:
                logger.debug(f"  - {item}")
            
            return SnipesOrderData(order_number=order_number, items=items)
        
        except Exception as e:
            logger.error(f"Error parsing Snipes email: {e}", exc_info=True)
            return None

    def _extract_order_number(self, subject: str) -> Optional[str]:
        """
        Extract order number from Snipes email subject.
        
        Subject format: Confirmation of Your SNIPES Order #SNP21092730
        Extract: SNP21092730
        
        Args:
            subject: Email subject string
        
        Returns:
            Order number or None
        """
        try:
            # Pattern: Confirmation of Your SNIPES Order #SNP21092730
            match = re.search(r'Order\s+#(SNP\d+)', subject, re.IGNORECASE)
            if match:
                order_number = match.group(1)
                logger.debug(f"Found Snipes order number in subject: {order_number}")
                return order_number
            
            logger.warning("Order number not found in Snipes email subject")
            return None
        
        except Exception as e:
            logger.error(f"Error extracting Snipes order number: {e}")
            return None

    def _extract_items(self, soup: BeautifulSoup) -> List[SnipesOrderItem]:
        """
        Extract order items from Snipes email.
        
        Snipes email structure:
        - Products in table rows with class "tablecell-image-wrapper"
        - Product name in <p> with font-weight: bold
        - Size after gender indicator (e.g., "Unisex / 4.5Y")
        - Quantity: "Quantity: 4"
        - SKU: "SKU: 15408700018"
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            List of SnipesOrderItem objects
        """
        items = []
        processed_products = set()  # Track processed products to avoid duplicates
        
        try:
            # Look for product image cells (tablecell-image-wrapper)
            product_image_cells = soup.find_all('td', class_='tablecell-image-wrapper')
            
            logger.info(f"Found {len(product_image_cells)} product image cells")
            
            for image_cell in product_image_cells:
                try:
                    # Get the parent row
                    parent_row = image_cell.find_parent('tr')
                    if not parent_row:
                        continue
                    
                    # Extract product details from this row
                    product_details = self._extract_snipes_product_details(parent_row)
                    
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
                            items.append(SnipesOrderItem(
                                unique_id=unique_id,
                                size=self._clean_size(size),
                                quantity=quantity,
                                product_name=product_name
                            ))
                            processed_products.add(product_key)
                            logger.info(
                                f"Extracted Snipes item: {product_name} | "
                                f"unique_id={unique_id}, Size={size}, Qty={quantity}"
                            )
                        else:
                            logger.warning(
                                f"Invalid or missing data: "
                                f"unique_id={unique_id}, size={size}, product_name={product_name}"
                            )
                
                except Exception as e:
                    logger.error(f"Error processing Snipes product row: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error extracting Snipes items: {e}", exc_info=True)
        
        logger.info(f"Snipes extracted {len(items)} items total")
        return items

    def _extract_snipes_product_details(self, row) -> Optional[dict]:
        """
        Extract product details from a Snipes product row.
        
        Expected format:
        - Product name in <p> with font-weight: bold
        - Size after gender indicator (e.g., "Unisex / 4.5Y")
        - Quantity: "Quantity: 4"
        - SKU: "SKU: 15408700018"
        
        Returns:
            Dictionary with unique_id, size, quantity, product_name or None
        """
        try:
            details = {}
            row_text = row.get_text()
            
            # Find product name - look for <p> tag with font-weight: bold
            product_name_tag = row.find('p', style=lambda x: x and 'font-weight: bold' in x)
            if product_name_tag:
                product_name = product_name_tag.get_text(strip=True)
                details['product_name'] = product_name
                logger.debug(f"Found product name: {product_name}")
            else:
                logger.warning("Product name not found in Snipes row")
                return None
            
            # Extract SKU - format: "SKU: 15408700018"
            sku_match = re.search(r'SKU:\s*(\d+)', row_text, re.IGNORECASE)
            if sku_match:
                sku = sku_match.group(1).strip()
                details['unique_id'] = sku
                logger.debug(f"Found SKU: {sku}")
            else:
                logger.warning("SKU not found in Snipes row")
                return None
            
            # Extract size - look for pattern after gender/category
            # Format: "Unisex / 4.5Y" or "Men's / 10" etc.
            # The size comes after the slash
            size_match = re.search(r'(?:Unisex|Men\'?s?|Women\'?s?|Kids?\'?s?)\s*/\s*([^\s<]+)', row_text, re.IGNORECASE)
            if size_match:
                size = size_match.group(1).strip()
                details['size'] = size
                logger.debug(f"Found size: {size}")
            else:
                # Try alternative pattern - standalone size after product name
                size_match2 = re.search(r'\b(\d+(?:\.\d+)?Y?|[A-Z]{1,3})\b', row_text)
                if size_match2:
                    size = size_match2.group(1).strip()
                    details['size'] = size
                    logger.debug(f"Found size (alternative): {size}")
                else:
                    logger.warning("Size not found in Snipes row")
                    return None
            
            # Extract quantity - format: "Quantity: 4"
            quantity_match = re.search(r'Quantity:\s*(\d+)', row_text, re.IGNORECASE)
            if quantity_match:
                quantity = int(quantity_match.group(1))
                details['quantity'] = quantity
                logger.debug(f"Found quantity: {quantity}")
            else:
                # Default to 1 if not found
                details['quantity'] = 1
                logger.debug("Quantity not found, defaulting to 1")
            
            # Return only if we have the essential fields
            if details.get('unique_id') and details.get('size') and details.get('product_name'):
                return details
            
            logger.warning(f"Missing essential fields: {details}")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting Snipes product details: {e}", exc_info=True)
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

