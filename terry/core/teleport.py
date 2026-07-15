"""Session Teleportation — cross-machine session export and import.

Exports an agent session to a portable .tar.gz archive containing:
  - session.json: messages, config (no api_key), metadata
  - checkpoints/: git patch files and checkpoint index
  - manifest.json: version and integrity info

Usage:
    exporter = TeleportExporter()
    path = exporter.export(agent, "my-session")

    importer = TeleportImporter()
    importer.import_archive(agent, path)
"""

from __future__ import annotations

import json
import logging
import shutil
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MANIFEST_VERSION = 1


class TeleportExporter:
    """Export an agent session to a portable archive."""

    def export(self, agent: Any, name: str = "") -> Path:
        """Export current session state to a .terry-teleport archive.

        Args:
            agent: The Agent instance to export from.
            name: Optional name for the archive.

        Returns:
            Path to the created archive file.
        """
        safe_name = "".join(c if c.isalnum() or c in "-_" else "-" for c in (name or "session"))
        archive_name = f"{safe_name}.terry-teleport.tar.gz"
        archive_path = Path.cwd() / archive_name

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            # 1. Session metadata (no api_key)
            session_data = {
                "version": MANIFEST_VERSION,
                "exported_at": datetime.now().isoformat(),
                "terry_version": getattr(__import__("terry"), "__version__", "unknown"),
                "message_count": len(agent.messages),
                "tool_call_count": agent.tool_call_count,
                "workdir": str(agent.workdir),
                "mode": agent.get_mode(),
            }
            # Config without api_key
            config_dict = agent.config._to_dict()
            if "model" in config_dict and "api_key" in config_dict.get("model", {}):
                config_dict["model"]["api_key"] = None

            session_data["config"] = config_dict
            (tmp / "session.json").write_text(json.dumps(session_data, indent=2), encoding="utf-8")

            # 2. Messages as JSONL
            messages = []
            for msg in agent.messages:
                if isinstance(msg, dict):
                    messages.append(msg)
            if messages:
                (tmp / "messages.jsonl").write_text(
                    "\n".join(json.dumps(m, ensure_ascii=False) for m in messages),
                    encoding="utf-8",
                )

            # 3. Checkpoint patches
            if agent.checkpoint_manager:
                cps = agent.checkpoint_manager.list_checkpoints()
                if cps:
                    cps_dir = tmp / "checkpoints"
                    cps_dir.mkdir()
                    cp_index = []
                    for cp in cps[:10]:  # Only export last 10
                        cp_index.append({
                            "id": cp.get("id", ""),
                            "tag": cp.get("tag", ""),
                            "timestamp": cp.get("timestamp", ""),
                        })
                        src = Path(agent.checkpoint_manager.checkpoints_dir) / cp.get("id", "")
                        if src.exists():
                            dst = cps_dir / cp.get("id", "")
                            if src.is_dir():
                                shutil.copytree(src, dst, dirs_exist_ok=True)
                    (cps_dir / "index.json").write_text(json.dumps(cp_index, indent=2))

            # 4. Manifest
            manifest = {
                "version": MANIFEST_VERSION,
                "name": safe_name,
                "exported_at": session_data["exported_at"],
                "files": [f.name for f in tmp.rglob("*") if f.is_file()],
            }
            (tmp / "manifest.json").write_text(json.dumps(manifest, indent=2))

            # 5. Create archive
            with tarfile.open(archive_path, "w:gz") as tar:
                for f in tmp.rglob("*"):
                    if f.is_file():
                        tar.add(f, arcname=f.relative_to(tmp))

        logger.info("Teleport exported: %s (%d messages)", archive_name, len(messages))
        return archive_path


class TeleportImporter:
    """Import a teleport archive into an agent session."""

    def import_archive(self, agent: Any, archive_path: Path) -> dict[str, Any]:
        """Import session state from a teleport archive.

        Args:
            agent: The Agent instance to import into.
            archive_path: Path to the .terry-teleport.tar.gz file.

        Returns:
            Dict with import summary: {restored, messages, checkpoints, warnings}
        """
        if not archive_path.exists():
            return {"restored": False, "error": f"Archive not found: {archive_path}"}

        result = {"restored": False, "messages": 0, "checkpoints": 0, "warnings": []}

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            with tarfile.open(archive_path, "r:gz") as tar:
                tar.extractall(tmp, filter="data")

            # Validate manifest
            manifest_file = tmp / "manifest.json"
            if not manifest_file.exists():
                return {"restored": False, "error": "Invalid archive: no manifest.json"}

            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
            if manifest.get("version", 0) > MANIFEST_VERSION:
                result["warnings"].append(
                    f"Archive version {manifest['version']} is newer than this Terry. Some data may be skipped."
                )

            # Restore messages
            messages_file = tmp / "messages.jsonl"
            if messages_file.exists():
                restored = []
                for line in messages_file.read_text(encoding="utf-8").strip().split("\n"):
                    if line.strip():
                        try:
                            restored.append(json.loads(line))
                        except json.JSONDecodeError:
                            result["warnings"].append("Skipped malformed message line")
                agent.messages = restored
                result["messages"] = len(restored)
                result["restored"] = True

            # Restore checkpoints
            cps_dir = tmp / "checkpoints"
            if cps_dir.exists() and agent.checkpoint_manager:
                cp_index = json.loads((cps_dir / "index.json").read_text(encoding="utf-8"))
                for cp in cp_index:
                    src = cps_dir / cp["id"]
                    dst = agent.checkpoint_manager.checkpoints_dir / cp["id"]
                    if src.exists() and not dst.exists():
                        shutil.copytree(src, dst, dirs_exist_ok=True)
                        result["checkpoints"] += 1

            logger.info(
                "Teleport imported: %d messages, %d checkpoints",
                result["messages"], result["checkpoints"],
            )

        return result
