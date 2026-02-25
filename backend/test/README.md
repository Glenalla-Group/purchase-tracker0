# Order Confirmation Email Parser Tests

This directory contains test scripts for all retailer order confirmation email parsers.

## Available Test Scripts

- `test_footlocker.py` - Test Footlocker order confirmation emails
- `test_champs.py` - Test Champs Sports order confirmation emails
- `test_dicks.py` - Test Dick's Sporting Goods order confirmation emails
- `test_hibbett.py` - Test Hibbett Sports order confirmation emails
- `test_shoepalace.py` - Test Shoe Palace order confirmation emails
- `test_snipes.py` - Test Snipes order confirmation emails
- `test_finishline.py` - Test Finish Line order confirmation emails
- `test_shopsimon.py` - Test Shop Simon order confirmation emails
- `test_urban.py` - Test Urban Outfitters order confirmation emails
- `test_bloomingdales.py` - Test Bloomingdale's order confirmation emails
- `test_gazelle.py` - Test Gazelle Sports order confirmation emails
- `test_netaporter.py` - Test NET-A-PORTER order confirmation emails
- `test_carbon38.py` - Test Carbon38 order confirmation emails

## Usage

Each test script can be run in multiple ways:

### 1. Search Gmail for the first email (default)
```bash
# Run as a module (from backend directory)
python -m test.test_footlocker
python -m test.test_champs
python -m test.test_dicks
python -m test.test_hibbett
python -m test.test_shoepalace
python -m test.test_snipes
python -m test.test_finishline
python -m test.test_shopsimon
python -m test.test_urban
python -m test.test_bloomingdales
python -m test.test_carbon38
python -m test.test_gazelle
python -m test.test_netaporter

# Or run directly (from backend directory)
python test/test_footlocker.py
python test/test_champs.py
python test/test_dicks.py
python test/test_hibbett.py
python test/test_shoepalace.py
python test/test_snipes.py
python test/test_finishline.py
python test/test_shopsimon.py
python test/test_urban.py
python test/test_bloomingdales.py
python test/test_carbon38.py
python test/test_gazelle.py
python test/test_netaporter.py
```

### 2. Use a specific email file
```bash
# Run a test with a specific email file
python -m test.test_footlocker footlocker1.txt
python test/test_footlocker.py footlocker1.txt
python -m test.test_champs champs.txt
python -m test.test_dicks dicks.txt
python -m test.test_hibbett hibbett.txt
python -m test.test_shoepalace shoepalace.txt
python -m test.test_snipes snipes.txt
python -m test.test_finishline finishline.txt
python -m test.test_shopsimon shopsimon.txt
python -m test.test_urban urban.txt
python -m test.test_bloomingdales bloomingdale.txt
python -m test.test_carbon38 carbon38.txt
python -m test.test_gazelle gazelle.txt
python -m test.test_netaporter netaporter.txt
```

### 3. Run all tests at once
```bash
python -m test.run_all_tests
```

## Test Email Files

Test email files are located in `../feed/order-confirmation-emails/`:
- `footlocker.txt`, `footlocker1.txt`
- `champs.txt`
- `dicks.txt`
- `hibbett.txt`
- `shoepalace.txt`
- `snipes.txt`
- `finishline.txt`
- `shopsimon.txt`
- `urban.txt`
- `bloomingdale.txt`
- `carbon38.txt`
- `gazelle.txt`
- `netaporter.txt`

## Output

Each test script will:
1. Load the email HTML file
2. Parse it using the appropriate parser
3. Display the extracted order information:
   - Order number
   - Number of items
   - For each item:
     - Product name
     - Unique ID
     - Size
     - Quantity
   - Shipping address (if available)

## Example Output

```
Reading Footlocker email from: /path/to/feed/order-confirmation-emails/footlocker1.txt
================================================================================

Parsing Footlocker order confirmation email...

✅ Successfully parsed order email!
================================================================================

Order Number: P7404599286928818176
Number of items: 4

Items:
--------------------------------------------------------------------------------

Item 1:
  Product Name: Nike LeBron XXII - Men's
  Unique ID: V8451400
  Size: 12.0
  Quantity: 1

Item 2:
  Product Name: Nike Killshot 2 Leather - Men's
  Unique ID: 32997121
  Size: 08.0
  Quantity: 6

...
```
