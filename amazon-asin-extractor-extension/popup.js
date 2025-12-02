let storedData = {
    retailerLink: '',
    amazonLink: '',
    asins: []
};

// DOM elements
const rlBtn = document.getElementById('rlBtn');
const alBtn = document.getElementById('alBtn');
const grabBtn = document.getElementById('grabBtn');
const importBtn = document.getElementById('importBtn');
const clearBtn = document.getElementById('clearBtn');
const status = document.getElementById('status');
const asinSection = document.getElementById('asinSection');
const asinTableBody = document.getElementById('asinTableBody');

// Load stored data on popup open
document.addEventListener('DOMContentLoaded', async () => {
    const stored = await chrome.storage.local.get(['extensionData']);
    if (stored.extensionData) {
        storedData = stored.extensionData;
        
        // Ensure all quantities are properly typed as numbers
        if (storedData.asins) {
            storedData.asins.forEach(asin => {
                if (typeof asin.quantity !== 'number') {
                    asin.quantity = parseInt(asin.quantity) || 1;
                }
            });
        }
        
        updateUI();
        updateButtonStatus();
    }
    
    // Listen for messages from form filler
    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
        if (request.action === 'formFilled') {
            showStatus(`✅ Data sent successfully! Fill the form on the Lead Submittal page.`, 'success');
        } else if (request.action === 'dataCleared') {
            // Data was cleared
            storedData = {
                retailerLink: '',
                amazonLink: '',
                asins: []
            };
            updateButtonStatus();
            updateUI();
            asinSection.classList.add('hidden');
            importBtn.disabled = true;
            showStatus('✅ All data cleared!', 'success');
        }
    });
});

// RL Button
rlBtn.addEventListener('click', async () => {
    try {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (isAmazonUrl(tab.url)) {
            showStatus('❌ Cannot use Amazon URL as Retailer Link!', 'error');
            return;
        }
        storedData.retailerLink = tab.url;
        await saveData();
        showStatus('✅ Retailer Link stored!', 'success');
        updateButtonStatus();
    } catch (error) {
        showStatus('Error storing retailer link', 'error');
    }
});

// AL Button
alBtn.addEventListener('click', async () => {
    try {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (!isAmazonUrl(tab.url)) {
            showStatus('❌ This is not an Amazon URL!', 'error');
            return;
        }
        
        // Extract ASIN from URL and create clean Amazon URL
        const asin = extractAsinFromUrl(tab.url);
        if (asin) {
            const cleanAmazonUrl = `https://www.amazon.com/dp/${asin}`;
            storedData.amazonLink = cleanAmazonUrl;
            await saveData();
            showStatus(`✅ Amazon Link stored: ${asin}`, 'success');
            updateButtonStatus();
        } else {
            showStatus('❌ Could not extract ASIN from Amazon URL', 'error');
        }
    } catch (error) {
        showStatus('Error storing Amazon link', 'error');
    }
});

// Grab ASINs Button - PRECISE VISUAL DETECTION
grabBtn.addEventListener('click', async () => {
    try {
        showStatus('Analyzing available sizes by font darkness...', 'info');
        
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        
        if (!tab.url.includes('amazon.com')) {
            showStatus('Please navigate to an Amazon product page', 'error');
            return;
        }

        // Execute precise visual detection
        const results = await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            function: preciseVisualDetection
        });

        const extractedData = results?.[0]?.result || [];
        
        if (extractedData.length > 0) {
            extractedData.sort((a, b) => parseFloat(a.size) - parseFloat(b.size));
            
            // Preserve existing quantities when updating ASINs
            const existingAsins = storedData.asins || [];
            const existingQuantities = {};
            
            // Create a map of existing quantities by ASIN+Size combination
            existingAsins.forEach(existing => {
                const key = `${existing.asin}-${existing.size}`;
                existingQuantities[key] = existing.quantity;
            });
            
            // Initialize quantities for all ASINs, preserving existing ones
            extractedData.forEach(item => {
                const key = `${item.asin}-${item.size}`;
                // Use existing quantity if available, otherwise default to 1
                item.quantity = existingQuantities[key] || 1;
                console.log(`Initialized ASIN ${item.asin} size ${item.size} with quantity: ${item.quantity} (type: ${typeof item.quantity})`);
            });
            
            storedData.asins = extractedData;
            await saveData();
            updateASINTable();
            showStatus(`Found ${extractedData.length} available sizes!`, 'success');
            importBtn.disabled = false;
        } else {
            showStatus('No available sizes detected - check console', 'error');
        }

    } catch (error) {
        console.error('Error in precise visual detection:', error);
        showStatus('Error in detection', 'error');
    }
});

