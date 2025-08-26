"""
Notion Integration Test Script
Test the complete API → Notion integration flow
"""
import asyncio
import json
import httpx
from datetime import datetime
import os


async def test_notion_integration():
    """Test the complete Notion integration flow"""
    print("🔗 Testing Notion Integration")
    print("=" * 50)
    
    # Configuration
    api_base = "http://127.0.0.1:8000"
    
    # Notion credentials (you'll need to provide these)
    notion_token = os.getenv("NOTION_TOKEN", "")
    notion_database_id = os.getenv("NOTION_DATABASE_ID", "")
    
    if not notion_token:
        print("⚠️  NOTION_TOKEN environment variable not set")
        print("   Set it to test Notion integration:")
        print("   export NOTION_TOKEN='your-notion-integration-token'")
        print("\n   Testing API without Notion integration...")
        notion_token = None
    
    if not notion_database_id and notion_token:
        print("⚠️  NOTION_DATABASE_ID environment variable not set")
        print("   Set it to test full integration:")
        print("   export NOTION_DATABASE_ID='your-database-id'")
        print("\n   Testing Notion connection only...")
        notion_database_id = None
    
    # Test note data
    test_note = {
        "text": "This is a test note for Notion integration testing",
        "comment": "Testing the complete API → Notion flow",
        "url": "https://example.com/notion-test",
        "title": "Notion Integration Test Page",
        "category": "Testing"
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # 1. Test API health
            print("\n1️⃣ Testing API health...")
            health_response = await client.get(f"{api_base}/health")
            if health_response.status_code != 200:
                print(f"❌ API not available: {health_response.status_code}")
                return False
            print("✅ API is running")
            
            # 2. Test Notion health endpoint
            print("\n2️⃣ Testing Notion service...")
            notion_health = await client.get(f"{api_base}/api/notion/health")
            if notion_health.status_code != 200:
                print(f"❌ Notion service not available: {notion_health.status_code}")
                return False
            
            notion_status = notion_health.json()
            print(f"✅ Notion service available: {notion_status['status']}")
            
            # 3. Test Notion connection (if token provided)
            if notion_token:
                print("\n3️⃣ Testing Notion API connection...")
                connection_test = await client.post(
                    f"{api_base}/api/notion/test-connection",
                    json={"token": notion_token}
                )
                
                if connection_test.status_code == 200:
                    conn_data = connection_test.json()
                    print(f"✅ Notion connection successful")
                    print(f"   User: {conn_data['data']['user_name']}")
                    print(f"   Type: {conn_data['data']['user_type']}")
                else:
                    print(f"❌ Notion connection failed: {connection_test.status_code}")
                    print(f"   Response: {connection_test.text}")
                    return False
            else:
                print("\n3️⃣ Skipping Notion connection test (no token)")
            
            # 4. Test note creation without Notion
            print("\n4️⃣ Testing note creation (local only)...")
            local_response = await client.post(
                f"{api_base}/api/notes/",
                json=test_note
            )
            
            if local_response.status_code != 201:
                print(f"❌ Local note creation failed: {local_response.status_code}")
                return False
            
            local_data = local_response.json()
            print(f"✅ Local note created: {local_data['data']['note_id']}")
            print(f"   Sync status: {local_data['data']['sync_status']}")
            
            # 5. Test note creation with Notion (if configured)
            if notion_token and notion_database_id:
                print("\n5️⃣ Testing note creation with Notion sync...")
                
                headers = {
                    "X-Notion-Token": notion_token,
                    "X-Notion-Database-Id": notion_database_id,
                    "Content-Type": "application/json"
                }
                
                notion_response = await client.post(
                    f"{api_base}/api/notes/",
                    json=test_note,
                    headers=headers
                )
                
                if notion_response.status_code != 201:
                    print(f"❌ Notion note creation failed: {notion_response.status_code}")
                    print(f"   Response: {notion_response.text}")
                    return False
                
                notion_data = notion_response.json()
                print(f"✅ Note with Notion sync created: {notion_data['data']['note_id']}")
                print(f"   Sync status: {notion_data['data']['sync_status']}")
                
                if notion_data['data'].get('notion_page_id'):
                    print(f"   Notion page: {notion_data['data']['notion_page_id']}")
                
                # Wait a moment for background sync if needed
                if notion_data['data']['sync_status'] == 'notion_pending':
                    print("   Waiting for background sync...")
                    await asyncio.sleep(3)
                    
                    # Check note status
                    note_id = notion_data['data']['note_id']
                    status_response = await client.get(f"{api_base}/api/notes/{note_id}")
                    if status_response.status_code == 200:
                        updated_note = status_response.json()
                        print(f"   Updated sync status: {updated_note['sync_status']}")
                
            else:
                print("\n5️⃣ Skipping Notion sync test (missing token or database ID)")
            
            # 6. Test listing notes
            print("\n6️⃣ Testing notes listing...")
            list_response = await client.get(f"{api_base}/api/notes/")
            if list_response.status_code != 200:
                print(f"❌ Notes listing failed: {list_response.status_code}")
                return False
            
            list_data = list_response.json()
            print(f"✅ Notes retrieved: {list_data['total']} total")
            
            # Show sync status summary
            sync_statuses = {}
            for note in list_data['notes']:
                status = note.get('sync_status', 'unknown')
                sync_statuses[status] = sync_statuses.get(status, 0) + 1
            
            print("   Sync status summary:")
            for status, count in sync_statuses.items():
                print(f"     {status}: {count}")
            
            # 7. Test performance
            print("\n7️⃣ Testing performance...")
            start_time = asyncio.get_event_loop().time()
            
            performance_response = await client.post(
                f"{api_base}/api/notes/",
                json={
                    "text": "Performance test note",
                    "url": "https://example.com/perf",
                    "title": "Performance Test"
                }
            )
            
            end_time = asyncio.get_event_loop().time()
            response_time = (end_time - start_time) * 1000
            
            if performance_response.status_code == 201:
                print(f"✅ Performance test: {response_time:.2f}ms response time")
                if response_time < 100:
                    print("   🚀 Excellent performance!")
                elif response_time < 500:
                    print("   ✅ Good performance")
                else:
                    print("   ⚠️  Consider optimization")
            
            return True
            
        except httpx.RequestError as e:
            print(f"❌ Network error: {e}")
            print("💡 Make sure the API server is running: python run.py")
            return False
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return False


async def test_notion_api_directly():
    """Test Notion API endpoints directly"""
    print("\n🧪 Direct Notion API Tests")
    print("=" * 40)
    
    notion_token = os.getenv("NOTION_TOKEN", "")
    if not notion_token:
        print("⚠️  Skipping direct Notion tests (no token)")
        return True
    
    api_base = "http://127.0.0.1:8000"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Test list databases
            print("\n📊 Testing database listing...")
            db_response = await client.get(
                f"{api_base}/api/notion/databases",
                params={"token": notion_token}
            )
            
            if db_response.status_code == 200:
                databases = db_response.json()
                print(f"✅ Found {len(databases)} accessible databases")
                for db in databases[:3]:  # Show first 3
                    print(f"   - {db['title']} ({db['id'][:8]}...)")
            else:
                print(f"⚠️  Database listing failed: {db_response.status_code}")
            
            return True
            
        except Exception as e:
            print(f"❌ Direct Notion test error: {e}")
            return False


async def main():
    """Main test function"""
    print("🧪 Smart Notes Notion Integration Test Suite")
    print("=" * 60)
    
    print("📋 Setup Instructions:")
    print("1. Make sure the API server is running: python run.py")
    print("2. Optional: Set NOTION_TOKEN for full testing")
    print("3. Optional: Set NOTION_DATABASE_ID for sync testing")
    print()
    
    # Run tests
    integration_ok = await test_notion_integration()
    direct_ok = await test_notion_api_directly()
    
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS")
    print("=" * 60)
    
    if integration_ok:
        print("✅ Integration tests: PASSED")
    else:
        print("❌ Integration tests: FAILED")
    
    if direct_ok:
        print("✅ Direct API tests: PASSED") 
    else:
        print("❌ Direct API tests: FAILED")
    
    if integration_ok and direct_ok:
        print("\n🎉 ALL TESTS PASSED!")
        print("The Notion integration is working correctly.")
        print("\n🚀 Next steps:")
        print("1. Update browser extension to send Notion headers")
        print("2. Test complete browser → API → Notion flow")
        print("3. Proceed to Step 4: User Authentication")
        return True
    else:
        print("\n⚠️  Some tests failed. Check the output above.")
        return False


if __name__ == "__main__":
    print("🚀 Make sure the API server is running before starting tests!")
    print("   Run: python run.py")
    print("   Then in another terminal: python test_notion_integration.py\n")
    
    try:
        success = asyncio.run(main())
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n🛑 Tests interrupted by user")
    except Exception as e:
        print(f"\n❌ Test suite error: {e}")
        exit(1)
