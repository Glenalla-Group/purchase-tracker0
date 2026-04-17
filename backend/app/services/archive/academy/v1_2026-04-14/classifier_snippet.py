# Snippet: Academy Sports sections from backend/app/services/retailer_email_classifier.py
# Archived: 2026-04-14 (pre-edit state — before replacing "Your order is on the way"
# shipping subject with "Packed and Ready to Ship" subjects)

# Line 45 — import
from app.services.academy_parser import AcademyEmailParser

# Line 106 — instantiation in __init__
# self._academy = AcademyEmailParser()

# Lines 240-243 — shipping detection in _check_shipping_or_cancellation()
# Academy Sports (shipping only, no cancellation)
# if self._academy.is_academy_email(email_data):
#     if self._academy.is_shipping_email(email_data):
#         return ClassificationResult("academy", EmailType.SHIPPING, "Academy Sports")

# Line 304 — entry in confirmation_checks list
# ("academy", "Academy Sports", self._academy, "is_academy_email"),
