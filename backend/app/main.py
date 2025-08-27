"""
Smart Notes API - High Performance FastAPI Backend
Optimized for low latency and security
"""
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import ORJSONResponse
from fastapi.exception_handlers import http_exception_handler
import orjson

from app.config import settings, SECURITY_HEADERS
from app.routers import notes
from app.middleware.security import (
    RateLimitMiddleware, 
    RequestValidationMiddleware,
    SecurityHeadersMiddleware
)
from app.schemas.note import ErrorResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    print(f"Smart Notes API starting...")
    print(f"   Environment: {settings.environment}")
    print(f"   Debug: {settings.debug}")
    print(f"   Rate Limit: {settings.rate_limit_requests} req/{settings.rate_limit_window}s")
    print(f"   Allowed Methods: {settings.allowed_methods}")
    print(f"   Allowed Origins: {settings.allowed_origins}")
    print(f"   Allowed Headers: {settings.allowed_headers}")
    
    yield
    
    # Shutdown
    print("Smart Notes API shutting down...")


# Create FastAPI app with performance optimizations
app = FastAPI(
    title="Smart Notes API",
    description="High-performance API for capturing and organizing web notes",
    version="1.0.0",
    debug=settings.debug,
    lifespan=lifespan,
    default_response_class=ORJSONResponse,  # Faster JSON serialization
    docs_url="/docs" if settings.debug else None,  # Disable docs in production
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
)

# Add middleware in reverse order (last added = first executed)

# 1. CORS FIRST (most important for browser extension)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,  # Must be False when allow_origins=["*"]
    allow_methods=settings.allowed_methods,
    allow_headers=settings.allowed_headers,
    max_age=600,  # Cache preflight for 10 minutes
)

# 2. Security headers (after CORS)
app.add_middleware(SecurityHeadersMiddleware)

# 3. Gzip compression for better performance
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 4. Rate limiting to prevent abuse
app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=settings.rate_limit_requests,
    window_seconds=settings.rate_limit_window
)

# 5. Request validation (innermost)
app.add_middleware(RequestValidationMiddleware)


# Custom exception handlers
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    """Custom exception handler with security headers"""
    response = await http_exception_handler(request, exc)
    
    # Add security headers to error responses
    for header, value in SECURITY_HEADERS.items():
        response.headers[header] = value
    
    return response


@app.exception_handler(422)
async def validation_exception_handler(request: Request, exc):
    """Handle validation errors with consistent format"""
    return ORJSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": "Validation error",
            "detail": "Invalid request data",
            "validation_errors": exc.detail if hasattr(exc, 'detail') else None
        },
        headers=SECURITY_HEADERS
    )


@app.exception_handler(500)
async def internal_server_error_handler(request: Request, exc):
    """Handle internal server errors"""
    return ORJSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "detail": "An unexpected error occurred"
        },
        headers=SECURITY_HEADERS
    )


# Include routers
app.include_router(notes.router)

# Import and include Notion router
from app.routers import notion
app.include_router(notion.router)


# Health check endpoint (minimal overhead)
@app.get("/health", 
         tags=["health"],
         summary="Health check",
         description="Check if the API is running")
async def health_check():
    """Fast health check endpoint"""
    return ORJSONResponse(
        content={
            "status": "healthy",
            "timestamp": time.time(),
            "version": "1.0.0"
        }
    )


# Root endpoint
@app.get("/",
         tags=["root"],
         summary="API information",
         description="Get basic API information")
async def root():
    """Root endpoint with API info"""
    return ORJSONResponse(
        content={
            "name": "Smart Notes API",
            "version": "1.0.0",
            "description": "High-performance API for capturing and organizing web notes",
            "endpoints": {
                "notes": "/api/notes",
                "health": "/health",
                "docs": "/docs" if settings.debug else "disabled"
            }
        }
    )


# Performance monitoring endpoint (debug only)
if settings.debug:
    @app.get("/debug/performance",
             tags=["debug"],
             summary="Performance metrics",
             description="Get basic performance metrics (debug mode only)")
    async def performance_metrics():
        """Debug endpoint for performance monitoring"""
        import psutil
        import gc
        
        return ORJSONResponse(
            content={
                "memory": {
                    "rss": psutil.Process().memory_info().rss,
                    "percent": psutil.virtual_memory().percent
                },
                "cpu_percent": psutil.cpu_percent(),
                "gc_stats": {
                    "collections": gc.get_stats(),
                    "count": gc.get_count()
                }
            }
        )


# Request timing middleware for monitoring
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add response time header for monitoring"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


if __name__ == "__main__":
    import uvicorn
    
    # Production-optimized uvicorn config
    uvicorn_config = {
        "app": "app.main:app",
        "host": settings.api_host,
        "port": settings.api_port,
        "reload": settings.debug,
        "log_level": "info" if not settings.debug else "debug",
        "access_log": settings.debug,
        "workers": 1 if settings.debug else 4,
        "loop": "auto",  # Use uvloop on Unix for better performance
        "http": "auto",  # Use httptools for better performance
        "timeout_keep_alive": settings.keep_alive_timeout,
        "limit_concurrency": 1000,
        "limit_max_requests": 10000,
    }
    
    uvicorn.run(**uvicorn_config)
