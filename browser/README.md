# Smart Notes Browser Extension

## 🔐 Security Setup (Important!)

### **Step 1: Create Your Config Files**
```bash
# Copy the templates to create your configs
cp config.template.js config.js
cp background/background.template.js background/background.js
```

### **Step 2: Add Your Credentials**
**Edit `config.js`** and replace the placeholder values:
```javascript
const NOTION_CONFIG = {
  TOKEN: "secret_your_actual_notion_token_here",
  DATABASE_ID: "your_actual_database_id_here"
};
```

**Edit `background/background.js`** and replace the placeholder values:
```javascript
const NOTION_CONFIG = {
  TOKEN: "secret_your_actual_notion_token_here",  
  DATABASE_ID: "your_actual_database_id_here"    
};
```

### **Step 3: Verify Security**
- ✅ `config.js` is in `.gitignore` (your tokens won't be committed)
- ✅ `config.template.js` is safe to commit (no real tokens)
- ✅ Only you have access to your actual tokens

## 🚀 Loading the Extension

1. **Open Chrome**: Go to `chrome://extensions/`
2. **Enable Developer Mode**: Toggle the switch
3. **Load Extension**: Click "Load unpacked" → select the `browser/` folder
4. **Ready**: The extension icon should appear

## 🧪 Testing

1. **Go to any website**
2. **Select text** → right-click → "Add to Notes"
3. **Add comment** and save
4. **Check Notion**: Your note should appear in the Research Notes database

## 🐛 Troubleshooting

### "Adding Notion integration headers" not appearing in console
- Check that `config.js` exists and has real values
- Verify the extension is reloaded after creating `config.js`

### Notes save locally but don't sync to Notion
- Check your Notion token is valid
- Verify the database ID is correct
- Check the API server is running (`python run.py`)

### Permission errors
- Make sure your Notion integration has access to the database
- Check that the database exists in your workspace

## 📁 File Structure

```
browser/
├── config.template.js           ✅ Safe to commit (template)
├── config.js                    ❌ Never commit (your secrets)
├── manifest.json
├── popup/
├── content/
└── background/
    ├── background.template.js   ✅ Safe to commit (template)  
    └── background.js            ❌ Never commit (your secrets)
```

## 🔒 Security Notes

- **Never commit `config.js`** - it contains your personal tokens
- **Always use `config.template.js`** for sharing code
- **Keep tokens private** - they give access to your Notion workspace
- **Regenerate tokens** if accidentally exposed

---

**Ready to capture notes and sync them to Notion!** 🎉
