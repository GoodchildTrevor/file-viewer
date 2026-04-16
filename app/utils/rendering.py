import html
import urllib.parse
from pathlib import Path

from app.config import logger, URL_PREFIX

# Build base path for client-side file fetches, respecting the app mount prefix
_FILES_BASE = f"{URL_PREFIX}/files" if URL_PREFIX else "/files"


def pdf_viewer(filepath: str, highlight: str = "", page: int | None = None) -> str:
    """
    Generate HTML for PDF file preview.

    :param filepath: Relative path to the PDF file (may include subdirectories)
    :type filepath: str
    :param highlight: Text to highlight (used for in-viewer search)
    :type highlight: str
    :param page: Initial page to open (1-based)
    :type page: int | None
    :return: HTML string with PDF viewer
    :rtype: str
    """
    logger.debug(f"Generating PDF viewer for {filepath} (page={page}, highlight={bool(highlight)})")

    safe_filepath = "/".join(urllib.parse.quote(p, safe="") for p in filepath.split("/"))
    filename = html.escape(Path(filepath).name)

    # initial page for JS (fallback to 1)
    initial_page = page or 1

    # optional JS for search inside the viewer
    highlight_js = ""
    if highlight:
        safe = (
            html.escape(highlight[:150])
            .replace("'", "\\\\'")
            .replace("\\n", " ")
        )
        highlight_js = f"""
        setTimeout(() => {{
            if (window.PDFViewerApplication && window.PDFViewerApplication.findBar) {{
                window.PDFViewerApplication.findBar.findField.value = '{safe}';
                window.PDFViewerApplication.findBar.highlightAll.checked = true;
                window.PDFViewerApplication.findBar.findNextButton.click();
            }}
        }}, 1500);
        """

    return f"""
    <style>
        .pdf-shell {{
            display: flex;
            flex-direction: column;
            gap: 0;
            height: 82vh;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 0 0 1px #232336, 0 8px 40px #0008;
        }}
        .pdf-toolbar {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 10px 20px;
            background: #18182a;
            border-bottom: 1px solid #232336;
            gap: 16px;
            flex-shrink: 0;
        }}
        .pdf-toolbar-left {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .pdf-icon {{
            width: 28px;
            height: 28px;
            background: linear-gradient(135deg, #ef4444 60%, #b91c1c);
            border-radius: 6px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            font-weight: 700;
            color: #fff;
            letter-spacing: 0.02em;
            flex-shrink: 0;
        }}
        .pdf-fname {{
            font-size: 13px;
            font-weight: 500;
            color: #c8c8e0;
            max-width: 340px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .pdf-nav {{
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .pdf-nav button {{
            background: #232336;
            border: 1px solid #2e2e4a;
            color: #a78bfa;
            cursor: pointer;
            font-size: 15px;
            border-radius: 7px;
            width: 32px;
            height: 32px;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: background 0.15s, color 0.15s;
        }}
        .pdf-nav button:hover {{ background: #2e2e4a; color: #c4b5fd; }}
        .pdf-nav button:disabled {{ opacity: 0.35; cursor: default; }}
        .pdf-page-info {{
            font-size: 13px;
            color: #888;
            min-width: 80px;
            text-align: center;
            font-variant-numeric: tabular-nums;
        }}
        .pdf-zoom {{
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .pdf-zoom button {{
            background: #232336;
            border: 1px solid #2e2e4a;
            color: #a78bfa;
            cursor: pointer;
            font-size: 16px;
            border-radius: 7px;
            width: 32px;
            height: 32px;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: background 0.15s;
        }}
        .pdf-zoom button:hover {{ background: #2e2e4a; }}
        .pdf-zoom-label {{
            font-size: 12px;
            color: #666;
            min-width: 42px;
            text-align: center;
        }}
        .pdf-canvas-wrap {{
            flex: 1;
            overflow: auto;
            background: #111120;
            display: flex;
            align-items: flex-start;
            justify-content: center;
            padding: 24px 16px;
        }}
        .pdf-loading {{
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100%;
            gap: 14px;
            color: #555;
            font-size: 14px;
        }}
        .pdf-spinner {{
            width: 36px;
            height: 36px;
            border: 3px solid #232336;
            border-top-color: #a78bfa;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }}
        @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
        #pdf-canvas {{
            display: block;
            border-radius: 6px;
            box-shadow: 0 4px 32px #0009;
        }}
    </style>

    <div class="pdf-shell">
        <div class="pdf-toolbar">
            <div class="pdf-toolbar-left">
                <div class="pdf-icon">PDF</div>
                <span class="pdf-fname">{filename}</span>
            </div>
            <div class="pdf-nav">
                <button id="pdf-prev" onclick="pdfChangePage(-1)" title="Предыдущая страница">‹</button>
                <span class="pdf-page-info" id="page-info">— / —</span>
                <button id="pdf-next" onclick="pdfChangePage(1)" title="Следующая страница">›</button>
            </div>
            <div class="pdf-zoom">
                <button onclick="pdfZoom(-0.25)" title="Уменьшить">−</button>
                <span class="pdf-zoom-label" id="zoom-label">150%</span>
                <button onclick="pdfZoom(0.25)" title="Увеличить">+</button>
            </div>
        </div>
        <div class="pdf-canvas-wrap" id="pdf-canvas-wrap">
            <div class="pdf-loading" id="pdf-loading">
                <div class="pdf-spinner"></div>
                <span>Загрузка PDF…</span>
            </div>
            <canvas id="pdf-canvas" style="display:none;"></canvas>
        </div>
    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js"></script>
    <script>
        pdfjsLib.GlobalWorkerOptions.workerSrc =
            'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

        const pdfUrl = '{_FILES_BASE}/{safe_filepath}';
        const initialPage = {initial_page};

        let pdfDoc = null;
        let currentPage = initialPage;
        let totalPages = 1;
        let scale = 1.5;

        function updatePageInfo() {{
            const info = document.getElementById('page-info');
            info.textContent = currentPage + ' / ' + totalPages;
            document.getElementById('pdf-prev').disabled = currentPage <= 1;
            document.getElementById('pdf-next').disabled = currentPage >= totalPages;
        }}

        function renderPage(num) {{
            if (!pdfDoc) return;
            pdfDoc.getPage(num).then(page => {{
                const viewport = page.getViewport({{ scale }});
                const canvas = document.getElementById('pdf-canvas');
                const ctx = canvas.getContext('2d');
                canvas.height = viewport.height;
                canvas.width = viewport.width;
                page.render({{ canvasContext: ctx, viewport }});
            }});
        }}

        function pdfChangePage(delta) {{
            if (!pdfDoc) return;
            const next = currentPage + delta;
            if (next >= 1 && next <= totalPages) {{
                currentPage = next;
                updatePageInfo();
                renderPage(currentPage);
            }}
        }}

        function pdfZoom(delta) {{
            scale = Math.min(4, Math.max(0.5, scale + delta));
            document.getElementById('zoom-label').textContent =
                Math.round(scale * 100) + '%';
            renderPage(currentPage);
        }}

        document.addEventListener('keydown', e => {{
            if (e.key === 'ArrowLeft') pdfChangePage(-1);
            else if (e.key === 'ArrowRight') pdfChangePage(1);
        }});

        pdfjsLib.getDocument(pdfUrl).promise.then(pdf => {{
            pdfDoc = pdf;
            totalPages = pdf.numPages;

            // Normalize initialPage into [1, totalPages]
            if (currentPage < 1 || currentPage > totalPages) {{
                currentPage = 1;
            }}

            document.getElementById('pdf-loading').style.display = 'none';
            document.getElementById('pdf-canvas').style.display = 'block';
            updatePageInfo();
            renderPage(currentPage);
        }}).catch(err => {{
            const loading = document.getElementById('pdf-loading');
            if (loading) {{
                loading.innerHTML =
                    '<span style="color:#ef4444;">Не удалось загрузить PDF: ' +
                    err.message + '</span>';
            }}
            console.error('PDF loading error:', err);
        }});

        {highlight_js}
    </script>
    """


