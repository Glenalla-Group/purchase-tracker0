"""
ASOS Email Parser
Parses order confirmation emails from ASOS using BeautifulSoup

Email Format:
- From: orders@asos.com
- Subject: "Thanks for your order!"
- Order Number: Extract from "Order No.: 1026481322"

HTML Structure:
- Products are listed individually in table rows
- Each product has:
  - Image URL: https://images.asos-media.com/products/.../206568080-1-black
    Unique ID: 206568080 (extract from image URL before -1-black)
  - Product name: "Nike Running Air Zoom Pegasus 41 sneakers in black and white"
  - Size/Qty: "Black / WM US 10 / Qty 8" or "Black / WM US 5.5 / Qty 2"

Important: ASOS lists products individually. If you order multiple units of the same product
in the same size, they appear as separate items. We need to:
- Group items by unique_id + size
- Sum quantities for identical items
- Return consolidated items

Example:
  Input: 8 items of 206568080, Size 10, Qty 1 each
  Output: 1 item of 206568080, Size 10, Qty 8
"""

import re
import logging
from typing import List, Optional, Dict
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from app.models.email import EmailData
from app.utils.address_utils import normalize_shipping_address
from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class ASOSOrderItem(BaseModel):
    unique_id: str = Field(..., description="Unique identifier for the product (e.g., 206568080)")
    size: str = Field(..., description="Size of the product")
    quantity: int = Field(..., description="Quantity of the product (summed for identical items)")
    product_name: Optional[str] = Field(None, description="Name of the product")
    
    def __repr__(self):
        if self.product_name and len(self.product_name) > 50:
            product_display = self.product_name[:50] + "..."
        else:
            product_display = self.product_name or "Unknown"
        return f"<ASOSOrderItem(unique_id={self.unique_id}, size={self.size}, qty={self.quantity}, product={product_display})>"


class ASOSOrderData(BaseModel):
    order_number: str = Field(..., description="The order number")
    items: List[ASOSOrderItem] = Field(..., description="List of items in the order (consolidated)")
    items_count: int = Field(0, description="Total number of items in the order")
    shipping_address: str = Field("", description="Normalized shipping address")

    def __init__(self, **data):
        super().__init__(**data)
        self.items_count = len(self.items)


class ASOSShippingData(BaseModel):
    """ASOS shipping notification data (full or partial). Same unique_id logic as order confirmation."""
    order_number: str = Field(..., description="The order number")
    items: List[ASOSOrderItem] = Field(..., description="Shipped items (consolidated by unique_id + size)")
    tracking_number: str = Field("", description="Tracking number if present")

    def __repr__(self):
        tk = (self.tracking_number[:20] + "...") if len(self.tracking_number) > 20 else self.tracking_number
        return f"<ASOSShippingData(order={self.order_number}, items={len(self.items)}, tracking={tk})>"


