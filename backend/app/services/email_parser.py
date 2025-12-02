"""
Email parser service using BeautifulSoup for HTML content extraction.
"""

import logging
import re
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from app.models.email import EmailData, ExtractedInfo

logger = logging.getLogger(__name__)


class EmailParser:
    """Service class for parsing email HTML content and extracting information."""
    
    def __init__(self):
        """Initialize the email parser."""
        pass
    
    def parse_email(self, email_data: EmailData) -> ExtractedInfo:
        """
        Parse email and extract relevant information.
        
        Args:
            email_data: EmailData object containing email information
        
        Returns:
            ExtractedInfo object with parsed data
        """
        try:
            extracted_info = ExtractedInfo(
                email_id=email_data.message_id,
                subject=email_data.subject,
                sender=email_data.sender,
                extraction_successful=True
            )
            
            # Use HTML content if available, otherwise use text content
            content = email_data.html_content or email_data.text_content
            
            if not content:
                logger.warning(f"No content available for email {email_data.message_id}")
                extracted_info.extraction_successful = False
                extracted_info.error_message = "No content available"
                return extracted_info
            
            # Parse HTML content
            if email_data.html_content:
                soup = BeautifulSoup(email_data.html_content, 'lxml')
                extracted_info.extracted_data = self._extract_from_html(soup, email_data)
                
                # Try to extract purchase-specific information
                self._extract_purchase_info(soup, extracted_info)
            else:
                # Parse plain text
                extracted_info.extracted_data = self._extract_from_text(content)
            
            logger.info(f"Successfully parsed email {email_data.message_id}")
            return extracted_info
        
        except Exception as e:
            logger.error(f"Error parsing email {email_data.message_id}: {e}")
            return ExtractedInfo(
                email_id=email_data.message_id,
                subject=email_data.subject,
                sender=email_data.sender,
                extraction_successful=False,
                error_message=str(e)
            )
    
    def _extract_from_html(self, soup: BeautifulSoup, email_data: EmailData) -> Dict[str, Any]:
        """
        Extract information from HTML content.
        
        Args:
            soup: BeautifulSoup object of HTML content
            email_data: Original email data
        
        Returns:
            Dictionary of extracted data
        """
        extracted = {}
        
        # Extract all text
        extracted['full_text'] = soup.get_text(separator=' ', strip=True)
        
        # Extract all links
        links = []
        for link in soup.find_all('a', href=True):
            links.append({
                'text': link.get_text(strip=True),
                'url': link['href']
            })
        extracted['links'] = links
        
        # Extract all images
        images = []
        for img in soup.find_all('img', src=True):
            images.append({
                'alt': img.get('alt', ''),
                'src': img['src']
            })
        extracted['images'] = images
        
        # Extract tables (useful for order details)
        tables = []
        for table in soup.find_all('table'):
            table_data = self._parse_table(table)
            if table_data:
                tables.append(table_data)
        extracted['tables'] = tables
        
        # Extract specific classes or IDs that might contain important info
        # Common patterns in e-commerce emails
        patterns = [
            'order-number', 'order-id', 'order_number', 'orderId',
            'total', 'amount', 'price', 'cost',
            'date', 'order-date', 'purchase-date',
            'item', 'product', 'items-list'
        ]
        
        for pattern in patterns:
            # Search by ID
            element = soup.find(id=re.compile(pattern, re.IGNORECASE))
            if element:
                extracted[f'id_{pattern}'] = element.get_text(strip=True)
            
            # Search by class
            elements = soup.find_all(class_=re.compile(pattern, re.IGNORECASE))
            if elements:
                extracted[f'class_{pattern}'] = [el.get_text(strip=True) for el in elements]
        
        return extracted
    
    def _parse_table(self, table) -> List[List[str]]:
        """
        Parse HTML table into list of lists.
        
        Args:
            table: BeautifulSoup table element
        
        Returns:
            List of rows, each row is a list of cell values
        """
        table_data = []
        rows = table.find_all('tr')
        
        for row in rows:
            cells = row.find_all(['td', 'th'])
            row_data = [cell.get_text(strip=True) for cell in cells]
            if row_data:  # Only add non-empty rows
                table_data.append(row_data)
        
        return table_data
    
    def _extract_from_text(self, text: str) -> Dict[str, Any]:
        """
        Extract information from plain text content.
        
        Args:
            text: Plain text content
        
        Returns:
            Dictionary of extracted data
        """
        extracted = {
            'full_text': text
        }
        
        # Extract URLs using regex
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        urls = re.findall(url_pattern, text)
        extracted['urls'] = urls
        
        # Extract email addresses
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, text)
        extracted['emails'] = emails
        
        # Extract phone numbers (basic pattern)
        phone_pattern = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
        phones = re.findall(phone_pattern, text)
        extracted['phones'] = phones
        
        return extracted
    
    def _extract_purchase_info(self, soup: BeautifulSoup, extracted_info: ExtractedInfo) -> None:
        """
        Extract purchase-specific information from HTML.
        This is a customizable method - modify based on your specific needs.
        
        Args:
            soup: BeautifulSoup object
            extracted_info: ExtractedInfo object to populate
        """
        text = soup.get_text()
        
        # Extract order number (common patterns)
        order_patterns = [
            r'Order\s*#?\s*:?\s*([A-Z0-9-]+)',
            r'Order\s+Number\s*:?\s*([A-Z0-9-]+)',
            r'Order\s+ID\s*:?\s*([A-Z0-9-]+)',
            r'Confirmation\s*#?\s*:?\s*([A-Z0-9-]+)',
        ]
        
        for pattern in order_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                extracted_info.order_number = match.group(1)
                break
        
        # Extract total amount (common patterns)
        amount_patterns = [
            r'Total\s*:?\s*\$?([0-9,]+\.?\d{0,2})',
            r'Amount\s*:?\s*\$?([0-9,]+\.?\d{0,2})',
            r'Grand\s+Total\s*:?\s*\$?([0-9,]+\.?\d{0,2})',
        ]
        
        for pattern in amount_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                extracted_info.total_amount = match.group(1)
                break
        
        # Extract merchant/company name from sender or subject
        # This is a basic implementation - customize based on your needs
        sender_match = re.search(r'<([^@>]+)@', extracted_info.sender)
        if sender_match:
            extracted_info.merchant = sender_match.group(1)
        
        # Extract date (look for date patterns)
        date_patterns = [
            r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'(\w+ \d{1,2},? \d{4})',
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                extracted_info.purchase_date = match.group(1)
                break
        
        # Extract items (look for product names)
        # This is highly dependent on email structure
        # Example: finding list items
        items_list = soup.find_all(['li', 'tr'])
        potential_items = []
        
        for item in items_list[:10]:  # Limit to first 10 to avoid noise
            item_text = item.get_text(strip=True)
            # Filter out very short or very long items
            if 5 < len(item_text) < 200 and not item_text.startswith(('http', 'www')):
                potential_items.append(item_text)
        
        if potential_items:
            extracted_info.items = potential_items
    
    def extract_custom_data(
        self, 
        html_content: str, 
        selectors: Dict[str, str]
    ) -> Dict[str, Optional[str]]:
        """
        Extract custom data using CSS selectors.
        
        This method allows flexible extraction based on specific CSS selectors.
        
        Args:
            html_content: HTML content to parse
            selectors: Dictionary mapping field names to CSS selectors
        
        Returns:
            Dictionary with extracted values for each field
        
        Example:
            selectors = {
                'order_id': '#order-number',
                'total': '.total-amount',
                'tracking': 'a[href*="tracking"]'
            }
        """
        soup = BeautifulSoup(html_content, 'lxml')
        extracted = {}
        
        for field_name, selector in selectors.items():
            try:
                element = soup.select_one(selector)
                if element:
                    extracted[field_name] = element.get_text(strip=True)
                else:
                    extracted[field_name] = None
            except Exception as e:
                logger.error(f"Error extracting {field_name} with selector {selector}: {e}")
                extracted[field_name] = None
        
        return extracted

