# Urban Outfitters sections extracted from backend/app/services/retailer_email_classifier.py
# Archived: 2026-04-15

# --- Import (line 28) ---
from app.services.urban_parser import UrbanOutfittersEmailParser

# --- Instantiation in __init__ (line 87) ---
# self._urban = UrbanOutfittersEmailParser()

# --- Confirmation check entry in _check_order_confirmation() (line 289) ---
# ("urbanoutfitters", "Urban Outfitters", self._urban, "is_urban_email"),

# NOTE: Urban Outfitters is NOT in _check_shipping_or_cancellation() — that's the gap being fixed
