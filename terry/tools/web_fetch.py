"""Web fetch tool - fetch content from URLs."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

import httpx

from . import BaseTool, tool_registry


def _is_private_hostname(hostname: str) -> bool:
    """Check if a hostname resolves to a private/internal IP.

    Blocks: loopback, link-local, private ranges, cloud metadata endpoints.
    """
    # Block well-known internal hostnames
    internal_names = {
        "localhost", "localhost.localdomain",
        "0.0.0.0", "[::]", "::1",
    }
    if hostname.lower() in internal_names:
        return True

    # Try DNS resolution to check actual IP
    try:
        addr_info = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for family, _type, _proto, _canonname, sockaddr in addr_info:
            ip_str = sockaddr[0]
            ip = ipaddress.ip_address(ip_str)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return True
            # Block AWS/GCP/Azure metadata endpoints
            if ip_str in ("169.254.169.254", "fd00:ec2::254"):
                return True
    except (socket.gaierror, OSError):
        # If we can't resolve, be cautious and block
        return True

    return False


class WebFetchTool(BaseTool):
    """Fetch content from a URL with SSRF protection."""

    name = "web_fetch"
    description = "Fetch text content from a URL. Useful for reading documentation or web pages."
    input_schema = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL to fetch content from",
            },
            "max_chars": {
                "type": "integer",
                "description": "Maximum characters to return (default: 50000)",
                "default": 50000,
            },
        },
        "required": ["url"],
    }

    # Maximum HTTP redirects allowed
    MAX_REDIRECTS = 5

    def execute(self, url: str, max_chars: int = 50000) -> str:
        """Fetch content from URL with SSRF protection."""
        try:
            # Validate URL
            parsed = urlparse(url)
            if not parsed.scheme:
                url = "https://" + url
                parsed = urlparse(url)

            if parsed.scheme not in ("http", "https"):
                return f"Error: Invalid URL scheme: {parsed.scheme}"

            # Security: Resolve and check hostname against private IP ranges
            hostname = parsed.hostname or ""
            if _is_private_hostname(hostname):
                return "Error: Access to internal/private addresses is not allowed"

            # Fetch URL with redirect limit
            with httpx.Client(
                timeout=30,
                max_redirects=self.MAX_REDIRECTS,
            ) as client:
                response = client.get(url)
                response.raise_for_status()

                # Check final URL hostname after redirects (prevent redirect-based SSRF)
                final_parsed = urlparse(str(response.url))
                final_hostname = final_parsed.hostname or ""
                if _is_private_hostname(final_hostname):
                    return "Error: Redirect to internal/private address is not allowed"

            # Get text content
            content = response.text

            # Limit output
            original_length = len(content)
            if original_length > max_chars:
                content = content[:max_chars]
                content += f"\n\n... (truncated, {original_length - max_chars} chars omitted)"

            return content

        except httpx.TimeoutException:
            return "Error: Request timed out after 30 seconds"
        except httpx.HTTPStatusError as e:
            return f"Error: HTTP {e.response.status_code} - {e.response.reason_phrase}"
        except Exception as e:
            return f"Error: {e}"


# Auto-register
tool_registry.register(WebFetchTool())
