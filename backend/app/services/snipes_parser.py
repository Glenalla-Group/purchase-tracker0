"""
Snipes Email Parser
Parses order confirmation, shipping, and cancellation emails from Snipes

Order Confirmation:
- From: no-reply@snipesusa.com (prod), glenallagroupc@gmail.com (dev)
- Subject: "Confirmation of Your SNIPES Order #SNP21092730"
- Unique ID: style code from link ...fj4146-100-1000113535.html or image nike_fj4146-100_01.jpg -> fj4146-100

Shipping:
- From: info@t.snipesusa.com (prod), glenallagroupc@gmail.com (dev)
- Subject: "Get Hyped! Your Order Has Shipped"

Cancellation:
- From: info@t.snipesusa.com (prod), glenallagroupc@gmail.com (dev)
- Subject: "Cancelation Update"
- Items: same structure as shipping - unique_id, SKU, Size, Qty
"""

import re
import logging
from typing import List, Optional
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from app.models.email import EmailData
from app.utils.address_utils import normalize_shipping_address

logger = logging.getLogger(__name__)


class SnipesOrderItem(BaseModel):
    unique_id: str = Field(..., description="Unique identifier for the product (e.g., SKU, style code)")
    size: str = Field(..., description="Size of the product")
    quantity: int = Field(..., description="Quantity of the product")
    product_name: Optional[str] = Field(None, description="Name of the product")
    
    def __repr__(self):
        if self.product_name and len(self.product_name) > 50:
            product_display = self.product_name[:50] + "..."
        else:
            product_display = self.product_name or "Unknown"
        return f"<SnipesOrderItem(unique_id={self.unique_id}, size={self.size}, qty={self.quantity}, product={product_display})>"


class SnipesOrderData(BaseModel):
    order_number: str = Field(..., description="The order number")
    items: List[SnipesOrderItem] = Field(..., description="List of items in the order")
    items_count: int = Field(0, description="Total number of items in the order")
    shipping_address: str = Field("", description="Normalized shipping address")

    def __init__(self, **data):
        super().__init__(**data)
        self.items_count = len(self.items)


class SnipesShippingData(BaseModel):
    """Snipes shipping notification data - same structure as Footlocker for processing."""
    order_number: str = Field(..., description="The order number")
    tracking_number: str = Field("", description="Tracking number if available")
    items: List[SnipesOrderItem] = Field(..., description="List of shipped items")


class SnipesCancellationData(BaseModel):
    """Snipes cancellation notification data - partial cancellations, same item structure as shipping."""
    order_number: str = Field(..., description="The order number")
    items: List[SnipesOrderItem] = Field(..., description="List of cancelled items")


