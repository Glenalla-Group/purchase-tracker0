# Urban Outfitters sections extracted from backend/app/services/retailer_order_processor.py
# Archived: 2026-04-15

# --- Import (line 30) ---
from app.services.urban_parser import UrbanOutfittersEmailParser, UrbanOrderData, UrbanOrderItem

# --- Instantiation in __init__ (line 85) ---
# self.urban_parser = UrbanOutfittersEmailParser()

# --- Retailer map entry in process_single_order_confirmation_email() (lines 5866-5869) ---
# 'urbanoutfitters': {
#     'parser': self.urban_parser,
#     'processor': self._process_urban_order
# },

# --- _process_urban_order method (lines 3496-3549) ---
def _process_urban_order(self, order_data: UrbanOrderData) -> Tuple[bool, Optional[str]]:
    """
    Process an Urban Outfitters order and create purchase tracker records.

    Args:
        order_data: Parsed order data

    Returns:
        Tuple of (success, error_message)
    """
    try:
        # Get Urban Outfitters retailer
        urban_retailer = self.db.query(Retailer).filter(
            Retailer.name.ilike('%Urban Outfitters%')
        ).first()

        if not urban_retailer:
            return False, "Urban Outfitters retailer not found in database"

        created_count = 0
        skipped_count = 0

        for item in order_data.items:
            success, error = self._create_purchase_tracker_record_urban(
                order_number=order_data.order_number,
                item=item,
                retailer=urban_retailer,
                shipping_address=order_data.shipping_address
            )

            if success:
                created_count += 1
            else:
                logger.warning(f"Could not create record for item {item.unique_id}: {error}")
                skipped_count += 1

        # Commit all changes
        self.db.commit()

        if created_count == 0:
            return False, f"No purchase tracker records created (skipped: {skipped_count})"

        logger.info(f"Created {created_count} purchase tracker records for order {order_data.order_number}")

        if skipped_count > 0:
            logger.warning(f"Skipped {skipped_count} items (no matching OA sourcing lead)")

        return True, None

    except Exception as e:
        self.db.rollback()
        error_msg = f"Error processing order {order_data.order_number}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return False, error_msg

# --- _create_purchase_tracker_record_urban method (lines 3551-3643) ---
def _create_purchase_tracker_record_urban(
    self,
    order_number: str,
    item: UrbanOrderItem,
    retailer: Retailer,
    shipping_address: str = ""
) -> Tuple[bool, Optional[str]]:
    """
    Create a purchase tracker record for an Urban Outfitters order item.

    Args:
        order_number: Order number
        item: Urban Outfitters order item
        retailer: Urban Outfitters retailer record

    Returns:
        Tuple of (success, error_message)
    """
    try:
        # Look up OA sourcing by unique_id only
        oa_sourcing = self.db.query(OASourcing).filter(
            OASourcing.unique_id == item.unique_id
        ).first()

        if not oa_sourcing:
            return False, f"No OA sourcing lead found for unique_id: {item.unique_id}"

        # Look up ASIN from asin_bank by lead_id and size (with size normalization + OASourcing fallback)
        asin_record = self._get_asin_for_lead_and_size(oa_sourcing.lead_id, item.size, oa_sourcing=oa_sourcing)

        if not asin_record:
            asin_count = self.db.query(AsinBank).filter(AsinBank.lead_id == oa_sourcing.lead_id).count()
            logger.warning(
                f"No ASIN found for lead_id={oa_sourcing.lead_id}, size={item.size}. "
                f"Creating record without ASIN. (AsinBank has {asin_count} records for this lead. "
                f"Add via: POST /leads/{{lead_id}}/asins or POST /asin-bank)"
            )

        # Calculate FBA MSKU: {size}-{sku_upc}-{order_number}
        sku_upc = oa_sourcing.product_sku or "UNKNOWN"
        fba_msku = f"{item.size}-{sku_upc}-{order_number}"

        # Create purchase tracker record
        purchase_record = PurchaseTracker(
            # Foreign keys
            oa_sourcing_id=oa_sourcing.id,
            asin_bank_id=asin_record.id if asin_record else None,

            # Denormalized for performance
            lead_id=oa_sourcing.lead_id,

            # Purchase metadata
            date=datetime.utcnow(),
            platform="AMZ",  # Selling platform (Amazon)
            order_number=order_number,
            address=shipping_address,

            # Quantities
            og_qty=item.quantity,
            final_qty=item.quantity,

            # Pricing - use from oa_sourcing
            rsp=oa_sourcing.rsp,

            # FBA fields
            fba_msku=fba_msku,

            # Status and Location - set to Pending/Retailer for new purchases
            status="Pending",
            location="Retailer",

            # Audit
            audited=False
        )

        self.db.add(purchase_record)

        logger.info(
            f"Created Urban Outfitters purchase tracker record: "
            f"lead_id={oa_sourcing.lead_id}, "
            f"product={oa_sourcing.product_name}, "
            f"size={item.size}, "
            f"qty={item.quantity}, "
            f"asin={asin_record.asin if asin_record else 'N/A'}, "
            f"msku={fba_msku}"
        )

        return True, None

    except Exception as e:
        error_msg = f"Error creating purchase tracker record: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return False, error_msg
