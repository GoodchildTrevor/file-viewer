import asyncio
import html
import pathlib
import urllib.parse
from contextlib import asynccontextmanager

import aiofiles
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, Path, Request
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.routing import APIRouter
from starlette.routing import Route, WebSocketRoute, Mount

from app.config import (
    logger, 
    DOCS_DIR, 
    CACHE_DIR, 
    CACHE_EXPIRY_DAYS, 
    URL_PREFIX,
    ensure_directories
)
from app.models import SupportedExtension, PreviewRequest, CacheCleanResponse, CacheStatsResponse
from app.utils.cache import (
    load_cache_metadata,
    save_to_cache,
    get_cached_html,
    clean_old_cache,
)
from app.utils.file_handlers import (
    docx_to_html_async,
    text_file_to_html,
    highlight_text,
)
from app.utils.validations import secure_filename_path
from app.utils.rendering import pdf_viewer, excel_viewer, wrap_page


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Application startup initiated")
    ensure_directories()
    
    asyncio.create_task(asyncio.to_thread(clean_old_cache))

    routes_info = []
    for route in app.routes:
        if isinstance(route, (Route, WebSocketRoute)):
            routes_info.append(f"{getattr(route, 'methods', {'WS'})} {route.path}")
        elif isinstance(route, Mount):
            routes_info.append(f"Mount: {route.path}")
        else:
            routes_info.append(f"{type(route).__name__}")
    logger.info("Registered routes: %s", routes_info)
    
    try:
        files = list(DOCS_DIR.glob("*"))
        logger.info(f"Found {len(files)} files in {DOCS_DIR}")
    except OSError as e:
        logger.error(f"Error scanning documents directory: {e}")
    
    yield
    
    logger.info("Application shutdown initiated")


app = FastAPI(title="File Preview Service", lifespan=lifespan)
router = APIRouter(prefix=URL_PREFIX if URL_PREFIX else "")


@router.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main page with list of available files."""
    logger.info("Serving root page")
    files = []
    for ext in SupportedExtension.all():
        try:
            files.extend(DOCS_DIR.glob(ext))
        except OSError as e:
            logger.warning(f"Error scanning for {ext}: {e}")
    
    files_html = ""
    for file in sorted(files, key=lambda x: x.name.lower()):
        ext = file.suffix.lower()
        icon = {
            ".docx": "📝", ".pdf": "📕", ".xlsx": "📊", 
            ".xls": "📊", ".txt": "📄", ".md": "📋"
        }.get(ext, "📁")
        safe_name = html.escape(file.name)
        files_html += (
            f'<li><a href="/preview/{safe_name}" style="color:#a78bfa;">'
            f'{icon} {safe_name}</a> '
            f'<span style="color:#6b7280;font-size:12px;">({ext})</span></li>'
        )
    
    logger.debug(f"Found {len(files)} files for listing")
    
    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>File Preview Service</title>
        <style>
            body {{ font-family: 'Segoe UI', sans-serif; background: #1a1a2e; color: #e0e0e0; padding: 40px; }}
            .container {{ max-width: 800px; margin: 0 auto; background: #13131f; padding: 30px; border-radius: 10px; }}
            h1 {{ color: #a78bfa; margin-bottom: 20px; }}
            ul {{ list-style: none; padding: 0; }}
            li {{ padding: 10px; border-bottom: 1px solid #1e1e32; }}
            li:hover {{ background: #1e1e32; }}
            a {{ text-decoration: none; color: #e0e0e0; }}
            .stats {{ color: #6b7280; font-size: 14px; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📁 Available Files</h1>
            <ul>
                {files_html if files_html else "<li style='color:#6b7280;'>No files available for preview</li>"}
            </ul>
            <div class="stats">
                Total files: {len(files)} | 
                Directory: {DOCS_DIR} | 
                Cache: {CACHE_DIR}
            </div>
        </div>
    </body>
    </html>
    """)


@router.get("/files/{filename:path}")
async def get_file(filename: str = Path(..., min_length=1, max_length=500)):
    """Serve file for download."""
    logger.info(f"File download requested: {filename}")
    
    decoded = urllib.parse.unquote(filename)
    logger.info(f"Decoded filename: {decoded}")
    
    file_path = secure_filename_path(decoded)
    logger.info(f"Full file path: {file_path}")
    logger.info(f"File exists: {file_path.exists()}")
    
    return FileResponse(
        path=file_path,
        filename=pathlib.Path(decoded).name,
        media_type="application/octet-stream"
    )


