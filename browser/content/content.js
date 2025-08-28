// Content script for Smart Notes Capture
let selectedText = '';

// Ensure content script is ready
console.log('Smart Notes content script loaded on:', window.location.href);

// Check if we're in a frame/iframe and skip injection there
if (window.self !== window.top) {
  console.log('Smart Notes: Skipping injection in iframe/frame');
} else {
  console.log('Smart Notes: Initializing in main frame');
}

// Listen for text selection
document.addEventListener('mouseup', () => {
  const selection = window.getSelection();
  selectedText = selection.toString().trim();
  
  if (selectedText.length > 0) {
    console.log('Text selected:', selectedText);
  }
});

// Also listen for selection change events
document.addEventListener('selectionchange', () => {
  const selection = window.getSelection();
  const newSelectedText = selection.toString().trim();
  
  if (newSelectedText !== selectedText) {
    selectedText = newSelectedText;
    if (selectedText.length > 0) {
      console.log('Selection changed to:', selectedText);
    }
  }
});

// Listen for messages from background script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  console.log('Content script received message:', message);
  
  try {
    if (message.action === 'getSelectedText') {
      // Get fresh selection in case the stored one is stale
      const currentSelection = window.getSelection().toString().trim();
      const textToSend = currentSelection || selectedText;
      
      const response = {
        text: textToSend,
        url: window.location.href,
        title: document.title
      };
      
      console.log('Sending selected text response:', response);
      sendResponse(response);
      
    } else if (message.action === 'showModal') {
      console.log('Showing modal with data:', message.data);
      showCaptureModal(message.data);
      sendResponse({ success: true });
    }
  } catch (error) {
    console.error('Error in content script message handler:', error);
    sendResponse({ error: error.message });
  }
  
  // Return true to indicate we might send a response asynchronously
  return true;
});

