import time
import uuid

from starlette.types import ASGIApp
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from loguru import logger


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": (
                "geolocation=(), microphone=(), camera=(), payment=(), usb=()"
            ),
            "Cross-Origin-Resource-Policy": "cross-origin",
        }


    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        for header, value in self.security_headers.items():
            response.headers[header] = value

        from config import settings
        if settings.app_env == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using slowapi."""

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for certain paths
        if self._should_skip_rate_limit(request):
            return await call_next(request)

        # Apply rate limiting
        return await call_next(request)

    def _should_skip_rate_limit(self, request: Request) -> bool:
        """Determine if rate limiting should be skipped for this request."""
        skip_paths = [
            "/api/v1/health",
            "/api/v1/metrics",
            "/favicon.ico",
        ]

        return any(request.url.path.startswith(path) for path in skip_paths)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log all incoming requests with timing information."""

    async def dispatch(self, request: Request, call_next):
        # Generate request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Get client IP
        client_ip = self._get_client_ip(request)

        # Log request start
        logger.info(
            f"Request started | "
            f"id={request_id} | "
            f"method={request.method} | "
            f"path={request.url.path} | "
            f"client_ip={client_ip} | "
            f"user_agent={request.headers.get('user-agent', 'unknown')}"
        )

        # Process request
        start_time = time.time()
        try:
            response = await call_next(request)
            process_time = time.time() - start_time

            # Log successful response
            logger.info(
                f"Request completed | "
                f"id={request_id} | "
                f"method={request.method} | "
                f"path={request.url.path} | "
                f"status={response.status_code} | "
                f"duration={process_time:.3f}s"
            )

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as exc:
            process_time = time.time() - start_time
            logger.exception(
                f"Request failed | "
                f"id={request_id} | "
                f"method={request.method} | "
                f"path={request.url.path} | "
                f"duration={process_time:.3f}s | "
                f"error={str(exc)}"
            )

            raise

    def _get_client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"


class ProcessTimeMiddleware(BaseHTTPMiddleware):
    """Add process time to response headers."""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time

        response.headers["X-Process-Time"] = f"{process_time:.3f}"
        response.headers["X-Response-Time"] = str(int(process_time * 1000))

        return response
