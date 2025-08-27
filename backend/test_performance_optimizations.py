"""
Test performance optimizations for categorization
"""
import asyncio
import time
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.services.category_extractor import extract_existing_categories, warm_category_cache, clear_category_cache
from app.services.ai_categorization import get_category_ai
from app.config import settings

async def test_performance_improvements():
    """Test the performance optimizations"""
    
    print("🚀 Testing Performance Optimizations")
    print("=" * 50)
    
    if not settings.claude_api_key or not settings.notion_token:
        print("❌ Please ensure CLAUDE_API_KEY and NOTION_TOKEN are set in .env")
        return
    
    test_content = "Today's AI assistants are lackluster in comparison to what we could build with proper real-time reasoning capabilities"
    
    # **Test 1: Cold start (no cache)**
    print("\n1. 🧊 Cold start (no cache)")
    clear_category_cache()
    
    start_time = time.time()
    
    # Fetch categories (will hit Notion API)
    categories = await extract_existing_categories(settings.notion_token, settings.notion_database_id)
    
    # Get AI suggestion
    category_ai = get_category_ai()
    suggestion = await category_ai.suggest_category(
        content=test_content,
        existing_categories=categories
    )
    
    cold_time = time.time() - start_time
    print(f"   ⏱️  Time: {cold_time:.2f}s")
    print(f"   📝 Category: {suggestion.category}")
    print(f"   📝 Title: {suggestion.title}")
    print(f"   📊 Categories fetched: {len(categories)}")
    
    # **Test 2: Warm cache**
    print("\n2. 🔥 Warm cache (categories cached)")
    
    start_time = time.time()
    
    # Fetch categories (will use cache)
    cached_categories = await extract_existing_categories(settings.notion_token, settings.notion_database_id)
    
    # Get AI suggestion
    suggestion2 = await category_ai.suggest_category(
        content=test_content,
        existing_categories=cached_categories
    )
    
    warm_time = time.time() - start_time
    print(f"   ⏱️  Time: {warm_time:.2f}s")
    print(f"   📝 Category: {suggestion2.category}")
    print(f"   📝 Title: {suggestion2.title}")
    print(f"   📊 Categories from cache: {len(cached_categories)}")
    
    # **Test 3: True parallel execution (like in production)**
    print("\n3. ⚡ True parallel execution")
    clear_category_cache()
    
    start_time = time.time()
    
    # Simulate the true parallel execution from the API
    async def fetch_categories():
        return await extract_existing_categories(settings.notion_token, settings.notion_database_id)
    
    async def get_ai_suggestion(categories_list):
        return await category_ai.suggest_category(
            content=test_content,
            existing_categories=categories_list
        )
    
    # True parallel: start both simultaneously
    categories_task = asyncio.create_task(fetch_categories())
    ai_task = asyncio.create_task(get_ai_suggestion([]))  # Start AI with empty list
    
    print(f"   🚀 Started both operations simultaneously...")
    
    # Wait for both to complete
    done, pending = await asyncio.wait(
        [categories_task, ai_task], 
        timeout=5.0,
        return_when=asyncio.ALL_COMPLETED
    )
    
    # Get results
    if categories_task.done() and not categories_task.exception():
        parallel_categories = await categories_task
        print(f"   📦 Categories completed: {len(parallel_categories)} found")
    else:
        parallel_categories = ["General", "Research", "Development"]
        print(f"   📦 Categories failed, using defaults")
        
    if ai_task.done() and not ai_task.exception():
        suggestion3 = await ai_task
        print(f"   🤖 AI completed successfully")
    else:
        # AI failed, fallback
        print(f"   🤖 AI failed, using fallback")
        suggestion3 = await get_ai_suggestion(parallel_categories)
    
    # Cancel any pending tasks
    for task in pending:
        task.cancel()
    
    parallel_time = time.time() - start_time
    print(f"   ⏱️  Time: {parallel_time:.2f}s")
    print(f"   📝 Category: {suggestion3.category}")
    print(f"   📝 Title: {suggestion3.title}")
    print(f"   📊 Categories: {len(parallel_categories)}")
    
    # **Performance Summary**
    print("\n📊 Performance Summary")
    print("-" * 30)
    print(f"Cold start:          {cold_time:.2f}s")
    print(f"With cache:          {warm_time:.2f}s")
    print(f"True parallel:       {parallel_time:.2f}s")
    
    cache_improvement = ((cold_time - warm_time) / cold_time) * 100
    parallel_improvement = ((cold_time - parallel_time) / cold_time) * 100
    
    print(f"\n🎯 Improvements:")
    print(f"Cache saves:         {cache_improvement:.1f}%")
    print(f"Parallel approach:   {parallel_improvement:.1f}%")
    
    best_time = min(warm_time, parallel_time)
    if best_time < 2.0:
        print("✅ Excellent performance! Under 2 seconds")
    elif best_time < 3.0:
        print("✅ Good performance! Under 3 seconds")
    else:
        print("⚠️  Consider further optimizations")
        
    print(f"\n🏆 Best approach: {'Cache' if warm_time < parallel_time else 'Parallel'} ({best_time:.2f}s)")

if __name__ == "__main__":
    asyncio.run(test_performance_improvements())
