"""Security headers for Terry HTTP servers.

Provides a reusable set of HTTP security headers that can be applied
uniformly across all three server implementations:
  - terry/webui/server.py       (WebUI)
  - terry/server/__init__.py     (CLI server)
  - terry/server/async_server.py (Async server)

Usage:
    from terry.core.security_headers import SECURITY_HEADERS
    # Merge into response headers dict
    response_headers.update(SECURITY_HEADERS)
"""

from __future__ import annotations

# ── Standard security headers ──────────────────────────────────────────
#
# Applied to every HTTP response to protect against common web attacks.
# All three server implementations should include these headers.

SECURITY_HEADERS: dict[str, str] = {
    # Prevent MIME-type sniffing
    "X-Content-Type-Options": "nosniff",
    # Prevent clickjacking by blocking framing
    "X-Frame-Options": "DENY",
    # Enable browser XSS filter
    "X-XSS-Protection": "1; mode=block",
    # Enforce HTTPS for 1 year (include subdomains)
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    # Restrict resource loading to same origin (allow inline scripts for SSE/WebUI)
    "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",
    # Don't leak referrer information to other origins
    "Referrer-Policy": "no-referrer",
    # Control which features can be used in the browser
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}

# ── CORS headers (applied selectively) ─────────────────────────────────

CORS_HEADERS: dict[str, str] = {
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With",
    "Access-Control-Max-Age": "86400",  # Cache preflight for 24 hours
}


def apply_security_headers(headers: dict[str, str]) -> dict[str, str]:
    """Merge standard security headers into an existing headers dict.

    Args:
        headers: Existing response headers dict.

    Returns:
        The same dict with security headers added (mutated in-place).
    """
    headers.update(SECURITY_HEADERS)
    return headers


def apply_cors_headers(headers: dict[str, str], origin: str | None = None) -> dict[str, str]:
    """Merge CORS headers into an existing headers dict.

    Args:
        headers: Existing response headers dict.
        origin: Optional origin to allow. Defaults to '*'.

    Returns:
        The same dict with CORS headers added (mutated in-place).
    """
    headers.update(CORS_HEADERS)
    headers["Access-Control-Allow-Origin"] = origin or "*"
    return headers
