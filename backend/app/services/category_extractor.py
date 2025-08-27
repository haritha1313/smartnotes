"""
Category extraction service for reading existing categories from Notion database
"""
import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from notion_client import Client
from notion_client.errors import APIResponseError, RequestTimeoutError

from app.services.notion_service import NotionService, NotionServiceError, NotionServiceContext

logger = logging.getLogger(__name__)

# In-memory cache for categories
_category_cache = {}
_cache_expiry = {}
CACHE_DURATION_MINUTES = 10  # Cache categories for 10 minutes


async def extract_existing_categories(notion_token: str, database_id: str, use_cache: bool = True) -> List[str]:
    """
    Extract existing category options from Notion database's Category select property.
    Uses in-memory caching to reduce API calls.
    
    Args:
        notion_token: Notion integration token
        database_id: ID of the Research Notes database
        use_cache: Whether to use cached results (default: True)
        
    Returns:
        List of category names as strings
        
    Raises:
        NotionServiceError: If unable to read database or extract categories
    """
    cache_key = f"{database_id}"
    
    # Check cache first
    if use_cache and cache_key in _category_cache:
        expiry_time = _cache_expiry.get(cache_key)
        if expiry_time and datetime.now() < expiry_time:
            logger.info(f"Using cached categories for database {database_id}")
            return _category_cache[cache_key]
        else:
            # Cache expired, remove it
            logger.info(f"Category cache expired for database {database_id}")
            _category_cache.pop(cache_key, None)
            _cache_expiry.pop(cache_key, None)
    
    logger.info(f"Fetching fresh categories from Notion database {database_id}")
    
    try:
        async with NotionServiceContext(notion_token) as notion:
            # Get database schema to read Category property options
            database_info = await notion._make_request(
                notion.client.databases.retrieve,
                database_id=database_id
            )
            
            # Extract Category property information
            properties = database_info.get("properties", {})
            category_property = properties.get("Category", {})
            
            if not category_property:
                logger.warning("No Category property found in database")
                return ["General"]  # Default fallback
            
            # Check if it's a select property
            if category_property.get("type") != "select":
                logger.warning("Category property is not a select type")
                return ["General"]
            
            # Extract options from select property
            select_options = category_property.get("select", {}).get("options", [])
            categories = []
            
            for option in select_options:
                category_name = option.get("name", "").strip()
                if category_name:
                    categories.append(category_name)
            
            # Ensure we always have at least one category
            if not categories:
                categories = ["General"]
            
            # Cache the results
            if use_cache:
                _category_cache[cache_key] = categories
                _cache_expiry[cache_key] = datetime.now() + timedelta(minutes=CACHE_DURATION_MINUTES)
                logger.info(f"Cached {len(categories)} categories for {CACHE_DURATION_MINUTES} minutes")
            
            logger.info(f"Extracted {len(categories)} categories from database: {categories}")
            return categories
            
    except APIResponseError as e:
        if hasattr(e, 'status') and e.status == 404:
            raise NotionServiceError(f"Database not found: {database_id}")
        elif hasattr(e, 'status') and e.status == 403:
            raise NotionServiceError(f"Permission denied for database: {database_id}")
        else:
            raise NotionServiceError(f"Notion API error: {str(e)}")
    
    except Exception as e:
        logger.error(f"Failed to extract categories from database {database_id}: {e}")
        raise NotionServiceError(f"Category extraction failed: {str(e)}")


def clear_category_cache(database_id: Optional[str] = None):
    """Clear category cache for specific database or all databases"""
    global _category_cache, _cache_expiry
    
    if database_id:
        cache_key = f"{database_id}"
        _category_cache.pop(cache_key, None)
        _cache_expiry.pop(cache_key, None)
        logger.info(f"Cleared category cache for database {database_id}")
    else:
        _category_cache.clear()
        _cache_expiry.clear()
        logger.info("Cleared all category cache")


async def warm_category_cache(notion_token: str, database_id: str) -> bool:
    """Pre-warm the category cache for faster subsequent requests"""
    try:
        await extract_existing_categories(notion_token, database_id, use_cache=False)
        logger.info(f"Warmed category cache for database {database_id}")
        return True
    except Exception as e:
        logger.warning(f"Failed to warm category cache: {e}")
        return False


