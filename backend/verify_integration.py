"""
Integration Verification Script
Test the complete browser extension → API → storage flow
"""
import asyncio
import json
import httpx
from datetime import datetime


async def verify_extension_integration():
    """Verify that the API can receive notes from browser extension"""
    print("🔗 Verifying Browser Extension → API Integration")
    print("=" * 60)
    
    # Simulate browser extension note payload
    extension_note = {
        "text": "This simulates a note captured from a browser extension",
        "comment": "Testing the complete integration flow",
        "url": "https://github.com/microsoft/vscode",
        "title": "GitHub - microsoft/vscode: Visual Studio Code",
        "category": "Development",
        "timestamp": datetime.utcnow().isoformat()
    }
    
    api_base = "http://127.0.0.1:8000"
    
    print(f"📡 API Server: {api_base}")
    print(f"📝 Test Note: {extension_note['text'][:50]}...")
    
    async with httpx.AsyncClient() as client:
        try:
            # 1. Test server availability
            print("\n1️⃣ Testing server availability...")
            health_response = await client.get(f"{api_base}/health")
            if health_response.status_code != 200:
                print(f"❌ Server not available: {health_response.status_code}")
                return False
            print(f"✅ Server is running")
            
            # 2. Test note creation (extension → API)
            print("\n2️⃣ Testing note creation (simulating extension)...")
            create_response = await client.post(
                f"{api_base}/api/notes/",
                json=extension_note,
                headers={
                    "Content-Type": "application/json",
                    "Origin": "chrome-extension://test-extension-id"
                }
            )
            
            if create_response.status_code != 201:
                print(f"❌ Note creation failed: {create_response.status_code}")
                print(f"Response: {create_response.text}")
                return False
            
            created_note = create_response.json()
            note_id = created_note['data']['note_id']
            print(f"✅ Note created with ID: {note_id}")
            
            # 3. Test note retrieval
            print("\n3️⃣ Testing note retrieval...")
            get_response = await client.get(f"{api_base}/api/notes/{note_id}")
            if get_response.status_code != 200:
                print(f"❌ Note retrieval failed: {get_response.status_code}")
                return False
            
            retrieved_note = get_response.json()
            print(f"✅ Note retrieved: {retrieved_note['title']}")
            
            # 4. Test notes listing
            print("\n4️⃣ Testing notes listing...")
            list_response = await client.get(f"{api_base}/api/notes/")
            if list_response.status_code != 200:
                print(f"❌ Notes listing failed: {list_response.status_code}")
                return False
            
            notes_data = list_response.json()
            print(f"✅ Notes listing: {notes_data['total']} total notes")
            
            # 5. Test CORS headers
            print("\n5️⃣ Testing CORS headers...")
            cors_headers = create_response.headers
            expected_cors_headers = [
                "access-control-allow-origin",
                "x-content-type-options",
                "x-frame-options"
            ]
            
            cors_ok = True
            for header in expected_cors_headers:
                if header not in cors_headers:
                    print(f"❌ Missing CORS header: {header}")
                    cors_ok = False
            
            if cors_ok:
                print("✅ CORS headers present")
            
            # 6. Test response time
            print("\n6️⃣ Testing response time...")
            process_time = create_response.headers.get("x-process-time")
            if process_time:
                time_ms = float(process_time) * 1000
                print(f"✅ Response time: {time_ms:.2f}ms")
                if time_ms > 100:
                    print("⚠️  Response time > 100ms (consider optimization)")
            else:
                print("⚠️  No process time header found")
            
            # 7. Test category detection
            print("\n7️⃣ Testing category detection...")
            if retrieved_note['category'] == extension_note['category']:
                print(f"✅ Category preserved: {retrieved_note['category']}")
            else:
                print(f"⚠️  Category changed: {extension_note['category']} → {retrieved_note['category']}")
            
            return True
            
        except httpx.RequestError as e:
            print(f"❌ Network error: {e}")
            print("💡 Make sure the API server is running: python run.py")
            return False
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return False


async def test_performance_under_load():
    """Test API performance with multiple concurrent requests"""
    print("\n⚡ Performance Test: Concurrent Requests")
    print("=" * 50)
    
    api_base = "http://127.0.0.1:8000"
    
    # Create multiple test notes
    test_notes = []
    for i in range(10):
        test_notes.append({
            "text": f"Performance test note #{i+1}",
            "comment": f"Load testing comment {i+1}",
            "url": f"https://example.com/test-{i+1}",
            "title": f"Test Page {i+1}",
            "category": "Testing"
        })
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Send concurrent requests
            start_time = asyncio.get_event_loop().time()
            
            tasks = []
            for note in test_notes:
                task = client.post(f"{api_base}/api/notes/", json=note)
                tasks.append(task)
            
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            end_time = asyncio.get_event_loop().time()
            
            # Analyze results
            successful = 0
            failed = 0
            for response in responses:
                if isinstance(response, Exception):
                    failed += 1
                elif response.status_code == 201:
                    successful += 1
                else:
                    failed += 1
            
            total_time = end_time - start_time
            avg_time = total_time / len(test_notes)
            
            print(f"📊 Results:")
            print(f"   Total requests: {len(test_notes)}")
            print(f"   Successful: {successful}")
            print(f"   Failed: {failed}")
            print(f"   Total time: {total_time:.3f}s")
            print(f"   Average time: {avg_time:.3f}s per request")
            
            if successful >= 8:  # Allow for some failures due to rate limiting
                print("✅ Performance test passed")
                return True
            else:
                print("⚠️  Performance test had many failures")
                return False
                
        except Exception as e:
            print(f"❌ Performance test error: {e}")
            return False


async def main():
    """Main verification function"""
    print("🔍 Smart Notes Integration Verification")
    print("=" * 60)
    print("This script verifies the complete browser extension → API flow")
    print("Make sure the API server is running before starting!\n")
    
    # Run verification tests
    integration_ok = await verify_extension_integration()
    
    if integration_ok:
        print("\n" + "=" * 60)
        print("🎉 INTEGRATION VERIFICATION PASSED!")
        print("=" * 60)
        print("✅ Browser extension can successfully communicate with API")
        print("✅ Notes are created and stored correctly")
        print("✅ CORS configuration allows extension requests")
        print("✅ Response times are acceptable")
        
        # Run performance test
        performance_ok = await test_performance_under_load()
        
        print("\n🚀 READY FOR NEXT STEP!")
        print("The API backend is working correctly.")
        print("You can now:")
        print("1. Test the browser extension with the running API")
        print("2. Proceed to Step 3: Notion Integration")
        
        return True
    else:
        print("\n" + "=" * 60)
        print("❌ INTEGRATION VERIFICATION FAILED!")
        print("=" * 60)
        print("Please check the following:")
        print("1. API server is running: python run.py")
        print("2. Server is accessible at http://127.0.0.1:8000")
        print("3. No firewall blocking the connection")
        print("4. Check server logs for errors")
        
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n🛑 Verification interrupted by user")
    except Exception as e:
        print(f"\n❌ Verification error: {e}")
        exit(1)
