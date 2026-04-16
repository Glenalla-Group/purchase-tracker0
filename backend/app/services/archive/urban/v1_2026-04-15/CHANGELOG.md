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

## Changes Made (appended after edit)
**Edit date:** 2026-04-15
**Edit type:** Slug normalization + shipping dispatch + new subject pattern + URL extractor fix
**Files modified:**
- backend/app/services/urban_parser.py (added _normalize_slug, new subject pattern, updated docstring)
- backend/app/services/retailer_email_classifier.py (added Urban to _check_shipping_or_cancellation)
- backend/app/services/retailer_order_update_processor.py (added UrbanOutfittersShippingData import, shipping dispatch, _process_urban_shipping_update handler)
- lambda-purchase-tracker/src/unique_id_extractor.py (fixed /shop/hybrid/ path, added slug normalization)
- lambda-purchase-tracker/src/parsers/urban_parser.py (synced from backend)
- lambda-purchase-tracker/src/parsers/__init__.py (added 'urbanoutfitters' alias)
- lambda-purchase-tracker/src/retailer_registry.py (updated shipping_types to full + partial)
- backend/test/run_all_order_tests.py (added urban1-6.txt test files + new subject)

**Tests added:**
- 6 new order confirmation .eml files extracted to backend/feed/order-confirmation-emails/urban{1-6}.txt covering Nike, Gola, On, Sperry brands

**Verification:**
- Order confirmation: 7/7 Urban tests pass (urban + urban1-6)
- Shipping: 3/3 Urban tests pass
- Cancellation: 1/1 Urban test passes
- URL extractor vs email parser crossover: ALL MATCH for all 6 new emails
- Lambda deployed successfully to us-east-2 (stack: purchase-tracker-lambda)

**Git commits:** bb369b8 (archive), 0e97fec (changes)