// Show the capture modal
function showCaptureModal(data) {
  console.log('showCaptureModal called with data:', data);
  
  // Validate data
  if (!data || !data.text) {
    console.error('No text data provided to modal');
    showNotification('No text selected', 'error');
    return;
  }

  // Skip if we're in an iframe
  if (window.self !== window.top) {
    console.log('Smart Notes: Skipping modal in iframe');
    return;
  }
  
  // Check if document.body is available
  if (!document.body) {
    console.error('Document body not available for modal injection');
    showNotification('Page not ready for notes capture', 'error');
    return;
  }
  
  // Remove existing tooltip if any
  const existingModal = document.getElementById('smart-notes-modal');
  if (existingModal) {
    console.log('Removing existing tooltip');
    existingModal.remove();
  }

  // Get selection position for tooltip placement
  const selection = window.getSelection();
  let rect = null;
  if (selection.rangeCount > 0) {
    rect = selection.getRangeAt(0).getBoundingClientRect();
  }

  // Create floating tooltip
  const modal = document.createElement('div');
  modal.id = 'smart-notes-modal';
  modal.className = 'smart-notes-floating-tooltip';
  
  modal.innerHTML = `
    <div class="smart-notes-tooltip-content">
      <div class="smart-notes-input-row">
        <textarea id="smart-notes-comment" 
                 placeholder="💬 Add comment (optional)... Press Enter to save!" 
                 rows="1"></textarea>
        <button id="smart-notes-save" class="smart-notes-save-btn" title="Save Note">
          <span class="save-icon">💾</span>
          <span class="save-text">Save</span>
        </button>
        <button class="smart-notes-close" title="Close">&times;</button>
      </div>
      <div class="smart-notes-ai-hint">
        🤖 AI will categorize automatically
      </div>
    </div>
  `;

  // Position tooltip near selection or center of viewport
  const scrollX = window.pageXOffset || document.documentElement.scrollLeft;
  const scrollY = window.pageYOffset || document.documentElement.scrollTop;
  
  let top, left;
  
  if (rect && rect.width > 0 && rect.height > 0) {
    // Position below the selection with some margin
    top = rect.bottom + scrollY + 10;
    left = Math.max(10, Math.min(rect.left + scrollX, window.innerWidth - 320));
  } else {
    // Fallback: center of current viewport
    top = scrollY + (window.innerHeight / 2) - 50;
    left = scrollX + (window.innerWidth / 2) - 150;
  }
  
  modal.style.position = 'absolute';
  modal.style.top = `${top}px`;
  modal.style.left = `${left}px`;
  modal.style.zIndex = '2147483647';

  try {
    document.body.appendChild(modal);
    console.log('Modal appended to body');

    // Use a small delay to ensure DOM is fully updated
    setTimeout(() => {
      try {
        // Add event listeners with error handling
        const closeBtn = modal.querySelector('.smart-notes-close');
        const saveBtn = modal.querySelector('.smart-notes-save-btn') || modal.querySelector('#smart-notes-save');
        const commentArea = modal.querySelector('#smart-notes-comment');
        
        if (closeBtn) {
          closeBtn.addEventListener('click', closeModal);
        } else {
          console.warn('Close button not found');
        }
        
        if (saveBtn) {
          saveBtn.addEventListener('click', () => saveNote(data));
        } else {
          console.warn('Save button not found');
        }
        
        // No click-outside-to-close for floating tooltip (too easy to accidentally trigger)

        // Focus on comment textarea and add Enter key handler
        if (commentArea) {
          setTimeout(() => {
            try {
              commentArea.focus();
            } catch (focusError) {
              console.warn('Could not focus comment area:', focusError);
            }
          }, 100);
          
          // Handle keyboard shortcuts: Enter to save, Escape to cancel
          commentArea.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              saveNote(data);
            }
            if (e.key === 'Escape') {
              closeModal();
            }
          });
        } else {
          console.warn('Comment textarea not found');
        }
        
        console.log('Modal setup complete');
        
        // Just warm cache in background (no AI suggestions blocking the UI)
        warmCache();
        
      } catch (setupError) {
        console.error('Error setting up modal event listeners:', setupError);
        showNotification('Modal setup failed, but modal is visible', 'error');
      }
    }, 50);
    
  } catch (error) {
    console.error('Error setting up modal:', error);
    showNotification('Failed to show capture modal', 'error');
  }
}

function closeModal() {
  const modal = document.getElementById('smart-notes-modal');
  if (modal) {
    modal.remove();
  }
}

// 🚀 BACKGROUND AI PROCESSING
async function processNoteWithAI(note, savedNoteId = null) {
  /**
   * Process a saved note with AI in the background (non-blocking)
   * This improves the note with AI-generated title and category
   */
  try {
    console.log('🤖 Background AI: Processing note', note.id);
    
    // Prepare request data for AI categorization
    const requestData = {
      content: note.text,
      comment: note.comment,
      // Don't send existing_categories - let API fetch from Notion
    };
    
    // Use background script to get AI suggestions
    const result = await chrome.runtime.sendMessage({
      action: 'categorizeContent',
      data: requestData
    });
    
    if (result && result.success && result.data) {
      const { title: aiTitle, category: aiCategory, confidence, is_new } = result.data;
      
      console.log('🤖 Background AI: Got suggestions', { aiTitle, aiCategory, confidence });
      
      // Update the note with AI suggestions
      const updatedNote = {
        ...note,
        title: aiTitle, // Always use AI title

        category: note.category === 'General' ? aiCategory : note.category, // Only replace default category
        aiProcessed: true,
        aiConfidence: confidence,

        aiSuggestions: {
          originalTitle: note.title,
          originalCategory: note.category,
          aiTitle: aiTitle,
          aiCategory: aiCategory,
          isNewCategory: is_new
        }
      };
      
      // Save the updated note (this will sync to Notion with better data)
      chrome.runtime.sendMessage({
        action: 'updateNoteWithAI',
        noteId: savedNoteId || note.id,
        updatedNote: updatedNote
      }, (updateResponse) => {
        if (updateResponse && updateResponse.success) {
          console.log('🤖 Background AI: Note updated successfully');
          showNotification(`✨ AI improved your note: "${aiTitle}" → ${aiCategory}`, 'success');
        } else {
          console.warn('🤖 Background AI: Failed to update note:', updateResponse?.error);
        }
      });
      
    } else {
      console.warn('🤖 Background AI: Failed to get suggestions:', result?.error);
      // Don't show error to user - this is background processing
    }
    
  } catch (error) {
    console.error('🤖 Background AI: Processing failed:', error);
    // Don't show error to user - this is background processing
  }
}

