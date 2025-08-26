#!/usr/bin/env python3

import requests
import json

def test_api_with_notion_headers():
    """Test the exact request the extension is making"""
    
    # Test data - exactly what the extension sends
    data = {
        'text': 'Test note from debug script',
        'comment': 'Debug test', 
        'url': 'https://example.com',
        'title': 'Debug Test Page',
        'category': 'General',
        'timestamp': '2025-08-25T23:30:00Z'
    }

    # Headers with Notion credentials
    headers = {
        'Content-Type': 'application/json',
        'X-Notion-Token': 'YOUR_NOTION_TOKEN_HERE',
        'X-Notion-Database-Id': 'YOUR_DATABASE_ID_HERE'
    }

    print("🧪 Testing API call with Notion headers...")
    print(f"📤 Request URL: http://localhost:8000/api/notes/")
    print(f"📤 Headers: {list(headers.keys())}")
    print(f"📤 Data: {data}")
    print()

    try:
        response = requests.post('http://localhost:8000/api/notes/', json=data, headers=headers)
        
        print(f"📨 Status Code: {response.status_code}")
        print(f"📨 Response Headers: {dict(response.headers)}")
        print()
        
        if response.status_code == 200:
            result = response.json()
            print("✅ SUCCESS!")
            print(f"📨 Response: {json.dumps(result, indent=2)}")
            
            # Check the key fields we expect
            if 'sync_status' in result:
                print(f"🔄 Sync Status: {result.get('sync_status', 'unknown')}")
            if 'notion_page_id' in result:
                print(f"📄 Notion Page ID: {result.get('notion_page_id', 'none')}")
            if 'notion_page_url' in result:
                print(f"🔗 Notion Page URL: {result.get('notion_page_url', 'none')}")
        else:
            print("❌ ERROR!")
            try:
                error_data = response.json()
                print(f"📨 Error Response: {json.dumps(error_data, indent=2)}")
            except:
                print(f"📨 Raw Response: {response.text}")
                
    except requests.exceptions.ConnectionError:
        print("❌ CONNECTION ERROR - Is the backend server running?")
        print("   Run: uvicorn app.main:app --reload")
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}")

if __name__ == "__main__":
    test_api_with_notion_headers()
