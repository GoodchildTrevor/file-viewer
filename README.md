# file-viewer

Lightweight **document preview backend** built with **FastAPI** that renders DOCX, PDF, XLSX, TXT, and MD files directly in the browser. Features caching, text highlighting, and secure file access — ideal for internal knowledge bases or document management systems.

## Features

- Multi-format preview: DOCX, PDF, XLS/XLSX, TXT, Markdown
- Smart caching with TTL and automatic invalidation on file change
- Text highlighting with case-insensitive search
- Path traversal protection and extension whitelisting
- Clean dark-mode UI with responsive design
- Structured logging with configurable levels
- Modular architecture with explicit imports

## Getting Started

```bash
git clone https://github.com/GoodchildTrevor/file-viewer.git
cd file-viewer
cp .env.example .env
# Edit .env as needed
docker compose up -d --build
```

The service runs on port **8070** by default.

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `DOCS_DIR` | `/app/documents` | Path to source documents (mount your files here) |
| `CACHE_DIR` | `/app/cache` | Path for HTML cache |
| `CACHE_EXPIRY_DAYS` | `30` | Days before cached files expire |
| `LOG_LEVEL` | `INFO` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `APP_PORT` | `8070` | Host port (docker-compose only) |

## API Reference

### Preview a file

```http
GET /file-preview/preview/{filename}?highlight=search_term
```

Returns HTML preview with optional text highlighting.

### Download original file

```http
GET /file-preview/files/{filename}
```

Returns the raw file for download.

### Cache management

```http
GET  /file-preview/cache/stats    # View cache statistics
POST /file-preview/cache/clean    # Trigger cleanup of expired entries
```

### Health check

```http
GET /health
```

Returns `{"status": "ok"}`.

## System dependencies

Required only for local development (not needed in Docker):

```bash
# Ubuntu/Debian
apt install libmagic1
```

## Project Structure

```
file-viewer/
├── app/
│   ├── main.py       # FastAPI app and route handlers
│   ├── config.py     # Settings and directory setup
│   ├── models.py     # Pydantic models
│   └── utils/        # Format-specific rendering logic
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## License

[GPL-2.0](LICENSE)
