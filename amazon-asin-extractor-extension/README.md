# Amazon ASIN Extractor + Lead Submittal Integration

A Chrome extension that extracts Amazon ASINs and product information from Amazon product pages and automatically fills your frontend Lead Submittal page.

## Features

### Core Functionality
- **Retailer Link (RL)**: Store non-Amazon website URLs
- **Amazon Link (AL)**: Store Amazon product URLs and automatically extract ASINs
- **ASIN Extraction**: Automatically detect available sizes and their corresponding ASINs
- **Lead Submittal Integration**: Auto-fill your frontend Lead Submittal page with extracted data
- **Quantity Management**: Set and manage quantities for each size

### Latest Updates (Version 2.0)

#### 🎯 Frontend Integration
- **Direct Integration**: Seamlessly connects with your frontend Lead Submittal page
- **Auto-Fill**: Automatically fills retailer link, Amazon link, and all ASIN data
- **Real-time Sync**: Data instantly appears in your form fields
- **Visual Feedback**: Success notifications confirm data transfer

#### 🗑️ Clear Functionality
- **Clear All Data Button**: Manually clear all stored data (Retailer Link, Amazon Link, ASINs)
- **Helper Buttons**: On-page buttons for filling and clearing data
- **Confirmation Dialog**: Prevents accidental data loss with detailed confirmation

#### 🔧 Bug Fixes & Enhancements
- **Quantity Import Fix**: Quantities now properly transfer to the frontend
- **Amazon Link Grabbing Fix**: Automatically extracts ASIN from any Amazon URL and creates clean URLs (e.g., `https://www.amazon.com/dp/B0D95L7KRY`)
- **Enhanced UI**: Summary section shows total items and total quantity

## How to Use

### 1. Store Links
1. **RL Button**: Click while on a non-Amazon website (e.g., Nike, Adidas) to store the retailer link
2. **AL Button**: Click while on an Amazon product page to store the Amazon link and extract ASIN

### 2. Extract ASINs
1. Navigate to an Amazon product page with size variations
2. Click **"Grab ASINs"** to automatically detect available sizes and their ASINs
3. Review the extracted ASINs in the table
4. Adjust quantities for each size using the input fields (defaults to 1)

### 3. Send to Lead Submittal Page
1. Set your frontend URL in the text field (default: `http://localhost:5173`)
2. Click **"Send to Lead Submittal"** button
3. The extension will:
   - Open your frontend Lead Submittal page in a new tab
   - Automatically fill in all the data:
     - Retailer Link
     - Amazon Link
     - All ASINs with their sizes and quantities
4. Complete the remaining form fields and submit

### 4. Clear Data
- Use the **"Clear All Data"** button in the extension popup to manually clear stored information
- Or use the **"Clear Data"** button on the frontend page
- Data can also be manually cleared before starting a new product

## Technical Details

### ASIN Extraction Methods
1. **Visual Analysis**: Detects available sizes by analyzing font darkness
2. **URL Monitoring**: Captures ASIN changes when sizes are selected
3. **Multiple Strategies**: Works with dropdown selectors and tile-based UIs
4. **Smart Detection**: Handles various Amazon product page layouts

### Frontend Integration
- **postMessage API**: Securely communicates with your frontend React app
- **Content Script**: Runs on localhost and your production domain
- **Auto-Detection**: Automatically detects when you're on the Lead Submittal page
- **Data Format**: 
  ```javascript
  {
    type: 'ASIN_DATA_FROM_EXTENSION',
    retailerLink: 'https://...',
    amazonLink: 'https://amazon.com/dp/...',
    asins: [
      { asin: 'B01EXAMPLE', size: '10', quantity: '5' },
      // ...
    ]
  }
  ```

### Data Storage
- Uses Chrome's local storage for data persistence
- Maintains data between browser sessions
- Can be manually cleared at any time

## Installation

