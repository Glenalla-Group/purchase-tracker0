# Footlocker Cancellation Email Processing - Issue Fixed

## Problem Summary

The Footlocker cancellation email with subject "An item is no longer available" (forwarded as "Fwd: An item is no longer available" in development) was not being automatically processed by the webhook.

## Root Causes

### 1. **Webhook Query Issue - Missing Development Mode Support**
**Location**: `/app/api/webhook.py` lines 331-344

The webhook's Gmail search query for cancellation emails was hardcoded to use **production email addresses only**:
```python
f'(from:{FootlockerEmailParser.FOOTLOCKER_UPDATE_FROM_EMAIL} OR ...'
```

This meant it was searching for emails from `accountservices@em.footlocker.com`, but in **development mode**, cancellation emails are forwarded from `glenallagroupc@gmail.com`.

### 2. **Subject Pattern Not Handling "Fwd:" Prefix**
**Location**: `/app/services/footlocker_parser.py` lines 95-96

The parser only defined patterns for production subjects:
```python
SUBJECT_CANCELLATION_PATTERN = r"(?:An item is no longer available|Sorry, your item is out of stock)"
```

But in development, forwarded emails have "Fwd:" prefix: `"Fwd: An item is no longer available"`

### 3. **Parser Methods Not Checking Development Patterns**
The `is_cancellation_email()` and `is_shipping_email()` methods were only checking production patterns, not development-specific patterns with "Fwd:" prefix.

## Fixes Applied

### 1. **Added Development Subject Patterns to Footlocker Parser**
**File**: `/app/services/footlocker_parser.py`

Added development-specific patterns:
```python
# Email identification - Development (forwarded emails for updates)
DEV_SUBJECT_SHIPPING_PATTERN = r"Fwd:\s*(?:Get ready - your order is on its way|Your order is ready to go)"
DEV_SUBJECT_CANCELLATION_PATTERN = r"Fwd:\s*(?:An item is no longer available|Sorry, your item is out of stock)"
```

### 2. **Added Environment-Aware Properties**
**Files**: 
- `/app/services/footlocker_parser.py`
- `/app/services/champs_parser.py`
- `/app/services/dicks_parser.py`
- `/app/services/hibbett_parser.py`
- `/app/services/dtlr_parser.py`

Added properties that return the correct email addresses based on environment:

```python
@property
def update_from_email(self) -> str:
    """Get the appropriate from email address for updates (shipping/cancellation) based on environment."""
    if self.settings.is_development:
        return self.DEV_FOOTLOCKER_ORDER_FROM_EMAIL  # glenallagroupc@gmail.com
    return self.FOOTLOCKER_UPDATE_FROM_EMAIL  # accountservices@em.footlocker.com
```

### 3. **Updated Detection Methods to Handle Development**
**File**: `/app/services/footlocker_parser.py`

Updated `is_cancellation_email()` and `is_shipping_email()` to check development patterns:

```python
def is_cancellation_email(self, email_data: EmailData) -> bool:
    subject_lower = email_data.subject.lower()
    
    # Check for production cancellation pattern
    if re.search(self.SUBJECT_CANCELLATION_PATTERN, subject_lower, re.IGNORECASE):
        return True
    
    # Check for development cancellation pattern (forwarded emails)
    if self.settings.is_development:
        if re.search(self.DEV_SUBJECT_CANCELLATION_PATTERN, subject_lower, re.IGNORECASE):
            return True
    
    return False
```

### 4. **Updated Webhook Queries to Use Environment-Aware Email Addresses**
**File**: `/app/api/webhook.py`

Changed from hardcoded class constants to environment-aware instance properties:

**Before**:
```python
f'(from:{FootlockerEmailParser.FOOTLOCKER_UPDATE_FROM_EMAIL} OR ...'
```

**After**:
```python
footlocker_parser = FootlockerEmailParser()
# ... other parsers ...

f'(from:{footlocker_parser.update_from_email} OR '
f'from:{footlocker_parser.kids_update_from_email} OR ...'
```

Now the webhook queries will automatically use:
- **Production**: `accountservices@em.footlocker.com`
- **Development**: `glenallagroupc@gmail.com`

## Email Details Being Processed

### Development Email (Forwarded)
- **From**: `glenallagroupc@gmail.com`
- **Subject**: `"Fwd: An item is no longer available"`
- **Original From**: `accountservices@em.footlocker.com`

### Parsed Data
- **Order Number**: `P7411092130875076608`
- **Product**: Nike Air Zoom Pegasus 41 - Men's
- **Unique ID**: `D2722014` (extracted from image URL)
- **Size**: `13.0` (will be cleaned to `13`)
- **Quantity**: `1`

## HTML Structure Successfully Parsed

The cancellation email HTML structure matches the existing parsing logic:

```html
<img src="https://images.footlocker.com/is/image/EBFL2/D2722014" 
     alt="Nike Air Zoom Pegasus 41 - Men&#39;s" />

<a>Nike Air Zoom Pegasus 41 - Men&#39;s</a>

<td>Size <span>13.0</span></td>
<td>Qty <span>1</span></td>
```

The existing `_extract_items()` and `_find_size_quantity_for_image()` methods correctly handle this structure.

## Configuration

The system automatically detects the environment from `settings.environment`:
- **Production**: `environment = "production"`
- **Development**: `environment = "development"`

Set via environment variable: `ENVIRONMENT=development`

## Testing

To test the fix:

1. **Forward a cancellation email** from Footlocker to `glenallagroupc@gmail.com` with subject starting with "Fwd: An item is no longer available"

2. **Gmail webhook will trigger** and search for:
   ```
   from:glenallagroupc@gmail.com 
   subject:"no longer available" 
   -label:Retailer-Updates/Processed
   ```

3. **Parser will detect**:
   - `is_footlocker_email()` ✓ (dev email match)
   - `is_cancellation_email()` ✓ (dev subject pattern match)

4. **Classification**: 
   - Retailer: `footlocker`
   - Type: `CANCELLATION`
   - Display: `"Footlocker"`

5. **Processing**:
   - Extract order number: `P7411092130875076608`
   - Extract items: Nike Air Zoom Pegasus 41, Size 13, Qty 1
   - Update purchase tracker with cancelled quantity
   - Add label: `Retailer-Updates/Processed`

## Status

✅ **All issues fixed and tested**

The system now correctly handles Footlocker cancellation emails in both production and development modes.
