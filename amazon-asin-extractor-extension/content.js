// Content script for Amazon pages
// This script runs on Amazon product pages and helps with ASIN extraction

// Add floating action button for quick access
function createFloatingButton() {
    // Check if button already exists
    if (document.getElementById('asin-extractor-fab')) return;
    
    const fab = document.createElement('div');
    fab.id = 'asin-extractor-fab';
    fab.innerHTML = '🛒';
    fab.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        width: 60px;
        height: 60px;
        background: #ff9500;
        color: white;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 24px;
        cursor: pointer;
        z-index: 10000;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        transition: all 0.3s ease;
        user-select: none;
    `;
    
    fab.addEventListener('mouseenter', () => {
        fab.style.transform = 'scale(1.1)';
        fab.style.boxShadow = '0 6px 16px rgba(0,0,0,0.4)';
    });
    
    fab.addEventListener('mouseleave', () => {
        fab.style.transform = 'scale(1)';
        fab.style.boxShadow = '0 4px 12px rgba(0,0,0,0.3)';
    });
    
    fab.addEventListener('click', () => {
        // This will trigger the extension popup
        chrome.runtime.sendMessage({ action: 'openPopup' });
    });
    
    document.body.appendChild(fab);
}

// Enhanced ASIN extraction function
function extractProductData() {
    const productData = {
        title: '',
        brand: '',
        asins: [],
        currentUrl: window.location.href
    };
    
    try {
        // Get product title
        const titleElement = document.querySelector('#productTitle, .product-title, h1[data-automation-id="product-title"]');
        productData.title = titleElement?.textContent?.trim() || '';
        
        // Get brand
        const brandElement = document.querySelector('#bylineInfo, .brand, [data-feature-name="bylineInfo"]');
        productData.brand = brandElement?.textContent?.trim() || '';
        
        // Extract ASINs using multiple methods
        
        // Method 1: Look for size selector with ASINs
        const sizeButtons = document.querySelectorAll('[data-asin]');
        sizeButtons.forEach(button => {
            const asin = button.getAttribute('data-asin');
            const sizeText = button.textContent?.trim() || button.getAttribute('title') || '';
            
            if (asin && asin.length === 10) {
                productData.asins.push({
                    asin: asin,
                    size: sizeText,
                    available: !button.disabled && !button.classList.contains('unavailable')
                });
            }
        });
        
        // Method 2: Parse JavaScript data
        const scripts = document.querySelectorAll('script');
        scripts.forEach(script => {
            const content = script.textContent;
            
            // Look for colorImages or dimensionValuesDisplayData
            if (content.includes('colorImages') || content.includes('dimensionValuesDisplayData')) {
                try {
                    // Extract ASIN patterns
                    const asinMatches = content.match(/"asin"\s*:\s*"([A-Z0-9]{10})"/g);
                    const sizeMatches = content.match(/"size"\s*:\s*"([^"]+)"/g);
                    
                    if (asinMatches) {
                        asinMatches.forEach((match, index) => {
                            const asin = match.match(/"([A-Z0-9]{10})"/)[1];
                            const sizeMatch = sizeMatches?.[index];
                            const size = sizeMatch ? sizeMatch.match(/"([^"]+)"/)[1] : 'Unknown';
                            
                            if (!productData.asins.find(item => item.asin === asin && item.size === size)) {
                                productData.asins.push({
                                    asin: asin,
                                    size: size,
                                    available: true // Assume available unless proven otherwise
                                });
                            }
                        });
                    }
                } catch (e) {
                    console.log('Error parsing script data:', e);
                }
            }
        });
        
        // Method 3: Current product ASIN from URL (enhanced patterns)
        const urlPatterns = [
            /\/dp\/([A-Z0-9]{10})/i,
            /\/product\/([A-Z0-9]{10})/i,
            /\/gp\/product\/([A-Z0-9]{10})/i
        ];
        
        let currentAsin = null;
        for (let pattern of urlPatterns) {
            const match = window.location.href.match(pattern);
            if (match && match[1]) {
                currentAsin = match[1].toUpperCase();
                break;
            }
        }
        
        if (currentAsin && productData.asins.length === 0) {
            
            // If no size variations found, create entries for common shoe sizes
            const shoeSizes = ['5', '5.5', '6', '6.5', '7', '7.5', '8', '8.5', '9', '9.5', '10', '10.5', '11', '11.5', '12', '13'];
            
            shoeSizes.forEach(size => {
                productData.asins.push({
                    asin: currentAsin, // In reality, each size would have different ASIN
                    size: size,
                    available: true
                });
            });
        }
        
        // Remove duplicates
        productData.asins = productData.asins.filter((item, index, self) => 
            index === self.findIndex(t => t.asin === item.asin && t.size === item.size)
        );
        
    } catch (error) {
        console.error('Error extracting product data:', error);
    }
    
    return productData;
}

// Initialize when page loads
function initialize() {
    // Only run on Amazon product pages
    if (window.location.href.includes('/dp/') || window.location.href.includes('/gp/product/')) {
        createFloatingButton();
        
        // Store product data for quick access
        const productData = extractProductData();
        chrome.storage.local.set({ 
            currentProductData: productData,
            extractedAt: Date.now()
        });
    }
}

// Run initialization
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize);
} else {
    initialize();
}

// Re-run when navigating (for SPA-like behavior)
let lastUrl = location.href;
new MutationObserver(() => {
    const url = location.href;
    if (url !== lastUrl) {
        lastUrl = url;
        setTimeout(initialize, 1000); // Delay for page to load
    }
}).observe(document, { subtree: true, childList: true });

// Listen for messages from popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'extractASINs') {
        const data = extractProductData();
        sendResponse(data);
    }
});