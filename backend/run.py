#!/usr/bin/env python3
"""
Smart Notes API - Production Runner
Optimized startup script with environment validation
"""
import os
import sys
import uvicorn
from pathlib import Path

# Add app directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.config import settings


def validate_environment():
    """Validate critical environment settings"""
    errors = []
    
    # Check secret key strength
    if len(settings.secret_key) < 32:
        errors.append("SECRET_KEY must be at least 32 characters long")
    
    # Check if running in production with debug enabled
    if settings.environment == "production" and settings.debug:
        errors.append("DEBUG should be False in production environment")
    
    # Check CORS origins in production
    if settings.environment == "production" and "*" in settings.allowed_origins:
        errors.append("Wildcard CORS origins not recommended in production")
    
    if errors:
        print("❌ Environment validation failed:")
        for error in errors:
            print(f"   • {error}")
        return False
    
    return True


def main():
    """Main startup function"""
    print("🚀 Starting Smart Notes API...")
    print(f"   Environment: {settings.environment}")
    print(f"   Debug: {settings.debug}")
    print(f"   Host: {settings.api_host}:{settings.api_port}")
    
    # Validate environment
    if not validate_environment():
        print("\n❌ Startup aborted due to configuration errors")
        sys.exit(1)
    
    print("✅ Environment validation passed")
    
    # Production-optimized uvicorn configuration
    config = {
        "app": "app.main:app",
        "host": settings.api_host,
        "port": settings.api_port,
        "reload": settings.debug,
        "reload_dirs": ["app"] if settings.debug else None,
        "log_level": "info",
        "access_log": settings.debug,
        "workers": 1 if settings.debug else min(4, os.cpu_count() or 1),
        "timeout_keep_alive": settings.keep_alive_timeout,
        "limit_concurrency": 1000,
        "limit_max_requests": 10000,
    }
    
    # Use high-performance settings on Unix systems
    if os.name != 'nt':  # Not Windows
        config.update({
            "loop": "uvloop",      # High-performance event loop
            "http": "httptools",   # Fast HTTP parser
        })
    
    print(f"🌐 Starting server on http://{settings.api_host}:{settings.api_port}")
    print(f"📚 API docs: http://{settings.api_host}:{settings.api_port}/docs" if settings.debug else "")
    print("🔄 Ready to receive requests...")
    
    try:
        uvicorn.run(**config)
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