@router.get("/preview/{path:path}", response_class=HTMLResponse)
async def preview(
    path: str = Path(..., min_length=1, max_length=500),
    highlight: str = Query(default="", max_length=150),
    page: int = Query(default=1, ge=1)
):
    """Generate file preview with optional text highlighting."""
    logger.info(f"Preview requested: {path}, highlight: {bool(highlight)}")
    
    filename = path.split('/')[-1] if '/' in path else path
    
    try:
        request = PreviewRequest(filename=filename, highlight=highlight, page=page)
    except ValueError as e:
        logger.warning(f"Invalid preview request parameters: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid request: {str(e)}")
    
    file_path = secure_filename_path(path)
    ext = file_path.suffix.lower()
    
    try:
        if ext == SupportedExtension.DOCX:
            cached_path = get_cached_html(file_path)
            
            if cached_path:
                logger.debug(f"Cache hit for {request.filename}")
                async with aiofiles.open(cached_path, "r", encoding="utf-8") as f:
                    base_html = await f.read()
            else:
                logger.debug(f"Cache miss for {request.filename}, converting...")
                base_html = await docx_to_html_async(file_path, "")
                save_to_cache(file_path, base_html)
            
            body_html = highlight_text(base_html, request.highlight) if request.highlight else base_html
        
        elif ext == SupportedExtension.PDF:
            logger.debug(f"Serving PDF preview: {path}")
            body_html = pdf_viewer(path, request.highlight, request.page)
        elif ext in (SupportedExtension.XLSX, SupportedExtension.XLS):
            logger.debug(f"Serving Excel preview: {path}")
            body_html = excel_viewer(path)
        elif ext in (SupportedExtension.TXT, SupportedExtension.MD):
            logger.debug(f"Serving text preview: {request.filename}")
            body_html = text_file_to_html(file_path, request.highlight)
        
        else:
            logger.error(f"Unsupported extension: {ext}")
            raise HTTPException(status_code=415, detail=f"Format {ext} is not supported")
        
        return HTMLResponse(wrap_page(request.filename, body_html))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error processing {request.filename}",
            extra={"filename": request.filename, "highlight": request.highlight},
            exc_info=True
        )
        raise HTTPException(status_code=500, detail="Internal processing error")


@router.post("/cache/clean", response_model=CacheCleanResponse)
async def clean_cache(background_tasks: BackgroundTasks):
    """Trigger cleanup of expired cache files."""
    logger.info("Cache cleanup triggered via API")
    background_tasks.add_task(clean_old_cache)
    return CacheCleanResponse(
        status="cleaning_started",
        cache_dir=str(CACHE_DIR)
    )


@router.get("/cache/stats", response_model=CacheStatsResponse)
async def cache_stats():
    """Return cache statistics."""
    logger.debug("Cache stats requested")
    metadata = load_cache_metadata()
    cache_files = list(CACHE_DIR.glob("*.html"))
    
    try:
        total_size = sum(f.stat().st_size for f in cache_files)
    except OSError as e:
        logger.warning(f"Error calculating cache size: {e}")
        total_size = 0
    
    return CacheStatsResponse(
        cached_files=len(metadata),
        cache_files_on_disk=len(cache_files),
        cache_dir=str(CACHE_DIR),
        total_size_mb=round(total_size / (1024 * 1024), 2),
        expiry_days=CACHE_EXPIRY_DAYS
    )


@router.get("/raw-preview/{path:path}", response_class=RedirectResponse)
async def raw_preview(
    request: Request,
    path: str = Path(..., min_length=1, max_length=500),
    highlight: str = Query(default="", max_length=150),
    page: int = Query(default=1, ge=1),
):
    logger.info(f"Raw preview requested: {path}, highlight: {bool(highlight)}, page: {page}")

    encoded_path = urllib.parse.quote(path, safe='')
    encoded_path = encoded_path.replace('/', '%2F')

    redirect_url = str(request.url_for("preview", path=encoded_path))

    params = []
    if highlight:
        params.append(f"highlight={urllib.parse.quote(highlight)}")
    if page != 1:
        params.append(f"page={page}")

    if params:
        redirect_url += "?" + "&".join(params)

    logger.debug(f"Redirecting to: {redirect_url}")
    return RedirectResponse(url=redirect_url, status_code=307)


@router.get("/raw-file/{path:path}", response_class=RedirectResponse)
async def raw_file(
    request: Request,
    path: str = Path(..., min_length=1, max_length=500)
):
    logger.info(f"Raw file download requested: {path}")

    encoded_path = urllib.parse.quote(path, safe='')
    redirect_url = str(request.url_for("get_file", filename=encoded_path))
    
    logger.debug(f"Redirecting to: {redirect_url}")
    return RedirectResponse(url=redirect_url, status_code=307)


@router.get("/preview-info/{path:path}")
async def preview_info(
    path: str = Path(..., min_length=1, max_length=500)
):
    logger.info(f"Preview info requested for: {path}")
    
    try:
        decoded_path = urllib.parse.unquote(path)
        is_encoded = decoded_path != path
    except Exception:
        decoded_path = path
        is_encoded = False
    
    encoded_path = urllib.parse.quote(path, safe='')
    
    file_exists = False
    existing_path = None
    
    test_path = secure_filename_path(path)
    if test_path.exists():
        file_exists = True
        existing_path = str(test_path)
    else:
        test_decoded = secure_filename_path(decoded_path)
        if test_decoded.exists():
            file_exists = True
            existing_path = str(test_decoded)
    
    return {
        "original_path": path,
        "decoded_path": decoded_path,
        "encoded_path": encoded_path,
        "is_encoded": is_encoded,
        "preview_url": f"/preview/{encoded_path}",
        "download_url": f"/files/{encoded_path}",
        "file_exists": file_exists,
        "existing_path": existing_path,
        "document_root": str(DOCS_DIR)
    }

app.include_router(router)
