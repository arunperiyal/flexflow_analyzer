// Workspace state (panels, traces, linkX) in localStorage, and the sidebar
// panel tree that renders it (§5 of the plan). The server holds no
// per-session state -- this is the whole of it.
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
      markerSize: null, markerStep: null, latex: false,
      showPanelBorder: false, panelGapPct: null,
      marginTop: null, marginRight: null, marginBottom: null, marginLeft: null,
    };
  }

  // width/height: null means "auto" (Plotly's own responsive sizing) -- set
  // by Layout -> New/Edit, not required to have a value. areas: merged
  // (span > 1x1) regions only -- every other cell is an implicit 1x1 area
  // (see PlotArea.gridSlots).
  function defaultLayout() {
    return { rows: 1, columns: 1, width: null, height: null, areas: [] };
  }

  // A layout tab is its own independent workspace: panels/traces, the
  // grid, global style, and Link X-axes all belong to exactly one tab --
  // switching tabs swaps the whole set. `raw` may be a bare, pre-tabs
  // workspace object (id/name absent) or an already-tabbed entry that
  // predates a later field -- either way, every field ends up backfilled
  // the same way the old single-workspace `load()` did it.
  function normalizeLayoutEntry(raw, fallbackId, fallbackName) {
    const panels = raw.panels || [];
    const oldLayout = raw.layout || {};
    const layout = {
      ...defaultLayout(),
      columns: oldLayout.columns || 1,
      rows: oldLayout.rows || Math.max(1, Math.ceil(panels.length / (oldLayout.columns || 1))),
      width: oldLayout.width ?? null,
      height: oldLayout.height ?? null,
      areas: Array.isArray(oldLayout.areas) ? oldLayout.areas : [],
    };
    for (const p of panels) {
      p.style = p.style || {};
      if (!('pane' in p)) p.pane = null;
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
      linkX: raw.linkX !== undefined ? raw.linkX : true,
      panels,
      layout,
      style: { ...defaultGlobalStyle(), ...(raw.style || {}) },
      activePanelId: raw.activePanelId || null,
      caseStyles,
    };
  }

  function defaultLayoutEntry(id, name, gridSpec) {
    return {
      id, name, linkX: true, panels: [],
      layout: { ...defaultLayout(), ...(gridSpec || {}) },
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
  // independently rotated color. Still just a *default*: a trace can be
  // styled away from it afterward via the per-trace controls, same as
  // always -- see setCaseStyle for how a later case-style edit respects that.
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
  // deliberately overlaying two cases is a choice, not a default.
  function panelFor(caseName, pane) {
    // Excludes spatial panels: they share the "same case -> same panel"
    // instinct, but a time trace and a spatial trace can never share an
    // x-axis, so auto-routing must not merge them just because the case matches.
    const L = active();
    let panel = L.panels.find(p => p.kind !== 'spatial' && p.traces.some(t => t.case === caseName));
    if (!panel) {
      panel = { id: `p${nextPanelId++}`, title: caseName, traces: [], style: {}, pane: pane ?? null };
      L.panels.push(panel);
    }
    return panel;
  }

  // targetPanelId: omit/falsy for the routing default above; '__new__' to
  // force a fresh panel even if one already holds this case; an existing
  // panel id to overlay onto it regardless of which case(s) it already holds.
  // pane ({row, col}): where a *newly created* panel should sit in the
  // grid; ignored when overlaying onto an existing panel, which already
  // has one.
  function addTraces(caseName, group, rows, nodeOf, column, targetPanelId, pane) {
    const L = active();
    let panel;
    if (targetPanelId === '__new__') {
      panel = { id: `p${nextPanelId++}`, title: caseName, traces: [], style: {}, pane: pane ?? null };
      L.panels.push(panel);
    } else if (targetPanelId) {
      panel = L.panels.find(p => p.id === targetPanelId);
    }
    if (!panel) panel = panelFor(caseName, pane);

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
  function panelForSpatial(caseName, pane) {
    const L = active();
    let panel = L.panels.find(p => p.kind === 'spatial' && p.traces.some(t => t.case === caseName));
    if (!panel) {
      panel = { id: `p${nextPanelId++}`, title: `${caseName} (spatial)`, kind: 'spatial', traces: [], style: {}, pane: pane ?? null };
      L.panels.push(panel);
    }
    return panel;
  }

  function addSpatialTrace(caseName, group, points, column, mode, opts, targetPanelId, pane) {
    const L = active();
    let panel;
    if (targetPanelId === '__new__') {
      panel = { id: `p${nextPanelId++}`, title: `${caseName} (spatial)`, kind: 'spatial', traces: [], style: {}, pane: pane ?? null };
      L.panels.push(panel);
    } else if (targetPanelId) {
      panel = L.panels.find(p => p.id === targetPanelId);
    }
    if (!panel) panel = panelForSpatial(caseName, pane);

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

  // Case -> Style: sets the case's default color/line-style/marker and
  // reapplies it to every trace of that case (any panel) that is still at
  // the case's *previous* default -- a trace deliberately styled away from
  // it (e.g. distinguishing several nodes of one case overlaid in a single
  // panel, via the per-trace controls) is left alone rather than being
  // silently snapped back on the next case-style edit.
  function setCaseStyle(caseName, patch) {
    const L = active();
    L.caseStyles = L.caseStyles || {};
    const prev = L.caseStyles[caseName] || { color: null, lineStyle: '', marker: '' };
    const next = { ...prev, ...patch };
    L.caseStyles[caseName] = next;

    for (const panel of L.panels) {
      for (const t of panel.traces) {
        if (t.case !== caseName) continue;
        if ('color' in patch && t.color === prev.color) t.color = next.color;
        if ('lineStyle' in patch && (t.lineStyle || '') === (prev.lineStyle || '')) t.lineStyle = next.lineStyle;
        if ('marker' in patch && (t.marker || '') === (prev.marker || '')) t.marker = next.marker;
      }
    }
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

  // Layout -> Edit: resizes the active layout's grid in place. A panel's
  // existing pane is left alone -- if it's now out of the shrunk grid's
  // bounds, resolvePanes() falls back to auto-placement for that panel
  // same as an unassigned one, rather than this needing to hunt it down.
  function updateLayout(patch) {
    const L = active();
    L.layout = { ...L.layout, ...patch };
    save();
  }

  function setPanelPane(panelId, pane) {
    const panel = active().panels.find(p => p.id === panelId);
    if (!panel) return;
    panel.pane = pane;
    save();
  }

  function setLinkX(v) {
    active().linkX = v;
    save();
  }

  function state() { return active(); }

  // -- Layout tabs -----------------------------------------------------
  // Each entry is its own independent workspace (panels, grid, style,
  // linkX) -- see normalizeLayoutEntry above.

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
  // tab with the chosen grid -- unlike the old single-workspace "New",
  // there are no existing panels to reset since nothing here existed yet.
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
    state, addTraces, addSpatialTrace, removeTrace, removePanel, clearPanel, renamePanel,
    setYLock, updateLayout, setPanelPane, setLinkX, setPanelStyle, setGlobalStyle, setCaseStyle,
    setActivePanel, setTraceStyle,
    listLayouts, activeLayoutId, setActiveLayout, createLayout, renameLayout, deleteLayout,
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
      kindTag.textContent = panel.kind === 'spatial' ? 'spatial' : '';

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
        const del = document.createElement('span');
        del.className = 'trace-remove';
        del.textContent = '×';
        del.addEventListener('click', () => { PlotWorkspace.removeTrace(panel.id, idx); refreshWorkspace(); });
        row.appendChild(swatch);
        row.appendChild(label);
        row.appendChild(del);
        node.appendChild(row);
      });

      container.appendChild(node);
    }

    const linkRow = document.createElement('label');
    linkRow.className = 'link-x-row';
    linkRow.innerHTML = `<input type="checkbox" id="link-x-toggle" ${ws.linkX ? 'checked' : ''}> Link x-axes`;
    container.appendChild(linkRow);
    document.getElementById('link-x-toggle').addEventListener('change', (e) => {
      PlotWorkspace.setLinkX(e.target.checked);
      PlotArea.render();
    });
  }

  function traceLabel(t) {
    if (!t.points) return `${t.case} r${t.row} ${t.col}`;   // time trace
    const n = t.points.length;
    const range = t.t1 == null && t.t2 == null ? '' : ` [${t.t1 ?? 'start'}, ${t.t2 ?? 'end'}]`;
    const what = t.mode === 'snapshot' ? `@t=${t.time}` : `${t.stat}${range}`;
    return `${t.case} ${t.col} ${what} (${n} node${n === 1 ? '' : 's'})`;
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
