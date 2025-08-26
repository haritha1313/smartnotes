"""
Security middleware for rate limiting, request validation, and attack prevention
"""
import time
from collections import defaultdict, deque
from typing import Dict, Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.status import HTTP_429_TOO_MANY_REQUESTS, HTTP_413_REQUEST_ENTITY_TOO_LARGE
from app.config import settings, SECURITY_HEADERS


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware to prevent abuse"""
    
    def __init__(self, app, requests_per_minute: int = None, window_seconds: int = None):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute or settings.rate_limit_requests
        self.window_seconds = window_seconds or settings.rate_limit_window
        self.clients: Dict[str, deque] = defaultdict(deque)
        self.cleanup_interval = 300  # Clean up old entries every 5 minutes
        self.last_cleanup = time.time()
    
    async def dispatch(self, request: Request, call_next: Callable):
        """Process request with rate limiting"""
        client_ip = self._get_client_ip(request)
        current_time = time.time()
        
        # Periodic cleanup of old entries
        if current_time - self.last_cleanup > self.cleanup_interval:
            self._cleanup_old_entries(current_time)
            self.last_cleanup = current_time
        
        # Check rate limit for this client
        if self._is_rate_limited(client_ip, current_time):
            return JSONResponse(
                status_code=HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "success": False,
                    "error": "Rate limit exceeded",
                    "detail": f"Maximum {self.requests_per_minute} requests per {self.window_seconds} seconds"
                },
                headers=SECURITY_HEADERS
            )
        
        # Add request timestamp
        self.clients[client_ip].append(current_time)
        
        # Process request
        response = await call_next(request)
        
        # Add security headers
        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP with proxy support"""
        # Check for forwarded headers (common in production)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"
    
    def _is_rate_limited(self, client_ip: str, current_time: float) -> bool:
        """Check if client has exceeded rate limit"""
        client_requests = self.clients[client_ip]
        
        # Remove requests outside the window
        cutoff_time = current_time - self.window_seconds
        while client_requests and client_requests[0] < cutoff_time:
            client_requests.popleft()
        
        # Check if limit exceeded
        return len(client_requests) >= self.requests_per_minute
    
    def _cleanup_old_entries(self, current_time: float):
        """Clean up old client entries to prevent memory leaks"""
        cutoff_time = current_time - self.window_seconds * 2  # Keep 2x window for safety
        clients_to_remove = []
        
        for client_ip, requests in self.clients.items():
            # Remove old requests
            while requests and requests[0] < cutoff_time:
                requests.popleft()
            
            # Mark empty clients for removal
            if not requests:
                clients_to_remove.append(client_ip)
        
        # Remove empty clients
        for client_ip in clients_to_remove:
            del self.clients[client_ip]


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """Middleware for request validation and size limits"""
    
    async def dispatch(self, request: Request, call_next: Callable):
        """Validate request before processing"""
        
        # Check request size
        content_length = request.headers.get("content-length")
        if content_length:
            content_length = int(content_length)
            if content_length > settings.max_request_size:
                return JSONResponse(
                    status_code=HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    content={
                        "success": False,
                        "error": "Request too large",
                        "detail": f"Maximum request size is {settings.max_request_size} bytes"
                    },
                    headers=SECURITY_HEADERS
                )
        
        # Validate request method
        if request.method not in settings.allowed_methods:
            return JSONResponse(
                status_code=405,
                content={
                    "success": False,
                    "error": "Method not allowed",
                    "detail": f"Allowed methods: {', '.join(settings.allowed_methods)}"
                },
                headers=SECURITY_HEADERS
            )
        
        # Check for suspicious patterns in path
        if self._has_suspicious_patterns(request.url.path):
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "Invalid request path",
                    "detail": "Request path contains suspicious patterns"
                },
                headers=SECURITY_HEADERS
            )
        
        return await call_next(request)
    
    def _has_suspicious_patterns(self, path: str) -> bool:
        """Check for common attack patterns in URL path"""
        suspicious_patterns = [
            "../",           # Path traversal
            "..\\",          # Path traversal (Windows)
            "<script",       # XSS attempt
            "javascript:",   # XSS attempt  
            "data:",         # Data URI attack
            "vbscript:",     # VBScript attack
            "onload=",       # Event handler injection
            "onerror=",      # Event handler injection
            "eval(",         # Code injection
            "exec(",         # Code injection
            "system(",       # System command injection
            "cmd.exe",       # Windows command injection
            "/bin/",         # Unix command injection
        ]
        
        path_lower = path.lower()
        return any(pattern in path_lower for pattern in suspicious_patterns)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses"""
    
    async def dispatch(self, request: Request, call_next: Callable):
        response = await call_next(request)
        
        # Add all security headers
        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value
        
        # Add CORS headers if needed
        origin = request.headers.get("origin")
        if origin and self._is_allowed_origin(origin):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        
        return response
    
    def _is_allowed_origin(self, origin: str) -> bool:
        """Check if origin is in allowed list"""
        for allowed in settings.allowed_origins:
            if allowed == "*" or origin == allowed or origin.startswith(allowed.replace("*", "")):
                return True
        return False
