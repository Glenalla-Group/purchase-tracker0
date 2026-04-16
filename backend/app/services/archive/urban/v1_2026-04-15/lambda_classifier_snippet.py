# Urban Outfitters sections extracted from lambda-purchase-tracker/src/classifier.py
# Archived: 2026-04-15

# --- Import (line 30) ---
from src.parsers.urban_parser import UrbanOutfittersEmailParser

# --- Instantiation in __init__ (line 93) ---
# self._urban = UrbanOutfittersEmailParser()

# --- Shipping/cancellation detection in _check_shipping_or_cancellation() (lines 227-232) ---
# # Urban Outfitters
# if self._urban.is_urban_email(email_data):
#     if self._urban.is_shipping_email(email_data):
#         return ClassificationResult("urban", EmailType.SHIPPING, "Urban Outfitters")
#     if self._urban.is_cancellation_email(email_data):
#         return ClassificationResult("urban", EmailType.CANCELLATION, "Urban Outfitters")

# --- Confirmation check in _check_order_confirmation() (line 328) ---
# ("urbanoutfitters", "Urban Outfitters", self._urban, "is_urban_email"),
