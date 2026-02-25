"""
Outbound Creation Service for generating Inventory Lab CSV files
"""

import logging
import csv
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from collections import defaultdict
from sqlalchemy.orm import Session

from app.models.database import PurchaseTracker
from app.services.keepa_service import KeepaService

logger = logging.getLogger(__name__)


class OutboundCreationService:
    """Service for creating outbound CSV files for Inventory Lab"""
    
    def __init__(self, db: Session):
        self.db = db
        self.keepa_service = KeepaService()
    
    def get_eligible_records(self) -> List[PurchaseTracker]:
        """
        Get records where checked_in = shipped_to_pw
        
        Returns:
            List of eligible purchase records
        """
        records = self.db.query(PurchaseTracker).filter(
            PurchaseTracker.checked_in == PurchaseTracker.shipped_to_pw,
            PurchaseTracker.checked_in.isnot(None),
            PurchaseTracker.shipped_to_pw.isnot(None),
            PurchaseTracker.checked_in > 0  # Must have at least 1 item checked in
        ).all()
        
        logger.info(f"Found {len(records)} eligible records for outbound creation")
        return records
    
    def calculate_weighted_average_cost(self, records: List[PurchaseTracker]) -> float:
        """
        Calculate weighted average cost (PPU) for a set of records
        
        Args:
            records: List of purchase records with same ASIN
            
        Returns:
            Weighted average cost per unit
        """
        total_cost = 0.0
        total_qty = 0
        
        for record in records:
            if record.ppu and record.checked_in:
                total_cost += record.ppu * record.checked_in
                total_qty += record.checked_in
        
        if total_qty == 0:
            return 0.0
        
        return round(total_cost / total_qty, 2)
    
    def get_majority_supplier(self, records: List[PurchaseTracker]) -> str:
        """
        Get the supplier with the majority quantity
        
        Args:
            records: List of purchase records with same ASIN
            
        Returns:
            Supplier name with most quantity
        """
        supplier_qty = defaultdict(int)
        
        for record in records:
            if record.supplier and record.checked_in:
                supplier_qty[record.supplier] += record.checked_in
        
        if not supplier_qty:
            return "Unknown"
        
        # Return supplier with max quantity
        return max(supplier_qty.items(), key=lambda x: x[1])[0]
    
    def generate_msku(self, size: str, sku: str, outbound_date: datetime) -> str:
        """
        Generate MSKU in format: SIZE-SKU-DATEOFOUTBOUND(OB)
        Example: "7-JQ7776-10-06-25OB"
        
        Args:
            size: Product size
            sku: Product SKU
            outbound_date: Date of outbound
            
        Returns:
            Formatted MSKU string
        """
        # Format date as MM-DD-YY
        date_str = outbound_date.strftime("%m-%d-%y")
        
        # Clean size and SKU
        size_clean = str(size).strip() if size else "NA"
        sku_clean = str(sku).strip() if sku else "NA"
        
        return f"{size_clean}-{sku_clean}-{date_str}OB"
    
    def group_by_asin(self, records: List[PurchaseTracker]) -> Dict[str, List[PurchaseTracker]]:
        """
        Group records by ASIN
        
        Args:
            records: List of purchase records
            
        Returns:
            Dictionary mapping ASIN to list of records
        """
        grouped = defaultdict(list)
        
        for record in records:
            if record.asin:
                grouped[record.asin].append(record)
        
        return dict(grouped)
    
    def generate_csv(self, output_filename: str = None) -> Dict[str, Any]:
        """
        Generate Inventory Lab CSV file from eligible records
        
        Args:
            output_filename: Optional custom filename (without extension)
            
        Returns:
            Dictionary with success status, file path, and statistics
        """
        try:
            # Get eligible records
            records = self.get_eligible_records()
            
            if not records:
                return {
                    "success": False,
                    "error": "No eligible records found (checked_in = shipped_to_pw)",
                    "file_path": None,
                    "total_records": 0
                }
            
            # Group by ASIN
            grouped_records = self.group_by_asin(records)
            
            # Prepare output directory
            backend_dir = Path(__file__).parent.parent.parent
            output_dir = backend_dir / "tmp"
            output_dir.mkdir(exist_ok=True)
            
            # Generate filename
            if not output_filename:
                today = datetime.now().strftime("%m-%d-%Y")
                output_filename = f"{today} Lloyd Outbound IL"
            
            output_path = output_dir / f"{output_filename}.csv"
            
            # Generate CSV data
            csv_rows = []
            # Use first day of current month for PURCHASEDDATE
            # If December 2025, use 12/1/2025. If July 2025, use 7/1/2025
            outbound_date = datetime.now().replace(day=1)
            
            for asin, asin_records in grouped_records.items():
                # Calculate weighted average cost
                cost_unit = self.calculate_weighted_average_cost(asin_records)
                
                # Get total quantity
                total_qty = sum(r.checked_in for r in asin_records if r.checked_in)
                
                # Get majority supplier
                supplier = self.get_majority_supplier(asin_records)
                
                # Get product title (use concat or product_name)
                title = asin_records[0].product_name or ""
                
                # Get size and SKU for MSKU generation
                # Use the first record's values
                size = asin_records[0].size or ""
                sku = asin_records[0].sku_upc or asin
                
                # Generate MSKU
                msku = self.generate_msku(size, sku, outbound_date)
                
                # Fetch list price from Keepa API
                logger.info(f"Fetching price for ASIN: {asin}")
                list_price = self.keepa_service.get_product_price(asin)
                
                if list_price is None:
                    logger.warning(f"Could not fetch price for ASIN: {asin}, using 0.00")
                    list_price = 0.00
                
                # Create CSV row
                csv_row = {
                    "ASIN": asin,
                    "TITLE": title,
                    "COSTUNIT": f"{cost_unit:.2f}",
                    "LISTPRICE": f"{list_price:.2f}",
                    "QUANTITY": str(total_qty),
                    "PURCHASEDDATE": outbound_date.strftime("%m/%d/%Y"),
                    "SUPPLIER": supplier,
                    "CONDITION": "NEW",
                    "MSKU": msku,
                    "SALESTAX": "",
                    "DISCOUNT": "",
                    "EXPIRATIONDATE": "",
                    "NOTES": "",
                    "TAXCODE": "",
                    "MINPRICE": "",
                    "MAXPRICE": "",
                    "MFN SHIPPING TEMPLATE": ""
                }
                
                csv_rows.append(csv_row)
            
            # Write CSV file
            fieldnames = [
                "ASIN", "TITLE", "COSTUNIT", "LISTPRICE", "QUANTITY", 
                "PURCHASEDDATE", "SUPPLIER", "CONDITION", "MSKU",
                "SALESTAX", "DISCOUNT", "EXPIRATIONDATE", "NOTES", 
                "TAXCODE", "MINPRICE", "MAXPRICE", "MFN SHIPPING TEMPLATE"
            ]
            
            with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(csv_rows)
            
            logger.info(f"✅ Successfully generated CSV: {output_path}")
            logger.info(f"   Total ASINs: {len(csv_rows)}")
            logger.info(f"   Total records processed: {len(records)}")
            
            return {
                "success": True,
                "file_path": str(output_path),
                "total_asins": len(csv_rows),
                "total_records": len(records),
                "filename": f"{output_filename}.csv"
            }
            
        except Exception as e:
            logger.error(f"Error generating outbound CSV: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "file_path": None,
                "total_records": 0
            }
    
    def generate_prepworx_csv(self, il_csv_path: str = None, output_filename: str = None) -> Dict[str, Any]:
        """
        Generate Prepworx CSV file from IL upload CSV file
        
        Args:
            il_csv_path: Path to IL upload CSV file. If None, finds most recent IL file in tmp folder
            output_filename: Optional custom filename (without extension)
            
        Returns:
            Dictionary with success status, file path, and statistics
        """
        try:
            backend_dir = Path(__file__).parent.parent.parent
            tmp_dir = backend_dir / "tmp"
            
            # Find IL CSV file if not provided
            if not il_csv_path:
                # Find most recent IL file in tmp folder
                il_files = list(tmp_dir.glob("*Outbound IL.csv"))
                if not il_files:
                    return {
                        "success": False,
                        "error": "No IL upload CSV file found in tmp folder",
                        "file_path": None,
                        "total_items": 0
                    }
                # Sort by modification time, get most recent
                il_csv_path = str(max(il_files, key=lambda p: p.stat().st_mtime))
                logger.info(f"Using IL file: {il_csv_path}")
            
            il_path = Path(il_csv_path)
            if not il_path.exists():
                return {
                    "success": False,
                    "error": f"IL CSV file not found: {il_csv_path}",
                    "file_path": None,
                    "total_items": 0
                }
            
            # Read IL CSV file
            items = []
            with open(il_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    asin = row.get('ASIN', '').strip()
                    title = row.get('TITLE', '').strip()
                    quantity = row.get('QUANTITY', '').strip()
                    
                    if not asin:
                        continue
                    
                    # Parse quantity
                    try:
                        qty = int(quantity) if quantity else 0
                    except ValueError:
                        qty = 0
                    
                    if qty <= 0:
                        continue
                    
                    items.append({
                        "name": title,
                        "asin": asin,
                        "quantity": qty
                    })
            
            if not items:
                return {
                    "success": False,
                    "error": "No valid items found in IL CSV file",
                    "file_path": None,
                    "total_items": 0
                }
            
            # Generate output filename
            if not output_filename:
                today = datetime.now().strftime("%m-%d-%Y")
                output_filename = f"{today} Outbound PW"
            
            output_path = tmp_dir / f"{output_filename}.csv"
            
            # Generate Prepworx CSV
            # Format: Reference Name, Workflow Name, Shipment Notes (header row)
            # Then: Name, ASIN, UPC, Multipack / Bundle, Number of Units, Notes (item rows)
            
            reference_name = f"{datetime.now().strftime('%m-%d-%Y')} Outbound"
            workflow_name = "AMZ"
            
            with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                # Write header section
                header_writer = csv.writer(csvfile)
                header_writer.writerow(["Reference Name", "Workflow Name", "Shipment Notes"])
                header_writer.writerow([reference_name, workflow_name, ""])
                
                # Write blank row (separator)
                header_writer.writerow([])
                
                # Write item header
                header_writer.writerow(["Name", "ASIN", "UPC", "Multipack / Bundle", "Number of Units", "Notes"])
                
                # Write items
                item_writer = csv.writer(csvfile)
                for item in items:
                    item_writer.writerow([
                        item["name"],      # Name (product name from IL)
                        item["asin"],      # ASIN
                        "",                # UPC (blank)
                        "None",            # Multipack/bundle
                        str(item["quantity"]),  # Number of Units
                        ""                 # Notes (blank)
                    ])
            
            logger.info(f"✅ Successfully generated Prepworx CSV: {output_path}")
            logger.info(f"   Total items: {len(items)}")
            
            return {
                "success": True,
                "file_path": str(output_path),
                "total_items": len(items),
                "filename": f"{output_filename}.csv",
                "reference_name": reference_name
            }
            
        except Exception as e:
            logger.error(f"Error generating Prepworx CSV: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "file_path": None,
                "total_items": 0
            }

