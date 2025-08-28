// Background script for Smart Notes Capture

// Import configuration from config.js
importScripts('../config.js');

// Log what we have
console.log('Background: Config embedded');
console.log('Background: TOKEN present:', !!NOTION_CONFIG.TOKEN);
console.log('Background: DATABASE_ID present:', !!NOTION_CONFIG.DATABASE_ID);

// Background-specific API Client functionality (renamed to avoid conflict)
const backgroundApiClient = {
  async getAuthToken() {
    try {
      const result = await chrome.storage.local.get(['authToken']);
      return result.authToken || null;
    } catch (error) {
      console.error('Error getting auth token:', error);
      return null;
    }
  },

  async post(endpoint, data) {
    try {
      const token = await this.getAuthToken();
      const url = `${API_CONFIG.BASE_URL}${endpoint}`;
      
      console.log('Background: Making API request to:', url);

      // Prepare headers
      const headers = {
        'Content-Type': 'application/json',
        ...(token && { 'Authorization': `Bearer ${token}` }),
      };

      // Add Notion headers if available
      if (endpoint === API_CONFIG.ENDPOINTS.NOTES && NOTION_CONFIG.TOKEN && NOTION_CONFIG.DATABASE_ID) {
        headers['X-Notion-Token'] = NOTION_CONFIG.TOKEN;
        headers['X-Notion-Database-Id'] = NOTION_CONFIG.DATABASE_ID;
        console.log('Background: Adding Notion integration headers');
      }

      const response = await fetch(url, {
        method: 'POST',
        headers: headers,
        body: JSON.stringify(data)
      });

      const result = await response.json();
      
      if (!response.ok) {
        throw new Error(result.detail || `HTTP ${response.status}: ${response.statusText}`);
      }

      return { success: true, data: result };

    } catch (error) {
      console.error('Background: API request failed:', error);
      return { 
        success: false, 
        error: error.message || 'Network request failed',
        isNetworkError: error.name === 'TypeError' || error.message.includes('fetch')
      };
    }
  }
};

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
  console.log('Background: Received message:', message.action);
  
  if (message.action === 'saveNote') {
    saveNote(message.note)
      .then((result) => {
        console.log('Background: Save result:', result);
        sendResponse({
          success: true,
          method: result.method,
          message: result.message,
          noteId: result.noteId,
          syncStatus: result.syncStatus,
          notionPageId: result.notionPageId
        });
      })
      .catch((error) => {
        console.error('Background: Error saving note:', error);
        sendResponse({ 
          success: false, 
          error: error.message,
          method: 'failed'
        });
      });
    
    return true; // Keep channel open for async response
  }
  
  if (message.action === 'categorizeContent') {
    handleCategorizeContent(message.data)
      .then(result => sendResponse(result))
      .catch(error => sendResponse({ success: false, error: error.message }));
    
    return true; // Keep channel open for async response
  }
  
  if (message.action === 'warmCache') {
    handleWarmCache()
      .then(result => sendResponse(result))
      .catch(error => sendResponse({ success: false, error: error.message }));
    
    return true; // Keep channel open for async response
  }
  
  if (message.action === 'updateNoteWithAI') {
    updateNoteWithAI(message.noteId, message.updatedNote)
      .then(result => sendResponse(result))
      .catch(error => sendResponse({ success: false, error: error.message }));
    
    return true; // Keep channel open for async response
  }
});

