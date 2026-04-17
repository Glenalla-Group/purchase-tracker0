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

---

## Changes Made (appended after edit)

**Edit date:** 2026-04-14
**Edit type:** Replace shipping subject regex + add multi-tracking/multi-carrier support

**Parser changes** (`backend/app/services/academy_parser.py`):
- Subject regex changed from `r"your\s+order\s+is\s+on\s+the\s+way"` to
  `r"(?:part\s+of\s+)?your\s+(?:items|order)\s+(?:are|is)\s+packed\s+and\s+ready\s+to\s+ship"`
  (matches both new full + partial subjects).
- `GMAIL_SHIPPING_QUERY` updated to `"packed and ready to ship"`.
- `AcademyShippingData` model: replaced `tracking_number: str` with `tracking_numbers: List[str]`
  and `carrier: Optional[str]` with `carriers: List[str]`; added compat `@property`
  methods (`tracking_number`, `carrier`) that comma-join the lists.
- Renamed `_extract_tracking_number` → `_extract_tracking_numbers` (returns `List[str]`,
  iterates all `<a>` tags in the row below "Tracking Number" `<td>`).
- Renamed `_extract_carrier` → `_extract_carriers` (returns `List[str]`, splits the
  next row's text on `<br>`-derived newlines to handle partial emails' multi-carrier
  `<text>...<br>` nested structure).
- Module docstring updated with new subject list + multi-package HTML notes.

**Files modified:**
- `backend/app/services/academy_parser.py` — parser rewrite
- `lambda-purchase-tracker/src/parsers/academy_parser.py` — synced (with import + `html.parser` swaps)
- `backend/test/run_all_shipping_tests.py:105` — updated test entry (files list + subject)
- `backend/feed/order-shipping-emails/academy.txt` — deleted (old "on the way" fixture)
- `backend/feed/order-shipping-emails/academy1.txt` — added (full packed)
- `backend/feed/order-shipping-emails/academy2.txt` — added (partial packed, 2 carriers + 2 trackings)

**Files NOT modified** (generic, unaffected):
- `backend/app/services/retailer_email_classifier.py`
- `backend/app/services/retailer_order_processor.py`
- `backend/app/services/retailer_order_update_processor.py` (uses `tracking_number` @property — still works)
- `lambda-purchase-tracker/src/classifier.py`
- `lambda-purchase-tracker/src/processor.py`
- `lambda-purchase-tracker/src/parsers/__init__.py`
- `lambda-purchase-tracker/src/retailer_registry.py`

**Test results:**
- Shipping suite: 57/57 passed (including `academy1.txt` + `academy2.txt`)
- Order suite: 63/64 passed (1 pre-existing `fit2run1.txt` failure, unrelated)
- Cancellation suite: 21/24 passed (3 pre-existing non-Academy failures, unrelated)

**Gate 1 parse output:**
- `academy1.txt` (full): order #500659500, 1 tracking (USPS), 1 item (brooks-w-glycerin-22-whiteblack01, size 9, qty 1)
- `academy2.txt` (partial): order #502369998, 2 trackings (USPS + FEDEX), 2 items (nike-m-pegasus-41-whiteturquoiseoraqua, size 10, qty 1 each)
- Subject matching: old `"Your order is on the way"` correctly rejected.

**Deployment:** SAM stack `purchase-tracker-lambda` in `us-east-2` updated successfully. Slack retailer status dashboard refreshed (canvas F0AP7UNSX16).

**Git commits:**
- `eeaf2e4` — archive v1
- `77e5393` — parser + tests + Lambda sync
- (deploy marker commit appended after this CHANGELOG update)
