// Trace Style: a small popup opened by clicking a trace row in the PANELS
// tree, so two traces of the same case that land in one panel (a
// displacement and a surface total, say -- both defaulting to the case's
// one color) can be told apart without hunting through the Style sidebar.
// Tabs match what a trace actually carries: Color, Line, Marker.
const TraceEditor = (() => {
  const HISTORY_KEY = 'flexflow.recentColors';
  const MAX_HISTORY = 16;

  function loadHistory() {
    try {
      const raw = localStorage.getItem(HISTORY_KEY);
      if (raw) return JSON.parse(raw);
    } catch (e) { /* private mode, cleared storage, etc. */ }
    return [];
  }

  function addToHistory(color) {
    const history = loadHistory().filter(c => c.toLowerCase() !== color.toLowerCase());
    history.unshift(color);
    try {
      localStorage.setItem(HISTORY_KEY, JSON.stringify(history.slice(0, MAX_HISTORY)));
    } catch (e) { /* ignore */ }
  }

  // Quick picks: the workspace's own rotating palette first -- the same
  // handful every time, so a color already used for one case is easy to
  // reuse for another -- then whatever else has actually been hand-picked,
  // most recent first.
  function swatchColors() {
    const seen = new Set();
    const combined = [];
    for (const c of [...PlotWorkspace.PALETTE, ...loadHistory()]) {
      const key = c.toLowerCase();
      if (seen.has(key)) continue;
      seen.add(key);
      combined.push(c);
    }
    return combined;
  }

  function sameColor(a, b) {
    return String(a || '').toLowerCase() === String(b || '').toLowerCase();
  }

  function escapeHtml(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function escapeAttr(s) {
    return String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;');
  }

  const TABS = [['color', 'Color'], ['line', 'Line'], ['marker', 'Marker']];
  let activeTab = 'color';

  function open(panelId, traceIndex) {
    const panel = PlotWorkspace.state().panels.find(p => p.id === panelId);
    if (!panel || !panel.traces[traceIndex]) return;
    activeTab = 'color';
    render(panel, traceIndex);
  }

  function tabBody(trace) {
    if (activeTab === 'line') {
      return `
        <label for="te-line">Line style</label>
        <select id="te-line">${StyleSidebar.options(StyleSidebar.LINE_STYLES, trace.lineStyle)}</select>
      `;
    }
    if (activeTab === 'marker') {
      return `
        <label for="te-marker">Marker</label>
        <select id="te-marker">${StyleSidebar.options(StyleSidebar.MARKERS, trace.marker)}</select>
      `;
    }
    const swatches = swatchColors().map(c => `
      <button type="button" class="color-swatch${sameColor(c, trace.color) ? ' active' : ''}"
              data-color="${escapeAttr(c)}" style="background:${escapeAttr(c)}" title="${escapeAttr(c)}"></button>
    `).join('');
    return `
      <label for="te-color">Color</label>
      <input type="color" id="te-color" value="${escapeAttr(trace.color || '#000000')}">
      <div class="color-swatches">${swatches}</div>
    `;
  }

  function render(panel, traceIndex) {
    const trace = panel.traces[traceIndex];
    Menu.openDialog(`
      <h2>Trace Style</h2>
      <div class="trace-editor-label">${escapeHtml(PanelTree.traceLabel(trace))}</div>
      <div class="trace-editor-tabs">
        ${TABS.map(([id, label]) => `
          <button type="button" class="trace-editor-tab${id === activeTab ? ' active' : ''}"
                  data-tab="${id}">${label}</button>
        `).join('')}
      </div>
      <div class="trace-editor-body">${tabBody(trace)}</div>
      <div class="btn-row"><button id="te-close" class="primary">Close</button></div>
    `);
    wire(panel, traceIndex);
  }

  // Applies immediately (no separate "Save") and re-renders the whole app --
  // a color/line/marker edit is cheap and PlotArea.render() already redraws
  // from scratch, so there is nothing gained by batching it behind a button.
  function apply(panel, traceIndex, patch) {
    PlotWorkspace.setTraceStyle(panel.id, traceIndex, patch);
    refreshWorkspace();
    render(panel, traceIndex);   // reflect the change in the still-open popup
  }

  function wire(panel, traceIndex) {
    document.getElementById('te-close').addEventListener('click', Menu.closeDialog);
    document.querySelectorAll('.trace-editor-tab').forEach(btn => {
      btn.addEventListener('click', () => {
        activeTab = btn.dataset.tab;
        render(panel, traceIndex);
      });
    });

    if (activeTab === 'color') {
      document.getElementById('te-color').addEventListener('change', (e) => {
        addToHistory(e.target.value);
        apply(panel, traceIndex, { color: e.target.value });
      });
      document.querySelectorAll('.color-swatch').forEach(el => {
        el.addEventListener('click', () => {
          addToHistory(el.dataset.color);
          apply(panel, traceIndex, { color: el.dataset.color });
        });
      });
    } else if (activeTab === 'line') {
      document.getElementById('te-line').addEventListener('change', (e) => {
        apply(panel, traceIndex, { lineStyle: e.target.value });
      });
    } else if (activeTab === 'marker') {
      document.getElementById('te-marker').addEventListener('change', (e) => {
        apply(panel, traceIndex, { marker: e.target.value });
      });
    }
  }

  return { open };
})();