// Save note with AI processing first, then API integration
async function saveNote(note) {
  console.log('Background: Attempting to save note with AI processing:', note);
  
  try {
    let finalNote = note;
    
    // If note needs AI processing, do it first BEFORE any API calls
    if (note.needsAI) {
      console.log('Background: 🤖 Processing note with AI first (BLOCKING API save until complete)...');
      
      try {
        const aiResult = await handleCategorizeContent({
          content: note.text,
          comment: note.comment || ''
        });
        
        if (aiResult && aiResult.success && aiResult.data) {
          const { title: aiTitle, category: aiCategory } = aiResult.data;
          
          console.log('Background: ✅ AI processing successful');
          console.log('Background: Full AI Response:', aiResult);
          console.log('Background: AI Response Data:', aiResult.data);
          console.log('Background: Extracted aiTitle:', aiTitle);
          console.log('Background: Extracted aiCategory:', aiCategory);
          console.log('Background: Original note title:', note.title);
          
          // Update note with AI improvements
          finalNote = {
            ...note,
            title: aiTitle || note.title,
            category: aiCategory || note.category,
            aiProcessed: true,
            needsAI: false
          };
          
          console.log('Background: Final note title after AI processing:', finalNote.title);
          console.log('Background: AI processing complete, enhanced note:', finalNote);
        } else {
          console.warn('Background: ❌ AI processing failed, using original note');
          console.warn('Background: AI Result:', aiResult);
          console.warn('Background: AI Success:', aiResult?.success);
          console.warn('Background: AI Data:', aiResult?.data);
          console.warn('Background: AI Error:', aiResult?.error);
        }
      } catch (aiError) {
        console.error('Background: ❌ AI processing exception, using original note:', aiError);
        console.error('Background: Error details:', aiError.message);
        console.error('Background: Stack:', aiError.stack);
      }
    }
    
    // Now save the final note (with or without AI improvements) to API
    const apiResult = await saveNoteToAPI(finalNote);
    
    if (apiResult.success) {
      console.log('Background: Note saved to API successfully');
      
      // Save to local storage as backup
      await saveNoteToLocalStorage(finalNote, { 
        ...finalNote, 
        syncStatus: 'synced',
        apiNoteId: apiResult.data?.data?.note_id 
      });
      
      // Check if Notion sync was successful
      const syncStatus = apiResult.data?.data?.sync_status || 'unknown';
      const notionPageId = apiResult.data?.data?.notion_page_id;
      
      let message = 'Note saved to API successfully';
      if (syncStatus === 'notion_synced') {
        message = 'Note saved and synced to Notion!';
      } else if (syncStatus === 'notion_pending') {
        message = 'Note saved, syncing to Notion in background...';
      } else if (syncStatus === 'notion_failed') {
        message = 'Note saved locally, Notion sync failed';
      }
      
      return { 
        success: true, 
        method: 'api',
        noteId: apiResult.data?.data?.note_id,
        syncStatus: syncStatus,
        notionPageId: notionPageId,
        message: message
      };
    } else {
      console.log('Background: API save failed, falling back to local storage');
      
      // Fallback to local storage
      await saveNoteToLocalStorage(finalNote, { 
        ...finalNote, 
        syncStatus: 'pending',
        lastError: apiResult.error 
      });
      
      return { 
        success: true, 
        method: 'local',
        message: `Saved locally (API unavailable: ${apiResult.error})`
      };
    }
  } catch (error) {
    console.error('Background: Error in saveNote:', error);
    
    // Last resort: try local storage
    try {
      await saveNoteToLocalStorage(note, { 
        ...note, 
        syncStatus: 'failed',
        lastError: error.message 
      });
      
      return { 
        success: true, 
        method: 'local',
        message: `Saved locally (Error: ${error.message})`
      };
    } catch (localError) {
      console.error('Background: Local storage also failed:', localError);
      throw new Error(`Failed to save note: ${localError.message}`);
    }
  }
}

// Save note to API
async function saveNoteToAPI(note) {
  try {
    // Transform note to API format
    const apiNote = {
      text: note.text,
      comment: note.comment || '',
      url: note.url,
      title: note.title,
      category: note.category || 'General',
      timestamp: note.timestamp
    };
    
    console.log('Background: 📤 Sending to API:', apiNote);
    console.log('Background: 📤 Note title being sent:', apiNote.title);
    console.log('Background: 📤 Note category being sent:', apiNote.category);
    console.log('Background: Using Notion config:', NOTION_CONFIG.TOKEN ? 'Token present' : 'No token', NOTION_CONFIG.DATABASE_ID ? 'DB ID present' : 'No DB ID');
    
    return await backgroundApiClient.post(API_CONFIG.ENDPOINTS.NOTES, apiNote);
  } catch (error) {
    console.error('Background: API save error:', error);
    return { success: false, error: error.message };
  }
}