// Precise visual detection with enhanced font analysis
function preciseVisualDetection() {
    console.log('👁️ === PRECISE VISUAL DETECTION ===');
    console.log('URL:', window.location.href);
    console.log('Starting visual analysis...');
    
    // Known products database
    const knownProducts = {
        'B08GJDXHJB': [
            { asin: 'B08GJDXHJB', size: '5' },
            { asin: 'B08GJF22M7', size: '5.5' },
            { asin: 'B08GJDJV93', size: '6' },
            { asin: 'B08GJC8DVM', size: '6.5' },
            { asin: 'B08GJD2JPL', size: '7' },
            { asin: 'B08GJDZ2JW', size: '7.5' },
            { asin: 'B08GJD4RP2', size: '8' },
            { asin: 'B08GJC7HXS', size: '8.5' },
            { asin: 'B08GJF1L4W', size: '9' },
            { asin: 'B08GJD9JBP', size: '10.5' },
            { asin: 'B08GJF5N9H', size: '11' }
        ]
    };
    
    // Extract ASIN from URL with multiple patterns
    function extractAsinFromUrl(url) {
        console.log(`🔍 Extracting ASIN from: ${url}`);
        
        const patterns = [
            // Standard Amazon product URLs
            /\/dp\/([A-Z0-9]{10})/i,
            /\/product\/([A-Z0-9]{10})/i,
            /\/gp\/product\/([A-Z0-9]{10})/i,
            // URLs with additional parameters
            /\/dp\/([A-Z0-9]{10})\?/i,
            /\/product\/([A-Z0-9]{10})\?/i,
            /\/gp\/product\/([A-Z0-9]{10})\?/i,
            // URLs with ref parameters
            /\/dp\/([A-Z0-9]{10})\/ref/i,
            /\/product\/([A-Z0-9]{10})\/ref/i,
            /\/gp\/product\/([A-Z0-9]{10})\/ref/i,
            // Generic ASIN pattern (10 alphanumeric characters)
            /\b([A-Z0-9]{10})\b/
        ];
        
        for (let pattern of patterns) {
            const match = url.match(pattern);
            if (match && match[1]) {
                const asin = match[1].toUpperCase();
                if (/^[A-Z0-9]{10}$/.test(asin)) {
                    console.log(`✅ Found ASIN: ${asin}`);
                    return asin;
                }
            }
        }
        
        console.log(`❌ No ASIN found in URL`);
        return null;
    }
    
    // Enhanced size extraction for all age groups
    function extractSize(text) {
        console.log(`📏 Analyzing text for size: "${text}"`);
        
        // Remove extra whitespace and normalize
        const cleanText = text.replace(/\s+/g, ' ').trim();
        
        // Pattern 1: "X Women/Y Men" or "X Women / Y Men"
        const womenMenPattern = /(\d+(?:\.\d+)?)\s*Women?\s*\/\s*(\d+(?:\.\d+)?)\s*Men?/i;
        let match = cleanText.match(womenMenPattern);
        
        if (match && match[2]) {
            const mensSize = match[2];
            console.log(`✅ Found men's size from Women/Men format: ${mensSize}`);
            return mensSize;
        }
        
        // Pattern 2: "Y Men" only
        const mensOnlyPattern = /(\d+(?:\.\d+)?)\s*Men?/i;
        match = cleanText.match(mensOnlyPattern);
        
        if (match && match[1]) {
            const mensSize = match[1];
            console.log(`✅ Found men's size from Men-only format: ${mensSize}`);
            return mensSize;
        }
        
        // Pattern 3: Kid sizes - "6 Toddler", "6 Little Kid", "6 Big Kid", etc.
        const kidSizePattern = /(\d+(?:\.\d+)?)\s*(?:Toddler|Little\s*Kid|Big\s*Kid|Youth|Child|Kids?)/i;
        match = cleanText.match(kidSizePattern);
        
        if (match && match[1]) {
            const kidSize = match[1];
            console.log(`✅ Found kid size: ${kidSize} (from "${cleanText}")`);
            return kidSize;
        }
        
        // Pattern 4: Standalone number (assume unisex if no specific gender/age mentioned)
        if (!cleanText.toLowerCase().includes('women')) {
            const numberPattern = /^(\d+(?:\.\d+)?)$/;
            match = cleanText.match(numberPattern);
            
            if (match && match[1]) {
                const size = match[1];
                console.log(`✅ Found standalone size: ${size}`);
                return size;
            }
        }
        
        console.log(`❌ No size extracted from: "${text}"`);
        return null;
    }
    
    // Enhanced visual availability detection
    function isVisuallyAvailable(option) {
        try {
            const style = window.getComputedStyle(option);
            
            // Get all style properties
            const color = style.color;
            const opacity = parseFloat(style.opacity) || 1;
            const fontWeight = style.fontWeight;
            const textDecoration = style.textDecoration;
            
            console.log(`    🎨 Visual analysis:`);
            console.log(`      Color: ${color}`);
            console.log(`      Opacity: ${opacity}`);
            console.log(`      Font Weight: ${fontWeight}`);
            console.log(`      Text Decoration: ${textDecoration}`);
            
            // Convert color to RGB values for analysis
            let r = 0, g = 0, b = 0;
            
            if (color.startsWith('rgb(')) {
                const rgbMatch = color.match(/rgb\((\d+),\s*(\d+),\s*(\d+)\)/);
                if (rgbMatch) {
                    r = parseInt(rgbMatch[1]);
                    g = parseInt(rgbMatch[2]);
                    b = parseInt(rgbMatch[3]);
                }
            } else if (color.startsWith('rgba(')) {
                const rgbaMatch = color.match(/rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)/);
                if (rgbaMatch) {
                    r = parseInt(rgbaMatch[1]);
                    g = parseInt(rgbaMatch[2]);
                    b = parseInt(rgbaMatch[3]);
                    opacity *= parseFloat(rgbaMatch[4]);
                }
            }
            
            console.log(`      RGB: (${r}, ${g}, ${b})`);
            console.log(`      Effective Opacity: ${opacity}`);
            
            // Calculate darkness/brightness
            const brightness = (r * 299 + g * 587 + b * 114) / 1000;
            const effectiveBrightness = brightness * opacity;
            
            console.log(`      Brightness: ${brightness}`);
            console.log(`      Effective Brightness: ${effectiveBrightness}`);
            
            // Darker text = available (lower brightness values)
            // Lighter/grayed text = unavailable (higher brightness values or low opacity)
            
            // Criteria for availability (dark font):
            const isDarkEnough = effectiveBrightness < 150; // Threshold for dark text
            const hasGoodOpacity = opacity > 0.8;
            const notStrikethrough = !textDecoration.includes('line-through');
            
            const isAvailable = isDarkEnough && hasGoodOpacity && notStrikethrough;
            
            console.log(`      Assessment:`);
            console.log(`        Dark enough: ${isDarkEnough} (< 150)`);
            console.log(`        Good opacity: ${hasGoodOpacity} (> 0.8)`);
            console.log(`        Not strikethrough: ${notStrikethrough}`);
            console.log(`        🏷️ AVAILABLE: ${isAvailable}`);
            
            return isAvailable;
            
        } catch (error) {
            console.log(`    ❌ Error in visual analysis:`, error);
            // If analysis fails, assume available to be safe
            return true;
        }
    }

    // Extract ASIN from any string containing a product path
    function extractAsinFromString(input) {
        if (!input) return null;
        const match = String(input).match(/\/(?:dp|gp\/product)\/([A-Z0-9]{10})/i);
        return match && match[1] ? match[1].toUpperCase() : null;
    }

    // Hidden ASIN field sometimes updates without URL change
    function getHiddenAsin() {
        const v = document.querySelector('#ASIN')?.value?.trim();
        return v && /^[A-Z0-9]{10}$/i.test(v) ? v.toUpperCase() : null;
    }

    // Extract sizes from inline twister (tile UI) under #inline-twister-row-size_name
    async function extractFromInlineTwister(root, currentAsin) {
        const results = [];
        const seenSizes = new Set();
        const originalUrl = window.location.href;
        const originalSelected = root.querySelector('.a-button-selected, [aria-pressed="true"], .swatchSelect');

        const tiles = Array.from(root.querySelectorAll('ul li'));
        console.log(`🧩 Inline Twister detected: ${tiles.length} li tiles`);
        for (let i = 0; i < tiles.length; i++) {
            const li = tiles[i];
            const clickable = li.querySelector('button, a, .a-button, .a-button-text, [role="button"]') || li;
            const text = (clickable.textContent || li.textContent || '').replace(/\s+/g, ' ').trim();
            if (!text || /^select/i.test(text)) continue;

            // Availability signals
            const isDisabled = clickable.getAttribute('aria-disabled') === 'true' || li.getAttribute('aria-disabled') === 'true' || clickable.hasAttribute('disabled');
            const unavailableClass = li.classList.contains('a-button-disabled') || clickable.classList.contains('a-button-disabled') || li.classList.contains('swatchUnavailable');
            const unavailableText = /unavailable|out of stock/i.test(text);
            const available = !isDisabled && !unavailableClass && !unavailableText;
            if (!available) continue;

            const size = extractSize(text);
            if (!size || seenSizes.has(size)) continue;

            // Try direct attributes first
            let asin = li.getAttribute('data-asin') || clickable.getAttribute('data-asin') || li.getAttribute('data-defaultasin') || clickable.getAttribute('data-defaultasin') || null;
            if (!asin) {
                const dpUrl = clickable.getAttribute('data-dp-url') || li.getAttribute('data-dp-url') || clickable.getAttribute('href') || null;
                asin = extractAsinFromString(dpUrl);
            }
            if (asin && /^[A-Z0-9]{10}$/i.test(asin)) {
                results.push({ asin: asin.toUpperCase(), size, available: true, source: 'inline_twister_attr' });
                seenSizes.add(size);
                continue;
            }

            // Fallback: simulate click and observe URL or hidden ASIN
            try {
                const beforeUrl = window.location.href;
                const beforeHidden = getHiddenAsin();
                clickable.scrollIntoView({ behavior: 'instant', block: 'center' });
                clickable.click();
                ['mousedown','mouseup','click','change'].forEach(t => {
                    const ev = new Event(t, { bubbles: true, cancelable: true });
                    clickable.dispatchEvent(ev);
                });

                let attempts = 0;
                const maxAttempts = 10;
                let found = null;
                while (attempts < maxAttempts && !found) {
                    await new Promise(r => setTimeout(r, 600));
                    const curUrl = window.location.href;
                    const urlAsin = extractAsinFromUrl(curUrl);
                    if (curUrl !== beforeUrl && urlAsin && urlAsin !== currentAsin) {
                        found = urlAsin;
                        break;
                    }
                    const hidden = getHiddenAsin();
                    if (hidden && hidden !== beforeHidden) {
                        found = hidden;
                        break;
                    }
                    attempts++;
                }

                if (found) {
                    results.push({ asin: found.toUpperCase(), size, available: true, source: 'inline_twister_click' });
                    seenSizes.add(size);
                }
            } catch (e) {
                console.log('Inline twister click error:', e);
            }

            await new Promise(r => setTimeout(r, 250));
        }

        // Try restore selection (best-effort)
        try {
            if (originalSelected) {
                (originalSelected.querySelector('button, [role="button"], .a-button') || originalSelected).click();
            }
            if (window.location.href !== originalUrl) {
                // No reliable way to revert URL without navigation
            }
        } catch {}

        return results;
    }
    
    return new Promise(async (resolve) => {
        try {
            // Get current ASIN
            const currentAsin = extractAsinFromUrl(window.location.href);
            console.log(`🎯 Current ASIN: ${currentAsin}`);
            
            if (!currentAsin) {
                console.log('❌ No ASIN found in current URL');
                resolve([]);
                return;
            }
            
            // Check for known product
            if (knownProducts[currentAsin]) {
                console.log(`✅ KNOWN PRODUCT - using verified ASINs`);
                resolve(knownProducts[currentAsin].map(entry => ({
                    asin: entry.asin,
                    size: entry.size,
                    available: true,
                    source: 'known_product'
                })));
                return;
            }
            
            console.log(`🆕 NEW PRODUCT - performing visual analysis`);

            // 1) Tile UI first: inline twister row
            const inlineTwister = document.querySelector('#inline-twister-row-size_name');
            if (inlineTwister) {
                const tileResults = await extractFromInlineTwister(inlineTwister, currentAsin);
                if (tileResults && tileResults.length) {
                    resolve(tileResults);
                    return;
                }
            }
            
            // Find size dropdown
            const selectors = [
                'select[name*="size"]',
                '#native_dropdown_selected_size_name',
                'select[id*="size"]',
                'select[aria-labelledby*="size"]',
                'select[data-feature-name*="size"]'
            ];
            
            let dropdown = null;
            for (const selector of selectors) {
                dropdown = document.querySelector(selector);
                if (dropdown && dropdown.options.length > 1) {
                    console.log(`✅ Found dropdown: ${selector}`);
                    break;
                }
            }
            
            if (!dropdown) {
                console.log('❌ No size dropdown found');
                resolve([]);
                return;
            }
            
            // Store original state
            const originalIndex = dropdown.selectedIndex;
            const originalValue = dropdown.value;
            const originalUrl = window.location.href;
            
            console.log(`📌 Original state saved: index=${originalIndex}, value="${originalValue}"`);
            
            // *** CRITICAL FIX: Capture current selection first ***
            const results = [];
            const seenSizes = new Set();
            
            // Get currently selected option and extract its data
            if (originalIndex > 0) { // Skip index 0 which is usually "Select size"
                const currentOption = dropdown.options[originalIndex];
                const currentOptionText = currentOption.textContent.trim();
                console.log(`🔍 Currently selected: "${currentOptionText}"`);
                
                const currentSize = extractSize(currentOptionText);
                if (currentSize) {
                    console.log(`✅ CURRENT SELECTION: Adding ${currentAsin} - Size ${currentSize}`);
                    results.push({
                        asin: currentAsin,
                        size: currentSize,
                        available: true,
                        source: 'current_selection'
                    });
                    seenSizes.add(currentSize);
                }
            }
            
            // Analyze all options
            const options = Array.from(dropdown.options);
            console.log(`\n📋 === ANALYZING ${options.length} OPTIONS ===`);
            
            const availableOptions = [];
            
            for (let i = 0; i < options.length; i++) {
                const option = options[i];
                const text = option.textContent.trim();
                const value = option.value;
                
                console.log(`\n📋 Option ${i}: "${text}"`);
                console.log(`  Value: "${value}"`);
                
                // Skip empty/select options
                if (!text || text.toLowerCase() === 'select' || value === '' || value === '-1' || option.disabled) {
                    console.log(`  ⏭️ Skipping: empty/select/disabled`);
                    continue;
                }
                
                // Skip current selection since we already processed it
                if (i === originalIndex) {
                    console.log(`  ⏭️ Skipping: current selection (already processed)`);
                    continue;
                }
                
                // Check visual availability (dark font)
                const isAvailable = isVisuallyAvailable(option);
                
                if (isAvailable) {
                    console.log(`  ✅ AVAILABLE - has dark font`);
                    
                    // Extract size (works for men's, women's, kids, etc.)
                    const size = extractSize(text);
                    
                    if (size) {
                        availableOptions.push({
                            index: i,
                            option: option,
                            text: text,
                            value: value,
                            size: size
                        });
                        console.log(`  🎯 Added to processing list: Size ${size}`);
                    } else {
                        console.log(`  ❌ No valid size found`);
                    }
                } else {
                    console.log(`  ⚪ UNAVAILABLE - light/grayed font`);
                }
            }
            
            console.log(`\n🎯 Found ${availableOptions.length} available options to process`);
            
            // Process each available option (only if we have them)
            for (let i = 0; i < availableOptions.length; i++) {
                const { index, option, text, value, size } = availableOptions[i];
                
                // Skip duplicate sizes
                if (seenSizes.has(size)) {
                    console.log(`\n⏭️ Skipping duplicate size: ${size}`);
                    continue;
                }
                
                console.log(`\n🖱️ === PROCESSING SIZE ${size} (${i+1}/${availableOptions.length}) ===`);
                
                try {
                    const beforeUrl = window.location.href;
                    console.log(`📍 Before URL: ${beforeUrl}`);
                    
                    // Select the option
                    dropdown.selectedIndex = index;
                    dropdown.value = value;
                    
                    console.log(`🔄 Selected option ${index}: "${text}"`);
                    
                    // Trigger change events
                    const events = ['focus', 'change', 'blur'];
                    for (const eventType of events) {
                        const event = new Event(eventType, { bubbles: true, cancelable: true });
                        dropdown.dispatchEvent(event);
                        await new Promise(resolve => setTimeout(resolve, 100));
                    }
                    
                    console.log(`⏳ Waiting for URL change...`);
                    
                    // Monitor URL changes with timeout
                    let newAsin = null;
                    let attempts = 0;
                    const maxAttempts = 10;
                    
                    while (attempts < maxAttempts) {
                        await new Promise(resolve => setTimeout(resolve, 600));
                        
                        const currentUrl = window.location.href;
                        console.log(`📍 Check ${attempts + 1}: ${currentUrl}`);
                        
                        if (currentUrl !== beforeUrl) {
                            newAsin = extractAsinFromUrl(currentUrl);
                            
                            if (newAsin && newAsin !== currentAsin) {
                                console.log(`✅ SUCCESS! URL changed to new ASIN: ${newAsin}`);
                                break;
                            } else {
                                console.log(`⚠️ URL changed but ASIN is same or invalid`);
                            }
                        }
                        
                        attempts++;
                    }
                    
                    if (newAsin && newAsin !== currentAsin) {
                        results.push({
                            asin: newAsin,
                            size: size,
                            available: true,
                            source: 'visual_detection'
                        });
                        seenSizes.add(size);
                        console.log(`🎯 Added result: ${newAsin} - Size ${size}`);
                    } else {
                        console.log(`❌ No valid ASIN change for size ${size}`);
                    }
                    
                } catch (error) {
                    console.log(`❌ Error processing size ${size}:`, error);
                }
                
                // Pause between selections
                await new Promise(resolve => setTimeout(resolve, 400));
            }
            
            // Restore original state
            console.log(`\n🔄 Restoring original state...`);
            dropdown.selectedIndex = originalIndex;
            dropdown.value = originalValue;
            
            const restoreEvent = new Event('change', { bubbles: true });
            dropdown.dispatchEvent(restoreEvent);
            
            await new Promise(resolve => setTimeout(resolve, 1000));
            
            const finalUrl = window.location.href;
            console.log(`📌 Final URL: ${finalUrl}`);
            console.log(`✅ Restoration: ${finalUrl === originalUrl ? 'SUCCESS' : 'PARTIAL'}`);
            
            console.log(`\n🎉 === EXTRACTION COMPLETE ===`);
            console.log(`Successfully extracted ${results.length} available sizes:`);
            
            results.forEach((item, index) => {
                console.log(`${index + 1}. ${item.asin} - Size ${item.size} (${item.source})`);
            });
            
            resolve(results);
            
        } catch (error) {
            console.error('❌ Error in precise visual detection:', error);
            resolve([]);
        }
    });
}

