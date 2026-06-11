"""Polling-based config file watcher for hot-reload support.

Simple polling approach with 2-second interval. No external dependencies.
Uses mtime comparison to detect changes. Compatible with any filesystem
that updates mtime on write.

Usage:
    watcher = ConfigWatcher(config_path, on_change=my_handler)
    watcher.start()  # background daemon thread
    ...
    watcher.stop()
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)


class ConfigWatcher:
    """Polls a config file for changes and invokes a callback on detection.

    Poll interval is intentionally set to 2.0 seconds — fast enough for
    interactive use but slow enough to avoid CPU waste. Uses mtime-based
    detection which is reliable across all major filesystems.
    """

    POLL_INTERVAL = 2.0

    def __init__(self, config_path: str | Path, on_change: Callable[[], None] | None = None):
        self.config_path = Path(config_path)
        self._last_mtime: float = 0.0
        self._on_change = on_change
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start polling in a background daemon thread.

        Does nothing if the config file does not exist or the watcher
        is already running.
        """
        if self._running:
            return
        if not self.config_path.exists():
            logger.warning("Config file not found, watcher not started: %s", self.config_path)
            return
        self._last_mtime = self.config_path.stat().st_mtime
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="config-watcher")
        self._thread.start()
        logger.info("Config watcher started for %s", self.config_path)

    def stop(self) -> None:
        """Stop the polling thread. Safe to call multiple times."""
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def _poll_loop(self) -> None:
        """Poll config file for mtime changes."""
        while self._running:
            try:
                if self.config_path.exists():
                    current_mtime = self.config_path.stat().st_mtime
                    if current_mtime > self._last_mtime:
                        self._last_mtime = current_mtime
                        logger.info("Config file change detected: %s", self.config_path)
                        if self._on_change:
                            try:
                                self._on_change()
                            except Exception:
                                logger.exception("ConfigWatcher callback failed")
            except Exception:
                logger.debug("Config watcher poll error", exc_info=True)
            time.sleep(self.POLL_INTERVAL)
