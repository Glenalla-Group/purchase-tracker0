// Background script for the Chrome extension

// Handle extension installation
chrome.runtime.onInstalled.addListener(() => {
  console.log('Amazon ASIN Extractor extension installed');
});

// Handle messages from content scripts
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'openPopup') {
    // This would ideally open the popup, but Chrome doesn't allow this
    // Instead, we can show a notification or badge
    chrome.action.setBadgeText({ text: '!' });
    chrome.action.setBadgeBackgroundColor({ color: '#ff9500' });
    
    // Clear badge after 3 seconds
    setTimeout(() => {
      chrome.action.setBadgeText({ text: '' });
    }, 3000);
  }
});

// Handle tab updates to reset badge
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && tab.url) {
    if (tab.url.includes('amazon.com') && tab.url.includes('/dp/')) {
      // Set badge to indicate extension is active
      chrome.action.setBadgeText({ tabId: tabId, text: '●' });
      chrome.action.setBadgeBackgroundColor({ color: '#4CAF50' });
    } else {
      // Clear badge on non-Amazon pages
      chrome.action.setBadgeText({ tabId: tabId, text: '' });
    }
  }
});