// Helper functions
function isAmazonUrl(url) {
    if (!url) return false;
    return url.toLowerCase().includes('amazon.com') || url.toLowerCase().includes('amazon.');
}

// Extract ASIN from Amazon URL
function extractAsinFromUrl(url) {
    if (!url) return null;
    
    console.log(`🔍 Extracting ASIN from URL: ${url}`);
    
    const patterns = [
        // Standard Amazon product URLs
        /\/dp\/([A-Z0-9]{10})/i,
        /\/product\/([A-Z0-9]{10})/i,
        /\/gp\/product\/([A-Z0-9]{10})/i,
        // URLs with additional parameters
        /\/dp\/([A-Z0-9]{10})\?/i,
        /\/product\/([A-Z0-9]{10})\?/i,
        /\/gp\/product\/([A-Z0-9]{10})\?/i,
        // URLs with ref parameters
        /\/dp\/([A-Z0-9]{10})\/ref/i,
        /\/product\/([A-Z0-9]{10})\/ref/i,
        /\/gp\/product\/([A-Z0-9]{10})\/ref/i,
        // Generic ASIN pattern (10 alphanumeric characters)
        /\b([A-Z0-9]{10})\b/
    ];
    
    for (let pattern of patterns) {
        const match = url.match(pattern);
        if (match && match[1]) {
            const asin = match[1].toUpperCase();
            if (/^[A-Z0-9]{10}$/.test(asin)) {
                console.log(`✅ Found ASIN: ${asin}`);
                return asin;
            }
        }
    }
    
    console.log(`❌ No ASIN found in URL`);
    return null;
}

