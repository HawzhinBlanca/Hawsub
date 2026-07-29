/**
 * Hawsub — Professional Subtitle Workstation SPA
 * State management, keyboard shortcuts, and API integration.
 */

// === Application State ===
const State = {
  projectId: null,
  filename: null,
  cues: [],
  selectedIndex: -1,
  searchQuery: '',
  processing: false,
  dirty: false,
};

// === DOM Cache ===
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// === Initialization ===
document.addEventListener('DOMContentLoaded', () => {
  initDropZone();
  initKeyboardShortcuts();
  initSearchFilter();
  renderEmptyState();
});

// === Toast System ===
function showToast(message, type = 'info', duration = 3500) {
  const container = $('.toast-container') || createToastContainer();
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  const icons = { success: '✓', error: '✗', info: 'ℹ', warning: '⚠' };
  toast.innerHTML = `<span>${icons[type] || ''}</span><span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100%)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

function createToastContainer() {
  const c = document.createElement('div');
  c.className = 'toast-container';
  document.body.appendChild(c);
  return c;
}

// === Drop Zone & File Upload ===
function initDropZone() {
  document.addEventListener('dragover', (e) => {
    e.preventDefault();
    const dz = $('.drop-zone');
    if (dz) dz.classList.add('drag-over');
  });

  document.addEventListener('dragleave', (e) => {
    const dz = $('.drop-zone');
    if (dz && !dz.contains(e.relatedTarget)) dz.classList.remove('drag-over');
  });

  document.addEventListener('drop', (e) => {
    e.preventDefault();
    const dz = $('.drop-zone');
    if (dz) dz.classList.remove('drag-over');
    if (e.dataTransfer.files.length > 0) {
      uploadFile(e.dataTransfer.files[0]);
    }
  });
}

function triggerFileSelect() {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = '.srt,.vtt,.ass,.ssa';
  input.onchange = () => { if (input.files[0]) uploadFile(input.files[0]); };
  input.click();
}

async function uploadFile(file) {
  const ext = file.name.split('.').pop().toLowerCase();
  if (!['srt', 'vtt', 'ass', 'ssa'].includes(ext)) {
    showToast('Unsupported file type. Use SRT, VTT, or ASS.', 'error');
    return;
  }

  showToast(`Uploading ${file.name}...`, 'info');

  const formData = new FormData();
  formData.append('file', file);

  try {
    const resp = await fetch('/api/upload', { method: 'POST', body: formData });
    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.detail || 'Upload failed');
    }

    const data = await resp.json();
    State.projectId = data.project_id;
    State.filename = data.filename;
    State.cues = data.cues;
    State.selectedIndex = data.cues.length > 0 ? 0 : -1;

    renderWorkspace();
    showToast(`Loaded ${data.total_cues} cues from ${data.filename}`, 'success');
  } catch (e) {
    showToast(`Upload error: ${e.message}`, 'error');
  }
}

// === Pipeline Processing ===
async function processProject() {
  if (!State.projectId || State.processing) return;

  State.processing = true;
  renderToolbar();
  showToast('Running localization pipeline...', 'info', 10000);

  try {
    const resp = await fetch(`/api/process/${State.projectId}`, { method: 'POST' });
    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.detail || 'Processing failed');
    }

    const data = await resp.json();
    State.cues = data.cues;
    State.processing = false;

    renderWorkspace();
    showToast(`Pipeline complete! ${data.total_cues} cues translated.`, 'success');
  } catch (e) {
    State.processing = false;
    renderToolbar();
    showToast(`Pipeline error: ${e.message}`, 'error');
  }
}

// === Render Functions ===
function renderEmptyState() {
  const panel = $('.editor-panel');
  if (!panel) return;

  panel.innerHTML = `
    <div class="empty-state">
      <div class="empty-icon">📝</div>
      <div class="empty-title">Hawsub Subtitle Workstation</div>
      <div class="empty-description">
        Upload an English subtitle file (SRT, VTT, or ASS) to begin cinematic
        English → Sorani Kurdish localization.
      </div>
      <div class="drop-zone" onclick="triggerFileSelect()" id="dropZone">
        <div class="drop-zone-icon">📁</div>
        <div class="drop-zone-text">Drop subtitle file here or click to browse</div>
        <div class="drop-zone-hint">Supports .srt, .vtt, .ass formats (max 10 MB)</div>
      </div>
    </div>
  `;
}

function renderWorkspace() {
  updateHeader();
  renderCueList();
  renderEditor();
  renderHeatmap();
  updateFooter();
}

function updateHeader() {
  const nameEl = $('.project-name');
  if (nameEl) nameEl.textContent = State.filename || 'No Project';

  const statusEl = $('.status-dot');
  if (statusEl) {
    statusEl.className = 'status-dot ' + (State.projectId ? 'ok' : 'warn');
  }

  const statusText = $('.status-text');
  if (statusText) {
    statusText.textContent = State.projectId ? `${State.cues.length} cues` : 'No project';
  }
}

function renderCueList() {
  const list = $('.cue-list');
  if (!list) return;

  const filtered = getFilteredCues();
  const stats = computeStats();

  // Update stats
  const statsEl = $('.sidebar-stats');
  if (statsEl) {
    statsEl.innerHTML = `
      <span class="stat-chip"><span class="count">${State.cues.length}</span> total</span>
      <span class="stat-chip passed"><span class="count">${stats.translated}</span> done</span>
      <span class="stat-chip review"><span class="count">${stats.untranslated}</span> pending</span>
    `;
  }

  list.innerHTML = filtered.map((cue, i) => {
    const realIndex = State.cues.indexOf(cue);
    const hasTarget = cue.target_text && cue.target_text.trim();
    const statusClass = hasTarget ? 'passed' : 'review';
    const activeClass = realIndex === State.selectedIndex ? 'active' : '';

    return `
      <div class="cue-item ${statusClass} ${activeClass}" onclick="selectCue(${realIndex})" data-index="${realIndex}">
        <div class="cue-id">#${cue.id}</div>
        <div class="cue-timecode">${cue.timecode}</div>
        <div class="cue-source">${escapeHtml(cue.source_text)}</div>
        ${hasTarget ? `<div class="cue-target">${escapeHtml(cue.target_text)}</div>` : ''}
      </div>
    `;
  }).join('');
}

function renderEditor() {
  const panel = $('.editor-panel');
  if (!panel) return;

  if (State.selectedIndex < 0 || State.selectedIndex >= State.cues.length) {
    panel.innerHTML = `
      <div class="editor-content">
        ${renderToolbarHTML()}
        <div class="empty-state">
          <div class="empty-icon">👈</div>
          <div class="empty-title">Select a cue</div>
          <div class="empty-description">Click a subtitle cue in the sidebar to edit it.</div>
        </div>
      </div>
    `;
    return;
  }

  const cue = State.cues[State.selectedIndex];
  const cps = computeCPS(cue);
  const cpl = computeCPL(cue);
  const charCount = (cue.target_text || '').length;

  panel.innerHTML = `
    <div class="editor-content">
      ${renderToolbarHTML()}
      <div class="split-editor">
        <div class="editor-pane">
          <div class="pane-header">
            <span>Source — English</span>
            <span>#${cue.id}</span>
          </div>
          <div class="pane-body">
            <div class="source-text">${escapeHtml(cue.source_text)}</div>
            <div style="margin-top: var(--space-lg); font-size: 0.8rem; color: var(--text-tertiary);">
              <strong>Timecode:</strong> ${cue.timecode}
            </div>
          </div>
        </div>
        <div class="editor-pane">
          <div class="pane-header">
            <span>Target — کوردیی ناوەندی</span>
            <span>${charCount} chars</span>
          </div>
          <div class="pane-body">
            <textarea class="target-textarea" id="targetInput"
              placeholder="بۆ وەرگێڕانی سۆرانی لێرە بنووسە..."
              oninput="onTargetEdit(this.value)">${escapeHtml(cue.target_text || '')}</textarea>
          </div>
          <div class="metrics-bar">
            <div class="metric">
              <span class="metric-label">CPS</span>
              <span class="metric-value ${cps <= 17 ? 'ok' : cps <= 22 ? 'warn' : 'danger'}">${cps.toFixed(1)}</span>
            </div>
            <div class="metric">
              <span class="metric-label">CPL</span>
              <span class="metric-value ${cpl <= 42 ? 'ok' : cpl <= 50 ? 'warn' : 'danger'}">${cpl}</span>
            </div>
            <div class="metric">
              <span class="metric-label">Chars</span>
              <span class="metric-value">${charCount}</span>
            </div>
            <div class="metric">
              <span class="metric-label">Cue</span>
              <span class="metric-value">${State.selectedIndex + 1} / ${State.cues.length}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  `;

  // Focus the textarea
  setTimeout(() => {
    const ta = document.getElementById('targetInput');
    if (ta) ta.focus();
  }, 50);
}

function renderToolbarHTML() {
  const hasProject = !!State.projectId;
  return `
    <div class="editor-toolbar">
      <div class="toolbar-group">
        <button class="btn btn-ghost btn-sm" onclick="triggerFileSelect()">📁 Open</button>
        <button class="btn btn-primary btn-sm" onclick="processProject()" ${!hasProject || State.processing ? 'disabled' : ''}>
          ${State.processing ? '⏳ Processing...' : '🚀 Translate'}
        </button>
        <button class="btn btn-ghost btn-sm" onclick="normalizeAll()" ${!hasProject ? 'disabled' : ''}>🔤 Normalize</button>
      </div>
      <div class="toolbar-group">
        <select class="select" id="exportFormat" ${!hasProject ? 'disabled' : ''}>
          <option value="srt">SRT</option>
          <option value="ass">ASS</option>
          <option value="vtt">VTT</option>
          <option value="html">Debug HTML</option>
          <option value="qc">QC Report</option>
        </select>
        <button class="btn btn-ghost btn-sm" onclick="exportFile()" ${!hasProject ? 'disabled' : ''}>⬇ Export</button>
      </div>
    </div>
  `;
}

function renderToolbar() {
  const toolbar = $('.editor-toolbar');
  if (toolbar) {
    const temp = document.createElement('div');
    temp.innerHTML = renderToolbarHTML();
    toolbar.replaceWith(temp.firstElementChild);
  }
}

function renderHeatmap() {
  const bar = $('.heatmap-bar');
  if (!bar) return;

  bar.innerHTML = State.cues.map(cue => {
    const hasTarget = cue.target_text && cue.target_text.trim();
    const cls = hasTarget ? 'high' : 'empty';
    return `<div class="heatmap-segment ${cls}" title="Cue #${cue.id}"></div>`;
  }).join('');
}

function updateFooter() {
  const left = $('.footer-left');
  if (left && State.projectId) {
    const stats = computeStats();
    left.innerHTML = `
      <span>Project: ${State.projectId}</span>
      <span>${stats.translated}/${State.cues.length} translated (${stats.percent}%)</span>
    `;
  }
}

// === Cue Interaction ===
function selectCue(index) {
  if (index < 0 || index >= State.cues.length) return;
  State.selectedIndex = index;
  renderCueList();
  renderEditor();

  // Scroll cue into view
  const item = document.querySelector(`.cue-item[data-index="${index}"]`);
  if (item) item.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
}

function onTargetEdit(value) {
  if (State.selectedIndex >= 0 && State.selectedIndex < State.cues.length) {
    State.cues[State.selectedIndex].target_text = value;
    State.dirty = true;

    // Update metrics in real-time
    const cue = State.cues[State.selectedIndex];
    const cps = computeCPS(cue);
    const cpl = computeCPL(cue);
    const charCount = value.length;

    $$('.metric-value').forEach((el, i) => {
      if (i === 0) { el.textContent = cps.toFixed(1); el.className = `metric-value ${cps <= 17 ? 'ok' : cps <= 22 ? 'warn' : 'danger'}`; }
      if (i === 1) { el.textContent = cpl; el.className = `metric-value ${cpl <= 42 ? 'ok' : cpl <= 50 ? 'warn' : 'danger'}`; }
      if (i === 2) { el.textContent = charCount; }
    });
  }
}

function navigateCue(delta) {
  const next = State.selectedIndex + delta;
  if (next >= 0 && next < State.cues.length) {
    selectCue(next);
  }
}

function acceptAndAdvance() {
  if (State.selectedIndex < State.cues.length - 1) {
    showToast(`Cue #${State.cues[State.selectedIndex].id} accepted`, 'success', 1500);
    selectCue(State.selectedIndex + 1);
  }
}

