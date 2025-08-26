#!/bin/bash
# Setup script for Smart Notes extension

echo "🚀 Setting up Smart Notes Extension..."

# Create config.js from template if it doesn't exist
if [ ! -f "browser/config.js" ]; then
    echo "📋 Creating config.js from template..."
    cp browser/config.template.js browser/config.js
    echo "✅ Created browser/config.js"
    echo "⚠️  IMPORTANT: Edit browser/config.js and add your Notion credentials!"
    echo "   - Get token from: https://www.notion.so/my-integrations"
    echo "   - Create a database in Notion and get its ID"
else
    echo "✅ config.js already exists"
fi

# Check if backend dependencies need to be installed
if [ -f "backend/requirements.txt" ]; then
    echo "📦 Backend found. To set up:"
    echo "   cd backend && pip install -r requirements.txt"
    echo "   python -m uvicorn app.main:app --reload"
fi

echo ""
echo "🎉 Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit browser/config.js with your Notion credentials"
echo "2. Load extension in Chrome: chrome://extensions/ → Load unpacked → browser/"  
echo "3. Test on test-page.html or any website"
echo "4. (Optional) Start backend API for enhanced features"
echo ""
echo "For detailed instructions, see SETUP.md"