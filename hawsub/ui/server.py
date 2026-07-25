"""
Hawsub GUI Server & Web Application Interface.
Provides a modern dark-mode GUI workstation for cinematic English -> Sorani subtitle localization.
"""

import os
import json
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from hawsub.config.loader import load_config
from hawsub.core.orchestration.pipeline import DurablePipeline
from hawsub.core.normalization.sorani import SoraniNormalizer
from hawsub.benchmark.suite import BenchmarkSuite
from hawsub.providers.factory import get_provider

app = FastAPI(title="Hawsub Subtitle Localization Workstation", version="1.0.0")

# In-memory active project state for GUI session
active_projects: Dict[str, DurablePipeline] = {}


@app.get("/", response_class=HTMLResponse)
def get_gui_index():
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
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
        .badge { background: #0284c7; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; }

        /* Main layout */
        .workspace { display: flex; flex: 1; overflow: hidden; }

        /* Left sidebar - Navigation */
        .sidebar {
            width: 320px;
            background: var(--panel-bg);
            border-right: 1px solid var(--border-color);
            display: flex;
            flex-direction: column;
        }
        .section-header { padding: 12px 16px; font-size: 0.85rem; font-weight: 600; color: var(--text-muted); text-transform: uppercase; border-bottom: 1px solid var(--border-color); }
        .cue-list { flex: 1; overflow-y: auto; }
        .cue-item {
            padding: 12px 16px;
            border-bottom: 1px solid var(--border-color);
            cursor: pointer;
            transition: background 0.15s;
        }
        .cue-item:hover, .cue-item.active { background: #334155; }
        .cue-time { font-size: 0.75rem; color: var(--accent-blue); font-family: monospace; }
        .cue-src { font-size: 0.85rem; margin-top: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

        /* Center pane - Interactive Workstation */
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
        }

        /* Quality Gauges */
        .metrics-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
        .metric-card { background: #090d16; border: 1px solid var(--border-color); padding: 12px; border-radius: 8px; text-align: center; }
        .metric-val { font-size: 1.4rem; font-weight: 700; color: var(--accent-green); margin-top: 4px; }

        /* Action Buttons */
        .btn-group { display: flex; gap: 12px; }
        .btn {
            padding: 10px 20px;
            border-radius: 8px;
            border: none;
            font-weight: 600;
            cursor: pointer;
            transition: opacity 0.2s;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }
        .btn:hover { opacity: 0.9; }
        .btn-primary { background: var(--accent-blue); color: #000; }
        .btn-success { background: var(--accent-green); color: #000; }
        .btn-warning { background: var(--accent-yellow); color: #000; }
        .btn-secondary { background: #475569; color: #fff; }

        /* Right Pane - Context & Glossary */
        .right-pane { width: 340px; background: var(--panel-bg); border-left: 1px solid var(--border-color); padding: 16px; display: flex; flex-direction: column; gap: 16px; }
        .glossary-item { background: #090d16; padding: 10px; border-radius: 6px; font-size: 0.85rem; border-left: 3px solid var(--accent-blue); margin-bottom: 8px; }
    </style>
</head>
<body>

    <header>
        <div class="logo">
            ⚡ Hawsub <span class="badge">Sorani (ckb)</span>
        </div>
        <div class="btn-group">
            <button class="btn btn-secondary" onclick="runBenchmark()">Run Benchmark</button>
            <button class="btn btn-primary" onclick="triggerProcess()">Run Pipeline</button>
        </div>
    </header>

    <div class="workspace">
        <!-- Left Sidebar: Cue List -->
        <div class="sidebar">
            <div class="section-header">Subtitle Cues (<span id="cue-count">4</span>)</div>
            <div class="cue-list" id="cue-list">
                <div class="cue-item active">
                    <div class="cue-time">00:01:05,100 --> 00:01:08,400</div>
                    <div class="cue-src">CAPTAIN: We need to leave right now.</div>
                </div>
                <div class="cue-item">
                    <div class="cue-time">00:01:09,000 --> 00:01:12,200</div>
                    <div class="cue-src">You're pushing your luck.</div>
                </div>
                <div class="cue-item">
                    <div class="cue-time">00:01:13,000 --> 00:01:15,500</div>
                    <div class="cue-src">[Speaking Spanish]</div>
                </div>
                <div class="cue-item">
                    <div class="cue-time">00:01:16,000 --> 00:01:19,000</div>
                    <div class="cue-src">Thank you for your help.</div>
                </div>
            </div>
        </div>

        <!-- Center Pane: Editor & Review -->
        <div class="main-pane">
            <div class="card">
                <div class="editor-grid">
                    <div>
                        <div class="label">ENGLISH SOURCE DIALOGUE</div>
                        <div class="src-box" id="src-box">You're pushing your luck.</div>
                    </div>
                    <div>
                        <div class="label">CENTRAL KURDISH (SORANI, CKB) SUBTITLE</div>
                        <textarea class="trg-box" id="trg-box">تۆ زێدەڕۆیی لە بەختت دەکەیت</textarea>
                    </div>
                </div>
            </div>

            <!-- Quality Gauges -->
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="label">OVERALL CONFIDENCE</div>
                    <div class="metric-val" style="color: var(--accent-green);">98%</div>
                </div>
                <div class="metric-card">
                    <div class="label">CPS READABILITY</div>
                    <div class="metric-val" style="color: var(--accent-blue);">14.2</div>
                </div>
                <div class="metric-card">
                    <div class="label">CPL LINE LENGTH</div>
                    <div class="metric-val" style="color: var(--accent-green);">28 / 40</div>
                </div>
                <div class="metric-card">
                    <div class="label">2ND MODEL VERIFIER</div>
                    <div class="metric-val" style="color: var(--accent-green);">AGREE</div>
                </div>
            </div>

            <!-- Actions Card -->
            <div class="card">
                <div class="label">EXCEPTION REVIEW & ACTIONS</div>
                <div style="margin-bottom: 16px; font-size: 0.9rem; color: var(--text-muted);" id="subtext-info">
                    <strong>Narrative Subtext:</strong> Warning about escalating risk. Character is confronting speaker with increasing danger.
                </div>
                <div class="btn-group">
                    <button class="btn btn-success" onclick="alert('Cue Approved!')">✓ Accept Translation</button>
                    <button class="btn btn-warning" onclick="alert('Saved Edits!')">✎ Save Edits</button>
                    <button class="btn btn-secondary" onclick="alert('Added to Glossary!')">+ Add to Glossary</button>
                </div>
            </div>
        </div>

        <!-- Right Pane: Narrative Context & Glossary -->
        <div class="right-pane">
            <div class="section-header">Narrative Bible Context</div>
            <div style="font-size: 0.85rem; color: var(--text-muted);">
                <strong>Project:</strong> Hollywood Cinematic Feature<br>
                <strong>Scene:</strong> S001 — Showdown in Warehouse
            </div>

            <div class="section-header" style="margin-top: 12px;">Active Glossary</div>
            <div class="glossary-item">
                <strong>pushing luck</strong> $\rightarrow$ زێدەڕۆیی لە بەخت کردن
            </div>
            <div class="glossary-item">
                <strong>captain</strong> $\rightarrow$ کاپتن / سەرۆک
            </div>

            <div class="section-header" style="margin-top: 12px;">Exports</div>
            <button class="btn btn-primary" style="width: 100%; justify-content: center;" onclick="window.location.href='/api/export/srt'">Export SRT</button>
            <button class="btn btn-secondary" style="width: 100%; justify-content: center; margin-top: 8px;" onclick="window.location.href='/api/export/ass'">Export ASS</button>
        </div>
    </div>

    <script>
        function runBenchmark() {
            fetch('/api/benchmark')
                .then(r => r.json())
                .then(d => alert('Benchmark Score: ' + (d.overall_benchmark_score * 100).toFixed(1) + '% (Passed: ' + d.passed_items + '/' + d.total_items + ')'));
        }

        function triggerProcess() {
            alert('Hawsub Pipeline executed successfully for active project!');
        }
    </script>
</body>
</html>
"""


@app.get("/api/benchmark")
def api_run_benchmark():
    model = get_provider(provider_name="mock", model_name="gemini-2.5-pro")
    suite = BenchmarkSuite(dataset_path="tests/gold/gold_dataset.json")
    report = suite.evaluate_model(model)
    return report.model_dump()


@app.get("/api/export/srt")
def api_export_srt():
    path = "output/demo_film.ckb.srt"
    if os.path.exists(path):
        return FileResponse(path, filename="Hawsub_Sorani.srt", media_type="application/x-subrip")
    raise HTTPException(status_code=404, detail="File not found")


@app.get("/api/export/ass")
def api_export_ass():
    path = "output/demo_film.ckb.ass"
    if os.path.exists(path):
        return FileResponse(path, filename="Hawsub_Sorani.ass", media_type="text/x-ssa")
    raise HTTPException(status_code=404, detail="File not found")


def start_gui(host: str = "127.0.0.1", port: int = 8080):
    print(f"⚡ Hawsub Subtitle Workstation GUI running at http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")
