// Background script for Smart Notes Capture

// Create context menu item when extension installs
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: 'add-to-notes',
    title: 'Add to Notes',
    contexts: ['selection']
  });
});

// Handle context menu clicks
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId === 'add-to-notes') {
    try {
      // Get selected text from content script with retry logic
      const response = await sendMessageWithRetry(tab.id, { action: 'getSelectedText' }, 3);
      
      if (response && response.text) {
        console.log('Got selected text:', response.text);
        
        // Show modal with selected text
        await sendMessageWithRetry(tab.id, {
          action: 'showModal',
          data: {
            text: response.text,
            url: response.url,
            title: response.title
          }
        }, 3);
        
        console.log('Modal should be showing now');
      } else {
        console.warn('No text selected or content script not responding');
        
        // Fallback: use the selection from info object if available
        if (info.selectionText) {
          await sendMessageWithRetry(tab.id, {
            action: 'showModal',
            data: {
              text: info.selectionText,
              url: tab.url,
              title: tab.title
            }
          }, 3);
        }
      }
    } catch (error) {
      console.error('Error handling context menu click:', error);
    }
  }
});

// Helper function to send messages with retry logic
async function sendMessageWithRetry(tabId, message, maxRetries = 3) {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      const response = await new Promise((resolve, reject) => {
        chrome.tabs.sendMessage(tabId, message, (response) => {
          if (chrome.runtime.lastError) {
            reject(new Error(chrome.runtime.lastError.message));
          } else {
            resolve(response);
          }
        });
      });
      
      return response;
    } catch (error) {
      console.warn(`Message send attempt ${attempt} failed:`, error.message);
      
      if (attempt === maxRetries) {
        throw error;
      }
      
      // Wait before retrying (exponential backoff)
      await new Promise(resolve => setTimeout(resolve, 100 * attempt));
    }
  }
}

// Handle messages from content script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'saveNote') {
    saveNote(message.note)
      .then(() => sendResponse({ success: true }))
      .catch((error) => {
        console.error('Error saving note:', error);
        sendResponse({ success: false, error: error.message });
      });
    
    // Return true to indicate we'll send a response asynchronously
    return true;
  }
});

// Save note to storage
async function saveNote(note) {
  try {
    // Get existing notes
    const result = await chrome.storage.local.get(['notes']);
    const notes = result.notes || [];
    
    // Add new note to the beginning of the array
    notes.unshift(note);
    
    // Save back to storage
    await chrome.storage.local.set({ notes: notes });
    
    console.log('Note saved:', note);
  } catch (error) {
    console.error('Error saving note:', error);
    throw error;
  }
}

// Get all notes
async function getAllNotes() {
  try {
    const result = await chrome.storage.local.get(['notes']);
    return result.notes || [];
  } catch (error) {
    console.error('Error getting notes:', error);
    throw error;
  }
}