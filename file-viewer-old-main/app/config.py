import os
import logging
from pathlib import Path


def setup_logger(name: str = "file_preview_service", level: int = logging.INFO) -> logging.Logger:
    """
    Configure and return application logger.
    
    :param name: Logger name
    :type name: str
    :param level: Logging level (default: INFO)
    :type level: int
    :return: Configured logger instance
    :rtype: logging.Logger
    """
    logger_obj = logging.getLogger(name)
    logger_obj.setLevel(level)
    
    if not logger_obj.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger_obj.addHandler(handler)
    
    return logger_obj

logger: logging.Logger = setup_logger()

DOCS_DIR: Path = Path(os.getenv("DOCS_DIR", "/app/documents"))
"""Directory for storing source documents."""

CACHE_DIR: Path = Path(os.getenv("CACHE_DIR", "/app/cache"))
"""Directory for storing cached HTML files."""

CACHE_METADATA_FILE: Path = CACHE_DIR / "metadata.json"
"""Path to cache metadata JSON file."""

CACHE_EXPIRY_DAYS: int = int(os.getenv("CACHE_EXPIRY_DAYS", "30"))
"""Number of days before cached files expire."""

SUPPORTED_EXTENSIONS: tuple[str, ...] = (".docx", ".pdf", ".xlsx", ".xls", ".txt", ".md")
"""Tuple of supported file extensions for preview."""

URL_PREFIX: str = "/file-preview"


def ensure_directories() -> None:
    """
    Create required directories if they don't exist.
    
    :raises OSError: If directory creation fails
    """
    for directory in (DOCS_DIR, CACHE_DIR):
        directory.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Directory ready: {directory}")
