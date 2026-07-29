"""
Hawsub GUI Server & Web Application Interface.
Serves the professional subtitle workstation GUI and REST API.
"""

import os
import re
import json
import uuid
import time
import logging
import tempfile
import platform
from typing import Dict, Any, List, Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from hawsub.config.loader import load_config
from hawsub.core.orchestration.pipeline import DurablePipeline
from hawsub.core.normalization.sorani import SoraniNormalizer
from hawsub.benchmark.suite import BenchmarkSuite
from hawsub.providers.factory import get_provider

logger = logging.getLogger("hawsub.server")

# === App Configuration ===
APP_VERSION = "1.0.0"
START_TIME = time.time()
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {".srt", ".vtt", ".ass", ".ssa"}

# Auth token from environment (optional — if not set, auth is disabled)
AUTH_TOKEN = os.environ.get("HAWSUB_GUI_TOKEN", "")

# === FastAPI App ===
app = FastAPI(
    title="Hawsub Subtitle Localization Workstation",
    version=APP_VERSION,
    docs_url="/api/docs",
    redoc_url=None,
)

# CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# === State ===
active_projects: Dict[str, Dict[str, Any]] = {}
normalizer = SoraniNormalizer()
request_count = 0
total_processed = 0

# === Static Files ===
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# === Auth Dependency ===
async def verify_auth(request: Request):
    """Verify bearer token if HAWSUB_GUI_TOKEN is configured."""
    if not AUTH_TOKEN:
        return  # Auth disabled

    # Public endpoints that don't require auth
    public_paths = {"/", "/api/health", "/api/docs", "/openapi.json"}
    if request.url.path in public_paths or request.url.path.startswith("/static"):
        return

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = auth_header[7:]
    if token != AUTH_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid API token")


# === Request Logging Middleware ===
@app.middleware("http")
async def log_requests(request: Request, call_next):
    global request_count
    request_count += 1
    start = time.time()
    response = await call_next(request)
    elapsed_ms = (time.time() - start) * 1000
    logger.info(
        f"{request.method} {request.url.path} → {response.status_code} ({elapsed_ms:.0f}ms)"
    )
    return response


# === HTML Entrypoint ===
@app.get("/", response_class=HTMLResponse)
def get_gui_index():
    """Serve the professional GUI."""
    html_path = STATIC_DIR / "index.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Hawsub</h1><p>Static files not found.</p>", status_code=500)


# === Health & Monitoring ===
@app.get("/api/health")
def api_health():
    """Health check endpoint for Docker/Kubernetes probes."""
    uptime_sec = time.time() - START_TIME
    return {
        "status": "healthy",
        "version": APP_VERSION,
        "uptime_seconds": round(uptime_sec, 1),
        "python_version": platform.python_version(),
        "active_projects": len(active_projects),
    }


@app.get("/api/stats")
def api_stats():
    """System statistics for monitoring dashboards."""
    uptime_sec = time.time() - START_TIME

    # Memory info (best effort)
    try:
        import resource
        mem_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024  # macOS gives KB
    except Exception:
        mem_mb = 0

    return {
        "uptime_seconds": round(uptime_sec, 1),
        "total_requests": request_count,
        "total_processed": total_processed,
        "active_projects": len(active_projects),
        "memory_mb": round(mem_mb, 1),
    }


# === Project ID Validation ===
def _validate_project_id(project_id: str) -> str:
    """Sanitize project_id to prevent path traversal or invalid characters."""
    if not project_id or not re.match(r"^[a-zA-Z0-9_\-]+$", project_id):
        raise HTTPException(status_code=400, detail="Invalid project ID format")
    return project_id


# === Upload ===
@app.post("/api/upload")
async def api_upload_file(file: UploadFile = File(...)):
    """Upload an SRT/VTT/ASS subtitle file and create a project."""
    from hawsub.core.ingest.parser import SubtitleParser, format_timestamp_srt

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Supported: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    raw_bytes = await file.read()
    if len(raw_bytes) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(raw_bytes)} bytes). Maximum: {MAX_UPLOAD_SIZE} bytes.",
        )
    if len(raw_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    try:
        content = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            content = raw_bytes.decode("latin-1")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="File encoding not recognized. Use UTF-8.")

    if not content.strip():
        raise HTTPException(status_code=400, detail="File contains no content")

    cues = SubtitleParser.parse_auto(content, file.filename)
    if not cues:
        raise HTTPException(status_code=400, detail="No subtitle cues could be parsed from file")

    project_id = f"proj_{uuid.uuid4().hex[:8]}"

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

    logger.info(f"Project {project_id} created: {file.filename} ({len(cues)} cues)")

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


