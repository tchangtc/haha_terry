"""OAuth 2.0 Device Authorization Grant for Terry CLI.

Implements RFC 8628 device code flow for CLI-native authentication.
Supports Anthropic Console and Moonshot AI (Kimi) OAuth providers.

Usage:
    python -m terry.oauth login --provider anthropic
    python -m terry.oauth logout --provider anthropic
"""

from __future__ import annotations

import json
import logging
import os
import time
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

# ── Provider Configurations ────────────────────────────────────────


@dataclass
class OAuthProvider:
    """OAuth 2.0 device flow configuration for a provider."""

    name: str
    device_authorization_endpoint: str
    token_endpoint: str
    client_id: str
    scopes: list[str] = field(default_factory=list)
    audience: str = ""


# Known providers
PROVIDERS: dict[str, OAuthProvider] = {
    "anthropic": OAuthProvider(
        name="anthropic",
        device_authorization_endpoint="https://api.anthropic.com/oauth/device_authorization",
        token_endpoint="https://api.anthropic.com/oauth/token",
        client_id="terry-cli",  # Registered OAuth client
        scopes=["openid", "offline_access"],
    ),
    "moonshot": OAuthProvider(
        name="moonshot",
        device_authorization_endpoint="https://api.moonshot.cn/oauth/device_authorization",
        token_endpoint="https://api.moonshot.cn/oauth/token",
        client_id="terry-cli",
        scopes=["openid", "offline_access"],
    ),
}


# ── Token Storage ──────────────────────────────────────────────────


def _get_token_dir() -> Path:
    """Get the directory for storing OAuth tokens."""
    base = os.environ.get("TERRY_HOME", os.path.join(Path.home(), ".local", "share", "terry"))
    token_dir = Path(base) / "tokens"
    token_dir.mkdir(parents=True, exist_ok=True)
    return token_dir


def _token_path(provider: str) -> Path:
    return _get_token_dir() / f"{provider}.json"


def load_token(provider: str) -> dict | None:
    """Load a stored OAuth token for a provider."""
    path = _token_path(provider)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def save_token(provider: str, token: dict) -> None:
    """Persist an OAuth token to disk."""
    _token_path(provider).write_text(json.dumps(token, indent=2))
    os.chmod(_token_path(provider), 0o600)


def delete_token(provider: str) -> None:
    """Remove a stored OAuth token."""
    path = _token_path(provider)
    if path.exists():
        path.unlink()


# ── Device Flow ────────────────────────────────────────────────────


@dataclass
class DeviceAuthResult:
    """Result of a device authorization request."""

    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str
    expires_in: int
    interval: int = 5


def request_device_auth(provider: str) -> DeviceAuthResult:
    """Request device authorization from the OAuth provider.

    Returns the verification URI and user code for the user to complete
    in their browser.
    """
    config = PROVIDERS.get(provider)
    if not config:
        raise ValueError(f"Unknown OAuth provider: {provider}. Available: {list(PROVIDERS)}")

    data = {
        "client_id": config.client_id,
        "scope": " ".join(config.scopes),
    }
    if config.audience:
        data["audience"] = config.audience

    req = Request(
        config.device_authorization_endpoint,
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"},
    )

    try:
        with urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
        return DeviceAuthResult(
            device_code=result["device_code"],
            user_code=result["user_code"],
            verification_uri=result["verification_uri"],
            verification_uri_complete=result.get("verification_uri_complete", result["verification_uri"]),
            expires_in=result.get("expires_in", 600),
            interval=result.get("interval", 5),
        )
    except HTTPError as e:
        body = e.read().decode() if e.fp else ""
        raise RuntimeError(f"Device auth failed ({e.code}): {body}") from e
    except URLError as e:
        raise RuntimeError(f"Network error contacting {provider}: {e}") from e


