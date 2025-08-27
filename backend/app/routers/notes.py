"""
Notes API router with optimized endpoints for low latency and security
"""
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Depends, status, Header, Request
from fastapi.responses import ORJSONResponse
import uuid
import orjson
import logging
import asyncio

from app.schemas.note import (
    NoteCreate, 
    NoteResponse, 
    NoteUpdate, 
    NotesListResponse,
    ApiResponse,
    ErrorResponse
)
from app.config import settings
from app.services.notion_service import NotionServiceContext, NotionServiceError
from app.services.ai_categorization import get_category_ai, CategorySuggestion
from app.services.category_extractor import extract_existing_categories, warm_category_cache, clear_category_cache

logger = logging.getLogger(__name__)

# Use ORJSONResponse for faster JSON serialization
router = APIRouter(
    prefix="/api/notes",
    tags=["notes"],
    default_response_class=ORJSONResponse,
    responses={
        400: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    }
)

# In-memory storage for now (will be replaced with database in Step 5)
notes_storage: dict = {}


async def sync_to_notion(note_data: dict, notion_token: str = None, database_id: str = None) -> Optional[str]:
    """Async function to sync note to Notion (non-blocking)"""
    if not notion_token or not database_id:
        return None
    
    try:
        async with NotionServiceContext(notion_token) as notion:
            page_id = await notion.create_note_page(database_id, note_data)
            logger.info(f"Note synced to Notion: {page_id}")
            return page_id
    except NotionServiceError as e:
        logger.warning(f"Notion sync failed (non-critical): {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected Notion sync error: {e}")
        return None


def generate_note_id() -> str:
    """Generate a secure, unique note ID"""
    return str(uuid.uuid4())


def validate_note_id(note_id: str) -> str:
    """Validate note ID format"""
    try:
        uuid.UUID(note_id)
        return note_id
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid note ID format"
        )


@router.post("/", 
             response_model=ApiResponse,
             status_code=status.HTTP_201_CREATED,
             summary="Create a new note",
             description="Create a new note with captured text and optional comment")
async def create_note(
    note_data: NoteCreate,
    request: Request,
    notion_token: Optional[str] = Header(None, alias="X-Notion-Token", description="Optional Notion integration token"),
    notion_database_id: Optional[str] = Header(None, alias="X-Notion-Database-Id", description="Optional Notion database ID")
) -> ORJSONResponse:
    """
    Create a new note with security validation and fast response
    Optionally syncs to Notion if credentials provided
    """
    # Debug: Log ALL received headers
    logger.info(f"🔍 ALL REQUEST HEADERS: {dict(request.headers)}")
    logger.info(f"Received Notion headers - Token: {'present' if notion_token else 'missing'}, Database: {'present' if notion_database_id else 'missing'}")
    if notion_token:
        logger.info(f"Token starts with: {notion_token[:10]}...")
    if notion_database_id:
        logger.info(f"Database ID: {notion_database_id}")
    
    try:
        # Generate unique ID
        note_id = generate_note_id()
        current_time = datetime.utcnow()
        
        # Create note record
        note_record = {
            "id": note_id,
            "text": note_data.text,
            "comment": note_data.comment,
            "url": str(note_data.url),
            "title": note_data.title,
            "category": note_data.category or "General",
            "timestamp": note_data.timestamp or current_time,
            "created_at": current_time,
            "updated_at": current_time,
            "sync_status": "local"  # Start as local, update if Notion sync succeeds
        }
        
        # Store note locally first (always succeeds)
        notes_storage[note_id] = note_record
        
        # Prepare response data
        response_data = {
            "note_id": note_id,
            "created_at": current_time.isoformat(),
            "sync_status": "local"
        }
        
        # Attempt Notion sync asynchronously (non-blocking)
        if notion_token and notion_database_id:
            logger.info(f"Attempting Notion sync for note {note_id}")
            
            # Start Notion sync in background
            notion_data = {
                "text": note_data.text,
                "comment": note_data.comment,
                "url": str(note_data.url),
                "title": note_data.title,
                "category": note_data.category or "General",
                "timestamp": (note_data.timestamp or current_time).isoformat()
            }
            
            # Non-blocking Notion sync
            try:
                # Use asyncio.create_task for true background execution
                notion_task = asyncio.create_task(
                    sync_to_notion(notion_data, notion_token, notion_database_id)
                )
                
                # Give Notion sync a very brief moment to complete (max 1 second)
                try:
                    notion_page_id = await asyncio.wait_for(notion_task, timeout=1.0)
                    if notion_page_id:
                        # Update note record with Notion success
                        note_record["sync_status"] = "notion_synced"
                        note_record["notion_page_id"] = notion_page_id
                        notes_storage[note_id] = note_record
                        response_data["sync_status"] = "notion_synced"
                        response_data["notion_page_id"] = notion_page_id
                        logger.info(f"Note {note_id} synced to Notion: {notion_page_id}")
                    
                except asyncio.TimeoutError:
                    # Notion sync taking too long, continue in background
                    logger.info(f"Notion sync timeout for note {note_id}, continuing in background")
                    response_data["sync_status"] = "notion_pending"
                    
                    # Update status when background task completes
                    def update_on_completion(task):
                        try:
                            page_id = task.result()
                            if page_id:
                                note_record["sync_status"] = "notion_synced"
                                note_record["notion_page_id"] = page_id
                                notes_storage[note_id] = note_record
                        except Exception as e:
                            logger.error(f"Background Notion sync failed for {note_id}: {e}")
                            note_record["sync_status"] = "notion_failed"
                            notes_storage[note_id] = note_record
                    
                    notion_task.add_done_callback(update_on_completion)
                    
            except Exception as e:
                logger.warning(f"Notion sync setup failed for note {note_id}: {e}")
                response_data["sync_status"] = "notion_failed"
        
        # Fast response regardless of Notion status
        return ORJSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "success": True,
                "message": "Note created successfully", 
                "data": response_data
            }
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid data: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create note"
        )


