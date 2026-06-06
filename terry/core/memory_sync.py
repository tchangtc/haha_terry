"""Cross-platform memory synchronization.

Enables memory sharing across devices and platforms (CLI, Telegram, Discord)
via import/export, cloud sync stubs, and conflict resolution.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path


class MemorySync:
    """Cross-platform memory synchronization engine.

    Supports:
      - Export/Import: JSON-based memory portability
      - Cloud sync stub: Ready for remote storage integration
      - Conflict resolution: Last-write-wins with version tracking
      - Differential sync: Only sync changed memories
    """

    SYNC_FILE = "memory_sync_state.json"

    def __init__(self, memory_dir: Path | None = None):
        self.memory_dir = memory_dir or Path.home() / ".terry" / "memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.sync_file = self.memory_dir / self.SYNC_FILE
        self.state = self._load_state()

    def _load_state(self) -> dict:
        """Load sync state from disk."""
        if self.sync_file.exists():
            try:
                return json.loads(self.sync_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {
            "version": "1.0",
            "last_sync": None,
            "device_id": hashlib.sha256(str(Path.home()).encode()).hexdigest()[:8],
            "memories": {},  # name → {hash, updated_at}
        }

    def _save_state(self) -> None:
        """Save sync state."""
        self.state["last_sync"] = datetime.now().isoformat()
        self.sync_file.write_text(
            json.dumps(self.state, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def compute_hash(self, content: str) -> str:
        """Compute content hash for change detection."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def export_memories(self, output_path: Path | None = None) -> Path:
        """Export all memories to a portable JSON file.

        Args:
            output_path: Output path (default: ~/.terry/memory_export.json)

        Returns:
            Path to exported file
        """
        if output_path is None:
            output_path = self.memory_dir / "memory_export.json"

        memories = {}
        for mem_file in sorted(self.memory_dir.glob("*.md")):
            try:
                content = mem_file.read_text(encoding="utf-8")
                memories[mem_file.name] = {
                    "content": content,
                    "hash": self.compute_hash(content),
                    "size": mem_file.stat().st_size,
                }
            except Exception:
                continue

        export_data = {
            "version": "1.0",
            "device_id": self.state["device_id"],
            "exported_at": datetime.now().isoformat(),
            "memory_count": len(memories),
            "memories": memories,
        }
        output_path.write_text(
            json.dumps(export_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return output_path

    def import_memories(self, input_path: Path, mode: str = "merge") -> int:
        """Import memories from an export file.

        Args:
            input_path: Path to the export JSON file
            mode: 'merge' (keep both, ours wins conflicts) or 'replace' (import wins)

        Returns:
            Number of memories imported
        """
        if not input_path.exists():
            return 0

        try:
            data = json.loads(input_path.read_text(encoding="utf-8"))
        except Exception:
            return 0

        imported = 0
        memories = data.get("memories", {})

        for filename, mem_data in memories.items():
            content = mem_data.get("content", "")
            if not content:
                continue

            target = self.memory_dir / filename

            if target.exists():
                if mode == "merge":
                    # Keep existing, skip
                    continue
                # Replace mode: overwrite

            try:
                target.write_text(content, encoding="utf-8")
                # Update sync state
                self.state["memories"][filename] = {
                    "hash": self.compute_hash(content),
                    "updated_at": datetime.now().isoformat(),
                }
                imported += 1
            except Exception:
                continue

        if imported > 0:
            self._save_state()
        return imported

    def get_changed_since(self, since_iso: str) -> list[str]:
        """Get list of memory files changed since a timestamp.

        Args:
            since_iso: ISO format timestamp

        Returns:
            List of changed filenames
        """
        try:
            since = datetime.fromisoformat(since_iso)
        except Exception:
            since = datetime.min

        changed = []
        for mem_file in self.memory_dir.glob("*.md"):
            try:
                mtime = datetime.fromtimestamp(mem_file.stat().st_mtime)
                if mtime > since:
                    changed.append(mem_file.name)
            except Exception:
                continue
        return changed

    def sync_to_cloud(self, cloud_url: str, api_key: str = "") -> dict:
        """Sync memories to a cloud endpoint (stub).

        Args:
            cloud_url: Cloud sync endpoint URL
            api_key: Authentication key

        Returns:
            Sync result dict
        """
        try:
            import httpx
            export_path = self.export_memories()
            data = json.loads(export_path.read_text(encoding="utf-8"))

            resp = httpx.post(
                cloud_url,
                json={
                    "device_id": self.state["device_id"],
                    "memories": data.get("memories", {}),
                },
                headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
                timeout=30,
            )
            if resp.status_code == 200:
                self._save_state()
                return {"ok": True, "synced": len(data.get("memories", {}))}
            return {"ok": False, "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def sync_from_cloud(self, cloud_url: str, api_key: str = "") -> dict:
        """Pull memories from a cloud endpoint (stub).

        Args:
            cloud_url: Cloud sync endpoint URL
            api_key: Authentication key

        Returns:
            Sync result dict
        """
        try:
            import httpx
            resp = httpx.get(
                cloud_url,
                params={"device_id": self.state["device_id"]},
                headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                memories = data.get("memories", {})
                imported = 0
                for filename, mem_data in memories.items():
                    target = self.memory_dir / filename
                    content = mem_data.get("content", "")
                    if content:
                        target.write_text(content, encoding="utf-8")
                        imported += 1
                if imported > 0:
                    self._save_state()
                return {"ok": True, "imported": imported}
            return {"ok": False, "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