async function getAISuggestions(data) {
  const titleInput = document.getElementById('smart-notes-title');
  const categoryInput = document.getElementById('smart-notes-category');
  const loadingIndicator = document.getElementById('smart-notes-ai-loading');
  
  if (!titleInput || !categoryInput || !loadingIndicator) {
    console.warn('AI suggestion elements not found');
    return;
  }
  
  try {
    console.log('Getting AI suggestions for:', data.text.substring(0, 100) + '...');
    
    // Show loading state
    loadingIndicator.style.display = 'flex';
    
    // Prepare request data
    const requestData = {
      content: data.text,
      comment: '', // No comment yet since user hasn't typed it
      // Don't send existing_categories - let API fetch from Notion
    };
    
    // Use background script to make API call (bypasses CORS)
    console.log('🚀 Sending categorization request to background script');
    console.log('📦 Request data:', requestData);
    
    const result = await chrome.runtime.sendMessage({
      action: 'categorizeContent',
      data: requestData
    });
    
    console.log('📡 Background script response:', result);
    
    if (!result || !result.success) {
      throw new Error(result?.error || 'Background script request failed');
    }
    console.log('AI suggestions received:', result);
    
    if (result.success && result.data) {
      const { title, category, confidence, is_new } = result.data;
      
      // Update title field
      if (title) {
        titleInput.value = title;
        titleInput.disabled = false;
        titleInput.placeholder = 'Edit title if needed...';
      }
      
      // Update category field
      if (category) {
        categoryInput.value = category;
        categoryInput.disabled = false;
        categoryInput.placeholder = 'Edit category if needed...';
        
        // Update AI indicator to show if it's a new category
        const categoryIndicator = categoryInput.parentNode.querySelector('.smart-notes-ai-indicator');
        if (categoryIndicator) {
          if (is_new) {
            categoryIndicator.textContent = '✨ New category suggested';
            categoryIndicator.style.color = '#28a745'; // Green for new
          } else {
            categoryIndicator.textContent = '✨ Existing category matched';
            categoryIndicator.style.color = '#007bff'; // Blue for existing
          }
        }
      }
      
      // Show confidence in console
      console.log(`AI confidence: ${confidence}, New category: ${is_new}`);
      
      // Hide loading indicator
      loadingIndicator.style.display = 'none';
      
      // Show success briefly
      showNotification(`✨ AI suggestions ready (${Math.round(confidence * 100)}% confidence)`, 'info');
      
    } else {
      throw new Error(result.message || 'No suggestions received');
    }
    
  } catch (error) {
    console.error('Failed to get AI suggestions:', error);
    
    // CRITICAL: Hide loading indicator and clear placeholders
    loadingIndicator.style.display = 'none';
    
    // Fallback to basic categorization
    const fallbackCategory = suggestCategory(data.url);
    const fallbackTitle = data.text.split(/\s+/).slice(0, 4).join(' ') || 'Saved Content';
    
    // Update title field completely
    titleInput.value = fallbackTitle;
    titleInput.disabled = false;
    titleInput.placeholder = 'Edit title if needed...';
    
    // Update category field completely (CLEAR the "Analyzing content..." placeholder)
    categoryInput.value = fallbackCategory;
    categoryInput.disabled = false;
    categoryInput.placeholder = 'Edit category if needed...';
    
    // Update indicators to show fallback mode
    const titleIndicator = titleInput.parentNode.querySelector('.smart-notes-ai-indicator');
    const categoryIndicator = categoryInput.parentNode.querySelector('.smart-notes-ai-indicator');
    
    if (titleIndicator) {
      titleIndicator.textContent = '📝 Basic suggestion';
      titleIndicator.style.color = '#666';
    }
    if (categoryIndicator) {
      categoryIndicator.textContent = '📝 URL-based suggestion';
      categoryIndicator.style.color = '#666';
    }
    
    // Show more detailed error information
    console.log('AI Error details:', error);
    showNotification('AI unavailable - using basic suggestions', 'info');
  }
}