@router.get("/",
            response_model=NotesListResponse,
            summary="Get notes list",
            description="Retrieve notes with optional filtering and pagination")
async def get_notes(
    page: int = Query(1, ge=1, le=1000, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    category: Optional[str] = Query(None, max_length=50, description="Filter by category"),
    search: Optional[str] = Query(None, max_length=100, description="Search in text/comment")
) -> ORJSONResponse:
    """
    Get notes with efficient pagination and filtering
    """
    try:
        # Convert storage to list for processing
        all_notes = list(notes_storage.values())
        
        # Apply filters
        filtered_notes = all_notes
        
        if category:
            filtered_notes = [n for n in filtered_notes if n.get("category", "").lower() == category.lower()]
        
        if search:
            search_lower = search.lower()
            filtered_notes = [
                n for n in filtered_notes 
                if (search_lower in n.get("text", "").lower() or 
                    search_lower in n.get("comment", "").lower() or
                    search_lower in n.get("title", "").lower())
            ]
        
        # Sort by created_at (newest first)
        filtered_notes.sort(key=lambda x: x.get("created_at", datetime.min), reverse=True)
        
        # Pagination
        total = len(filtered_notes)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_notes = filtered_notes[start_idx:end_idx]
        
        # Convert to response format
        response_notes = []
        for note in page_notes:
            note_response = {
                "id": note["id"],
                "text": note["text"],
                "comment": note.get("comment"),
                "url": note["url"], 
                "title": note["title"],
                "category": note.get("category", "General"),
                "created_at": note["created_at"].isoformat() if isinstance(note["created_at"], datetime) else note["created_at"],
                "updated_at": note["updated_at"].isoformat() if isinstance(note["updated_at"], datetime) else note["updated_at"],
                "sync_status": note.get("sync_status", "local")
            }
            
            # Add Notion fields if available
            if note.get("notion_page_id"):
                note_response["notion_page_id"] = note["notion_page_id"]
                note_response["notion_page_url"] = f"https://notion.so/{note['notion_page_id'].replace('-', '')}"
            
            response_notes.append(note_response)
        
        return ORJSONResponse(
            content={
                "notes": response_notes,
                "total": total,
                "page": page,
                "page_size": page_size,
                "has_next": end_idx < total
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve notes"
        )


@router.get("/{note_id}",
            response_model=NoteResponse,
            summary="Get single note",
            description="Retrieve a specific note by ID")
async def get_note(note_id: str = Depends(validate_note_id)) -> ORJSONResponse:
    """
    Get a single note by ID
    """
    if note_id not in notes_storage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )
    
    note = notes_storage[note_id]
    
    response_data = {
        "id": note["id"],
        "text": note["text"],
        "comment": note.get("comment"),
        "url": note["url"],
        "title": note["title"],
        "category": note.get("category", "General"),
        "created_at": note["created_at"].isoformat() if isinstance(note["created_at"], datetime) else note["created_at"],
        "updated_at": note["updated_at"].isoformat() if isinstance(note["updated_at"], datetime) else note["updated_at"],
        "sync_status": note.get("sync_status", "local")
    }
    
    # Add Notion fields if available
    if note.get("notion_page_id"):
        response_data["notion_page_id"] = note["notion_page_id"]
        response_data["notion_page_url"] = f"https://notion.so/{note['notion_page_id'].replace('-', '')}"
    
    return ORJSONResponse(content=response_data)


@router.put("/{note_id}",
            response_model=ApiResponse,
            summary="Update note", 
            description="Update an existing note's comment or category")
async def update_note(
    note_update: NoteUpdate,
    note_id: str = Depends(validate_note_id)
) -> ORJSONResponse:
    """
    Update an existing note
    """
    if note_id not in notes_storage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )
    
    try:
        note = notes_storage[note_id]
        
        # Update fields if provided
        if note_update.comment is not None:
            note["comment"] = note_update.comment
        
        if note_update.category is not None:
            note["category"] = note_update.category
        
        # Update timestamp
        note["updated_at"] = datetime.utcnow()
        
        return ORJSONResponse(
            content={
                "success": True,
                "message": "Note updated successfully",
                "data": {"note_id": note_id}
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update note"
        )


@router.delete("/{note_id}",
               response_model=ApiResponse,
               summary="Delete note",
               description="Delete a specific note")
async def delete_note(note_id: str = Depends(validate_note_id)) -> ORJSONResponse:
    """
    Delete a note by ID
    """
    if note_id not in notes_storage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )
    
    try:
        del notes_storage[note_id]
        
        return ORJSONResponse(
            content={
                "success": True,
                "message": "Note deleted successfully",
                "data": {"note_id": note_id}
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete note"
        )


@router.get("/stats/summary",
            summary="Get notes statistics",
            description="Get summary statistics about notes")
async def get_notes_stats() -> ORJSONResponse:
    """
    Get quick statistics about notes
    """
    try:
        total_notes = len(notes_storage)
        
        # Count by category
        categories = {}
        for note in notes_storage.values():
            cat = note.get("category", "General")
            categories[cat] = categories.get(cat, 0) + 1
        
        return ORJSONResponse(
            content={
                "total_notes": total_notes,
                "categories": categories,
                "generated_at": datetime.utcnow().isoformat()
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get statistics"
        )


@router.post("/categorize",
             summary="Suggest category for content",
             description="Use AI to suggest the best category for content")
async def categorize_content(
    request: Request,
    notion_token: Optional[str] = Header(None, alias="X-Notion-Token", description="Notion integration token"),
    notion_database_id: Optional[str] = Header(None, alias="X-Notion-Database-Id", description="Notion database ID")
) -> ORJSONResponse:
    """
    Suggest a category for content using AI (Phi3 via Ollama)
    
    Expects JSON body:
    {
        "content": "The text content to categorize",
        "comment": "Optional user comment",
        "existing_categories": ["cat1", "cat2"] // Optional, will fetch from Notion if not provided
    }
    """
    try:
        # Parse request body
        body = await request.json()
        content = body.get("content", "").strip()
        comment = body.get("comment", "").strip()
        existing_categories = body.get("existing_categories")
        
        # Validate content
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Content is required for categorization"
            )
        
        # **OPTIMIZATION: Parallel execution of category fetching and AI categorization**
        async def fetch_categories():
            """Fetch existing categories with caching"""
            if existing_categories is not None:
                return existing_categories
                
            try:
                # Try to get from Notion if tokens provided
                if notion_token and notion_database_id:
                    logger.info("Fetching existing categories from Notion database (cached)")
                    return await extract_existing_categories(notion_token, notion_database_id)
                else:
                    # Use config defaults
                    if settings.notion_token and settings.notion_database_id:
                        logger.info("Using config tokens to fetch categories (cached)")
                        return await extract_existing_categories(
                            settings.notion_token, 
                            settings.notion_database_id
                        )
                    else:
                        logger.warning("No Notion credentials available, using default categories")
                        return ["General", "Research", "Development", "Articles", "Tech News"]
                        
            except Exception as e:
                logger.warning(f"Failed to fetch existing categories: {e}")
                return ["General", "Research", "Development", "Articles", "Tech News"]
        
        async def get_ai_suggestion(categories_list):
            """Get AI categorization suggestion"""
            category_ai = get_category_ai()
            return await category_ai.suggest_category(
                content=content,
                comment=comment,
                existing_categories=categories_list
            )
        
        # **TRUE PARALLEL EXECUTION - Start both simultaneously**
        logger.info("Starting true parallel execution (categories + AI)")
        start_time = asyncio.get_event_loop().time()
        
        try:
            # CRITICAL FIX: Always fetch categories FIRST, then pass to AI
            existing_categories = await fetch_categories()
            logger.info(f"✅ Fetched {len(existing_categories)} existing categories: {existing_categories}")
            
            # Run AI with the actual existing categories (not empty list)
            suggestion = await get_ai_suggestion(existing_categories)
            logger.info(f"✅ AI suggestion completed: {suggestion.category} (confidence: {suggestion.confidence})")
                
        except Exception as e:
            logger.error(f"Parallel execution failed: {e}")
            # Simple sequential fallback
            existing_categories = await fetch_categories()
            suggestion = await get_ai_suggestion(existing_categories)
        
        elapsed_time = asyncio.get_event_loop().time() - start_time
        logger.info(f"Categorization completed in {elapsed_time:.2f}s with {len(existing_categories)} categories")
        
        # Format response
        response_data = {
            "category": suggestion.category,
            "title": suggestion.title,
            "confidence": suggestion.confidence,
            "is_new": suggestion.is_new,
            "reasoning": suggestion.reasoning,
            "existing_categories": existing_categories
        }
        
        logger.info(f"Categorization complete: {suggestion.category} (confidence: {suggestion.confidence})")
        
        return ORJSONResponse(
            content={
                "success": True,
                "message": "Category suggestion generated successfully",
                "data": response_data
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Categorization failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate category suggestion"
        )


@router.post("/warm-cache",
             summary="Warm category cache",
             description="Pre-load categories to improve categorization speed")
async def warm_category_cache_endpoint(
    notion_token: Optional[str] = Header(None, alias="X-Notion-Token"),
    notion_database_id: Optional[str] = Header(None, alias="X-Notion-Database-Id")
) -> ORJSONResponse:
    """
    Warm the category cache for faster subsequent categorization requests.
    Call this when the extension loads or when you want to refresh the cache.
    """
    try:
        # Determine which credentials to use
        token = notion_token or settings.notion_token
        database_id = notion_database_id or settings.notion_database_id
        
        if not token or not database_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Notion token and database ID required"
            )
        
        # Warm the cache
        success = await warm_category_cache(token, database_id)
        
        if success:
            return ORJSONResponse(
                content={
                    "success": True,
                    "message": "Category cache warmed successfully",
                    "cache_duration_minutes": 10
                }
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to warm category cache"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cache warming failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to warm cache"
        )


@router.delete("/clear-cache",
               summary="Clear category cache",
               description="Clear the category cache to force fresh data")
async def clear_cache_endpoint(
    notion_database_id: Optional[str] = Header(None, alias="X-Notion-Database-Id")
) -> ORJSONResponse:
    """
    Clear the category cache. Useful when you've added new categories manually in Notion.
    """
    try:
        database_id = notion_database_id or settings.notion_database_id
        clear_category_cache(database_id)
        
        return ORJSONResponse(
            content={
                "success": True,
                "message": "Category cache cleared successfully"
            }
        )
        
    except Exception as e:
        logger.error(f"Cache clearing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear cache"
        )
