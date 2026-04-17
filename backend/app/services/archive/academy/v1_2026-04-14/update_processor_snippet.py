# Snippet: Academy Sports sections from backend/app/services/retailer_order_update_processor.py
# Archived: 2026-04-14 (pre-edit state — unchanged by this edit, since
# shipping_data.tracking_number is now a @property returning the comma-joined list)

# Line 101 — import
from app.services.academy_parser import AcademyEmailParser, AcademyShippingData

# Line 150 — instantiation in __init__
# self.academy_parser = AcademyEmailParser()

# Lines 1344-1350 — dispatch in process_single_shipping_email()
# elif retailer_name == 'academy':
#     shipping_data = self.academy_parser.parse_shipping_email(email_data)
#
#     if not shipping_data:
#         return {'success': False, 'error': "Failed to parse Academy Sports shipping data"}
#
#     success, error_msg = self._process_academy_shipping_update(shipping_data)

# Lines 3238-3310 — _process_academy_shipping_update()
# def _process_academy_shipping_update(self, shipping_data: AcademyShippingData) -> Tuple[bool, Optional[str]]:
#     """
#     Process Academy Sports shipping update: Update shipped_to_pw and tracking.
#     Match by order_number + unique_id + size.
#     """
#     try:
#         logger.info(f"Processing Academy shipping update for order {shipping_data.order_number}")
#         items_updated = 0
#
#         for item in shipping_data.items:
#             normalized_size = self._normalize_size(item.size)
#             matching_records = self.db.query(PurchaseTracker).join(
#                 OASourcing, PurchaseTracker.oa_sourcing_id == OASourcing.id
#             ).outerjoin(
#                 AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
#             ).filter(
#                 and_(
#                     PurchaseTracker.order_number == shipping_data.order_number,
#                     OASourcing.unique_id == item.unique_id,
#                     or_(
#                         AsinBank.size == item.size,
#                         AsinBank.size == normalized_size
#                     )
#                 )
#             ).all()
#             ...
#             for record in matching_records:
#                 current_shipped = record.shipped_to_pw or 0
#                 record.shipped_to_pw = current_shipped + item.quantity
#                 if not record.tracking and shipping_data.tracking_number:
#                     record.tracking = shipping_data.tracking_number
#                 ...
