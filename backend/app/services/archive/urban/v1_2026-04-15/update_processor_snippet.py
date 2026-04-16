# Urban Outfitters sections extracted from backend/app/services/retailer_order_update_processor.py
# Archived: 2026-04-15

# --- Import (lines 44-48) ---
from app.services.urban_parser import (
    UrbanOutfittersEmailParser,
    UrbanOutfittersCancellationData,
    UrbanOrderItem as UrbanOutfittersOrderItem
)

# --- Instantiation in __init__ (line 138) ---
# self.urban_parser = UrbanOutfittersEmailParser()

# --- Cancellation dispatch in process_single_cancellation_email() (lines 1510-1527) ---
# elif retailer_name == 'urban' or retailer_name == 'urbanoutfitters':
#     cancellation_data = self.urban_parser.parse_cancellation_email(email_data)
#     if not cancellation_data:
#         self._add_error_label(message_id, 'cancellation')
#         return {'success': False, 'error': 'Failed to parse cancellation data'}
#
#     success, error_msg = self._process_urban_cancellation_update(cancellation_data)
#
#     if success:
#         self._add_processed_label(message_id, 'cancellation')
#         return {
#             'success': True,
#             'order_number': cancellation_data.order_number,
#             'items_count': len(cancellation_data.items)
#         }
#     else:
#         self._add_error_label(message_id, 'cancellation')
#         return {'success': False, 'error': error_msg}

# NOTE: NO shipping dispatch exists for Urban Outfitters — that's the gap being fixed

# --- _process_urban_cancellation_update method (lines 2831-2923) ---
def _process_urban_cancellation_update(self, cancellation_data: UrbanOutfittersCancellationData) -> Tuple[bool, Optional[str]]:
    """
    Process Urban Outfitters cancellation update: Deduct quantity from 'final_qty' and update 'cancelled_qty'.

    For each item in the cancellation notification:
    1. Find matching purchase tracker record by order number and size (with size normalization)
    2. Deduct the quantity from 'final_qty'
    3. Add the quantity to 'cancelled_qty' (cumulative)

    Args:
        cancellation_data: UrbanOutfittersCancellationData object

    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    try:
        logger.info(f"Processing Urban Outfitters cancellation update for order {cancellation_data.order_number}")

        items_updated = 0

        for item in cancellation_data.items:
            # Normalize the size from cancellation email for comparison
            normalized_cancel_size = self._normalize_size(item.size)

            # Find matching purchase tracker record(s)
            # Match by order_number and size (handle both normalized and non-normalized sizes)
            matching_records = self.db.query(PurchaseTracker).join(
                AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
            ).filter(
                and_(
                    PurchaseTracker.order_number == cancellation_data.order_number,
                    or_(
                        AsinBank.size == item.size,  # Exact match
                        AsinBank.size == normalized_cancel_size  # Normalized match
                    )
                )
            ).all()

            # If no exact matches, try to match by normalizing all sizes manually
            if not matching_records:
                all_order_records = self.db.query(PurchaseTracker).join(
                    AsinBank, PurchaseTracker.asin_bank_id == AsinBank.id
                ).filter(
                    PurchaseTracker.order_number == cancellation_data.order_number
                ).all()

                for record in all_order_records:
                    db_size = record.asin_bank_ref.size if record.asin_bank_ref else None
                    if db_size:
                        normalized_db_size = self._normalize_size(db_size)
                        if normalized_db_size == normalized_cancel_size:
                            matching_records.append(record)

            if not matching_records:
                logger.warning(
                    f"No purchase tracker record found for order {cancellation_data.order_number}, "
                    f"size {item.size} (normalized: {normalized_cancel_size}), unique_id {item.unique_id}"
                )
                continue

            # Update each matching record
            for record in matching_records:
                # Deduct from final_qty
                current_final_qty = record.final_qty or 0
                record.final_qty = max(0, current_final_qty - item.quantity)

                # Add to cancelled_qty (cumulative)
                current_cancelled = record.cancelled_qty or 0
                record.cancelled_qty = current_cancelled + item.quantity

                # Recalculate status and location
                self._recalculate_status_and_location(record)

                logger.info(
                    f"Updated purchase tracker ID {record.id}: "
                    f"order={cancellation_data.order_number}, "
                    f"size={item.size} (matched DB size: {record.asin_bank_ref.size if record.asin_bank_ref else 'N/A'}), "
                    f"final_qty {current_final_qty} -> {record.final_qty}, "
                    f"cancelled_qty {current_cancelled} -> {record.cancelled_qty}"
                )
                items_updated += 1

        # Commit changes
        self.db.commit()

        logger.info(f"Successfully updated {items_updated} purchase tracker records for cancellation")
        return (True, None)

    except Exception as e:
        self.db.rollback()
        error_msg = f"Error processing Urban Outfitters cancellation update: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return (False, error_msg)
