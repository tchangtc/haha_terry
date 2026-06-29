"""External editor integration for Terry.

Respects $VISUAL and $EDITOR environment variables (gemini-cli +62).
Lets users open files in their preferred editor directly from Terry.

Usage:
    from terry.core.editor import open_in_editor
    open_in_editor("src/main.py")  # Opens in $VISUAL or $EDITOR
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def detect_editor() -> str:
    """Detect the user's preferred editor.

    Priority: $VISUAL → $EDITOR → platform defaults.
    """
    for var in ("VISUAL", "EDITOR"):
        editor = os.environ.get(var, "").strip()
        if editor:
            return editor

    # Platform defaults
    if os.name == "nt":
        return "notepad.exe"
    if os.environ.get("TERM", ""):
        for candidate in ("vim", "vi", "nano", "emacs"):
            if shutil_which(candidate):
                return candidate
    return "nano"


def open_in_editor(filepath: str | Path, line: int = 0) -> bool:
    """Open a file in the user's preferred editor.

    Args:
        filepath: Path to the file to open
        line: Optional line number to jump to

    Returns:
        True if editor launched successfully
    """
    path = Path(filepath).resolve()
    if not path.exists():
        logger.warning("File not found: %s", filepath)
        return False

    editor = detect_editor()
    if not editor:
        logger.warning("No editor configured — set $VISUAL or $EDITOR")
        return False

    cmd: list[str] = _build_command(editor, str(path), line)
    try:
        subprocess.Popen(cmd, start_new_session=True)
        return True
    except (OSError, subprocess.SubprocessError) as e:
        logger.warning("Failed to launch editor '%s': %s", editor, e)
        return False


def _build_command(editor: str, path: str, line: int) -> list[str]:
    """Build the editor command with line number support."""
    base = editor.split()

    # Vim/Neovim: +line
    if any(v in base[0] for v in ("vim", "nvim", "vi")):
        if line > 0:
            return base[:1] + [f"+{line}", path]
        return base[:1] + [path]

    # VS Code / Cursor
    if any(v in base[0] for v in ("code", "cursor", "codium")):
        goto = f"{path}:{line}" if line > 0 else path
        return base[:1] + ["--goto", goto]

    # Emacs
    if "emacs" in base[0]:
        if line > 0:
            return base[:1] + [f"+{line}", path]
        return base[:1] + [path]

    # Nano: +line,column
    if "nano" in base[0]:
        if line > 0:
            return base[:1] + [f"+{line}", path]
        return base[:1] + [path]

    # Generic: just open the file
    return base[:1] + [path]


def shutil_which(cmd: str) -> str | None:
    """Cross-platform which() for finding executables."""
    import shutil
    return shutil.which(cmd)


def get_editor_info() -> dict:
    """Get information about the current editor configuration."""
    editor = detect_editor()
    return {
        "editor": editor,
        "visual": os.environ.get("VISUAL", ""),
        "editor_env": os.environ.get("EDITOR", ""),
        "available": shutil_which(editor.split()[0]) is not None if editor else False,
    }
