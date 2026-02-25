# Outbound Creation Feature

## Overview
This feature generates Inventory Lab CSV files for Lloyd Lane outbound shipments by filtering purchase tracker records and enriching them with pricing data from the Keepa API.

## How It Works

### 1. Trigger
- User clicks "Process Outbound Creation for Lloyd Lane" button in the Purchase Tracker frontend
- Frontend calls `/api/v1/purchase-tracker/process-outbound-creation` endpoint

### 2. Data Filtering
- Backend filters records where `checked_in = shipped_to_pw`
- Only includes records with at least 1 item checked in
- Groups records by ASIN for aggregation

### 3. CSV Generation

The system generates a CSV file with the following columns:

#### Populated Columns:
- **ASIN**: Product ASIN from database
- **TITLE**: Product name from `concat` or `name` field
- **COSTUNIT**: Weighted average cost per unit
  - Formula: `(PPU₁ × Qty₁ + PPU₂ × Qty₂ + ...) / Total Qty`
  - Example: 7 pairs @ $50 + 3 pairs @ $100 = $65 average
- **LISTPRICE**: Amazon Buy Box price × 1.15 (from Keepa API)
- **QUANTITY**: Total checked-in quantity for the ASIN
- **PURCHASEDDATE**: Current date (date of outbound)
- **SUPPLIER**: Retailer with majority quantity
  - If 100 pairs from Hibbett and 1 from Finishline → "Hibbett"
- **CONDITION**: Always "NEW"
- **MSKU**: Custom format: `SIZE-SKU-MM-DD-YYOB`
  - Example: "7-JQ7776-10-06-25OB" (Size 7, SKU JQ7776, shipped 10/06/2025)

#### Blank Columns (as requested):
- SALESTAX
- DISCOUNT
- EXPIRATIONDATE
- NOTES
- TAXCODE
- MINPRICE
- MAXPRICE
- MFN SHIPPING TEMPLATE

### 4. File Output
- Saved to: `backend/tmp/MM-DD-YYYY Lloyd Outbound IL.csv`
- Example: `12-12-2025 Lloyd Outbound IL.csv`

## Technical Implementation

### Backend Components

#### 1. Keepa Service (`app/services/keepa_service.py`)
- Fetches current Amazon Buy Box prices from Keepa API
- Applies 15% markup automatically
- Handles multiple price sources (NEW, Amazon, Buy Box)
- Converts Keepa's cent-based prices to dollars

#### 2. Outbound Creation Service (`app/services/outbound_creation_service.py`)
- Filters eligible records from database
- Groups records by ASIN
- Calculates weighted average costs
- Determines majority supplier
- Generates MSKU format
- Creates CSV file with proper formatting

#### 3. API Endpoint (`app/api/purchase_tracker_api.py`)
- Route: `POST /api/v1/purchase-tracker/process-outbound-creation`
- Returns: File path, statistics (total ASINs, total records)

### Frontend Components

#### 1. Service Method (`frontend/src/api/services/purchaseTrackerService.ts`)
- `processOutboundCreation()`: Calls backend endpoint
- 5-minute timeout for API calls

#### 2. UI Handler (`frontend/src/pages/dashboard/purchase-tracker/index.tsx`)
- `handleProcessOutboundCreation()`: Handles button click
- Shows toast notifications with progress and results
- Displays statistics (ASINs, records processed)

### Configuration

#### Environment Variables
Add to `.env` or `.env.development`:
```env
KEEPA_API_KEY=43n6aphgivclutfndctif5am60ik50ps9gbaj91hhtfh80j24kv345dib6k5561h
```

#### Dependencies
Added to `requirements.txt`:
```
requests==2.31.0
```

## Usage

1. Navigate to Purchase Tracker page
2. Click "Process Outbound Creation for Lloyd Lane" button
3. Wait for processing (may take a few minutes due to Keepa API calls)
4. Success toast will show:
   - Filename
   - Number of ASINs processed
   - Number of records processed
5. CSV file is saved to `backend/tmp/` directory

## Example Output

```csv
ASIN,TITLE,COSTUNIT,LISTPRICE,QUANTITY,PURCHASEDDATE,SUPPLIER,CONDITION,MSKU,SALESTAX,DISCOUNT,EXPIRATIONDATE,NOTES,TAXCODE,MINPRICE,MAXPRICE,MFN SHIPPING TEMPLATE
B0DYLJGHPM,Nike Air Jordan 1 High,98.85,149.99,14,12/12/2025,Hibbett,NEW,10.5-B0DYLJGHPM-12-12-25OB,,,,,,,,
```

## Weighted Average Cost Example

Given these records for ASIN B0DYLJGHPM:
| Order Number | PPU    | Checked In Qty |
|--------------|--------|----------------|
| 1234567      | $97.71 | 5              |
| 2764287374   | $104.99| 6              |
| ABC12642     | $75.44 | 1              |
| 2764287313   | $104.99| 1              |
| ORD12451     | $85.00 | 1              |

Calculation:
- Total Cost: (97.71×5) + (104.99×6) + (75.44×1) + (104.99×1) + (85×1) = $1,383.92
- Total Qty: 5 + 6 + 1 + 1 + 1 = 14
- **COSTUNIT: $1,383.92 ÷ 14 = $98.85**

## Error Handling

- If no eligible records found: Returns error message
- If Keepa API fails: Uses $0.00 as LISTPRICE and logs warning
- If database error: Returns 500 status with error details
- Frontend shows appropriate toast notifications for all scenarios

## Notes

- This feature does NOT perform automatic login or browser automation
- It only generates CSV files from existing database records
- Keepa API calls may take time depending on number of unique ASINs
- The `outbound_name` field in the database is preserved but not used in this process

