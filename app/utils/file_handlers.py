import asyncio
import re
from pathlib import Path

from fastapi import HTTPException
import mammoth
import markdown as md_lib

from app.config import logger


def docx_to_html(file_path: Path, highlight: str = "") -> str:
    try:
        logger.debug(f"Converting DOCX to HTML: {file_path}")
        with open(file_path, "rb") as f:
            result = mammoth.convert_to_html(
                f,
                convert_image=mammoth.images.data_uri
            )
        
        if result.messages:
            for msg in result.messages:
                if msg.type == "warning":
                    logger.warning(f"mammoth warning for {file_path}: {msg.message}")
        
        html = result.value
        
        if highlight:
            html = highlight_text(html, highlight)
        
        return html
    except IOError as e:
        logger.error(f"Failed to read DOCX file {file_path}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")
    except Exception as e:
        logger.error(f"DOCX conversion error for {file_path}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"DOCX conversion error: {str(e)}")


async def docx_to_html_async(file_path: Path, highlight: str = "") -> str:
    """
    Asynchronously convert DOCX file to HTML.

    Since mammoth is synchronous, this runs the conversion in a thread pool.
    
    :param file_path: Path to the DOCX file
    :type file_path: Path
    :param highlight: Text to highlight in the output
    :type highlight: str
    :return: Converted HTML content
    :rtype: str
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, docx_to_html, file_path, highlight)


def highlight_text(html: str, highlight: str) -> str:
    """
    Highlight text occurrences in HTML content.
    
    :param html: HTML content to process
    :type html: str
    :param highlight: Text pattern to highlight
    :type highlight: str
    :return: HTML with highlighted text
    :rtype: str
    """
    if not highlight or len(highlight) > 150:
        return html
    
    try:
        escaped = re.escape(highlight[:150])
        parts = re.split(r'(<[^>]+>)', html)
        
        for i in range(len(parts)):
            if not parts[i].startswith('<'):
                parts[i] = re.sub(
                    f'({escaped})',
                    r'<mark style="background:#ffd700;color:#000;border-radius:3px;padding:0 2px;">\1</mark>',
                    parts[i],
                    flags=re.IGNORECASE
                )
        
        return ''.join(parts)
        
    except re.error as e:
        logger.warning(f"Regex error during highlighting: {e}")
        return html


def text_file_to_html(file_path: Path, highlight: str = "") -> str:
    """
    Convert text or markdown file to HTML with optional highlighting.

    Both .txt and .md files are rendered as Markdown
    (with tables, fenced code blocks, TOC, etc.).
    
    :param file_path: Path to the text file
    :type file_path: Path
    :param highlight: Text to highlight
    :type highlight: str
    :return: HTML-formatted content
    :rtype: str
    :raises HTTPException: If file reading fails
    """
    try:
        logger.debug(f"Reading text file: {file_path}")
        text = file_path.read_text(encoding="utf-8", errors="replace")

        body = md_lib.markdown(
            text,
            extensions=["extra", "codehilite", "toc"],
        )
        if highlight:
            body = highlight_text(body, highlight)
        return f'<div class="markdown-body">{body}</div>'

    except UnicodeDecodeError as e:
        logger.error(f"Encoding error reading {file_path}: {e}")
        raise HTTPException(status_code=500, detail="Failed to decode file content")
    except IOError as e:
        logger.error(f"Failed to read text file {file_path}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")