async function warmCacheAndGetSuggestions(data) {
  /**
   * OPTIMIZATION: Warm cache first (if needed), then get AI suggestions
   * This reduces latency for subsequent requests
   */
  try {
    console.log('Starting optimized categorization with cache warming...');
    
    // **Step 1: Try to warm cache in parallel with AI suggestions** 
    const warmCachePromise = warmCache();
    const aiSuggestionsPromise = getAISuggestions(data);
    
    // Run both in parallel - cache warming is fire-and-forget
    await Promise.allSettled([warmCachePromise, aiSuggestionsPromise]);
    
  } catch (error) {
    console.error('Optimized categorization failed:', error);
    // Fallback to just AI suggestions
    await getAISuggestions(data);
  }
}

async function warmCache() {
  /**
   * Warm the category cache for faster subsequent requests
   * This is a fire-and-forget operation that improves performance
   */
  try {
    const result = await chrome.runtime.sendMessage({
      action: 'warmCache'
    });
    
    if (result && result.success) {
      console.log('✅ Category cache warmed successfully');
    } else {
      console.log('⚠️ Cache warming failed, but continuing...');
    }
  } catch (error) {
    console.log('⚠️ Cache warming failed (network issue), but continuing...');
    // Don't throw - this is optional optimization
  }
}

function saveNote(data) {
  const comment = document.getElementById('smart-notes-comment').value.trim();
  const saveBtn = document.querySelector('.smart-notes-save-btn') || document.getElementById('smart-notes-save');

  // Disable button briefly to prevent double-clicks
  if (saveBtn) {
    saveBtn.disabled = true;
  }

  const note = {
    id: generateId(),
    text: data.text,
    comment: comment,
    url: data.url,
    title: data.title || 'Saved Content', // Use webpage title or fallback

    timestamp: new Date().toISOString(),
    category: 'General', // Temporary category until AI processes
    aiProcessed: false, // Will be updated when background AI processing completes
    needsAI: true, // Always need AI since no user inputs
    titleSource: data.title ? 'webpage' : 'fallback' // Track title source
  };

  console.log('Content: Saving note:', note);

  // INSTANT FEEDBACK: Close tooltip and show notification immediately
  showNotification('📝 Captured!', 'success');
  closeModal();

  // Send to background script for storage (happens async)
  chrome.runtime.sendMessage({
    action: 'saveNote',
    note: note
  }, (response) => {
    console.log('Content: Save response:', response);
    
    if (response && response.success) {
      console.log('Content: Note saved successfully via:', response.method);
      console.log('Content: Sync status:', response.syncStatus);
      
      // Log Notion page ID if available
      if (response.notionPageId) {
        console.log('Content: Notion page created:', response.notionPageId);
      }
    } else {
      console.error('Content: Failed to save note:', response?.error);
      // Show error notification if save actually failed
      showNotification('❌ Save failed - will retry', 'error');
    }
  });
}

