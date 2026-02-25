"""
Utility functions for calculating purchase status and location
based on fulfillment tracking fields.
"""

from typing import Tuple, Optional


def calculate_status_and_location(
    shipped_to_pw: Optional[int] = None,
    checked_in: Optional[int] = None,
    shipped_out: Optional[int] = None,
    final_qty: Optional[int] = None
) -> Tuple[str, str]:
    """
    Calculate status and location based on fulfillment tracking fields.
    
    Status Logic:
    - Pending: shipped_to_pw is blank (None or 0)
    - Shipped to PW: shipped_to_pw > 0
    - Checked in: checked_in == shipped_to_pw
    - Partially Checked in: shipped_to_pw > 0 AND checked_in < shipped_to_pw AND shipped_out is blank
    - Partially Shipped Out: shipped_to_pw > 0 AND checked_in > 0 AND shipped_out < checked_in
    - Shipped out: shipped_to_pw > 0 AND checked_in >= shipped_to_pw AND shipped_out >= checked_in
    - Cancelled: final_qty < 1
    
    Args:
        shipped_to_pw: Number of items shipped to PrepWorx (defaults to 0 if None)
        checked_in: Number of items checked in (defaults to 0 if None)
        shipped_out: Number of items shipped out (defaults to 0 if None)
        final_qty: Final quantity (defaults to None)
    
    Returns:
        Tuple of (status, location)
    """
    # Normalize None values to 0 for comparison
    shipped_to_pw = shipped_to_pw or 0
    checked_in = checked_in or 0
    shipped_out = shipped_out or 0
    
    # Check for cancelled status first (highest priority)
    if final_qty is not None and final_qty < 1:
        return ("Cancelled", "Cancelled")
    
    # Pending: shipped_to_pw is blank (0 or None)
    if shipped_to_pw == 0:
        return ("Pending", "Retailer")
    
    # Shipped out: shipped_to_pw > 0 AND checked_in >= shipped_to_pw AND shipped_out >= checked_in
    if checked_in >= shipped_to_pw and shipped_out >= checked_in:
        return ("Shipped out", "AMZ")
    
    # Partially Shipped Out: shipped_to_pw > 0 AND checked_in > 0 AND shipped_out < checked_in
    if checked_in > 0 and shipped_out < checked_in:
        return ("Partially Shipped Out", "PW/AMZ")
    
    # Checked in: checked_in == shipped_to_pw
    if checked_in == shipped_to_pw:
        return ("Checked in", "PW")
    
    # Partially Checked in: shipped_to_pw > 0 AND checked_in < shipped_to_pw AND shipped_out is blank (0)
    if checked_in < shipped_to_pw and shipped_out == 0:
        return ("Partially Checked in", "Retailer/PW")
    
    # Shipped to PW: shipped_to_pw > 0 (default case when shipped but not checked in yet)
    if shipped_to_pw > 0:
        return ("Shipped to PW", "Transit")
    
    # Fallback to Pending
    return ("Pending", "Retailer")

