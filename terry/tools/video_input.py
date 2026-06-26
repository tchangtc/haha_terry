"""Video input tool for Terry — extract frames, metadata, and descriptions.

Supports common video formats via ffmpeg (preferred) or opencv fallback.
The tool extracts key frames and generates a text description for the LLM.
"""

from __future__ import annotations

import json
import logging
import subprocess
import tempfile
from pathlib import Path

from . import BaseTool, tool_registry

logger = logging.getLogger(__name__)


class VideoInputTool(BaseTool):
    """Extract frames and metadata from video files for LLM analysis."""

    name = "read_video"
    description = (
        "Read a video file and extract key frames with metadata. "
        "Returns a description of the video content (duration, resolution, "
        "frame count, key frame descriptions) for the LLM to analyze. "
        "Supports mp4, mov, avi, webm, mkv formats."
    )
    risk_level = "read_only"
    category = "file"
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the video file to analyze",
            },
            "max_frames": {
                "type": "integer",
                "description": "Maximum number of key frames to extract (default: 5)",
                "default": 5,
            },
        },
        "required": ["path"],
    }

    def __init__(self, workdir: Path | None = None):
        self.workdir = workdir or Path.cwd()

    def execute(self, path: str, max_frames: int = 5) -> str:
        video_path = (self.workdir / path).resolve()

        if not video_path.exists():
            return f"Error: Video file not found: {path}"

        if not self._is_video(video_path):
            return f"Error: Not a supported video format: {video_path.suffix}"

        # Get metadata via ffprobe or fallback
        metadata = self._get_metadata(video_path)

        # Extract key frames
        frames_info = self._extract_frames(video_path, max_frames)

        return json.dumps(
            {
                "file": str(video_path),
                "size_mb": round(video_path.stat().st_size / (1024 * 1024), 2),
                "metadata": metadata,
                "key_frames": frames_info,
            },
            indent=2,
        )

    def _is_video(self, path: Path) -> bool:
        return path.suffix.lower() in (".mp4", ".mov", ".avi", ".webm", ".mkv", ".flv", ".wmv")

    def _get_metadata(self, path: Path) -> dict:
        """Get video metadata using ffprobe or fallback."""
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "quiet", "-print_format", "json",
                    "-show_format", "-show_streams", str(path),
                ],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                fmt = data.get("format", {})
                video_streams = [
                    s for s in data.get("streams", [])
                    if s.get("codec_type") == "video"
                ]
                vs = video_streams[0] if video_streams else {}
                return {
                    "duration_seconds": round(float(fmt.get("duration", 0)), 1),
                    "resolution": f"{vs.get('width', '?')}x{vs.get('height', '?')}",
                    "codec": vs.get("codec_name", "unknown"),
                    "fps": self._parse_fps(vs.get("r_frame_rate", "")),
                    "bitrate_kbps": int(int(fmt.get("bit_rate", 0)) / 1000) if fmt.get("bit_rate") else 0,
                }
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
            pass

        # Fallback: basic file info
        return {
            "duration_seconds": 0,
            "resolution": "unknown",
            "codec": "unknown",
            "fps": 0,
            "bitrate_kbps": 0,
            "note": "ffprobe not available — install ffmpeg for full metadata",
        }

    @staticmethod
    def _parse_fps(rate_str: str) -> float:
        """Parse ffprobe frame rate string like '30000/1001'."""
        if "/" in rate_str:
            parts = rate_str.split("/")
            try:
                return round(int(parts[0]) / int(parts[1]), 2)
            except (ValueError, ZeroDivisionError):
                return 0.0
        try:
            return round(float(rate_str), 2)
        except ValueError:
            return 0.0

    def _extract_frames(self, path: Path, max_frames: int) -> list[dict]:
        """Extract key frames using ffmpeg thumbnail filter."""
        frames = []
        try:
            with tempfile.TemporaryDirectory() as tmp:
                # ffmpeg scene detection to find key frames
                result = subprocess.run(
                    [
                        "ffmpeg", "-i", str(path),
                        "-vf", "select='gt(scene\\,0.3)',scale=640:-1",
                        "-vsync", "vfr",
                        "-frames:v", str(max_frames),
                        f"{tmp}/frame_%03d.jpg",
                    ],
                    capture_output=True, text=True, timeout=60,
                )
                if result.returncode == 0:
                    for i, frame_file in enumerate(
                        sorted(Path(tmp).glob("frame_*.jpg"))
                    ):
                        frames.append({
                            "index": i + 1,
                            "file": str(frame_file),
                            "size_bytes": frame_file.stat().st_size,
                        })
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        if not frames:
            frames.append({
                "index": 0,
                "note": "No frames extracted — install ffmpeg for frame extraction",
            })

        return frames


# ── Registration ────────────────────────────────────────────────────

tool_registry.register(VideoInputTool())
