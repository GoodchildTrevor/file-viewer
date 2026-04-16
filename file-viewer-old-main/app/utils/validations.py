from pathlib import Path

from fastapi import HTTPException

from app.config import logger, DOCS_DIR
from app.models import FilePathRequest, SupportedExtension


def secure_filename_path(filename: str) -> Path:
    """
    Securely resolve file path, preventing path traversal attacks.
    
    :param filename: Requested filename
    :type filename: str
    :return: Resolved and validated file path
    :rtype: Path
    :raises HTTPException: If path validation fails
    """
    
    try:
        request = FilePathRequest(filename=filename)
        full_path = request.get_secure_path(DOCS_DIR)
        
        logger.info(f"Resolved path: {full_path}")  # ДОБАВЬТЕ
        logger.info(f"Path exists: {full_path.exists()}")  # ДОБАВЬТЕ
        
        if not full_path.exists():
            logger.warning(f"File not found: {full_path}")
            raise HTTPException(status_code=404, detail="File not found")
        
        ext = full_path.suffix.lower()
        if not SupportedExtension.is_supported(ext):
            logger.warning(f"Unsupported file extension: {ext}")
            raise HTTPException(
                status_code=415, 
                detail=f"Unsupported file format: {ext}. Supported: {', '.join(SupportedExtension.all())}"
            )
        
        logger.debug(f"Validated file path: {full_path}")
        return full_path
        
    except HTTPException:
        raise
    except (ValueError, RuntimeError) as e:
        logger.error(f"Path validation error for '{filename}': {e}")
        raise HTTPException(status_code=400, detail=f"Invalid path: {str(e)}")
    