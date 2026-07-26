"""
Hawsub GUI Server & Web Application Interface.
Provides a modern dark-mode GUI workstation for cinematic English -> Sorani subtitle localization.
"""

import os
import json
import uuid
import tempfile
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
import uvicorn

from hawsub.config.loader import load_config
from hawsub.core.orchestration.pipeline import DurablePipeline
from hawsub.core.normalization.sorani import SoraniNormalizer
from hawsub.benchmark.suite import BenchmarkSuite
from hawsub.providers.factory import get_provider

app = FastAPI(title="Hawsub Subtitle Localization Workstation", version="1.0.0")

# In-memory active project state for GUI session
active_projects: Dict[str, Dict[str, Any]] = {}
normalizer = SoraniNormalizer()


@app.get("/", response_class=HTMLResponse)
def get_gui_index():
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="Hawsub — Production-grade English to Central Kurdish (Sorani, ckb) cinematic subtitle localization workstation.">
    <title>Hawsub — Sorani Subtitle Workstation</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Naskh+Arabic:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-dark: #0f172a;
            --panel-bg: #1e293b;
            --border-color: #334155;
            --accent-blue: #38bdf8;
            --accent-green: #22c55e;
            --accent-yellow: #f59e0b;
            --accent-red: #ef4444;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
            background: var(--bg-dark);
            color: var(--text-main);
            height: 100vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        /* Header */
        header {
            background: #020617;
            border-bottom: 1px solid var(--border-color);
            padding: 12px 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .logo { font-size: 1.25rem; font-weight: 700; color: var(--accent-blue); display: flex; align-items: center; gap: 8px; }
        .badge { background: #0369a1; color: #ffffff; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
        .status-bar { display: flex; align-items: center; gap: 16px; font-size: 0.85rem; color: var(--text-muted); }
        .status-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
        .status-dot.ok { background: var(--accent-green); }
        .status-dot.warn { background: var(--accent-yellow); }

        /* Main layout */
        .workspace { display: flex; flex: 1; overflow: hidden; }

        /* Left sidebar */
        .sidebar {
            width: 320px;
            background: var(--panel-bg);
            border-right: 1px solid var(--border-color);
            display: flex;
            flex-direction: column;
        }
        .section-header { padding: 12px 16px; font-size: 0.85rem; font-weight: 600; color: var(--text-muted); text-transform: uppercase; border-bottom: 1px solid var(--border-color); display: flex; align-items: center; justify-content: space-between; }
        .cue-list { flex: 1; overflow-y: auto; }
        .cue-item {
            padding: 12px 16px;
            border-bottom: 1px solid var(--border-color);
            cursor: pointer;
            transition: background 0.15s;
        }
        .cue-item:hover, .cue-item.active { background: #334155; }
        .cue-item.failed { border-left: 3px solid var(--accent-red); }
        .cue-item.review { border-left: 3px solid var(--accent-yellow); }
        .cue-item.passed { border-left: 3px solid var(--accent-green); }
        .cue-time { font-size: 0.75rem; color: var(--accent-blue); font-family: monospace; }
        .cue-src { font-size: 0.85rem; margin-top: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .cue-trg { font-size: 0.8rem; margin-top: 2px; color: var(--text-muted); direction: rtl; font-family: 'Noto Naskh Arabic', sans-serif; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

        /* Center pane */
        .main-pane { flex: 1; display: flex; flex-direction: column; background: #0f172a; padding: 24px; gap: 20px; overflow-y: auto; }

        .card { background: var(--panel-bg); border: 1px solid var(--border-color); border-radius: 12px; padding: 20px; }

        .editor-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .label { font-size: 0.8rem; font-weight: 600; color: var(--text-muted); margin-bottom: 8px; }

        .src-box { background: #090d16; border: 1px solid var(--border-color); border-radius: 8px; padding: 14px; font-size: 1.1rem; min-height: 80px; }
        .trg-box {
            background: #090d16;
            border: 1px solid var(--accent-blue);
            border-radius: 8px;
            padding: 14px;
            font-size: 1.25rem;
            min-height: 80px;
            direction: rtl;
            font-family: 'Noto Naskh Arabic', sans-serif;
            color: #fff;
            width: 100%;
            resize: vertical;
        }

        /* Quality Gauges */
        .metrics-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
        .metric-card { background: #090d16; border: 1px solid var(--border-color); padding: 12px; border-radius: 8px; text-align: center; }
        .metric-val { font-size: 1.4rem; font-weight: 700; color: var(--accent-green); margin-top: 4px; }

        /* File Upload Zone */
        .upload-zone {
            border: 2px dashed var(--border-color);
            border-radius: 12px;
            padding: 40px;
            text-align: center;
            transition: all 0.3s;
            cursor: pointer;
        }
        .upload-zone:hover { border-color: var(--accent-blue); background: rgba(56, 189, 248, 0.05); }
        .upload-zone.dragging { border-color: var(--accent-green); background: rgba(34, 197, 94, 0.05); }
        .upload-zone h3 { font-size: 1.1rem; margin-bottom: 8px; }
        .upload-zone p { font-size: 0.85rem; color: var(--text-muted); }

        /* Action Buttons */
        .btn-group { display: flex; gap: 12px; flex-wrap: wrap; }
        .btn {
            padding: 10px 20px;
            border-radius: 8px;
            border: none;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-size: 0.9rem;
        }
        .btn:hover { opacity: 0.9; transform: translateY(-1px); }
        .btn:active { transform: translateY(0); }
        .btn-primary { background: var(--accent-blue); color: #000; }
        .btn-success { background: var(--accent-green); color: #000; }
        .btn-warning { background: var(--accent-yellow); color: #000; }
        .btn-danger { background: var(--accent-red); color: #fff; }
        .btn-secondary { background: #475569; color: #fff; }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }

        /* Right Pane */
        .right-pane { width: 340px; background: var(--panel-bg); border-left: 1px solid var(--border-color); padding: 16px; display: flex; flex-direction: column; gap: 16px; overflow-y: auto; }
        .glossary-item { background: #090d16; padding: 10px; border-radius: 6px; font-size: 0.85rem; border-left: 3px solid var(--accent-blue); margin-bottom: 8px; }

        /* Progress */
        .progress-bar { width: 100%; height: 4px; background: var(--border-color); border-radius: 2px; overflow: hidden; }
        .progress-fill { height: 100%; background: var(--accent-blue); transition: width 0.5s ease; border-radius: 2px; }

        /* Toast */
        .toast { position: fixed; top: 20px; right: 20px; padding: 12px 20px; border-radius: 8px; font-weight: 500; z-index: 1000; animation: slideIn 0.3s ease; }
        .toast.success { background: var(--accent-green); color: #000; }
        .toast.error { background: var(--accent-red); color: #fff; }
        @keyframes slideIn { from { transform: translateX(100px); opacity: 0; } to { transform: translateX(0); opacity: 1; } }

        /* Spinner */
        .spinner { display: inline-block; width: 16px; height: 16px; border: 2px solid transparent; border-top: 2px solid currentColor; border-radius: 50%; animation: spin 0.6s linear infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }
    </style>
</head>
<body>

    <header>
        <div class="logo">
            ⚡ Hawsub <span class="badge">Sorani (ckb)</span>
        </div>
        <div class="status-bar">
            <span><span class="status-dot ok"></span> Pipeline Ready</span>
            <span id="project-status">No project loaded</span>
        </div>
        <div class="btn-group">
            <button class="btn btn-secondary" onclick="runBenchmark()">📊 Benchmark</button>
            <button class="btn btn-secondary" onclick="normalizeText()">🔤 Normalize</button>
            <button class="btn btn-primary" id="btn-process" onclick="triggerProcess()" disabled>▶ Run Pipeline</button>
        </div>
    </header>

    <main class="workspace">
        <!-- Left Sidebar: Cue List -->
        <div class="sidebar">
            <div class="section-header">
                <span>Subtitle Cues (<span id="cue-count">0</span>)</span>
                <label class="btn btn-secondary" style="padding: 4px 10px; font-size: 0.8rem;">
                    📂 Upload
                    <input type="file" accept=".srt,.vtt,.ass,.ssa" style="display:none;" onchange="handleFileUpload(event)">
                </label>
            </div>
            <div id="upload-zone" class="upload-zone" style="margin: 16px;">
                <h3>📁 Drop subtitle file here</h3>
                <p>Supports SRT, VTT, ASS/SSA</p>
            </div>
            <div class="cue-list" id="cue-list" style="display:none;"></div>
        </div>

        <!-- Center Pane -->
        <div class="main-pane">
            <div id="editor-section" style="display:none;">
                <div class="card" style="margin-bottom: 20px;">
                    <div class="editor-grid">
                        <div>
                            <div class="label">ENGLISH SOURCE DIALOGUE</div>
                            <div class="src-box" id="src-box">Select a cue to view...</div>
                        </div>
                        <div>
                            <div class="label">CENTRAL KURDISH (SORANI, CKB) SUBTITLE</div>
                            <textarea class="trg-box" id="trg-box" placeholder="Translation will appear here..."></textarea>
                        </div>
                    </div>
                </div>

                <!-- Quality Gauges -->
                <div class="metrics-grid" style="margin-bottom: 20px;">
                    <div class="metric-card">
                        <div class="label">OVERALL CONFIDENCE</div>
                        <div class="metric-val" id="m-confidence">—</div>
                    </div>
                    <div class="metric-card">
                        <div class="label">CPS READABILITY</div>
                        <div class="metric-val" id="m-cps" style="color: var(--accent-blue);">—</div>
                    </div>
                    <div class="metric-card">
                        <div class="label">CPL LINE LENGTH</div>
                        <div class="metric-val" id="m-cpl">—</div>
                    </div>
                    <div class="metric-card">
                        <div class="label">2ND MODEL VERIFIER</div>
                        <div class="metric-val" id="m-verify" style="color: var(--accent-green);">—</div>
                    </div>
                </div>

                <!-- Actions Card -->
                <div class="card">
                    <div class="label">ACTIONS</div>
                    <div style="margin-top: 12px;" class="btn-group">
                        <button class="btn btn-success" onclick="approveCue()">✓ Accept</button>
                        <button class="btn btn-warning" onclick="saveEdit()">✎ Save Edit</button>
                        <button class="btn btn-secondary" onclick="prevCue()">← Prev</button>
                        <button class="btn btn-secondary" onclick="nextCue()">→ Next</button>
                    </div>
                </div>
            </div>

            <!-- Pipeline Progress -->
            <div id="progress-section" style="display:none;">
                <div class="card">
                    <div class="label">PIPELINE PROGRESS</div>
                    <div class="progress-bar" style="margin-top: 12px;">
                        <div class="progress-fill" id="progress-fill" style="width: 0%;"></div>
                    </div>
                    <p id="progress-text" style="margin-top: 8px; color: var(--text-muted); font-size: 0.85rem;">Waiting...</p>
                </div>
            </div>

            <!-- Welcome screen when no project loaded -->
            <div id="welcome-section">
                <div class="card" style="text-align: center; padding: 60px;">
                    <h2 style="margin-bottom: 12px;">⚡ Hawsub Subtitle Workstation</h2>
                    <p style="color: var(--text-muted); max-width: 500px; margin: 0 auto;">
                        Professional English → Central Kurdish (Sorani) cinematic subtitle localization.
                        Upload an SRT, VTT, or ASS subtitle file to begin.
                    </p>
                </div>
            </div>
        </div>

        <!-- Right Pane -->
        <div class="right-pane">
            <div class="section-header">Project Info</div>
            <div id="project-info" style="font-size: 0.85rem; color: var(--text-muted);">
                <strong>Project:</strong> None loaded<br>
                <strong>Cues:</strong> 0<br>
                <strong>Status:</strong> Idle
            </div>

            <div class="section-header" style="margin-top: 12px;">Exports</div>
            <button class="btn btn-primary" style="width: 100%; justify-content: center;" onclick="exportFile('srt')">Export SRT</button>
            <button class="btn btn-secondary" style="width: 100%; justify-content: center;" onclick="exportFile('ass')">Export ASS</button>
            <button class="btn btn-secondary" style="width: 100%; justify-content: center;" onclick="exportFile('vtt')">Export VTT</button>
            <button class="btn btn-secondary" style="width: 100%; justify-content: center;" onclick="exportFile('html')">Debug HTML</button>
            <button class="btn btn-secondary" style="width: 100%; justify-content: center;" onclick="exportFile('qc')">QC Report</button>
        </div>
    </main>

    <script>
        let projectId = null;
        let cues = [];
        let currentCueIdx = 0;

        function escapeHtml(str) {
            if (!str) return '';
            const div = document.createElement('div');
            div.textContent = str;
            return div.innerHTML;
        }

        function showToast(msg, type = 'success') {
            const t = document.createElement('div');
            t.className = 'toast ' + type;
            t.textContent = msg;
            document.body.appendChild(t);
            setTimeout(() => t.remove(), 3000);
        }

        window.addEventListener('DOMContentLoaded', async () => {
            const params = new URLSearchParams(window.location.search);
            const pidParam = params.get('project_id') || params.get('id');
            if (pidParam) {
                await loadProjectById(pidParam);
            } else {
                try {
                    const resp = await fetch('/api/projects');
                    const projects = await resp.json();
                    if (projects && projects.length > 0) {
                        await loadProjectById(projects[projects.length - 1].project_id);
                    }
                } catch(e) {}
            }
        });

        async function loadProjectById(pid) {
            try {
                const resp = await fetch('/api/project/' + pid);
                if (!resp.ok) return;
                const data = await resp.json();
                if (data.project_id) {
                    projectId = data.project_id;
                    cues = data.cues || [];
                    document.getElementById('project-status').textContent = 'Project: ' + projectId;
                    document.getElementById('btn-process').disabled = false;
                    window.history.replaceState(null, '', '?project_id=' + projectId);
                    renderCueList();
                    showToast('Loaded project ' + projectId + ' (' + cues.length + ' cues)');
                }
            } catch(e) {}
        }

        // File Upload
        function handleFileUpload(event) {
            const file = event.target.files[0];
            if (!file) return;
            uploadFile(file);
        }

        const dropZone = document.getElementById('upload-zone');
        dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragging'); });
        dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragging'));
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragging');
            const file = e.dataTransfer.files[0];
            if (file) uploadFile(file);
        });

        async function uploadFile(file) {
            const formData = new FormData();
            formData.append('file', file);
            try {
                const resp = await fetch('/api/upload', { method: 'POST', body: formData });
                const data = await resp.json();
                if (data.project_id) {
                    projectId = data.project_id;
                    cues = data.cues || [];
                    document.getElementById('project-status').textContent = 'Project: ' + projectId;
                    document.getElementById('btn-process').disabled = false;
                    window.history.pushState(null, '', '?project_id=' + projectId);
                    renderCueList();
                    showToast('Loaded ' + cues.length + ' cues from ' + file.name);
                }
            } catch(e) {
                showToast('Upload failed: ' + e.message, 'error');
            }
        }

        function renderCueList() {
            const list = document.getElementById('cue-list');
            const uploadZone = document.getElementById('upload-zone');
            uploadZone.style.display = 'none';
            list.style.display = 'block';
            document.getElementById('cue-count').textContent = cues.length;
            document.getElementById('welcome-section').style.display = 'none';
            document.getElementById('editor-section').style.display = 'block';
            document.getElementById('project-info').innerHTML =
                '<strong>Project:</strong> ' + projectId + '<br>' +
                '<strong>Cues:</strong> ' + cues.length + '<br>' +
                '<strong>Status:</strong> Ready';

            list.innerHTML = cues.map((c, i) => `
                <div class="cue-item ${i === currentCueIdx ? 'active' : ''} ${c.target_text ? 'passed' : ''}"
                     onclick="selectCue(${i})">
                    <div class="cue-time">${escapeHtml(c.timecode)}</div>
                    <div class="cue-src">${escapeHtml(c.source_text)}</div>
                    ${c.target_text ? '<div class="cue-trg">' + escapeHtml(c.target_text) + '</div>' : ''}
                </div>
            `).join('');

            if (cues.length > 0) selectCue(0);
        }

        function selectCue(idx) {
            currentCueIdx = idx;
            const cue = cues[idx];
            document.getElementById('src-box').textContent = cue.source_text;
            document.getElementById('trg-box').value = cue.target_text || '';

            document.querySelectorAll('.cue-item').forEach((el, i) => {
                el.classList.toggle('active', i === idx);
            });
        }

        function prevCue() { if (currentCueIdx > 0) selectCue(currentCueIdx - 1); }
        function nextCue() { if (currentCueIdx < cues.length - 1) selectCue(currentCueIdx + 1); }
        function approveCue() { showToast('Cue #' + (currentCueIdx + 1) + ' approved'); nextCue(); }
        function saveEdit() {
            const newText = document.getElementById('trg-box').value;
            cues[currentCueIdx].target_text = newText;
            renderCueList();
            showToast('Edit saved');
        }

        async function triggerProcess() {
            if (!projectId) return;
            document.getElementById('progress-section').style.display = 'block';
            document.getElementById('progress-fill').style.width = '20%';
            document.getElementById('progress-text').textContent = 'Processing pipeline...';
            document.getElementById('btn-process').disabled = true;

            try {
                const resp = await fetch('/api/process/' + projectId, { method: 'POST' });
                const data = await resp.json();
                document.getElementById('progress-fill').style.width = '100%';
                document.getElementById('progress-text').textContent = 'Pipeline complete!';
                if (data.cues) { cues = data.cues; renderCueList(); }
                showToast('Pipeline finished — ' + (data.total_cues || 0) + ' cues translated');
            } catch(e) {
                document.getElementById('progress-text').textContent = 'Pipeline failed: ' + e.message;
                showToast('Pipeline error', 'error');
            }
            document.getElementById('btn-process').disabled = false;
        }

        async function runBenchmark() {
            try {
                const resp = await fetch('/api/benchmark');
                const d = await resp.json();
                showToast('Benchmark: ' + (d.overall_benchmark_score * 100).toFixed(1) + '% (' + d.passed_items + '/' + d.total_items + ')');
            } catch(e) { showToast('Benchmark error', 'error'); }
        }

        function normalizeText() {
            const text = document.getElementById('trg-box').value;
            if (!text) { showToast('No text to normalize', 'error'); return; }
            fetch('/api/normalize', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({text}) })
                .then(r => r.json())
                .then(d => { document.getElementById('trg-box').value = d.normalized; showToast('Text normalized'); })
                .catch(e => showToast('Normalize error', 'error'));
        }

        function exportFile(format) {
            if (!projectId) { showToast('No project loaded', 'error'); return; }
            window.location.href = '/api/export/' + projectId + '/' + format;
        }
    </script>
</body>
</html>
"""


# Maximum upload size (10 MB)
MAX_UPLOAD_SIZE = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".srt", ".vtt", ".ass", ".ssa"}


@app.post("/api/upload")
async def api_upload_file(file: UploadFile = File(...)):
    """Upload an SRT/VTT/ASS subtitle file and create a project."""
    from hawsub.core.ingest.parser import SubtitleParser, format_timestamp_srt

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    # Validate file extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}. Supported: {', '.join(ALLOWED_EXTENSIONS)}")

    # Read with size limit
    raw_bytes = await file.read()
    if len(raw_bytes) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail=f"File too large ({len(raw_bytes)} bytes). Maximum: {MAX_UPLOAD_SIZE} bytes.")
    if len(raw_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    # Decode with BOM handling
    try:
        content = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            content = raw_bytes.decode("latin-1")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="File encoding not recognized. Please use UTF-8.")

    if not content.strip():
        raise HTTPException(status_code=400, detail="File contains no content")

    cues = SubtitleParser.parse_auto(content, file.filename)
    if not cues:
        raise HTTPException(status_code=400, detail="No subtitle cues could be parsed from file")

    project_id = f"proj_{uuid.uuid4().hex[:8]}"

    # Store in active projects
    upload_dir = os.path.join(tempfile.gettempdir(), "hawsub_uploads")
    os.makedirs(upload_dir, exist_ok=True)
    input_path = os.path.join(upload_dir, f"{project_id}{ext}")
    with open(input_path, "w", encoding="utf-8") as f:
        f.write(content)

    active_projects[project_id] = {
        "input_path": input_path,
        "filename": file.filename,
        "cues": cues,
    }

    return {
        "project_id": project_id,
        "filename": file.filename,
        "total_cues": len(cues),
        "cues": [
            {
                "id": c.id,
                "source_text": c.clean_source_text,
                "target_text": c.target_text or "",
                "timecode": f"{format_timestamp_srt(c.start_ms)} --> {format_timestamp_srt(c.end_ms)}",
            }
            for c in cues
        ],
    }


@app.post("/api/process/{project_id}")
async def api_process_project(project_id: str):
    """Run the full localization pipeline on a project."""
    from hawsub.core.ingest.parser import format_timestamp_srt

    proj = active_projects.get(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    output_dir = os.path.join(tempfile.gettempdir(), "hawsub_output", project_id)
    os.makedirs(output_dir, exist_ok=True)

    db_path = os.path.join(output_dir, f"{project_id}.hawsub.db")

    try:
        pipeline = DurablePipeline(project_id=project_id, db_path=db_path)
        results = pipeline.process_file(proj["input_path"], output_dir=output_dir)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {e}")

    # Re-read source cues with BOM handling
    from hawsub.core.ingest.parser import SubtitleParser
    with open(proj["input_path"], "r", encoding="utf-8-sig") as f:
        content = f.read()
    cues = SubtitleParser.parse_auto(content, proj["filename"])

    # Read back translated SRT to get target texts
    if os.path.exists(results["srt"]):
        with open(results["srt"], "r", encoding="utf-8") as f:
            translated = SubtitleParser.parse_srt(f.read())
            for orig, trans in zip(cues, translated):
                orig.target_text = trans.source_text

    proj["cues"] = cues
    proj["results"] = results

    return {
        "project_id": project_id,
        "total_cues": len(cues),
        "output_files": results,
        "cues": [
            {
                "id": c.id,
                "source_text": c.clean_source_text,
                "target_text": c.target_text or "",
                "timecode": f"{format_timestamp_srt(c.start_ms)} --> {format_timestamp_srt(c.end_ms)}",
            }
            for c in cues
        ],
    }


@app.post("/api/normalize")
async def api_normalize(body: dict):
    text = body.get("text", "")
    return {"original": text, "normalized": normalizer.normalize(text)}


@app.get("/api/benchmark")
def api_run_benchmark():
    model = get_provider(provider_name="mock", model_name="gemini-2.5-pro")
    suite = BenchmarkSuite(dataset_path="tests/gold/gold_dataset.json")
    report = suite.evaluate_model(model)
    return report.model_dump()


@app.get("/api/projects")
def api_list_projects():
    """List all active projects."""
    return [
        {"project_id": pid, "filename": p.get("filename"), "cues": len(p.get("cues", []))}
        for pid, p in active_projects.items()
    ]


@app.get("/api/project/{project_id}")
def api_get_project(project_id: str):
    """Retrieve details and formatted cues for a specific project."""
    from hawsub.core.ingest.parser import format_timestamp_srt
    proj = active_projects.get(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    cues = proj.get("cues", [])
    return {
        "project_id": project_id,
        "filename": proj.get("filename"),
        "total_cues": len(cues),
        "cues": [
            {
                "id": c.id,
                "source_text": c.clean_source_text,
                "target_text": c.target_text or "",
                "timecode": f"{format_timestamp_srt(c.start_ms)} --> {format_timestamp_srt(c.end_ms)}",
            }
            for c in cues
        ],
    }


@app.get("/api/export/{project_id}/{format}")
def api_export(project_id: str, format: str):
    proj = active_projects.get(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    results = proj.get("results", {})
    format_map = {
        "srt": ("srt", "application/x-subrip", "Hawsub_Sorani.srt"),
        "ass": ("ass", "text/x-ssa", "Hawsub_Sorani.ass"),
        "vtt": ("vtt", "text/vtt", "Hawsub_Sorani.vtt"),
        "html": ("bilingual_html", "text/html", "Hawsub_Debug.html"),
        "qc": ("qc_report", "application/json", "Hawsub_QC_Report.json"),
    }

    if format not in format_map:
        raise HTTPException(status_code=400, detail=f"Unknown format: {format}")

    key, media_type, filename = format_map[format]
    path = results.get(key)
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"Export file not found. Run the pipeline first.")

    return FileResponse(path, filename=filename, media_type=media_type)


def start_gui(host: str = "127.0.0.1", port: int = 8080):
    print(f"⚡ Hawsub Subtitle Workstation GUI running at http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")