def poll_token(provider: str, device_code: str, interval: int = 5, timeout: int = 900) -> dict:
    """Poll the token endpoint until the user completes authorization.

    Blocks until success, timeout, or unrecoverable error.
    """
    config = PROVIDERS[provider]
    deadline = time.time() + timeout

    while time.time() < deadline:
        time.sleep(interval)

        data = {
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "device_code": device_code,
            "client_id": config.client_id,
        }

        req = Request(
            config.token_endpoint,
            data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"},
        )

        try:
            with urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read())
            if "access_token" in result:
                result["obtained_at"] = time.time()
                return result
            # Should not reach here — token endpoint returns error or success
        except HTTPError as e:
            body = json.loads(e.read().decode()) if e.fp else {}
            error = body.get("error", "")
            if error == "authorization_pending":
                continue  # User hasn't completed yet
            elif error == "slow_down":
                interval += 5
                continue
            elif error in ("access_denied", "expired_token"):
                raise RuntimeError(f"Authorization denied or expired: {error}")
            else:
                raise RuntimeError(f"Token error ({e.code}): {body}") from e
        except URLError as e:
            raise RuntimeError(f"Network error: {e}") from e

    raise TimeoutError(f"Timed out waiting for authorization after {timeout}s")


def refresh_token(provider: str, refresh_token_str: str) -> dict:
    """Refresh an expired access token using a refresh token."""
    config = PROVIDERS[provider]

    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token_str,
        "client_id": config.client_id,
    }

    req = Request(
        config.token_endpoint,
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"},
    )

    try:
        with urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
        result["obtained_at"] = time.time()
        return result
    except HTTPError as e:
        body = e.read().decode() if e.fp else ""
        raise RuntimeError(f"Token refresh failed ({e.code}): {body}") from e


def get_valid_token(provider: str) -> str | None:
    """Get a valid access token, refreshing if necessary."""
    token = load_token(provider)
    if not token:
        return None

    access_token = token.get("access_token")
    if not access_token:
        return None

    # Check if expired
    obtained = token.get("obtained_at", 0)
    expires_in = token.get("expires_in", 3600)
    if time.time() - obtained > expires_in - 60:
        # Needs refresh
        refresh = token.get("refresh_token")
        if refresh:
            try:
                new_token = refresh_token(provider, refresh)
                save_token(provider, new_token)
                return new_token["access_token"]
            except RuntimeError:
                delete_token(provider)
                return None
        return None

    return access_token


# ── CLI ────────────────────────────────────────────────────────────


def login(provider: str, auto_open: bool = True) -> bool:
    """Run the OAuth device flow login.

    Returns True if login succeeded.
    """
    print(f"\n🔑 Logging in to {provider}...\n")

    try:
        auth = request_device_auth(provider)
    except RuntimeError as e:
        print(f"❌ {e}")
        return False

    print(f"   1. Open: {auth.verification_uri}")
    print(f"   2. Enter code: {auth.user_code}")
    print(f"   (Code expires in {auth.expires_in}s)\n")

    if auto_open:
        try:
            webbrowser.open(auth.verification_uri_complete)
            print("   🌐 Browser opened automatically.\n")
        except Exception:
            pass

    print("   ⏳ Waiting for authorization...", end="", flush=True)

    try:
        token = poll_token(provider, auth.device_code, auth.interval, timeout=600)
        save_token(provider, token)
        print(" ✅\n")
        print(f"   Logged in to {provider} successfully!\n")
        return True
    except (RuntimeError, TimeoutError) as e:
        print(f"\n❌ {e}")
        return False


def logout(provider: str) -> None:
    """Remove stored credentials for a provider."""
    delete_token(provider)
    print(f"   Logged out from {provider}.")


def status(provider: str | None = None) -> None:
    """Show login status for one or all providers."""
    providers = [provider] if provider else list(PROVIDERS)
    for p in providers:
        token = load_token(p)
        if token:
            obtained = token.get("obtained_at", 0)
            expires_in = token.get("expires_in", 3600)
            remaining = int(expires_in - (time.time() - obtained))
            state = "✅ valid" if remaining > 60 else "⚠️  expiring"
            print(f"   {p}: {state} ({max(0, remaining)}s remaining)")
        else:
            print(f"   {p}: ❌ not logged in")
