from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        # Control referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # Restrict browser permissions/features
        response.headers["Permissions-Policy"] = "geolocation=(self), camera=(), microphone=()"
        # Content Security Policy compatible with Leaflet Maps, OpenStreetMap tiles, and Firebase
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "img-src 'self' data: blob: https://*.tile.openstreetmap.org https://images.unsplash.com https://*.amazonaws.com; "
            "script-src 'self' 'unsafe-inline' https://www.gstatic.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "connect-src 'self' https://fcm.googleapis.com https://*.firebaseio.com; "
            "frame-ancestors 'none';"
        )
        # Enforce HTTPS transport security
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
