"""
AI client service for categorization using Claude API with keyword fallback
"""
import asyncio
import logging
import json
import re
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import httpx
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Content-based caching for AI suggestions
_suggestion_cache = {}
_cache_expiry = {}
SUGGESTION_CACHE_DURATION_MINUTES = 30  # Cache suggestions for 30 minutes

# Optional import for Claude API
try:
    import anthropic
    CLAUDE_AVAILABLE = True
except ImportError:
    CLAUDE_AVAILABLE = False
    logger.warning("Anthropic library not installed. Claude API will not be available.")

@dataclass
class CategorySuggestion:
    """Data class for category suggestions"""
    category: str
    confidence: float
    is_new: bool
    title: str = ""  # Generated 3-5 word title
    reasoning: Optional[str] = None

# Ollama client removed - using Claude API only


class ClaudeClient:
    """Client for communicating with Claude API"""
    
    def __init__(self, api_key: str, model: str = "claude-3-haiku-20240307"):
        """Initialize Claude client"""
        if not CLAUDE_AVAILABLE:
            raise AIError("Anthropic library not installed. Run: pip install anthropic")
        
        if not api_key:
            raise AIError("Claude API key is required")
            
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.timeout = 30.0  # Claude is much faster than local models
        
    async def is_available(self) -> bool:
        """Check if Claude API is available"""
        try:
            # Test with a minimal request
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.client.messages.create,
                    model=self.model,
                    max_tokens=1,
                    messages=[{"role": "user", "content": "Hi"}]
                ),
                timeout=10.0
            )
            return response is not None
        except Exception as e:
            logger.error(f"Claude availability check failed: {e}")
            return False
    
    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate text using Claude API"""
        try:
            messages = [{"role": "user", "content": prompt}]
            
            request_params = {
                "model": self.model,
                "max_tokens": 150,  # Sufficient for categorization
                "messages": messages,
                "temperature": 0.1  # Very low temperature for maximum consistency
            }
            
            if system_prompt:
                request_params["system"] = system_prompt
            
            # Use asyncio.to_thread to run sync Claude API in async context
            response = await asyncio.wait_for(
                asyncio.to_thread(self.client.messages.create, **request_params),
                timeout=self.timeout
            )
            
            # Extract text from Claude response
            if response.content and len(response.content) > 0:
                return response.content[0].text.strip()
            else:
                raise AIError("Empty response from Claude API")
                
        except asyncio.TimeoutError:
            raise AIError(f"Claude API request timed out after {self.timeout} seconds")
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            raise AIError(f"Claude API request failed: {str(e)}")


class CategoryAI:
    """AI-powered categorization service using Claude API with keyword fallback"""
    
    def __init__(
        self, 
        claude_client: Optional[ClaudeClient] = None,
        use_claude: bool = True
    ):
        """Initialize categorization service"""
        self.claude = claude_client
        self.use_claude = use_claude and claude_client is not None
        
        logger.info(f"CategoryAI initialized with Claude: {self.use_claude}")
        
    def _create_categorization_prompt(
        self, 
        content: str, 
        comment: str, 
        existing_categories: List[str]
    ) -> str:
        """Create the prompt for category suggestion"""
        
        # Truncate content if too long to avoid token limits
        max_content_length = 1000
        if len(content) > max_content_length:
            content = content[:max_content_length] + "..."
        
        existing_cats_str = ", ".join(existing_categories) if existing_categories else "None"
        
        prompt = f"""You should STRONGLY PREFER existing categories, but can create new ones if content truly doesn't fit.

Content: {content}

User Comment: {comment}

EXISTING CATEGORIES (prefer these): {existing_cats_str}

DECISION PROCESS:
1. FIRST: Try to match content to existing categories (strongly preferred)
2. ONLY IF no existing category fits well: create a new descriptive category
3. Use high confidence (0.8+) for existing categories that fit
4. Use lower confidence (0.6-0.7) when creating new categories

EXISTING CATEGORY GUIDELINES:
- Research: studies, papers, analysis, investigations, data, experiments
- Development: coding, programming, software, apps, tech building, frameworks
- Articles: tutorials, guides, how-tos, blog posts, explanations, documentation
- Tech News: announcements, releases, industry news, updates
- General: miscellaneous content that doesn't fit specialized categories

EXAMPLES:
- "AI research paper" → "Research" (existing, confidence: 0.9)
- "Python tutorial" → "Articles" (existing, confidence: 0.9)  
- "Building a React app" → "Development" (existing, confidence: 0.9)
- "Cooking recipe" → "Cooking" (new category, confidence: 0.7)
- "Finance investing tips" → "Finance" (new category, confidence: 0.7)

