"""
Hibbett Email Parser
Parses order confirmation emails from Hibbett
"""

import re
import logging
from typing import List, Optional
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from app.models.email import EmailData

logger = logging.getLogger(__name__)


class HibbettOrderItem(BaseModel):
    unique_id: str = Field(..., description="Unique identifier for the product (e.g., SKU, style code)")
    size: str = Field(..., description="Size of the product")
    quantity: int = Field(..., description="Quantity of the product")
    product_name: Optional[str] = Field(None, description="Name of the product")


class HibbettOrderData(BaseModel):
    order_number: str = Field(..., description="The order number")
    items: List[HibbettOrderItem] = Field(..., description="List of items in the order")
    items_count: int = Field(0, description="Total number of items in the order")

    def __init__(self, **data):
        super().__init__(**data)
        self.items_count = len(self.items)


class HibbettEmailParser:
    HIBBETT_FROM_EMAIL = "hibbett@email.hibbett.com"
    SUBJECT_ORDER_PATTERN = "Confirmation of your Order"

    def is_hibbett_email(self, email_data: EmailData) -> bool:
        """Check if email is from Hibbett"""
        return self.HIBBETT_FROM_EMAIL in email_data.sender

    def is_order_confirmation_email(self, email_data: EmailData) -> bool:
        """Check if email is an order confirmation"""
        return self.SUBJECT_ORDER_PATTERN in email_data.subject

    def parse_email(self, email_data: EmailData) -> Optional[HibbettOrderData]:
        """
        Parse Hibbett order confirmation email.
        
        Args:
            email_data: EmailData object containing email information
        
        Returns:
            HibbettOrderData object or None if parsing fails
        """
        try:
            html_content = email_data.html_content
            
            if not html_content:
                logger.error("No HTML content in Hibbett email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extract order number
            order_number = self._extract_order_number(soup)
            if not order_number:
                logger.error("Failed to extract order number from Hibbett email")
                return None
            
            logger.info(f"Extracted Hibbett order number: {order_number}")
            
            # Extract items using BeautifulSoup
            items = self._extract_items(soup)
            
            if not items:
                logger.error("Failed to extract any items from Hibbett email")
                return None
            
            logger.info(f"Successfully extracted {len(items)} items from Hibbett order {order_number}")
            for item in items:
                logger.debug(f"  - {item}")
            
            return HibbettOrderData(order_number=order_number, items=items)
        
        except Exception as e:
            logger.error(f"Error parsing Hibbett email: {e}", exc_info=True)
            return None

    def _extract_order_number(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract order number from Hibbett email using BeautifulSoup.
        
        Hibbett structure: Order number is in the subject and also in the email content.
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            Order number or None
        """
        try:
            # Method 1: Look for order number in the email content
            # Hibbett order numbers are typically in format like #0017328512104
            text = soup.get_text()
            order_match = re.search(r'#(\d{13,15})', text)
            if order_match:
                logger.debug(f"Found Hibbett order number in content: {order_match.group(1)}")
                return order_match.group(1)
            
            # Method 2: Look for order number in links or specific elements
            order_links = soup.find_all('a', href=re.compile(r'hibbett\.com'))
            for link in order_links:
                link_text = link.get_text(strip=True)
                # Check if this looks like an order number (13-15 digits)
                if re.match(r'^\d{13,15}$', link_text):
                    logger.debug(f"Found Hibbett order number in link: {link_text}")
                    return link_text
            
            # Method 3: Look for order number in specific text patterns
            order_elements = soup.find_all(text=re.compile(r'Order\s*#?\s*(\d{13,15})'))
            for element in order_elements:
                match = re.search(r'Order\s*#?\s*(\d{13,15})', element)
                if match:
                    logger.debug(f"Found Hibbett order number in text: {match.group(1)}")
                    return match.group(1)
            
            logger.warning("Order number not found in Hibbett email")
            return None
        
        except Exception as e:
            logger.error(f"Error extracting Hibbett order number: {e}")
            return None

    def _extract_items(self, soup: BeautifulSoup) -> List[HibbettOrderItem]:
        """
        Extract order items from Hibbett email.
        
        Hibbett structure analysis:
        - Product images: classic.cdn.media.amplience.net/i/hibbett/G4461_9107_right/
        - Product names: In table cells with product descriptions
        - Sizes: In <b>SIZE</b>: 13 format
        - Quantities: In <b>QTY</b>: 4 format or table cells
        - Unique IDs: From image URLs (G4461 pattern)
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            List of HibbettOrderItem objects
        """
        items = []
        
        try:
            # Find all product images with Hibbett's specific pattern
            product_images = soup.find_all('img', src=re.compile(r'classic\.cdn\.media\.amplience\.net/i/hibbett/'))
            logger.debug(f"Found {len(product_images)} Hibbett product images")
            
            for img in product_images:
                try:
                    # Extract unique ID from image URL
                    img_src = img.get('src', '')
                    unique_id = self._extract_unique_id_from_hibbett_image(img_src)
                    
                    if not unique_id:
                        logger.warning(f"Could not extract unique ID from image: {img_src}")
                        continue
                    
                    # Find the product container (table row containing this image)
                    product_container = self._find_hibbett_product_container(img)
                    if not product_container:
                        logger.warning(f"Could not find product container for image: {img_src}")
                        continue
                    
                    # Extract product details from the container
                    product_name = self._extract_product_name_from_hibbett_container(product_container)
                    size = self._extract_size_from_hibbett_container(product_container)
                    quantity = self._extract_quantity_from_hibbett_container(product_container)
                    
                    # Validate and create item
                    if size and self._is_valid_size(size):
                        items.append(HibbettOrderItem(
                            unique_id=unique_id,
                            size=self._clean_size(size),
                            quantity=quantity,
                            product_name=product_name
                        ))
                        logger.debug(
                            f"Extracted: {product_name} (unique_id={unique_id}), "
                            f"Size: {size}, Qty: {quantity}"
                        )
                    else:
                        logger.warning(
                            f"Invalid or missing data for {unique_id}: "
                            f"size={size}, product_name={product_name}"
                        )
                
                except Exception as e:
                    logger.error(f"Error processing Hibbett product image: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error extracting Hibbett items: {e}", exc_info=True)
        
        logger.info(f"Hibbett Items: {items}")
        return items

    def _extract_unique_id_from_hibbett_image(self, img_src: str) -> Optional[str]:
        """Extract unique ID from Hibbett image URL"""
        try:
            # Hibbett pattern: classic.cdn.media.amplience.net/i/hibbett/G4461_9107_right/
            match = re.search(r'hibbett/([A-Z0-9]+)_', img_src)
            if match:
                return match.group(1)
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting unique ID from Hibbett image: {e}")
            return None

    def _find_hibbett_product_container(self, img) -> Optional[BeautifulSoup]:
        """Find the product container for a given Hibbett image"""
        try:
            # Navigate up to find the table row containing this image
            current = img.parent
            while current:
                if current.name == 'tr':
                    return current
                current = current.parent
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding Hibbett product container: {e}")
            return None

    def _extract_product_name_from_hibbett_container(self, container) -> str:
        """Extract product name from the Hibbett product container"""
        try:
            # Look for product name in table cells with product descriptions
            # The product name is typically in a td with the full product description
            cells = container.find_all('td')
            
            for cell in cells:
                text = cell.get_text(strip=True)
                # Look for product names that are longer and contain typical product keywords
                if (text and len(text) > 10 and 
                    any(keyword in text.lower() for keyword in ['shoe', 'men', 'women', 'nike', 'adidas', 'jordan', 'leather', 'sneaker'])):
                    
                    # Clean up the text by removing extra whitespace and newlines
                    product_name = re.sub(r'\s+', ' ', text).strip()
                    
                    # Try to extract just the main product name (before Product # or other metadata)
                    # Look for patterns like "Product #" or "COLOR:" to split the text
                    if 'Product #' in product_name:
                        product_name = product_name.split('Product #')[0].strip()
                    elif 'COLOR:' in product_name:
                        product_name = product_name.split('COLOR:')[0].strip()
                    
                    return product_name
            
            return "Unknown Product"
            
        except Exception as e:
            logger.error(f"Error extracting Hibbett product name: {e}")
            return "Unknown Product"

    def _extract_size_from_hibbett_container(self, container) -> Optional[str]:
        """Extract size from the Hibbett product container"""
        try:
            # Look for SIZE: pattern in the container
            container_text = container.get_text()
            
            # Pattern: SIZE: 13 or <b>SIZE</b>: 13
            match = re.search(r'SIZE[:\s]+(\d+(?:\.\d+)?)', container_text)
            if match:
                return match.group(1)
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting Hibbett size: {e}")
            return None

    def _extract_quantity_from_hibbett_container(self, container) -> int:
        """Extract quantity from the Hibbett product container"""
        try:
            container_text = container.get_text()
            
            # Pattern: QTY: 4 or <b>QTY</b>: 4
            match = re.search(r'QTY[:\s]+(\d+)', container_text)
            if match:
                return int(match.group(1))
            
            # Default to 1 if not specified
            return 1
            
        except Exception as e:
            logger.error(f"Error extracting Hibbett quantity: {e}")
            return 1


    def _is_valid_size(self, size: str) -> bool:
        """Validate if size is valid"""
        return bool(re.match(r'^\d+(\.\d+)?$', size))

    def _is_valid_quantity(self, quantity: str) -> bool:
        """Validate if quantity is valid"""
        return quantity.isdigit() and int(quantity) > 0

    def _clean_size(self, size: str) -> str:
        """Clean size string"""
        return size.replace('.0', '') if size.endswith('.0') else size
