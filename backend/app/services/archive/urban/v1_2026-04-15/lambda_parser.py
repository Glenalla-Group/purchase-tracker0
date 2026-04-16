"""
Urban Outfitters Email Parser
Parses cancellation, shipping, and order confirmation emails from Urban Outfitters using BeautifulSoup

Email Format:
- From: urbanoutfitters@st.urbanoutfitters.com (production)
- From: glenallagroupc@gmail.com (dev - forwarded emails)
- Subject: "Order Confirmation", "Cancellation Notice", "Your order has shipped"
- Order Number: Extract from HTML (e.g., "TN20434232")

HTML Structure:
- Products are listed in table rows with class "m_-5406526606445553728item-table-container"
- Each product has:
  - Image URL: https://images.urbndata.com/is/image/UrbanOutfitters/84448976_067_b
    Pattern: {style_number}_{color_code}_b
  - Product name: <h4>Gola Women's Elan Leather Sneaker</h4>
  - Style No.: <span>84448976</span>
  - Color: <span>Peach</span>
  - Size: <span>US 6/UK 4</span>
  - Quantity: In <td> with class "m_-5406526606445553728item-price-large" and align="center"

Unique ID Extraction:
- Format: {product-slug}-{color_code}
- Product slug: Convert product name to lowercase, replace spaces/special chars with hyphens
- Color code: Extract from image URL pattern {style_number}_{color_code}_b
- Example: "Gola Women's Elan Leather Sneaker" + color "067" -> "gola-womens-elan-leather-sneaker-067"

URL-to-Email Crossover Analysis:
- URL pattern: urbanoutfitters.com/shop/{slug}?color={color_code}
- URL regex: r'urbanoutfitters\\.com/shop/([a-z0-9-]+)(?:\\?.*?color=(\\d{3}))?'
  - Group 1: product slug (e.g., "gola-elan-sneaker2")
  - Group 2: color code (e.g., "020")
- URL unique_id: {slug} or {slug}-{color_code} when ?color= is present
- Crossover status: PARTIAL
  - Color codes MATCH: URL ?color=020 == email image _020_b
  - Slugs DO NOT MATCH: URL uses marketing slug (e.g., "gola-elan-sneaker2"),
    email derives slug from full product name (e.g., "gola-womens-elan-sneaker")
  - The 3-digit color code is the only reliable crossover point
  - Style number (e.g., 84448976) is in email but NOT in URL
- Verified against order TN20625575:
  - URL: gola-elan-sneaker2?color=020 -> email: 84448976_020_b (color yes, slug no)
  - URL: gola-tornado-sneaker?color=043 -> email: 89004956_043_b (color yes, slug no)
"""

import re
import logging
from typing import List, Optional, Dict
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from src.models import EmailData
from src.utils.address_utils import normalize_shipping_address
from src.config import get_config as get_settings

logger = logging.getLogger(__name__)


class UrbanOrderItem(BaseModel):
    unique_id: str = Field(..., description="Unique identifier for the product (e.g., gola-womens-elan-leather-sneaker-067)")
    size: str = Field(..., description="Size of the product")
    quantity: int = Field(..., description="Quantity of the product")
    product_name: Optional[str] = Field(None, description="Name of the product")
    style_number: Optional[str] = Field(None, description="Style number")
    color: Optional[str] = Field(None, description="Color name")

    def __repr__(self):
        if self.product_name and len(self.product_name) > 50:
            product_display = self.product_name[:50] + "..."
        else:
            product_display = self.product_name or "Unknown"
        return f"<UrbanOrderItem(unique_id={self.unique_id}, size={self.size}, qty={self.quantity}, product={product_display})>"


class UrbanOrderData(BaseModel):
    order_number: str = Field(..., description="The order number")
    items: List[UrbanOrderItem] = Field(..., description="List of items in the order")
    items_count: int = Field(0, description="Total number of items in the order")
    shipping_address: str = Field("", description="Normalized shipping address")

    def __init__(self, **data):
        super().__init__(**data)
        self.items_count = len(self.items)


