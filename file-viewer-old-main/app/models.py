from pathlib import Path
from typing import List

from fastapi import HTTPException
from pydantic import BaseModel, Field, field_validator, ConfigDict


class SupportedExtension:
    """
    Supported file extensions for the preview service.
    
    Provides constants and utility methods for working with supported file types.
    """
    DOCX: str = ".docx"
    PDF: str = ".pdf"
    XLSX: str = ".xlsx"
    XLS: str = ".xls"
    TXT: str = ".txt"
    MD: str = ".md"
    
    _ALL: tuple[str, ...] = (DOCX, PDF, XLSX, XLS, TXT, MD)
    
    @classmethod
    def all(cls) -> List[str]:
        """
        Return list of all supported extensions.
        
        :return: List of supported file extensions
        :rtype: List[str]
        """
        return list(cls._ALL)
    
    @classmethod
    def is_supported(cls, ext: str) -> bool:
        """
        Check if extension is supported.
        
        :param ext: File extension to check (e.g., ".docx")
        :type ext: str
        :return: True if extension is supported, False otherwise
        :rtype: bool
        """
        return ext.lower() in cls._ALL


class FilePathRequest(BaseModel):
    """
    Model for validating file path requests.
    
    Validates filename for security (path traversal prevention)
    and format constraints.
    """
    filename: str = Field(..., min_length=1, max_length=255, description="Filename to request")
    
    model_config = ConfigDict(str_strip_whitespace=True)
    
    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v: str) -> str:
        """
        Validate filename for security and format.
        
        :param v: Raw filename value
        :type v: str
        :return: Sanitized filename
        :rtype: str
        :raises ValueError: If filename contains invalid characters or patterns
        """
        if ".." in v or v.startswith("/") or v.startswith("\\"):
            raise ValueError("Filename contains invalid path characters")
        
        if any(char in v for char in ["<", ">", ":", '"', "|", "?", "*"]):
            raise ValueError("Filename contains invalid characters")
        
        return v.strip()
    
    def get_secure_path(self, base_dir: Path) -> Path:
        """
        Resolve and validate secure file path.
        
        :param base_dir: Base directory for file resolution
        :type base_dir: Path
        :return: Resolved and validated file path
        :rtype: Path
        :raises HTTPException: If path validation fails
        """
        full_path = (base_dir / self.filename).resolve()
        base_resolved = base_dir.resolve()
        
        if not str(full_path).startswith(str(base_resolved)):
            raise HTTPException(status_code=403, detail="Access denied: invalid path")
        
        return full_path


class PreviewRequest(FilePathRequest):
    """
    Model for preview endpoint with optional highlight parameter.
    
    Extends FilePathRequest with text highlighting support.
    """
    highlight: str = Field(default="", max_length=150, description="Text to highlight in preview")
    page: int = Field(default=1, description="Page number of a pdf file")
    
    @field_validator("highlight")
    @classmethod
    def sanitize_highlight(cls, v: str) -> str:
        """
        Sanitize highlight parameter to prevent XSS.
        
        :param v: Raw highlight value
        :type v: str
        :return: Sanitized highlight string
        :rtype: str
        """
        if not v:
            return v
        return v.strip()


class CacheStatsResponse(BaseModel):
    """Response model for cache statistics endpoint."""
    cached_files: int = Field(..., description="Number of files in cache metadata")
    cache_files_on_disk: int = Field(..., description="Number of cache files on disk")
    cache_dir: str = Field(..., description="Path to cache directory")
    total_size_mb: float = Field(..., description="Total cache size in megabytes")
    expiry_days: int = Field(..., description="Cache expiry period in days")
    
    model_config = ConfigDict(from_attributes=True)


class CacheCleanResponse(BaseModel):
    """Response model for cache cleaning endpoint."""
    status: str = Field(..., description="Status of cache cleaning operation")
    cache_dir: str = Field(..., description="Path to cache directory")
    
    model_config = ConfigDict(from_attributes=True)
