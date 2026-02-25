# Order Confirmation Unique ID Patterns

This document shows how each retailer parser generates `unique_id` for order items.

## Overview

The `unique_id` field is used to match order confirmation items with products in the OA Sourcing database. Each retailer has a different way of identifying products.

---

## 1. **Footlocker**

### Source
Extracted from product image URL

### Pattern
```
/EBFL2/{UNIQUE_ID}
```

### Examples
- `64033WWH` - from image URL: `.../EBFL2/64033WWH`
- `6197725` - from image URL: `.../EBFL2/6197725`

### Code Location
`app/services/footlocker_parser.py` - Line 369
```python
unique_id_match = re.search(r'/EBFL2/([A-Z0-9]+)', img_src)
unique_id = unique_id_match.group(1)
```

---

## 2. **Champs Sports**

### Source
Extracted from product image URL (same CDN as Footlocker)

### Pattern
```
/EBFL2/{UNIQUE_ID}
```

### Examples
- `4181D090` - from image URL: `.../EBFL2/4181D090`
- `5621W140` - from image URL: `.../EBFL2/5621W140`
- `6197725` - from image URL: `.../EBFL2/6197725`

### Code Location
`app/services/champs_parser.py` - Lines 283, 297-303
```python
# Find all product images with unique IDs
product_images = soup.find_all('img', src=re.compile(r'/EBFL2/([A-Z0-9]+)'))

# Extract unique ID from image URL
unique_id_match = re.search(r'/EBFL2/([A-Z0-9]+)', img_src)
unique_id = unique_id_match.group(1)
```

### Note
Champs and Footlocker share the same image CDN infrastructure, so they use the same unique_id pattern.

---

## 3. **Dick's Sporting Goods**

### Source
Extracted from product image URL

### Pattern
```
{NUMERIC_ID} or {ALPHANUMERIC_CODE}
```

### Examples
- `23413456` - from image URL
- `DK8765432` - from image URL

### Code Location
`app/services/dicks_parser.py` - Line 537
```python
def _extract_unique_id_from_dicks_image(self, img_src: str) -> Optional[str]:
    # Multiple patterns for Dick's images
    # Pattern varies based on image CDN URL structure
```

---

## 4. **Hibbett Sports**

### Source
1. Extracted from product image URL (order confirmations)
2. Generated from product name (shipping/cancellation notifications)

### Pattern (Image URL)
```
{NUMERIC_CODE} or {STYLE_CODE}
```

### Pattern (Generated)
```
{FIRST_3_WORDS_UPPERCASE_NO_SPACES}
```

### Examples
- `12345678` - from image URL
- `HB87654` - from image URL
- `MENSNIKEAIRJORDAN` - generated from "Men's Nike Air Jordan 1 Mid"
- `WOMENSADIDASULTRABOOST` - generated from "Women's adidas Ultraboost"

### Code Location
`app/services/hibbett_parser.py` - Lines 311, 992
```python
def _extract_unique_id_from_hibbett_image(self, img_src: str) -> Optional[str]:
    # Extract from image URL
    
def _generate_unique_id_from_product_name(self, product_name: str) -> str:
    words = product_name.split()[:3]
    return ''.join(word.upper() for word in words if word)
```

---

## 5. **Shoe Palace**

### Source
Generated from product name (removing color and "Final Sale")

### Pattern
```
SP-{Product Name Without Color}
```

### Examples
- Product: "Air Jordan Collectors Duffle Bag Mens Bag (Black) - OS"
  - → `SP-Air Jordan Collectors Duffle Bag Mens Bag`
- Product: "Clifton 9 Mens Running Shoes (Black) Final Sale - 10"
  - → `SP-Clifton 9 Mens Running Shoes`

### Code Location
`app/services/shoepalace_parser.py` - Lines 367-369
```python
# Create unique_id: SP-{product_name_without_color}
unique_id = f"SP-{product_name_no_color}"
```

### Processing
1. Extract product name from email
2. Remove color in parentheses: `(Black)` → removed
3. Remove "Final Sale" text
4. Prefix with `SP-`

---

## 6. **Snipes**

### Source
Extracted from SKU field in email

### Pattern
```
{NUMERIC_SKU}
```

### Examples
- `15408700018` - from "SKU: 15408700018"
- `15209800042` - from "SKU: 15209800042"

