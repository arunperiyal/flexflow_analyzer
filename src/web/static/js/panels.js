// Workspace state (panels, traces, x-axis link groups) in localStorage,
// and the sidebar panel tree that renders it (§5 of the plan). The server
// holds no per-session state -- this is the whole of it.
const PlotWorkspace = (() => {
  const STORAGE_KEY = 'flexflow.workspace';
  const COLORS = ['#dc2626', '#f59e0b', '#7c3aed', '#059669', '#2563eb', '#db2777', '#0891b2', '#65a30d'];

  // Global style defaults: unset numeric/text fields (null/'') mean "let
  // Plotly pick", so an old saved workspace with no `style` block at all
  // renders exactly as it did before this existed.
  function defaultGlobalStyle() {
    return {
      fontFamily: '', labelFontSize: null, legendFontSize: null, tickFontSize: null,
      title: '', showLegend: false, legendPosition: 'top-right', showGrid: true,
      markerSize: null, markerStep: null, lineWidth: null, latex: false,
      showPanelBorder: false, ticksInside: false,
      marginTop: null, marginRight: null, marginBottom: null, marginLeft: null,
    };
  }

  // width/height: the figure's fixed canvas size, in inches -- set by
  // Layout -> New/Edit. Every pane is positioned/sized independently within
  // this canvas (see defaultPane) rather than being a cell of a shared grid.
  function defaultLayout() {
    return { width: 6.5, height: 4.5 };
  }

  // An unset panel.pane (never touched in Layout -> Panes) fills the whole
  // canvas -- the sane starting point for a freshly added panel, which the
  // user then repositions/resizes explicitly.
  function defaultPane(layout) {
    return { x: 0, y: 0, w: layout.width, h: layout.height };
  }

  function isFreeformPane(p) {
    return !!p && typeof p.x === 'number' && typeof p.y === 'number'
      && typeof p.w === 'number' && typeof p.h === 'number';
  }

  // A layout tab is its own independent workspace: panels/traces, the
  // canvas, and global style all belong to exactly one tab -- switching
  // tabs swaps the whole set. `raw` may be a bare, pre-tabs workspace
  // object (id/name absent) or an already-tabbed entry that predates a
  // later field -- either way, every field ends up backfilled the same way
  // the old single-workspace `load()` did it. A saved workspace from before
  // free-form panes (grid rows/columns, width/height in px) has no sane
  // geometric mapping onto inches, so it is reset to fresh defaults rather
  // than misread as inches -- detected by the old `rows`/`columns` fields,
  // which the new shape never has.
  function normalizeLayoutEntry(raw, fallbackId, fallbackName) {
    const panels = raw.panels || [];
    const oldLayout = raw.layout || {};
    const isLegacyGrid = 'rows' in oldLayout || 'columns' in oldLayout;
    const layout = {
      width: (!isLegacyGrid && typeof oldLayout.width === 'number') ? oldLayout.width : defaultLayout().width,
      height: (!isLegacyGrid && typeof oldLayout.height === 'number') ? oldLayout.height : defaultLayout().height,
    };
    for (const p of panels) {
      p.style = p.style || {};
      if (!isFreeformPane(p.pane)) p.pane = defaultPane(layout);
    }
    // A workspace saved before case styles existed still gets one: the
    // first trace already plotted for each case becomes that case's
    // registered style, so nothing visually changes on load, but every
    // later trace of that case (and any edit made here) now follows it.
    const caseStyles = { ...(raw.caseStyles || {}) };
    for (const p of panels) {
      for (const t of p.traces) {
        if (t.case && !caseStyles[t.case]) {
          caseStyles[t.case] = { color: t.color || null, lineStyle: t.lineStyle || '', marker: t.marker || '' };
        }
      }
    }
    return {
      id: raw.id || fallbackId,
      name: raw.name || fallbackName,
      panels,
      layout,
      style: { ...defaultGlobalStyle(), ...(raw.style || {}) },
      activePanelId: raw.activePanelId || null,
      caseStyles,
    };
  }

  function defaultLayoutEntry(id, name, canvasSpec) {
    return {
      id, name, panels: [],
      layout: { ...defaultLayout(), ...(canvasSpec || {}) },
      style: defaultGlobalStyle(), activePanelId: null, caseStyles: {},
    };
  }

  function load() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed.layouts) && parsed.layouts.length) {
          const layouts = parsed.layouts.map((l, i) => normalizeLayoutEntry(l, `l${i + 1}`, `Layout ${i + 1}`));
          const activeLayoutId = layouts.some(l => l.id === parsed.activeLayoutId)
            ? parsed.activeLayoutId : layouts[0].id;
          return { activeLayoutId, layouts };
        }
        // Pre-tabs workspace: the whole saved object WAS one layout.
        return { activeLayoutId: 'l1', layouts: [normalizeLayoutEntry(parsed, 'l1', 'Layout 1')] };
      }
    } catch (e) { /* private mode, cleared storage, etc. */ }
    return { activeLayoutId: 'l1', layouts: [defaultLayoutEntry('l1', 'Layout 1')] };
  }

  let ws = load();

  function active() {
    return ws.layouts.find(l => l.id === ws.activeLayoutId) || ws.layouts[0];
  }

  let nextPanelId = 1 + ws.layouts.flatMap(l => l.panels).reduce((max, p) => {
    const n = parseInt((p.id || '').replace('p', ''), 10);
    return isNaN(n) ? max : Math.max(max, n);
  }, 0);
  let nextLayoutId = 1 + ws.layouts.reduce((max, l) => {
    const n = parseInt((l.id || '').replace('l', ''), 10);
    return isNaN(n) ? max : Math.max(max, n);
  }, 0);
  let colorIdx = 0;

  function save() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(ws)); } catch (e) { /* ignore */ }
  }

  function nextColor() {
    const c = COLORS[colorIdx % COLORS.length];
    colorIdx += 1;
    return c;
  }

  // A case's color/line-style/marker, registered the first time any trace
  // of it is added to this layout (auto-assigning a color the same way a
  // trace always has) so every later trace of the same case -- in any
  // panel -- starts out looking consistent rather than getting its own
  // independently rotated color. Still just a *default*: two traces of the
  // same case landing in one panel (a displacement and a surface total,
  // say) look identical until told apart, which is exactly what
  // TraceEditor (opened from a trace row in the PANELS tree) is for.
  function caseStyleFor(caseName) {
    const L = active();
    L.caseStyles = L.caseStyles || {};
    if (!L.caseStyles[caseName]) {
      L.caseStyles[caseName] = { color: nextColor(), lineStyle: '', marker: '' };
    }
    return L.caseStyles[caseName];
  }

  // Routing default (§5): a panel already holding this case's traces gets the
  // new ones too (several rows, one case -> shared panel); otherwise a new
  // panel is made, which is what keeps two cases from landing on one panel
  // by accident. Overridable per row (targetPanelId in addTraces) --
  // deliberately overlaying two cases is a choice, not a default. A new
  // panel's pane is left unset (fills the canvas -- see defaultPane) until
  // arranged via Layout -> Panes.
  function panelFor(caseName) {
    // Excludes spatial, surface and fft panels: they share the "same case ->
    // same panel" instinct, but none of them shares an x-axis (spatial:
    // position; fft: frequency) or a sane shared y-scale (surface, usually a
    // wildly different physical quantity from a nodal trace -- totArea next
    // to a displacement) with a plain time trace, so auto-routing must not
    // merge them just because the case matches.
    const L = active();
    let panel = L.panels.find(p => p.kind !== 'spatial' && p.kind !== 'surface' && p.kind !== 'fft'
                                   && p.traces.some(t => t.case === caseName));
    if (!panel) {
      panel = { id: `p${nextPanelId++}`, title: caseName, traces: [], style: {}, pane: null };
      L.panels.push(panel);
    }
    return panel;
  }

  // targetPanelId: omit/falsy for the routing default above; '__new__' to
  // force a fresh panel even if one already holds this case; an existing
  // panel id to overlay onto it regardless of which case(s) it already holds.
  function addTraces(caseName, group, rows, nodeOf, column, targetPanelId) {
    const L = active();
    let panel;
    if (targetPanelId === '__new__') {
      panel = { id: `p${nextPanelId++}`, title: caseName, traces: [], style: {}, pane: null };
      L.panels.push(panel);
    } else if (targetPanelId) {
      panel = L.panels.find(p => p.id === targetPanelId);
    }
    if (!panel) panel = panelFor(caseName);

    const cs = caseStyleFor(caseName);
    for (const row of rows) {
      const already = panel.traces.some(
        t => t.case === caseName && t.group === group && t.row === row && t.col === column
      );
      if (already) continue;
      panel.traces.push({ case: caseName, group, row, node: nodeOf ? nodeOf(row) : null,
                          col: column, color: cs.color, lineStyle: cs.lineStyle, marker: cs.marker });
    }
    if (!L.activePanelId) L.activePanelId = panel.id;
    save();
  }

  // Spatial traces plot one number per node against its position along the
  // probe -- the opposite axis choice from addTraces, which plots one
  // node's value against time. A trace here holds every selected node as
  // `points` ([{row, x, node}], sorted by x so a connecting line reads
  // sensibly) rather than being one node's own trace, since the whole
  // point is comparing across nodes. `x` is captured once at add-time from
  // the picker's own projection -- a property of the map, not of history,
  // so there is nothing to refetch later.
  function panelForSpatial(caseName) {
    const L = active();
    let panel = L.panels.find(p => p.kind === 'spatial' && p.traces.some(t => t.case === caseName));
    if (!panel) {
      panel = { id: `p${nextPanelId++}`, title: `${caseName} (spatial)`, kind: 'spatial', traces: [], style: {}, pane: null };
      L.panels.push(panel);
    }
    return panel;
  }

  function addSpatialTrace(caseName, group, points, column, mode, opts, targetPanelId) {
    const L = active();
    let panel;
    if (targetPanelId === '__new__') {
      panel = { id: `p${nextPanelId++}`, title: `${caseName} (spatial)`, kind: 'spatial', traces: [], style: {}, pane: null };
      L.panels.push(panel);
    } else if (targetPanelId) {
      panel = L.panels.find(p => p.id === targetPanelId);
    }
    if (!panel) panel = panelForSpatial(caseName);

    const cs = caseStyleFor(caseName);
    panel.traces.push({
      case: caseName, group, col: column, mode,
      time: opts.time, stat: opts.stat, t1: opts.t1, t2: opts.t2, axLabel: opts.axLabel,
      points: [...points].sort((a, b) => a.x - b.x),
      color: cs.color, lineStyle: cs.lineStyle, marker: cs.marker,
    });
    if (!L.activePanelId) L.activePanelId = panel.id;
    save();
    return panel;
  }

  // A surface trace is still a plain time-vs-value line -- same x-axis
  // (time), same fetch shape (/history with row always 0) as a nodal trace.
  // It gets its own panel kind purely so auto-routing keeps it separate from
  // a case's nodal traces (see panelFor's own comment): overlaying a nodal
  // displacement with a surface's totArea by accident would share a y-axis
  // between two unrelated physical quantities. Still overlayable onto any
  // panel deliberately, via targetPanelId, same as addTraces.
  function panelForSurface(caseName) {
    const L = active();
    let panel = L.panels.find(p => p.kind === 'surface' && p.traces.some(t => t.case === caseName));
    if (!panel) {
      panel = { id: `p${nextPanelId++}`, title: `${caseName} (surface)`, kind: 'surface', traces: [], style: {}, pane: null };
      L.panels.push(panel);
    }
    return panel;
  }

  function addSurfaceTrace(caseName, group, block, column, targetPanelId) {
    const L = active();
    let panel;
    if (targetPanelId === '__new__') {
      panel = { id: `p${nextPanelId++}`, title: `${caseName} (surface)`, kind: 'surface', traces: [], style: {}, pane: null };
      L.panels.push(panel);
    } else if (targetPanelId) {
      panel = L.panels.find(p => p.id === targetPanelId);
    }
    if (!panel) panel = panelForSurface(caseName);

    const cs = caseStyleFor(caseName);
    const already = panel.traces.some(
      t => t.case === caseName && t.group === group && t.col === column && t.source === 'oisd'
    );
    if (!already) {
      panel.traces.push({ case: caseName, group, row: 0, block, col: column, source: 'oisd',
                          color: cs.color, lineStyle: cs.lineStyle, marker: cs.marker });
    }
    if (!L.activePanelId) L.activePanelId = panel.id;
    save();
    return panel;
  }

  // An FFT trace names the same (case, group, row, column, source) as a
  // plain time trace -- its spectrum is computed from that same signal,
  // server-side, fresh at every render (see plot.js's fetchFFT), not baked
  // in at add time the way a spatial trace's own reduction is. `kind: 'fft'`
  // marks the trace itself (not just its panel), since autoLabel needs to
  // tell an FFT of a signal apart from the signal's own time trace even
  // when both are, in principle, overlaid onto one panel by hand. Its own
  // panel kind (mirroring surface's own reasoning) keeps a spectrum
  // (frequency on x) from landing on a time trace's panel (time on x) by
  // accident -- the two axes mean completely different things.
  function panelForFFT(caseName) {
    const L = active();
    let panel = L.panels.find(p => p.kind === 'fft' && p.traces.some(t => t.case === caseName));
    if (!panel) {
      panel = { id: `p${nextPanelId++}`, title: `${caseName} (FFT)`, kind: 'fft', traces: [], style: {}, pane: null };
      L.panels.push(panel);
    }
    return panel;
  }

  // opts: { t1, t2 } -- an optional time window the spectrum is computed
  // over (both ends open, unset means the whole series), same shape as
  // addSpatialTrace's own opts. Folded into the dedup check below since two
  // FFT traces of the same signal windowed differently are legitimately
  // different traces (an early transient next to the steady state, say),
  // not a re-add of the same one.
  function addFFTTrace(caseName, group, rows, nodeOf, column, source, block, opts, targetPanelId) {
    const L = active();
    let panel;
    if (targetPanelId === '__new__') {
      panel = { id: `p${nextPanelId++}`, title: `${caseName} (FFT)`, kind: 'fft', traces: [], style: {}, pane: null };
      L.panels.push(panel);
    } else if (targetPanelId) {
      panel = L.panels.find(p => p.id === targetPanelId);
    }
    if (!panel) panel = panelForFFT(caseName);

    const cs = caseStyleFor(caseName);
    const t1 = (opts && opts.t1 != null) ? opts.t1 : null;
    const t2 = (opts && opts.t2 != null) ? opts.t2 : null;
    for (const row of rows) {
      const already = panel.traces.some(t => t.case === caseName && t.group === group && t.row === row
                                        && t.col === column && (t.source || 'othd') === (source || 'othd')
                                        && (t.t1 ?? null) === t1 && (t.t2 ?? null) === t2);
      if (already) continue;
      const trace = { case: caseName, group, row, node: nodeOf ? nodeOf(row) : null,
                      col: column, source: source || 'othd', kind: 'fft',
                      color: cs.color, lineStyle: cs.lineStyle, marker: cs.marker };
      if (block) trace.block = block;
      if (t1 != null) trace.t1 = t1;
      if (t2 != null) trace.t2 = t2;
      panel.traces.push(trace);
    }
    if (!L.activePanelId) L.activePanelId = panel.id;
    save();
  }

  // A Field -> Render panel: a static PNG (pyvista, rendered server-side and
  // saved to a persistent cache -- see api/field.py's field_render_save),
  // not a data recipe like every other panel kind here. No targetPanelId:
  // there's no sensible "overlay" for two images the way traces overlay on
  // a chart, so this always creates a fresh panel. `traces: []` (not
  // omitted) keeps it working with every bit of generic panel machinery
  // that assumes the field exists (PanelTree.render, normalizeLayoutEntry).
  function addRenderPanel(caseName, title, imageToken) {
    const L = active();
    const panel = { id: `p${nextPanelId++}`, title, kind: 'render',
                    case: caseName, imageToken, traces: [], style: {}, pane: null };
    L.panels.push(panel);
    if (!L.activePanelId) L.activePanelId = panel.id;
    save();
    return panel;
  }

  function removeTrace(panelId, index) {
    const L = active();
    const panel = L.panels.find(p => p.id === panelId);
    if (!panel) return;
    panel.traces.splice(index, 1);
    if (!panel.traces.length) {
      L.panels = L.panels.filter(p => p.id !== panelId);
      if (L.activePanelId === panelId) {
        L.activePanelId = L.panels.length ? L.panels[0].id : null;
      }
    }
    save();
  }

  function removePanel(panelId) {
    const L = active();
    L.panels = L.panels.filter(p => p.id !== panelId);
    if (L.activePanelId === panelId) {
      L.activePanelId = L.panels.length ? L.panels[0].id : null;
    }
    save();
  }

  function clearPanel(panelId) {
    const panel = active().panels.find(p => p.id === panelId);
    if (!panel) return;
    panel.traces = [];
    save();
  }

  function renamePanel(panelId, title) {
    const panel = active().panels.find(p => p.id === panelId);
    if (!panel) return;
    panel.title = title;
    save();
  }

  function setPanelStyle(panelId, patch) {
    const panel = active().panels.find(p => p.id === panelId);
    if (!panel) return;
    panel.style = { ...(panel.style || {}), ...patch };
    save();
  }

  // The panel-tree's quick "lock" toggle is a shortcut for the style
  // sidebar's own Y limits field -- both read/write panel.style.ylim, so
  // locking from the tree and typing exact numbers in the sidebar agree.
  function setYLock(panelId, range) {
    setPanelStyle(panelId, { ylim: range });   // range: [min, max], or null to unlock
  }

  function setGlobalStyle(patch) {
    const L = active();
    L.style = { ...L.style, ...patch };
    save();
  }

  // Per-trace overrides (color, line style, marker) -- distinct from panel
  // style since these describe one line, not the axes it is drawn on.
  function setTraceStyle(panelId, traceIndex, patch) {
    const panel = active().panels.find(p => p.id === panelId);
    if (!panel || !panel.traces[traceIndex]) return;
    panel.traces[traceIndex] = { ...panel.traces[traceIndex], ...patch };
    save();
  }

  function setActivePanel(id) {
    active().activePanelId = id;
    save();
  }

  // Layout -> Edit: resizes the active layout's canvas (inches) in place.
  // Panes are left exactly as they are -- unlike the old grid, there is no
  // "no longer fits" case to fall back from, since a pane's x/y/w/h is
  // never relative to the canvas size.
  function updateLayout(patch) {
    const L = active();
    L.layout = { ...L.layout, ...patch };
    save();
  }

  // Layout -> Panes: patches one panel's pane (x/y/w/h, inches), merging
  // onto its current one (or the fill-the-canvas default if never set) so
  // a caller can pass just the one field that changed.
  function setPanelPane(panelId, patch) {
    const L = active();
    const panel = L.panels.find(p => p.id === panelId);
    if (!panel) return;
    const current = isFreeformPane(panel.pane) ? panel.pane : defaultPane(L.layout);
    panel.pane = { ...current, ...patch };
    save();
  }

  function state() { return active(); }

  // -- Layout tabs -----------------------------------------------------
  // Each entry is its own independent workspace (panels, grid, style) --
  // see normalizeLayoutEntry above.

  function listLayouts() {
    return ws.layouts.map(l => ({ id: l.id, name: l.name }));
  }

  function activeLayoutId() {
    return ws.activeLayoutId;
  }

  function setActiveLayout(id) {
    if (!ws.layouts.some(l => l.id === id)) return;
    ws.activeLayoutId = id;
    save();
  }

  // Layout -> New (also the tab strip's "+"): a brand new, empty layout
  // tab with the chosen canvas size -- unlike the old single-workspace
  // "New", there are no existing panels to reset since nothing here existed yet.
  function createLayout(spec) {
    const id = `l${nextLayoutId++}`;
    const name = `Layout ${ws.layouts.length + 1}`;
    const entry = defaultLayoutEntry(id, name, spec);
    ws.layouts.push(entry);
    ws.activeLayoutId = id;
    save();
    return id;
  }

  function renameLayout(id, name) {
    const entry = ws.layouts.find(l => l.id === id);
    if (!entry) return;
    entry.name = (name || '').trim() || entry.name;
    save();
  }

  // Always keeps at least one layout -- there is no sane "no layout"
  // empty state for the rest of the app to fall back to.
  function deleteLayout(id) {
    if (ws.layouts.length <= 1) return;
    const idx = ws.layouts.findIndex(l => l.id === id);
    if (idx === -1) return;
    ws.layouts.splice(idx, 1);
    if (ws.activeLayoutId === id) {
      ws.activeLayoutId = ws.layouts[Math.min(idx, ws.layouts.length - 1)].id;
    }
    save();
  }

  return {
    state, addTraces, addSpatialTrace, addSurfaceTrace, addFFTTrace, addRenderPanel,
    removeTrace, removePanel, clearPanel, renamePanel,
    setYLock, updateLayout, setPanelPane, setPanelStyle, setGlobalStyle,
    setActivePanel, setTraceStyle,
    listLayouts, activeLayoutId, setActiveLayout, createLayout, renameLayout, deleteLayout,
    PALETTE: COLORS,
  };
})();

