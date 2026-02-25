"""
Address Utility Functions
Normalize shipping addresses to standard formats
"""

import re
import logging

logger = logging.getLogger(__name__)


def normalize_shipping_address(raw_address: str) -> str:
    """
    Normalize shipping addresses to standard formats.
    
    Handles two main patterns:
    1. "595 Lloyd Lane" variations -> "595 Lloyd Lane"
    2. "2025 Vista Ave" variations -> "2025 Vista Ave"
    
    Args:
        raw_address: Raw address string from email
        
    Returns:
        Normalized address string
    """
    if not raw_address:
        return ""
    
    # Clean up whitespace, remove trailing commas, and standardize
    address_clean = re.sub(r'\s+', ' ', raw_address.strip())
    address_clean = re.sub(r',\s*$', '', address_clean)  # Remove trailing comma
    address_lower = address_clean.lower()
    
    # Pattern 1: 595 Lloyd Lane variations
    # Matches: "595 LLOYD LN", "595 Lloyd Ln", "595 Lloyd Lane", "595 LLOYD LANE"
    # With any of: STE D, Ste D, -NERT, etc.
    if re.search(r'595\s+(lloyd|LLOYD)', address_lower):
        return "595 Lloyd Lane"
    
    # Pattern 2: 2025 Vista Ave variations
    # Matches: "2025 Vista Ave", "2025 VISTA AVE", "2025 Vista Avenue"
    if re.search(r'2025\s+(vista|VISTA)', address_lower):
        return "2025 Vista Ave"
    
    # If no pattern matches, return the cleaned address
    logger.warning(f"Unknown address pattern: {address_clean}")
    return address_clean


def extract_shipping_address_from_text(text: str, patterns: list = None) -> str:
    """
    Extract shipping address from text using common patterns.
    
    Args:
        text: Text content to search
        patterns: Optional list of regex patterns to use
        
    Returns:
        Extracted and normalized address, or empty string if not found
    """
    if not text:
        return ""
    
    # Default patterns if none provided
    if patterns is None:
        patterns = [
            # Pattern: "595 Lloyd Ln STE D Independence, OR 97351"
            r'(595\s+[Ll][Ll][Oo][Yy][Dd]\s+(?:Ln|Lane|LN|LANE)(?:[^,\n]*?)(?:,?\s*Independence,?\s*OR\s*\d{5}(?:-\d{4})?)?)',
            # Pattern: "2025 Vista Ave SE # B130, Salem, OR 97302"
            r'(2025\s+[Vv][Ii][Ss][Tt][Aa]\s+(?:Ave|Avenue|AVE)(?:[^,\n]*?)(?:,?\s*Salem,?\s*OR\s*\d{5}(?:-\d{4})?)?)',
        ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            raw_address = match.group(1)
            return normalize_shipping_address(raw_address)
    
    return ""

