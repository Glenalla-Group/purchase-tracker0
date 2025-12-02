"""
Helper utility functions.
"""

import re
from typing import Optional


def clean_email_address(email: str) -> str:
    """
    Extract clean email address from format like "Name <email@example.com>".
    
    Args:
        email: Email string potentially containing name
    
    Returns:
        Clean email address
    """
    match = re.search(r'<([^>]+)>', email)
    if match:
        return match.group(1)
    return email.strip()


def extract_domain(email: str) -> Optional[str]:
    """
    Extract domain from email address.
    
    Args:
        email: Email address
    
    Returns:
        Domain name or None
    """
    clean = clean_email_address(email)
    match = re.search(r'@([^@]+)$', clean)
    if match:
        return match.group(1)
    return None


def sanitize_html(html: str) -> str:
    """
    Remove potentially dangerous HTML elements.
    
    Args:
        html: HTML content
    
    Returns:
        Sanitized HTML
    """
    # Remove script tags
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    
    # Remove style tags
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    
    # Remove event handlers
    html = re.sub(r'\s*on\w+="[^"]*"', '', html, flags=re.IGNORECASE)
    html = re.sub(r"\s*on\w+='[^']*'", '', html, flags=re.IGNORECASE)
    
    return html


def format_currency(amount: str) -> Optional[float]:
    """
    Convert currency string to float.
    
    Args:
        amount: Currency string (e.g., "$1,234.56")
    
    Returns:
        Float value or None
    """
    try:
        # Remove currency symbols and commas
        clean = re.sub(r'[$,\s]', '', amount)
        return float(clean)
    except (ValueError, TypeError):
        return None


def is_purchase_email(subject: str, sender: str) -> bool:
    """
    Determine if email is likely a purchase confirmation.
    
    Args:
        subject: Email subject
        sender: Email sender
    
    Returns:
        True if likely a purchase email
    """
    # Keywords that indicate purchase
    purchase_keywords = [
        'order', 'purchase', 'receipt', 'confirmation',
        'invoice', 'payment', 'shipped', 'tracking',
        'delivery', 'thank you for your order'
    ]
    
    subject_lower = subject.lower()
    
    return any(keyword in subject_lower for keyword in purchase_keywords)



