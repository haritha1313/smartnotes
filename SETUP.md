# Smart Notes - Setup Instructions

## Quick Start

### 1. Configure Extension
```bash
# Copy the configuration template
cp browser/config.template.js browser/config.js

# Edit browser/config.js and add your Notion credentials:
# - TOKEN: Get from https://www.notion.so/my-integrations  
# - DATABASE_ID: Create a database in Notion and get its ID from the URL
```

### 2. Start Backend (Optional)
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

### 3. Load Extension
1. Open Chrome → `chrome://extensions/`
2. Enable "Developer mode" 
3. Click "Load unpacked" → select the `browser/` folder
4. Test on `test-page.html` or any website

## Configuration

### Browser Extension
- Copy `browser/config.template.js` to `browser/config.js`
- Add your actual Notion integration token and database ID
- The `config.js` file is ignored by git for security

### Notion Integration
1. Create a Notion integration at https://www.notion.so/my-integrations
2. Create a database in Notion
3. Add the integration to your database (Share → Add connections)
4. Copy the token and database ID to your `config.js`

### Backend API (Optional)
- The extension works offline/locally without the backend
- Backend enables server storage and enhanced features
- Configure via environment variables or `backend/app/config.py`

## Security

⚠️ **Never commit sensitive credentials to git:**
- `browser/config.js` is in `.gitignore` 
- Use the template files for configuration
- Credentials should be personal and never shared

## Testing

1. Open `test-page.html` in your browser
2. Select text and right-click → "Add to Notes"  
3. Check browser console for detailed logs
4. Use `browser/debug.js` for advanced debugging

## Troubleshooting

- **Context menu missing**: Reload extension and refresh page
- **Modal not appearing**: Check browser console for errors
- **API issues**: Verify backend is running on localhost:8000
- **Notion sync failing**: Check token and database permissions