const PanelTree = (() => {
  function render() {
    const ws = PlotWorkspace.state();
    const container = document.getElementById('panel-tree');
    container.innerHTML = '';

    if (!ws.panels.length) {
      container.innerHTML = '<div class="empty">Plot &rarr; New arrives here</div>';
      return;
    }

    for (const panel of ws.panels) {
      const node = document.createElement('div');
      node.className = 'panel-node' + (panel.id === ws.activePanelId ? ' active-for-style' : '');

      const header = document.createElement('div');
      header.className = 'panel-node-header';

      const title = document.createElement('span');
      title.className = 'panel-title';
      title.textContent = panel.title;
      title.title = 'Click to select for Style -- double-click to rename';
      title.addEventListener('click', () => { PlotWorkspace.setActivePanel(panel.id); refreshWorkspace(); });
      title.addEventListener('dblclick', () => startRename(header, title, panel));

      const kindTag = document.createElement('span');
      kindTag.className = 'panel-kind-tag';
      kindTag.textContent = panel.kind === 'spatial' ? 'spatial' : panel.kind === 'render' ? 'render' : '';

      const yLim = panel.style && panel.style.ylim;
      const lock = document.createElement('span');
      lock.className = 'panel-lock' + (yLim ? ' active' : '');
      lock.textContent = yLim ? 'locked' : 'lock';
      lock.title = yLim
        ? 'Y-axis locked to its range when locked -- click to unlock'
        : 'Lock the y-axis to its current range';
      lock.addEventListener('click', () => {
        if (yLim) {
          PlotWorkspace.setYLock(panel.id, null);
          refreshWorkspace();
        } else {
          const range = PlotArea.currentYRange(panel.id, !!(panel.style && panel.style.swapAxes));
          PlotWorkspace.setYLock(panel.id, range);
          refreshWorkspace();
        }
      });

      const close = document.createElement('span');
      close.className = 'panel-remove';
      close.textContent = '×';
      close.title = 'Remove panel';
      close.addEventListener('click', () => { PlotWorkspace.removePanel(panel.id); refreshWorkspace(); });

      header.appendChild(title);
      if (kindTag.textContent) header.appendChild(kindTag);
      header.appendChild(lock);
      header.appendChild(close);
      node.appendChild(header);

      panel.traces.forEach((t, idx) => {
        const row = document.createElement('div');
        row.className = 'trace-row';
        const swatch = document.createElement('span');
        swatch.className = 'trace-swatch';
        swatch.style.background = t.color;
        const label = document.createElement('span');
        label.className = 'trace-label';
        label.textContent = traceLabel(t);
        // Swatch + label open the style editor; the remove "x" stays its own
        // target so deleting a trace never also opens the editor for the row
        // that takes its place.
        const openEditor = () => TraceEditor.open(panel.id, idx);
        swatch.addEventListener('click', openEditor);
        label.addEventListener('click', openEditor);
        row.appendChild(swatch);
        row.appendChild(label);
        if (t.secondaryAxis) {
          const axisTag = document.createElement('span');
          axisTag.className = 'trace-axis-tag';
          axisTag.textContent = 'Y2';
          axisTag.title = 'Plotted on the secondary y-axis';
          row.appendChild(axisTag);
        }
        const del = document.createElement('span');
        del.className = 'trace-remove';
        del.textContent = '×';
        del.title = 'Remove trace';
        del.addEventListener('click', () => { PlotWorkspace.removeTrace(panel.id, idx); refreshWorkspace(); });
        row.appendChild(del);
        node.appendChild(row);
      });

      container.appendChild(node);
    }
  }

  function traceLabel(t) {
    if (t.points) {
      const n = t.points.length;
      const range = t.t1 == null && t.t2 == null ? '' : ` [${t.t1 ?? 'start'}, ${t.t2 ?? 'end'}]`;
      const what = t.mode === 'snapshot' ? `@t=${t.time}` : `${t.stat}${range}`;
      return `${t.case} ${t.col} ${what} (${n} node${n === 1 ? '' : 's'})`;
    }
    const base = `${t.case} r${t.row} ${t.col}`;   // time trace
    if (t.kind !== 'fft') return base;
    const range = t.t1 == null && t.t2 == null ? '' : ` [${t.t1 ?? 'start'}, ${t.t2 ?? 'end'}]`;
    return `${base} FFT${range}`;
  }

  function startRename(header, titleEl, panel) {
    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'panel-title-edit';
    input.value = panel.title;
    header.replaceChild(input, titleEl);
    input.focus();
    input.select();

    const commit = () => {
      const value = input.value.trim() || panel.title;
      PlotWorkspace.renamePanel(panel.id, value);
      refreshWorkspace();
    };
    input.addEventListener('blur', commit);
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') input.blur();
      if (e.key === 'Escape') { input.value = panel.title; input.blur(); }
    });
  }

  return { render, traceLabel };
})();

function refreshWorkspace() {
  Layout.renderTabs();
  PanelTree.render();
  PlotArea.render();
  StyleSidebar.render();
}
