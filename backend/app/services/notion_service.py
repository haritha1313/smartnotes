"""
Notion API Service - High Performance Integration
Optimized for low latency and robust error handling
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from notion_client import Client
from notion_client.errors import RequestTimeoutError, APIResponseError
import httpx
from app.config import settings

logger = logging.getLogger(__name__)


class NotionRateLimiter:
    """Custom rate limiter for Notion API (3 requests per second)"""
    
    def __init__(self, requests_per_second: float = 3.0):
        self.requests_per_second = requests_per_second
        self.min_interval = 1.0 / requests_per_second
        self.last_request_time = 0.0
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        """Acquire permission to make a request"""
        async with self._lock:
            current_time = asyncio.get_event_loop().time()
            time_since_last = current_time - self.last_request_time
            
            if time_since_last < self.min_interval:
                sleep_time = self.min_interval - time_since_last
                await asyncio.sleep(sleep_time)
            
            self.last_request_time = asyncio.get_event_loop().time()


class NotionService:
    """High-performance Notion API service with error handling and rate limiting"""
    
    def __init__(self, token: str):
        """Initialize Notion service with authentication token"""
        if not token:
            raise ValueError("Notion token is required")
        
        self.client = Client(auth=token)
        self.rate_limiter = NotionRateLimiter()
        self.database_cache = {}  # Cache database IDs to avoid repeated lookups
        
        # Database schema for Research Notes
        self.database_schema = {
            "title": [{"text": {"content": "Research Notes"}}],
            "properties": {
                "Title": {"title": {}},
                "Content": {"rich_text": {}},
                "Comment": {"rich_text": {}},
                "Source": {"url": {}},
                "Captured": {"date": {}},
                "Category": {
                    "select": {
                        "options": [
                            {"name": "General", "color": "gray"},
                            {"name": "Research", "color": "blue"},
                            {"name": "Development", "color": "green"},
                            {"name": "Articles", "color": "yellow"},
                            {"name": "Tech News", "color": "orange"},
                            {"name": "Professional", "color": "red"},
                            {"name": "Discussion", "color": "purple"},
                            {"name": "Reference", "color": "pink"},
                            {"name": "Learning", "color": "brown"},
                            {"name": "Documents", "color": "default"},
                        ]
                    }
                },
                "Status": {
                    "select": {
                        "options": [
                            {"name": "New", "color": "red"},
                            {"name": "Reviewed", "color": "yellow"},
                            {"name": "Archived", "color": "gray"},
                        ]
                    }
                }
            }
        }
    
    async def _make_request(self, request_func, *args, **kwargs):
        """Make rate-limited request with retry logic"""
        await self.rate_limiter.acquire()
        
        max_retries = 3
        base_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                return request_func(*args, **kwargs)
            
            except RequestTimeoutError:
                if attempt == max_retries - 1:
                    raise
                delay = base_delay * (2 ** attempt)
                logger.warning(f"Notion API timeout, retrying in {delay}s (attempt {attempt + 1})")
                await asyncio.sleep(delay)
            
            except APIResponseError as e:
                if hasattr(e, 'status') and e.status == 429:  # Rate limited
                    if attempt == max_retries - 1:
                        raise
                    delay = base_delay * (2 ** attempt) + 5  # Extra delay for rate limits
                    logger.warning(f"Notion API rate limited, retrying in {delay}s")
                    await asyncio.sleep(delay)
                else:
                    raise
            
            except Exception as e:
                logger.error(f"Notion API error: {e}")
                if attempt == max_retries - 1:
                    raise
                delay = base_delay * (2 ** attempt)
                await asyncio.sleep(delay)
    
    async def create_database(self, parent_page_id: str, title: str = "Research Notes") -> str:
        """Create a new database in the user's Notion workspace"""
        try:
            # Check cache first
            cache_key = f"{parent_page_id}:{title}"
            if cache_key in self.database_cache:
                return self.database_cache[cache_key]
            
            # Update title in schema
            schema = self.database_schema.copy()
            schema["title"] = [{"text": {"content": title}}]
            
            response = await self._make_request(
                self.client.databases.create,
                parent={"page_id": parent_page_id},
                **schema
            )
            
            database_id = response["id"]
            self.database_cache[cache_key] = database_id
            
            logger.info(f"Created Notion database: {database_id}")
            return database_id
            
        except Exception as e:
            logger.error(f"Failed to create Notion database: {e}")
            raise NotionServiceError(f"Database creation failed: {str(e)}")
    
    async def create_note_page(self, database_id: str, note_data: Dict[str, Any]) -> str:
        """Create a new page in the Research Notes database"""
        try:
            # Validate required fields
            required_fields = ["text", "url", "title"]
            for field in required_fields:
                if not note_data.get(field):
                    raise ValueError(f"Missing required field: {field}")
            
            # Prepare page properties with content limits for performance
            text_content = str(note_data["text"])[:2000]  # Limit text length
            comment_content = str(note_data.get("comment", ""))[:500]  # Limit comment
            
            # Generate title from text content (first 100 chars)
            page_title = text_content[:100].strip()
            if len(text_content) > 100:
                page_title += "..."
            
            properties = {
                "Title": {
                    "title": [{"text": {"content": page_title}}]
                },
                "Content": {
                    "rich_text": [{"text": {"content": text_content}}]
                },
                "Source": {
                    "url": note_data["url"]
                },
                "Captured": {
                    "date": {"start": note_data.get("timestamp", datetime.utcnow().isoformat())}
                },
                "Category": {
                    "select": {"name": note_data.get("category", "General")}
                },
                "Status": {
                    "select": {"name": "New"}
                }
            }
            
            # Add comment if provided
            if comment_content:
                properties["Comment"] = {
                    "rich_text": [{"text": {"content": comment_content}}]
                }
            
            response = await self._make_request(
                self.client.pages.create,
                parent={"database_id": database_id},
                properties=properties
            )
            
            page_id = response["id"]
            logger.info(f"Created Notion page: {page_id}")
            return page_id
            
        except ValueError as e:
            raise NotionServiceError(f"Invalid note data: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to create Notion page: {e}")
            raise NotionServiceError(f"Page creation failed: {str(e)}")
    
    async def get_databases(self) -> List[Dict[str, Any]]:
        """Get list of databases accessible to the integration"""
        try:
            response = await self._make_request(
                self.client.search,
                filter={"property": "object", "value": "database"}
            )
            
            return response.get("results", [])
            
        except Exception as e:
            logger.error(f"Failed to get databases: {e}")
            raise NotionServiceError(f"Database lookup failed: {str(e)}")
    
    async def test_connection(self) -> bool:
        """Test if the Notion API connection is working"""
        try:
            await self._make_request(self.client.users.me)
            return True
        except Exception as e:
            logger.error(f"Notion connection test failed: {e}")
            return False


