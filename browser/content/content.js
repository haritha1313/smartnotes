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
  
  // Remove existing modal if any
  const existingModal = document.getElementById('smart-notes-modal');
  if (existingModal) {
    console.log('Removing existing modal');
    existingModal.remove();
  }

  // Create modal overlay
  const modal = document.createElement('div');
  modal.id = 'smart-notes-modal';
  modal.className = 'smart-notes-overlay';
  
  modal.innerHTML = `
    <div class="smart-notes-modal">
      <div class="smart-notes-header">
        <h3>Add to Notes</h3>
        <button class="smart-notes-close">&times;</button>
      </div>
      <div class="smart-notes-content">
        <div class="smart-notes-selected-text">
          <label>Selected Text:</label>
          <div class="smart-notes-text-preview">${data.text}</div>
        </div>
        <div class="smart-notes-comment-section">
          <label for="smart-notes-comment">Your Comment (optional):</label>
          <textarea id="smart-notes-comment" placeholder="Add your thoughts about this text..."></textarea>
        </div>
      </div>
      <div class="smart-notes-actions">
        <button id="smart-notes-cancel" class="smart-notes-btn-secondary">Cancel</button>
        <button id="smart-notes-save" class="smart-notes-btn-primary">Save Note</button>
      </div>
    </div>
  `;

  try {
    document.body.appendChild(modal);
    console.log('Modal appended to body');

    // Use a small delay to ensure DOM is fully updated
    setTimeout(() => {
      try {
        // Add event listeners with error handling
        const cancelBtn = document.getElementById('smart-notes-cancel');
        const closeBtn = document.querySelector('.smart-notes-close');
        const saveBtn = document.getElementById('smart-notes-save');
        const commentArea = document.getElementById('smart-notes-comment');

        if (cancelBtn) {
          cancelBtn.addEventListener('click', closeModal);
        } else {
          console.warn('Cancel button not found');
        }
        
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
        
        // Close modal when clicking outside
        modal.addEventListener('click', (e) => {
          if (e.target === modal) {
            closeModal();
          }
        });

        // Focus on comment textarea and add Enter key handler
        if (commentArea) {
          setTimeout(() => {
            try {
              commentArea.focus();
            } catch (focusError) {
              console.warn('Could not focus comment area:', focusError);
            }
          }, 100);
          
          // Handle Enter key to save note (Ctrl+Enter or just Enter)
          commentArea.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              saveNote(data);
            }
          });
        } else {
          console.warn('Comment textarea not found');
        }
        
        console.log('Modal setup complete');
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

function saveNote(data) {
  const comment = document.getElementById('smart-notes-comment').value.trim();
  const saveBtn = document.getElementById('smart-notes-save');
  const cancelBtn = document.getElementById('smart-notes-cancel');

  // Show loading state
  if (saveBtn) {
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving...';
    saveBtn.style.opacity = '0.7';
  }
  if (cancelBtn) {
    cancelBtn.disabled = true;
  }

  const note = {
    id: generateId(),
    text: data.text,
    comment: comment,
    url: data.url,
    title: data.title,
    timestamp: new Date().toISOString(),
    category: suggestCategory(data.url)
  };

  console.log('Content: Saving note:', note);

  // Send to background script for storage
  chrome.runtime.sendMessage({
    action: 'saveNote',
    note: note
  }, (response) => {
    console.log('Content: Save response:', response);
    
    // Reset button states
    if (saveBtn) {
      saveBtn.disabled = false;
      saveBtn.textContent = 'Save Note';
      saveBtn.style.opacity = '1';
    }
    if (cancelBtn) {
      cancelBtn.disabled = false;
    }

    if (response && response.success) {
      console.log('Content: Note saved successfully via:', response.method);
      console.log('Content: Sync status:', response.syncStatus);
      
      // Show detailed success message based on sync status
      let notificationMessage = '✓ Note saved locally';
      if (response.syncStatus === 'notion_synced') {
        notificationMessage = '🎉 Note saved and synced to Notion!';
      } else if (response.syncStatus === 'notion_pending') {
        notificationMessage = '⏳ Note saved, syncing to Notion...';
      } else if (response.syncStatus === 'notion_failed') {
        notificationMessage = '⚠️ Note saved locally, Notion sync failed';
      } else if (response.method === 'api') {
        notificationMessage = '✓ Note saved to server';
      }
      
      showNotification(notificationMessage, 'success');
      
      // Log Notion page ID if available
      if (response.notionPageId) {
        console.log('Content: Notion page created:', response.notionPageId);
      }
      
      // Close modal after short delay
      setTimeout(() => {
        closeModal();
      }, 2000); // Slightly longer delay to read the Notion status
    } else {
      console.error('Content: Failed to save note:', response?.error);
      
      // Show error message
      const errorMsg = response?.error || 'Unknown error occurred';
      showNotification(`✗ Failed to save: ${errorMsg}`, 'error');
    }
  });
}

// Show notification messages to user
function showNotification(message, type = 'info') {
  try {
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

    // Auto-remove after 3 seconds
    setTimeout(() => {
      if (notification.parentNode) {
        notification.classList.add('slide-out');
        setTimeout(() => {
          if (notification.parentNode) {
            notification.parentNode.removeChild(notification);
          }
        }, 300);
      }
    }, 3000);
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