def excel_viewer(filepath: str) -> str:
    """
    Generate HTML for Excel file preview.

    :param filepath: Relative path to the Excel file (may include subdirectories)
    :type filepath: str
    :return: HTML string with Excel viewer
    :rtype: str
    """
    logger.debug(f"Generating Excel viewer for {filepath}")
    safe_filepath = '/'.join(urllib.parse.quote(p, safe='') for p in filepath.split('/'))
    filename = html.escape(Path(filepath).name)

    return f"""
    <style>
        .xl-shell {{
            display: flex;
            flex-direction: column;
            height: 82vh;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 0 0 1px #232336, 0 8px 40px #0008;
        }}
        .xl-toolbar {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 10px 20px;
            background: #18182a;
            border-bottom: 1px solid #232336;
            gap: 16px;
            flex-shrink: 0;
        }}
        .xl-toolbar-left {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .xl-icon {{
            width: 28px;
            height: 28px;
            background: linear-gradient(135deg, #16a34a 60%, #15803d);
            border-radius: 6px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            font-weight: 700;
            color: #fff;
            flex-shrink: 0;
        }}
        .xl-fname {{
            font-size: 13px;
            font-weight: 500;
            color: #c8c8e0;
            max-width: 360px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .xl-tabs {{
            display: flex;
            gap: 4px;
            align-items: center;
        }}
        .xl-tab {{
            padding: 4px 14px;
            border-radius: 6px 6px 0 0;
            font-size: 12px;
            cursor: pointer;
            border: 1px solid transparent;
            color: #666;
            background: transparent;
            transition: all 0.15s;
            white-space: nowrap;
            max-width: 140px;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .xl-tab:hover {{ color: #a78bfa; background: #1e1e32; }}
        .xl-tab.active {{
            color: #a78bfa;
            background: #13131f;
            border-color: #2e2e4a #2e2e4a transparent;
        }}
        .xl-stats {{
            font-size: 11px;
            color: #444;
        }}
        .xl-body {{
            flex: 1;
            overflow: auto;
            background: #13131f;
            padding: 0;
        }}
        .xl-loading {{
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100%;
            gap: 14px;
            color: #555;
            font-size: 14px;
        }}
        .xl-spinner {{
            width: 36px;
            height: 36px;
            border: 3px solid #232336;
            border-top-color: #16a34a;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }}
        @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
        .xl-error {{
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100%;
            color: #ef4444;
            font-size: 14px;
            gap: 8px;
        }}
        #xl-table-wrap {{
            min-width: 100%;
        }}
        #xl-table-wrap table {{
            border-collapse: collapse;
            width: 100%;
            font-size: 12.5px;
            font-family: 'JetBrains Mono', 'Fira Mono', 'Consolas', monospace;
        }}
        #xl-table-wrap td, #xl-table-wrap th {{
            border: 1px solid #1e1e32;
            padding: 6px 12px;
            color: #d0d0e8;
            white-space: nowrap;
            min-width: 80px;
        }}
        #xl-table-wrap tr:first-child td,
        #xl-table-wrap tr:first-child th {{
            background: #1a1a2e;
            color: #a78bfa;
            font-weight: 600;
            position: sticky;
            top: 0;
            z-index: 2;
            border-bottom: 2px solid #2e2e4a;
        }}
        #xl-table-wrap tr:nth-child(even) td {{
            background: #141424;
        }}
        #xl-table-wrap tr:hover td {{
            background: #1e1e36;
        }}
        #xl-table-wrap td:first-child {{
            color: #555;
            background: #16162a;
            font-size: 11px;
            text-align: center;
            min-width: 40px;
            position: sticky;
            left: 0;
            z-index: 1;
            border-right: 2px solid #2e2e4a;
        }}
        #xl-table-wrap tr:first-child td:first-child {{
            z-index: 3;
            background: #1a1a2e;
        }}
    </style>

    <div class="xl-shell">
        <div class="xl-toolbar">
            <div class="xl-toolbar-left">
                <div class="xl-icon">XL</div>
                <span class="xl-fname">{filename}</span>
            </div>
            <div class="xl-tabs" id="xl-tabs"></div>
            <span class="xl-stats" id="xl-stats"></span>
        </div>
        <div class="xl-body" id="xl-body">
            <div class="xl-loading" id="xl-loading">
                <div class="xl-spinner"></div>
                <span>Загрузка таблицы…</span>
            </div>
        </div>
    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js"></script>
    <script>
        let xlWorkbook = null;
        let xlCurrentSheet = null;

        fetch('{_FILES_BASE}/{safe_filepath}')
            .then(r => {{
                if (!r.ok) throw new Error('HTTP ' + r.status + ': ' + r.statusText);
                return r.arrayBuffer();
            }})
            .then(buf => {{
                xlWorkbook = XLSX.read(buf, {{ type: 'array' }});
                renderTabs();
                showSheet(xlWorkbook.SheetNames[0]);
            }})
            .catch(err => {{
                console.error('Excel loading error:', err);
                document.getElementById('xl-loading').outerHTML =
                    '<div class="xl-error">⚠ Не удалось загрузить файл: ' + err.message + '</div>';
            }});

        function renderTabs() {{
            const tabs = document.getElementById('xl-tabs');
            tabs.innerHTML = '';
            xlWorkbook.SheetNames.forEach(name => {{
                const btn = document.createElement('button');
                btn.className = 'xl-tab';
                btn.textContent = name;
                btn.title = name;
                btn.onclick = () => showSheet(name);
                tabs.appendChild(btn);
            }});
        }}

        function showSheet(name) {{
            xlCurrentSheet = name;

            // Update active tab
            document.querySelectorAll('.xl-tab').forEach(btn => {{
                btn.classList.toggle('active', btn.textContent === name);
            }});

            const sheet = xlWorkbook.Sheets[name];
            const tableHtml = XLSX.utils.sheet_to_html(sheet, {{ id: 'xl-raw-table', editable: false }});

            const wrap = document.createElement('div');
            wrap.id = 'xl-table-wrap';
            wrap.innerHTML = tableHtml;

            const body = document.getElementById('xl-body');
            body.innerHTML = '';
            body.appendChild(wrap);

            // Stats
            const range = sheet['!ref'];
            if (range) {{
                const ref = XLSX.utils.decode_range(range);
                const rows = ref.e.r - ref.s.r + 1;
                const cols = ref.e.c - ref.s.c + 1;
                document.getElementById('xl-stats').textContent = rows + ' стр × ' + cols + ' ст';
            }} else {{
                document.getElementById('xl-stats').textContent = '';
            }}
        }}
    </script>
    """


