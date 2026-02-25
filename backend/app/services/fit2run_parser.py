"""
Fit2Run Email Parser
Parses order confirmation emails from Fit2Run using BeautifulSoup

Email Format:
- From: support@fit2run.com (production)
- From: glenallagroupc@gmail.com (dev - forwarded emails)
- Subject: "Thank you for your purchase!" or similar
- Order Number: Extract from HTML (e.g., "2000814919")

HTML Structure:
- Products are listed in tables
- Each product has:
  - Product image: <img src="https://cdn.shopify.com/.../files/110435_014_L_Revel_7_compact_cropped.png">
  - Product name: <span>Brooks Revel 7 × 1</span>
  - Size/Variant: <span>Primer - Blackened Pearl / D / 11.5</span>
  - Quantity: Extracted from product name (× 1, × 3, etc.)

Unique ID Extraction:
- Format: {product_id}_{variant_id} (e.g., "110435_014")
- Extract from product image URL: https://cdn.shopify.com/.../files/{product_id}_{variant_id}_...
- Pattern: files/(\d+)_(\d+)_
- Example: "110435_014_L_Revel_7_compact_cropped.png" -> "110435_014"
- Note: May need to handle Gmail proxy URLs that contain actual URL after #
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


class Fit2RunOrderItem(BaseModel):
    unique_id: str = Field(..., description="Unique identifier for the product (e.g., 110435_014)")
    size: str = Field(..., description="Size of the product")
    quantity: int = Field(..., description="Quantity of the product")
    product_name: Optional[str] = Field(None, description="Name of the product")
    
    def __repr__(self):
        if self.product_name and len(self.product_name) > 50:
            product_display = self.product_name[:50] + "..."
        else:
            product_display = self.product_name or "Unknown"
        return f"<Fit2RunOrderItem(unique_id={self.unique_id}, size={self.size}, qty={self.quantity}, product={product_display})>"


class Fit2RunOrderData(BaseModel):
    order_number: str = Field(..., description="The order number")
    items: List[Fit2RunOrderItem] = Field(..., description="List of items in the order")
    items_count: int = Field(0, description="Total number of items in the order")
    shipping_address: str = Field("", description="Normalized shipping address")

    def __init__(self, **data):
        super().__init__(**data)
        self.items_count = len(self.items)


class Fit2RunEmailParser:
    # Email identification - Order Confirmation (Production)
    FIT2RUN_FROM_EMAIL = "support@fit2run.com"
    SUBJECT_ORDER_PATTERN = r"thank\s+you\s+for\s+your\s+purchase"
    
    # Email identification - Development (forwarded emails)
    DEV_FIT2RUN_ORDER_FROM_EMAIL = "glenallagroupc@gmail.com"
    DEV_SUBJECT_ORDER_PATTERN = r"(?:Fwd:\s*)?(?:thank\s+you\s+for\s+your\s+purchase|order|fit2run)"

    def __init__(self):
        """Initialize the Fit2Run email parser."""
        self.settings = get_settings()
    
    @property
    def order_from_email(self) -> str:
        """Get the appropriate from email address based on environment."""
        if self.settings.is_development:
            return self.DEV_FIT2RUN_ORDER_FROM_EMAIL
        return self.FIT2RUN_FROM_EMAIL
    
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
            return "Thank you for your purchase"
        return "Thank you for your purchase"

    def is_fit2run_email(self, email_data: EmailData) -> bool:
        """Check if email is from Fit2Run"""
        sender_lower = email_data.sender.lower()
        
        # In development, check for forwarded emails from dev email address
        if self.settings.is_development:
            if self.DEV_FIT2RUN_ORDER_FROM_EMAIL.lower() in sender_lower:
                return True
        
        # In production, check for Fit2Run email
        return self.FIT2RUN_FROM_EMAIL.lower() in sender_lower

    def is_order_confirmation_email(self, email_data: EmailData) -> bool:
        """Check if email is an order confirmation"""
        subject_lower = email_data.subject.lower()
        pattern = self.order_subject_pattern
        
        # Use regex matching for subject pattern
        if re.search(pattern, subject_lower, re.IGNORECASE):
            return True
        
        # For forwarded emails in dev mode, also check HTML content for Fit2Run confirmation indicators
        if self.settings.is_development and email_data.html_content:
            html_lower = email_data.html_content.lower()
            # Check for "Thank you for your purchase" or order confirmation indicators
            has_confirmation_text = (
                'thank you for your purchase' in html_lower or
                'order summary' in html_lower or
                ('fit2run' in html_lower and 'order' in html_lower) or
                ('order ' in html_lower and 'fit2run' in html_lower)
            )
            if has_confirmation_text:
                return True
        
        return False

    def parse_email(self, email_data: EmailData) -> Optional[Fit2RunOrderData]:
        """
        Parse Fit2Run order confirmation email.
        
        Args:
            email_data: EmailData object containing email information
        
        Returns:
            Fit2RunOrderData object or None if parsing fails
        """
        try:
            html_content = email_data.html_content
            
            if not html_content:
                logger.error("No HTML content in Fit2Run email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extract order number from HTML
            order_number = self._extract_order_number(soup)
            if not order_number:
                logger.error("Failed to extract order number from Fit2Run email")
                return None
            
            logger.info(f"Extracted Fit2Run order number: {order_number}")
            
            # Extract items using BeautifulSoup
            items = self._extract_items(soup)
            
            if not items:
                logger.error("Failed to extract any items from Fit2Run email")
                return None
            
            logger.info(f"Successfully extracted {len(items)} items from Fit2Run order {order_number}")
            for item in items:
                logger.debug(f"  - {item}")
            
            # Extract shipping address
            shipping_address = self._extract_shipping_address(soup)
            if shipping_address:
                logger.info(f"Extracted shipping address: {shipping_address}")
            
            return Fit2RunOrderData(order_number=order_number, items=items, shipping_address=shipping_address)
        
        except Exception as e:
            logger.error(f"Error parsing Fit2Run email: {e}", exc_info=True)
            return None

    def _extract_order_number(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract order number from Fit2Run email HTML.
        
        HTML format: 
        - "Order 2000814919" or "Order 2000866160"
        
        Extract: 2000814919
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            Order number or None
        """
        try:
            # Method 1: Look for "Order " text followed by number
            # Find the order number cell
            order_cell = soup.find('td', class_=re.compile(r'order-number', re.IGNORECASE))
            if order_cell:
                text = order_cell.get_text()
                match = re.search(r'Order\s+(\d+)', text, re.IGNORECASE)
                if match:
                    order_number = match.group(1)
                    logger.debug(f"Found Fit2Run order number: {order_number}")
                    return order_number
            
            # Method 2: Search entire text for "Order " followed by digits
            text_content = soup.get_text()
            match = re.search(r'Order\s+(\d+)', text_content, re.IGNORECASE)
            if match:
                order_number = match.group(1)
                logger.debug(f"Found Fit2Run order number (fallback): {order_number}")
                return order_number
            
            logger.warning("Order number not found in Fit2Run email")
            return None
        
        except Exception as e:
            logger.error(f"Error extracting Fit2Run order number: {e}")
            return None

    def _extract_items(self, soup: BeautifulSoup) -> List[Fit2RunOrderItem]:
        """
        Extract order items from Fit2Run email.
        
        Fit2Run email structure:
        - Products are in table rows within the "Order summary" section
        - Each product has:
          - Product image: <img src=".../files/110435_014_L_Revel_7_compact_cropped.png">
          - Product name: <span>Brooks Revel 7 × 1</span>
          - Size/Variant: <span>Primer - Blackened Pearl / D / 11.5</span>
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            List of Fit2RunOrderItem objects
        """
        items = []
        
        try:
            # Find the "Order summary" section
            order_summary_header = soup.find('h3', string=re.compile(r'Order\s+summary', re.IGNORECASE))
            
            if not order_summary_header:
                logger.warning("Order summary section not found")
                return []
            
            # Find all product rows by looking for rows that contain product name spans
            # Product rows have: span with font-size:16px and font-weight:600 containing product name × quantity
            product_rows = []
            
            # Find the container table after the order summary header
            order_summary_container = order_summary_header.find_parent('table')
            
            # Find the "Customer information" header to use as a boundary
            customer_info_header = soup.find('h3', string=re.compile(r'Customer\s+information', re.IGNORECASE))
            
            # Find all spans with product name pattern (font-size:16px, font-weight:600)
            # Look within the order summary section
            search_start = order_summary_header
            
            # Find all spans with product name pattern
            all_product_name_spans = search_start.find_all_next('span', style=lambda x: x and 'font-size:16px' in str(x) and 'font-weight:600' in str(x))
            
            # Filter spans to only include those before customer information
            # Use document order comparison: get all descendants and compare indices
            product_name_spans = []
            if customer_info_header:
                # Get all descendants to compare positions
                all_descendants = list(soup.descendants)
                try:
                    customer_index = all_descendants.index(customer_info_header)
                except ValueError:
                    customer_index = len(all_descendants)
                
                for span in all_product_name_spans:
                    try:
                        span_index = all_descendants.index(span)
                        # Only include spans that come before customer_info_header
                        if span_index < customer_index:
                            product_name_spans.append(span)
                        else:
                            # We've reached customer info section, stop
                            break
                    except ValueError:
                        # Span not found in descendants, skip it
                        continue
            else:
                # No customer info header found, include all spans
                product_name_spans = all_product_name_spans
            
            # Now process all collected spans
            for span in product_name_spans:
                text = span.get_text(strip=True)
                # Check if this looks like a product name with quantity (contains ×)
                if '×' in text and re.search(r'×\s*\d+', text):
                    # Find the parent row (tr) that contains this span
                    row = span.find_parent('tr')
                    if row:
                        # Find the image in this row or nearby
                        img = row.find('img', src=re.compile(r'cdn\.shopify\.com.*files/'))
                        if not img:
                            # Try to find image in parent table
                            parent_table = row.find_parent('table')
                            if parent_table:
                                img = parent_table.find('img', src=re.compile(r'cdn\.shopify\.com.*files/'))
                        
                        if img:
                            # Exclude logo and other non-product images
                            img_src = img.get('src', '')
                            if any(exclude in img_src.lower() for exclude in ['logo', 'fit2runlogo', 'spacer', 'discounttag']):
                                continue
                            product_rows.append((row, img))
            
            # If we didn't find products by name spans, try finding by image pattern
            if not product_rows:
                # Find all product images with Shopify CDN URLs (files/ pattern)
                product_images = search_start.find_all_next('img', src=re.compile(r'cdn\.shopify\.com.*files/'))
                
                for img in product_images:
                    # Exclude logo and other non-product images
                    img_src = img.get('src', '')
                    if any(exclude in img_src.lower() for exclude in ['logo', 'fit2runlogo', 'spacer', 'discounttag']):
                        continue
                    
                    # Find the parent row (tr) that contains this image
                    row = img.find_parent('tr')
                    if row:
                        # Check if this row contains product name span
                        has_product_name = row.find('span', style=lambda x: x and 'font-size:16px' in str(x) and 'font-weight:600' in str(x))
                        if has_product_name:
                            product_rows.append((row, img))
            
            # Remove duplicates (same row might be found multiple times)
            seen_rows = set()
            unique_product_rows = []
            for row, img in product_rows:
                row_id = id(row)
                if row_id not in seen_rows:
                    seen_rows.add(row_id)
                    unique_product_rows.append((row, img))
            
            # Process each product row
            for row, img in unique_product_rows:
                try:
                    product_details = self._extract_fit2run_product_details(row, img)
                    
                    if product_details:
                        items.append(product_details)
                
                except Exception as e:
                    logger.error(f"Error processing Fit2Run product row: {e}")
                    continue
            
            # Log items with ID, size, and quantity
            if items:
                items_summary = [f"(ID: {item.unique_id}, Size: {item.size}, Qty: {item.quantity})" for item in items]
                logger.info(f"[Fit2Run] Extracted {len(items)} items: {', '.join(items_summary)}")
            
            return items
        
        except Exception as e:
            logger.error(f"Error extracting Fit2Run items: {e}", exc_info=True)
            return []

    def _extract_fit2run_product_details(self, row, img) -> Optional[Fit2RunOrderItem]:
        """
        Extract product details from a Fit2Run product row.
        
        Returns:
            Fit2RunOrderItem object or None
        """
        try:
            # Extract unique ID from image URL
            img_src = img.get('src', '') if img else ''
            unique_id = None
            
            if img_src:
                unique_id = self._extract_unique_id_from_image(img_src)
            
            # If we couldn't extract unique ID from image, try to find it elsewhere or skip
            if not unique_id:
                logger.warning(f"Could not extract unique ID from image URL: {img_src[:100] if img_src else 'No image'}")
                # For now, we require unique ID - return None if not found
                # In the future, we might try alternative extraction methods
                return None
            
            # Extract product name
            # Look for span with font-size:16px and font-weight:600 (product name)
            product_name = None
            product_name_text = None
            product_spans = row.find_all('span', style=lambda x: x and 'font-size:16px' in str(x) and 'font-weight:600' in str(x))
            if product_spans:
                product_name_text = product_spans[0].get_text(strip=True)
                # Remove quantity suffix (× 1, × 3, etc.)
                product_name_match = re.match(r'(.+?)\s*×\s*\d+', product_name_text)
                if product_name_match:
                    product_name = product_name_match.group(1).strip()
                else:
                    product_name = product_name_text
            
            # Extract size
            # Format: "Primer - Blackened Pearl / D / 11.5" or "Black - White / D / 12.5"
            # Size is the last part after the last "/"
            size = None
            size_spans = row.find_all('span', style=lambda x: x and 'font-size:14px' in str(x) and 'color:#999' in str(x))
            if size_spans:
                size_text = size_spans[0].get_text(strip=True)
                # Extract size - it's the last part after the last "/"
                # Format: "Color - Color / Width / Size"
                size_match = re.search(r'/\s*([^/\s]+)\s*$', size_text)
                if size_match:
                    size = size_match.group(1).strip()
                else:
                    # Fallback: try to extract any number that looks like a size
                    size_match = re.search(r'(\d+(?:\.\d+)?)', size_text)
                    if size_match:
                        size = size_match.group(1)
            
            if not size:
                logger.warning(f"Size not found for product: {product_name or 'Unknown'}")
                return None
            
            # Extract quantity
            # Format: "Brooks Revel 7 × 1" or "Brooks Glycerin 21 × 3"
            quantity = 1
            if product_name_text:
                qty_match = re.search(r'×\s*(\d+)', product_name_text)
                if qty_match:
                    quantity = int(qty_match.group(1))
            
            return Fit2RunOrderItem(
                unique_id=unique_id,
                size=size,
                quantity=quantity,
                product_name=product_name
            )
            
        except Exception as e:
            logger.error(f"Error extracting Fit2Run product details: {e}", exc_info=True)
            return None
    
    def _extract_unique_id_from_image(self, img_src: str) -> Optional[str]:
        """
        Extract unique ID from Fit2Run product image URL.
        
        URL formats:
        1. Numeric pattern: 
           https://cdn.shopify.com/s/files/1/0878/6811/3205/files/110435_014_L_Revel_7_compact_cropped.png?v=1756388083
           Extract: 110435_014
         
        2. Alphanumeric pattern:
           https://cdn.shopify.com/s/files/1/0878/6811/3205/files/wblkwht1_compact_cropped.png?v=1763576828
           Extract: wblkwht1
        
        Or Gmail proxy URL:
        https://ci3.googleusercontent.com/...=s0-d-e1-ft#https://cdn.shopify.com/s/files/1/0878/6811/3205/files/110435_014_L_Revel_7_compact_cropped.png?v=1756388083
        
        Args:
            img_src: Image source URL
        
        Returns:
            Unique ID or None
        """
        try:
            # Handle Gmail proxy URLs - extract actual URL after #
            if '#' in img_src:
                # Extract the URL after the hash
                actual_url = img_src.split('#')[-1]
                img_src = actual_url
            
            # Pattern 1: files/(\d+)_(\d+)_ - numeric pattern (e.g., 110435_014)
            match = re.search(r'/files/(\d+)_(\d+)_', img_src)
            if match:
                product_id = match.group(1)
                variant_id = match.group(2)
                unique_id = f"{product_id}_{variant_id}"
                logger.debug(f"Extracted unique ID (numeric pattern) from URL: {unique_id}")
                return unique_id
            
            # Pattern 2: files/([a-zA-Z0-9]+)_ - alphanumeric pattern (e.g., wblkwht1)
            # Extract the filename part before the first underscore after "compact_cropped" or similar suffixes
            # Or extract the part before "_compact_cropped" or similar
            match = re.search(r'/files/([a-zA-Z0-9]+?)(?:_compact_cropped|_|\.)', img_src)
            if match:
                unique_id = match.group(1)
                logger.debug(f"Extracted unique ID (alphanumeric pattern) from URL: {unique_id}")
                return unique_id
            
            # Fallback: Try to extract any alphanumeric sequence after /files/ and before underscore or dot
            match = re.search(r'/files/([a-zA-Z0-9]+)', img_src)
            if match:
                unique_id = match.group(1)
                logger.debug(f"Extracted unique ID (fallback pattern) from URL: {unique_id}")
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
                # Find the address text in the next p or div
                address_element = shipping_header.find_next(['p', 'div'])
                if address_element:
                    # Get address text, handling <br> tags
                    address_text = address_element.get_text(separator=' ', strip=True)
                    
                    if address_text:
                        normalized = normalize_shipping_address(address_text)
                        logger.debug(f"Extracted shipping address: {normalized}")
                        return normalized
            
            return ""
        
        except Exception as e:
            logger.error(f"Error extracting shipping address: {e}", exc_info=True)
            return ""
