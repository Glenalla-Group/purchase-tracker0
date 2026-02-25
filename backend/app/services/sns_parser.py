"""
SNS (Sneakersnstuff) Email Parser
Parses order confirmation emails from SNS using BeautifulSoup

Email Format:
- From: order@orderinfo.sneakersnstuff.com (production)
- From: glenallagroupc@gmail.com (dev - forwarded emails)
- Subject: "We've got your order." or similar
- Order Number: Extract from HTML (e.g., "5000055", "5026433")

HTML Structure:
- Products are listed in tables
- Each product has:
  - Product image: <img src="https://cdn11.bigcommerce.com/...">
  - Product name: "Nike Air Max 1 SC"
  - Size: "US Size: 10" or "US Size: W6.5"
  - Quantity: "Qty: 4"
  - Price: "60.00 USD"

Unique ID Extraction:
- Format: Extract from product name (e.g., "air-max-1-sc")
- Convert product name to URL-friendly format:
  1. Remove "Nike" prefix if present
  2. Convert to lowercase
  3. Replace spaces with hyphens
  4. Remove special characters (apostrophes, etc.)
  5. Handle year format ('07 -> 07, '23 -> 23)
- Example: "Nike Air Force 1 '07" -> "air-force-1-07"
- Example: "Nike Air Max 1 SC" -> "air-max-1-sc"
- Example: "Nike Cortez '23" -> "cortez-23"
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


class SNSOrderItem(BaseModel):
    unique_id: str = Field(..., description="Unique identifier for the product (e.g., air-force-1-07)")
    size: str = Field(..., description="Size of the product")
    quantity: int = Field(..., description="Quantity of the product")
    product_name: Optional[str] = Field(None, description="Name of the product")
    
    def __repr__(self):
        if self.product_name and len(self.product_name) > 50:
            product_display = self.product_name[:50] + "..."
        else:
            product_display = self.product_name or "Unknown"
        return f"<SNSOrderItem(unique_id={self.unique_id}, size={self.size}, qty={self.quantity}, product={product_display})>"


class SNSOrderData(BaseModel):
    order_number: str = Field(..., description="The order number")
    items: List[SNSOrderItem] = Field(..., description="List of items in the order")
    items_count: int = Field(0, description="Total number of items in the order")
    shipping_address: str = Field("", description="Normalized shipping address")

    def __init__(self, **data):
        super().__init__(**data)
        self.items_count = len(self.items)


class SNSEmailParser:
    # Email identification - Order Confirmation (Production)
    SNS_FROM_EMAIL = "order@orderinfo.sneakersnstuff.com"
    SUBJECT_ORDER_PATTERN = r"we['\u2019]ve\s+got\s+your\s+order|order\s+confirmation"
    
    # Email identification - Development (forwarded emails)
    DEV_SNS_ORDER_FROM_EMAIL = "glenallagroupc@gmail.com"
    DEV_SUBJECT_ORDER_PATTERN = r"(?:Fwd:\s*)?(?:we['\u2019]ve\s+got\s+your\s+order|order|sns|sneakersnstuff)"

    def __init__(self):
        """Initialize the SNS email parser."""
        self.settings = get_settings()
    
    @property
    def order_from_email(self) -> str:
        """Get the appropriate from email address based on environment."""
        if self.settings.is_development:
            return self.DEV_SNS_ORDER_FROM_EMAIL
        return self.SNS_FROM_EMAIL
    
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
            return "We've got your order"
        return "We've got your order"

    def is_sns_email(self, email_data: EmailData) -> bool:
        """Check if email is from SNS"""
        sender_lower = email_data.sender.lower()
        
        # In development, check for forwarded emails from dev email address
        if self.settings.is_development:
            if self.DEV_SNS_ORDER_FROM_EMAIL.lower() in sender_lower:
                return True
        
        # In production, check for SNS email
        return self.SNS_FROM_EMAIL.lower() in sender_lower

    def is_order_confirmation_email(self, email_data: EmailData) -> bool:
        """Check if email is an order confirmation"""
        subject_lower = email_data.subject.lower()
        pattern = self.order_subject_pattern
        
        # Use regex matching for subject pattern
        if re.search(pattern, subject_lower, re.IGNORECASE):
            return True
        
        # For forwarded emails in dev mode, also check HTML content for SNS confirmation indicators
        if self.settings.is_development and email_data.html_content:
            html_lower = email_data.html_content.lower()
            # Check for "We've got your order" or order confirmation indicators
            has_confirmation_text = (
                "we've got your order" in html_lower or
                "we've got your order" in html_lower or
                "order confirmation" in html_lower or
                ("sns" in html_lower and "order" in html_lower) or
                ("sneakersnstuff" in html_lower and "order" in html_lower)
            )
            if has_confirmation_text:
                return True
        
        return False

    def parse_email(self, email_data: EmailData) -> Optional[SNSOrderData]:
        """
        Parse SNS order confirmation email.
        
        Args:
            email_data: EmailData object containing email information
        
        Returns:
            SNSOrderData object or None if parsing fails
        """
        try:
            html_content = email_data.html_content
            
            if not html_content:
                logger.error("No HTML content in SNS email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extract order number from HTML
            order_number = self._extract_order_number(soup)
            if not order_number:
                logger.error("Failed to extract order number from SNS email")
                return None
            
            logger.info(f"Extracted SNS order number: {order_number}")
            
            # Extract items using BeautifulSoup
            items = self._extract_items(soup)
            
            if not items:
                logger.error("Failed to extract any items from SNS email")
                return None
            
            logger.info(f"Successfully extracted {len(items)} items from SNS order {order_number}")
            for item in items:
                logger.debug(f"  - {item}")
            
            # Extract shipping address
            shipping_address = self._extract_shipping_address(soup)
            if shipping_address:
                logger.info(f"Extracted shipping address: {shipping_address}")
            
            return SNSOrderData(order_number=order_number, items=items, shipping_address=shipping_address)
        
        except Exception as e:
            logger.error(f"Error parsing SNS email: {e}", exc_info=True)
            return None

    def _extract_order_number(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract order number from SNS email HTML.
        
        HTML format: 
        - Hidden span: <span style="...">Order number: 5000055</span>
        - Visible text: "5000055" or "5026433"
        
        Extract: 5000055
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            Order number or None
        """
        try:
            # Method 1: Look for hidden span with "Order number: XXXX"
            hidden_spans = soup.find_all('span', style=lambda x: x and 'display:none' in str(x) and 'transparent' in str(x))
            for span in hidden_spans:
                text = span.get_text()
                match = re.search(r'Order\s+number:\s*(\d+)', text, re.IGNORECASE)
                if match:
                    order_number = match.group(1)
                    logger.debug(f"Found SNS order number from hidden span: {order_number}")
                    return order_number
            
            # Method 2: Look for "ORDER NUMBER:" label followed by number
            order_labels = soup.find_all(string=re.compile(r'ORDER\s+NUMBER:', re.IGNORECASE))
            for label in order_labels:
                # Find the next text element that contains a number
                parent = label.find_parent()
                if parent:
                    # Look for the number in the same cell/block
                    next_elements = parent.find_next_siblings()
                    for elem in next_elements:
                        text = elem.get_text(strip=True)
                        match = re.search(r'(\d+)', text)
                        if match:
                            order_number = match.group(1)
                            logger.debug(f"Found SNS order number from label: {order_number}")
                            return order_number
                    
                    # Also check parent's text
                    parent_text = parent.get_text()
                    match = re.search(r'ORDER\s+NUMBER:.*?(\d+)', parent_text, re.IGNORECASE | re.DOTALL)
                    if match:
                        order_number = match.group(1)
                        logger.debug(f"Found SNS order number from parent text: {order_number}")
                        return order_number
            
            # Method 3: Search entire text for order number pattern
            text_content = soup.get_text()
            # Look for standalone numbers that could be order numbers (typically 7 digits)
            match = re.search(r'\b(\d{6,8})\b', text_content)
            if match:
                order_number = match.group(1)
                logger.debug(f"Found SNS order number (fallback): {order_number}")
                return order_number
            
            logger.warning("Order number not found in SNS email")
            return None
        
        except Exception as e:
            logger.error(f"Error extracting SNS order number: {e}")
            return None

    def _extract_items(self, soup: BeautifulSoup) -> List[SNSOrderItem]:
        """
        Extract order items from SNS email.
        
        SNS email structure:
        - Products are in table rows
        - Each product row has:
          - Column 1 (25%): Product image
          - Column 2 (41.67%): Product name, size, quantity
          - Column 3 (33.33%): Price
        
        Product format:
        - Product name: "Nike Air Max 1 SC"
        - Size: "US Size: 10" or "US Size: W6.5"
        - Quantity: "Qty: 4"
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            List of SNSOrderItem objects
        """
        items = []
        
        try:
            # Find all product rows - look for tables with product images from bigcommerce
            product_images = soup.find_all('img', src=re.compile(r'cdn11\.bigcommerce\.com.*products'))
            
            seen_rows = set()
            
            for img in product_images:
                # Exclude logo and other non-product images
                img_src = img.get('src', '')
                if any(exclude in img_src.lower() for exclude in ['logo', 'spacer', 'convert']):
                    continue
                
                # Find the correct parent row that contains both image and product details
                # The structure: img is in column-1, product details are in column-2
                # Both are in the same <tr> row, but img.find_parent('tr') might get nested tr
                # We need the outer tr that contains both column-1 and column-2
                
                # Find all parent tr elements
                current = img
                row = None
                
                # Walk up the tree to find the tr that contains both column-1 and column-2
                for _ in range(10):  # Limit depth to avoid infinite loops
                    parent_tr = current.find_parent('tr')
                    if not parent_tr:
                        break
                    
                    # Check if this tr contains both column-1 (image) and column-2 (product details)
                    column_1 = parent_tr.find('td', class_=lambda x: x and 'column-1' in str(x))
                    column_2 = parent_tr.find('td', class_=lambda x: x and 'column-2' in str(x))
                    
                    if column_1 and column_2:
                        # This is the correct row - it has both image and product details
                        row = parent_tr
                        break
                    
                    current = parent_tr
                
                # Fallback: if we didn't find the right row, use the first parent tr
                if not row:
                    row = img.find_parent('tr')
                
                if not row:
                    logger.debug(f"Could not find parent row for image: {img_src[:100]}")
                    continue
                
                row_id = id(row)
                if row_id in seen_rows:
                    continue
                seen_rows.add(row_id)
                
                try:
                    product_details = self._extract_sns_product_details(row)
                    
                    if product_details:
                        items.append(product_details)
                    else:
                        logger.debug(f"Could not extract product details from row with image: {img_src[:100]}")
                
                except Exception as e:
                    logger.error(f"Error processing SNS product row: {e}")
                    continue
            
            # Log items with ID, size, and quantity
            if items:
                items_summary = [f"(ID: {item.unique_id}, Size: {item.size}, Qty: {item.quantity})" for item in items]
                logger.info(f"[SNS] Extracted {len(items)} items: {', '.join(items_summary)}")
            
            return items
        
        except Exception as e:
            logger.error(f"Error extracting SNS items: {e}", exc_info=True)
            return []

    def _extract_sns_product_details(self, row) -> Optional[SNSOrderItem]:
        """
        Extract product details from a SNS product row.
        
        HTML structure:
        - Product info is in a <p> tag with text-align:left
        - Format: "Nike Air Max 1 SC <br>US Size: 10 <br>Qty: 4"
        
        Returns:
            SNSOrderItem object or None
        """
        try:
            text_content = None
            
            # Method 1: Look for <p> tag with text-align:left that contains product info
            product_paragraphs = row.find_all('p', style=lambda x: x and 'text-align:left' in str(x))
            for p in product_paragraphs:
                p_text = p.get_text(separator='\n', strip=True)
                # Check if this paragraph contains product info (has "US Size:" or "Qty:")
                if 'US Size:' in p_text or 'Qty:' in p_text:
                    text_content = p_text
                    break
            
            # Method 2: If not found, look for the middle column (41.67% width) that contains product details
            if not text_content:
                middle_column = row.find('td', class_=lambda x: x and 'column-2' in str(x))
                if middle_column:
                    # Find <p> tag inside the column
                    product_paragraph = middle_column.find('p')
                    if product_paragraph:
                        text_content = product_paragraph.get_text(separator='\n', strip=True)
                    else:
                        # Get text from the column, but filter out price info
                        column_text = middle_column.get_text(separator='\n', strip=True)
                        # Check if it contains product info
                        if 'US Size:' in column_text or 'Qty:' in column_text:
                            text_content = column_text
            
            # Method 3: Fallback - search for any paragraph or div containing "US Size:" pattern
            if not text_content:
                # Find all text elements in the row
                all_text_elements = row.find_all(['p', 'div'])
                for elem in all_text_elements:
                    elem_text = elem.get_text(separator='\n', strip=True)
                    # Check if this element contains product info
                    if ('US Size:' in elem_text or 'Qty:' in elem_text) and not re.search(r'\d+\.\d+\s*USD', elem_text):
                        text_content = elem_text
                        break
            
            # Method 4: Final fallback - use entire row text
            if not text_content:
                text_content = row.get_text(separator='\n', strip=True)
            
            # Parse product name, size, and quantity
            lines = [line.strip() for line in text_content.split('\n') if line.strip()]
            
            logger.debug(f"Parsing SNS product lines: {lines}")
            
            product_name = None
            size = None
            quantity = 1
            
            # Process lines in order - product name should come first, then size, then quantity
            for i, line in enumerate(lines):
                # Skip empty lines and price lines
                if not line or re.match(r'^\d+\.\d+\s*USD?$', line, re.IGNORECASE):
                    continue
                
                # Extract size
                size_match = re.search(r'US\s+Size:\s*(.+)', line, re.IGNORECASE)
                if size_match:
                    size = size_match.group(1).strip()
                    continue
                
                # Extract quantity
                qty_match = re.search(r'Qty:\s*(\d+)', line, re.IGNORECASE)
                if qty_match:
                    quantity = int(qty_match.group(1))
                    continue
                
                # Extract product name (first line that doesn't match size/qty/price pattern)
                if not product_name:
                    # Check if this line matches size or qty pattern (shouldn't happen due to checks above)
                    if re.match(r'^(US\s+Size:|Qty:)', line, re.IGNORECASE):
                        continue
                    # This should be the product name
                    product_name = line
                    continue
            
            # If we still don't have product name, try to get first non-matching line
            if not product_name and lines:
                for line in lines:
                    # Skip lines that match size, qty, or price patterns
                    if re.match(r'^(US\s+Size:|Qty:|USD|\d+\.\d+)', line, re.IGNORECASE):
                        continue
                    # This should be the product name
                    product_name = line
                    break
            
            if not product_name:
                logger.warning(f"Product name not found in SNS product row. Lines: {lines}")
                return None
            
            if not size:
                logger.warning(f"Size not found for product: {product_name}. Lines: {lines}")
                return None
            
            # Extract unique ID from product name
            unique_id = self._extract_unique_id_from_product_name(product_name)
            if not unique_id:
                logger.warning(f"Could not extract unique ID from product name: {product_name}")
                return None
            
            return SNSOrderItem(
                unique_id=unique_id,
                size=size,
                quantity=quantity,
                product_name=product_name
            )
            
        except Exception as e:
            logger.error(f"Error extracting SNS product details: {e}", exc_info=True)
            return None
    
    def _extract_unique_id_from_product_name(self, product_name: str) -> Optional[str]:
        """
        Extract unique ID from SNS product name.
        
        Format: Convert product name to URL-friendly format
        - Remove "Nike" prefix if present
        - Convert to lowercase
        - Replace spaces with hyphens
        - Remove special characters (apostrophes, etc.)
        - Handle year format ('07 -> 07, '23 -> 23)
        
        Examples:
        - "Nike Air Force 1 '07" -> "air-force-1-07"
        - "Nike Air Max 1 SC" -> "air-max-1-sc"
        - "Nike Cortez '23" -> "cortez-23"
        
        Args:
            product_name: Product name string
        
        Returns:
            Unique ID or None
        """
        try:
            # Remove "Nike" prefix if present
            name = product_name.strip()
            if name.lower().startswith('nike '):
                name = name[5:].strip()
            
            # Convert to lowercase
            name = name.lower()
            
            # Handle year format: '07 -> 07, '23 -> 23
            # Replace apostrophes followed by digits
            name = re.sub(r"[''](\d+)", r'\1', name)
            
            # Replace spaces and special characters with hyphens
            # Keep only alphanumeric characters and hyphens
            name = re.sub(r'[^a-z0-9\s-]', '', name)
            
            # Replace multiple spaces with single hyphen
            name = re.sub(r'\s+', '-', name)
            
            # Remove leading/trailing hyphens
            name = name.strip('-')
            
            if not name:
                logger.warning(f"Empty unique ID after processing product name: {product_name}")
                return None
            
            logger.debug(f"Extracted unique ID '{name}' from product name '{product_name}'")
            return name
        
        except Exception as e:
            logger.error(f"Error extracting unique ID from product name: {e}")
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
            # Look for "SHIPPING ADDRESS:" label
            shipping_labels = soup.find_all(string=re.compile(r'SHIPPING\s+ADDRESS:', re.IGNORECASE))
            
            for label in shipping_labels:
                # Find the parent element
                parent = label.find_parent()
                if parent:
                    # Find the next block that contains the address
                    # Address is typically in the next table cell or div
                    address_elements = parent.find_next_siblings()
                    for elem in address_elements:
                        address_text = elem.get_text(separator=' ', strip=True)
                        if address_text and len(address_text) > 10:  # Address should be substantial
                            normalized = normalize_shipping_address(address_text)
                            if normalized:
                                logger.debug(f"Extracted shipping address: {normalized}")
                                return normalized
                    
                    # Also check parent's next sibling
                    next_sibling = parent.find_next_sibling()
                    if next_sibling:
                        address_text = next_sibling.get_text(separator=' ', strip=True)
                        if address_text and len(address_text) > 10:
                            normalized = normalize_shipping_address(address_text)
                            if normalized:
                                logger.debug(f"Extracted shipping address: {normalized}")
                                return normalized
            
            return ""
        
        except Exception as e:
            logger.error(f"Error extracting shipping address: {e}", exc_info=True)
            return ""
