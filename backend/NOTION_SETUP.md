# Notion Integration Setup Guide

## 🚀 Quick Setup (5 minutes)

### Step 1: Create Notion Integration

1. **Go to Notion Integrations**: https://www.notion.so/my-integrations
2. **Click "New integration"**
3. **Fill in details**:
   - Name: `Smart Notes Capture`
   - Logo: (optional)
   - Associated workspace: Select your workspace
4. **Click "Submit"**
5. **Copy the Integration Token** (starts with `secret_`)

### Step 2: Create a Test Page

1. **Open Notion** and create a new page
2. **Name it**: `Smart Notes Test`
3. **Copy the page ID** from the URL:
   - URL: `https://notion.so/Smart-Notes-Test-abc123def456...`
   - Page ID: `abc123def456...` (the part after the last dash)

### Step 3: Share Page with Integration

1. **On your test page**, click "Share" → "Invite"
2. **Search for your integration**: `Smart Notes Capture`
3. **Select it** and give it "Full access"
4. **Click "Invite"**

### Step 4: Test the Integration

```bash
# Set environment variables
export NOTION_TOKEN="secret_your_integration_token_here"

# Test the connection
cd backend
python test_notion_integration.py
```

You should see:
```
✅ Notion connection successful
   User: Smart Notes Capture
   Type: bot
```

---

## 🔧 Advanced Setup (Database Creation)

### Option 1: Let API Create Database (Recommended)

The API can automatically create a "Research Notes" database for you:

```bash
# Use the setup endpoint
curl -X POST "http://127.0.0.1:8000/api/notion/setup-workspace" \
  -H "Content-Type: application/json" \
  -d '{
    "token": "secret_your_token_here",
    "parent_page_id": "your_page_id_here"
  }'
```

### Option 2: Create Database Manually

1. **In Notion**, create a new database
2. **Add these properties**:
   - `Title` (Title) - Auto-generated from content
   - `Content` (Text) - Captured text  
   - `Comment` (Text) - User's thoughts
   - `Source` (URL) - Original webpage
   - `Captured` (Date) - When it was saved
   - `Category` (Select) - Note category
   - `Status` (Select) - New, Reviewed, Archived

3. **Share the database** with your integration
4. **Copy the database ID** from the URL

---

## 🧪 Testing the Complete Flow

### Test 1: Basic Connection
```bash
cd backend
export NOTION_TOKEN="secret_your_token_here"
python test_notion_integration.py
```

### Test 2: Create Database
```bash
curl -X POST "http://127.0.0.1:8000/api/notion/setup-workspace" \
  -H "Content-Type: application/json" \
  -d '{
    "token": "secret_your_token_here", 
    "parent_page_id": "your_page_id_here"
  }'
```

### Test 3: Create Note with Notion Sync
```bash
curl -X POST "http://127.0.0.1:8000/api/notes/" \
  -H "Content-Type: application/json" \
  -H "X-Notion-Token: secret_your_token_here" \
  -H "X-Notion-Database-Id: your_database_id_here" \
  -d '{
    "text": "This is a test note that will sync to Notion",
    "comment": "Testing the integration",
    "url": "https://example.com",
    "title": "Test Page",
    "category": "Testing"
  }'
```

Expected response:
```json
{
  "success": true,
  "message": "Note created successfully",
  "data": {
    "note_id": "uuid-here",
    "sync_status": "notion_synced",
    "notion_page_id": "notion-page-id"
  }
}
```

---

## 🔒 Security Best Practices

### Environment Variables
Never commit tokens to code. Use environment variables:

```bash
# Add to .env file
NOTION_TOKEN=secret_your_token_here
NOTION_DATABASE_ID=your_database_id_here
```

### Token Permissions
The integration token has limited permissions:
- ✅ Can read/write pages you explicitly share
- ❌ Cannot access other pages in your workspace
- ❌ Cannot invite users or change workspace settings

### Rate Limiting
The API automatically handles Notion's rate limits:
- Max 3 requests per second
- Automatic retry with exponential backoff
- Background sync for optimal performance

---

## 🐛 Troubleshooting

### Common Issues

**❌ "Notion connection failed"**
- Check token format (should start with `secret_`)
- Verify token is copied correctly (no extra spaces)
- Make sure integration is in the correct workspace

**❌ "Permission denied"**  
- Share the page/database with your integration
- Give the integration "Full access" permissions
- Wait a few seconds after sharing, then retry

**❌ "Database not found"**
- Verify database ID is correct
- Make sure database is shared with integration
- Check that database hasn't been deleted

**❌ "Sync status: notion_pending"**
- Normal for large notes or slow connections
- Check again in a few seconds
- Background sync will complete automatically

### Debug Commands

```bash
# Test connection only
curl -X POST "http://127.0.0.1:8000/api/notion/test-connection" \
  -H "Content-Type: application/json" \
  -d '{"token": "secret_your_token_here"}'

# List accessible databases  
curl "http://127.0.0.1:8000/api/notion/databases?token=secret_your_token_here"

# Check API health
curl "http://127.0.0.1:8000/api/notion/health"
```

### Enable Debug Logging

```bash
# Start server with debug logging
DEBUG=True python run.py
```

---

## 📊 Performance Notes

### Sync Speeds
- **Fast sync**: < 2 seconds (appears in API response)
- **Background sync**: 2-10 seconds (updates later)
- **Failed sync**: Logged but doesn't block API

### Optimization Features
- **Rate limiting**: Prevents API abuse
- **Background processing**: Non-blocking sync
- **Caching**: Reduces duplicate database lookups  
- **Timeout handling**: Fast responses even if Notion is slow
- **Content limits**: 2000 chars text, 500 chars comment

### Production Recommendations
- Monitor sync success rates
- Set up retry queues for failed syncs
- Consider webhook notifications for important failures
- Use database indices for large note collections

---

## 🚀 Next Steps

Once Notion integration is working:

1. **Update Browser Extension**: Add Notion headers to API calls
2. **Test End-to-End**: Browser → API → Notion flow
3. **User Authentication**: Step 4 in the development plan
4. **Database Persistence**: Step 5 for production scalability

### Browser Extension Integration

The extension will need to send these headers:
```javascript
const headers = {
  'X-Notion-Token': userNotionToken,
  'X-Notion-Database-Id': userDatabaseId,
  'Content-Type': 'application/json'
};
```

This enables automatic Notion sync for all captured notes! 🎉
