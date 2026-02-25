# Automatic Inbound Creation Feature

## Overview

This feature automates the inbound creation process in PrepWorx by:

1. Extracting purchase records where `final_qty = shipped_to_pw` (items fully shipped to warehouse)
2. Checking the shipping address (595 Lloyd Lane or 2025 Vista Ave)
3. Automatically logging into PrepWorx with appropriate credentials
4. Processing inbound creation (placeholder for now, to be extended)

## Architecture

### Backend Components

1. **PrepWorx Automation Service** (`app/services/prepworx_automation.py`)
   - `PrepWorxCredentials`: Maps addresses to PrepWorx account credentials
   - `PrepWorxAutomation`: Handles browser automation using Playwright
   - `process_inbound_creation()`: Main function to process records

2. **API Endpoint** (`app/api/purchase_tracker_api.py`)
   - `POST /api/v1/purchase-tracker/process-inbound-creation`
   - Queries database for eligible records
   - Filters by supported addresses
   - Calls automation service

### Frontend Components

1. **Service Method** (`frontend/src/api/services/purchaseTrackerService.ts`)
   - `processInboundCreation()`: Calls backend API

2. **UI Button** (`frontend/src/pages/dashboard/purchase-tracker/index.tsx`)
   - Purple "Process Inbound Creation" button
   - Handler with toast notifications

## Installation

### 1. Install Playwright

From the backend directory:

```bash
cd /home/kdh/dev/purchase-tracker/backend

# Make sure virtual environment is activated
source venv/bin/activate

# Run setup script
./setup_playwright.sh
```

Or manually:

```bash
# Install Python package
pip install playwright==1.40.0

# Install browsers
playwright install

# Install browser dependencies (Linux only)
playwright install-deps
```

### 2. Update Dependencies

The `requirements.txt` has already been updated with:

```
# Browser automation
playwright==1.40.0
```

### 3. Restart Backend

After installing Playwright, restart your backend server:

```bash
cd /home/kdh/dev/purchase-tracker/backend
source venv/bin/activate
python run.py
```

## Usage

### From Frontend

1. Navigate to Purchase Tracker page
2. Click the purple **"Process Inbound Creation"** button
3. The system will:
   - Query eligible purchase records
   - Group by address
   - Login to PrepWorx automatically
   - Process inbound creation
   - Display results

### From API

```bash
curl -X POST http://localhost:8000/api/v1/purchase-tracker/process-inbound-creation
```

## Configuration

### Supported Addresses and Credentials

The system supports two addresses with different PrepWorx accounts:

#### 595 Lloyd Lane
- **Email**: `glenallagroupc@gmail.com`
- **Password**: `GroupGlenalla25!!@`

#### 2025 Vista Ave
- **Email**: `griffin@glenallagroup.com`
- **Password**: `GlenallaGroup26!@!`

### Modifying Credentials

Edit `app/services/prepworx_automation.py`:

```python
class PrepWorxCredentials:
    LLOYD_LANE = {
        "email": "your-email@example.com",
        "password": "your-password",
        "address": "595 Lloyd Lane"
    }
    
    VISTA_AVE = {
        "email": "your-email@example.com",
        "password": "your-password",
        "address": "2025 Vista Ave"
    }
```

## Selection Criteria

The automation processes purchase records that meet ALL of these conditions:

1. `final_qty` is not NULL
2. `shipped_to_pw` is not NULL
3. `final_qty = shipped_to_pw` (items fully shipped)
4. `address` is not NULL
5. Address contains either "595 Lloyd Lane" or "2025 Vista Ave"

## Current Implementation Status

### ✅ Completed

- [x] Backend automation service with Playwright
- [x] Login automation to PrepWorx
- [x] Database query for eligible records
- [x] Address-based credential selection
- [x] API endpoint for processing
- [x] Frontend button and handler
- [x] Error handling and logging
- [x] Toast notifications

### 🚧 To Be Implemented (Phase 2)

The current implementation includes a **placeholder** for the actual inbound creation logic in PrepWorx. The next phase will involve:

1. **Navigate to Inbound Creation Page**
   - After successful login, navigate to the inbound creation section
   - Wait for page load

2. **Fill Inbound Form**
   - Product name
   - SKU/ASIN
   - Quantity
   - Other required fields

3. **Submit and Verify**
   - Submit the form
   - Wait for confirmation
   - Capture inbound ID/reference

4. **Update Database**
   - Mark records as processed
   - Store inbound reference

## Development Notes

### Running in Non-Headless Mode

For debugging, you can modify the automation to show the browser:

In `prepworx_automation.py`, change:

```python
result = run_automation(purchase_records, headless=False)  # Show browser
```

### Logging

All automation actions are logged. Check the backend logs:

```bash
tail -f /home/kdh/dev/purchase-tracker/backend/app.log
```

### Testing

Test with a small dataset first:

1. Ensure you have test records matching the criteria
2. Run the process
3. Verify PrepWorx login works
4. Check logs for any issues

## Troubleshooting

### Playwright Not Found

```bash
pip install playwright==1.40.0
playwright install
```

### Browser Dependencies Missing (Linux)

```bash
playwright install-deps
```

### Login Fails

- Verify credentials in `PrepWorxCredentials`
- Check PrepWorx website hasn't changed its login form
- Run in non-headless mode to see what's happening
- Check for CAPTCHA or 2FA requirements

### No Records Found

- Verify records exist with `final_qty = shipped_to_pw`
- Check address format in database matches expected format
- Query database directly to confirm:

```sql
SELECT id, order_number, address, final_qty, shipped_to_pw
FROM purchase_tracker
WHERE final_qty IS NOT NULL 
  AND shipped_to_pw IS NOT NULL
  AND final_qty = shipped_to_pw
  AND address IS NOT NULL;
```

## Security Considerations

⚠️ **Important**: Credentials are currently hardcoded in the source code. For production:

1. Move credentials to environment variables
2. Use secrets management (AWS Secrets Manager, HashiCorp Vault, etc.)
3. Encrypt sensitive data
4. Implement credential rotation

Example using environment variables:

```python
import os

class PrepWorxCredentials:
    LLOYD_LANE = {
        "email": os.getenv("PREPWORX_LLOYD_EMAIL"),
        "password": os.getenv("PREPWORX_LLOYD_PASSWORD"),
        "address": "595 Lloyd Lane"
    }
```

## Next Steps

1. **Test the Current Implementation**
   - Install Playwright
   - Test login automation
   - Verify records are queried correctly

2. **Implement Inbound Creation Logic**
   - Inspect PrepWorx UI for inbound creation
   - Identify form fields and selectors
   - Implement form filling logic
   - Add submission and verification

3. **Add Database Updates**
   - Mark processed records
   - Store inbound references
   - Update timestamps

4. **Enhance Error Handling**
   - Retry logic for failed logins
   - Partial success handling
   - Detailed error messages

5. **Add Monitoring**
   - Track success/failure rates
   - Alert on repeated failures
   - Dashboard for automation status

## Contact

For questions or issues with this feature, contact the development team.






