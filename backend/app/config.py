"""
Configuration module with security and performance optimizations
"""
import os
from typing import List
from pydantic import validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with security defaults"""
    
    # API Configuration
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    debug: bool = False
    environment: str = "production"
    
    # Security Configuration
    secret_key: str = "your-super-secret-key-change-this-in-production-min-32-chars"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # CORS Configuration (restrictive by default)
    allowed_origins: List[str] = [
        "http://localhost:3000",
        "chrome-extension://*"
    ]
    allowed_methods: List[str] = ["GET", "POST", "PUT", "DELETE"]
    allowed_headers: List[str] = [
        "Content-Type",
        "Authorization", 
        "X-Notion-Token",
        "X-Notion-Database-Id"
    ]
    
    # Rate Limiting (per IP)
    rate_limit_requests: int = 60  # requests per window
    rate_limit_window: int = 60    # window in seconds
    
    # Request size limits (security)
    max_request_size: int = 1048576    # 1MB max request
    max_field_size: int = 65536        # 64KB max field
    max_text_length: int = 10000       # 10K chars max text
    max_comment_length: int = 2000     # 2K chars max comment
    
    # Timeouts (performance/security)
    request_timeout: int = 30
    keep_alive_timeout: int = 5
    
    # Notion API Configuration
    notion_client_id: str = ""
    notion_client_secret: str = ""
    notion_redirect_uri: str = "http://localhost:8000/api/auth/notion/callback"
    notion_token: str = ""  # For direct integration testing
    notion_database_id: str = ""  # For direct database testing
    
    # Database Configuration
    database_url: str = "sqlite:///./notes.db"
    
    @validator('secret_key')
    def validate_secret_key(cls, v):
        """Ensure secret key is strong enough"""
        if len(v) < 32:
            raise ValueError('SECRET_KEY must be at least 32 characters long')
        return v
    
    @validator('allowed_origins')
    def validate_origins(cls, v):
        """Ensure CORS origins are properly configured"""
        if not v:
            raise ValueError('At least one allowed origin must be specified')
        return v
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields in .env file


# Global settings instance
settings = Settings()


# Security headers for all responses
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY", 
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Content-Security-Policy": "default-src 'self'",
}

# Input validation patterns
VALIDATION_PATTERNS = {
    "url_pattern": r"^https?:\/\/.+",
    "safe_text_pattern": r"^[^<>]*$",  # No HTML tags
    "id_pattern": r"^[a-zA-Z0-9\-_]{1,50}$",
}

# Performance settings
PERFORMANCE_CONFIG = {
    "json_encoder": "orjson",  # Faster JSON serialization
    "response_compression": True,
    "cache_control_max_age": 300,  # 5 minutes
}