class ASOSEmailParser:
    # Email identification - Order Confirmation (Production)
    ASOS_FROM_EMAIL = "orders@asos.com"
    SUBJECT_ORDER_PATTERN = r"thanks for your order"
    
    # Email identification - Development (forwarded emails)
    DEV_ASOS_ORDER_FROM_EMAIL = "glenallagroupc@gmail.com"
    DEV_SUBJECT_ORDER_PATTERN = r"Fwd:\s*Thanks for your order"
    
    # Shipping - Subject: "Your order's on its way!"
    SUBJECT_SHIPPING_PATTERN = r"your order'?s?\s+on its way"
    DEV_SUBJECT_SHIPPING_PATTERN = r"Fwd:\s*Your order'?s?\s+on its way"

    def __init__(self):
        """Initialize the ASOS email parser."""
        self.settings = get_settings()
    
    @property
    def order_from_email(self) -> str:
        """Get the appropriate from email address based on environment."""
        if self.settings.is_development:
            return self.DEV_ASOS_ORDER_FROM_EMAIL
        return self.ASOS_FROM_EMAIL
    
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
            return "Fwd: Thanks for your order"
        return "Thanks for your order"
    
    @property
    def update_from_email(self) -> str:
        """From address for shipping updates (same as order)."""
        if self.settings.is_development:
            return self.DEV_ASOS_ORDER_FROM_EMAIL
        return self.ASOS_FROM_EMAIL
    
    @property
    def shipping_subject_query(self) -> str:
        """Gmail subject query for shipping emails."""
        if self.settings.is_development:
            return 'subject:"Fwd: Your order\'s on its way!"'
        return 'subject:"Your order\'s on its way!"'

    def is_asos_email(self, email_data: EmailData) -> bool:
        """
        Check if email is from ASOS.
        
        In dev mode, both ASOS and Nike forward from glenallagroupc with "Thanks for your order".
        Differentiate via HTML: ASOS has asos.com or images.asos-media.com.
        
        For SHIPPING emails ("Your order's on its way!"): subject is ASOS-specific, so accept
        glenallagroupc without HTML check - prevents Carbon38/others from stealing via broad "order" match.
        """
        sender_lower = email_data.sender.lower()
        subject_lower = (email_data.subject or "").lower()
        
        # Shipping subject "Your order's on its way!" is unique to ASOS - accept without HTML check
        if re.search(r"your order'?s?\s+on its way", subject_lower):
            if self.ASOS_FROM_EMAIL.lower() in sender_lower:
                return True
            if self.settings.is_development and self.DEV_ASOS_ORDER_FROM_EMAIL.lower() in sender_lower:
                return True
        
        # In development, order confirmation: both ASOS and Nike use glenallagroupc - check HTML
        if self.settings.is_development:
            if self.DEV_ASOS_ORDER_FROM_EMAIL.lower() in sender_lower:
                html = (email_data.html_content or "").lower()
                if "asos.com" in html or "images.asos-media.com" in html:
                    return True
                return False
        
        # In production, check for ASOS email
        return self.ASOS_FROM_EMAIL.lower() in sender_lower

    def is_order_confirmation_email(self, email_data: EmailData) -> bool:
        """Check if email is an order confirmation"""
        subject_lower = email_data.subject.lower()
        pattern = self.order_subject_pattern
        
        # Use regex matching for subject pattern
        return bool(re.search(pattern, subject_lower, re.IGNORECASE))
    
    def is_shipping_email(self, email_data: EmailData) -> bool:
        """Check if email is a shipping notification (Your order's on its way!)."""
        subject_lower = email_data.subject.lower()
        pattern = self.DEV_SUBJECT_SHIPPING_PATTERN if self.settings.is_development else self.SUBJECT_SHIPPING_PATTERN
        return bool(re.search(pattern, subject_lower, re.IGNORECASE))

    def parse_email(self, email_data: EmailData) -> Optional[ASOSOrderData]:
        """
        Parse ASOS order confirmation email.
        
        Args:
            email_data: EmailData object containing email information
        
        Returns:
            ASOSOrderData object or None if parsing fails
        """
        try:
            html_content = email_data.html_content
            
            if not html_content:
                logger.error("No HTML content in ASOS email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extract order number from email content
            order_number = self._extract_order_number(soup)
            if not order_number:
                logger.error("Failed to extract order number from ASOS email")
                return None
            
            logger.info(f"Extracted ASOS order number: {order_number}")
            
            # Extract items using BeautifulSoup
            items = self._extract_items(soup)
            
            if not items:
                logger.error("Failed to extract any items from ASOS email")
                return None
            
            logger.info(f"Successfully extracted {len(items)} consolidated items from ASOS order {order_number}")
            for item in items:
                logger.debug(f"  - {item}")
            
            # Extract shipping address
            shipping_address = self._extract_shipping_address(soup)
            if shipping_address:
                logger.info(f"Extracted shipping address: {shipping_address}")
            
            return ASOSOrderData(order_number=order_number, items=items, shipping_address=shipping_address)
        
        except Exception as e:
            logger.error(f"Error parsing ASOS email: {e}", exc_info=True)
            return None
    
    def parse_shipping_email(self, email_data: EmailData) -> Optional[ASOSShippingData]:
        """
        Parse ASOS shipping notification email (Your order's on its way!).
        
        - Order number from body (Order No.: 1026481488)
        - Items only from "X item sent" / "X items sent" section (ignores "also on its/their way")
        - unique_id from image URL (e.g. .../206568080-1-black -> 206568080), same as confirmation
        - Consolidation by unique_id + size
        """
        try:
            html_content = email_data.html_content
            if not html_content:
                logger.error("No HTML content in ASOS shipping email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            order_number = self._extract_order_number(soup)
            if not order_number:
                logger.error("Failed to extract order number from ASOS shipping email")
                return None
            
            items = self._extract_items_from_item_sent_section(soup)
            if not items:
                logger.error("Failed to extract any items from ASOS shipping email")
                return None
            
            logger.info(
                f"Extracted ASOS shipping - Order: {order_number}, Items: {len(items)} "
                f"(unique_id from image URL, same as order confirmation)"
            )
            for item in items:
                logger.debug(f"  - {item}")
            
            return ASOSShippingData(
                order_number=order_number,
                items=items,
                tracking_number=""
            )
        
        except Exception as e:
            logger.error(f"Error parsing ASOS shipping email: {e}", exc_info=True)
            return None

    def _extract_order_number(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract order number from ASOS email.
        
        Format: Order No.: 1026481322
        Extract: 1026481322
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            Order number or None
        """
        try:
            # Look for "Order No.:" text
            text = soup.get_text()
            
            # Pattern: Order No.: 1026481322
            match = re.search(r'Order\s+No\.?:\s*(\d+)', text, re.IGNORECASE)
            if match:
                order_number = match.group(1)
                logger.debug(f"Found ASOS order number: {order_number}")
                return order_number
            
            logger.warning("Order number not found in ASOS email")
            return None
        
        except Exception as e:
            logger.error(f"Error extracting ASOS order number: {e}")
            return None

    def _extract_items(self, soup: BeautifulSoup) -> List[ASOSOrderItem]:
        """
        Extract order items from ASOS email and consolidate duplicates.
        
        ASOS email structure:
        - Products are in table rows with product images
        - Each product row contains:
          - Image with URL: https://images.asos-media.com/products/.../206568080-1-black
          - Product name in <a> tag
          - Size/Qty: "Black / WM US 10 / Qty 8"
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            List of ASOSOrderItem objects (consolidated by unique_id + size)
        """
        # First, extract all raw items
        raw_items = []
        
        try:
            # Find all product images from asos-media.com
            product_images = soup.find_all('img', src=lambda x: x and 'images.asos-media.com/products' in str(x))
            
            for img in product_images:
                try:
                    # Find the parent table row
                    parent_row = img.find_parent('tr')
                    if not parent_row:
                        continue
                    
                    # Extract product details from this row
                    product_details = self._extract_asos_product_details(parent_row, img)
                    
                    if product_details:
                        raw_items.append(product_details)
                
                except Exception as e:
                    logger.error(f"Error processing ASOS product row: {e}")
                    continue
            
            # Consolidate items by unique_id + size
            consolidated_items = self._consolidate_items(raw_items)
            
            # Log items with ID, size, and quantity
            if consolidated_items:
                items_summary = [f"(ID: {item.unique_id}, Size: {item.size}, Qty: {item.quantity})" for item in consolidated_items]
                logger.info(f"[ASOS] Extracted {len(consolidated_items)} consolidated items: {', '.join(items_summary)}")
            
            return consolidated_items
        
        except Exception as e:
            logger.error(f"Error extracting ASOS items: {e}", exc_info=True)
            return []

    def _extract_items_from_item_sent_section(self, soup: BeautifulSoup) -> List[ASOSOrderItem]:
        """
        Extract items only from the "X item sent" / "X items sent" section.
        Ignores "X item(s) also on its/their way" sections.
        
        Blocks are wrapped in tr tags. Scope = trs from "X items sent" h2 until the next block
        (tr that contains table with #f5f5f2 or h2 with "also on its way").
        """
        raw_items = []
        try:
            # Find the first h2 matching "1 item sent" or "2 items sent" (not "also on its way")
            item_sent_header = None
            for h2 in soup.find_all('h2'):
                text = (h2.get_text() or '').strip()
                if re.match(r'^\d+ items? sent$', text, re.IGNORECASE):
                    item_sent_header = h2
                    break
            
            if not item_sent_header:
                logger.warning("No 'X item(s) sent' section found in ASOS shipping email")
                return []
            
            # Scope to trs: from the h2's tr up to (but not including) the next block
            # Next block = tr containing table with #f5f5f2 or h2 with "also on its way"
            start_tr = item_sent_header.find_parent('tr')
            if not start_tr:
                logger.warning("Could not find parent tr for 'item sent' header")
                return []
            
            # Build scope: start_tr + following sibling trs until next block boundary
            # Next block = tr with table#f5f5f2 or h2 "also on its/their way"
            scope_trs = [start_tr]
            for tr in start_tr.find_next_siblings('tr'):
                if tr.find('table', style=re.compile(r'f5f5f2', re.I)):
                    break
                if tr.find('h2', string=re.compile(r'also on (?:its|their)', re.I)):
                    break
                scope_trs.append(tr)
            
            # Search for product images only within these trs (products are in nested tables)
            for tr in scope_trs:
                for img in tr.find_all('img', src=lambda x: x and 'images.asos-media.com/products' in str(x)):
                    try:
                        parent_row = img.find_parent('tr')
                        if not parent_row:
                            continue
                        product_details = self._extract_asos_product_details(parent_row, img)
                        if product_details:
                            raw_items.append(product_details)
                    except Exception as e:
                        logger.error(f"Error processing ASOS product row: {e}")
                        continue
            
            consolidated_items = self._consolidate_items(raw_items)
            if consolidated_items:
                items_summary = [f"(ID: {item.unique_id}, Size: {item.size}, Qty: {item.quantity})" for item in consolidated_items]
                logger.info(f"[ASOS] Extracted {len(consolidated_items)} items from 'item sent' section: {', '.join(items_summary)}")
            return consolidated_items
        
        except Exception as e:
            logger.error(f"Error extracting ASOS items from item sent section: {e}", exc_info=True)
            return []

    def _extract_asos_product_details(self, row, img) -> Optional[Dict]:
        """
        Extract product details from an ASOS product row.
        
        Returns:
            Dictionary with unique_id, size, quantity, product_name or None
        """
        try:
            details = {}
            row_text = row.get_text()
            
            # Extract unique_id from image URL
            # Pattern: .../206568080-1-black -> 206568080
            img_src = img.get('src', '')
            unique_id_match = re.search(r'/(\d+)-\d+-', img_src)
            if unique_id_match:
                details['unique_id'] = unique_id_match.group(1)
                logger.debug(f"Found unique ID: {details['unique_id']}")
            else:
                logger.warning("Unique ID not found in ASOS image URL")
                return None
            
            # Extract product name from alt text or link
            product_name = img.get('alt', '')
            if not product_name:
                # Try to find product name in link
                product_link = row.find('a', href=lambda x: x and 'asos.com' in str(x))
                if product_link:
                    product_name = product_link.get_text(strip=True)
            
            if product_name:
                details['product_name'] = product_name
                logger.debug(f"Found product name: {product_name}")
            
            # Extract size and quantity from text
            # Pattern: "Black / WM US 10 / Qty 8" or "LIGHT BLUE / WOMENS 6 - MENS 5 / Qty 1"
            # Size is after "US" or "MENS" or "WOMENS"
            size_qty_match = re.search(
                r'(?:US|MENS|WOMENS)\s+([\d.]+)(?:\s*-\s*MENS\s+[\d.]+)?\s*/\s*Qty\s+(\d+)',
                row_text,
                re.IGNORECASE
            )
            
            if size_qty_match:
                size = size_qty_match.group(1).strip()
                quantity = int(size_qty_match.group(2))
                details['size'] = size
                details['quantity'] = quantity
                logger.debug(f"Found size: {size}, quantity: {quantity}")
            else:
                # Try alternative pattern: just look for Qty
                qty_match = re.search(r'Qty\s+(\d+)', row_text, re.IGNORECASE)
                if qty_match:
                    quantity = int(qty_match.group(1))
                    details['quantity'] = quantity
                    # Try to extract size separately
                    size_match = re.search(r'(?:US|MENS|WOMENS)\s+([\d.]+)', row_text, re.IGNORECASE)
                    if size_match:
                        details['size'] = size_match.group(1).strip()
                    else:
                        logger.warning("Size not found in ASOS row")
                        return None
                else:
                    logger.warning("Quantity not found in ASOS row")
                    return None
            
            # Return only if we have the essential fields
            if details.get('unique_id') and details.get('size') and details.get('quantity'):
                return details
            
            logger.warning(f"Missing essential fields: {details}")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting ASOS product details: {e}", exc_info=True)
            return None

    def _consolidate_items(self, raw_items: List[Dict]) -> List[ASOSOrderItem]:
        """
        Consolidate items by unique_id + size, summing quantities.
        
        Args:
            raw_items: List of raw item dictionaries
        
        Returns:
            List of consolidated ASOSOrderItem objects
        """
        # Group items by unique_id + size
        grouped: Dict[str, Dict] = {}
        
        for item in raw_items:
            unique_id = item.get('unique_id')
            size = item.get('size')
            quantity = item.get('quantity', 1)
            product_name = item.get('product_name')
            
            if not unique_id or not size:
                continue
            
            # Create key for grouping
            key = f"{unique_id}_{size}"
            
            if key in grouped:
                # Add quantity to existing item
                grouped[key]['quantity'] += quantity
                logger.debug(f"Consolidating {unique_id} size {size}: adding qty {quantity}, total now {grouped[key]['quantity']}")
            else:
                # Create new grouped item
                grouped[key] = {
                    'unique_id': unique_id,
                    'size': size,
                    'quantity': quantity,
                    'product_name': product_name
                }
        
        # Convert to ASOSOrderItem objects
        consolidated = []
        for key, item_data in grouped.items():
            consolidated.append(ASOSOrderItem(
                unique_id=item_data['unique_id'],
                size=item_data['size'],
                quantity=item_data['quantity'],
                product_name=item_data.get('product_name')
            ))
        
        logger.info(f"Consolidated {len(raw_items)} raw items into {len(consolidated)} unique items")
        return consolidated
    
    def _extract_shipping_address(self, soup: BeautifulSoup) -> str:
        """
        Extract shipping address from email and normalize it.
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            Normalized shipping address or empty string
        """
        try:
            # Look for "Shipping details" header
            shipping_header = soup.find('h2', string=re.compile(r'Shipping\s+details', re.IGNORECASE))
            
            if not shipping_header:
                logger.debug("Shipping details header not found")
                return ""
            
            # Find all tr elements and look for address after shipping header
            all_trs = soup.find_all('tr')
            found_shipping_header = False
            
            for tr in all_trs:
                tr_text = tr.get_text(strip=True)
                
                # Check if this tr contains the shipping header
                if 'Shipping details' in tr_text:
                    found_shipping_header = True
                    continue
                
                # After finding header, look for tr with address content
                if found_shipping_header:
                    # Check if this tr contains address-like content (street numbers, city names)
                    # But skip if it contains "Order No." or "Order date"
                    if ('Order No.' in tr_text or 'Order date' in tr_text):
                        continue
                    
                    if re.search(r'\d+\s+[A-Z]', tr_text) or 'Lloyd' in tr_text or 'Independence' in tr_text or 'Lane' in tr_text or 'Avenue' in tr_text:
                        # Found address tr - extract all p tags
                        address_td = tr.find('td')
                        if address_td:
                            address_ps = address_td.find_all('p')
                            
                            address_lines = []
                            for p in address_ps:
                                p_text = p.get_text(strip=True)
                                
                                # Skip name (usually capitalized first and last name) and phone number
                                if re.match(r'^[A-Z][a-z]+\s+[A-Z][a-z]+$', p_text) or re.match(r'^\d{10}$', p_text):
                                    continue
                                
                                # Skip "Order No." and "Order date" lines
                                if 'Order No.' in p_text or 'Order date' in p_text:
                                    continue
                                
                                # Stop if we hit "Estimated delivery" or other sections
                                if 'Estimated delivery' in p_text or 'Payment details' in p_text:
                                    break
                                
                                # Collect address lines (street, suite, city, state, zip)
                                # Must contain street number pattern (digits followed by letters) or be a state/city
                                if re.search(r'^\d+\s+[A-Z]', p_text) or 'Oregon' in p_text or 'Independence' in p_text or 'SUITE' in p_text:
                                    address_lines.append(p_text)
                            
                            if address_lines:
                                # Remove "United States" if it's the last line
                                if address_lines[-1].lower() in ['united states', 'usa', 'us']:
                                    address_lines = address_lines[:-1]
                                
                                # Join address lines
                                address_combined = ', '.join(address_lines)
                                normalized = normalize_shipping_address(address_combined)
                                logger.debug(f"Extracted shipping address: {normalized}")
                                return normalized
                    
                    # Stop if we've moved past address section
                    if 'Estimated delivery' in tr_text or 'Payment details' in tr_text:
                        break
            
            logger.debug("Shipping address not found in expected location")
            return ""
        
        except Exception as e:
            logger.error(f"Error extracting shipping address: {e}", exc_info=True)
            return ""
