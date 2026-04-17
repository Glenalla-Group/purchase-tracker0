# Snippet: Academy Sports sections from backend/app/services/retailer_order_processor.py
# Archived: 2026-04-14 (pre-edit state — unchanged by this edit, kept for completeness)

# Line 45 — import
from app.services.academy_parser import AcademyEmailParser, AcademyOrderData, AcademyOrderItem

# Line 100 — instantiation in __init__
# self.academy_parser = AcademyEmailParser()

# Lines 5561-5604 — _process_academy_order()
# def _process_academy_order(self, order_data: AcademyOrderData) -> Tuple[bool, Optional[str]]:
#     """Process an Academy Sports order and create purchase tracker records."""
#     try:
#         academy_retailer = self.db.query(Retailer).filter(
#             Retailer.name.ilike('%Academy%')
#         ).first()
#
#         if not academy_retailer:
#             return False, "Academy Sports retailer not found in database"
#
#         created_count = 0
#         skipped_count = 0
#
#         for item in order_data.items:
#             success, error = self._create_purchase_tracker_record_academy(
#                 order_number=order_data.order_number,
#                 item=item,
#                 retailer=academy_retailer,
#                 shipping_address=order_data.shipping_address
#             )
#
#             if success:
#                 created_count += 1
#             else:
#                 logger.warning(f"Could not create record for Academy item {item.unique_id}: {error}")
#                 skipped_count += 1
#
#         self.db.commit()
#         ...
#         return True, None
#     ...

# Lines 5606-5668 — _create_purchase_tracker_record_academy()
# def _create_purchase_tracker_record_academy(
#     self, order_number: str, item: AcademyOrderItem, retailer: Retailer,
#     shipping_address: str = ""
# ) -> Tuple[bool, Optional[str]]:
#     """Create a purchase tracker record for an Academy Sports order item."""
#     ...

# Lines 5926-5929 — entry in retailer_map dict inside process_single_order_confirmation_email()
# 'academy': {
#     'parser': self.academy_parser,
#     'processor': self._process_academy_order
# },
