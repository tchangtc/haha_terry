"""Automatic backup for agent data — config, memory, sessions, tokens.

Hermes users (+27) demand this. Backs up ~/.terry/ to a configurable
location on schedule, with rotation and compression.

Usage:
    from terry.core.auto_backup import AutoBackup
    backup = AutoBackup()
    backup.run()  # Creates a timestamped backup
    backup.list_backups()
    backup.restore("backup-2026-06-29.tar.gz")
"""

from __future__ import annotations

import json
import logging
import tarfile
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_MAX_BACKUPS = 10
BYTES_PER_MB = 1024 * 1024
DEFAULT_BACKUP_INTERVAL_HOURS = 24
BACKUP_NAME_FORMAT = "terry-backup-%Y%m%d-%H%M%S"


class AutoBackup:
    """Automatic backup and restore for Terry agent data."""

    def __init__(self, backup_dir: Path | None = None,
                 source_dir: Path | None = None,
                 max_backups: int = DEFAULT_MAX_BACKUPS):
        if backup_dir is None:
            backup_dir = Path.home() / ".local" / "share" / "terry" / "backups"
        self._dir = backup_dir
        self._dir.mkdir(parents=True, exist_ok=True)

        if source_dir is None:
            from terry.core.platform_utils import get_terry_dir
            source_dir = get_terry_dir()
        self._source = source_dir
        self._max = max_backups
        self._index_path = self._dir / "index.json"
        self._index: list[dict] = []
        self._load_index()

    def _load_index(self):
        if self._index_path.exists():
            try:
                self._index = json.loads(self._index_path.read_text())
            except (json.JSONDecodeError, KeyError):
                self._index = []

    def _save_index(self):
        self._index_path.write_text(json.dumps(self._index, indent=2))

    def run(self) -> str | None:
        """Create a new backup. Returns backup name or None if failed."""
        name = datetime.now().strftime(BACKUP_NAME_FORMAT)
        archive = self._dir / f"{name}.tar.gz"

        try:
            with tarfile.open(archive, "w:gz") as tar:
                if self._source.exists():
                    for item in self._source.iterdir():
                        # Skip large cache files and old backups
                        if item.name in ("backups", "__pycache__", ".cache"):
                            continue
                        try:
                            tar.add(item, arcname=item.name)
                        except (OSError, PermissionError):
                            pass

            size_bytes = archive.stat().st_size
            self._index.append({
                "name": name,
                "timestamp": time.time(),
                "size_bytes": size_bytes,
                "files": len(tarfile.open(archive).getnames()),
            })
            self._save_index()
            self._rotate()
            logger.info("Backup created: %s (%d bytes)", name, size_bytes)
            return name
        except (OSError, tarfile.TarError) as e:
            logger.warning("Backup failed: %s", e)
            if archive.exists():
                archive.unlink()
            return None

    def list_backups(self) -> list[dict]:
        """List available backups, newest first."""
        return sorted(self._index, key=lambda b: b["timestamp"], reverse=True)

    def restore(self, name: str) -> bool:
        """Restore from a backup archive."""
        archive = self._dir / f"{name}.tar.gz"
        if not archive.exists():
            logger.warning("Backup not found: %s", name)
            return False

        try:
            with tarfile.open(archive, "r:gz") as tar:
                tar.extractall(path=self._source, filter="data")
            logger.info("Restored from backup: %s", name)
            return True
        except (OSError, tarfile.TarError) as e:
            logger.warning("Restore failed: %s", e)
            return False

    def delete(self, name: str) -> bool:
        """Delete a backup archive."""
        archive = self._dir / f"{name}.tar.gz"
        if archive.exists():
            archive.unlink()
        self._index = [b for b in self._index if b["name"] != name]
        self._save_index()
        return True

    def _rotate(self):
        """Remove oldest backups beyond max limit."""
        while len(self._index) > self._max:
            oldest = min(self._index, key=lambda b: b["timestamp"])
            self.delete(oldest["name"])

    def get_stats(self) -> dict:
        total_size = sum(b.get("size_bytes", 0) for b in self._index)
        return {
            "total_backups": len(self._index),
            "total_size_mb": round(total_size / (BYTES_PER_MB), 2),
            "max_backups": self._max,
            "directory": str(self._dir),
        }