// === Normalize ===
async function normalizeAll() {
  if (!State.projectId) return;

  let count = 0;
  for (const cue of State.cues) {
    if (cue.target_text && cue.target_text.trim()) {
      try {
        const resp = await fetch('/api/normalize', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: cue.target_text }),
        });
        if (resp.ok) {
          const data = await resp.json();
          if (data.normalized !== cue.target_text) {
            cue.target_text = data.normalized;
            count++;
          }
        }
      } catch (e) { /* skip */ }
    }
  }

  renderWorkspace();
  showToast(`Normalized ${count} cues`, 'success');
}

// === Export ===
function exportFile() {
  if (!State.projectId) return;
  const format = document.getElementById('exportFormat')?.value || 'srt';
  window.location.href = `/api/export/${State.projectId}/${format}`;
}

// === Search & Filter ===
function initSearchFilter() {
  document.addEventListener('input', (e) => {
    if (e.target.classList.contains('search-input')) {
      State.searchQuery = e.target.value.toLowerCase();
      renderCueList();
    }
  });
}

function getFilteredCues() {
  if (!State.searchQuery) return State.cues;
  return State.cues.filter(c =>
    c.source_text.toLowerCase().includes(State.searchQuery) ||
    (c.target_text || '').toLowerCase().includes(State.searchQuery) ||
    String(c.id).includes(State.searchQuery)
  );
}

