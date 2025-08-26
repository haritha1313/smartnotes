"""
Notion API router for workspace setup and testing
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status, Depends, Query
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel, Field
import logging

from app.services.notion_service import (
    NotionService, 
    NotionServiceError, 
    NotionServiceContext,
    setup_user_workspace
)
from app.schemas.note import ErrorResponse, ApiResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/notion",
    tags=["notion"],
    default_response_class=ORJSONResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    }
)


# Pydantic models for Notion operations
class NotionTokenValidation(BaseModel):
    """Schema for validating Notion tokens"""
    token: str = Field(..., min_length=10, max_length=200, description="Notion integration token")


class DatabaseSetupRequest(BaseModel):
    """Schema for database setup requests"""
    token: str = Field(..., min_length=10, max_length=200, description="Notion integration token")
    parent_page_id: str = Field(..., min_length=10, description="Parent page ID where database will be created")
    database_title: Optional[str] = Field("Research Notes", max_length=100, description="Database title")


class DatabaseInfo(BaseModel):
    """Schema for database information"""
    id: str
    title: str
    url: str
    created_time: str
    last_edited_time: str


class WorkspaceSetupResponse(BaseModel):
    """Schema for workspace setup response"""
    success: bool
    database_id: str
    database_url: str
    message: str


def validate_notion_token(token: str) -> str:
    """Validate Notion token format"""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Notion token is required"
        )
    
    if not token.startswith(("secret_", "ntn_")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Notion token format"
        )
    
    return token


@router.post("/test-connection",
             response_model=ApiResponse,
             summary="Test Notion API connection",
             description="Verify that the provided Notion token is valid and can access the API")
async def test_notion_connection(request: NotionTokenValidation) -> ORJSONResponse:
    """Test Notion API connection with provided token"""
    try:
        token = validate_notion_token(request.token)
        
        async with NotionServiceContext(token) as notion:
            # Connection test is performed in context manager
            user_info = await notion._make_request(notion.client.users.me)
            
            return ORJSONResponse(
                content={
                    "success": True,
                    "message": "Notion connection successful",
                    "data": {
                        "user_id": user_info.get("id"),
                        "user_name": user_info.get("name"),
                        "user_type": user_info.get("type")
                    }
                }
            )
    
    except NotionServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Notion API error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Notion connection test failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to test Notion connection"
        )


@router.get("/databases",
            response_model=List[DatabaseInfo],
            summary="List accessible databases",
            description="Get list of databases accessible to the Notion integration")
async def list_databases(
    token: str = Query(..., description="Notion integration token")
) -> ORJSONResponse:
    """List databases accessible to the integration"""
    try:
        validated_token = validate_notion_token(token)
        
        async with NotionServiceContext(validated_token) as notion:
            databases = await notion.get_databases()
            
            # Format database information
            formatted_databases = []
            for db in databases:
                title = ""
                if db.get("title"):
                    title = "".join([t.get("plain_text", "") for t in db["title"]])
                
                formatted_databases.append({
                    "id": db["id"],
                    "title": title or "Untitled Database",
                    "url": db.get("url", ""),
                    "created_time": db.get("created_time", ""),
                    "last_edited_time": db.get("last_edited_time", "")
                })
            
            return ORJSONResponse(content=formatted_databases)
    
    except NotionServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Notion API error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Failed to list databases: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve databases"
        )


@router.post("/setup-workspace",
             response_model=WorkspaceSetupResponse,
             summary="Setup user workspace",
             description="Create a Research Notes database in the user's Notion workspace")
async def setup_workspace(request: DatabaseSetupRequest) -> ORJSONResponse:
    """Setup user workspace with Research Notes database"""
    try:
        token = validate_notion_token(request.token)
        
        # Create database using the service
        database_id = await setup_user_workspace(token, request.parent_page_id)
        
        # Generate database URL
        database_url = f"https://notion.so/{database_id.replace('-', '')}"
        
        return ORJSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "success": True,
                "database_id": database_id,
                "database_url": database_url,
                "message": "Workspace setup completed successfully"
            }
        )
    
    except NotionServiceError as e:
        if "permission" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {str(e)}"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Setup failed: {str(e)}"
            )
    except Exception as e:
        logger.error(f"Workspace setup failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to setup workspace"
        )


@router.post("/create-page",
             response_model=ApiResponse,
             summary="Create note page",
             description="Create a new note page in a Notion database")
async def create_note_page(
    database_id: str = Query(..., description="Target database ID"),
    token: str = Query(..., description="Notion integration token"),
    note_data: dict = None
) -> ORJSONResponse:
    """Create a new note page in the specified database"""
    try:
        validated_token = validate_notion_token(token)
        
        if not note_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Note data is required"
            )
        
        async with NotionServiceContext(validated_token) as notion:
            page_id = await notion.create_note_page(database_id, note_data)
            
            # Generate page URL
            page_url = f"https://notion.so/{page_id.replace('-', '')}"
            
            return ORJSONResponse(
                status_code=status.HTTP_201_CREATED,
                content={
                    "success": True,
                    "message": "Note page created successfully",
                    "data": {
                        "page_id": page_id,
                        "page_url": page_url
                    }
                }
            )
    
    except NotionServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create page: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Page creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create note page"
        )


@router.get("/health",
            summary="Notion service health check",
            description="Check if Notion service is available")
async def notion_health() -> ORJSONResponse:
    """Health check for Notion service"""
    return ORJSONResponse(
        content={
            "service": "notion",
            "status": "healthy",
            "version": "1.0.0",
            "features": [
                "database_creation",
                "page_creation", 
                "connection_testing",
                "workspace_setup"
            ]
        }
    )
