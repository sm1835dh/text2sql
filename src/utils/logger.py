"""
Custom logger module with color support, rotation, and structured logging.
"""

import logging
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Union
from functools import wraps
import time
import traceback
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler

import colorlog


class SingletonMeta(type):
    """Metaclass for implementing singleton pattern."""
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class CustomLogger(metaclass=SingletonMeta):
    """
    Custom logger with color support, file rotation, and structured logging.
    Implements singleton pattern to ensure single logger instance.
    """

    def __init__(
        self,
        name: str = "text2sql",
        log_level: str = "INFO",
        log_dir: Optional[Path] = None,
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
        use_json: bool = False,
    ):
        """
        Initialize the custom logger.

        Args:
            name: Logger name
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_dir: Directory for log files (creates logs/ if None)
            max_bytes: Max size for log rotation
            backup_count: Number of backup files to keep
            use_json: Whether to use JSON format for file logs
        """
        self.name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, log_level.upper()))
        self.logger.handlers = []  # Clear existing handlers

        self.use_json = use_json
        self.context: Dict[str, Any] = {}

        # Setup log directory
        if log_dir is None:
            log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        # Setup console handler with color
        self._setup_console_handler()

        # Setup file handlers
        self._setup_file_handlers(log_dir, max_bytes, backup_count)

    def _setup_console_handler(self):
        """Setup colored console handler."""
        console_handler = logging.StreamHandler(sys.stdout)

        # Color scheme for different log levels
        log_colors = {
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'bold_red',
        }

        # Colored formatter for console
        console_format = colorlog.ColoredFormatter(
            "%(log_color)s%(asctime)s [%(levelname)-8s] %(name)s - %(message)s",
            datefmt='%Y-%m-%d %H:%M:%S',
            log_colors=log_colors
        )

        console_handler.setFormatter(console_format)
        self.logger.addHandler(console_handler)

    def _setup_file_handlers(self, log_dir: Path, max_bytes: int, backup_count: int):
        """Setup rotating file handlers."""
        # Size-based rotation
        size_handler = RotatingFileHandler(
            log_dir / f"{self.name}.log",
            maxBytes=max_bytes,
            backupCount=backup_count
        )

        # Time-based rotation (daily)
        time_handler = TimedRotatingFileHandler(
            log_dir / f"{self.name}_daily.log",
            when='midnight',
            interval=1,
            backupCount=30  # Keep 30 days
        )

        # Formatter for file handlers
        if self.use_json:
            formatter = JsonFormatter()
        else:
            formatter = logging.Formatter(
                '%(asctime)s [%(levelname)-8s] %(name)s - %(funcName)s:%(lineno)d - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )

        size_handler.setFormatter(formatter)
        time_handler.setFormatter(formatter)

        self.logger.addHandler(size_handler)
        self.logger.addHandler(time_handler)

    def set_context(self, **kwargs):
        """Set context variables for structured logging."""
        self.context.update(kwargs)

    def clear_context(self):
        """Clear context variables."""
        self.context.clear()

    def _add_context(self, msg: str) -> str:
        """Add context to message if available."""
        if self.context:
            context_str = ' '.join(f'{k}={v}' for k, v in self.context.items())
            return f"{msg} | Context: {context_str}"
        return msg

    def debug(self, msg: str, **kwargs):
        """Log debug message."""
        self.logger.debug(self._add_context(msg), extra=kwargs)

    def info(self, msg: str, **kwargs):
        """Log info message."""
        self.logger.info(self._add_context(msg), extra=kwargs)

    def warning(self, msg: str, **kwargs):
        """Log warning message."""
        self.logger.warning(self._add_context(msg), extra=kwargs)

    def error(self, msg: str, exc_info: bool = False, **kwargs):
        """Log error message."""
        if exc_info:
            kwargs['exc_info'] = True
        self.logger.error(self._add_context(msg), **kwargs)

    def critical(self, msg: str, **kwargs):
        """Log critical message."""
        self.logger.critical(self._add_context(msg), **kwargs)


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'message': record.getMessage(),
        }

        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'created', 'filename',
                          'funcName', 'levelname', 'levelno', 'lineno',
                          'module', 'msecs', 'message', 'pathname', 'process',
                          'processName', 'relativeCreated', 'thread', 'threadName']:
                log_data[key] = value

        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def log_execution(
    log_params: bool = True,
    log_result: bool = False,
    log_time: bool = True,
    log_errors: bool = True
):
    """
    Decorator for logging function execution.

    Args:
        log_params: Whether to log input parameters
        log_result: Whether to log return value
        log_time: Whether to log execution time
        log_errors: Whether to log errors

    Returns:
        Decorated function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_logger()
            func_name = func.__name__

            # Log function entry
            entry_msg = f"Entering {func_name}"
            if log_params:
                # Avoid logging sensitive data
                safe_kwargs = {k: '***' if 'password' in k.lower() or 'key' in k.lower()
                              else v for k, v in kwargs.items()}
                entry_msg += f" | Args: {args[:3] if len(args) > 3 else args} | Kwargs: {safe_kwargs}"
            logger.debug(entry_msg)

            start_time = time.time()
            error_occurred = False
            result = None

            try:
                result = func(*args, **kwargs)
                return result

            except Exception as e:
                error_occurred = True
                if log_errors:
                    logger.error(
                        f"Error in {func_name}: {str(e)}",
                        exc_info=True
                    )
                raise

            finally:
                # Calculate execution time
                execution_time = time.time() - start_time

                # Log function exit
                exit_msg = f"Exiting {func_name}"
                if log_time:
                    exit_msg += f" | Execution time: {execution_time:.3f}s"
                if log_result and not error_occurred:
                    # Truncate large results
                    result_str = str(result)[:200] if result else None
                    exit_msg += f" | Result: {result_str}"
                if error_occurred:
                    exit_msg += " | Status: ERROR"
                else:
                    exit_msg += " | Status: SUCCESS"

                logger.debug(exit_msg)

        return wrapper
    return decorator


# Global logger instance
_logger: Optional[CustomLogger] = None


def get_logger(
    name: Optional[str] = None,
    log_level: Optional[str] = None,
    **kwargs
) -> CustomLogger:
    """
    Get or create logger instance.

    Args:
        name: Logger name
        log_level: Logging level
        **kwargs: Additional arguments for CustomLogger

    Returns:
        CustomLogger instance
    """
    global _logger

    if _logger is None:
        import os
        from dotenv import load_dotenv
        load_dotenv()

        _logger = CustomLogger(
            name=name or "text2sql",
            log_level=log_level or os.getenv("LOG_LEVEL", "INFO"),
            use_json=os.getenv("LOG_FORMAT", "text").lower() == "json",
            **kwargs
        )

    return _logger


def set_log_level(level: str):
    """Set global log level."""
    logger = get_logger()
    logger.logger.setLevel(getattr(logging, level.upper()))
    for handler in logger.logger.handlers:
        handler.setLevel(getattr(logging, level.upper()))