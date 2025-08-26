"""
Smart Notes API Test Script
Quick functional tests for API endpoints
"""
import asyncio
import json
import time
from datetime import datetime
import httpx


API_BASE = "http://127.0.0.1:8000"


async def test_health_endpoint():
    """Test health check endpoint"""
    print("🏥 Testing health endpoint...")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{API_BASE}/health")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Health check passed: {data['status']}")
                return True
            else:
                print(f"❌ Health check failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Health check error: {e}")
            return False


async def test_create_note():
    """Test note creation endpoint"""
    print("📝 Testing note creation...")
    
    test_note = {
        "text": "This is a test note from the API test script",
        "comment": "Testing the API functionality",
        "url": "https://example.com/test",
        "title": "Test Page Title",
        "category": "Testing"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{API_BASE}/api/notes/",
                json=test_note,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 201:
                data = response.json()
                print(f"✅ Note created: {data['data']['note_id']}")
                return data['data']['note_id']
            else:
                print(f"❌ Note creation failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return None
        except Exception as e:
            print(f"❌ Note creation error: {e}")
            return None


async def test_get_notes():
    """Test notes listing endpoint"""
    print("📋 Testing notes listing...")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{API_BASE}/api/notes/")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Notes retrieved: {data['total']} total notes")
                return True
            else:
                print(f"❌ Notes listing failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Notes listing error: {e}")
            return False


async def test_get_single_note(note_id):
    """Test single note retrieval"""
    if not note_id:
        print("⏭️  Skipping single note test (no note ID)")
        return True
        
    print(f"🔍 Testing single note retrieval...")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{API_BASE}/api/notes/{note_id}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Note retrieved: {data['title']}")
                return True
            else:
                print(f"❌ Single note retrieval failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Single note retrieval error: {e}")
            return False


async def test_stats_endpoint():
    """Test statistics endpoint"""
    print("📊 Testing statistics endpoint...")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{API_BASE}/api/notes/stats/summary")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Stats retrieved: {data['total_notes']} notes")
                return True
            else:
                print(f"❌ Stats failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Stats error: {e}")
            return False


async def test_performance():
    """Test API performance"""
    print("⚡ Testing API performance...")
    
    async with httpx.AsyncClient() as client:
        # Test multiple concurrent requests
        start_time = time.time()
        
        tasks = []
        for i in range(10):
            task = client.get(f"{API_BASE}/health")
            tasks.append(task)
        
        try:
            responses = await asyncio.gather(*tasks)
            end_time = time.time()
            
            success_count = sum(1 for r in responses if r.status_code == 200)
            total_time = end_time - start_time
            
            print(f"✅ Performance test: {success_count}/10 requests successful")
            print(f"   Total time: {total_time:.3f}s, Avg: {total_time/10:.3f}s per request")
            
            return success_count == 10
        except Exception as e:
            print(f"❌ Performance test error: {e}")
            return False


async def test_rate_limiting():
    """Test rate limiting"""
    print("🛡️  Testing rate limiting...")
    
    async with httpx.AsyncClient() as client:
        # Send requests rapidly to trigger rate limiting
        requests_sent = 0
        rate_limited = False
        
        try:
            for i in range(5):  # Send 5 quick requests
                response = await client.get(f"{API_BASE}/health")
                requests_sent += 1
                
                if response.status_code == 429:
                    rate_limited = True
                    break
                    
                await asyncio.sleep(0.1)  # Small delay
            
            if rate_limited:
                print("✅ Rate limiting working (got 429 status)")
            else:
                print(f"ℹ️  Rate limiting not triggered in {requests_sent} requests (normal for low volume)")
            
            return True
        except Exception as e:
            print(f"❌ Rate limiting test error: {e}")
            return False


async def main():
    """Main test function"""
    print("🧪 Smart Notes API Test Suite")
    print("=" * 50)
    
    print(f"🎯 Testing API at: {API_BASE}")
    print(f"🕐 Started at: {datetime.now().strftime('%H:%M:%S')}\n")
    
    # Test sequence
    tests = [
        ("Health Check", test_health_endpoint),
        ("Performance", test_performance),
        ("Rate Limiting", test_rate_limiting),
        ("Create Note", test_create_note),
        ("List Notes", test_get_notes),
        ("Statistics", test_stats_endpoint),
    ]
    
    results = []
    note_id = None
    
    for test_name, test_func in tests:
        print(f"\n🔄 Running: {test_name}")
        try:
            if test_name == "Create Note":
                result = await test_func()
                note_id = result
                success = result is not None
            else:
                success = await test_func()
            
            results.append((test_name, success))
            print(f"{'✅' if success else '❌'} {test_name}: {'PASSED' if success else 'FAILED'}")
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}")
            results.append((test_name, False))
    
    # Test single note retrieval if we have a note ID
    if note_id:
        print(f"\n🔄 Running: Single Note Retrieval")
        try:
            success = await test_get_single_note(note_id)
            results.append(("Single Note Retrieval", success))
            print(f"{'✅' if success else '❌'} Single Note Retrieval: {'PASSED' if success else 'FAILED'}")
        except Exception as e:
            print(f"❌ Single Note Retrieval: ERROR - {e}")
            results.append(("Single Note Retrieval", False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 50)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status:<8} {test_name}")
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! API is working correctly.")
        return True
    else:
        print("⚠️  Some tests failed. Check the API setup.")
        return False


if __name__ == "__main__":
    print("🚀 Make sure the API server is running before starting tests!")
    print("   Run: python run.py")
    print("   Then in another terminal: python test_api.py\n")
    
    try:
        success = asyncio.run(main())
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n🛑 Tests interrupted by user")
    except Exception as e:
        print(f"\n❌ Test suite error: {e}")
        exit(1)