class SnipesEmailParser:
    # Email identification - Order Confirmation (Production)
    SNIPES_FROM_EMAIL = "no-reply@snipesusa.com"
    SUBJECT_ORDER_PATTERN = "confirmation of your snipes order"
    
    # Email identification - Development (forwarded emails)
    DEV_SNIPES_ORDER_FROM_EMAIL = "glenallagroupc@gmail.com"
    DEV_SUBJECT_ORDER_PATTERN = r"Fwd:\s*Confirmation of Your SNIPES Order"

    # Shipping (Production: info@t.snipesusa.com, Dev: glenallagroupc)
    SNIPES_SHIPPING_FROM_EMAIL = "info@t.snipesusa.com"
    SUBJECT_SHIPPING_PATTERN = r"get hyped! your order has shipped"
    DEV_SUBJECT_SHIPPING_PATTERN = r"(?:Fwd:\s*)?Get Hyped! Your Order Has Shipped"

    # Cancellation - partial (extractable) and full (manual input)
    SUBJECT_CANCELLATION_PATTERN = r"cancelation\s+update|cancellation\s+update"
    DEV_SUBJECT_CANCELLATION_PATTERN = r"(?:Fwd:\s*)?Cancelation Update"
    # Full cancellation: "Update on Your SNIPES Order" - no extractable data, needs manual order_number
    SUBJECT_FULL_CANCELLATION_PATTERN = r"update\s+on\s+your\s+snipes\s+order"
    DEV_SUBJECT_FULL_CANCELLATION_PATTERN = r"(?:Fwd:\s*)?Update on Your SNIPES Order"

    def __init__(self):
        """Initialize the Snipes email parser."""
        from app.config.settings import get_settings
        self.settings = get_settings()
    
    @property
    def order_from_email(self) -> str:
        """Get the appropriate from email address based on environment."""
        if self.settings.is_development:
            return self.DEV_SNIPES_ORDER_FROM_EMAIL
        return self.SNIPES_FROM_EMAIL
    
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
            # For Gmail queries, use a simpler pattern that Gmail can understand
            return "Fwd: Confirmation of Your SNIPES Order"
        return "Confirmation of Your SNIPES Order"

    def is_snipes_email(self, email_data: EmailData) -> bool:
        """
        Check if email is from Snipes.
        
        In dev mode, multiple retailers forward from glenallagroupc. Require either:
        - Subject contains "SNIPES Order" (very Snipes-specific), or
        - HTML contains "snipesusa" (Snipes branding)
        to avoid Snipes claiming other retailers' forwarded emails.
        """
        sender_lower = email_data.sender.lower()
        
        # Production: direct from Snipes (order or shipping)
        if self.SNIPES_FROM_EMAIL.lower() in sender_lower:
            return True
        if self.SNIPES_SHIPPING_FROM_EMAIL.lower() in sender_lower:
            return True
        
        # Development: forwarded from glenallagroupc - require subject or HTML confirmation
        if self.settings.is_development:
            if self.DEV_SNIPES_ORDER_FROM_EMAIL.lower() not in sender_lower:
                return False
            subject = (email_data.subject or "").lower()
            # Subject "Confirmation of Your SNIPES Order #SNP..." is Snipes-specific
            if "snipes order" in subject:
                return True
            html = (email_data.html_content or "").lower()
            if "snipesusa" in html:
                return True
            # Shipping subject "Get Hyped! Your Order Has Shipped" is Snipes-specific
            if "your order has shipped" in subject:
                return True
            # Cancellation subject "Cancelation Update" or "Update on Your SNIPES Order" is Snipes-specific
            if "cancelation update" in subject or "cancellation update" in subject:
                return True
            if "update on your snipes order" in subject:
                return True
            return False
        
        return False

    @property
    def update_from_email(self) -> str:
        """From address for shipping emails (prod vs dev)."""
        if self.settings.is_development:
            return self.DEV_SNIPES_ORDER_FROM_EMAIL
        return self.SNIPES_SHIPPING_FROM_EMAIL

    @property
    def shipping_subject_query(self) -> str:
        """Subject query for Gmail shipping search."""
        return 'subject:"Get Hyped! Your Order Has Shipped"'

    @property
    def cancellation_subject_query(self) -> str:
        """Subject query for Gmail cancellation search (typo: Cancelation)."""
        return 'subject:"Cancelation Update"'

    @property
    def full_cancellation_subject_query(self) -> str:
        """Subject query for Gmail full cancellation search (no extractable data)."""
        return 'subject:"Update on Your SNIPES Order"'

    def is_shipping_email(self, email_data: EmailData) -> bool:
        """Check if email is a Snipes shipping notification."""
        subject_lower = (email_data.subject or "").lower()
        return bool(re.search(self.SUBJECT_SHIPPING_PATTERN, subject_lower, re.IGNORECASE))

    def is_cancellation_email(self, email_data: EmailData) -> bool:
        """Check if email is a Snipes cancellation notification (partial or full)."""
        subject_lower = (email_data.subject or "").lower()
        if re.search(self.SUBJECT_CANCELLATION_PATTERN, subject_lower, re.IGNORECASE):
            return True
        if re.search(self.SUBJECT_FULL_CANCELLATION_PATTERN, subject_lower, re.IGNORECASE):
            return True
        return False

    def is_full_cancellation_email(self, email_data: EmailData) -> bool:
        """Check if email is Snipes full cancellation (Update on Your SNIPES Order - no extractable data)."""
        subject_lower = (email_data.subject or "").lower()
        return bool(re.search(self.SUBJECT_FULL_CANCELLATION_PATTERN, subject_lower, re.IGNORECASE))

    def parse_cancellation_email(self, email_data: EmailData) -> Optional[SnipesCancellationData]:
        """
        Parse Snipes cancellation notification email.
        
        Subject: "Cancelation Update"
        Order: SNP15751775
        Items: same structure as shipping - unique_id from image (nike_454350-700_01.jpg -> 454350-700), SKU, Size, Qty
        """
        try:
            html_content = email_data.html_content
            if not html_content:
                logger.error("No HTML content in Snipes cancellation email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            order_number = self._extract_shipping_order_number(soup)
            if not order_number:
                logger.error("Failed to extract order number from Snipes cancellation email")
                return None
            
            items = self._extract_shipping_items(soup)  # Same HTML structure as shipping
            if not items:
                logger.error("Failed to extract items from Snipes cancellation email")
                return None
            
            logger.info(f"Parsed Snipes cancellation: order={order_number}, items={len(items)}")
            return SnipesCancellationData(order_number=order_number, items=items)
        except Exception as e:
            logger.error(f"Error parsing Snipes cancellation email: {e}", exc_info=True)
            return None

    def parse_shipping_email(self, email_data: EmailData) -> Optional[SnipesShippingData]:
        """
        Parse Snipes shipping notification email.
        
        Subject: "Get Hyped! Your Order Has Shipped"
        Order: SNP22181213
        Items: unique_id from image (nike_fj4146-100_01.jpg -> fj4146-100), SKU, Size, Qty
        """
        try:
            html_content = email_data.html_content
            if not html_content:
                logger.error("No HTML content in Snipes shipping email")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            order_number = self._extract_shipping_order_number(soup)
            if not order_number:
                logger.error("Failed to extract order number from Snipes shipping email")
                return None
            
            tracking_number = self._extract_shipping_tracking_number(soup)
            if not tracking_number:
                tracking_number = "Unknown"
            
            items = self._extract_shipping_items(soup)
            if not items:
                logger.error("Failed to extract items from Snipes shipping email")
                return None
            
            logger.info(f"Parsed Snipes shipping: order={order_number}, tracking={tracking_number}, items={len(items)}")
            return SnipesShippingData(
                order_number=order_number,
                tracking_number=tracking_number or "",
                items=items
            )
        except Exception as e:
            logger.error(f"Error parsing Snipes shipping email: {e}", exc_info=True)
            return None

    def _extract_shipping_order_number(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract order number from shipping email (Order Number: SNP22181213)."""
        text = soup.get_text()
        match = re.search(r'Order\s+Number:\s*(SNP\d+)', text, re.IGNORECASE)
        if match:
            return match.group(1)
        match = re.search(r'\b(SNP\d{8,})\b', text)
        if match:
            return match.group(1)
        return None

    def _extract_shipping_tracking_number(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract tracking number (UPS 1Z..., etc.)."""
        text = soup.get_text()
        match = re.search(r'1Z[A-Z0-9]{16}', text, re.IGNORECASE)
        if match:
            return match.group(0)
        return None

    def _extract_shipping_items(self, soup: BeautifulSoup) -> List[SnipesOrderItem]:
        """Extract shipped items - unique_id from image (fj4146-100), Size, Qty from adjacent cell."""
        items = []
        try:
            # Find all imgs with snipesusa in src (product images)
            imgs = soup.find_all('img', src=lambda x: x and 'snipesusa.com' in str(x))
            for img in imgs:
                src = img.get('src', '')
                # Extract unique_id: nike_fj4146-100_01.jpg -> fj4146-100 (style code, same as order confirmation)
                img_match = re.search(r'/([a-z]+)_([a-z0-9-]+)_(?:V\d+|0\d+)\.jpg', src, re.IGNORECASE)
                if not img_match:
                    alt_match = re.search(r'/([a-z0-9-]+)_(?:V\d+|0\d+)\.jpg', src, re.IGNORECASE)
                    if not alt_match:
                        continue
                    unique_id = alt_match.group(1)
                else:
                    unique_id = img_match.group(2)
                
                # Find parent th/td, then sibling with SKU/Size/Qty
                cell = img.find_parent(['th', 'td'])
                if not cell:
                    continue
                
                # Get the parent row (tr)
                row = cell.find_parent('tr')
                if not row:
                    continue
                
                # Find the details cell - next th/td in same row, or look in row for SKU/Size/Qty
                detail_cells = row.find_all(['th', 'td'])
                details_text = ""
                for dc in detail_cells:
                    if dc != cell:
                        details_text = dc.get_text()
                        if 'SKU:' in details_text or 'Size:' in details_text:
                            break
                
                if not details_text:
                    continue
                
                # Extract Size: 11 or Size: 11.5
                size_match = re.search(r'Size:\s*([^\s\n]+)', details_text, re.IGNORECASE)
                size = size_match.group(1).strip() if size_match else ""
                
                # Extract Qty: 1 or Qty: 3
                qty_match = re.search(r'Qty:\s*(\d+)', details_text, re.IGNORECASE)
                quantity = int(qty_match.group(1)) if qty_match else 1
                
                # Product name - first div with font-size:18px in details (e.g. "Air Force 1 '07")
                product_name = None
                for div in row.find_all('div', style=re.compile(r'font-size:18px', re.I)):
                    txt = div.get_text(strip=True)
                    if txt and 'SKU:' not in txt and 'Size:' not in txt and 'Qty:' not in txt:
                        product_name = txt
                        break
                
                if unique_id and size:
                    items.append(SnipesOrderItem(
                        unique_id=unique_id,
                        size=size,
                        quantity=quantity,
                        product_name=product_name
                    ))
            
            # Deduplicate (unique_id, size) - sum quantities for responsive duplicates
            seen = {}
            for item in items:
                key = (item.unique_id, item.size)
                if key in seen:
                    seen[key].quantity += item.quantity
                else:
                    seen[key] = item
            return list(seen.values())
        except Exception as e:
            logger.error(f"Error extracting Snipes shipping items: {e}", exc_info=True)
            return []

    def is_order_confirmation_email(self, email_data: EmailData) -> bool:
        """Check if email is an order confirmation"""
        subject_lower = (email_data.subject or "").lower()
        
        # Use environment-aware subject pattern
        if re.search(self.order_subject_pattern, subject_lower, re.IGNORECASE):
            return True
        
        # Also check for the base pattern (for forwarded emails that might have variations)
        if re.search(self.SUBJECT_ORDER_PATTERN, subject_lower, re.IGNORECASE):
            return True
        
        return False

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
            
            # Extract order number from subject, with fallback to HTML body
            order_number = self._extract_order_number(email_data.subject, soup)
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
            
            # Extract shipping address
            shipping_address = self._extract_shipping_address(soup)
            if shipping_address:
                logger.info(f"Extracted shipping address: {shipping_address}")
            
            return SnipesOrderData(order_number=order_number, items=items, shipping_address=shipping_address)
        
        except Exception as e:
            logger.error(f"Error parsing Snipes email: {e}", exc_info=True)
            return None

    def _extract_order_number(self, subject: str, soup: BeautifulSoup = None) -> Optional[str]:
        """
        Extract order number from Snipes email subject or HTML body.
        
        Subject format: Confirmation of Your SNIPES Order #SNP21092730
        HTML format: Order Number section with <span>SNP22349214</span>
        Extract: SNP21092730
        
        Args:
            subject: Email subject string
            soup: BeautifulSoup object of email HTML (optional, for fallback)
        
        Returns:
            Order number or None
        """
        try:
            # First try to extract from subject
            # Pattern: Confirmation of Your SNIPES Order #SNP21092730
            match = re.search(r'Order\s+#(SNP\d+)', subject, re.IGNORECASE)
            if match:
                order_number = match.group(1)
                logger.debug(f"Found Snipes order number in subject: {order_number}")
                return order_number
            
            # Fallback: extract from HTML body if soup is provided
            if soup:
                # Look for "Order Number" header followed by the order number
                order_number_header = soup.find('strong', string=re.compile(r'Order\s+Number', re.IGNORECASE))
                if order_number_header:
                    # Find the parent container
                    container = order_number_header.find_parent(['td', 'div'])
                    if container:
                        # Look for SNP pattern in the container
                        container_text = container.get_text()
                        order_match = re.search(r'(SNP\d+)', container_text, re.IGNORECASE)
                        if order_match:
                            order_number = order_match.group(1)
                            logger.debug(f"Found Snipes order number in HTML body: {order_number}")
                            return order_number
                
                # Alternative: search for SNP pattern anywhere in the HTML
                html_text = soup.get_text()
                order_match = re.search(r'\b(SNP\d{8,})\b', html_text, re.IGNORECASE)
                if order_match:
                    order_number = order_match.group(1)
                    logger.debug(f"Found Snipes order number in HTML (fallback): {order_number}")
                    return order_number
            
            logger.warning("Order number not found in Snipes email subject or HTML")
            return None
        
        except Exception as e:
            logger.error(f"Error extracting Snipes order number: {e}")
            return None

    def _extract_items(self, soup: BeautifulSoup) -> List[SnipesOrderItem]:
        """
        Extract order items from Snipes email.
        
        Snipes email structure:
        - Products in table rows with class containing "tablecell-image-wrapper"
        - Product name in <p> with font-weight: bold
        - Size after gender indicator (e.g., "Men's / 10.5")
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
            # Look for product image cells - class contains "tablecell-image-wrapper"
            # The actual class has a prefix like "m_-2892033387574715046tablecell-image-wrapper"
            # Find all td elements and filter by class name
            all_tds = soup.find_all('td')
            product_image_cells = [
                td for td in all_tds 
                if td.get('class') and any('tablecell-image-wrapper' in str(cls) for cls in td.get('class', []))
            ]
            
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
        
        # Log items with ID, size, and quantity (product names come from OA Sourcing table)
        if items:
            items_summary = [f"(ID: {item.unique_id}, Size: {item.size}, Qty: {item.quantity})" for item in items]
            logger.info(f"[Snipes] Extracted {len(items)} items: {', '.join(items_summary)}")
        return items

    def _extract_snipes_product_details(self, row) -> Optional[dict]:
        """
        Extract product details from a Snipes product row.
        
        Expected format:
        - Product name in <p> with font-weight: bold
        - Size after gender indicator (e.g., "Men's / 10.5")
        - Quantity: "Quantity: 4"
        - SKU: "SKU: 15408700018"
        
        Returns:
            Dictionary with unique_id, size, quantity, product_name or None
        """
        try:
            details = {}
            row_text = row.get_text()
            
            # Find product name - look for <p> tag with font-weight: bold
            # Can be in style attribute or in a style tag
            product_name_tag = row.find('p', style=lambda x: x and ('font-weight: bold' in str(x) or 'font-weight:bold' in str(x)))
            if product_name_tag:
                product_name = product_name_tag.get_text(strip=True)
                details['product_name'] = product_name
                logger.debug(f"Found product name: {product_name}")
            else:
                logger.warning("Product name not found in Snipes row")
                return None
            
            # Extract unique_id from image URL or product link
            # Priority 1: Extract from product link URL (if exists)
            # Pattern: ...fq8249-104-1000123364.html -> 1000123364
            product_link = row.find('a', href=lambda x: x and 'snipesusa.com' in str(x) and '.html' in str(x))
            if product_link:
                href = product_link.get('href', '')
                # Prefer style code (e.g. fj4146-100) - same as shipping, matches OA Sourcing
                style_match = re.search(r'-([a-z0-9-]+)-\d+\.html', href, re.IGNORECASE)
                if style_match:
                    unique_id = style_match.group(1)
                    details['unique_id'] = unique_id
                    logger.debug(f"Found unique ID (style code) from product URL: {unique_id}")
                else:
                    url_match = re.search(r'-(\d+)\.html', href)
                    if url_match:
                        unique_id = url_match.group(1)
                        details['unique_id'] = unique_id
                        logger.debug(f"Found unique ID from product URL: {unique_id}")
            
            # Priority 2: Extract from image URL if no product link found
            if 'unique_id' not in details:
                # Find image in the row
                img = row.find('img', src=lambda x: x and 'snipesusa.com' in str(x))
                if img:
                    img_src = img.get('src', '')
                    # Pattern: nike_fq8249-104_01.jpg or nike_fq8249-104_V1.jpg -> fq8249-104
                    # Extract the style code from filename pattern: {brand}_{style_code}_{variant}.jpg
                    img_match = re.search(r'/([a-z]+)_([a-z0-9-]+)_(?:V\d+|0\d+)\.jpg', img_src, re.IGNORECASE)
                    if img_match:
                        unique_id = img_match.group(2)  # Extract style code (e.g., fq8249-104)
                        details['unique_id'] = unique_id
                        logger.debug(f"Found unique ID from image URL: {unique_id}")
                    else:
                        # Alternative pattern: just look for style code pattern in filename
                        alt_match = re.search(r'/([a-z0-9-]+)_(?:V\d+|0\d+)\.jpg', img_src, re.IGNORECASE)
                        if alt_match:
                            unique_id = alt_match.group(1)
                            details['unique_id'] = unique_id
                            logger.debug(f"Found unique ID from image URL (alt pattern): {unique_id}")
            
            if 'unique_id' not in details:
                logger.warning("Unique ID not found in Snipes row (neither from URL nor image)")
                return None
            
            # Extract size - look for pattern after gender/category
            # Format: "Men's / 10.5" or "Unisex / 4.5Y" etc.
            # The size comes after the slash and before <br> or end of line
            # Pattern: Men's / 10.5<br> or Men's / 10.5\n
            size_match = re.search(r'(?:Unisex|Men\'?s?|Women\'?s?|Kids?\'?s?)\s*/\s*([^\s<]+)', row_text, re.IGNORECASE)
            if size_match:
                size = size_match.group(1).strip()
                # Clean up any trailing characters
                size = re.sub(r'[<>\n\r]+', '', size).strip()
                details['size'] = size
                logger.debug(f"Found size: {size}")
            else:
                # Try alternative pattern - look for size after "Men's /" or similar
                # Sometimes it's in separate spans: <span>Men's / </span><span>10.5</span>
                size_spans = row.find_all('span')
                for i, span in enumerate(size_spans):
                    span_text = span.get_text(strip=True)
                    # Check if this span contains a gender indicator
                    if re.search(r'(?:Men\'?s?|Women\'?s?|Kids?\'?s?|Unisex)\s*/', span_text, re.IGNORECASE):
                        # Next span should contain the size
                        if i + 1 < len(size_spans):
                            next_span = size_spans[i + 1]
                            size_text = next_span.get_text(strip=True)
                            # Check if it looks like a size
                            if re.match(r'^\d+(\.\d+)?Y?$', size_text):
                                details['size'] = size_text
                                logger.debug(f"Found size from spans: {size_text}")
                                break
                
                if 'size' not in details:
                    # Try standalone size pattern
                    size_match2 = re.search(r'\b(\d+(?:\.\d+)?Y?)\b', row_text)
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
    
    def _extract_shipping_address(self, soup: BeautifulSoup) -> str:
        """
        Extract shipping address from email and normalize it.
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            Normalized shipping address or empty string
        """
        try:
            # Look for "Shipping Address" header
            shipping_address_header = soup.find('strong', string=re.compile(r'Shipping\s+Address', re.IGNORECASE))
            
            if shipping_address_header:
                # Find the parent td that contains the address section
                address_td = shipping_address_header.find_parent('td')
                
                if address_td:
                    # Get all text from the td
                    address_text = address_td.get_text(separator='\n', strip=True)
                    
                    # Parse line by line to find address components
                    lines = [line.strip() for line in address_text.split('\n') if line.strip()]
                    
                    address_lines = []
                    found_shipping_header = False
                    
                    for i, line in enumerate(lines):
                        # Mark when we find the Shipping Address header
                        if 'Shipping Address' in line:
                            found_shipping_header = True
                            continue
                        
                        # Only process lines after the header
                        if not found_shipping_header:
                            continue
                        
                        # Skip phone number lines
                        if 'Phone:' in line or re.match(r'^\d{10}$', line):
                            break
                        
                        # Skip "United States"
                        if line.lower() in ['united states', 'usa', 'us']:
                            continue
                        
                        # Look for address lines (contain numbers or city/state/zip pattern)
                        if re.search(r'\d+', line) or re.search(r',\s*[A-Z]{2}\s+\d{5}', line):
                            address_lines.append(line)
                            # Stop after we have street and city/state/zip
                            if len(address_lines) >= 2:
                                break
                    
                    if address_lines:
                        address_combined = ', '.join(address_lines)
                        logger.debug(f"Raw address before normalization: {address_combined}")
                        normalized = normalize_shipping_address(address_combined)
                        logger.debug(f"Extracted shipping address: {normalized}")
                        return normalized
                    
                    # Fallback: look for any pattern matching street + city/state/zip
                    address_match = re.search(
                        r'(\d+\s+[^\n,]+(?:Ln|Lane|St|Street|Ave|Avenue|Rd|Road|Dr|Drive|Blvd|Boulevard|Way|Ct|Court|Pl|Place|Pkwy|Parkway|Ste|Suite)[^\n]*)\s*\n\s*([^\n]+,\s*[A-Z]{2}\s+\d{5})',
                        address_text,
                        re.IGNORECASE | re.MULTILINE
                    )
                    
                    if address_match:
                        street = address_match.group(1).strip()
                        city_state_zip = address_match.group(2).strip()
                        address_combined = f"{street}, {city_state_zip}"
                        normalized = normalize_shipping_address(address_combined)
                        logger.debug(f"Extracted shipping address (regex fallback): {normalized}")
                        return normalized
            
            # Fallback: try regex pattern matching
            text = soup.get_text(separator='\n')
            
            # Look for address pattern: Street\nCity, State ZIP
            address_match = re.search(
                r'(\d+[^,\n]+(?:St|Street|Ave|Avenue|Rd|Road|Ln|Lane|Dr|Drive|Blvd|Boulevard|Ste|Suite)[^,\n]*)\s*\n\s*([^,\n]+,\s*[A-Z]{2}\s+\d{5})',
                text,
                re.IGNORECASE | re.MULTILINE
            )
            
            if address_match:
                street = address_match.group(1).strip()
                city_state_zip = address_match.group(2).strip()
                address_combined = f"{street}, {city_state_zip}"
                normalized = normalize_shipping_address(address_combined)
                logger.debug(f"Extracted shipping address (fallback): {normalized}")
                return normalized
            
            return ""
        
        except Exception as e:
            logger.error(f"Error extracting shipping address: {e}", exc_info=True)
            return ""

