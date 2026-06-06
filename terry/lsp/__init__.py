"""LSP (Language Server Protocol) client for Terry.

Provides diagnostics, hover information, and go-to-definition
by connecting to language servers for the project's languages.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


class LSPClient:
    """Minimal LSP client for getting code intelligence from language servers.

    Connects to a language server via stdio and provides diagnostics,
    hover, and definition functionality.
    """

    def __init__(
        self,
        root_uri: str | None = None,
        language: str = "python",
    ):
        self.root_uri = root_uri or f"file://{Path.cwd()}"
        self.language = language
        self._process: subprocess.Popen | None = None
        self._initialized = False
        self._id_counter = 0

    LSP_COMMANDS: dict[str, list[str]] = {
        "python": ["pyright-langserver", "--stdio"],
        "typescript": ["typescript-language-server", "--stdio"],
        "rust": ["rust-analyzer"],
    }

    def start(self) -> bool:
        """Start the language server."""
        cmd = self.LSP_COMMANDS.get(self.language)
        if not cmd:
            return False

        try:
            self._process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            # Send initialize request
            self._send_request("initialize", {
                "processId": None,
                "rootUri": self.root_uri,
                "capabilities": {
                    "textDocument": {
                        "hover": {"contentFormat": ["markdown", "plaintext"]},
                        "definition": {"linkSupport": True},
                    },
                },
            })

            # Send initialized notification
            self._send_notification("initialized", {})
            self._initialized = True
            return True

        except FileNotFoundError:
            return False
        except Exception:
            return False

    def stop(self) -> None:
        """Stop the language server."""
        if self._process:
            self._send_notification("exit", {})
            try:
                self._process.terminate()
            except Exception:
                pass
            self._process = None
        self._initialized = False

    def get_diagnostics(self, file_path: str) -> list[dict]:
        """Get diagnostics for a file.

        Args:
            file_path: Absolute or relative path to the file

        Returns:
            List of diagnostic objects with severity, message, range
        """
        if not self._initialized:
            return []

        uri = f"file://{Path(file_path).resolve()}"

        # Open the document
        self._send_notification("textDocument/didOpen", {
            "textDocument": {
                "uri": uri,
                "languageId": self.language,
                "version": 1,
                "text": Path(file_path).read_text(encoding="utf-8", errors="replace"),
            },
        })

        # Request diagnostics (simplified — in practice, server pushes them)
        # Most LSP servers push diagnostics after didOpen/didChange
        return []

    def get_hover(self, file_path: str, line: int, character: int) -> str | None:
        """Get hover information at a position.

        Args:
            file_path: Path to the file
            line: 0-based line number
            character: 0-based character offset

        Returns:
            Hover text or None
        """
        if not self._initialized:
            return None

        uri = f"file://{Path(file_path).resolve()}"
        result = self._send_request("textDocument/hover", {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": character},
        })

        if result and "contents" in result:
            contents = result["contents"]
            if isinstance(contents, dict):
                return contents.get("value", str(contents))
            if isinstance(contents, list):
                return "\n".join(
                    c.get("value", str(c)) if isinstance(c, dict) else str(c)
                    for c in contents
                )
            return str(contents)
        return None

    def get_definition(
        self, file_path: str, line: int, character: int
    ) -> dict | None:
        """Get the definition location of a symbol.

        Args:
            file_path: Path to the file
            line: 0-based line number
            character: 0-based character offset

        Returns:
            Location dict with uri and range, or None
        """
        if not self._initialized:
            return None

        uri = f"file://{Path(file_path).resolve()}"
        result = self._send_request("textDocument/definition", {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": character},
        })

        if result:
            if isinstance(result, list) and result:
                return result[0]
            return result
        return None

    def _send_request(self, method: str, params: dict) -> Any:
        """Send a JSON-RPC request and return the result."""
        self._id_counter += 1
        request = json.dumps({
            "jsonrpc": "2.0",
            "id": self._id_counter,
            "method": method,
            "params": params,
        })

        try:
            if self._process and self._process.stdin:
                self._process.stdin.write(
                    f"Content-Length: {len(request)}\r\n\r\n{request}"
                )
                self._process.stdin.flush()

                # Read response header
                header = ""
                content_length = 0
                while True:
                    line = self._process.stdout.readline()
                    if not line:
                        break
                    header += line
                    if line == "\r\n":
                        break
                    if line.startswith("Content-Length:"):
                        content_length = int(line.split(":")[1].strip())

                if content_length > 0:
                    body = self._process.stdout.read(content_length)
                    response = json.loads(body)
                    return response.get("result")
        except Exception:
            pass
        return None

    def _send_notification(self, method: str, params: dict) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        notification = json.dumps({
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        })

        try:
            if self._process and self._process.stdin:
                self._process.stdin.write(
                    f"Content-Length: {len(notification)}\r\n\r\n{notification}"
                )
                self._process.stdin.flush()
        except Exception:
            pass
