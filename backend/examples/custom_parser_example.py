"""
Examples of custom email parsing for specific merchants.

This file shows how to create specialized parsers for different email formats.
"""

from bs4 import BeautifulSoup
import re
from typing import Dict, Any, Optional


class AmazonEmailParser:
    """Parser specifically for Amazon order confirmation emails."""
    
    @staticmethod
    def parse(html_content: str) -> Dict[str, Any]:
        """
        Parse Amazon order confirmation email.
        
        Args:
            html_content: HTML content of Amazon email
        
        Returns:
            Dictionary with extracted order information
        """
        soup = BeautifulSoup(html_content, 'lxml')
        extracted = {}
        
        # Amazon order number (usually in format: XXX-XXXXXXX-XXXXXXX)
        order_pattern = r'Order #\s*(\d{3}-\d{7}-\d{7})'
        text = soup.get_text()
        match = re.search(order_pattern, text)
        if match:
            extracted['order_number'] = match.group(1)
        
        # Total amount
        total_elem = soup.find(string=re.compile(r'Order Total:', re.IGNORECASE))
        if total_elem:
            parent = total_elem.find_parent()
            if parent:
                amount_text = parent.get_text()
                amount_match = re.search(r'\$([0-9,]+\.\d{2})', amount_text)
                if amount_match:
                    extracted['total_amount'] = amount_match.group(1)
        
        # Items
        items = []
        # Amazon usually has product names in specific divs
        product_links = soup.find_all('a', href=re.compile(r'/dp/|/gp/product/'))
        for link in product_links[:10]:  # Limit to first 10
            item_name = link.get_text(strip=True)
            if item_name and len(item_name) > 3:
                items.append(item_name)
        
        extracted['items'] = items
        extracted['merchant'] = 'Amazon'
        
        return extracted


class EbayEmailParser:
    """Parser specifically for eBay transaction emails."""
    
    @staticmethod
    def parse(html_content: str) -> Dict[str, Any]:
        """Parse eBay transaction email."""
        soup = BeautifulSoup(html_content, 'lxml')
        extracted = {}
        
        # eBay order number
        order_pattern = r'Order number:\s*(\d+-\d+)'
        text = soup.get_text()
        match = re.search(order_pattern, text)
        if match:
            extracted['order_number'] = match.group(1)
        
        # Total
        total_pattern = r'Total:\s*\$([0-9,]+\.\d{2})'
        match = re.search(total_pattern, text)
        if match:
            extracted['total_amount'] = match.group(1)
        
        extracted['merchant'] = 'eBay'
        
        return extracted


class GenericEcommerceParser:
    """Generic parser for common e-commerce email patterns."""
    
    PATTERNS = {
        'order_number': [
            r'Order\s*(?:Number|#|ID)?\s*:?\s*([A-Z0-9-]+)',
            r'Confirmation\s*(?:Number|#)?\s*:?\s*([A-Z0-9-]+)',
            r'Reference\s*(?:Number|#)?\s*:?\s*([A-Z0-9-]+)',
        ],
        'total': [
            r'(?:Total|Amount|Grand Total)\s*:?\s*\$?([0-9,]+\.\d{2})',
            r'Total\s*(?:Amount|Price)?\s*:?\s*USD\s*([0-9,]+\.\d{2})',
        ],
        'tracking': [
            r'(?:Tracking|Track)\s*(?:Number|#)?\s*:?\s*([A-Z0-9]+)',
            r'(?:Carrier|Shipped via)\s*:?\s*([A-Z\s]+)\s*-?\s*([A-Z0-9]+)',
        ],
        'date': [
            r'(?:Order|Purchase|Transaction)\s*Date\s*:?\s*(\w+\s+\d{1,2},?\s+\d{4})',
            r'Date\s*:?\s*(\d{1,2}/\d{1,2}/\d{2,4})',
        ]
    }
    
    @staticmethod
    def parse(html_content: str, sender_domain: str = '') -> Dict[str, Any]:
        """
        Parse using generic e-commerce patterns.
        
        Args:
            html_content: HTML content
            sender_domain: Email sender domain for context
        
        Returns:
            Extracted information
        """
        soup = BeautifulSoup(html_content, 'lxml')
        text = soup.get_text()
        extracted = {}
        
        # Try each pattern type
        for field, patterns in GenericEcommerceParser.PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    extracted[field] = match.group(1)
                    break
        
        # Extract merchant from domain
        if sender_domain:
            domain_parts = sender_domain.split('.')
            if len(domain_parts) >= 2:
                extracted['merchant'] = domain_parts[-2].capitalize()
        
        return extracted


class EmailParserFactory:
    """
    Factory class to select appropriate parser based on email characteristics.
    """
    
    PARSERS = {
        'amazon.com': AmazonEmailParser,
        'ebay.com': EbayEmailParser,
    }
    
    @staticmethod
    def get_parser(sender_email: str) -> Any:
        """
        Get appropriate parser based on sender email.
        
        Args:
            sender_email: Email sender address
        
        Returns:
            Parser class
        """
        # Extract domain
        match = re.search(r'@([^@]+)$', sender_email.lower())
        if match:
            domain = match.group(1)
            
            # Check if we have a specialized parser
            for key, parser in EmailParserFactory.PARSERS.items():
                if key in domain:
                    return parser
        
        # Default to generic parser
        return GenericEcommerceParser
    
    @staticmethod
    def parse_email(sender: str, html_content: str) -> Dict[str, Any]:
        """
        Parse email using appropriate parser.
        
        Args:
            sender: Email sender
            html_content: HTML content
        
        Returns:
            Extracted information
        """
        parser = EmailParserFactory.get_parser(sender)
        return parser.parse(html_content)


# Integration example:
"""
# In app/services/email_parser.py, modify the parse_email method:

from examples.custom_parser_example import EmailParserFactory

def parse_email(self, email_data: EmailData) -> ExtractedInfo:
    # ... existing code ...
    
    # Use custom parser based on sender
    if email_data.html_content:
        custom_data = EmailParserFactory.parse_email(
            email_data.sender,
            email_data.html_content
        )
        
        # Merge custom data with extracted_info
        if custom_data.get('order_number'):
            extracted_info.order_number = custom_data['order_number']
        if custom_data.get('total_amount'):
            extracted_info.total_amount = custom_data['total_amount']
        if custom_data.get('merchant'):
            extracted_info.merchant = custom_data['merchant']
        if custom_data.get('items'):
            extracted_info.items = custom_data['items']
    
    return extracted_info
"""


if __name__ == "__main__":
    # Example usage
    sample_html = """
    <html>
        <body>
            <h1>Order Confirmation</h1>
            <p>Order #: 123-4567890-1234567</p>
            <p>Order Total: $49.99</p>
            <p>Items:</p>
            <ul>
                <li>Product Name Here</li>
            </ul>
        </body>
    </html>
    """
    
    parser = GenericEcommerceParser()
    result = parser.parse(sample_html)
    print("Extracted:", result)