### Load the Extension
1. Download or clone the extension folder
2. Open Chrome and navigate to `chrome://extensions/`
3. Enable **"Developer mode"** (toggle in top right)
4. Click **"Load unpacked"** 
5. Select the `amazon-asin-extractor-extension` folder
6. The extension icon will appear in your toolbar

### Configure Frontend URL
1. Click the extension icon to open the popup
2. Set your frontend URL in the text field:
   - Development: `http://localhost:5173` (or your dev port)
   - Production: `https://your-app.vercel.app`
3. The URL is saved automatically

## Workflow Example

### Complete Workflow:
1. **Find a product on retailer's website** (e.g., Nike.com)
   - Click **RL** button to store the retailer link

2. **Navigate to the same product on Amazon**
   - Click **AL** button to store the Amazon link
   - Click **Grab ASINs** to extract all available sizes

3. **Review and adjust quantities**
   - Check the extracted ASINs in the table
   - Modify quantities as needed (e.g., size 10 → quantity 5)

4. **Send to Lead Submittal**
   - Click **Send to Lead Submittal** button
   - Frontend page opens with all data pre-filled
   - Complete remaining fields (submitted by, product name, PPU, RSP, etc.)
   - Submit the lead

5. **Start fresh**
   - Click **Clear All Data** for the next product

## Supported URLs

### Amazon URLs
- `https://www.amazon.com/*`
- `https://amazon.com/*`

### Frontend URLs
- `http://localhost:*/*` (development)
- `https://*.vercel.app/*` (production)
- Update `manifest.json` for other domains

## Troubleshooting

### Common Issues

**No ASINs detected:**
- Ensure you're on an Amazon product page with size variations
- Check console logs for detailed extraction information
- Some products may use tile-based UI instead of dropdowns

**Data not appearing on frontend:**
- Verify the frontend URL is correct
- Check that you're on the `/dashboard/lead-submittal` page
- Open browser console to see postMessage logs
- Ensure the frontend page has the message listener active

**Quantities not transferring:**
- Verify quantities are set to positive numbers
- Check the extension popup table shows correct quantities
- Review console logs for data format issues

**Extension not loading:**
- Ensure manifest permissions match your frontend domain
- Check that all required files are present
- Reload the extension from `chrome://extensions/`

### Debug Information
- **Extension Popup Console**: Right-click popup → Inspect
- **Frontend Console**: Check for "Received data from extension" messages
- **Storage Inspection**: Chrome DevTools → Application → Storage → Local Storage
- **Network Tab**: Verify no CORS or permission issues

## Development

### File Structure
```
amazon-asin-extractor-extension/
├── manifest.json           # Extension configuration
├── popup.html             # Extension popup UI
├── popup.js               # Popup logic and ASIN extraction
├── content.js             # Amazon page content script
├── frontend-filler.js     # Frontend page content script
├── background.js          # Background service worker
├── styles.css             # Popup styles
└── README.md             # This file
```

### Modifying for Different Domains

To use with a different frontend domain, update `manifest.json`:

```json
{
  "host_permissions": [
    "https://your-domain.com/*"
  ],
  "content_scripts": [
    {
      "matches": ["https://your-domain.com/*"],
      "js": ["frontend-filler.js"]
    }
  ]
}
```

## Version History

### Version 2.0 (Current)
- ✅ Removed Google Forms integration
- ✅ Added frontend Lead Submittal page integration
- ✅ Enhanced data transfer with retailer and Amazon links
- ✅ Improved visual feedback and notifications
- ✅ Better error handling and debugging

### Version 1.0
- Initial release with Google Forms integration
- Basic ASIN extraction
- Quantity management

## Support

For issues or feature requests:
1. Check the browser console logs (F12)
2. Review the extension popup status messages
3. Verify data in Chrome DevTools → Application → Storage
4. Check that manifest.json permissions match your domains

## License

Copyright © 2024. All rights reserved.
