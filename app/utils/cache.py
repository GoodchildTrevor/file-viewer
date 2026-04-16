import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict

from fastapi import HTTPException

from app.config import logger, CACHE_DIR, CACHE_METADATA_FILE, CACHE_EXPIRY_DAYS, DOCS_DIR


def load_cache_metadata() -> Dict[str, Dict]:
    """
    Load cache metadata from JSON file.
    
    :return: Dictionary containing cache metadata, empty dict if file doesn't exist or is corrupted
    :rtype: Dict[str, Dict]
    """
    if CACHE_METADATA_FILE.exists():
        try:
            with open(CACHE_METADATA_FILE, "r", encoding="utf-8") as f:
                logger.debug(f"Loaded cache metadata from {CACHE_METADATA_FILE}")
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse cache metadata: {e}")
            return {}
        except OSError as e:
            logger.error(f"Failed to read cache metadata file: {e}")
            return {}
    
    logger.debug("Cache metadata file not found, starting with empty cache")
    return {}


def save_cache_metadata(metadata: Dict[str, Dict]) -> None:
    """
    Save cache metadata to JSON file.
    
    :param metadata: Dictionary containing cache metadata to save
    :type metadata: Dict[str, Dict]
    :raises OSError: If failed to write to file
    """
    try:
        with open(CACHE_METADATA_FILE, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        logger.debug(f"Saved cache metadata to {CACHE_METADATA_FILE}")
    except OSError as e:
        logger.error(f"Failed to save cache metadata: {e}")
        raise


def get_cache_key(file_path: Path, modified_time: float) -> str:
    """
    Generate cache key based on file path and modification time.
    
    :param file_path: Path to the source file
    :type file_path: Path
    :param modified_time: File modification timestamp
    :type modified_time: float
    :return: MD5 hash string for cache key
    :rtype: str
    """
    unique = f"{file_path}_{modified_time}"
    return hashlib.md5(unique.encode()).hexdigest()


def get_cached_html(file_path: Path) -> Optional[Path]:
    """
    Check if valid cached HTML exists for the given file.
    
    :param file_path: Path to the source file
    :type file_path: Path
    :return: Path to cached HTML file if valid, None otherwise
    :rtype: Optional[Path]
    """
    if not file_path.exists():
        logger.debug(f"File does not exist: {file_path}")
        return None
    
    try:
        stat = file_path.stat()
        modified_time = stat.st_mtime
        file_size = stat.st_size
    except OSError as e:
        logger.error(f"Failed to get file stats for {file_path}: {e}")
        return None
    
    metadata = load_cache_metadata()
    file_key = str(file_path.relative_to(DOCS_DIR))
    
    if file_key in metadata:
        cache_info = metadata[file_key]
        if cache_info["modified"] == modified_time and cache_info["size"] == file_size:
            cache_path = CACHE_DIR / cache_info["cache_file"]
            if cache_path.exists():
                try:
                    cache_time = datetime.fromisoformat(cache_info["cached_at"])
                    age = datetime.now() - cache_time
                    if age < timedelta(days=CACHE_EXPIRY_DAYS):
                        logger.debug(f"Cache hit for {file_key}, age: {age}")
                        return cache_path
                    else:
                        logger.info(f"Cache expired for {file_key}, age: {age}")
                        cache_path.unlink(missing_ok=True)
                except ValueError as e:
                    logger.warning(f"Invalid timestamp in cache metadata for {file_key}: {e}")
                    cache_path.unlink(missing_ok=True)
    
    logger.debug(f"Cache miss for {file_path}")
    return None


def save_to_cache(file_path: Path, html_content: str) -> Path:
    """
    Save HTML content to cache and update metadata.
    
    :param file_path: Path to the source file
    :type file_path: Path
    :param html_content: HTML content to cache
    :type html_content: str
    :return: Path to the saved cache file
    :rtype: Path
    :raises HTTPException: If file operations fail
    """
    try:
        stat = file_path.stat()
        modified_time = stat.st_mtime
        file_size = stat.st_size
    except OSError as e:
        logger.error(f"Failed to get file stats for {file_path}: {e}")
        raise HTTPException(status_code=500, detail="Failed to read file metadata")
    
    cache_key = get_cache_key(file_path, modified_time)
    cache_file = CACHE_DIR / f"{cache_key}.html"
    
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            f.write(html_content)
        logger.debug(f"Saved cache file: {cache_file}")
    except OSError as e:
        logger.error(f"Failed to write cache file {cache_file}: {e}")
        raise HTTPException(status_code=500, detail="Failed to save cache")
    
    metadata = load_cache_metadata()
    file_key = str(file_path.relative_to(DOCS_DIR))
    metadata[file_key] = {
        "cache_file": cache_file.name,
        "modified": modified_time,
        "size": file_size,
        "cached_at": datetime.now().isoformat()
    }
    save_cache_metadata(metadata)
    
    return cache_file


def clean_old_cache() -> None:
    """
    Remove expired and orphaned cache files.
    
    Cleans up cache files that have exceeded their expiry period
    and removes any cache files without corresponding metadata entries.
    """
    logger.info("Starting cache cleanup")
    metadata = load_cache_metadata()
    metadata_updated = False
    cache_files = set()
    removed_count = 0
    
    for file_key, cache_info in list(metadata.items()):
        cache_path = CACHE_DIR / cache_info["cache_file"]
        cache_files.add(cache_path.name)
        
        try:
            cache_time = datetime.fromisoformat(cache_info["cached_at"])
            age = datetime.now() - cache_time
            if age > timedelta(days=CACHE_EXPIRY_DAYS):
                cache_path.unlink(missing_ok=True)
                del metadata[file_key]
                metadata_updated = True
                removed_count += 1
                logger.info(f"Removed expired cache: {cache_path.name}, age: {age}")
        except (ValueError, OSError) as e:
            logger.warning(f"Error processing cache entry {file_key}: {e}")
            if cache_path.exists():
                cache_path.unlink(missing_ok=True)
            del metadata[file_key]
            metadata_updated = True
    
    for cache_file in CACHE_DIR.glob("*.html"):
        if cache_file.name not in cache_files:
            cache_file.unlink(missing_ok=True)
            logger.debug(f"Removed orphaned cache file: {cache_file.name}")
            removed_count += 1
    
    if metadata_updated:
        save_cache_metadata(metadata)
    
    logger.info(f"Cache cleanup completed, removed {removed_count} files")
