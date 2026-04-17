# Academy Sports Parser — v1 Archive

**Archived:** 2026-04-14
**Reason:** Academy Sports changed their shipping email subjects. The old `"Your order is on the way"` subject (matching "Items have been shipped" status emails) is being replaced with two new earlier-stage subjects:
1. `"Your items are packed and ready to ship"` (full shipment)
2. `"Part of Your Order is Packed and Ready to Ship"` (partial shipment, possibly with multiple tracking numbers across different carriers)

**Previous state:**
- Order confirmation (`parse_email`) — supported ✓
- Shipping (`parse_shipping_email`) — supported ✓ for subject `"Your order is on the way"` only, single tracking/carrier
- Cancellation — not supported

**Files archived:** 7 files
- `academy_parser.py` — backend parser (full copy, pre-edit)
- `lambda_parser.py` — lambda parser (full copy, pre-edit)
- `classifier_snippet.py` — retailer sections from backend `retailer_email_classifier.py`
- `order_processor_snippet.py` — retailer sections from backend `retailer_order_processor.py`
- `update_processor_snippet.py` — retailer sections from backend `retailer_order_update_processor.py`
- `lambda_classifier_snippet.py` — retailer sections from lambda `classifier.py`
- `lambda_parser_registry_snippet.py` — retailer entry from lambda `parsers/__init__.py`

**Source file locations:**
- Backend parser: `backend/app/services/academy_parser.py`
- Backend classifier: `backend/app/services/retailer_email_classifier.py`
- Backend order processor: `backend/app/services/retailer_order_processor.py`
- Backend update processor: `backend/app/services/retailer_order_update_processor.py`
- Lambda parser: `lambda-purchase-tracker/src/parsers/academy_parser.py`
- Lambda classifier: `lambda-purchase-tracker/src/classifier.py`
- Lambda parser registry: `lambda-purchase-tracker/src/parsers/__init__.py`