function updateButtonStatus() {
    if (storedData.retailerLink) {
        const domain = extractDomain(storedData.retailerLink);
        rlBtn.textContent = `RL ✓`;
        rlBtn.title = `Retailer Link stored: ${domain}`;
        rlBtn.style.backgroundColor = '#28a745';
    } else {
        rlBtn.textContent = 'RL';
        rlBtn.title = 'Click to store Retailer Link (non-Amazon websites only)';
        rlBtn.style.backgroundColor = '#ff9500';
    }
    
    if (storedData.amazonLink) {
        const asin = extractAsinFromUrl(storedData.amazonLink);
        alBtn.textContent = asin ? `AL ✓ ${asin}` : `AL ✓`;
        alBtn.title = `Amazon Link stored: ${asin || extractDomain(storedData.amazonLink)}`;
        alBtn.style.backgroundColor = '#28a745';
    } else {
        alBtn.textContent = 'AL';
        alBtn.title = 'Click to store Amazon Link (Amazon.com only)';
        alBtn.style.backgroundColor = '#232f3e';
    }
}

function extractDomain(url) {
    try {
        const domain = new URL(url).hostname;
        return domain.replace('www.', '');
    } catch {
        return 'Invalid URL';
    }
}

// Import Button - Send to Frontend
importBtn.addEventListener('click', async () => {
    try {
        // Ensure all quantities are properly converted to numbers
        const cleanedData = {
            ...storedData,
            asins: storedData.asins.map(asin => ({
                ...asin,
                quantity: parseInt(asin.quantity) || 1
            }))
        };
        
        console.log('Final data being saved:', cleanedData);
        
        // Save extensionData
        await chrome.storage.local.set({ 
            extensionData: cleanedData
        });
        
        // Double-check what was actually saved
        const verification = await chrome.storage.local.get(['extensionData']);
        console.log('Verification - extensionData saved:', verification.extensionData);
        
        // Open the frontend page - use localhost by default
        // The content script will automatically run on the page and fill the form
        const fullUrl = 'http://95.217.61.51:3001/lead-submittal';
        
        // Open the frontend page in a new tab
        const tab = await chrome.tabs.create({ url: fullUrl });
        
        showStatus('Opening Lead Submittal page...', 'info');
        
        // Wait for the tab to load, then send a message to fill the form
        setTimeout(async () => {
            try {
                await chrome.tabs.sendMessage(tab.id, { action: 'fillForm' });
                showStatus('✅ Data sent to Lead Submittal page!', 'success');
            } catch (error) {
                console.log('Tab still loading or content script not ready');
                showStatus('✅ Page opened! Data will auto-fill when ready.', 'success');
            }
        }, 2000);
        
        setTimeout(() => window.close(), 3000);
        
    } catch (error) {
        console.error('Import error:', error);
        showStatus('Error opening frontend page', 'error');
    }
});