class UrbanOutfittersCancellationData(BaseModel):
    """Represents Urban Outfitters cancellation notification data"""
    order_number: str = Field(..., description="The order number")
    items: List[UrbanOrderItem] = Field(..., description="List of cancelled items")

    def __repr__(self):
        return f"<UrbanOutfittersCancellationData(order={self.order_number}, items={len(self.items)})>"


class UrbanOutfittersShippingData(BaseModel):
    """Represents Urban Outfitters shipping notification data"""
    order_number: str = Field(..., description="The order number")
    items: List[UrbanOrderItem] = Field(..., description="List of shipped items")
    tracking_number: Optional[str] = Field(None, description="Tracking number")
    shipment_type: str = Field(..., description="Type of shipment: 'partial', 'rest', or 'full'")

    def __repr__(self):
        return f"<UrbanOutfittersShippingData(order={self.order_number}, items={len(self.items)}, tracking={self.tracking_number}, type={self.shipment_type})>"


class UrbanOutfittersEmailParser:
    # Email identification - Production
    URBAN_FROM_EMAIL = "urbanoutfitters@st.urbanoutfitters.com"
    URBAN_FROM_PATTERN = r"urbanoutfitters"

    # Subject patterns for different email types
    SUBJECT_ORDER_PATTERN = r"order\s+confirmation"
    SUBJECT_CANCELLATION_PATTERN = r"cancellation notice"
    SUBJECT_SHIPPING_PATTERN = r"shipping\s+confirmation|your order.*shipped|order.*shipped|shipping.*notification"

    # Email identification - Development (forwarded emails)
    DEV_URBAN_ORDER_FROM_EMAIL = "glenallagroupc@gmail.com"
    DEV_SUBJECT_ORDER_PATTERN = r"(?:Fwd:\s*)?order\s+confirmation"

    def __init__(self):
        """Initialize the Urban Outfitters email parser."""
        self.settings = get_settings()

    @property
    def order_from_email(self) -> str:
        """Get the appropriate from email address based on environment."""
        if self.settings.is_development:
            return self.DEV_URBAN_ORDER_FROM_EMAIL
        return self.URBAN_FROM_EMAIL

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
            return "Order Confirmation"
        return "Order Confirmation"

    def is_urban_email(self, email_data: EmailData) -> bool:
        """Check if email is from Urban Outfitters"""
        sender_lower = email_data.sender.lower()

        # In development, check for forwarded emails from dev email address
        if self.settings.is_development:
            if self.DEV_URBAN_ORDER_FROM_EMAIL.lower() in sender_lower:
                return True

        # In production, check for Urban Outfitters email
        if self.URBAN_FROM_EMAIL.lower() in sender_lower:
            return True

        # Check for "urbanoutfitters" in sender name
        if re.search(self.URBAN_FROM_PATTERN, sender_lower, re.IGNORECASE):
            return True

        return False

    def is_urban_outfitters_email(self, email_data: EmailData) -> bool:
        """Alias for is_urban_email for compatibility"""
        return self.is_urban_email(email_data)

    def is_order_confirmation_email(self, email_data: EmailData) -> bool:
        """Check if email is an order confirmation"""
        # Check if sender matches Urban Outfitters
        if not self.is_urban_email(email_data):
            return False

        subject_lower = email_data.subject.lower()
        # Exclude Revolve: "Your order #XXX has been processed"
        if re.search(r"your order\s+#\d+\s+has been processed", subject_lower, re.IGNORECASE):
            return False

        pattern = self.order_subject_pattern

        # Use regex matching for subject pattern
        if re.search(pattern, subject_lower, re.IGNORECASE):
            return True

        # Also check body text for order confirmation indicators
        if email_data.html_content:
            html_lower = email_data.html_content.lower()
            if any(phrase in html_lower for phrase in [
                "order confirmation",
                "thank you for your order",
                "order received"
            ]):
                # Make sure it's not a cancellation or shipping email
                if not self.is_cancellation_email(email_data) and not self.is_shipping_email(email_data):
                    return True

        return False

    def is_cancellation_email(self, email_data: EmailData) -> bool:
        """
        Check if email is a cancellation notification.

        Args:
            email_data: EmailData object

        Returns:
            True if this is a cancellation notification email
        """
        # Check if sender matches Urban Outfitters
        if not self.is_urban_email(email_data):
            return False

        subject_lower = email_data.subject.lower()

        # Check subject pattern
        if re.search(self.SUBJECT_CANCELLATION_PATTERN, subject_lower, re.IGNORECASE):
            return True

        # Also check body text for cancellation indicators
        if email_data.html_content:
            html_lower = email_data.html_content.lower()
            if any(phrase in html_lower for phrase in [
                "cancellation notice",
                "have been cancelled",
                "no longer in stock",
                "have been canceled"
            ]):
                return True

        return False

    def is_shipping_email(self, email_data: EmailData) -> bool:
        """
        Check if email is a shipping notification.

        Args:
            email_data: EmailData object

        Returns:
            True if this is a shipping notification email
        """
        # Check if sender matches Urban Outfitters
        if not self.is_urban_email(email_data):
            return False

        subject_lower = email_data.subject.lower()

        # Check subject pattern
        if re.search(self.SUBJECT_SHIPPING_PATTERN, subject_lower, re.IGNORECASE):
            return True

        # Also check body text for shipping indicators
        if email_data.html_content:
            html_lower = email_data.html_content.lower()
            if any(phrase in html_lower for phrase in [
                "shipping confirmation",
                "the below items shipped",
                "your order has shipped",
                "order shipped",
                "tracking number",
                "has been shipped"
            ]):
                return True

        return False

    def parse_email(self, email_data: EmailData):
        """
        Generic parse method that routes to the appropriate parser based on email type.

        Args:
            email_data: EmailData object containing email information

        Returns:
            UrbanOrderData, UrbanOutfittersShippingData, or UrbanOutfittersCancellationData depending on email type
        """
        if self.is_order_confirmation_email(email_data):
            return self.parse_order_confirmation_email(email_data)
        elif self.is_shipping_email(email_data):
            return self.parse_shipping_email(email_data)
        elif self.is_cancellation_email(email_data):
            return self.parse_cancellation_email(email_data)
        else:
            logger.warning(f"Unknown Urban Outfitters email type: {email_data.subject}")
            return None

    def parse_order_confirmation_email(self, email_data: EmailData) -> Optional[UrbanOrderData]:
        """
        Parse Urban Outfitters order confirmation email.

        Args:
            email_data: EmailData object containing email information

        Returns:
            UrbanOrderData object or None if parsing fails
        """
        try:
            html_content = email_data.html_content

            if not html_content:
                logger.error("No HTML content in Urban Outfitters email")
                return None

            soup = BeautifulSoup(html_content, 'html.parser')

            # Extract order number from HTML
            order_number = self._extract_order_number(soup)
            if not order_number:
                logger.error("Failed to extract order number from Urban Outfitters email")
                return None

            logger.info(f"Extracted Urban Outfitters order number: {order_number}")

            # Extract items using BeautifulSoup
            items = self._extract_items(soup)

            if not items:
                logger.error("Failed to extract any items from Urban Outfitters email")
                return None

            logger.info(f"Successfully extracted {len(items)} items from Urban Outfitters order {order_number}")
            for item in items:
                logger.debug(f"  - {item}")

            # Extract shipping address
            shipping_address = self._extract_shipping_address(soup)
            if shipping_address:
                logger.info(f"Extracted shipping address: {shipping_address}")

            return UrbanOrderData(order_number=order_number, items=items, shipping_address=shipping_address)

        except Exception as e:
            logger.error(f"Error parsing Urban Outfitters email: {e}", exc_info=True)
            return None

    def parse_cancellation_email(self, email_data: EmailData) -> Optional[UrbanOutfittersCancellationData]:
        """
        Parse Urban Outfitters cancellation notification email.

        Args:
            email_data: EmailData object containing email information

        Returns:
            UrbanOutfittersCancellationData object or None if parsing fails
        """
        try:
            html_content = email_data.html_content

            if not html_content:
                logger.error("No HTML content in Urban Outfitters cancellation email")
                return None

            soup = BeautifulSoup(html_content, 'html.parser')

            # Extract order number
            order_number = self._extract_order_number(soup)
            if not order_number:
                logger.error("Failed to extract order number from Urban Outfitters cancellation email")
                return None

            logger.info(f"Extracted Urban Outfitters cancellation order number: {order_number}")

            # Extract cancelled items (reuse the same extraction logic)
            items = self._extract_items(soup)

            if not items:
                logger.warning(f"No cancelled items found in Urban Outfitters cancellation email for order {order_number}")
                return None

            logger.info(f"Successfully extracted {len(items)} cancelled items from Urban Outfitters cancellation order {order_number}")
            for item in items:
                logger.debug(f"  - {item}")

            return UrbanOutfittersCancellationData(order_number=order_number, items=items)

        except Exception as e:
            logger.error(f"Error parsing Urban Outfitters cancellation email: {e}", exc_info=True)
            return None

    def parse_shipping_email(self, email_data: EmailData) -> Optional[UrbanOutfittersShippingData]:
        """
        Parse Urban Outfitters shipping notification email.

        Args:
            email_data: EmailData object containing email information

        Returns:
            UrbanOutfittersShippingData object or None if parsing fails
        """
        try:
            html_content = email_data.html_content

            if not html_content:
                logger.error("No HTML content in Urban Outfitters shipping email")
                return None

            soup = BeautifulSoup(html_content, 'html.parser')

            # Extract order number
            order_number = self._extract_order_number(soup)
            if not order_number:
                logger.error("Failed to extract order number from Urban Outfitters shipping email")
                return None

            logger.info(f"Extracted Urban Outfitters shipping order number: {order_number}")

            # Determine shipment type (partial, rest, or full)
            shipment_type = self._determine_shipment_type(soup)
            logger.info(f"Detected shipment type: {shipment_type}")

            # Extract tracking number
            tracking_number = self._extract_tracking_number(soup)

            # Extract shipped items from "The Below Items Shipped" section only
            items = self._extract_shipping_items(soup)

            if not items:
                logger.warning(f"No shipped items found in Urban Outfitters shipping email for order {order_number}")
                return None

            logger.info(f"Successfully extracted {len(items)} shipped items from Urban Outfitters shipping order {order_number}")
            for item in items:
                logger.debug(f"  - {item}")

            return UrbanOutfittersShippingData(
                order_number=order_number,
                items=items,
                tracking_number=tracking_number,
                shipment_type=shipment_type
            )

        except Exception as e:
            logger.error(f"Error parsing Urban Outfitters shipping email: {e}", exc_info=True)
            return None

    def _extract_order_number(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract order number from Urban Outfitters email HTML.

        HTML format: <h4> Order Number: <a href="...">TN20434232</a></h4>
        Extract: TN20434232

        Args:
            soup: BeautifulSoup object of email HTML

        Returns:
            Order number or None
        """
        try:
            # Look for "Order Number:" text
            order_number_pattern = re.compile(r'Order\s+Number:', re.IGNORECASE)
            order_number_header = soup.find('h4', string=order_number_pattern)

            if not order_number_header:
                # Try finding by text content
                order_number_header = soup.find('h4', string=re.compile(r'Order\s+Number:', re.IGNORECASE))

            if order_number_header:
                # Get the parent h4 element and find the link
                h4_element = order_number_header if order_number_header.name == 'h4' else order_number_header.find_parent('h4')
                if h4_element:
                    link = h4_element.find('a')
                    if link:
                        order_number = link.get_text(strip=True)
                        if order_number:
                            logger.debug(f"Found Urban Outfitters order number: {order_number}")
                            return order_number

            # Fallback: search for pattern in text
            text_content = soup.get_text()
            match = re.search(r'Order\s+Number:\s*([A-Z0-9]+)', text_content, re.IGNORECASE)
            if match:
                order_number = match.group(1)
                logger.debug(f"Found Urban Outfitters order number (fallback): {order_number}")
                return order_number

            logger.warning("Order number not found in Urban Outfitters email")
            return None

        except Exception as e:
            logger.error(f"Error extracting Urban Outfitters order number: {e}")
            return None

    def _extract_items(self, soup: BeautifulSoup) -> List[UrbanOrderItem]:
        """
        Extract order items from Urban Outfitters email.

        Urban Outfitters email structure:
        - Products are in table rows with class containing "item-table-container"
        - Each product row contains:
          - Image with URL: https://images.urbndata.com/is/image/UrbanOutfitters/84448976_067_b
          - Product name in <h4> tag
          - Style No. in <span>
          - Color in <span>
          - Size in <span>
          - Quantity in <td> with align="center"

        Args:
            soup: BeautifulSoup object of email HTML

        Returns:
            List of UrbanOrderItem objects
        """
        items = []

        try:
            # Find all product containers - look for tables with item-table-container class
            product_containers = soup.find_all('td', class_=lambda x: x and 'item-table-container' in str(x))

            for container in product_containers:
                try:
                    product_details = self._extract_urban_product_details(container)

                    if product_details:
                        items.append(product_details)

                except Exception as e:
                    logger.error(f"Error processing Urban Outfitters product container: {e}")
                    continue

            # Log items with ID, size, and quantity
            if items:
                items_summary = [f"(ID: {item.unique_id}, Size: {item.size}, Qty: {item.quantity})" for item in items]
                logger.info(f"[Urban Outfitters] Extracted {len(items)} items: {', '.join(items_summary)}")

            return items

        except Exception as e:
            logger.error(f"Error extracting Urban Outfitters items: {e}", exc_info=True)
            return []

    def _extract_urban_product_details(self, container) -> Optional[UrbanOrderItem]:
        """
        Extract product details from an Urban Outfitters product container.

        Returns:
            UrbanOrderItem object or None
        """
        try:
            details = {}
            container_text = container.get_text()

            # Extract product name - look for <h4> tag
            product_name_tag = container.find('h4')
            if product_name_tag:
                product_name = product_name_tag.get_text(strip=True)
                details['product_name'] = product_name
                logger.debug(f"Found product name: {product_name}")
            else:
                logger.warning("Product name not found in Urban Outfitters container")
                return None

            # Extract style number - look for "Style No." followed by <span>
            style_number_tag = container.find(string=re.compile(r'Style\s+No\.', re.IGNORECASE))
            if style_number_tag:
                style_span = style_number_tag.find_next('span')
                if style_span:
                    style_number = style_span.get_text(strip=True)
                    details['style_number'] = style_number
                    logger.debug(f"Found style number: {style_number}")

            # Extract color - look for "Color:" followed by <span>
            color_tag = container.find(string=re.compile(r'Color:', re.IGNORECASE))
            if color_tag:
                color_span = color_tag.find_next('span')
                if color_span:
                    color = color_span.get_text(strip=True)
                    details['color'] = color
                    logger.debug(f"Found color: {color}")

            # Extract size - look for "Size:" followed by <span>
            size_tag = container.find(string=re.compile(r'Size:', re.IGNORECASE))
            if size_tag:
                size_span = size_tag.find_next('span')
                if size_span:
                    size = size_span.get_text(strip=True)
                    details['size'] = size
                    logger.debug(f"Found size: {size}")

            if not details.get('size'):
                # Try regex fallback - look for "Size:" followed by text in span
                size_match = re.search(r'Size:\s*<span>([^<]+)</span>', str(container), re.IGNORECASE)
                if size_match:
                    size = size_match.group(1).strip()
                    details['size'] = size
                    logger.debug(f"Found size (regex span): {size}")

            if not details.get('size'):
                # Try regex fallback - look for "Size:" followed by any text
                size_match = re.search(r'Size:\s*([^\n<]+)', container_text, re.IGNORECASE)
                if size_match:
                    size = size_match.group(1).strip()
                    # Clean up any HTML entities or extra whitespace
                    size = re.sub(r'<[^>]+>', '', size).strip()
                    details['size'] = size
                    logger.debug(f"Found size (regex fallback): {size}")

            if not details.get('size'):
                logger.warning("Size not found in Urban Outfitters container")
                return None

            # Extract quantity - look for <td> with align="center" containing a number
            quantity_td = container.find('td', class_=lambda x: x and 'item-price-large' in str(x), style=lambda x: x and 'text-align:center' in str(x))
            if not quantity_td:
                # Try finding by text alignment
                quantity_td = container.find('td', style=re.compile(r'text-align:\s*center', re.IGNORECASE))

            if quantity_td:
                quantity_text = quantity_td.get_text(strip=True)
                # Try to extract number
                qty_match = re.search(r'(\d+)', quantity_text)
                if qty_match:
                    quantity = int(qty_match.group(1))
                    details['quantity'] = quantity
                    logger.debug(f"Found quantity: {quantity}")
                else:
                    # Default to 1 if not found
                    details['quantity'] = 1
                    logger.debug("Quantity not found, defaulting to 1")
            else:
                # Default to 1 if quantity td not found
                details['quantity'] = 1
                logger.debug("Quantity td not found, defaulting to 1")

            # Extract color code from image URL for unique ID
            # Pattern: https://images.urbndata.com/is/image/UrbanOutfitters/84448976_067_b
            # Extract: 067 from {style_number}_{color_code}_b
            img = container.find('img', src=lambda x: x and 'urbndata.com' in str(x))
            color_code = None
            if img:
                img_src = img.get('src', '')
                # Extract color code from URL pattern
                color_match = re.search(r'/(\d+)_(\d{3})_b', img_src)
                if color_match:
                    color_code = color_match.group(2)
                    logger.debug(f"Found color code from image URL: {color_code}")

            if not color_code:
                logger.warning("Color code not found in image URL")
                return None

            # Generate unique ID: {product-slug}-{color_code}
            # Convert product name to slug
            product_slug = self._product_name_to_slug(product_name)
            unique_id = f"{product_slug}-{color_code}"
            details['unique_id'] = unique_id
            logger.debug(f"Generated unique ID: {unique_id}")

            # Return only if we have the essential fields
            if details.get('unique_id') and details.get('size'):
                return UrbanOrderItem(
                    unique_id=details['unique_id'],
                    size=details['size'],
                    quantity=details.get('quantity', 1),
                    product_name=details.get('product_name'),
                    style_number=details.get('style_number'),
                    color=details.get('color')
                )

            logger.warning(f"Missing essential fields: {details}")
            return None

        except Exception as e:
            logger.error(f"Error extracting Urban Outfitters product details: {e}", exc_info=True)
            return None

    def _product_name_to_slug(self, product_name: str) -> str:
        """
        Convert product name to URL-friendly slug.

        Example: "Gola Women's Elan Leather Sneaker" -> "gola-womens-elan-leather-sneaker"

        Args:
            product_name: Product name string

        Returns:
            Slug string
        """
        # Convert to lowercase
        slug = product_name.lower()

        # Replace apostrophes and other special characters with spaces
        slug = re.sub(r"['\u2019`]", '', slug)

        # Replace non-alphanumeric characters (except hyphens) with hyphens
        slug = re.sub(r'[^a-z0-9-]+', '-', slug)

        # Remove leading/trailing hyphens and collapse multiple hyphens
        slug = re.sub(r'-+', '-', slug).strip('-')

        return slug

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
            shipping_header = soup.find('h3', string=re.compile(r'Shipping\s+Address', re.IGNORECASE))

            if shipping_header:
                # Find the address text in the next td
                address_td = shipping_header.find_parent('table')
                if address_td:
                    # Find the td with class containing "address"
                    address_element = address_td.find('td', class_=lambda x: x and 'address' in str(x))
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

    def _determine_shipment_type(self, soup: BeautifulSoup) -> str:
        """
        Determine shipment type: 'partial', 'rest', or 'full'.

        Logic:
        - If "Other Items In Your Order" exists -> partial shipment (some items haven't shipped yet)
        - If "Previously Shipped Items" exists -> rest shipment (some items shipped before)
        - If only "The Below Items Shipped" exists -> full shipment (all items shipped)

        Args:
            soup: BeautifulSoup object of email HTML

        Returns:
            'partial', 'rest', or 'full'
        """
        try:
            text = soup.get_text()
            text_lower = text.lower()

            has_other_items = "other items in your order" in text_lower
            has_previously_shipped = "previously shipped items" in text_lower

            if has_other_items:
                logger.debug("Detected partial shipment (has 'Other Items In Your Order')")
                return "partial"
            elif has_previously_shipped:
                logger.debug("Detected rest shipment (has 'Previously Shipped Items')")
                return "rest"
            else:
                logger.debug("Detected full shipment (only 'The Below Items Shipped')")
                return "full"

        except Exception as e:
            logger.error(f"Error determining shipment type: {e}")
            return "full"  # Default to full if we can't determine

    def _extract_shipping_items(self, soup: BeautifulSoup) -> List[UrbanOrderItem]:
        """
        Extract shipped items from "The Below Items Shipped" section only.
        This excludes items from "Other Items In Your Order" and "Previously Shipped Items" sections.

        Args:
            soup: BeautifulSoup object of email HTML

        Returns:
            List of UrbanOrderItem objects from the shipped section
        """
        items = []

        try:
            # Get HTML as string to find positions
            html_str = str(soup)
            html_lower = html_str.lower()

            # Find positions of section markers
            shipped_marker_pos = html_lower.find("the below items shipped")
            other_items_pos = html_lower.find("other items in your order")
            prev_shipped_pos = html_lower.find("previously shipped items")

            if shipped_marker_pos < 0:
                logger.warning("Could not find 'The Below Items Shipped' section")
                # Fallback: extract all items
                return self._extract_items(soup)

            # Find all product containers
            all_containers = soup.find_all('td', class_=lambda x: x and 'item-table-container' in str(x))

            for container in all_containers:
                try:
                    # Get position of this container in HTML
                    container_str = str(container)
                    container_pos = html_str.find(container_str)

                    # Skip if container is before "The Below Items Shipped"
                    if container_pos < shipped_marker_pos:
                        continue

                    # Skip if container is after "Other Items In Your Order" (if it exists)
                    if other_items_pos >= 0 and container_pos > other_items_pos:
                        continue

                    # Skip if container is after "Previously Shipped Items" (if it exists)
                    if prev_shipped_pos >= 0 and container_pos > prev_shipped_pos:
                        continue

                    # Extract product details
                    product_details = self._extract_urban_product_details(container)
                    if product_details:
                        items.append(product_details)

                except Exception as e:
                    logger.error(f"Error processing Urban Outfitters shipping product container: {e}")
                    continue

            # Log items with ID, size, and quantity
            if items:
                items_summary = [f"(ID: {item.unique_id}, Size: {item.size}, Qty: {item.quantity})" for item in items]
                logger.info(f"[Urban Outfitters] Extracted {len(items)} shipped items: {', '.join(items_summary)}")

            return items

        except Exception as e:
            logger.error(f"Error extracting Urban Outfitters shipping items: {e}", exc_info=True)
            return []

    def _extract_tracking_number(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract tracking number from shipping email.

        Args:
            soup: BeautifulSoup object of email HTML

        Returns:
            Tracking number string or None
        """
        try:
            # First, try to find tracking number in the "Tracking Number:" link
            tracking_links = soup.find_all('a', href=True)
            for link in tracking_links:
                link_text = link.get_text(strip=True)
                # Look for tracking number patterns in link text
                if re.match(r'^[A-Z0-9]{10,30}$', link_text):
                    # Check if it's near "Tracking Number" text
                    parent_text = ""
                    parent = link.find_parent(['td', 'h4', 'table'])
                    if parent:
                        parent_text = parent.get_text().lower()

                    if "tracking number" in parent_text or "tracking" in parent_text:
                        logger.debug(f"Found tracking number from link: {link_text}")
                        return link_text

            # Fallback: search in text
            text = soup.get_text()

            # Look for common tracking number patterns
            # UPS: 1Z... or T... or 1Z[0-9A-Z]{16}
            # FedEx: [0-9]{12,14}
            # USPS: [0-9]{20,22}
            tracking_patterns = [
                r'tracking\s*(?:number|#)?[:\s]+([A-Z0-9]{10,30})',
                r'track\s*(?:number|#)?[:\s]+([A-Z0-9]{10,30})',
                r'\b(1Z[0-9A-Z]{16})\b',  # UPS
                r'\b([0-9]{12,14})\b',  # FedEx
                r'\b([0-9]{20,22})\b',  # USPS
            ]

            for pattern in tracking_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    tracking = match.group(1)
                    logger.debug(f"Found tracking number: {tracking}")
                    return tracking

            logger.debug("No tracking number found in shipping email")
            return None

        except Exception as e:
            logger.error(f"Error extracting tracking number: {e}")
            return None