class NotionServiceError(Exception):
    """Custom exception for Notion service errors"""
    pass


def create_notion_service(token: str) -> NotionService:
    """Factory function to create Notion service with validation"""
    if not token:
        raise ValueError("Notion token is required")
    
    if len(token) < 10:  # Basic validation
        raise ValueError("Invalid Notion token format")
    
    return NotionService(token)


# Async context manager for temporary Notion service
class NotionServiceContext:
    """Context manager for Notion service operations"""
    
    def __init__(self, token: str):
        self.token = token
        self.service = None
    
    async def __aenter__(self):
        self.service = create_notion_service(self.token)
        # Test connection on entry
        if not await self.service.test_connection():
            raise NotionServiceError("Failed to connect to Notion API")
        return self.service
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Cleanup if needed
        self.service = None


# Utility functions for common operations
async def quick_create_note(token: str, database_id: str, note_data: Dict[str, Any]) -> str:
    """Quick utility to create a note with minimal setup"""
    async with NotionServiceContext(token) as notion:
        return await notion.create_note_page(database_id, note_data)


async def setup_user_workspace(token: str, parent_page_id: str) -> str:
    """Setup a new user's workspace with Research Notes database"""
    async with NotionServiceContext(token) as notion:
        return await notion.create_database(parent_page_id, "Research Notes")