// Save note to local storage
async function saveNoteToLocalStorage(originalNote, enhancedNote = null) {
  try {
    const noteToSave = enhancedNote || originalNote;
    
    // Get existing notes
    const result = await chrome.storage.local.get(['notes']);
    const notes = result.notes || [];
    
    // Add new note to the beginning of the array
    notes.unshift(noteToSave);
    
    // Save back to storage
    await chrome.storage.local.set({ notes: notes });
    
    console.log('Background: Note saved to local storage:', noteToSave);
  } catch (error) {
    console.error('Background: Error saving to local storage:', error);
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

// Handle AI categorization requests (bypasses CORS)
async function handleCategorizeContent(requestData) {
  try {
    console.log('Background: Making categorization request');
    
    const response = await fetch(API_CONFIG.BASE_URL + '/api/notes/categorize', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Notion-Token': NOTION_CONFIG.TOKEN,
        'X-Notion-Database-Id': NOTION_CONFIG.DATABASE_ID
      },
      body: JSON.stringify(requestData)
    });
    
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`API returned ${response.status}: ${response.statusText} - ${errorText}`);
    }
    
    const result = await response.json();
    console.log('Background: AI categorization successful');
    console.log('Background: Full AI response:', result);
    return result;
    
  } catch (error) {
    console.error('Background: AI categorization failed:', error);
    throw error;
  }
}

// Handle cache warming requests (bypasses CORS)
async function handleWarmCache() {
  try {
    console.log('Background: Making cache warm request');
    
    const response = await fetch(API_CONFIG.BASE_URL + '/api/notes/warm-cache', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Notion-Token': NOTION_CONFIG.TOKEN,
        'X-Notion-Database-Id': NOTION_CONFIG.DATABASE_ID
      }
    });
    
    if (!response.ok) {
      throw new Error(`Cache warm failed: ${response.status}`);
    }
    
    const result = await response.json();
    console.log('Background: Cache warming successful');
    return result;
    
  } catch (error) {
    console.error('Background: Cache warming failed:', error);
    throw error;
  }
}

// Update a saved note with AI-generated improvements
async function updateNoteWithAI(noteId, updatedNote) {
  try {
    console.log('Background: Updating note with AI improvements', noteId);
    
    // Update in local storage
    const result = await chrome.storage.local.get(['notes']);
    const notes = result.notes || [];
    
    const noteIndex = notes.findIndex(note => note.id === noteId);
    if (noteIndex !== -1) {
      notes[noteIndex] = { ...notes[noteIndex], ...updatedNote };
      await chrome.storage.local.set({ notes: notes });
      console.log('Background: Note updated in local storage');
    }
    
    // Update the note in Notion with AI improvements
    const apiNote = {
      text: updatedNote.text,
      comment: updatedNote.comment || '',
      url: updatedNote.url,
      title: updatedNote.title,  // This will be the AI title
      category: updatedNote.category,
      timestamp: updatedNote.timestamp,

    };
    
    console.log('Background: Updating note in Notion with AI improvements:', apiNote);
    
    // Make API request to update the note
    const response = await fetch(`${API_CONFIG.BASE_URL}/api/notes/${noteId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'X-Notion-Token': NOTION_CONFIG.TOKEN,
        'X-Notion-Database-Id': NOTION_CONFIG.DATABASE_ID
      },
      body: JSON.stringify(apiNote)
    });
    
    if (!response.ok) {
      throw new Error(`Failed to update note in API: ${response.status}`);
    }
    
    const apiResult = await response.json();
    console.log('Background: Note updated in API:', apiResult);
    
    return { 
      success: true, 
      method: 'api_updated',
      syncStatus: apiResult.data?.sync_status || 'updated',
      notionPageId: apiResult.data?.notion_page_id
    };
    
  } catch (error) {
    console.error('Background: Failed to update note with AI:', error);
    throw error;
  }
}