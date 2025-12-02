// Frontend Lead Submittal Auto-Filler
// This script runs on the frontend Lead Submittal page and fills in the data

let formData = null;
let fieldsFound = 0;
let fieldsFilled = 0;

// Initialize form filler
async function initializeFormFiller() {
    try {
        // Get stored form data
        const stored = await chrome.storage.local.get(['extensionData']);
        console.log('📦 Storage check - extensionData:', stored.extensionData);
        
        if (stored.extensionData && stored.extensionData.asins && stored.extensionData.asins.length > 0) {
            formData = stored.extensionData;
            console.log('✅ Form data loaded:', formData);
            
            // Wait a bit for the page to be fully loaded
            setTimeout(() => {
                fillFrontendForm();
            }, 2000);
        } else {
            console.log('ℹ️ No form data found in storage');
        }
    } catch (error) {
        console.error('❌ Error loading form data:', error);
    }
}

// Fill the Frontend Lead Submittal form
function fillFrontendForm() {
    if (!formData) {
        console.log('❌ No form data available');
        showFormStatus('No data to fill. Please extract ASINs first.', 'error');
        return;
    }
    
    fieldsFound = 0;
    fieldsFilled = 0;
    
    try {
        console.log('🚀 Starting form fill with data:', formData);
        
        // Check if we're on the lead-submittal page
        if (!window.location.pathname.includes('lead-submittal')) {
            console.log('⚠️ Not on lead-submittal page');
            return;
        }
        
        // Use postMessage to communicate with the React app
        const messageData = {
            type: 'ASIN_DATA_FROM_EXTENSION',
            retailerLink: formData.retailerLink || '',
            amazonLink: formData.amazonLink || '',
            asins: formData.asins.map(asin => ({
                asin: asin.asin,
                size: asin.size,
                quantity: String(asin.quantity || 1)
            }))
        };
        
        console.log('📤 Sending data to frontend:', messageData);
        
        // Send message to the React app
        window.postMessage(messageData, '*');
        
        showFormStatus(`✅ Successfully sent ${formData.asins.length} ASINs to the form!`, 'success');
        
        // Send confirmation to popup
        try {
            chrome.runtime.sendMessage({ 
                action: 'formFilled', 
                fieldsFilled: formData.asins.length 
            });
        } catch (e) {
            console.log('Could not send message to popup:', e);
        }
        
    } catch (error) {
        console.error('❌ Error filling form:', error);
        showFormStatus('Error filling form. Please fill manually.', 'error');
    }
}

