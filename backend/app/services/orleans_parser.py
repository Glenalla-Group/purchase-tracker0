"""
Orleans Shoe Co Email Parser
Parses order confirmation emails from Orleans Shoe Co using BeautifulSoup

Email Format:
- From: tore+15639833@t.shopifyemail.com (production)
- From: glenallagroupc@gmail.com (dev - forwarded emails)
- Subject: "Order confirmation" or similar
- Order Number: Extract from HTML (e.g., "103812")

HTML Structure:
- Products are listed in tables
- Each product has:
  - Product image: <img src="https://cdn.shopify.com/.../products/O6_15a34896-b598-4985-a6e2-03cf6cafbbdf_compact_cropped.jpg">
  - Product name: "On Women's Cloudgo Rose Magnet - 6.5 M × 2"
  - Size: "6.5 M" in a span with color:#999
  - Quantity: Embedded in product name as "× 2" or "× 1"

Unique ID Extraction:
- Format: Extract from product link URL (e.g., "on-womens-cloudgo-rose-magnet")
- Pattern: Extract from URL path like /products/on-womens-cloudgo-rose-magnet
- If no product link found, extract from product name by converting to URL-friendly format
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


class OrleansOrderItem(BaseModel):
    unique_id: str = Field(..., description="Unique identifier for the product (e.g., on-womens-cloudgo-rose-magnet)")
    size: str = Field(..., description="Size of the product")
    quantity: int = Field(..., description="Quantity of the product")
    product_name: Optional[str] = Field(None, description="Name of the product")
    
    def __repr__(self):
        if self.product_name and len(self.product_name) > 50:
            product_display = self.product_name[:50] + "..."
        else:
            product_display = self.product_name or "Unknown"
        return f"<OrleansOrderItem(unique_id={self.unique_id}, size={self.size}, qty={self.quantity}, product={product_display})>"


class OrleansOrderData(BaseModel):
    order_number: str = Field(..., description="The order number")
    items: List[OrleansOrderItem] = Field(..., description="List of items in the order")
    items_count: int = Field(0, description="Total number of items in the order")
    shipping_address: str = Field("", description="Normalized shipping address")

    def __init__(self, **data):
        super().__init__(**data)
        self.items_count = len(self.items)


class OrleansCancellationData(BaseModel):
    """Represents Orleans Shoe Co cancellation notification data"""
    order_number: str = Field(..., description="The order number")
    items: List[OrleansOrderItem] = Field(..., description="List of cancelled items")
    
    def __repr__(self):
        return f"<OrleansCancellationData(order={self.order_number}, items={len(self.items)})>"


class OrleansEmailParser:
    # Email identification - Order Confirmation (Production)
    ORLEANS_FROM_EMAIL = "store+15639833@t.shopifyemail.com"
    SUBJECT_ORDER_PATTERN = r"order\s+confirmation|thank\s+you\s+for\s+your\s+purchase"
    
    # Email identification - Cancellation (Production)
    SUBJECT_CANCELLATION_PATTERN = r"order.*cancel|your\s+order\s+has\s+been\s+cancel"
    
    # Email identification - Development (forwarded emails)
    DEV_ORLEANS_ORDER_FROM_EMAIL = "glenallagroupc@gmail.com"
    DEV_SUBJECT_ORDER_PATTERN = r"(?:Fwd:\s*)?(?:order\s+confirmation|order|orleans|orleans\s+shoe)"
    DEV_SUBJECT_CANCELLATION_PATTERN = r"(?:Fwd:\s*)?(?:order.*cancel|your\s+order\s+has\s+been\s+cancel)"

    def __init__(self):
        """Initialize the Orleans Shoe Co email parser."""
        self.settings = get_settings()
    
    @property
    def order_from_email(self) -> str:
        """Get the appropriate from email address based on environment."""
        if self.settings.is_development:
            return self.DEV_ORLEANS_ORDER_FROM_EMAIL
        return self.ORLEANS_FROM_EMAIL
    
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
            return "orleans shoe order"
        return "order confirmation"
    
    def is_orleans_email(self, email_data: EmailData) -> bool:
        """
        Check if the email is from Orleans Shoe Co.
        
        Args:
            email_data: Email data to check
        
        Returns:
            True if the email is from Orleans Shoe Co, False otherwise
        """
        sender_lower = email_data.sender.lower()
        subject = email_data.subject.lower() if email_data.subject else ""
        
        # Check production email
        if self.ORLEANS_FROM_EMAIL.lower() in sender_lower:
            return True
        
        # Check dev email with subject pattern
        if self.DEV_ORLEANS_ORDER_FROM_EMAIL.lower() in sender_lower:
            if re.search(self.DEV_SUBJECT_ORDER_PATTERN, subject, re.IGNORECASE):
                return True
        
        return False
    
    def is_order_confirmation_email(self, email_data: EmailData) -> bool:
        """
        Check if the email is an order confirmation email from Orleans Shoe Co.
        
        Args:
            email_data: Email data to check
        
        Returns:
            True if the email is an order confirmation, False otherwise
        """
        if not self.is_orleans_email(email_data):
            return False
        
        # Make sure it's not a cancellation email
        if self.is_cancellation_email(email_data):
            return False
        
        subject = email_data.subject.lower() if email_data.subject else ""
        
        # Check subject pattern
        if re.search(self.order_subject_pattern, subject, re.IGNORECASE):
            return True
        
        # Also check HTML content for order confirmation indicators
        if email_data.html_content:
            html_lower = email_data.html_content.lower()
            if "order confirmation" in html_lower or ("order #" in html_lower and "cancel" not in html_lower):
                return True
        
        return False
    
    def is_cancellation_email(self, email_data: EmailData) -> bool:
        """
        Check if the email is a cancellation notification from Orleans Shoe Co.
        
        Args:
            email_data: Email data to check
        
        Returns:
            True if the email is a cancellation notification, False otherwise
        """
        if not self.is_orleans_email(email_data):
            return False
        
        subject = email_data.subject.lower() if email_data.subject else ""
        
        # Check subject pattern
        pattern = self.DEV_SUBJECT_CANCELLATION_PATTERN if self.settings.is_development else self.SUBJECT_CANCELLATION_PATTERN
        if re.search(pattern, subject, re.IGNORECASE):
            return True
        
        # Also check HTML content for cancellation indicators
        if email_data.html_content:
            html_lower = email_data.html_content.lower()
            if any(phrase in html_lower for phrase in [
                "your order has been canceled",
                "your order has been cancelled",
                "removed items",
                "order has been canceled"
            ]):
                return True
        
        return False
    
    def _extract_unique_id_from_product_link(self, product_link_url: Optional[str], product_name: Optional[str] = None) -> Optional[str]:
        """
        Extract unique ID from Orleans product link URL or derive from product name.
        
        Pattern: Extract from URL path like /products/on-womens-cloudgo-rose-magnet
        If no link, derive from product name by converting to URL-friendly format
        
        Args:
            product_link_url: Product link URL (may be None)
            product_name: Product name as fallback
        
        Returns:
            Unique ID string or None if not found
        """
        try:
            # Try to extract from product link URL first
            if product_link_url:
                # Handle Gmail proxy URLs - extract actual URL after #
                if "#" in product_link_url:
                    parts = product_link_url.split("#")
                    if len(parts) > 1:
                        product_link_url = parts[-1]
                
                # Extract from URL path like /products/on-womens-cloudgo-rose-magnet
                # Pattern: /products/([^/?]+)
                pattern = r'/products/([^/?]+)'
                match = re.search(pattern, product_link_url.lower())
                
                if match:
                    unique_id = match.group(1)
                    logger.debug(f"Extracted unique ID '{unique_id}' from product link URL: {product_link_url}")
                    return unique_id
            
            # Fallback: Derive from product name
            if product_name:
                # Convert product name to URL-friendly format
                # Example: "On Women's Cloudgo Rose Magnet - 6.5 M" -> "on-womens-cloudgo-rose-magnet"
                # Remove size and quantity info first
                cleaned_name = re.sub(r'\s*-\s*\d+(?:\.\d+)?\s*[MW]?\s*×\s*\d+\s*$', '', product_name)
                cleaned_name = re.sub(r'\s*-\s*\d+(?:\.\d+)?\s*[MW]?\s*$', '', cleaned_name)
                
                # Convert to lowercase and replace spaces/special chars with hyphens
                unique_id = re.sub(r'[^\w\s-]', '', cleaned_name.lower())
                unique_id = re.sub(r'\s+', '-', unique_id)
                unique_id = re.sub(r'-+', '-', unique_id).strip('-')
                
                logger.debug(f"Derived unique ID '{unique_id}' from product name: {product_name}")
                return unique_id
            
            logger.warning(f"Could not extract unique ID from product link or name")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting unique ID: {e}", exc_info=True)
            return None
    
    def _extract_orleans_product_details(self, product_row) -> Optional[OrleansOrderItem]:
        """
        Extract product details from an Orleans Shoe Co product row.
        
        Args:
            product_row: BeautifulSoup element containing product information
        
        Returns:
            OrleansOrderItem object or None
        """
        try:
            # Find product image
            img = product_row.find('img', src=re.compile(r'cdn\.shopify\.com'))
            
            if not img:
                logger.warning("Could not find product image")
                return None
            
            img_src = img.get('src', '')
            
            # Find product name - look for span with font-size:16px and font-weight:600
            product_name = None
            product_name_span = None
            
            # Try multiple patterns to find product name span
            spans = product_row.find_all('span')
            for span in spans:
                style = span.get('style', '')
                if 'font-size:16px' in style and 'font-weight:600' in style:
                    span_text = span.get_text(strip=True)
                    # Check if it contains the product name pattern (has × symbol)
                    if '×' in span_text:
                        product_name_span = span
                        break
            
            if product_name_span:
                raw_product_name = product_name_span.get_text(strip=True)
                # Extract product name and quantity
                # Format: "On Women's Cloudgo Rose Magnet - 6.5 M × 2"
                # Remove quantity part (× 2 or × 1) and size info
                product_name = re.sub(r'\s*-\s*\d+(?:\.\d+)?\s*[MW]?\s*×\s*\d+\s*$', '', raw_product_name).strip()
                # Also remove standalone size at the end if present
                product_name = re.sub(r'\s*-\s*\d+(?:\.\d+)?\s*[MW]?\s*$', '', product_name).strip()
            
            # Find product link - look for link with orleansshoes.com/products
            product_link_url = None
            product_link = product_row.find('a', href=re.compile(r'orleansshoes\.com.*products'))
            if product_link:
                product_link_url = product_link.get('href', '')
            
            # Extract unique ID from product link or product name
            unique_id = self._extract_unique_id_from_product_link(product_link_url, product_name)
            
            if not unique_id:
                logger.warning(f"Could not extract unique ID from product link or name")
                return None
            
            # Find size - look for span with color:#999
            size = None
            size_spans = product_row.find_all('span', style=re.compile(r'color:#999'))
            for span in size_spans:
                span_text = span.get_text(strip=True)
                # Size format: "6.5 M" - extract just the number part
                size_match = re.match(r'^(\d+(?:\.\d+)?)\s*[MW]?', span_text)
                if size_match:
                    size = size_match.group(1)
                    break
            
            if not size:
                size = "Unknown"
            
            # Find quantity - extract from product name if available, otherwise default to 1
            quantity = 1
            if product_name_span:
                raw_product_name = product_name_span.get_text(strip=True)
                qty_match = re.search(r'×\s*(\d+)', raw_product_name)
                if qty_match:
                    quantity = int(qty_match.group(1))
            
            return OrleansOrderItem(
                unique_id=unique_id,
                size=size,
                quantity=quantity,
                product_name=product_name
            )
            
        except Exception as e:
            logger.error(f"Error extracting Orleans product details: {e}", exc_info=True)
            return None
    
    def _extract_order_number(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract order number from HTML.
        
        Args:
            soup: BeautifulSoup object
        
        Returns:
            Order number string or None
        """
        try:
            # Look for "Order #" followed by number
            # Format: <span style="font-size:16px"> Order #103812 </span>
            order_spans = soup.find_all('span', string=re.compile(r'Order\s+#\s*\d+', re.IGNORECASE))
            
            for span in order_spans:
                text = span.get_text()
                match = re.search(r'Order\s+#\s*(\d+)', text, re.IGNORECASE)
                if match:
                    order_number = match.group(1)
                    logger.debug(f"Extracted order number: {order_number}")
                    return order_number
            
            # Fallback: Look for text containing "Order #"
            order_text = soup.find(string=re.compile(r'Order\s+#', re.IGNORECASE))
            if order_text:
                match = re.search(r'Order\s+#\s*(\d+)', order_text, re.IGNORECASE)
                if match:
                    order_number = match.group(1)
                    logger.debug(f"Extracted order number (fallback): {order_number}")
                    return order_number
            
            logger.warning("Could not extract order number")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting order number: {e}", exc_info=True)
            return None
    
    def _extract_products(self, soup: BeautifulSoup) -> List[OrleansOrderItem]:
        """
        Extract products from HTML.
        
        Args:
            soup: BeautifulSoup object
        
        Returns:
            List of OrleansOrderItem objects
        """
        items = []
        
        try:
            # Find all product images from shopify
            product_images = soup.find_all('img', src=re.compile(r'cdn\.shopify\.com.*(?:files|products)'))
            
            logger.debug(f"Found {len(product_images)} Shopify images")
            
            seen_products = set()
            
            for img in product_images:
                # Exclude non-product images
                img_src = img.get('src', '')
                if any(exclude in img_src.lower() for exclude in ['logo', 'spacer', 'icon', 'arrow', 'facebook', 'twitter', 'instagram', 'discounttag', 'email_settings']):
                    logger.debug(f"Skipping non-product image: {img_src[:100]}")
                    continue
                
                # Check if this is a product image (has product name nearby)
                parent = img.find_parent(['td', 'tr'])
                if not parent:
                    logger.debug(f"No parent found for image: {img_src[:100]}")
                    continue
                
                # Find the containing table row
                product_row = img.find_parent('tr')
                if not product_row:
                    product_row = parent.find_parent('tr')
                if not product_row:
                    product_row = parent
                
                # Check if this row contains product information
                # Look for product name span with × symbol or size span
                row_text = product_row.get_text()
                has_product_name = bool(re.search(r'×\s*\d+', row_text))
                has_size = bool(re.search(r'\b\d+(?:\.\d+)?\s*[MW]?\b', row_text))
                
                if not (has_product_name or has_size):
                    logger.debug(f"No product indicators found in row text for image: {img_src[:100]}")
                    continue
                
                logger.debug(f"Processing product image: {img_src[:100]}")
                
                # Try to extract size from nearby spans for uniqueness
                size_key = "unknown"
                size_spans = product_row.find_all('span', style=re.compile(r'color:#999'))
                for span in size_spans:
                    span_text = span.get_text(strip=True)
                    size_match = re.match(r'^(\d+(?:\.\d+)?)\s*[MW]?', span_text)
                    if size_match:
                        size_key = size_match.group(1)
                        break
                
                product_id = f"{img_src}_{size_key}"
                
                if product_id in seen_products:
                    continue
                seen_products.add(product_id)
                
                try:
                    # Extract product details from the product row
                    product_details = self._extract_orleans_product_details(product_row)
                    
                    if product_details:
                        items.append(product_details)
                        logger.debug(f"Successfully extracted product: {product_details.product_name}, unique_id: {product_details.unique_id}")
                    else:
                        logger.debug(f"Failed to extract product details from row")
                
                except Exception as e:
                    logger.error(f"Error extracting product details: {e}", exc_info=True)
                    import traceback
                    logger.debug(traceback.format_exc())
                    continue
            
            logger.info(f"Extracted {len(items)} products from Orleans Shoe Co email")
            return items
            
        except Exception as e:
            logger.error(f"Error extracting Orleans products: {e}", exc_info=True)
            return []
    
    def _extract_shipping_address(self, soup: BeautifulSoup) -> str:
        """
        Extract shipping address from HTML.
        
        Args:
            soup: BeautifulSoup object
        
        Returns:
            Normalized shipping address string
        """
        try:
            # Look for "Shipping address" heading
            shipping_heading = soup.find('h4', string=re.compile(r'Shipping\s+address', re.IGNORECASE))
            
            if shipping_heading:
                # Find the parent table/row
                parent = shipping_heading.find_parent(['td', 'tr'])
                
                if parent:
                    # Look for paragraph containing address information
                    address_p = parent.find('p')
                    
                    if address_p:
                        # Get text and clean it up
                        address_text = address_p.get_text(separator=' ', strip=True)
                        
                        # Normalize the address
                        normalized = normalize_shipping_address(address_text)
                        logger.debug(f"Extracted shipping address: {normalized}")
                        return normalized
            
            logger.warning("Could not extract shipping address")
            return ""
            
        except Exception as e:
            logger.error(f"Error extracting shipping address: {e}", exc_info=True)
            return ""
    
    def parse_email(self, email_data: EmailData):
        """
        Generic parse method that routes to the appropriate parser based on email type.
        
        Args:
            email_data: Email data to parse
        
        Returns:
            OrleansOrderData or OrleansCancellationData depending on email type
        """
        if self.is_cancellation_email(email_data):
            return self.parse_cancellation_email(email_data)
        elif self.is_order_confirmation_email(email_data):
            return self.parse_order_confirmation_email(email_data)
        else:
            logger.warning(f"Unknown Orleans email type: {email_data.subject}")
            return None
    
    def parse_order_confirmation_email(self, email_data: EmailData) -> Optional[OrleansOrderData]:
        """
        Parse an Orleans Shoe Co order confirmation email.
        
        Args:
            email_data: Email data to parse
        
        Returns:
            OrleansOrderData object or None if parsing fails
        """
        try:
            html_content = email_data.html_content
            
            if not html_content:
                logger.warning("No HTML content found in email")
                return None
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract order number
            order_number = self._extract_order_number(soup)
            if not order_number:
                logger.warning("Could not extract order number")
                return None
            
            # Extract products
            items = self._extract_products(soup)
            if not items:
                logger.warning("Could not extract any products")
                return None
            
            # Extract shipping address
            shipping_address = self._extract_shipping_address(soup)
            
            return OrleansOrderData(
                order_number=order_number,
                items=items,
                shipping_address=shipping_address
            )
            
        except Exception as e:
            logger.error(f"Error parsing Orleans Shoe Co order email: {e}", exc_info=True)
            return None
    
    def parse_cancellation_email(self, email_data: EmailData) -> Optional[OrleansCancellationData]:
        """
        Parse an Orleans Shoe Co cancellation notification email.
        
        Args:
            email_data: Email data to parse
        
        Returns:
            OrleansCancellationData object or None if parsing fails
        """
        try:
            html_content = email_data.html_content
            
            if not html_content:
                logger.warning("No HTML content found in cancellation email")
                return None
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract order number
            order_number = self._extract_order_number(soup)
            if not order_number:
                logger.warning("Could not extract order number from cancellation email")
                return None
            
            # Extract cancelled items from "Removed Items" section
            items = self._extract_cancellation_items(soup)
            if not items:
                logger.warning(f"No cancelled items found in cancellation email for order {order_number}")
                return None
            
            logger.info(f"Successfully extracted {len(items)} cancelled items from Orleans cancellation order {order_number}")
            for item in items:
                logger.debug(f"  - {item}")
            
            return OrleansCancellationData(order_number=order_number, items=items)
            
        except Exception as e:
            logger.error(f"Error parsing Orleans Shoe Co cancellation email: {e}", exc_info=True)
            return None
    def _extract_cancellation_items(self, soup: BeautifulSoup) -> List[OrleansOrderItem]:
        """
        Extract cancelled items from Orleans Shoe Co cancellation email.
        
        Cancellation email structure:
        - "Removed Items" heading
        - Products are in similar structure to order confirmation
        - Product name format: "On Women's Cloudgo Black Eclipse × 2"
        - Size format: "6 M" in a span with color:#999
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            List of OrleansOrderItem objects
        """
        items = []
        
        try:
            # Find "Removed Items" heading
            removed_items_heading = soup.find('h3', string=re.compile(r'Removed\s+Items', re.IGNORECASE))
            
            if not removed_items_heading:
                logger.warning("Could not find 'Removed Items' heading in cancellation email")
                # Fallback: look for products with "Refunded" text
                return self._extract_products_from_refunded_section(soup)
            
            # Find all product images after the "Removed Items" heading
            # Get the parent container
            container = removed_items_heading.find_parent(['td', 'table'])
            if not container:
                container = soup
            
            # Find all product images in this section
            product_images = container.find_all_next('img', src=re.compile(r'cdn\.shopify\.com.*(?:files|products)'))
            
            logger.debug(f"Found {len(product_images)} Shopify images in cancellation section")
            
            seen_products = set()
            
            for img in product_images:
                # Exclude non-product images
                img_src = img.get('src', '')
                if any(exclude in img_src.lower() for exclude in ['logo', 'spacer', 'icon', 'arrow', 'facebook', 'twitter', 'instagram', 'discounttag', 'email_settings']):
                    continue
                
                # Find the containing table row
                product_row = img.find_parent('tr')
                if not product_row:
                    product_row = img.find_parent('td')
                
                if not product_row:
                    continue
                
                # Check if this row contains product information
                row_text = product_row.get_text()
                has_product_name = bool(re.search(r'×\s*\d+', row_text))
                has_size = bool(re.search(r'\b\d+(?:\.\d+)?\s*[MW]?\b', row_text))
                has_refunded = 'refunded' in row_text.lower()
                
                # In cancellation emails, products should have "Refunded" text
                if not (has_product_name or has_size) or not has_refunded:
                    continue
                
                logger.debug(f"Processing cancellation product image: {img_src[:100]}")
                
                # Try to extract size from nearby spans for uniqueness
                size_key = "unknown"
                size_spans = product_row.find_all('span', style=re.compile(r'color:#999'))
                for span in size_spans:
                    span_text = span.get_text(strip=True)
                    size_match = re.match(r'^(\d+(?:\.\d+)?)\s*[MW]?', span_text)
                    if size_match:
                        size_key = size_match.group(1)
                        break
                
                product_id = f"{img_src}_{size_key}"
                
                if product_id in seen_products:
                    continue
                seen_products.add(product_id)
                
                try:
                    # Extract product details from the product row (reuse existing method)
                    product_details = self._extract_orleans_product_details(product_row)
                    
                    if product_details:
                        items.append(product_details)
                        logger.debug(f"Successfully extracted cancellation product: {product_details.product_name}, unique_id: {product_details.unique_id}")
                
                except Exception as e:
                    logger.error(f"Error extracting cancellation product details: {e}", exc_info=True)
                    continue
            
            logger.info(f"Extracted {len(items)} cancelled items from Orleans Shoe Co cancellation email")
            return items
            
        except Exception as e:
            logger.error(f"Error extracting Orleans cancellation items: {e}", exc_info=True)
            return []
    
    def _extract_products_from_refunded_section(self, soup: BeautifulSoup) -> List[OrleansOrderItem]:
        """
        Fallback method to extract products from refunded section if "Removed Items" heading not found.
        
        Args:
            soup: BeautifulSoup object of email HTML
        
        Returns:
            List of OrleansOrderItem objects
        """
        items = []
        
        try:
            # Find all spans with "Refunded" text
            refunded_spans = soup.find_all('span', string=re.compile(r'Refunded', re.IGNORECASE))
            
            for refunded_span in refunded_spans:
                # Find the parent row containing this refunded span
                product_row = refunded_span.find_parent('tr')
                if not product_row:
                    continue
                
                # Check if this row contains product information
                row_text = product_row.get_text()
                has_product_name = bool(re.search(r'×\s*\d+', row_text))
                
                if not has_product_name:
                    continue
                
                try:
                    # Extract product details from the product row
                    product_details = self._extract_orleans_product_details(product_row)
                    
                    if product_details:
                        items.append(product_details)
                        logger.debug(f"Successfully extracted cancellation product (fallback): {product_details.product_name}")
                
                except Exception as e:
                    logger.error(f"Error extracting cancellation product details (fallback): {e}", exc_info=True)
                    continue
            
            return items
            
        except Exception as e:
            logger.error(f"Error extracting products from refunded section: {e}", exc_info=True)
            return []