# Snippet: Academy Sports sections from lambda-purchase-tracker/src/classifier.py
# Archived: 2026-04-14 (pre-edit state — unchanged by this edit)

# Line 52 — import
from src.parsers.academy_parser import AcademyEmailParser

# Line 117 — instantiation in __init__
# self._academy = AcademyEmailParser()

# Lines 279-282 — shipping detection in _check_shipping_or_cancellation()
# Academy Sports (shipping only, no cancellation)
# if self._academy.is_academy_email(email_data):
#     if self._academy.is_shipping_email(email_data):
#         return ClassificationResult("academy", EmailType.SHIPPING, "Academy Sports")

# Line 348 — entry in confirmation_checks list
# ("academy", "Academy Sports", self._academy, "is_academy_email"),
