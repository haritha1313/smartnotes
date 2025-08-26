"""
Pydantic schemas for note validation with security constraints
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, validator, HttpUrl
import re
from app.config import settings


class NoteBase(BaseModel):
    """Base note schema with common fields"""
    text: str = Field(
        ..., 
        min_length=1, 
        max_length=settings.max_text_length,
        description="The captured text content"
    )
    comment: Optional[str] = Field(
        None, 
        max_length=settings.max_comment_length,
        description="Optional user comment"
    )
    url: HttpUrl = Field(..., description="Source webpage URL")
    title: str = Field(
        ..., 
        min_length=1, 
        max_length=500,
        description="Source webpage title"
    )
    category: Optional[str] = Field(
        "General", 
        max_length=50,
        description="Note category"
    )


class NoteCreate(NoteBase):
    """Schema for creating a new note"""
    timestamp: Optional[datetime] = Field(
        default_factory=datetime.utcnow,
        description="When the note was captured"
    )
    
    @validator('text')
    def validate_text_content(cls, v):
        """Validate text content for security"""
        if not v or not v.strip():
            raise ValueError('Text content cannot be empty')
        
        # Remove potential HTML/script tags for security
        cleaned = re.sub(r'<[^>]*>', '', v.strip())
        if len(cleaned) == 0:
            raise ValueError('Text content cannot contain only HTML tags')
        
        return cleaned[:settings.max_text_length]
    
    @validator('comment')
    def validate_comment_content(cls, v):
        """Validate comment content for security"""
        if not v:
            return v
        
        # Clean and validate comment
        cleaned = re.sub(r'<[^>]*>', '', v.strip())
        return cleaned[:settings.max_comment_length] if cleaned else None
    
    @validator('title')
    def validate_title_content(cls, v):
        """Validate title content"""
        if not v or not v.strip():
            raise ValueError('Title cannot be empty')
        
        # Clean title
        cleaned = re.sub(r'<[^>]*>', '', v.strip())
        return cleaned[:500]
    
    @validator('category')
    def validate_category(cls, v):
        """Validate category is safe"""
        if not v:
            return "General"
        
        # Only allow alphanumeric, spaces, and common punctuation
        if not re.match(r'^[a-zA-Z0-9\s\-_&.]+$', v):
            return "General"
        
        return v.strip()[:50]


class NoteResponse(NoteBase):
    """Schema for note responses"""
    id: str = Field(..., description="Unique note identifier")
    created_at: datetime = Field(..., description="When the note was created")
    updated_at: datetime = Field(..., description="When the note was last updated")
    sync_status: str = Field("pending", description="Synchronization status")
    notion_page_id: Optional[str] = Field(None, description="Notion page ID if synced")
    notion_page_url: Optional[str] = Field(None, description="Notion page URL if synced")
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class NoteUpdate(BaseModel):
    """Schema for updating existing notes"""
    comment: Optional[str] = Field(
        None, 
        max_length=settings.max_comment_length
    )
    category: Optional[str] = Field(None, max_length=50)
    
    @validator('comment')
    def validate_comment_content(cls, v):
        """Validate comment content for security"""
        if not v:
            return v
        
        cleaned = re.sub(r'<[^>]*>', '', v.strip())
        return cleaned[:settings.max_comment_length] if cleaned else None
    
    @validator('category')
    def validate_category(cls, v):
        """Validate category is safe"""
        if not v:
            return v
        
        if not re.match(r'^[a-zA-Z0-9\s\-_&.]+$', v):
            raise ValueError('Invalid category format')
        
        return v.strip()[:50]


class NotesListResponse(BaseModel):
    """Schema for paginated notes list"""
    notes: list[NoteResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
    
    class Config:
        from_attributes = True


class ApiResponse(BaseModel):
    """Generic API response schema"""
    success: bool
    message: str
    data: Optional[dict] = None
    
    class Config:
        from_attributes = True


class ErrorResponse(BaseModel):
    """Error response schema"""
    success: bool = False
    error: str
    detail: Optional[str] = None
    error_code: Optional[str] = None
    
    class Config:
        from_attributes = True
