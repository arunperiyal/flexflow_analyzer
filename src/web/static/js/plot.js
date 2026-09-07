// Renders the plot workspace: one Plotly figure, panels as stacked subplots
// sharing an x-axis when linked (§5 of the plan).
const PlotArea = (() => {
  // Lazy-loaded only when the LaTeX checkbox is turned on. Unlike the
  // single-file Plotly bundles, MathJax needs its own config/extension/
  // font-data tree alongside MathJax.js (self-hosted, trimmed to the SVG
  // output path only -- no CDN, per this app's air-gapped-compute-node
  // posture). Plotly has no "enable LaTeX" flag of its own: it checks for
  // window.MathJax at draw time and typesets any $...$ text automatically
  // once present, so loading the script is the whole integration.
  let mathJaxPromise = null;
  function ensureMathJax() {
    if (mathJaxPromise) return mathJaxPromise;
    mathJaxPromise = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = '/static/vendor/mathjax/MathJax.js?config=TeX-MML-AM_SVG';
      script.onload = resolve;
      script.onerror = () => { mathJaxPromise = null; reject(new Error('could not load MathJax')); };
      document.head.appendChild(script);
    });
    return mathJaxPromise;
  }

  function groupKey(t) { return `${t.case}\u0000${t.group}`; }

  async function fetchHistory(caseName, group, rows, columns) {
    const params = new URLSearchParams({
      group: String(group), columns: columns.join(','), rows: rows.join(','),
    });
    const res = await fetch(`/api/cases/${encodeURIComponent(caseName)}/history?${params}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'history request failed');
    return data;
  }

  // Each spatial trace is its own (rows, column, mode) request -- not worth
  // batching further, since a spatial selection is usually a handful of
  // nodes, not the whole case.
  async function fetchSpatial(t) {
    const params = new URLSearchParams({
      group: String(t.group), columns: t.col,
      rows: t.points.map(p => p.row).join(','), mode: t.mode,
    });
    if (t.mode === 'snapshot') {
      params.set('time', String(t.time));
    } else {
      params.set('stats', t.stat);
      if (t.t1 != null) params.set('t1', String(t.t1));
      if (t.t2 != null) params.set('t2', String(t.t2));
    }
    const res = await fetch(`/api/cases/${encodeURIComponent(t.case)}/spatial?${params}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'spatial request failed');
    return data;
  }

  function spatialTraceName(t) {
    return `${t.case} ${t.col} ${t.mode === 'snapshot' ? `@t=${t.time}` : t.stat}`;
  }

  function placeholder(msg) {
    document.getElementById('plotarea').innerHTML = `<div class="plot-placeholder">${msg}</div>`;
  }

  // One figure-wide legend (Plotly has no per-subplot legend), positioned
  // by the global style's choice.
  function legendLayout(style) {
    const legend = style.legendFontSize ? { font: { size: style.legendFontSize } } : {};
    if (style.legendPosition === 'top') {
      return { ...legend, orientation: 'h', x: 0.5, y: 1.08, xanchor: 'center', yanchor: 'bottom' };
    }
    if (style.legendPosition === 'bottom') {
      return { ...legend, orientation: 'h', x: 0.5, y: -0.18, xanchor: 'center', yanchor: 'top' };
    }
    return { ...legend, x: 1, y: 1, xanchor: 'left', yanchor: 'top' };   // top-right (default)
  }

  // A tick step that is tiny relative to the axis's actual range asks
  // Plotly to draw hundreds of gridlines and can hang the render for
  // several seconds. styles.js already rejects that at input time, but a
  // bad value already sitting in a saved workspace (from before that
  // guard existed, or restored from elsewhere) would still hit this on
  // every load -- so it is checked again here, against the real plotted
  // data range, and simply dropped rather than handed to Plotly.
  const MAX_TICKS = 200;

  // Global label size, tick label size, gridlines, and a panel's own tick
  // step / axis limits / tick-label rotation -- shared by both the time and
  // spatial branches below so they stay in sync rather than duplicating
  // this per branch. `dataRange` is the actual plotted extent, used only
  // as a fallback when there is no explicit `lim` to check the tick step
  // against.
  function applyAxisStyle(axisLayout, style, tickStep, lim, dataRange, tickAngle) {
    if (style.labelFontSize && axisLayout.title) {
      axisLayout.title = { text: axisLayout.title, font: { size: style.labelFontSize } };
    }
    if (style.tickFontSize) axisLayout.tickfont = { size: style.tickFontSize };
    if (tickAngle) axisLayout.tickangle = tickAngle;
    axisLayout.showgrid = style.showGrid !== false;
    // ticks:'' (no marks at all) is set ahead of this call when the panel's
    // own showXTicks/showYTicks is off -- global "inside" must not
    // override that back on.
    if (style.ticksInside && axisLayout.ticks !== '') axisLayout.ticks = 'inside';

    const range = lim || dataRange;
    if (tickStep > 0) {
      const tickCount = range ? Math.abs(range[1] - range[0]) / tickStep : 0;
      if (!range || tickCount <= MAX_TICKS) {
        axisLayout.dtick = tickStep;
      } else {
        console.warn(`Dropping a tick step of ${tickStep} -- would draw ~${Math.round(tickCount)} ticks over this axis.`);
      }
    }
    if (lim) {
      axisLayout.autorange = false;
      axisLayout.range = lim;
    }
  }

  // '' (unset) means "the sensible default for this trace kind": no marker
  // for a time trace, a circle for a spatial one (matches behavior before
  // markers were configurable). 'none' is an explicit request to hide it,
  // distinct from leaving the field blank.
  function markerSymbolFor(t, isSpatial) {
    if (t.marker === 'none') return null;
    if (t.marker) return t.marker;
    return isSpatial ? 'circle' : null;
  }

  // Plotly's cleanData chokes on an explicit `undefined` value for a key
  // like `line.dash` or a trace's `marker` (found by actually setting a
  // trace's line style: "Cannot use 'in' operator to search for 'line' in
  // undefined", from Plotly assuming a *present* key has a real object,
  // not JS's `{k: undefined}` where the key exists but the value doesn't).
  // So the key must be left off entirely, not set to undefined -- these
  // build that instead of inlining it, since it is easy to get wrong twice.
  function lineFor(t) {
    const line = { color: t.color, width: 1.4 };
    if (t.lineStyle) line.dash = t.lineStyle;
    return line;
  }

  // No `marker` key at all when there is no symbol -- see the note above
  // lineFor: assigning `marker: undefined` on the trace itself hits the
  // exact same Plotly bug, one level up. `style.markerSize` overrides the
  // per-kind default (5 for a spatial trace, 6 for a time one) globally.
  function addMarker(trace, t, symbol, defaultSize, style, pointCount) {
    if (!symbol) return;
    const size = style.markerSize > 0 ? style.markerSize : defaultSize;
    const step = style.markerStep > 1 ? Math.round(style.markerStep) : 1;
    trace.marker = { color: t.color, symbol, size: step > 1 ? stepSizes(pointCount, size, step) : size };
  }

  // Plotly has no built-in "show a marker every N points" for a
  // lines+markers trace; the usual trick is a per-point size array -- the
  // real size every `step`th point, 0 elsewhere -- so the line itself
  // stays fully drawn through every point and only the marker glyphs thin
  // out (dense time series can be thousands of points wide, where a
  // marker on every one is just visual noise).
  function stepSizes(pointCount, size, step) {
    return Array.from({ length: pointCount }, (_, i) => (i % step === 0 ? size : 0));
  }

  // A manual reduce, not Math.min(...values) -- a panel's combined series
  // can run into the hundred-thousands of points, past what some engines
  // accept as call arguments via spread.
  function extent(values) {
    let lo = Infinity, hi = -Infinity;
    for (const v of values) {
      if (typeof v !== 'number' || !Number.isFinite(v)) continue;
      if (v < lo) lo = v;
      if (v > hi) hi = v;
    }
    return lo <= hi ? [lo, hi] : null;
  }

  // Every cell of the (rows, columns) grid, as non-overlapping rectangular
  // slots: `areas` (merged, span > 1x1) first, then every remaining cell
  // as its own implicit 1x1 slot. An invalid area (out of bounds, or
  // overlapping an earlier one) is dropped rather than corrupting the
  // whole grid -- Layout -> New/Edit is expected to only ever hand this
  // valid, non-overlapping areas, but a hand-edited or stale saved
  // workspace should still render something sane. Sorted row-major by
  // top-left corner so auto-placement below has a stable order.
  function computeSlots(rows, columns, areas) {
    const covered = new Set();
    const slots = [];
    for (const a of areas || []) {
      if (!(a.rowSpan > 0) || !(a.colSpan > 0)) continue;
      if (a.row < 0 || a.col < 0 || a.row + a.rowSpan > rows || a.col + a.colSpan > columns) continue;
      let overlap = false;
      for (let r = a.row; r < a.row + a.rowSpan && !overlap; r++) {
        for (let c = a.col; c < a.col + a.colSpan; c++) {
          if (covered.has(`${r},${c}`)) { overlap = true; break; }
        }
      }
      if (overlap) continue;
      for (let r = a.row; r < a.row + a.rowSpan; r++) {
        for (let c = a.col; c < a.col + a.colSpan; c++) covered.add(`${r},${c}`);
      }
      slots.push({ row: a.row, col: a.col, rowSpan: a.rowSpan, colSpan: a.colSpan });
    }
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < columns; c++) {
        if (!covered.has(`${r},${c}`)) slots.push({ row: r, col: c, rowSpan: 1, colSpan: 1 });
      }
    }
    slots.sort((s1, s2) => s1.row - s2.row || s1.col - s2.col);
    return slots;
  }

  // The full slot list for the workspace's current layout -- used both by
  // resolvePanes below and by the Plot -> New pane picker (which needs
  // every slot, occupied or not, to draw the whole grid).
  function gridSlots(ws) {
    const columns = Math.max(1, ws.layout.columns || 1);
    const rows = Math.max(1, ws.layout.rows || 1);
    return { rows, columns, slots: computeSlots(rows, columns, ws.layout.areas) };
  }

  // Drops any area that no longer fits a (possibly shrunk) grid, or that
  // overlaps an area kept ahead of it -- shared by Layout -> New/Edit
  // (live, as rows/columns are edited) and the workspace load path.
  function clampAreas(areas, rows, columns) {
    return computeSlots(rows, columns, areas).filter(s => s.rowSpan > 1 || s.colSpan > 1);
  }

  // Assigns every panel a slot: a valid, non-conflicting panel.pane (its
  // slot's top-left corner) wins that slot; anything else (unset, no
  // matching slot, or a second panel claiming an already-taken slot) falls
  // back to the next free slot in row-major order, growing the grid
  // downward (as new, unmerged 1x1 rows) rather than dropping the panel.
  // Returns {rows, columns, paneOf}, paneOf mapping panel id -> the full
  // slot {row, col, rowSpan, colSpan} it landed in.
  function resolvePanes(ws) {
    const columns = Math.max(1, ws.layout.columns || 1);
    let rows = Math.max(1, ws.layout.rows || 1);
    let slots = computeSlots(rows, columns, ws.layout.areas);
    const bySlotKey = new Map(slots.map(s => [`${s.row},${s.col}`, s]));
    const used = new Set();
    const paneOf = new Map();

    ws.panels.forEach(panel => {
      const p = panel.pane;
      if (p && Number.isInteger(p.row) && Number.isInteger(p.col)) {
        const key = `${p.row},${p.col}`;
        const slot = bySlotKey.get(key);
        if (slot && !used.has(key)) {
          used.add(key);
          paneOf.set(panel.id, slot);
        }
      }
    });

    let freeSlots = slots.filter(s => !used.has(`${s.row},${s.col}`));
    let freeIdx = 0;
    ws.panels.forEach(panel => {
      if (paneOf.has(panel.id)) return;
      if (freeIdx >= freeSlots.length) {
        // Out of room: add one more unmerged row and try again.
        rows += 1;
        for (let c = 0; c < columns; c++) freeSlots.push({ row: rows - 1, col: c, rowSpan: 1, colSpan: 1 });
      }
      const slot = freeSlots[freeIdx++];
      used.add(`${slot.row},${slot.col}`);
      paneOf.set(panel.id, slot);
    });

    return { rows, columns, paneOf };
  }

  // A grid-with-gap layout (like a CSS grid with `gap`), rows/columns
  // equal-size by default but individually resizable by dragging (see
  // renderResizeHandles) -- `rowFracs`/`colFracs` are relative weights
  // (not required to sum to anything in particular), defaulting to equal
  // weights when absent. The gap itself is always the fixed size it would
  // be in the equal-weight case, so a plain (unresized) grid renders
  // pixel-identical to the old uniform-only implementation.
  const GRID_GAP = 0.08;   // fraction of one (equal-weight) cell's own size
  function trackLayout(fracsRaw, count) {
    const unitRef = 1 / (count + GRID_GAP * (count - 1));
    const gap = unitRef * GRID_GAP;
    const available = 1 - gap * Math.max(0, count - 1);
    const weights = (Array.isArray(fracsRaw) && fracsRaw.length === count && fracsRaw.every(w => w > 0))
      ? fracsRaw : Array(count).fill(1);
    const weightSum = weights.reduce((a, b) => a + b, 0);
    const sizes = weights.map(w => (w / weightSum) * available);
    const starts = [];
    let acc = 0;
    for (let i = 0; i < count; i++) {
      starts.push(acc);
      acc += sizes[i] + gap;
    }
    return { starts, sizes, gap };
  }
  function gridDims(rows, columns, rowFracs, colFracs) {
    const cols = trackLayout(colFracs, columns);
    const rowsL = trackLayout(rowFracs, rows);
    return { colStarts: cols.starts, colSizes: cols.sizes, rowStarts: rowsL.starts, rowSizes: rowsL.sizes };
  }
  function slotDomain(slot, dims) {
    const lastCol = slot.col + slot.colSpan - 1;
    const x0 = dims.colStarts[slot.col];
    const x1 = dims.colStarts[lastCol] + dims.colSizes[lastCol];
    const topRow = slot.row;
    const lastRow = slot.row + slot.rowSpan - 1;
    const yTop = 1 - dims.rowStarts[topRow];
    const yBottom = 1 - (dims.rowStarts[lastRow] + dims.rowSizes[lastRow]);
    return { x: [x0, x1], y: [yBottom, yTop] };
  }

  async function render() {
    const ws = PlotWorkspace.state();
    if (!ws.panels.length) {
      placeholder('Add a case, then Plot &rarr; New will build a panelled plot here.');
      return;
    }

    const groups = new Map();
    const spatialTraces = [];
    for (const panel of ws.panels) {
      if (panel.kind === 'spatial') {
        spatialTraces.push(...panel.traces);
        continue;
      }
      for (const t of panel.traces) {
        const key = groupKey(t);
        if (!groups.has(key)) {
          groups.set(key, { case: t.case, group: t.group, rows: new Set(), columns: new Set() });
        }
        const g = groups.get(key);
        g.rows.add(t.row);
        g.columns.add(t.col);
      }
    }

    const results = new Map();
    const spatialResults = new Map();   // trace -> Map(row -> value)
    try {
      for (const [key, g] of groups) {
        results.set(key, await fetchHistory(g.case, g.group, [...g.rows], [...g.columns]));
      }
      for (const t of spatialTraces) {
        const data = await fetchSpatial(t);
        spatialResults.set(t, new Map(data.values.map(v => [v.row, v.value])));
      }
    } catch (e) {
      placeholder(e.message);
      return;
    }

    // An explicit width/height (Layout -> New/Edit) must render at exactly
    // that pixel size -- forcing the container to width:100% here would
    // override it right back to "fill whatever space is available",
    // which is what silently ignored it before. Auto ('' width/height
    // unset) is the only case that should stretch to fill #plotarea.
    const hasExplicitSize = !!(ws.layout.width || ws.layout.height);
    document.getElementById('plotarea').innerHTML = hasExplicitSize
      ? '<div id="plotly-panels"></div>'
      : '<div id="plotly-panels" style="width:100%"></div>';

    const style = ws.style || {};
    // Covers every path that can end up rendering with latex:true, not
    // just the checkbox's own change handler -- a page reload restores
    // ws.style.latex from localStorage without ever firing that event, so
    // relying on the checkbox alone silently left MathJax never loaded
    // (found by actually reloading with it already on).
    if (style.latex && !window.MathJax) {
      ensureMathJax().then(() => render()).catch(err => console.warn(err.message));
    }
    const resolved = resolvePanes(ws);
    const { rows, columns } = resolved;
    const dims = gridDims(rows, columns, ws.layout.rowFracs, ws.layout.colFracs);

    // No Plotly `grid` here -- it has no notion of a subplot spanning more
    // than one cell, so each panel's xaxis/yaxis gets an explicit `domain`
    // (via slotDomain) instead, computed the same way for a plain 1x1 slot
    // or a merged one.
    const traces = [];
    const layout = {
      margin: {
        t: style.marginTop ?? (style.title ? 44 : 24),
        r: style.marginRight ?? 20,
        b: style.marginBottom ?? 40,
        l: style.marginLeft ?? 60,
      },
      showlegend: !!style.showLegend,
      width: ws.layout.width || undefined,
      height: ws.layout.height || Math.max(240, rows * 220),
      paper_bgcolor: '#ffffff',
      plot_bgcolor: '#ffffff',
    };
    if (style.fontFamily) layout.font = { family: style.fontFamily };
    if (style.title) layout.title = { text: style.title };
    if (style.showLegend) layout.legend = legendLayout(style);

    // "Swap X/Y" rotates a panel 90 degrees: the style sidebar's X/Y fields
    // (label, limits, tick step, tick angle) always describe the same
    // logical quantity (time or position on X, the plotted value on Y)
    // regardless of swap -- swapping only decides which physical Plotly
    // axis that quantity ends up drawn on. Built as logicalX/logicalY
    // below, then assigned to xKey/yKey (or the reverse) at the end,
    // rather than threading a swap flag through every line that touches
    // an axis.
    ws.panels.forEach((panel, panelIdx) => {
      const n = panelIdx + 1;
      const xref = n === 1 ? 'x' : `x${n}`;
      const yref = n === 1 ? 'y' : `y${n}`;
      const isSpatial = panel.kind === 'spatial';
      const pStyle = panel.style || {};
      const swap = !!pStyle.swapAxes;
      const tracesStart = traces.length;

      if (isSpatial) {
        panel.traces.forEach(t => {
          const byRow = spatialResults.get(t) || new Map();
          const symbol = markerSymbolFor(t, true);
          const logicalX = t.points.map(p => p.x);
          const logicalY = t.points.map(p => byRow.get(p.row));
          const trace = {
            x: swap ? logicalY : logicalX, y: swap ? logicalX : logicalY,
            xaxis: xref, yaxis: yref, mode: symbol ? 'lines+markers' : 'lines', type: 'scatter',
            name: spatialTraceName(t),
            line: lineFor(t),
          };
          addMarker(trace, t, symbol, 5, style, logicalX.length);
          traces.push(trace);
        });
      } else {
        panel.traces.forEach(t => {
          const data = results.get(groupKey(t));
          const s = data && data.series.find(s => s.row === t.row && s.column === t.col);
          const symbol = markerSymbolFor(t, false);
          const logicalX = data ? data.times : [];
          const logicalY = s ? s.values : [];
          const trace = {
            x: swap ? logicalY : logicalX, y: swap ? logicalX : logicalY,
            xaxis: xref, yaxis: yref, mode: symbol ? 'lines+markers' : 'lines', type: 'scatter',
            name: `${t.case} r${t.row} ${t.col}`,
            line: lineFor(t),
          };
          addMarker(trace, t, symbol, 6, style, logicalX.length);
          traces.push(trace);
        });
      }

      const xKey = n === 1 ? 'xaxis' : `xaxis${n}`;
      const yKey = n === 1 ? 'yaxis' : `yaxis${n}`;

      // Each panel's tick labels and axis title are shown or hidden
      // per-panel (Style sidebar's Panel section), not inferred from grid
      // position -- simpler and more predictable than trying to guess
      // which panel is "the one that needs it" in an arbitrary grid.
      const showXTicks = pStyle.showXTicks !== false;
      const showYTicks = pStyle.showYTicks !== false;
      const showXLabel = pStyle.showXLabel !== false;
      const showYLabel = pStyle.showYLabel !== false;

      let logicalXConfig, logicalYConfig;
      if (isSpatial) {
        const axLabel = (panel.traces[0] && panel.traces[0].axLabel) || 'position';
        logicalXConfig = { title: showXLabel ? (pStyle.xlabel || axLabel) : '', showticklabels: showXTicks };
        logicalYConfig = { title: showYLabel ? (pStyle.ylabel || panel.title) : '', showticklabels: showYTicks };
      } else {
        logicalXConfig = { title: showXLabel ? (pStyle.xlabel || 'time [s]') : '', showticklabels: showXTicks };
        logicalYConfig = { title: showYLabel ? (pStyle.ylabel || panel.title) : '', showticklabels: showYTicks };
      }
      if (!showXTicks) logicalXConfig.ticks = '';
      if (!showYTicks) logicalYConfig.ticks = '';

      const panelTraces = traces.slice(tracesStart);
      const logicalXRange = extent(panelTraces.flatMap(tr => (swap ? tr.y : tr.x)));
      const logicalYRange = extent(panelTraces.flatMap(tr => (swap ? tr.x : tr.y)));
      applyAxisStyle(logicalXConfig, style, pStyle.xtick, pStyle.xlim, logicalXRange, pStyle.xtickangle);
      applyAxisStyle(logicalYConfig, style, pStyle.ytick, pStyle.ylim, logicalYRange, pStyle.ytickangle);

      layout[xKey] = swap ? logicalYConfig : logicalXConfig;
      layout[yKey] = swap ? logicalXConfig : logicalYConfig;

      // Domain/anchor are pure page geometry -- which slot this panel sits
      // in -- independent of swap, which only decides which physical axis
      // carries which logical data. `anchor` takes Plotly's short axis
      // reference ('y2'), not the layout object's key ('yaxis2') -- passing
      // the key here is silently accepted (it doesn't match any real axis)
      // and Plotly falls back to some other anchor, which is what put a
      // panel's own tick labels over a completely different subplot.
      const slotForDomain = resolved.paneOf.get(panel.id);
      const domain = slotDomain(slotForDomain, dims);
      layout[xKey].domain = domain.x;
      layout[xKey].anchor = yref;
      layout[yKey].domain = domain.y;
      layout[yKey].anchor = xref;

      // A box around each panel: `mirror` draws the axis line on the
      // opposite side too, so showline+mirror on both axes closes the
      // rectangle.
      if (style.showPanelBorder) {
        layout[xKey].showline = true;
        layout[xKey].mirror = true;
        layout[xKey].linecolor = '#94a3b8';
        layout[yKey].showline = true;
        layout[yKey].mirror = true;
        layout[yKey].linecolor = '#94a3b8';
      }
    });

    // responsive stretches the plot to fill its container on resize --
    // exactly what an explicit width/height must NOT do, or the pixel
    // size just entered gets silently overridden right back to "fill
    // whatever space is available" (the width/height "doesn't properly
    // fit in" symptom).
    await Plotly.newPlot('plotly-panels', traces, layout, { displaylogo: false, responsive: !hasExplicitSize });
    renderResizeHandles(ws, rows, columns);
  }

  // Thin draggable strips laid directly over the rendered figure at each
  // row/column boundary -- dragging one grows one row/column and shrinks
  // its neighbor by the same amount (see PlotWorkspace.setGridFracs).
  // Positioned from Plotly's own internal `_fullLayout._size` (the plot
  // area's pixel box within the figure), the standard technique for
  // overlaying DOM elements aligned to a Plotly chart.
  function renderResizeHandles(ws, rows, columns) {
    const area = document.getElementById('plotarea');
    if (!area) return;
    area.querySelectorAll('.grid-resize-handle').forEach(el => el.remove());
    const gd = document.getElementById('plotly-panels');
    if (!gd || !gd._fullLayout || !gd._fullLayout._size) return;
    const size = gd._fullLayout._size;
    const baseLeft = gd.offsetLeft;
    const baseTop = gd.offsetTop;
    const dims = gridDims(rows, columns, ws.layout.rowFracs, ws.layout.colFracs);

    for (let c = 0; c < columns - 1; c++) {
      const midFrac = (dims.colStarts[c] + dims.colSizes[c] + dims.colStarts[c + 1]) / 2;
      const handle = document.createElement('div');
      handle.className = 'grid-resize-handle grid-resize-col';
      handle.style.left = `${baseLeft + size.l + midFrac * size.w - 3}px`;
      handle.style.top = `${baseTop + size.t}px`;
      handle.style.height = `${size.h}px`;
      handle.title = 'Drag to resize these columns';
      handle.addEventListener('mousedown', e => startGridResize(e, 'col', c, size));
      area.appendChild(handle);
    }
    for (let r = 0; r < rows - 1; r++) {
      const midFrac = (dims.rowStarts[r] + dims.rowSizes[r] + dims.rowStarts[r + 1]) / 2;
      const handle = document.createElement('div');
      handle.className = 'grid-resize-handle grid-resize-row';
      handle.style.top = `${baseTop + size.t + midFrac * size.h - 3}px`;
      handle.style.left = `${baseLeft + size.l}px`;
      handle.style.width = `${size.w}px`;
      handle.title = 'Drag to resize these rows';
      handle.addEventListener('mousedown', e => startGridResize(e, 'row', r, size));
      area.appendChild(handle);
    }
  }

  // Applies a live preview of candidate row/col weights via Plotly.relayout
  // (cheap -- no data refetch) while dragging; the real commit (persisting
  // the weights and a full render() to reposition the handles themselves)
  // only happens once, on mouseup.
  function applyGridFracsPreview(gd, ws, resolved, rowFracs, colFracs) {
    const dims = gridDims(resolved.rows, resolved.columns, rowFracs, colFracs);
    const update = {};
    ws.panels.forEach((panel, idx) => {
      const n = idx + 1;
      const xKey = n === 1 ? 'xaxis' : `xaxis${n}`;
      const yKey = n === 1 ? 'yaxis' : `yaxis${n}`;
      const slot = resolved.paneOf.get(panel.id);
      const domain = slotDomain(slot, dims);
      update[`${xKey}.domain`] = domain.x;
      update[`${yKey}.domain`] = domain.y;
    });
    Plotly.relayout(gd, update);
  }

  function startGridResize(e, kind, boundaryIdx, size) {
    e.preventDefault();
    const ws = PlotWorkspace.state();
    const gd = document.getElementById('plotly-panels');
    if (!gd) return;
    const resolved = resolvePanes(ws);
    const count = kind === 'col' ? resolved.columns : resolved.rows;
    const existing = kind === 'col' ? ws.layout.colFracs : ws.layout.rowFracs;
    const weights = (Array.isArray(existing) && existing.length === count) ? existing.slice() : Array(count).fill(1);
    const totalWeight = weights.reduce((a, b) => a + b, 0);
    const minWeight = totalWeight * 0.1;   // keeps a track from collapsing to nothing
    const a = boundaryIdx, b = boundaryIdx + 1;
    const startX = e.clientX, startY = e.clientY;
    let preview = null;

    function onMove(ev) {
      const deltaPx = kind === 'col' ? (ev.clientX - startX) : (ev.clientY - startY);
      const deltaWeight = (deltaPx / (kind === 'col' ? size.w : size.h)) * totalWeight;
      let newA = weights[a] + deltaWeight;
      let newB = weights[b] - deltaWeight;
      if (newA < minWeight) { newA = minWeight; newB = weights[a] + weights[b] - minWeight; }
      if (newB < minWeight) { newB = minWeight; newA = weights[a] + weights[b] - minWeight; }
      preview = weights.slice();
      preview[a] = newA;
      preview[b] = newB;
      const rowFracs = kind === 'row' ? preview : ws.layout.rowFracs;
      const colFracs = kind === 'col' ? preview : ws.layout.colFracs;
      applyGridFracsPreview(gd, ws, resolved, rowFracs, colFracs);
    }
    function onUp() {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      if (!preview) return;
      const rowFracs = kind === 'row' ? preview : ws.layout.rowFracs;
      const colFracs = kind === 'col' ? preview : ws.layout.colFracs;
      PlotWorkspace.setGridFracs(rowFracs, colFracs);
      render();
    }
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }

  // The logical Y/X range, i.e. what the style sidebar's Y/X fields (and
  // the panel-tree's quick lock button) mean -- when a panel is swapped,
  // that data is actually drawn on Plotly's *other* physical axis, so
  // reading gd.layout.yaxis for "logical Y" on a swapped panel would
  // silently hand back the wrong (logical X's) range. Keyed by panel id,
  // not array/render order -- with explicit panes the two can differ, so
  // the axis number has to be re-resolved the same way render() did it.
  function currentYRange(panelId, swap) {
    return axisRange(panelId, swap ? 'x' : 'y');
  }

  function currentXRange(panelId, swap) {
    return axisRange(panelId, swap ? 'y' : 'x');
  }

  function axisRange(panelId, letter) {
    const gd = document.getElementById('plotly-panels');
    if (!gd || !gd.layout) return null;
    // Axis numbering is just render()'s panel array order -- see the n =
    // panelIdx + 1 there -- since domains (not axis position) now carry
    // the grid geometry.
    const idx = PlotWorkspace.state().panels.findIndex(p => p.id === panelId);
    const n = idx + 1;
    const axis = gd.layout[n === 1 ? `${letter}axis` : `${letter}axis${n}`];
    return axis && axis.range ? [axis.range[0], axis.range[1]] : null;
  }

  return {
    render, placeholder, currentYRange, currentXRange, ensureMathJax,
    resolvePanes, gridSlots, clampAreas,
  };
})();

// Plot -> Export PNG (300 dpi): POSTs the workspace, matplotlib renders it
// server-side (§Phase 3 -- no client-side path from the raw arrays).
const Export = (() => {
  async function run() {
    const ws = PlotWorkspace.state();
    if (!ws.panels.length) {
      alert('No panels to export -- Plot → New first.');
      return;
    }
    CommandLog.prompt('plot export --dpi 300');
    const res = await fetch('/api/export', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ panels: ws.panels, style: ws.style, layout: ws.layout }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: 'export failed' }));
      alert(err.error);
      return;
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'flexflow_plot.png';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  return { run };
})();
