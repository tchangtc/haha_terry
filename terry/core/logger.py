"""Structured logging system with rotation and multiple outputs."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


class JSONFormatter(logging.Formatter):
    """Format log records as JSON."""

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as JSON.

        Args:
            record: Log record

        Returns:
            JSON string
        """
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        if hasattr(record, "extra_data"):
            log_data["data"] = record.extra_data

        return json.dumps(log_data, ensure_ascii=False)


class ColoredFormatter(logging.Formatter):
    """Format log records with colors for terminal output."""

    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record with colors.

        Args:
            record: Log record

        Returns:
            Formatted string with colors
        """
        color = self.COLORS.get(record.levelname, self.RESET)
        timestamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")

        message = f"{color}{timestamp} [{record.levelname:8s}] {record.name}: {record.getMessage()}{self.RESET}"

        if record.exc_info:
            message += "\n" + self.formatException(record.exc_info)

        return message


class Logger:
    """Structured logger with multiple outputs."""

    def __init__(
        self,
        name: str = "terry",
        log_dir: Path | None = None,
        level: int = logging.INFO,
        console: bool = True,
        file: bool = True,
        json_format: bool = False,
    ):
        """Initialize logger.

        Args:
            name: Logger name
            log_dir: Directory for log files
            level: Logging level
            console: Enable console output
            file: Enable file output
            json_format: Use JSON format for console output
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        self.logger.handlers = []  # Clear existing handlers

        # Console handler
        if console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(level)

            if json_format:
                console_handler.setFormatter(JSONFormatter())
            else:
                console_handler.setFormatter(ColoredFormatter())

            self.logger.addHandler(console_handler)

        # File handler
        if file and log_dir:
            log_dir.mkdir(parents=True, exist_ok=True)

            # Rotating file handler (10MB max, 5 backups)
            file_handler = RotatingFileHandler(
                log_dir / f"{name}.log",
                maxBytes=10 * 1024 * 1024,
                backupCount=5,
                encoding="utf-8",
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(JSONFormatter())

            self.logger.addHandler(file_handler)

            # Error log (separate file for errors)
            error_handler = RotatingFileHandler(
                log_dir / f"{name}.error.log",
                maxBytes=10 * 1024 * 1024,
                backupCount=5,
                encoding="utf-8",
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(JSONFormatter())

            self.logger.addHandler(error_handler)

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message.

        Args:
            message: Log message
            **kwargs: Extra data to include
        """
        self._log(logging.DEBUG, message, kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message.

        Args:
            message: Log message
            **kwargs: Extra data to include
        """
        self._log(logging.INFO, message, kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message.

        Args:
            message: Log message
            **kwargs: Extra data to include
        """
        self._log(logging.WARNING, message, kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        """Log error message.

        Args:
            message: Log message
            **kwargs: Extra data to include
        """
        self._log(logging.ERROR, message, kwargs)

    def critical(self, message: str, **kwargs: Any) -> None:
        """Log critical message.

        Args:
            message: Log message
            **kwargs: Extra data to include
        """
        self._log(logging.CRITICAL, message, kwargs)

    def _log(self, level: int, message: str, extra: dict[str, Any]) -> None:
        """Internal logging method.

        Args:
            level: Log level
            message: Log message
            extra: Extra data
        """
        if extra:
            record = self.logger.makeRecord(
                self.logger.name,
                level,
                "(unknown)",
                0,
                message,
                (),
                None,
            )
            record.extra_data = extra
            self.logger.handle(record)
        else:
            self.logger.log(level, message)


# Global logger instance
_logger_instance: Logger | None = None


def get_logger(
    name: str = "terry",
    log_dir: Path | None = None,
    level: int = logging.INFO,
    console: bool = True,
    file: bool = True,
) -> Logger:
    """Get or create the global logger instance.

    Args:
        name: Logger name
        log_dir: Log directory
        level: Logging level
        console: Enable console output
        file: Enable file output

    Returns:
        Logger instance
    """
    global _logger_instance
    if _logger_instance is None:
        if log_dir is None:
            log_dir = Path.home() / ".terry" / "logs"
        _logger_instance = Logger(
            name=name,
            log_dir=log_dir,
            level=level,
            console=console,
            file=file,
        )
    return _logger_instance


def set_logger(instance: Logger) -> None:
    """Inject a custom Logger instance (for testing/DI)."""
    global _logger_instance
    _logger_instance = instance


def reset_logger() -> None:
    """Reset logger singleton (forces re-initialization on next get)."""
    global _logger_instance
    _logger_instance = None