def wrap_page(filename: str, body_html: str) -> str:
    """
    Wrap content in common HTML template.

    :param filename: Name of the file being previewed
    :type filename: str
    :param body_html: HTML content to wrap
    :type body_html: str
    :return: Complete HTML page
    :rtype: str
    """
    safe_filename = html.escape(filename)
    ext = Path(filename).suffix.upper()[1:]
    logger.debug(f"Wrapping page for {filename}")

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{safe_filename}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #1a1a2e; color: #e0e0e0; min-height: 100vh; }}
        header {{ position: sticky; top: 0; z-index: 10; background: #13131f; border-bottom: 1px solid #1e1e32; padding: 12px 24px; display: flex; align-items: center; gap: 12px; backdrop-filter: blur(10px); }}
        header .fname {{ font-size: 14px; font-weight: 600; color: #a78bfa; max-width: 500px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
        header .ext-badge {{ font-size: 10px; padding: 2px 8px; border-radius: 10px; background: #1e1e32; color: #6b6b8a; font-family: monospace; text-transform: uppercase; }}
        header .nav-link {{ color: #6b6b8a; text-decoration: none; font-size: 13px; margin-left: auto; padding: 4px 12px; border-radius: 15px; background: #1e1e32; }}
        header .nav-link:hover {{ color: #a78bfa; }}
        .content {{ max-width: 1200px; margin: 0 auto; padding: 28px 24px; background: #13131f; min-height: calc(100vh - 61px); }}
        .content h1, .content h2, .content h3, .content h4 {{ color: #a78bfa; margin: 1.5em 0 0.5em; font-weight: 500; }}
        .content h1 {{ font-size: 2em; border-bottom: 1px solid #1e1e32; padding-bottom: 0.3em; }}
        .content p {{ line-height: 1.8; margin-bottom: 1em; color: #c8c8e0; }}
        .content table {{ border-collapse: collapse; width: 100%; margin: 1em 0; background: #1a1a2e; border-radius: 8px; overflow: hidden; }}
        .content td, .content th {{ border: 1px solid #1e1e32; padding: 8px 12px; text-align: left; }}
        .content th {{ background: #1e1e32; color: #a78bfa; font-weight: 600; }}
        .content tr:nth-child(even) {{ background: #151525; }}
        .content img {{ max-width: 100%; height: auto; border-radius: 8px; margin: 1em 0; }}
        .content a {{ color: #a78bfa; text-decoration: none; }}
        .content a:hover {{ text-decoration: underline; }}
        mark {{ background: #ffd700; color: #000; border-radius: 3px; padding: 2px 4px; scroll-margin-top: 80px; font-weight: 500; }}
        ::-webkit-scrollbar {{ width: 8px; height: 8px; }}
        ::-webkit-scrollbar-track {{ background: #1e1e32; }}
        ::-webkit-scrollbar-thumb {{ background: #a78bfa; border-radius: 4px; }}
        ::-webkit-scrollbar-thumb:hover {{ background: #b79cff; }}
    </style>
</head>
<body>
    <header>
        <span class="fname">📄 {safe_filename}</span>
        <span class="ext-badge">{ext}</span>
        <a href="/" class="nav-link">← Все файлы</a>
    </header>
    <div class="content">
        {body_html}
    </div>
    <script>
        setTimeout(() => {{
            const firstMark = document.querySelector('mark');
            if (firstMark) firstMark.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
        }}, 100);
    </script>
</body>
</html>"""