### Code Location
`app/services/snipes_parser.py` - Lines 342-346
```python
# Extract SKU - format: "SKU: 15408700018"
sku_match = re.search(r'SKU:\s*(\d+)', row_text, re.IGNORECASE)
if sku_match:
    sku = sku_match.group(1)
    details['unique_id'] = sku
```

---

## 7. **Finish Line**

### Source
Extracted from product image URL

### Pattern
```
{STYLE_CODE}_{COLOR_CODE} or {STYLE_CODE}
```

### Examples
- `DM4044_108` - from image URL: `media.finishline.com/s/finishline/DM4044_108`
- `IB4437_663` - from image URL: `media.finishline.com/s/finishline/IB4437_663`
- `FJ4209_001` - from image URL: `media.finishline.com/s/finishline/FJ4209_001`

### Code Location
`app/services/finishline_parser.py` - Lines 350-359
```python
# Extract SKU from URL: media.finishline.com/s/finishline/IB4437_663?$default$
img_tag = element.find('img', src=re.compile(r'media\.finishline\.com/s/finishline/'))
if img_tag:
    src = img_tag.get('src', '')
    sku_match = re.search(r'/finishline/([A-Z0-9_]+)', src)
    if sku_match:
        sku = sku_match.group(1).split('?')[0]
        details['unique_id'] = sku
```

---

## 8. **Shop Simon**

### Source
Generated from product name (with brand prefix)

### Pattern
```
SS-{Product Name Without Possessives}
```

### Examples
- Product: "Men's adidas Adilette 22 Slides - US 7"
  - → `SS-Mens adidas Adilette 22 Slides`
- Product: "Women's Nike Air Max 270 - US 8.5"
  - → `SS-Womens Nike Air Max 270`

### Code Location
`app/services/shopsimon_parser.py` - Lines 395-400
```python
# Generate unique_id: SS-{Product Name}
# Remove possessive apostrophes
product_name_clean = product_name.replace("'s", "s")
product_name_clean = product_name_clean.replace("'", "")

unique_id = f"SS-{product_name_clean}"
```

### Processing
1. Extract product name before " - US" pattern
2. Remove possessive apostrophes ('s → s)
3. Prefix with `SS-`

---

## 9. **JD Sports**

### Source
Extracted from product image URL

### Pattern
```
{STYLE_CODE}_{COLOR_CODE} or {STYLE_CODE}
```

### Examples
- `JH6365_100` - from image URL: `media.jdsports.com/s/jdsports/JH6365_100`
- `IG5187_001` - from image URL: `media.jdsports.com/s/jdsports/IG5187_001`

### Code Location
`app/services/jdsports_parser.py` - Lines 290-296
```python
# Extract SKU from image URL
# Pattern: media.jdsports.com/s/jdsports/JH6365_100?$default$
src = img.get('src', '')
sku_match = re.search(r'/jdsports/([A-Z0-9_]+)', src)
if sku_match:
    sku = sku_match.group(1).split('?')[0]  # Remove query parameters
    details['unique_id'] = sku
```

---

## Summary Table

| Retailer | Source | Format | Example |
|----------|--------|--------|---------|
| **Footlocker** | Image URL | Alphanumeric | `64033WWH` |
| **Champs** | Image URL (same as FL) | Alphanumeric | `4181D090` |
| **Dick's** | Image URL | Alphanumeric | `23413456` |
| **Hibbett** | Image URL or Name | Alphanumeric/Generated | `HB87654` or `MENSNIKEAIRJORDAN` |
| **Shoe Palace** | Product Name | `SP-{Name}` | `SP-Air Jordan Collectors Duffle Bag` |
| **Snipes** | SKU Field | Numeric | `15408700018` |
| **Finish Line** | Image URL | Style_Color | `DM4044_108` |
| **Shop Simon** | Product Name | `SS-{Name}` | `SS-Mens adidas Adilette 22 Slides` |
| **JD Sports** | Image URL | Style_Color | `JH6365_100` |

---

## Notes

1. **OA Sourcing Match**: The `unique_id` must exactly match the `unique_id` field in the `oa_sourcing` table for the parser to successfully create purchase tracker records.

2. **Consistency**: For retailers that generate IDs from product names (Champs, Shoe Palace, Shop Simon, Hibbett fallback), ensure the OA Sourcing table uses the same generation logic.

3. **URL-Based IDs**: Most reliable as they're directly from the retailer's system (Footlocker, Dick's, Hibbett, Snipes, Finish Line).

4. **Name-Based IDs**: Require careful matching as product names may have slight variations (Champs, Shoe Palace, Shop Simon).