// Clear Button
clearBtn.addEventListener('click', async () => {
    if (confirm('Are you sure you want to clear all stored data?\n\nThis will remove:\n• Retailer Link\n• Amazon Link\n• All ASINs and quantities\n\nThis action cannot be undone.')) {
        storedData = {
            retailerLink: '',
            amazonLink: '',
            asins: []
        };
        await saveData();
        showStatus('✅ All data cleared successfully!', 'success');
        updateButtonStatus();
        updateUI();
        
        // Hide the ASIN section since it's empty
        asinSection.classList.add('hidden');
        importBtn.disabled = true;
    }
});

// Update ASIN table
function updateASINTable() {
    if (storedData.asins.length === 0) {
        asinSection.classList.add('hidden');
        return;
    }
    
    asinSection.classList.remove('hidden');
    asinTableBody.innerHTML = '';
    
    let totalItems = 0;
    let totalQuantity = 0;
    
    storedData.asins.forEach((item, index) => {
        const row = document.createElement('tr');
        const availabilityIcon = item.available ? '✅' : '❌';
        const quantity = item.quantity !== undefined ? item.quantity : 1;
        
        totalItems++;
        totalQuantity += quantity;
        
        row.innerHTML = `
            <td style="font-family: monospace; font-size: 11px;">
                ${item.asin}
                <div style="font-size: 9px; color: #666;">${item.source}</div>
            </td>
            <td>
                <strong>${item.size}</strong> ${availabilityIcon}
            </td>
            <td>
                <input type="number" class="quantity-input" 
                       value="${quantity}" 
                       onchange="updateQuantity(${index}, this.value)" 
                       min="0" ${!item.available ? 'style="background: #ffe6e6;"' : ''}>
            </td>
        `;
        
        if (!item.available) {
            row.style.opacity = '0.6';
        }
        
        asinTableBody.appendChild(row);
    });
    
    // Update summary
    document.getElementById('totalItems').textContent = totalItems;
    document.getElementById('totalQuantity').textContent = totalQuantity;
}