// Show status message on the page
function showFormStatus(message, type) {
    console.log(`📢 Form status: ${message} (${type})`);
    
    // Remove existing status
    const existingStatus = document.getElementById('asin-extractor-status');
    if (existingStatus) {
        existingStatus.remove();
    }
    
    // Create status element
    const status = document.createElement('div');
    status.id = 'asin-extractor-status';
    status.textContent = message;
    status.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px 25px;
        border-radius: 8px;
        font-weight: bold;
        font-size: 14px;
        z-index: 100000;
        max-width: 400px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        animation: slideIn 0.3s ease-out;
        ${type === 'success' ? 
            'background: #d4edda; color: #155724; border: 2px solid #c3e6cb;' : 
            'background: #f8d7da; color: #721c24; border: 2px solid #f5c6cb;'
        }
    `;
    
    document.body.appendChild(status);
    
    // Auto-remove after 6 seconds
    setTimeout(() => {
        if (status && status.parentNode) {
            status.style.animation = 'slideOut 0.3s ease-in';
            setTimeout(() => status.remove(), 300);
        }
    }, 6000);
}

// Add helper buttons for manual operations
function addHelperButtons() {
    // Remove existing buttons
    const existingFillBtn = document.getElementById('asin-extractor-fill-btn');
    const existingClearBtn = document.getElementById('asin-extractor-clear-btn');
    if (existingFillBtn) existingFillBtn.remove();
    if (existingClearBtn) existingClearBtn.remove();
    
    // Create fill button container
    const fillButton = document.createElement('button');
    fillButton.id = 'asin-extractor-fill-btn';
    fillButton.className = 'asin-ext-btn';
    fillButton.innerHTML = `
        <span class="asin-ext-icon">📝</span>
        <span class="asin-ext-text">Fill Form</span>
    `;
    
    fillButton.addEventListener('click', () => {
        initializeFormFiller();
    });
    
    // Create clear button container
    const clearButton = document.createElement('button');
    clearButton.id = 'asin-extractor-clear-btn';
    clearButton.className = 'asin-ext-btn asin-ext-clear';
    clearButton.innerHTML = `
        <span class="asin-ext-icon">✕</span>
        <span class="asin-ext-text">Clear Data</span>
    `;
    
    clearButton.addEventListener('click', async () => {
        if (confirm('Are you sure you want to clear all stored ASIN data?')) {
            await chrome.storage.local.remove(['extensionData', 'formData']);
            showFormStatus('✅ All data cleared!', 'success');
            
            try {
                chrome.runtime.sendMessage({ action: 'dataCleared' });
            } catch (e) {
                console.log('Could not send clear message to popup:', e);
            }
        }
    });
    
    document.body.appendChild(fillButton);
    document.body.appendChild(clearButton);
}

// Add CSS animations and styles
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
    
    /* Extension helper buttons */
    .asin-ext-btn {
        position: fixed;
        right: 16px;
        width: 36px;
        height: 36px;
        padding: 0;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 18px;
        cursor: pointer;
        z-index: 99999;
        box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
        transition: all 0.35s cubic-bezier(0.68, -0.55, 0.265, 1.55);
        display: flex;
        align-items: center;
        justify-content: flex-start;
        overflow: hidden;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        font-weight: 600;
        font-size: 13px;
        white-space: nowrap;
        backdrop-filter: blur(10px);
    }
    
    #asin-extractor-fill-btn {
        bottom: 100px;
    }
    
    #asin-extractor-clear-btn {
        bottom: 52px;
    }
    
    .asin-ext-btn.asin-ext-clear {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        box-shadow: 0 2px 8px rgba(245, 87, 108, 0.3);
    }
    
    .asin-ext-icon {
        width: 36px;
        height: 36px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 16px;
        flex-shrink: 0;
        transition: transform 0.3s ease;
    }
    
    .asin-ext-text {
        opacity: 0;
        margin-left: -8px;
        margin-right: 12px;
        transition: all 0.3s ease;
        transform: translateX(-8px);
        letter-spacing: 0.3px;
    }
    
    .asin-ext-btn:hover {
        width: 130px;
        box-shadow: 0 4px 16px rgba(102, 126, 234, 0.5);
        transform: translateX(-4px);
    }
    
    .asin-ext-btn.asin-ext-clear:hover {
        box-shadow: 0 4px 16px rgba(245, 87, 108, 0.5);
    }
    
    .asin-ext-btn:hover .asin-ext-icon {
        transform: scale(1.15) rotate(5deg);
    }
    
    .asin-ext-btn:hover .asin-ext-text {
        opacity: 1;
        margin-left: 0;
        transform: translateX(0);
    }
    
    .asin-ext-btn:active {
        transform: translateX(-4px) scale(0.96);
    }
    
    @media (prefers-reduced-motion: reduce) {
        .asin-ext-btn {
            transition: all 0.2s ease;
        }
        .asin-ext-btn:hover .asin-ext-icon {
            transform: scale(1.1);
        }
    }
`;
document.head.appendChild(style);

// Initialize when page loads
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        setTimeout(initializeFormFiller, 1000);
        setTimeout(addHelperButtons, 2000);
    });
} else {
    setTimeout(initializeFormFiller, 1000);
    setTimeout(addHelperButtons, 2000);
}

// Listen for messages from the popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'fillForm') {
        console.log('📨 Received fillForm message from popup');
        initializeFormFiller();
        sendResponse({ success: true });
    } else if (request.action === 'checkPage') {
        const isLeadSubmittalPage = window.location.pathname.includes('lead-submittal');
        sendResponse({ isLeadSubmittalPage });
    }
    return true;
});

console.log('✅ Frontend filler content script loaded');

