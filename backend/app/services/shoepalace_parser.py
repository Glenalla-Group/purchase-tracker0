"""
Shoe Palace Email Parser
Parses order confirmation emails from Shoe Palace
"""

import re
import logging
from typing import List, Optional
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from app.models.email import EmailData

logger = logging.getLogger(__name__)


class ShoepalaceOrderItem(BaseModel):
    unique_id: str = Field(..., description="Unique identifier for the product (e.g., SKU, style code)")
    size: str = Field(..., description="Size of the product")
    quantity: int = Field(..., description="Quantity of the product")
    product_name: Optional[str] = Field(None, description="Name of the product")


class ShoepalaceOrderData(BaseModel):
    order_number: str = Field(..., description="The order number")
    items: List[ShoepalaceOrderItem] = Field(..., description="List of items in the order")
    items_count: int = Field(0, description="Total number of items in the order")

    def __init__(self, **data):
        super().__init__(**data)
        self.items_count = len(self.items)


class ShoepalaceEmailParser:
    SHOEPALACE_FROM_EMAIL = "store+8523376@t.shopifyemail.com"
    SUBJECT_ORDER_PATTERN = "confirmed"

    def is_shoepalace_email(self, email_data: EmailData) -> bool:
        """Check if email is from Shoe Palace"""
        return self.SHOEPALACE_FROM_EMAIL in email_data.sender

    def is_order_confirmation_email(self, email_data: EmailData) -> bool:
        """Check if email is an order confirmation"""
        return self.SUBJECT_ORDER_PATTERN in email_data.subject.lower()

    def parse_email(self, email_data: EmailData) -> Optional[ShoepalaceOrderData]:
        """
        Parse Shoe Palace order confirmation email.
        
        Args:
            email_data: EmailData object containing email information
        
        Returns:
            ShoepalaceOrderData object or None if parsing fails
        """
        try:
            html_content = email_data.html_content
            
            if not html_content:
                logger.error("No HTML content in Shoe Palace email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extract order number from subject
            order_number = self._extract_order_number(email_data.subject)
            if not order_number:
                logger.error("Failed to extract order number from Shoe Palace email")
                return None
            
            logger.info(f"Extracted Shoe Palace order number: {order_number}")
            
            # Extract items using BeautifulSoup
            items = self._extract_items(soup)
            
            if not items:
                logger.error("Failed to extract any items from Shoe Palace email")
                return None
            
            logger.info(f"Successfully extracted {len(items)} items from Shoe Palace order {order_number}")
            for item in items:
                logger.debug(f"  - {item}")
            
            return ShoepalaceOrderData(order_number=order_number, items=items)
        
        except Exception as e:
            logger.error(f"Error parsing Shoe Palace email: {e}", exc_info=True)
            return None

    def _extract_order_number(self, subject: str) -> Optional[str]:
        """
        Extract order number from Shoe Palace email subject.
        
        Subject format: Order #SP1909467 confirmed
        Extract: 1909467 (without SP prefix)
        
        Args:
            subject: Email subject string
        
        Returns:
            Order number or None
        """
        try:
            # Pattern: Order #SP1909467 confirmed
            match = re.search(r'Order\s+#SP(\d+)', subject, re.IGNORECASE)
            if match:
                order_number = match.group(1)
                logger.debug(f"Found Shoe Palace order number in subject: {order_number}")
                return order_number
            
            logger.warning("Order number not found in Shoe Palace email subject")
            return None
        
        except Exception as e:
            logger.error(f"Error extracting Shoe Palace order number: {e}")
            return None

    def _extract_items(self, soup: BeautifulSoup) -> List[ShoepalaceOrderItem]:
        """
        Extract order items from Shoe Palace email.
        
        Shoe Palace email structure:
        - Product name with color and size: "Air Jordan Collectors Duffle Bag Mens Bag (Black) - OS"
        - Quantity: "Quantitiy : 5"
        - Product image from Shopify CDN (e.g., 28e1a2ea4696547d42555eb7e9f28109_1024x1024.jpg)
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            List of ShoepalaceOrderItem objects
        """
        items = []
        processed_products = set()  # Track processed products to avoid duplicates
        
        try:
            # Find all product images first
            all_imgs = soup.find_all('img')
            
            for img in all_imgs:
                try:
                    src = img.get('src', '')
                    
                    # Check if this is a product image (not logo, banner, or social icons)
                    if not ('cdn.shopify.com/s/files/1/0852/3376/files/' in src):
                        continue
                    
                    # Exclude non-product images
                    if any(x in src.lower() for x in ['logo', 'icon', 'fb.png', 'tw.png', 'in.png', 'pi.png', 'preview-full', 'sp_stacked']):
                        continue
                    
                    # Must be a product image (has hash-like filename with _1024x1024.jpg)
                    if '_1024x1024.jpg' not in src:
                        continue
                    
                    logger.debug(f"Found product image: {src}")
                    
                    # Find the parent row containing this image
                    current = img
                    product_row = None
                    while current:
                        if current.name == 'tr':
                            product_row = current
                            break
                        current = current.parent
                    
                    if not product_row:
                        logger.warning(f"Could not find parent row for image: {src}")
                        continue
                    
                    # Extract product details from this row
                    product_details = self._extract_shoepalace_product_details(product_row)
                    
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
                            items.append(ShoepalaceOrderItem(
                                unique_id=unique_id,
                                size=self._clean_size(size),
                                quantity=quantity,
                                product_name=product_name
                            ))
                            processed_products.add(product_key)
                            logger.info(
                                f"Extracted Shoe Palace item: {product_name} | "
                                f"unique_id={unique_id}, Size={size}, Qty={quantity}"
                            )
                        else:
                            logger.warning(
                                f"Invalid or missing data: "
                                f"unique_id={unique_id}, size={size}, product_name={product_name}"
                            )
                
                except Exception as e:
                    logger.error(f"Error processing Shoe Palace product image: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error extracting Shoe Palace items: {e}", exc_info=True)
        
        logger.info(f"Shoe Palace extracted {len(items)} items total")
        return items

    def _extract_shoepalace_product_details(self, row) -> Optional[dict]:
        """
        Extract product details from a Shoe Palace product row.
        
        Expected format:
        - Product name: "Air Jordan Collectors Duffle Bag Mens Bag (Black) - OS"
        - Quantity: "Quantitiy : 5"
        
        Returns:
            Dictionary with unique_id, size, quantity, product_name or None
        """
        try:
            details = {}
            row_text = row.get_text()
            
            # Find product name - look for td with Josefin Sans font, size 18px
            product_cells = row.find_all('td', style=lambda x: x and 'Josefin Sans' in x and 'font-size: 18px' in x)
            
            if product_cells:
                full_product_name = product_cells[0].get_text(strip=True)
                logger.debug(f"Found product name: {full_product_name}")
                
                # Parse product name to extract size and create unique_id
                # Format: "Product Name (Color) - Size" or "Product Name - Size"
                # Examples:
                # - "Air Jordan Collectors Duffle Bag Mens Bag (Black) - OS"
                # - "Clifton 9 Mens Running Shoes (Black) Final Sale - 10"
                
                size = None
                product_base_name = full_product_name
                
                # Extract size (after the last dash)
                if ' - ' in full_product_name:
                    parts = full_product_name.rsplit(' - ', 1)
                    if len(parts) == 2:
                        product_base_name = parts[0].strip()
                        size = parts[1].strip()
                        logger.debug(f"Extracted size: {size}")
                
                # Remove color from product name for unique_id
                # Format: "Product Name (Color)" -> "Product Name"
                product_name_no_color = product_base_name
                if '(' in product_base_name and ')' in product_base_name:
                    # Remove everything from opening paren to closing paren
                    product_name_no_color = re.sub(r'\s*\([^)]*\)\s*', ' ', product_base_name).strip()
                
                # Remove "Final Sale" text
                product_name_no_color = product_name_no_color.replace(' Final Sale', '').strip()
                
                # Clean up multiple spaces
                product_name_no_color = re.sub(r'\s+', ' ', product_name_no_color).strip()
                
                # Create unique_id: SP-{product_name_without_color}
                unique_id = f"SP-{product_name_no_color}"
                logger.debug(f"Created unique_id: {unique_id}")
                
                details['product_name'] = product_base_name
                details['unique_id'] = unique_id
                details['size'] = size
            
            # Extract quantity - look for "Quantitiy : X" or "Quantity : X"
            quantity_match = re.search(r'Quantit[iy]\s*:\s*(\d+)', row_text, re.IGNORECASE)
            if quantity_match:
                quantity = int(quantity_match.group(1))
                details['quantity'] = quantity
                logger.debug(f"Found quantity: {quantity}")
            else:
                details['quantity'] = 1
            
            # Return only if we have the essential fields
            if details.get('unique_id') and details.get('size'):
                return details
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting Shoe Palace product details: {e}", exc_info=True)
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
