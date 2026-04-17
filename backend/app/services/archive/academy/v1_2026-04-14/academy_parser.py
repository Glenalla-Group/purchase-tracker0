"""
Academy Sports + Outdoors Email Parser
Parses order confirmation and shipping notification emails from Academy Sports.

Email Format:
- From: email@e.academy.com (production)
- From: glenallagroupc@gmail.com (dev - forwarded emails)
- Order Confirmation Subject: "Thanks for shopping with us!"
- Shipping Subject: "Your order is on the way"
- Order Number: "Order #500659500" in <th> element

HTML Structure (Order Confirmation):
- Order number: in <th> with class="tablet-copy-24 mobile-copy-24"
- Items in <table id="orderItemDetail"> blocks:
  - Product name: <span id="productName">
  - Color: <span id="value1"> (label in <span id="attribute1">)
  - Size: <span id="value2"> (label in <span id="attribute2">)
  - Width: <span id="value3"> (label in <span id="attribute3">)
  - SKU: <span id="sku">
  - Quantity: <span id="currentItemQuantity">
  - Image: academy.scene7.com/is/image/academy/{imageId}
- Shipping address: after "Shipping Information" text, in <span> with font-weight: 700

HTML Structure (Shipping):
- Order number: same pattern as confirmation
- Carrier: after "Shipping Carrier" text
- Tracking: after "Tracking Number" text, in <a> tag
- Items: flat text product description, SKU/QTY in bold <span> tags
  - Product text: "Brooks W Glycerin 22 WhiteBlack 01 09 Footwear B Width Footwear"
  - SKU: "SKU: 156905877"
  - QTY: "QTY: 1"
  - Image: same academy.scene7.com pattern

UNIQUE ID CROSSOVER:
  Status: Partial (slug + normalized color)
  Email source: Slugified product name + stripped color from <span id="value1"> or flat text
  URL regex: r'academy\\.com/p/([a-z0-9-]+)' + r'[?&]sku=\\d+(?:\\.\\d+)?-[a-z]-(.+?)(?:&|$)'
  Format: "brooks-w-glycerin-22-whiteblack01"
  Notes: Color normalized by stripping all non-alphanumeric chars + lowercase.
         Shipping email color extracted from flat text before zero-padded size.
         Same model in different colors will produce different unique_ids.
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


class AcademyOrderItem(BaseModel):
    unique_id: str = Field(..., description="Slug + normalized color (e.g., brooks-w-glycerin-22-whiteblack01)")
    size: str = Field(..., description="Size of the product")
    quantity: int = Field(..., description="Quantity ordered")
    product_name: Optional[str] = Field(None, description="Name of the product")
    category: Optional[str] = Field(None, description="Product category")

    def __repr__(self):
        product_display = self.product_name or "Unknown"
        if len(product_display) > 50:
            product_display = product_display[:50] + "..."
        return f"<AcademyOrderItem(unique_id={self.unique_id}, size={self.size}, qty={self.quantity}, product={product_display})>"


class AcademyOrderData(BaseModel):
    order_number: str = Field(..., description="The order number")
    items: List[AcademyOrderItem] = Field(..., description="List of items in the order")
    items_count: int = Field(0, description="Total number of line items")
    shipping_address: str = Field("", description="Normalized shipping address")

    def __init__(self, **data):
        super().__init__(**data)
        self.items_count = len(self.items)


class AcademyShippingData(BaseModel):
    order_number: str = Field(..., description="The order number")
    items: List[AcademyOrderItem] = Field(..., description="Shipped items")
    tracking_number: str = Field("", description="Tracking number")
    carrier: Optional[str] = Field(None, description="Shipping carrier")


class AcademyEmailParser:
    # Email identification - Production
    ACADEMY_FROM_EMAIL = "email@e.academy.com"
    SUBJECT_ORDER_PATTERN = r"thanks\s+for\s+shopping\s+with\s+us"
    SUBJECT_SHIPPING_PATTERN = r"your\s+order\s+is\s+on\s+the\s+way"

    # Email identification - Development (forwarded emails)
    DEV_ACADEMY_FROM_EMAIL = "glenallagroupc@gmail.com"
    DEV_SUBJECT_ORDER_PATTERN = r"(?:Fwd:\s*)?thanks\s+for\s+shopping\s+with\s+us"
    DEV_SUBJECT_SHIPPING_PATTERN = r"(?:Fwd:\s*)?your\s+order\s+is\s+on\s+the\s+way"

    # Gmail search queries (plain strings for Gmail API)
    GMAIL_ORDER_QUERY = "Thanks for shopping with us"
    GMAIL_SHIPPING_QUERY = "Your order is on the way"

    def __init__(self):
        """Initialize the Academy Sports email parser."""
        self.settings = get_settings()

    # ---------------------------------------------------------------
    # Properties: environment-aware email/subject patterns
    # ---------------------------------------------------------------

    @property
    def order_from_email(self) -> str:
        if self.settings.is_development:
            return self.DEV_ACADEMY_FROM_EMAIL
        return self.ACADEMY_FROM_EMAIL

    @property
    def order_subject_pattern(self) -> str:
        if self.settings.is_development:
            return self.DEV_SUBJECT_ORDER_PATTERN
        return self.SUBJECT_ORDER_PATTERN

    @property
    def order_subject_query(self) -> str:
        return self.GMAIL_ORDER_QUERY

    @property
    def shipping_from_email(self) -> str:
        if self.settings.is_development:
            return self.DEV_ACADEMY_FROM_EMAIL
        return self.ACADEMY_FROM_EMAIL

    @property
    def shipping_subject_pattern(self) -> str:
        if self.settings.is_development:
            return self.DEV_SUBJECT_SHIPPING_PATTERN
        return self.SUBJECT_SHIPPING_PATTERN

    @property
    def shipping_subject_query(self) -> str:
        return self.GMAIL_SHIPPING_QUERY

    # ---------------------------------------------------------------
    # Identification methods
    # ---------------------------------------------------------------

    def is_academy_email(self, email_data: EmailData) -> bool:
        """Check if email is from Academy Sports."""
        sender = (email_data.sender or "").lower()

        if self.settings.is_development:
            if self.DEV_ACADEMY_FROM_EMAIL.lower() in sender:
                html = email_data.html_content or ""
                if "academy" in html.lower() or "e.academy.com" in html.lower():
                    return True
            return False

        return self.ACADEMY_FROM_EMAIL.lower() in sender

    def is_order_confirmation_email(self, email_data: EmailData) -> bool:
        """Check if email is an Academy Sports order confirmation."""
        subject = email_data.subject or ""
        return bool(re.search(self.order_subject_pattern, subject, re.IGNORECASE))

    def is_shipping_email(self, email_data: EmailData) -> bool:
        """Check if email is an Academy Sports shipping notification."""
        subject = email_data.subject or ""
        return bool(re.search(self.shipping_subject_pattern, subject, re.IGNORECASE))

    def is_cancellation_email(self, email_data: EmailData) -> bool:
        """Academy Sports cancellation emails are not supported."""
        return False

    # ---------------------------------------------------------------
    # Normalization helpers
    # ---------------------------------------------------------------

    @staticmethod
    def _slugify(text: str) -> str:
        """Convert product name to URL-style slug.

        'Brooks W Glycerin 22' -> 'brooks-w-glycerin-22'
        """
        slug = text.lower().strip()
        slug = re.sub(r'[^a-z0-9\s-]', '', slug)
        slug = re.sub(r'[\s]+', '-', slug)
        slug = re.sub(r'-+', '-', slug)
        return slug.strip('-')

    @staticmethod
    def _normalize_color(color: str) -> str:
        """Strip all non-alphanumeric characters and lowercase.

        Produces consistent output regardless of source format:
        - Order confirmation: 'White / Black01' -> 'whiteblack01'
        - Shipping email:     'WhiteBlack 01'   -> 'whiteblack01'
        - URL sku param:      'white-black01'    -> 'whiteblack01'
        """
        return re.sub(r'[^a-z0-9]', '', color.lower())

    @staticmethod
    def _clean_size(size_str: str) -> str:
        """Normalize size string.

        '09' -> '9', '06.0' -> '6', '09.5' -> '9.5', '14.0' -> '14'
        """
        size = size_str.strip()
        try:
            num = float(size)
            if num == int(num):
                return str(int(num))
            return str(num)
        except ValueError:
            return size.upper()

    def _build_unique_id(self, product_name: str, color: str) -> str:
        """Build unique_id from product name slug + normalized color.

        'Brooks W Glycerin 22' + 'White / Black01' -> 'brooks-w-glycerin-22-whiteblack01'
        """
        slug = self._slugify(product_name)
        norm_color = self._normalize_color(color)
        if norm_color:
            return f"{slug}-{norm_color}"
        return slug

    # ---------------------------------------------------------------
    # Order confirmation parsing
    # ---------------------------------------------------------------

    def parse_email(self, email_data: EmailData) -> Optional[AcademyOrderData]:
        """Parse an Academy Sports order confirmation email."""
        try:
            body = email_data.html_content or ""
            if not body:
                logger.warning("Academy order confirmation email has empty body")
                return None

            soup = BeautifulSoup(body, 'lxml')

            order_number = self._extract_order_number(soup, body)
            if not order_number:
                logger.error("Failed to extract Academy order number")
                return None

            logger.info(f"Academy order number: {order_number}")

            items = self._extract_order_items(soup)
            if not items:
                logger.error(f"Failed to extract items for Academy order {order_number}")
                return None

            logger.info(f"Academy order {order_number}: found {len(items)} item(s)")

            shipping_address = self._extract_shipping_address(soup)
            logger.debug(f"Academy shipping address: {shipping_address}")

            return AcademyOrderData(
                order_number=order_number,
                items=items,
                shipping_address=shipping_address
            )

        except Exception as e:
            logger.error(f"Error parsing Academy order confirmation: {e}", exc_info=True)
            return None

    def _extract_order_number(self, soup: BeautifulSoup, body: str) -> Optional[str]:
        """Extract order number from the email."""
        # Primary: regex on text content
        text = soup.get_text()
        match = re.search(r'Order\s*#\s*(\d+)', text)
        if match:
            return match.group(1)

        # Fallback: search raw body
        match = re.search(r'Order\s*#\s*(\d+)', body)
        if match:
            return match.group(1)

        # Fallback: search <th> elements
        for th in soup.find_all('th'):
            th_text = th.get_text(strip=True)
            match = re.search(r'Order\s*#\s*(\d+)', th_text)
            if match:
                return match.group(1)

        logger.warning("Could not find Academy order number in email")
        return None

    def _extract_order_items(self, soup: BeautifulSoup) -> List[AcademyOrderItem]:
        """Extract items from order confirmation email.

        Academy uses semantic span IDs:
        - productName, value1 (color), value2 (size), value3 (width),
          sku, currentItemQuantity
        """
        items = []

        product_name_spans = soup.find_all(attrs={"id": "productName"})
        if not product_name_spans:
            logger.warning("No productName spans found in Academy order email")
            return items

        sku_spans = soup.find_all(attrs={"id": "sku"})
        color_spans = soup.find_all(attrs={"id": "value1"})
        size_spans = soup.find_all(attrs={"id": "value2"})
        qty_spans = soup.find_all(attrs={"id": "currentItemQuantity"})

        for i, name_span in enumerate(product_name_spans):
            try:
                product_name = name_span.get_text(strip=True)

                color = ""
                if i < len(color_spans):
                    color = color_spans[i].get_text(strip=True)

                size = ""
                if i < len(size_spans):
                    size = self._clean_size(size_spans[i].get_text(strip=True))

                quantity = 1
                if i < len(qty_spans):
                    qty_text = qty_spans[i].get_text(strip=True)
                    try:
                        quantity = int(qty_text)
                    except ValueError:
                        logger.warning(f"Could not parse quantity '{qty_text}', defaulting to 1")

                unique_id = self._build_unique_id(product_name, color)
                if not unique_id:
                    logger.warning(f"Empty unique_id for Academy item: {product_name}")
                    continue

                item = AcademyOrderItem(
                    unique_id=unique_id,
                    size=size,
                    quantity=quantity,
                    product_name=product_name
                )
                items.append(item)
                logger.debug(f"Academy order item: {item}")

            except Exception as e:
                logger.error(f"Error extracting Academy order item {i}: {e}", exc_info=True)
                continue

        return items

    def _extract_shipping_address(self, soup: BeautifulSoup) -> str:
        """Extract shipping address from the email.

        Address is in a <span> with font-weight after "Shipping Information" text.
        """
        try:
            for td in soup.find_all('td'):
                td_text = td.get_text(strip=True)
                if td_text == "Shipping Information":
                    parent_table = td.find_parent('table')
                    if parent_table:
                        rows = parent_table.find_all('tr')
                        for row_idx, row in enumerate(rows):
                            if td in row.descendants:
                                if row_idx + 1 < len(rows):
                                    addr_td = rows[row_idx + 1].find('td')
                                    if addr_td:
                                        addr_span = addr_td.find('span')
                                        if addr_span:
                                            # Use get_text with separator to handle <br> tags
                                            raw_parts = addr_span.get_text(separator="|").split("|")
                                            parts = [p.strip() for p in raw_parts if p.strip()]
                                            raw_address = ", ".join(parts)
                                            return normalize_shipping_address(raw_address)

            # Fallback: search for address pattern near "Shipping Information"
            text = soup.get_text()
            match = re.search(
                r'Shipping\s+Information\s+'
                r'(.+?)\s*\n\s*(.+?)\s*\n\s*(.+?,\s*[A-Z]{2}\s+\d{5})',
                text
            )
            if match:
                raw_address = f"{match.group(1)}, {match.group(2)}, {match.group(3)}"
                return normalize_shipping_address(raw_address)

        except Exception as e:
            logger.error(f"Error extracting Academy shipping address: {e}", exc_info=True)

        return ""

    # ---------------------------------------------------------------
    # Shipping email parsing
    # ---------------------------------------------------------------

    def parse_shipping_email(self, email_data: EmailData) -> Optional[AcademyShippingData]:
        """Parse an Academy Sports shipping notification email."""
        try:
            body = email_data.html_content or ""
            if not body:
                logger.warning("Academy shipping email has empty body")
                return None

            soup = BeautifulSoup(body, 'lxml')

            order_number = self._extract_order_number(soup, body)
            if not order_number:
                logger.error("Failed to extract order number from Academy shipping email")
                return None

            logger.info(f"Academy shipping order number: {order_number}")

            tracking_number = self._extract_tracking_number(soup)
            logger.info(f"Academy tracking number: {tracking_number}")

            carrier = self._extract_carrier(soup)
            logger.info(f"Academy carrier: {carrier}")

            items = self._extract_shipping_items(soup)
            if not items:
                logger.error(f"Failed to extract items from Academy shipping email for order {order_number}")
                return None

            logger.info(f"Academy shipping {order_number}: {len(items)} item(s) shipped")

            return AcademyShippingData(
                order_number=order_number,
                items=items,
                tracking_number=tracking_number,
                carrier=carrier
            )

        except Exception as e:
            logger.error(f"Error parsing Academy shipping email: {e}", exc_info=True)
            return None

    def _extract_tracking_number(self, soup: BeautifulSoup) -> str:
        """Extract tracking number from shipping email."""
        try:
            for td in soup.find_all('td'):
                td_text = td.get_text(strip=True)
                if td_text == "Tracking Number":
                    parent = td.find_parent('tr')
                    if parent:
                        next_row = parent.find_next_sibling('tr')
                        if next_row:
                            link = next_row.find('a')
                            if link:
                                tracking = link.get_text(strip=True)
                                if tracking and re.match(r'^[\dA-Z]+$', tracking, re.IGNORECASE):
                                    return tracking

            # Fallback: long numeric sequences
            text = soup.get_text()
            match = re.search(r'(?:tracking|track)[^0-9]*(\d{15,34})', text, re.IGNORECASE)
            if match:
                return match.group(1)

        except Exception as e:
            logger.error(f"Error extracting Academy tracking number: {e}", exc_info=True)

        return ""

    def _extract_carrier(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract shipping carrier from shipping email."""
        try:
            for td in soup.find_all('td'):
                td_text = td.get_text(strip=True)
                if td_text == "Shipping Carrier":
                    parent = td.find_parent('tr')
                    if parent:
                        next_row = parent.find_next_sibling('tr')
                        if next_row:
                            carrier_td = next_row.find('td')
                            if carrier_td:
                                carrier = carrier_td.get_text(strip=True)
                                if carrier:
                                    return carrier

            # Fallback: regex
            text = soup.get_text()
            match = re.search(r'Shipping\s+Carrier\s+(\w+)', text)
            if match:
                return match.group(1)

        except Exception as e:
            logger.error(f"Error extracting Academy carrier: {e}", exc_info=True)

        return None

    def _extract_shipping_items(self, soup: BeautifulSoup) -> List[AcademyOrderItem]:
        """Extract items from shipping notification email.

        Shipping email has flat text product descriptions (no span IDs).
        Structure per item:
        - Image: academy.scene7.com/is/image/academy/{id}
        - Product text: 'Brooks W Glycerin 22 WhiteBlack 01 09 Footwear B Width Footwear'
        - SKU: <span bold>SKU:</span> 156905877
        - QTY: <span bold>QTY:</span> 1
        """
        items = []

        images = soup.find_all('img', src=re.compile(r'academy\.scene7\.com/is/image/academy/'))

        for img in images:
            try:
                img_th = img.find_parent('th')
                if not img_th:
                    continue

                # Find the sibling <th> containing product details (skip spacer <th>)
                detail_th = None
                sibling = img_th.find_next_sibling('th')
                while sibling:
                    # Spacer th has width=20 and no content
                    if sibling.get_text(strip=True):
                        detail_th = sibling
                        break
                    sibling = sibling.find_next_sibling('th')

                if not detail_th:
                    logger.warning("Could not find detail column for Academy shipping item")
                    continue

                # Extract product text
                product_text = ""
                product_link = detail_th.find('a')
                if product_link:
                    product_text = product_link.get_text(strip=True)
                else:
                    first_td = detail_th.find('td')
                    if first_td:
                        product_text = first_td.get_text(strip=True)

                detail_text = detail_th.get_text()

                # Extract SKU
                sku = ""
                sku_match = re.search(r'SKU:\s*(\d+)', detail_text)
                if sku_match:
                    sku = sku_match.group(1)

                # Extract QTY
                quantity = 1
                qty_match = re.search(r'QTY:\s*(\d+)', detail_text)
                if qty_match:
                    quantity = int(qty_match.group(1))

                # Parse product name and color from the flat text
                product_name, color, size = self._parse_shipping_product_text(product_text)

                unique_id = self._build_unique_id(product_name, color)
                if not unique_id:
                    logger.warning(f"Empty unique_id for Academy shipping item: {product_text}")
                    continue

                size = self._clean_size(size) if size else ""

                item = AcademyOrderItem(
                    unique_id=unique_id,
                    size=size,
                    quantity=quantity,
                    product_name=product_name
                )
                items.append(item)
                logger.debug(f"Academy shipping item: {item}")

            except Exception as e:
                logger.error(f"Error extracting Academy shipping item: {e}", exc_info=True)
                continue

        return items

    def _parse_shipping_product_text(self, text: str) -> tuple:
        """Parse flat product text from shipping email into (product_name, color, size).

        Input:  'Brooks W Glycerin 22 WhiteBlack 01 09 Footwear B Width Footwear'
        Output: ('Brooks W Glycerin 22', 'WhiteBlack 01', '9')

        Strategy: The text ends with '{size} {category} {width} Width {category}'.
        We find the size by scanning for a 2-digit number followed by a category word.
        """
        text = text.strip()
        if not text:
            return ("", "", "")

        tokens = text.split()

        # Find the size token: a 1-2 digit number followed by a category word
        size_idx = None
        category_words = {
            'footwear', 'apparel', 'equipment', 'accessories', 'outdoors',
            'clothing', 'shoes', 'gear', 'sports'
        }
        width_letters = {'a', 'b', 'c', 'd', 'e', 'ee', 'w', 'm', 'n', '2e', '4e'}

        for i in range(len(tokens) - 1, 0, -1):
            token = tokens[i]
            if re.match(r'^\d{1,2}(?:\.\d)?$', token):
                # Check if followed by a category word or width letter
                if i + 1 < len(tokens):
                    next_lower = tokens[i + 1].lower()
                    if next_lower in category_words or next_lower in width_letters or next_lower == 'width':
                        size_idx = i
                        break

        if size_idx is None:
            # Fallback: look for zero-padded number like '09'
            for i, token in enumerate(tokens):
                if re.match(r'^0\d$', token) and i > 0:
                    size_idx = i
                    break

        if size_idx is not None:
            size = tokens[size_idx]
            # Find where product name ends: last numeric token before color starts
            name_end = self._find_product_name_end(tokens, size_idx)
            product_name = " ".join(tokens[:name_end])
            color = " ".join(tokens[name_end:size_idx])
            return (product_name, color, size)

        logger.warning(f"Could not parse shipping product text structure: {text}")
        return (text, "", "")

    def _find_product_name_end(self, tokens: list, size_idx: int) -> int:
        """Find where the product name ends in the token list.

        Product names end with a numeric model number (e.g., '22' in 'Brooks W Glycerin 22').
        Color tokens follow.
        """
        for i in range(size_idx - 1, 0, -1):
            token = tokens[i]
            if re.match(r'^\d{1,4}$', token):
                remaining = tokens[i + 1:size_idx]
                if remaining and all(
                    re.match(r'^[A-Za-z]+$', t) or re.match(r'^\d{1,2}$', t)
                    for t in remaining
                ):
                    return i + 1

        # Fallback: capital letter after a number signals color start
        for i in range(1, size_idx):
            prev = tokens[i - 1]
            curr = tokens[i]
            if re.match(r'^\d+$', prev) and re.match(r'^[A-Z][a-z]', curr):
                return i

        if size_idx > 1:
            return size_idx - 1
        return size_idx