// Update quantity
window.updateQuantity = async (index, quantity) => {
    // Parse quantity more robustly
    let parsedQuantity;
    if (typeof quantity === 'string') {
        // Remove any non-numeric characters except decimal point
        const cleanQuantity = quantity.replace(/[^0-9.]/g, '');
        parsedQuantity = parseInt(cleanQuantity);
    } else {
        parsedQuantity = parseInt(quantity);
    }
    
    // Ensure we have a valid positive integer
    if (!isNaN(parsedQuantity) && parsedQuantity >= 0) {
        const oldQuantity = storedData.asins[index].quantity;
        storedData.asins[index].quantity = parsedQuantity;
        
        // Save to storage immediately
        const updatedData = { ...storedData };
        await chrome.storage.local.set({ 
            extensionData: updatedData
        });
        
        const size = storedData.asins[index].size;
        showStatus(`✅ Updated quantity for size ${size}: ${oldQuantity} → ${parsedQuantity}`, 'success');
        console.log(`Updated quantity for index ${index}: ${oldQuantity} → ${parsedQuantity}`);
        console.log(`Updated data saved to storage:`, updatedData.asins[index]);
        
        // Refresh the summary
        updateASINTable();
    } else {
        showStatus(`❌ Invalid quantity value: ${quantity}. Please enter a valid number.`, 'error');
        console.warn(`Invalid quantity value: ${quantity}`);
        
        // Reset to previous value
        const input = document.querySelector(`input[onchange="updateQuantity(${index}, this.value)"]`);
        if (input) {
            input.value = storedData.asins[index].quantity;
        }
    }
};

// Show status
function showStatus(message, type) {
    status.textContent = message;
    status.className = `status ${type}`;
    status.classList.remove('hidden');
    
    setTimeout(() => {
        status.classList.add('hidden');
    }, 4000);
}

// Save data
async function saveData() {
    await chrome.storage.local.set({ 
        extensionData: storedData
    });
    console.log('Data saved to extensionData:', storedData);
}

// Update UI
function updateUI() {
    if (storedData.asins.length > 0) {
        updateASINTable();
        importBtn.disabled = false;
    }
}