CREATE NEW CATEGORY ONLY IF:
- Content is about a specialized domain not covered by existing categories
- New category would be genuinely useful for organizing similar future content
- Existing categories would be a poor fit (confidence < 0.5)

Respond EXACTLY in this format:
Title: [3-5 word title summarizing the content]
Category: [existing category name OR new descriptive category]
Confidence: [0.0-1.0, higher for existing categories]
Reasoning: [why you chose existing category OR why new category was needed]"""

        return prompt
    
    def _parse_ai_response(self, response: str, existing_categories: List[str]) -> CategorySuggestion:
        """Parse the AI response into a CategorySuggestion"""
        try:
            # Extract title
            title_match = re.search(r'Title:\s*(.+)', response, re.IGNORECASE)
            title = title_match.group(1).strip() if title_match else ""
            
            # Extract category
            category_match = re.search(r'Category:\s*(.+)', response, re.IGNORECASE)
            category = category_match.group(1).strip() if category_match else "General"
            
            # Extract confidence
            confidence_match = re.search(r'Confidence:\s*([\d.]+)', response, re.IGNORECASE)
            confidence = float(confidence_match.group(1)) if confidence_match else 0.5
            confidence = max(0.0, min(1.0, confidence))  # Clamp to 0-1 range
            
            # Extract reasoning
            reasoning_match = re.search(r'Reasoning:\s*(.+)', response, re.IGNORECASE)
            reasoning = reasoning_match.group(1).strip() if reasoning_match else None
            
            # FORCE existing category if close match exists
            category_match = None
            category_lower = category.lower()
            
            for existing_cat in existing_categories:
                existing_lower = existing_cat.lower()
                
                # Exact match
                if existing_lower == category_lower:
                    category_match = existing_cat
                    break
                
                # If AI suggests "Physics Research" and "Research" exists, use "Research" 
                if "research" in category_lower and "research" in existing_lower:
                    category_match = existing_cat
                    break
                    
                # If AI suggests "Software Development" and "Development" exists
                if "development" in category_lower and "development" in existing_lower:
                    category_match = existing_cat
                    break
                    
                # If AI suggests "Blog Article" and "Articles" exists
                if ("article" in category_lower or "blog" in category_lower) and "article" in existing_lower:
                    category_match = existing_cat
                    break
            
            if category_match:
                original_category = category
                category = category_match
                logger.warning(f"🔄 FORCED category match: '{category}' (was '{original_category}')")
            
            # Smart category validation - prefer existing but allow new ones
            category_lower = category.lower()
            existing_match = None
            
            # Check for exact or close matches with existing categories
            for existing_cat in existing_categories:
                existing_lower = existing_cat.lower()
                
                # Exact match - use existing
                if existing_lower == category_lower:
                    existing_match = existing_cat
                    break
                
                # Smart partial matching - only for very similar cases
                if confidence > 0.7:  # Only do smart matching for high confidence
                    # "Machine Learning" → "Research" if it contains research keywords
                    if ("research" in category_lower or "study" in category_lower or "analysis" in category_lower) and "research" in existing_lower:
                        existing_match = existing_cat
                        logger.info(f"🔍 Smart match: '{category}' → '{existing_cat}' (research-related)")
                        break
                    
                    # "Web Development" → "Development" 
                    if ("development" in category_lower or "programming" in category_lower) and "development" in existing_lower:
                        existing_match = existing_cat
                        logger.info(f"🔍 Smart match: '{category}' → '{existing_cat}' (development-related)")
                        break
                    
                    # "Tech Article" → "Articles"
                    if ("article" in category_lower or "tutorial" in category_lower or "guide" in category_lower) and "article" in existing_lower:
                        existing_match = existing_cat
                        logger.info(f"🔍 Smart match: '{category}' → '{existing_cat}' (article-related)")
                        break
            
            # Use existing category if found, otherwise allow new category
            if existing_match:
                original_category = category
                category = existing_match
                logger.info(f"✅ Using existing category: '{category}' (was '{original_category}')")
            else:
                logger.info(f"🆕 Creating new category: '{category}'")
            
            # Check if category is new
            is_new = category.lower() not in [cat.lower() for cat in existing_categories]
            
            # Clean up category name
            category = category.strip('"\'')  # Remove quotes
            category = re.sub(r'[^\w\s&.-]', '', category)  # Remove special chars except common ones
            category = ' '.join(category.split())  # Normalize whitespace
            
            # Clean up title
            title = title.strip('"\'')  # Remove quotes
            
            if not category or len(category) > 50:
                category = "General"
                is_new = False
                confidence = 0.3
            
            return CategorySuggestion(
                category=category,
                confidence=confidence,
                is_new=is_new,
                title=title,
                reasoning=reasoning
            )
            
        except Exception as e:
            logger.error(f"Failed to parse AI response: {e}")
            logger.error(f"AI response was: {response}")
            
            # Fallback
            return CategorySuggestion(
                category="General",
                confidence=0.2,
                is_new=False,
                title="Saved Content",
                reasoning="Failed to parse AI response"
            )
    
    def _get_content_cache_key(self, content: str, comment: str, existing_categories: List[str]) -> str:
        """Generate cache key based on content + existing categories"""
        # Normalize content for consistent caching
        normalized_content = ' '.join(content.lower().split())
        normalized_comment = ' '.join(comment.lower().split()) if comment else ""
        categories_str = ','.join(sorted([cat.lower() for cat in existing_categories]))
        
        # Create hash of combined content
        combined = f"{normalized_content}|{normalized_comment}|{categories_str}"
        return hashlib.md5(combined.encode()).hexdigest()
    
    async def suggest_category(
        self, 
        content: str, 
        comment: str = "", 
        existing_categories: List[str] = None
    ) -> CategorySuggestion:
        """Suggest a category for the given content using Claude API or keyword fallback"""
        
        if existing_categories is None:
            existing_categories = []
        
        # Check cache first for identical content
        cache_key = self._get_content_cache_key(content, comment, existing_categories)
        
        if cache_key in _suggestion_cache:
            expiry_time = _cache_expiry.get(cache_key)
            if expiry_time and datetime.now() < expiry_time:
                cached_suggestion = _suggestion_cache[cache_key]
                logger.info(f"Using cached suggestion: {cached_suggestion.category} (confidence: {cached_suggestion.confidence})")
                return cached_suggestion
            else:
                # Cache expired
                _suggestion_cache.pop(cache_key, None)
                _cache_expiry.pop(cache_key, None)
        
        # Not in cache, generate new suggestion
        suggestion = None
        
        # Try Claude first if available
        if self.use_claude and self.claude:
            try:
                logger.info("Using Claude API for categorization")
                suggestion = await self._categorize_with_claude(content, comment, existing_categories)
            except Exception as e:
                logger.warning(f"Claude categorization failed, using keyword fallback: {e}")
        
        # Fallback to keyword matching if Claude failed
        if suggestion is None:
            logger.info("Using keyword fallback for categorization")
            suggestion = self._fallback_categorization(content, comment, existing_categories)
        
        # Cache the suggestion
        _suggestion_cache[cache_key] = suggestion
        _cache_expiry[cache_key] = datetime.now() + timedelta(minutes=SUGGESTION_CACHE_DURATION_MINUTES)
        logger.info(f"Cached new suggestion: {suggestion.category} for {SUGGESTION_CACHE_DURATION_MINUTES} minutes")
        
        return suggestion
    
    async def _categorize_with_claude(
        self, 
        content: str, 
        comment: str, 
        existing_categories: List[str]
    ) -> CategorySuggestion:
        """Categorize using Claude API"""
        if not self.claude:
            raise AIError("Claude client not configured")
        
        # Check availability
        if not await self.claude.is_available():
            raise AIError("Claude API not available")
        
        # Create prompt
        prompt = self._create_categorization_prompt(content, comment, existing_categories)
        system_prompt = "You are a helpful assistant that categorizes content accurately and concisely. Follow the format exactly."
        
        # Get Claude response
        ai_response = await self.claude.generate_text(prompt, system_prompt)
        
        # Parse response
        suggestion = self._parse_ai_response(ai_response, existing_categories)
        logger.info(f"Claude suggested category: {suggestion.category} (confidence: {suggestion.confidence})")
        return suggestion
    
# Ollama categorization method removed - using Claude API only
    
    def _fallback_categorization(
        self, 
        content: str, 
        comment: str, 
        existing_categories: List[str]
    ) -> CategorySuggestion:
        """Fallback categorization using simple keyword matching"""
        
        content_lower = content.lower()
        comment_lower = comment.lower() if comment else ""
        text = f"{content_lower} {comment_lower}"
        
        # IMPROVED: Match against existing categories first
        best_match = None
        best_confidence = 0.0
        
        # First: Try to match existing categories with keywords
        category_keywords = {
            # Development related
            ["development", "dev", "programming", "coding", "software"]: ["development", "coding", "programming", "software", "app", "code", "git", "github"],
            ["research"]: ["research", "study", "analysis", "experiment", "investigation", "paper", "academic"],
            ["articles", "blog", "tutorial"]: ["article", "blog", "post", "tutorial", "guide", "how to", "tips"],
            ["tech", "news", "technology"]: ["news", "announcement", "release", "update", "tech", "technology"],
            ["ai", "machine learning", "ml"]: ["ai", "artificial intelligence", "machine learning", "ml", "neural", "gpt", "llm", "model"],
            ["notion", "productivity"]: ["notion", "productivity", "organize", "database", "workspace"],
            ["general", "misc", "other"]: []  # Catch-all
        }
        
        # Find best matching existing category
        for category in existing_categories:
            category_lower = category.lower()
            
            # Direct text similarity
            if category_lower in text:
                best_match = category
                best_confidence = 0.9
                break
            
            # Keyword matching
            for category_patterns, keywords in category_keywords.items():
                if any(pattern in category_lower for pattern in category_patterns):
                    score = sum(1 for keyword in keywords if keyword in text)
                    if score > 0:
                        confidence = min(0.85, 0.5 + score * 0.1)
                        if confidence > best_confidence:
                            best_match = category
                            best_confidence = confidence
        
        # If no existing category matches well, use fallback
        if not best_match:
            best_match = existing_categories[0] if existing_categories else "General"
            best_confidence = 0.4
        
        # Check if it's a new category
        is_new = best_match.lower() not in [cat.lower() for cat in existing_categories]
        
        # Generate simple title (first few words of content)
        content_words = content.split()[:4]  # Take first 4 words
        simple_title = ' '.join(content_words).title()
        if len(simple_title) > 30:
            simple_title = simple_title[:27] + "..."
        if not simple_title:
            simple_title = "Saved Content"
        
        return CategorySuggestion(
            category=best_match,
            confidence=best_confidence,
            is_new=is_new,
            title=simple_title,
            reasoning="Generated using keyword matching (AI unavailable)"
        )


class AIError(Exception):
    """Custom exception for AI-related errors"""
    pass


# Global instance for reuse
_category_ai_instance = None

def get_category_ai() -> CategoryAI:
    """Get global CategoryAI instance with Claude API"""
    global _category_ai_instance
    if _category_ai_instance is None:
        # Import here to avoid circular imports
        try:
            from app.config import settings
            
            logger.info("Initializing CategoryAI with Claude API")
            
            # Initialize Claude client if API key is available
            claude_client = None
            if settings.claude_api_key:
                try:
                    claude_client = ClaudeClient(
                        api_key=settings.claude_api_key,
                        model=settings.claude_model
                    )
                    logger.info("Claude client initialized successfully")
                except Exception as e:
                    logger.warning(f"Failed to initialize Claude client: {e}")
            else:
                logger.warning("No Claude API key found in config - using keyword fallback only")
            
            # Create CategoryAI instance
            _category_ai_instance = CategoryAI(
                claude_client=claude_client,
                use_claude=claude_client is not None
            )
            
        except ImportError:
            # Fallback if config not available
            logger.warning("Config not available, using keyword fallback CategoryAI")
            _category_ai_instance = CategoryAI(use_claude=False)
            
    return _category_ai_instance


# Test function
async def test_categorization():
    """Test the categorization system"""
    try:
        print("🔍 Testing Ollama categorization...")
        
        category_ai = get_category_ai()
        
        # Check availability
        is_available = await category_ai.ollama.is_available()
        print(f"Ollama/Phi3 available: {is_available}")
        
        # Test categorization
        test_content = "Today's AI assistants are lackluster in comparison to what we could build with proper real-time reasoning capabilities"
        test_comment = "relevant to recent work"
        test_categories = ["real time reasoning", "implementing notion integrations", "pricing strategy"]
        
        print(f"\nTesting with content: {test_content[:50]}...")
        
        suggestion = await category_ai.suggest_category(
            content=test_content,
            comment=test_comment,
            existing_categories=test_categories
        )
        
        print(f"✅ Suggested category: {suggestion.category}")
        print(f"✅ Confidence: {suggestion.confidence}")
        print(f"✅ Is new: {suggestion.is_new}")
        print(f"✅ Reasoning: {suggestion.reasoning}")
        
        return suggestion
        
    except Exception as e:
        print(f"❌ Categorization test failed: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    asyncio.run(test_categorization())