async def get_categories_with_counts(notion_token: str, database_id: str) -> Dict[str, int]:
    """
    Get existing categories with usage counts from the database.
    
    Args:
        notion_token: Notion integration token  
        database_id: ID of the Research Notes database
        
    Returns:
        Dictionary mapping category names to usage counts
    """
    try:
        async with NotionServiceContext(notion_token) as notion:
            # First get the available categories
            categories = await extract_existing_categories(notion_token, database_id)
            
            # Initialize counts
            category_counts = {cat: 0 for cat in categories}
            
            # Query database pages to count category usage
            # Note: We'll implement a simple count here, but in production
            # you might want to paginate through all results
            has_more = True
            start_cursor = None
            
            while has_more:
                query_params = {
                    "database_id": database_id,
                    "page_size": 100  # Max allowed by Notion API
                }
                
                if start_cursor:
                    query_params["start_cursor"] = start_cursor
                
                response = await notion._make_request(
                    notion.client.databases.query,
                    **query_params
                )
                
                # Count categories in this batch
                pages = response.get("results", [])
                for page in pages:
                    properties = page.get("properties", {})
                    category_prop = properties.get("Category", {})
                    
                    if category_prop.get("type") == "select":
                        category_data = category_prop.get("select")
                        if category_data and category_data.get("name"):
                            category_name = category_data["name"]
                            if category_name in category_counts:
                                category_counts[category_name] += 1
                
                has_more = response.get("has_more", False)
                start_cursor = response.get("next_cursor")
            
            logger.info(f"Category usage counts: {category_counts}")
            return category_counts
            
    except Exception as e:
        logger.error(f"Failed to get category counts: {e}")
        # Fallback to basic categories without counts
        basic_categories = await extract_existing_categories(notion_token, database_id)
        return {cat: 0 for cat in basic_categories}


async def add_category_to_database(notion_token: str, database_id: str, new_category: str, color: str = "default") -> bool:
    """
    Add a new category option to the database's Category select property.
    
    Args:
        notion_token: Notion integration token
        database_id: ID of the Research Notes database  
        new_category: Name of the new category to add
        color: Color for the new category option
        
    Returns:
        True if successful, False otherwise
    """
    try:
        async with NotionServiceContext(notion_token) as notion:
            # Get current database schema
            database_info = await notion._make_request(
                notion.client.databases.retrieve,
                database_id=database_id
            )
            
            properties = database_info.get("properties", {})
            category_property = properties.get("Category", {})
            
            if not category_property or category_property.get("type") != "select":
                logger.error("No valid Category select property found")
                return False
            
            # Get existing options
            current_options = category_property.get("select", {}).get("options", [])
            
            # Check if category already exists
            for option in current_options:
                if option.get("name", "").lower() == new_category.lower():
                    logger.info(f"Category '{new_category}' already exists")
                    return True
            
            # Add new option
            new_option = {
                "name": new_category.strip(),
                "color": color
            }
            updated_options = current_options + [new_option]
            
            # Update database schema
            await notion._make_request(
                notion.client.databases.update,
                database_id=database_id,
                properties={
                    "Category": {
                        "select": {
                            "options": updated_options
                        }
                    }
                }
            )
            
            logger.info(f"Successfully added category '{new_category}' to database")
            return True
            
    except Exception as e:
        logger.error(f"Failed to add category '{new_category}': {e}")
        return False


# Helper function for testing
async def test_category_extraction(notion_token: str, database_id: str) -> None:
    """
    Test function to verify category extraction works correctly.
    """
    try:
        print(f"Testing category extraction for database: {database_id}")
        
        # Test basic extraction
        categories = await extract_existing_categories(notion_token, database_id)
        print(f"✅ Extracted categories: {categories}")
        
        # Test with counts
        category_counts = await get_categories_with_counts(notion_token, database_id)
        print(f"✅ Category usage counts: {category_counts}")
        
        print("✅ Category extraction test completed successfully")
        
    except Exception as e:
        print(f"❌ Category extraction test failed: {e}")
        raise


if __name__ == "__main__":
    import asyncio
    import sys
    import os
    
    # Add parent directory to path to import config
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
    
    from app.config import settings
    
    # This allows testing the module directly using .env config
    async def main():
        print("🔍 Testing category extraction using .env config...")
        
        if not settings.notion_token:
            print("❌ NOTION_TOKEN not found in .env file")
            print("Please add: NOTION_TOKEN=your_token_here")
            return
        
        if not settings.notion_database_id:
            print("❌ NOTION_DATABASE_ID not found in .env file") 
            print("Please add: NOTION_DATABASE_ID=your_database_id_here")
            return
        
        await test_category_extraction(settings.notion_token, settings.notion_database_id)
    
    asyncio.run(main())
