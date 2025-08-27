"""
Test script specifically for Claude API categorization
"""
import asyncio
import json
import sys
import os

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.services.ai_categorization import get_category_ai, ClaudeClient, CategoryAI
from app.config import settings

async def test_claude_direct():
    """Test Claude API directly"""
    print("🔍 Testing Claude API directly...")
    
    # Check if Claude API key is configured
    if not settings.claude_api_key:
        print("❌ CLAUDE_API_KEY not found in .env file")
        print("Please add to your .env file:")
        print("CLAUDE_API_KEY=your_api_key_here")
        return False
    
    print(f"✅ Claude API key found (starts with: {settings.claude_api_key[:8]}...)")
    print(f"✅ Using model: {settings.claude_model}")
    
    try:
        # Create Claude client directly
        claude = ClaudeClient(
            api_key=settings.claude_api_key,
            model=settings.claude_model
        )
        
        # Test availability
        print("\n1. Testing Claude API availability...")
        is_available = await claude.is_available()
        if not is_available:
            print("❌ Claude API not available")
            return False
        
        print("✅ Claude API is available")
        
        # Test text generation
        print("\n2. Testing Claude text generation...")
        test_prompt = """Analyze this content and suggest a category.

Content: Today's AI assistants are lackluster in comparison to what we could build with proper real-time reasoning capabilities

User Comment: relevant to recent work

Existing Categories: real time reasoning, implementing notion integrations, pricing strategy

Respond in this exact format:
Category: [category name]
Confidence: [0.0-1.0]
Reasoning: [brief explanation]"""
        
        response = await claude.generate_text(
            prompt=test_prompt,
            system_prompt="You are a helpful assistant that categorizes content accurately."
        )
        
        print(f"✅ Claude response: {response}")
        
        # Test if response contains expected format
        if "Category:" in response and "Confidence:" in response:
            print("✅ Response format looks correct")
            return True
        else:
            print("⚠️  Response format unexpected, but Claude is working")
            return True
            
    except Exception as e:
        print(f"❌ Claude test failed: {e}")
        return False

async def test_category_ai_with_claude():
    """Test CategoryAI with Claude provider"""
    print("\n🔍 Testing CategoryAI with Claude provider...")
    
    try:
        # Create CategoryAI instance with Claude
        claude_client = ClaudeClient(
            api_key=settings.claude_api_key,
            model=settings.claude_model
        )
        
        category_ai = CategoryAI(
            provider="claude",
            claude_client=claude_client
        )
        
        # Test categorization
        test_content = "Today's assistants are lackluster in comparison to what we could build with proper real-time reasoning capabilities"
        test_comment = "relevant to recent work"
        test_categories = ["real time reasoning", "implementing notion integrations", "pricing strategy"]
        
        print(f"Testing categorization for: {test_content[:50]}...")
        
        suggestion = await category_ai.suggest_category(
            content=test_content,
            comment=test_comment,
            existing_categories=test_categories
        )
        
        print(f"✅ Suggested title: {suggestion.title}")
        print(f"✅ Suggested category: {suggestion.category}")
        print(f"✅ Confidence: {suggestion.confidence}")
        print(f"✅ Is new: {suggestion.is_new}")
        print(f"✅ Reasoning: {suggestion.reasoning}")
        
        # Expected results for this test case
        expected_suggestions = ["ai assistants", "real time reasoning", "ai research", "ai development"]
        is_good_suggestion = any(
            expected.lower() in suggestion.category.lower() 
            for expected in expected_suggestions
        )
        
        if is_good_suggestion:
            print("🎉 Claude suggestion looks excellent!")
        else:
            print(f"⚠️  Unexpected but potentially valid suggestion: {suggestion.category}")
        
        return suggestion
        
    except Exception as e:
        print(f"❌ CategoryAI with Claude failed: {e}")
        return None

async def test_configured_ai():
    """Test the configured AI system"""
    print("\n🔍 Testing configured AI system (should use Claude)...")
    
    try:
        # This should automatically use Claude based on config
        category_ai = get_category_ai()
        
        suggestion = await category_ai.suggest_category(
            content="This is a research paper about machine learning optimization techniques",
            comment="found this interesting",
            existing_categories=["Research", "Development", "Articles", "AI"]
        )
        
        print(f"✅ Config-based title: {suggestion.title}")
        print(f"✅ Config-based category: {suggestion.category}")
        print(f"✅ Confidence: {suggestion.confidence}")
        print(f"✅ Claude enabled: {category_ai.use_claude}")
        
        return suggestion
        
    except Exception as e:
        print(f"❌ Configured AI test failed: {e}")
        return None

async def main():
    """Run all Claude tests"""
    print("🚀 Claude API Categorization Tests")
    print("=" * 50)
    
    # Test 1: Direct Claude API
    claude_works = await test_claude_direct()
    
    if claude_works:
        # Test 2: CategoryAI with Claude
        ai_suggestion = await test_category_ai_with_claude()
        
        # Test 3: Configured system
        config_suggestion = await test_configured_ai()
        
        if ai_suggestion and config_suggestion:
            print("\n🎉 All Claude tests passed successfully!")
            print("\nNext steps:")
            print("1. ✅ Add CLAUDE_API_KEY to your .env file if you haven't")
            print("2. ✅ Test the API endpoint")
            print("3. ✅ Move to Step 3: Browser extension integration")
            
            print(f"\n📋 Your .env should contain:")
            print(f"CLAUDE_API_KEY=your_api_key_here")
            print(f"AI_PROVIDER=claude")
            
        else:
            print("\n⚠️  Some tests failed, but Claude API is working")
    else:
        print("\n❌ Claude API not working. Check your API key and try again.")

if __name__ == "__main__":
    asyncio.run(main())
