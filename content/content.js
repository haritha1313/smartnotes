// Content script for Smart Notes Capture
let selectedText = '';

// Ensure content script is ready
console.log('Smart Notes content script loaded on:', window.location.href);

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

    // Add event listeners with error handling
    const cancelBtn = document.getElementById('smart-notes-cancel');
    const closeBtn = document.querySelector('.smart-notes-close');
    const saveBtn = document.getElementById('smart-notes-save');
    const commentArea = document.getElementById('smart-notes-comment');

    if (cancelBtn) cancelBtn.addEventListener('click', closeModal);
    if (closeBtn) closeBtn.addEventListener('click', closeModal);
    if (saveBtn) saveBtn.addEventListener('click', () => saveNote(data));
    
    // Close modal when clicking outside
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        closeModal();
      }
    });

    // Focus on comment textarea
    if (commentArea) {
      setTimeout(() => commentArea.focus(), 100);
    }
    
    console.log('Modal setup complete');
    
  } catch (error) {
    console.error('Error setting up modal:', error);
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

  const note = {
    id: generateId(),
    text: data.text,
    comment: comment,
    url: data.url,
    title: data.title,
    timestamp: new Date().toISOString(),
    category: suggestCategory(data.url)
  };

  // Send to background script for storage
  chrome.runtime.sendMessage({
    action: 'saveNote',
    note: note
  }, (response) => {
    if (response && response.success) {
      console.log('Note saved successfully');
      closeModal();
    } else {
      console.error('Failed to save note');
    }
  });
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