// Show notification messages to user
function showNotification(message, type = 'info') {
  try {
    // Remove any existing notifications first (only one at a time)
    const existingNotifications = document.querySelectorAll('.smart-notes-notification');
    existingNotifications.forEach(notif => {
      if (notif.parentNode) {
        notif.parentNode.removeChild(notif);
      }
    });
    
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `smart-notes-notification ${type}`;
    notification.textContent = message;
    
    // Ensure body exists before appending
    if (document.body) {
      document.body.appendChild(notification);
    } else {
      console.warn('Document body not available for notification');
      return;
    }

    // Auto-remove after 2 seconds (faster)
    setTimeout(() => {
      if (notification.parentNode) {
        notification.classList.add('slide-out');
        setTimeout(() => {
          if (notification.parentNode) {
            notification.parentNode.removeChild(notification);
          }
        }, 200);
      }
    }, 2000);
  } catch (error) {
    console.error('Error showing notification:', error);
    // Fallback to console log if notification fails
    console.log(`Smart Notes: ${message}`);
  }
}

function generateId() {
  return Date.now().toString() + Math.random().toString(36).substr(2, 9);
}

function suggestCategory(url) {
  const categoryMap = {
    // Development
    'github.com': 'Development',
    'gitlab.com': 'Development',
    'bitbucket.org': 'Development',
    'stackoverflow.com': 'Development',
    'stackexchange.com': 'Development',
    'codepen.io': 'Development',
    'jsfiddle.net': 'Development',
    'replit.com': 'Development',
    'codesandbox.io': 'Development',
    
    // Articles & Blogs
    'medium.com': 'Articles',
    'dev.to': 'Articles',
    'hashnode.com': 'Articles',
    'substack.com': 'Articles',
    'blogger.com': 'Articles',
    'wordpress.com': 'Articles',
    
    // Tech News
    'news.ycombinator.com': 'Tech News',
    'techcrunch.com': 'Tech News',
    'arstechnica.com': 'Tech News',
    'theverge.com': 'Tech News',
    'wired.com': 'Tech News',
    'engadget.com': 'Tech News',
    
    // Professional
    'linkedin.com': 'Professional',
    'glassdoor.com': 'Professional',
    'indeed.com': 'Professional',
    'monster.com': 'Professional',
    
    // Social & Discussion  
    'reddit.com': 'Discussion',
    'twitter.com': 'Discussion',
    'x.com': 'Discussion',
    'discord.com': 'Discussion',
    'slack.com': 'Discussion',
    
    // Reference & Learning
    'wikipedia.org': 'Reference',
    'mdn.mozilla.org': 'Reference',
    'w3schools.com': 'Reference',
    'coursera.org': 'Learning',
    'udemy.com': 'Learning',
    'khanacademy.org': 'Learning',
    'edx.org': 'Learning',
    
    // Documentation
    'docs.google.com': 'Documents',
    'notion.so': 'Documents',
    'confluence.atlassian.com': 'Documents',
    
    // Shopping & Commerce
    'amazon.com': 'Shopping',
    'ebay.com': 'Shopping',
    'etsy.com': 'Shopping',
    'shopify.com': 'Shopping',
    
    // News & Media
    'cnn.com': 'News',
    'bbc.com': 'News',
    'nytimes.com': 'News',
    'reuters.com': 'News',
    'npr.org': 'News',
    
    // Entertainment
    'youtube.com': 'Entertainment',
    'netflix.com': 'Entertainment',
    'twitch.tv': 'Entertainment',
    'spotify.com': 'Entertainment'
  };

  try {
    const domain = new URL(url).hostname.replace('www.', '');
    console.log('Categorizing URL:', url, 'Domain:', domain);
    
    // Direct match
    if (categoryMap[domain]) {
      console.log('Direct match found:', categoryMap[domain]);
      return categoryMap[domain];
    }
    
    // Pattern matching for subdomains
    for (const [key, category] of Object.entries(categoryMap)) {
      if (domain.includes(key) || domain.endsWith(key)) {
        console.log('Pattern match found:', key, '→', category);
        return category;
      }
    }
    
    console.log('No match found, using General');
    return 'General';
  } catch (error) {
    console.log('Error categorizing URL:', error);
    return 'General';
  }
}