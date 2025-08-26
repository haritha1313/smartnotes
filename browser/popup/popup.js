// Smart Notes Popup Script
let allNotes = [];
let filteredNotes = [];

document.addEventListener('DOMContentLoaded', async () => {
  console.log('Smart Notes popup loaded');
  
  try {
    await loadNotes();
    setupEventListeners();
  } catch (error) {
    console.error('Error initializing popup:', error);
    showError('Failed to load notes');
  }
});

async function loadNotes() {
  try {
    const result = await chrome.storage.local.get(['notes']);
    allNotes = result.notes || [];
    filteredNotes = [...allNotes];
    
    console.log('Loaded notes:', allNotes);
    
    updateNoteCount();
    updateCategoryFilter();
    renderNotes();
  } catch (error) {
    console.error('Error loading notes:', error);
    throw error;
  }
}

function updateNoteCount() {
  const countElement = document.getElementById('note-count');
  if (countElement) {
    countElement.textContent = allNotes.length;
  }
}

function updateCategoryFilter() {
  const filterSelect = document.getElementById('category-filter');
  if (!filterSelect) return;
  
  // Get unique categories
  const categories = [...new Set(allNotes.map(note => note.category))];
  
  // Clear existing options except "All Categories"
  filterSelect.innerHTML = '<option value="">All Categories</option>';
  
  // Add category options
  categories.forEach(category => {
    const option = document.createElement('option');
    option.value = category;
    option.textContent = category;
    filterSelect.appendChild(option);
  });
}

function renderNotes() {
  const container = document.getElementById('notes-container');
  if (!container) return;
  
  if (filteredNotes.length === 0) {
    container.innerHTML = allNotes.length === 0 
      ? '<div class="no-notes">No notes saved yet.<br>Select text on any webpage and right-click to add notes.</div>'
      : '<div class="no-notes">No notes match your search.</div>';
    return;
  }
  
  container.innerHTML = filteredNotes.map(note => createNoteHTML(note)).join('');
  
  // Add event listeners to delete buttons
  container.querySelectorAll('.note-delete').forEach(button => {
    button.addEventListener('click', (e) => {
      const noteId = e.target.dataset.noteId;
      deleteNote(noteId);
    });
  });
  
  // Add event listeners to URL links
  container.querySelectorAll('.note-url').forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      chrome.tabs.create({ url: link.href });
    });
  });
}

function createNoteHTML(note) {
  const timestamp = new Date(note.timestamp).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
  
  const categoryClass = note.category.toLowerCase().replace(/\s+/g, '-');
  
  // Create a shortened version for display but keep full URL for linking
  const displayUrl = note.title || note.url;
  const shortUrl = displayUrl.length > 50 ? displayUrl.substring(0, 47) + '...' : displayUrl;
  
  const commentHTML = note.comment 
    ? `<div class="note-comment">"${escapeHtml(note.comment)}"</div>`
    : '';

  // Add sync status indicator
  const syncStatus = note.syncStatus || 'unknown';
  const syncHTML = getSyncStatusHTML(syncStatus, note.lastError);
  
  return `
    <div class="note-item">
      <div class="note-header">
        <span class="note-category ${categoryClass}">${escapeHtml(note.category)}</span>
        <div class="note-header-right">
          ${syncHTML}
          <span class="note-timestamp">${timestamp}</span>
        </div>
      </div>
      
      <div class="note-text">${escapeHtml(note.text)}</div>
      
      ${commentHTML}
      
      <div class="note-footer">
        <div class="note-info">
          <a href="${note.url}" class="note-url" title="${escapeHtml(note.url)}">${escapeHtml(shortUrl)}</a>
        </div>
        <div class="note-actions">
          <button class="note-delete" data-note-id="${note.id}" title="Delete note">Delete</button>
        </div>
      </div>
    </div>
  `;
}

function getSyncStatusHTML(syncStatus, lastError) {
  switch (syncStatus) {
    case 'synced':
      return '<span class="sync-status synced" title="Synced to server">☁</span>';
    case 'pending':
      return '<span class="sync-status pending" title="Saved locally, pending sync">⏳</span>';
    case 'failed':
      const errorTitle = lastError ? `Sync failed: ${lastError}` : 'Sync failed';
      return `<span class="sync-status failed" title="${errorTitle}">⚠</span>`;
    default:
      return '<span class="sync-status unknown" title="Unknown sync status">📱</span>';
  }
}

function setupEventListeners() {
  const searchInput = document.getElementById('search-input');
  const categoryFilter = document.getElementById('category-filter');
  
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      filterNotes();
    });
  }
  
  if (categoryFilter) {
    categoryFilter.addEventListener('change', (e) => {
      filterNotes();
    });
  }
}

function filterNotes() {
  const searchTerm = document.getElementById('search-input').value.toLowerCase();
  const selectedCategory = document.getElementById('category-filter').value;
  
  filteredNotes = allNotes.filter(note => {
    const matchesSearch = !searchTerm || 
      note.text.toLowerCase().includes(searchTerm) ||
      (note.comment && note.comment.toLowerCase().includes(searchTerm)) ||
      note.url.toLowerCase().includes(searchTerm) ||
      (note.title && note.title.toLowerCase().includes(searchTerm));
    
    const matchesCategory = !selectedCategory || note.category === selectedCategory;
    
    return matchesSearch && matchesCategory;
  });
  
  renderNotes();
}

async function deleteNote(noteId) {
  if (!confirm('Are you sure you want to delete this note?')) {
    return;
  }
  
  try {
    // Remove from local array
    allNotes = allNotes.filter(note => note.id !== noteId);
    
    // Save to storage
    await chrome.storage.local.set({ notes: allNotes });
    
    // Refresh display
    filteredNotes = filteredNotes.filter(note => note.id !== noteId);
    updateNoteCount();
    updateCategoryFilter();
    renderNotes();
    
    console.log('Note deleted:', noteId);
  } catch (error) {
    console.error('Error deleting note:', error);
    alert('Failed to delete note');
  }
}

function extractDomain(url) {
  try {
    return new URL(url).hostname.replace('www.', '');
  } catch {
    return url;
  }
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function showError(message) {
  const container = document.getElementById('notes-container');
  if (container) {
    container.innerHTML = `<div class="no-notes" style="color: #dc3545;">${message}</div>`;
  }
}