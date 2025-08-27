"""
Test script for category extraction using proper config system
"""
import asyncio
import sys
import os

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.services.category_extractor import extract_existing_categories, test_category_extraction
from app.config import settings

async def main():
    """Test category extraction using config from .env"""
    try:
        print("🔍 Testing category extraction with config from .env...")
        
        # Check if tokens are loaded from .env
        if not settings.notion_token:
            print("❌ NOTION_TOKEN not found in .env file")
            print("Please make sure your .env file contains:")
            print("NOTION_TOKEN=your_token_here")
            return None
            
        if not settings.notion_database_id:
            print("❌ NOTION_DATABASE_ID not found in .env file")
            print("Please make sure your .env file contains:")
            print("NOTION_DATABASE_ID=your_database_id_here")
            return None
        
        print(f"✅ Loaded tokens from .env")
        print(f"Database ID: {settings.notion_database_id}")
        print(f"Token starts with: {settings.notion_token[:10]}...")
        
        # Test basic category extraction
        print("\n1. Testing extract_existing_categories()...")
        categories = await extract_existing_categories(settings.notion_token, settings.notion_database_id)
        print(f"✅ Successfully extracted {len(categories)} categories:")
        for i, category in enumerate(categories, 1):
            print(f"   {i}. {category}")
        
        # Test the comprehensive test function
        print("\n2. Running comprehensive test...")
        await test_category_extraction(settings.notion_token, settings.notion_database_id)
        
        print(f"\n🎉 All tests passed! Your categories are: {categories}")
        return categories
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    result = asyncio.run(main())
    if result:
        print(f"\n✅ Category extraction is working! Found categories: {result}")
    else:
        print("\n❌ Category extraction failed. Please check your Notion setup.")
