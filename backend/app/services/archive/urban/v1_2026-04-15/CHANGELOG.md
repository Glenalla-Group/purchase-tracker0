# Urban Outfitters Parser -- v1 Archive
**Archived:** 2026-04-15
**Reason:** Slug normalization (strip womens/mens + trailing digits) + shipping registration + new subject pattern
**Previous state:** Order confirmation, shipping parser (unregistered), cancellation (registered in update processor only)
**Files archived:** 7 files + this changelog
**Source file locations:**
- Backend parser: backend/app/services/urban_parser.py
- Backend classifier: backend/app/services/retailer_email_classifier.py
- Backend order processor: backend/app/services/retailer_order_processor.py
- Backend update processor: backend/app/services/retailer_order_update_processor.py
- Lambda parser: lambda-purchase-tracker/src/parsers/urban_parser.py
- Lambda classifier: lambda-purchase-tracker/src/classifier.py
- Lambda parser registry: lambda-purchase-tracker/src/parsers/__init__.py
