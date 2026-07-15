"""Image and PDF reading tool - multimodal input support."""

from __future__ import annotations

import base64
from pathlib import Path

from . import BaseTool, tool_registry


class ReadImageTool(BaseTool):
    """Read image and PDF files, returning base64-encoded data for multimodal models."""
    risk_level = "read_only"
    category = "file"

    name = "read_image"
    description = (
        "Read an image (PNG, JPG, GIF, WEBP) or PDF file and return it as base64 data "
        "for vision-capable models. Use this to ask questions about images, diagrams, "
        "screenshots, or PDF documents."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the image or PDF file",
            },
            "detail": {
                "type": "string",
                "enum": ["low", "high", "auto"],
                "description": "Image detail level for vision models (default: auto)",
            },
        },
        "required": ["path"],
    }

    IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}
    PDF_EXTENSIONS = {".pdf"}

    def __init__(self, workdir: Path | None = None):
        self.workdir = workdir or Path.cwd()

    def execute(self, path: str, detail: str = "auto") -> str:
        """Read and encode image/PDF file."""
        try:
            file_path = (self.workdir / path).resolve()
            if not file_path.is_relative_to(self.workdir.resolve()):
                return f"Error: Path escapes workspace: {path}"

            if not file_path.exists():
                return f"Error: File not found: {path}"

            ext = file_path.suffix.lower()

            if ext in self.IMAGE_EXTENSIONS:
                return self._read_image(file_path, detail)
            elif ext in self.PDF_EXTENSIONS:
                return self._read_pdf(file_path)
            else:
                return (
                    f"Error: Unsupported file type '{ext}'. "
                    f"Supported: {', '.join(sorted(self.IMAGE_EXTENSIONS | self.PDF_EXTENSIONS))}"
                )

        except Exception as e:
            return f"Error: {e}"

    def _read_image(self, file_path: Path, detail: str) -> str:
        """Read and encode an image file."""
        data = file_path.read_bytes()

        # Determine media type
        ext = file_path.suffix.lower()
        media_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".bmp": "image/bmp",
            ".svg": "image/svg+xml",
        }
        media_type = media_types.get(ext, "application/octet-stream")

        # Limit size (10MB)
        if len(data) > 10 * 1024 * 1024:
            return f"Error: File too large ({len(data)} bytes, max 10MB)"

        encoded = base64.b64encode(data).decode("ascii")

        return (
            f"[Image: {file_path.name}]\n"
            f"Media type: {media_type}\n"
            f"Size: {len(data)} bytes ({len(data) / 1024:.1f} KB)\n"
            f"Detail: {detail}\n"
            f"Base64 length: {len(encoded)} chars\n\n"
            f'{{"type": "image", "source": {{"type": "base64", '
            f'"media_type": "{media_type}", "data": "{encoded}"}}}}'
        )

    def _read_pdf(self, file_path: Path) -> str:
        """Read a PDF file (basic text extraction or base64 encoding)."""
        data = file_path.read_bytes()

        if len(data) > 20 * 1024 * 1024:
            return f"Error: PDF too large ({len(data)} bytes, max 20MB)"

        # Try PyMuPDF for text extraction, fallback to base64
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(file_path)
            pages_text = []
            for page_num in range(min(len(doc), 20)):
                page = doc[page_num]
                pages_text.append(f"--- Page {page_num + 1} ---\n{page.get_text()}")
            doc.close()
            return (
                f"[PDF: {file_path.name}]\n"
                f"Pages: {len(doc)} (showing first {min(len(doc), 20)})\n\n"
                + "\n".join(pages_text)
            )
        except ImportError:
            # Fallback: encode as base64
            encoded = base64.b64encode(data).decode("ascii")
            return (
                f"[PDF: {file_path.name}]\n"
                f"Size: {len(data)} bytes\n"
                f"Base64: {encoded[:200]}...\n\n"
                f"(Install PyMuPDF for text extraction: pip install PyMuPDF)"
            )


# Auto-register
tool_registry.register(ReadImageTool())