# === Process ===
@app.post("/api/process/{project_id}")
async def api_process_project(project_id: str):
    """Run the full localization pipeline on a project."""
    global total_processed
    from hawsub.core.ingest.parser import SubtitleParser, format_timestamp_srt

    _validate_project_id(project_id)
    proj = active_projects.get(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    output_dir = os.path.join(tempfile.gettempdir(), "hawsub_output", project_id)
    os.makedirs(output_dir, exist_ok=True)
    db_path = os.path.join(output_dir, f"{project_id}.hawsub.db")

    def on_progress(data: dict):
        if project_id in active_projects:
            active_projects[project_id]["progress"] = data

    try:
        pipeline = DurablePipeline(project_id=project_id, db_path=db_path)
        results = pipeline.process_file(
            proj["input_path"],
            output_dir=output_dir,
            progress_callback=on_progress,
        )
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Pipeline failed for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Pipeline error: {e}")

    # Re-read cues
    with open(proj["input_path"], "r", encoding="utf-8-sig") as f:
        content = f.read()
    cues = SubtitleParser.parse_auto(content, proj["filename"])

    if os.path.exists(results["srt"]):
        with open(results["srt"], "r", encoding="utf-8") as f:
            translated = SubtitleParser.parse_srt(f.read())
            for orig, trans in zip(cues, translated):
                orig.target_text = trans.source_text

    proj["cues"] = cues
    proj["results"] = results
    total_processed += 1

    logger.info(f"Pipeline complete for {project_id}: {len(cues)} cues")

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


@app.get("/api/progress/{project_id}")
def api_get_progress(project_id: str):
    """Retrieve current processing progress for a project."""
    _validate_project_id(project_id)
    proj = active_projects.get(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    progress = proj.get("progress", {"stage": "idle", "percent": 0.0})
    return {"project_id": project_id, "progress": progress}



# === Normalize ===
@app.post("/api/normalize")
async def api_normalize(body: dict):
    """Normalize Sorani Kurdish text."""
    text = body.get("text", "")
    return {"original": text, "normalized": normalizer.normalize(text)}


# === Benchmark ===
@app.get("/api/benchmark")
def api_run_benchmark():
    """Run the gold standard benchmark evaluation."""
    model = get_provider(provider_name="mock", model_name="gemini-2.5-pro")
    suite = BenchmarkSuite(dataset_path="tests/gold/gold_dataset.json")
    report = suite.evaluate_model(model)
    return report.model_dump()


# === Projects ===
@app.get("/api/projects")
def api_list_projects():
    """List all active projects."""
    return [
        {"project_id": pid, "filename": p.get("filename"), "cues": len(p.get("cues", []))}
        for pid, p in active_projects.items()
    ]


@app.get("/api/project/{project_id}")
def api_get_project(project_id: str):
    """Get project details and cues."""
    from hawsub.core.ingest.parser import format_timestamp_srt

    _validate_project_id(project_id)
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


# === Cue Edit ===
@app.patch("/api/cue/{project_id}/{cue_id}")
async def api_edit_cue(project_id: str, cue_id: int, body: dict):
    """Edit a single cue's target text."""
    _validate_project_id(project_id)
    proj = active_projects.get(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    target_text = body.get("target_text")
    if target_text is None:
        raise HTTPException(status_code=400, detail="Missing target_text field")

    cues = proj.get("cues", [])
    for cue in cues:
        if cue.id == cue_id:
            cue.target_text = target_text
            return {"cue_id": cue_id, "target_text": target_text, "status": "updated"}

    raise HTTPException(status_code=404, detail=f"Cue {cue_id} not found")


# === Export ===
@app.get("/api/export/{project_id}/{format}")
def api_export(project_id: str, format: str):
    """Export translated subtitle files."""
    _validate_project_id(project_id)
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
        raise HTTPException(status_code=404, detail="Export file not found. Run the pipeline first.")

    return FileResponse(path, filename=filename, media_type=media_type)


# === Entry Point ===
def start_gui(host: str = "127.0.0.1", port: int = 8080):
    """Launch the Hawsub GUI workstation."""
    auth_msg = " (auth enabled)" if AUTH_TOKEN else " (no auth)"
    print(f"◈ Hawsub Subtitle Workstation v{APP_VERSION} — http://{host}:{port}{auth_msg}")
    uvicorn.run(app, host=host, port=port, log_level="info")
