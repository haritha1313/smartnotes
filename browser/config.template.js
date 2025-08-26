// API Configuration for Smart Notes Extension
const API_CONFIG = {
  BASE_URL: 'http://localhost:8000',
  ENDPOINTS: {
    NOTES: '/api/notes/',  // Fixed: Added trailing slash to avoid 307 redirect
    AUTH: '/api/auth',
    CATEGORIES: '/api/categories'
  }
};

// Notion Integration Configuration Template
// IMPORTANT: Copy this file to config.js and replace with your actual credentials
const NOTION_CONFIG = {
  // Get your integration token from https://www.notion.so/my-integrations
  TOKEN: "secret_YOUR_NOTION_INTEGRATION_TOKEN_HERE",
  
  // Your Notion database ID - create a database and get its ID from the URL
  DATABASE_ID: "YOUR_DATABASE_ID_HERE"
};

// API Client for making requests to backend
const apiClient = {
  /**
   * Get authentication token from storage
   */
  async getAuthToken() {
    try {
      const result = await chrome.storage.local.get(['authToken']);
      return result.authToken || null;
    } catch (error) {
      console.error('Error getting auth token:', error);
      return null;
    }
  },

  /**
   * Make POST request to API
   */
  async post(endpoint, data) {
    try {
      const token = await this.getAuthToken();
      const url = `${API_CONFIG.BASE_URL}${endpoint}`;
      
      console.log('Making API request to:', url);
      console.log('Request data:', data);

      // Prepare headers
      const headers = {
        'Content-Type': 'application/json',
        ...(token && { 'Authorization': `Bearer ${token}` }),
      };

      // Add Notion headers for notes endpoint
      if (endpoint === API_CONFIG.ENDPOINTS.NOTES && NOTION_CONFIG.TOKEN && NOTION_CONFIG.DATABASE_ID) {
        headers['X-Notion-Token'] = NOTION_CONFIG.TOKEN;
        headers['X-Notion-Database-Id'] = NOTION_CONFIG.DATABASE_ID;
        console.log('Adding Notion integration headers');
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

      console.log('API response:', result);
      return { success: true, data: result };

    } catch (error) {
      console.error('API request failed:', error);
      return { 
        success: false, 
        error: error.message || 'Network request failed',
        isNetworkError: error.name === 'TypeError' || error.message.includes('fetch')
      };
    }
  },

  /**
   * Make GET request to API
   */
  async get(endpoint, params = {}) {
    try {
      const token = await this.getAuthToken();
      const url = new URL(`${API_CONFIG.BASE_URL}${endpoint}`);
      
      // Add query parameters
      Object.keys(params).forEach(key => {
        if (params[key] !== undefined && params[key] !== null) {
          url.searchParams.append(key, params[key]);
        }
      });

      const response = await fetch(url, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          ...(token && { 'Authorization': `Bearer ${token}` }),
        }
      });

      const result = await response.json();
      
      if (!response.ok) {
        throw new Error(result.detail || `HTTP ${response.status}: ${response.statusText}`);
      }

      return { success: true, data: result };

    } catch (error) {
      console.error('API GET request failed:', error);
      return { 
        success: false, 
        error: error.message || 'Network request failed',
        isNetworkError: error.name === 'TypeError' || error.message.includes('fetch')
      };
    }
  },

  /**
   * Check if API is available
   */
  async checkConnection() {
    try {
      const response = await fetch(`${API_CONFIG.BASE_URL}/health`, {
        method: 'GET',
        timeout: 5000
      });
      return response.ok;
    } catch (error) {
      console.log('API not available:', error.message);
      return false;
    }
  }
};

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { API_CONFIG, apiClient };
}