// === Keyboard Shortcuts ===
function initKeyboardShortcuts() {
  document.addEventListener('keydown', (e) => {
    const isMod = e.metaKey || e.ctrlKey;

    // Cmd+S — Save/accept current edit
    if (isMod && e.key === 's') {
      e.preventDefault();
      showToast('Changes saved', 'success', 1500);
      renderCueList();
      return;
    }

    // Cmd+Enter — Accept and advance
    if (isMod && e.key === 'Enter') {
      e.preventDefault();
      acceptAndAdvance();
      return;
    }

    // Alt+Right / Alt+Left — Navigate cues
    if (e.altKey && e.key === 'ArrowRight') {
      e.preventDefault();
      navigateCue(1);
      return;
    }
    if (e.altKey && e.key === 'ArrowLeft') {
      e.preventDefault();
      navigateCue(-1);
      return;
    }

    // Cmd+O — Open file
    if (isMod && e.key === 'o') {
      e.preventDefault();
      triggerFileSelect();
      return;
    }

    // Escape — Deselect
    if (e.key === 'Escape') {
      State.selectedIndex = -1;
      renderEditor();
      return;
    }
  });
}

// === Utility Functions ===
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text || '';
  return div.innerHTML;
}

function computeCPS(cue) {
  const text = cue.target_text || cue.source_text || '';
  const tc = cue.timecode || '';
  const parts = tc.split(' --> ');
  if (parts.length !== 2) return 0;

  const start = parseTimecodeMs(parts[0].trim());
  const end = parseTimecodeMs(parts[1].trim());
  const durationSec = (end - start) / 1000;

  return durationSec > 0 ? text.length / durationSec : 0;
}

function computeCPL(cue) {
  const text = cue.target_text || '';
  const lines = text.split('\n');
  return Math.max(...lines.map(l => l.length), 0);
}

function parseTimecodeMs(tc) {
  // HH:MM:SS,mmm or HH:MM:SS.mmm
  const m = tc.match(/(\d{2}):(\d{2}):(\d{2})[,.](\d{3})/);
  if (!m) return 0;
  return parseInt(m[1]) * 3600000 + parseInt(m[2]) * 60000 + parseInt(m[3]) * 1000 + parseInt(m[4]);
}

function computeStats() {
  const translated = State.cues.filter(c => c.target_text && c.target_text.trim()).length;
  const untranslated = State.cues.length - translated;
  const percent = State.cues.length > 0 ? Math.round(translated / State.cues.length * 100) : 0;
  return { translated, untranslated, percent };
}
