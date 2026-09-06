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
    };
  }

  // width/height: null means "auto" (Plotly's own responsive sizing) -- set
  // by Layout -> New/Edit, not required to have a value.
  function defaultLayout() {
    return { rows: 1, columns: 1, width: null, height: null };
  }

  function load() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        const oldLayout = parsed.layout || {};
        // Pre-pane-grid workspaces only ever recorded `columns`; `rows` was
        // implicit (however many the panel count needed). Backfilling it
        // from the panel count keeps an old workspace's grid the same
        // shape it already had, rather than clipping it to one row.
        parsed.layout = {
          ...defaultLayout(),
          columns: oldLayout.columns || 1,
          rows: oldLayout.rows || Math.max(1, Math.ceil(parsed.panels.length / (oldLayout.columns || 1))),
          width: oldLayout.width ?? null,
          height: oldLayout.height ?? null,
        };
        parsed.style = { ...defaultGlobalStyle(), ...(parsed.style || {}) };
        for (const p of parsed.panels) {
          p.style = p.style || {};
          if (!('pane' in p)) p.pane = null;
        }
        return parsed;
      }
    } catch (e) { /* private mode, cleared storage, etc. */ }
    return { linkX: true, panels: [], layout: defaultLayout(), style: defaultGlobalStyle() };
  }

  let ws = load();
  let nextPanelId = 1 + ws.panels.reduce((max, p) => {
    const n = parseInt((p.id || '').replace('p', ''), 10);
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

  // Routing default (§5): a panel already holding this case's traces gets the
  // new ones too (several rows, one case -> shared panel); otherwise a new
  // panel is made, which is what keeps two cases from landing on one panel
  // by accident. Overridable per row (targetPanelId in addTraces) --
  // deliberately overlaying two cases is a choice, not a default.
  function panelFor(caseName, pane) {
    // Excludes spatial panels: they share the "same case -> same panel"
    // instinct, but a time trace and a spatial trace can never share an
    // x-axis, so auto-routing must not merge them just because the case matches.
    let panel = ws.panels.find(p => p.kind !== 'spatial' && p.traces.some(t => t.case === caseName));
    if (!panel) {
      panel = { id: `p${nextPanelId++}`, title: caseName, traces: [], style: {}, pane: pane ?? null };
      ws.panels.push(panel);
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
    let panel;
    if (targetPanelId === '__new__') {
      panel = { id: `p${nextPanelId++}`, title: caseName, traces: [], style: {}, pane: pane ?? null };
      ws.panels.push(panel);
    } else if (targetPanelId) {
      panel = ws.panels.find(p => p.id === targetPanelId);
    }
    if (!panel) panel = panelFor(caseName, pane);

    for (const row of rows) {
      const already = panel.traces.some(
        t => t.case === caseName && t.group === group && t.row === row && t.col === column
      );
      if (already) continue;
      panel.traces.push({ case: caseName, group, row, node: nodeOf ? nodeOf(row) : null,
                          col: column, color: nextColor() });
    }
    if (!ws.activePanelId) ws.activePanelId = panel.id;
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
    let panel = ws.panels.find(p => p.kind === 'spatial' && p.traces.some(t => t.case === caseName));
    if (!panel) {
      panel = { id: `p${nextPanelId++}`, title: `${caseName} (spatial)`, kind: 'spatial', traces: [], style: {}, pane: pane ?? null };
      ws.panels.push(panel);
    }
    return panel;
  }

  function addSpatialTrace(caseName, group, points, column, mode, opts, targetPanelId, pane) {
    let panel;
    if (targetPanelId === '__new__') {
      panel = { id: `p${nextPanelId++}`, title: `${caseName} (spatial)`, kind: 'spatial', traces: [], style: {}, pane: pane ?? null };
      ws.panels.push(panel);
    } else if (targetPanelId) {
      panel = ws.panels.find(p => p.id === targetPanelId);
    }
    if (!panel) panel = panelForSpatial(caseName, pane);

    panel.traces.push({
      case: caseName, group, col: column, mode,
      time: opts.time, stat: opts.stat, t1: opts.t1, t2: opts.t2, axLabel: opts.axLabel,
      points: [...points].sort((a, b) => a.x - b.x),
      color: nextColor(),
    });
    if (!ws.activePanelId) ws.activePanelId = panel.id;
    save();
    return panel;
  }

  function removeTrace(panelId, index) {
    const panel = ws.panels.find(p => p.id === panelId);
    if (!panel) return;
    panel.traces.splice(index, 1);
    if (!panel.traces.length) {
      ws.panels = ws.panels.filter(p => p.id !== panelId);
      if (ws.activePanelId === panelId) {
        ws.activePanelId = ws.panels.length ? ws.panels[0].id : null;
      }
    }
    save();
  }

  function removePanel(panelId) {
    ws.panels = ws.panels.filter(p => p.id !== panelId);
    if (ws.activePanelId === panelId) {
      ws.activePanelId = ws.panels.length ? ws.panels[0].id : null;
    }
    save();
  }

  function clearPanel(panelId) {
    const panel = ws.panels.find(p => p.id === panelId);
    if (!panel) return;
    panel.traces = [];
    save();
  }

  function renamePanel(panelId, title) {
    const panel = ws.panels.find(p => p.id === panelId);
    if (!panel) return;
    panel.title = title;
    save();
  }

  function setPanelStyle(panelId, patch) {
    const panel = ws.panels.find(p => p.id === panelId);
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
    ws.style = { ...ws.style, ...patch };
    save();
  }

  // Per-trace overrides (color, line style, marker) -- distinct from panel
  // style since these describe one line, not the axes it is drawn on.
  function setTraceStyle(panelId, traceIndex, patch) {
    const panel = ws.panels.find(p => p.id === panelId);
    if (!panel || !panel.traces[traceIndex]) return;
    panel.traces[traceIndex] = { ...panel.traces[traceIndex], ...patch };
    save();
  }

  function setActivePanel(id) {
    ws.activePanelId = id;
    save();
  }

  // Layout -> New: replaces the grid outright. Every panel's pane is
  // cleared rather than left pointing at a cell that may no longer exist
  // (or may now mean something else) in the new grid -- panels themselves
  // are untouched, they just fall back to auto-placement (see
  // PlotArea.resolvePanes) until re-assigned.
  function setLayout(spec) {
    ws.layout = { ...defaultLayout(), ...spec };
    for (const p of ws.panels) p.pane = null;
    save();
  }

  // Layout -> Edit: resizes the grid in place. A panel's existing pane is
  // left alone -- if it's now out of the shrunk grid's bounds,
  // resolvePanes() falls back to auto-placement for that panel same as an
  // unassigned one, rather than this needing to hunt down and clear it.
  function updateLayout(patch) {
    ws.layout = { ...ws.layout, ...patch };
    save();
  }

  function setPanelPane(panelId, pane) {
    const panel = ws.panels.find(p => p.id === panelId);
    if (!panel) return;
    panel.pane = pane;
    save();
  }

  function setLinkX(v) {
    ws.linkX = v;
    save();
  }

  function state() { return ws; }

  return {
    state, addTraces, addSpatialTrace, removeTrace, removePanel, clearPanel, renamePanel,
    setYLock, setLayout, updateLayout, setPanelPane, setLinkX, setPanelStyle, setGlobalStyle,
    setActivePanel, setTraceStyle,
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
  PanelTree.render();
  PlotArea.render();
  StyleSidebar.render();
}
