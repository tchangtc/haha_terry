"""Platform detection and cross-platform utilities."""

from __future__ import annotations

import os
import platform
import sys
from pathlib import Path


def get_platform() -> str:
    """Get current platform name.

    Returns:
        'windows', 'macos', 'linux', or 'unknown'
    """
    system = platform.system().lower()
    if system == 'windows':
        return 'windows'
    elif system == 'darwin':
        return 'macos'
    elif system == 'linux':
        return 'linux'
    else:
        return 'unknown'


def is_windows() -> bool:
    """Check if running on Windows."""
    return get_platform() == 'windows'


def is_macos() -> bool:
    """Check if running on macOS."""
    return get_platform() == 'macos'


def is_linux() -> bool:
    """Check if running on Linux."""
    return get_platform() == 'linux'


def is_mobile() -> bool:
    """Check if running on mobile platform (Android/iOS).

    Note: This is a basic check. Mobile Python environments
    (like Termux on Android or Pythonista on iOS) have limitations.
    """
    # Check for Android (Termux)
    if 'ANDROID_ROOT' in os.environ or 'TERMUX_VERSION' in os.environ:
        return True

    # Check for iOS (Pythonista)
    if sys.platform == 'ios':
        return True

    return False


def get_shell() -> str:
    """Get appropriate shell for current platform.

    Returns:
        Shell command string
    """
    if is_windows():
        # Use cmd.exe on Windows
        return 'cmd.exe'
    else:
        # Use sh/bash on Unix-like systems
        return os.environ.get('SHELL', '/bin/sh')


def get_shell_args(command: str) -> list[str]:
    """Get shell arguments for executing a command.

    Args:
        command: Command to execute

    Returns:
        List of arguments for subprocess
    """
    if is_windows():
        return ['cmd.exe', '/c', command]
    else:
        return [get_shell(), '-c', command]


def normalize_path(path: str | Path) -> Path:
    """Normalize path for current platform.

    Args:
        path: Path to normalize

    Returns:
        Normalized Path object
    """
    return Path(path).expanduser().resolve()


def get_config_dir() -> Path:
    """Get platform-appropriate config directory.

    Returns:
        Path to config directory
    """
    if is_windows():
        base = Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming'))
    elif is_macos():
        base = Path.home() / 'Library' / 'Application Support'
    else:
        base = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))

    return base / 'terry'


def get_data_dir() -> Path:
    """Get platform-appropriate data directory.

    Returns:
        Path to data directory
    """
    if is_windows():
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
    elif is_macos():
        base = Path.home() / 'Library' / 'Application Support'
    else:
        base = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share'))

    return base / 'terry'


def get_cache_dir() -> Path:
    """Get platform-appropriate cache directory.

    Returns:
        Path to cache directory
    """
    if is_windows():
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
        return base / 'terry' / 'cache'
    elif is_macos():
        return Path.home() / 'Library' / 'Caches' / 'terry'
    else:
        base = Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache'))
        return base / 'terry'
