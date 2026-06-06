"""File checkpoint system - save and restore file state snapshots."""

from __future__ import annotations

import json
import shutil
import subprocess
import tarfile
from datetime import datetime
from pathlib import Path
from typing import Any


class CheckpointManager:
    """Creates and manages file-level snapshots for undo/recovery.

    Supports two strategies:
      - Git-based: stores git hash + diff (lightweight, for git repos)
      - Tar-based: copies changed files (for non-git directories)

    Auto-creates snapshots before destructive operations (write_file, edit_file).
    """

    MAX_CHECKPOINTS = 50

    def __init__(
        self,
        workdir: Path,
        checkpoints_dir: Path | None = None,
    ):
        self.workdir = workdir.resolve()
        self.checkpoints_dir = checkpoints_dir or (
            Path.home() / ".terry" / "checkpoints"
        )
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
        self._index_file = self.checkpoints_dir / "checkpoint_index.json"
        self._index: list[dict[str, Any]] = []
        self._load_index()

    def _load_index(self) -> None:
        """Load checkpoint index from disk."""
        if self._index_file.exists():
            try:
                self._index = json.loads(self._index_file.read_text(encoding="utf-8"))
            except Exception:
                self._index = []

    def _save_index(self) -> None:
        """Save checkpoint index to disk."""
        self._index_file.write_text(
            json.dumps(self._index, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _is_git_repo(self) -> bool:
        """Check if workdir is inside a git repository."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=self.workdir,
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    def snapshot(self, tag: str = "", paths: list[str] | None = None) -> str:
        """Create a snapshot of current state.

        Args:
            tag: Human-readable label (e.g., "before-edit-main.py")
            paths: Specific files to snapshot (None = auto-detect changed files)

        Returns:
            Checkpoint ID
        """
        checkpoint_id = datetime.now().strftime("cp_%Y%m%d_%H%M%S_%f")
        cp_dir = self.checkpoints_dir / checkpoint_id
        cp_dir.mkdir(parents=True, exist_ok=True)

        is_git = self._is_git_repo()

        if is_git:
            # Git-based: store current HEAD + working tree diff
            self._snapshot_git(checkpoint_id, cp_dir)
        else:
            # Tar-based: save specified files
            self._snapshot_tar(cp_dir, paths)

        entry = {
            "id": checkpoint_id,
            "tag": tag,
            "timestamp": datetime.now().isoformat(),
            "method": "git" if is_git else "tar",
            "paths": paths or [],
        }
        self._index.append(entry)

        # Prune old checkpoints
        while len(self._index) > self.MAX_CHECKPOINTS:
            old = self._index.pop(0)
            old_dir = self.checkpoints_dir / old["id"]
            if old_dir.exists():
                shutil.rmtree(old_dir, ignore_errors=True)

        self._save_index()
        return checkpoint_id

    def _snapshot_git(self, cp_id: str, cp_dir: Path) -> None:
        """Create git-based checkpoint."""
        # Get current HEAD
        head_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.workdir,
            capture_output=True,
            text=True,
            timeout=10,
        )
        head_hash = head_result.stdout.strip() if head_result.returncode == 0 else "unknown"

        # Get working tree diff
        diff_result = subprocess.run(
            ["git", "diff", "HEAD"],
            cwd=self.workdir,
            capture_output=True,
            text=True,
            timeout=30,
        )
        diff_content = diff_result.stdout

        # Also get untracked files list
        status_result = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=self.workdir,
            capture_output=True,
            text=True,
            timeout=10,
        )
        untracked = status_result.stdout.strip()

        # Save metadata
        meta = {
            "type": "git",
            "head": head_hash,
            "has_diff": bool(diff_content.strip()),
            "untracked_files": untracked.split("\n") if untracked else [],
        }
        (cp_dir / "checkpoint.json").write_text(
            json.dumps(meta, indent=2), encoding="utf-8"
        )

        # Save diff
        if diff_content.strip():
            (cp_dir / "working_diff.patch").write_text(diff_content, encoding="utf-8")

    def _snapshot_tar(self, cp_dir: Path, paths: list[str] | None = None) -> None:
        """Create tar-based checkpoint of specified files."""
        if paths is None:
            paths = ["."]

        tar_path = cp_dir / "snapshot.tar.gz"
        with tarfile.open(tar_path, "w:gz") as tar:
            for path_str in paths:
                p = (self.workdir / path_str).resolve()
                if p.exists():
                    tar.add(p, arcname=p.relative_to(self.workdir))

        meta = {
            "type": "tar",
            "paths": paths,
        }
        (cp_dir / "checkpoint.json").write_text(
            json.dumps(meta, indent=2), encoding="utf-8"
        )

    def restore(self, checkpoint_id: str) -> bool:
        """Restore workdir to a checkpoint state.

        Args:
            checkpoint_id: Checkpoint ID to restore

        Returns:
            True if restored successfully
        """
        cp_dir = self.checkpoints_dir / checkpoint_id
        if not cp_dir.exists():
            return False

        meta_file = cp_dir / "checkpoint.json"
        if not meta_file.exists():
            return False

        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception:
            return False

        if meta["type"] == "git":
            return self._restore_git(cp_dir, meta)
        else:
            return self._restore_tar(cp_dir)

    def _restore_git(self, cp_dir: Path, meta: dict) -> bool:
        """Restore git working tree from diff."""
        diff_file = cp_dir / "working_diff.patch"
        if not diff_file.exists():
            return True  # Nothing to restore

        try:
            # Apply reverse diff to undo changes
            result = subprocess.run(
                ["git", "apply", "--reverse", str(diff_file)],
                cwd=self.workdir,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _restore_tar(self, cp_dir: Path) -> bool:
        """Restore from tar snapshot."""
        tar_path = cp_dir / "snapshot.tar.gz"
        if not tar_path.exists():
            return False

        try:
            with tarfile.open(tar_path, "r:gz") as tar:
                tar.extractall(path=self.workdir)
            return True
        except Exception:
            return False

    def list_checkpoints(self) -> list[dict[str, Any]]:
        """List all checkpoints, newest first."""
        return sorted(
            self._index,
            key=lambda x: x.get("timestamp", ""),
            reverse=True,
        )

    def get_last_checkpoint(self) -> dict[str, Any] | None:
        """Get the most recent checkpoint."""
        checkpoints = self.list_checkpoints()
        return checkpoints[0] if checkpoints else None

    def create_pre_tool_snapshot(self, tool_name: str, args: dict) -> str | None:
        """Auto-create snapshot before destructive file operations.

        Args:
            tool_name: Name of the tool being called
            args: Tool arguments

        Returns:
            Checkpoint ID or None if no snapshot needed
        """
        destructive_tools = {"write_file", "edit_file", "multi_edit", "bash"}

        if tool_name not in destructive_tools:
            return None

        paths = []
        if tool_name in ("write_file", "edit_file", "multi_edit"):
            p = args.get("path", "")
            if p:
                paths.append(p)

        tag = f"auto-before-{tool_name}"
        return self.snapshot(tag=tag, paths=paths or None)

    def prune(self, keep: int = 20) -> int:
        """Remove old checkpoints beyond keep count. Returns count removed."""
        removed = 0
        while len(self._index) > keep:
            old = self._index.pop(0)
            old_dir = self.checkpoints_dir / old["id"]
            if old_dir.exists():
                shutil.rmtree(old_dir, ignore_errors=True)
            removed += 1
        if removed > 0:
            self._save_index()
        return removed


# Global instance
_checkpoint_instance: CheckpointManager | None = None


def get_checkpoint_manager(
    workdir: Path | None = None,
    checkpoints_dir: Path | None = None,
) -> CheckpointManager:
    """Get or create the global checkpoint manager."""
    global _checkpoint_instance
    if _checkpoint_instance is None:
        _checkpoint_instance = CheckpointManager(
            workdir=workdir or Path.cwd(),
            checkpoints_dir=checkpoints_dir,
        )
    return _checkpoint_instance


def set_checkpoint_manager(instance: CheckpointManager) -> None:
    """Inject a custom CheckpointManager (for testing/DI)."""
    global _checkpoint_instance
    _checkpoint_instance = instance


def reset_checkpoint_manager() -> None:
    """Reset checkpoint singleton."""
    global _checkpoint_instance
    _checkpoint_instance = None
