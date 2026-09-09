// Renders the plot workspace: one Plotly figure, each panel its own
// independently positioned/sized subplot (§5 of the plan).
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

  // source ('othd' or 'oisd') is part of the key: othId and osgId are both
  // plain integers starting at 0, so a plain (case, group) key would batch a
  // surface trace and a nodal trace of the same case+group into one
  // /history request neither is right for.
  function groupKey(t) { return `${t.case} ${t.source || 'othd'} ${t.group}`; }

  async function fetchHistory(caseName, group, rows, columns, source = 'othd') {
    const params = new URLSearchParams({
      group: String(group), columns: columns.join(','), rows: rows.join(','), kind: source,
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

  // scale: a real unit transform (e.g. a force trace turned into a lift
  // coefficient), applied to the plotted values themselves -- not a visual
  // trick, so hover values and the exported figure agree with the legend.
  // null/unset means 1, not 0: `t.scale || 1` would silently turn a
  // genuine (if unusual) scale of 0 back into 1.
  function scaleOf(t) { return t.scale == null ? 1 : t.scale; }

  // label: overrides the auto-generated trace name (case/row/column, or
  // case/block/column for a surface trace) wherever it's about to be shown
  // -- an empty override falls back to that name rather than showing nothing.
  function labelOf(t, autoName) { return t.label ? t.label : autoName; }

  // The name a trace gets when its `label` override is unset -- one place,
  // so the legend, the exported figure (export.py mirrors this exact
  // format), and TraceEditor's own placeholder (what the Label field falls
  // back to) can never drift out of agreement with each other.
  function autoLabel(t) {
    if (t.points) return spatialTraceName(t);
    // A surface trace's row is always 0 -- "r0" would say nothing a reader
    // could use, unlike a nodal trace's row. The block name identifies it.
    return t.source === 'oisd' ? `${t.case} ${t.block} ${t.col}` : `${t.case} r${t.row} ${t.col}`;
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

  // An axis title is a plain string, unless applyAxisStyle already turned it
  // into {text, font} (a label font size was set) -- tinting the secondary
  // axis's title has to handle whichever shape it currently is, not assume
  // one, or it silently drops the font-size Plotly object already built.
  function withTitleColor(title, color) {
    if (!title) return title;
    if (typeof title === 'string') return { text: title, font: { color } };
    return { ...title, font: { ...(title.font || {}), color } };
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

  // A panel's own pane (x, y, w, h -- inches, from Layout -> Panes), or the
  // canvas-filling default when it hasn't been placed yet (see
  // PlotWorkspace's defaultPane). Every pane is independent: no grid, no
  // shared tracks, free to overlap or leave gaps -- entirely the typed
  // numbers' doing.
  function paneRect(ws, panel) {
    const p = panel.pane;
    if (p && typeof p.x === 'number' && typeof p.y === 'number' && typeof p.w === 'number' && typeof p.h === 'number') {
      return p;
    }
    return { x: 0, y: 0, w: ws.layout.width, h: ws.layout.height };
  }

  function clamp01(v) { return Math.max(0, Math.min(1, v)); }

  // Inches -> Plotly domain fraction [0,1] (y flipped: inches count down
  // from the canvas top, Plotly domains count up from the bottom). Clamped
  // rather than left to Plotly, which rejects a domain outside [0,1] --
  // a pane typed to run past the canvas edge, or with zero/negative size,
  // still renders something instead of breaking the whole figure; the
  // typed numbers themselves are left alone in state, so shrinking the
  // canvas back later doesn't lose the pane's intended rect.
  function paneDomain(pane, layout) {
    const w = layout.width || 0.001;
    const h = layout.height || 0.001;
    let x0 = clamp01(pane.x / w);
    let x1 = clamp01((pane.x + pane.w) / w);
    let yBottom = clamp01(1 - (pane.y + pane.h) / h);
    let yTop = clamp01(1 - pane.y / h);
    if (x1 <= x0) x1 = Math.min(1, x0 + 0.01);
    if (yTop <= yBottom) yTop = Math.min(1, yBottom + 0.01);
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
          groups.set(key, { case: t.case, group: t.group, source: t.source || 'othd',
                            rows: new Set(), columns: new Set() });
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
        results.set(key, await fetchHistory(g.case, g.group, [...g.rows], [...g.columns], g.source));
      }
      for (const t of spatialTraces) {
        const data = await fetchSpatial(t);
        spatialResults.set(t, new Map(data.values.map(v => [v.row, v.value])));
      }
    } catch (e) {
      placeholder(e.message);
      return;
    }

    document.getElementById('plotarea').innerHTML = '<div id="plotly-panels"></div>';

    const style = ws.style || {};
    // Covers every path that can end up rendering with latex:true, not
    // just the checkbox's own change handler -- a page reload restores
    // ws.style.latex from localStorage without ever firing that event, so
    // relying on the checkbox alone silently left MathJax never loaded
    // (found by actually reloading with it already on).
    if (style.latex && !window.MathJax) {
      ensureMathJax().then(() => render()).catch(err => console.warn(err.message));
    }
    const margin = {
      t: style.marginTop ?? (style.title ? 44 : 24),
      r: style.marginRight ?? 20,
      b: style.marginBottom ?? 40,
      l: style.marginLeft ?? 60,
    };
    // The canvas (Layout -> New/Edit) is always a fixed size, in inches --
    // rendered on-screen at the same 96 px/in CSS uses for "1in", so what
    // you see is to scale. No Plotly `grid` here -- each panel's xaxis/
    // yaxis gets an explicit `domain` (via paneDomain) computed straight
    // from its own pane rect, independent of every other panel's.
    const SCREEN_DPI = 96;
    const traces = [];
    const layout = {
      margin,
      showlegend: !!style.showLegend,
      width: ws.layout.width * SCREEN_DPI,
      height: ws.layout.height * SCREEN_DPI,
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

      // A trace's own secondary-axis toggle (TraceEditor's Axis tab) always
      // means "this trace's *value*, on its own independent scale" -- so it
      // rides whichever physical axis normally carries the value (X when
      // swapped, Y otherwise), never the shared time/position one. Numbered
      // past every panel's own primary slot (1..ws.panels.length) so it can
      // never collide with another panel's axis, whether or not this panel
      // ends up using it.
      const secondaryNum = ws.panels.length + n;
      const secondaryRef = swap ? `x${secondaryNum}` : `y${secondaryNum}`;
      const secondaryKey = swap ? `xaxis${secondaryNum}` : `yaxis${secondaryNum}`;
      const domain = paneDomain(paneRect(ws, panel), ws.layout);

      if (isSpatial) {
        panel.traces.forEach(t => {
          const byRow = spatialResults.get(t) || new Map();
          const symbol = markerSymbolFor(t, true);
          const scale = scaleOf(t);
          const onSecondary = !!t.secondaryAxis;
          const logicalX = t.points.map(p => p.x);
          const logicalY = t.points.map(p => byRow.get(p.row) * scale);
          const trace = {
            x: swap ? logicalY : logicalX, y: swap ? logicalX : logicalY,
            xaxis: (swap && onSecondary) ? secondaryRef : xref,
            yaxis: (!swap && onSecondary) ? secondaryRef : yref,
            mode: symbol ? 'lines+markers' : 'lines', type: 'scatter',
            name: labelOf(t, autoLabel(t)),
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
          const scale = scaleOf(t);
          const onSecondary = !!t.secondaryAxis;
          const logicalX = data ? data.times : [];
          const logicalY = s ? s.values.map(v => v * scale) : [];
          const trace = {
            x: swap ? logicalY : logicalX, y: swap ? logicalX : logicalY,
            xaxis: (swap && onSecondary) ? secondaryRef : xref,
            yaxis: (!swap && onSecondary) ? secondaryRef : yref,
            mode: symbol ? 'lines+markers' : 'lines', type: 'scatter',
            name: labelOf(t, autoLabel(t)),
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
      // The shared time/position axis's range still comes from every trace
      // (primary and secondary alike ride it) -- only the *value* axis
      // splits, since that is the one a secondary trace has opted out of.
      const onSecondary = panel.traces.map(t => !!t.secondaryAxis);
      const primaryTraces = panelTraces.filter((tr, i) => !onSecondary[i]);
      const secondaryTraces = panelTraces.filter((tr, i) => onSecondary[i]);
      const logicalXRange = extent(panelTraces.flatMap(tr => (swap ? tr.y : tr.x)));
      const logicalYRange = extent(primaryTraces.flatMap(tr => (swap ? tr.x : tr.y)));
      applyAxisStyle(logicalXConfig, style, pStyle.xtick, pStyle.xlim, logicalXRange, pStyle.xtickangle);
      applyAxisStyle(logicalYConfig, style, pStyle.ytick, pStyle.ylim, logicalYRange, pStyle.ytickangle);

      layout[xKey] = swap ? logicalYConfig : logicalXConfig;
      layout[yKey] = swap ? logicalXConfig : logicalYConfig;

      // Domain/anchor are pure page geometry -- this panel's own pane --
      // independent of swap, which only decides which physical axis
      // carries which logical data. `anchor` takes Plotly's short axis
      // reference ('y2'), not the layout object's key ('yaxis2') -- passing
      // the key here is silently accepted (it doesn't match any real axis)
      // and Plotly falls back to some other anchor, which is what put a
      // panel's own tick labels over a completely different subplot.
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

      // Only allocated when actually used: a panel with no secondary-axis
      // trace has nothing at this key, and Plotly never looks for it.
      // `overlaying` draws it sharing this panel's own plot area (not a new
      // subplot column); `domain`/`anchor` still have to be given explicitly
      // for the same multi-panel-contamination reason as the primary axes
      // above -- an overlay left to Plotly's own default spans the whole
      // canvas, not just this panel's pane.
      if (secondaryTraces.length) {
        const showY2Ticks = pStyle.showY2Ticks !== false;
        const showY2Label = pStyle.showY2Label !== false;
        const secondaryRange = extent(secondaryTraces.flatMap(tr => (swap ? tr.x : tr.y)));
        const secondaryConfig = { title: showY2Label ? (pStyle.y2label || '') : '', showticklabels: showY2Ticks };
        if (!showY2Ticks) secondaryConfig.ticks = '';
        applyAxisStyle(secondaryConfig, style, pStyle.y2tick, pStyle.y2lim, secondaryRange, pStyle.y2tickangle);
        secondaryConfig.overlaying = swap ? xref : yref;
        secondaryConfig.side = swap ? 'top' : 'right';
        secondaryConfig.anchor = swap ? yref : xref;
        secondaryConfig.domain = swap ? domain.x : domain.y;
        secondaryConfig.showgrid = false;   // the primary axis's own grid is enough
        // Which line belongs to which axis is otherwise only in the legend
        // -- tinting the axis line/ticks/label to match makes that visible
        // right on the plot. `color` alone reaches the line/ticks/tick
        // labels; the title text needs its own font.color, and applyAxisStyle
        // above may have already turned title into {text, font} (a label
        // font size set) or left it a plain string -- withTitleColor handles
        // either shape rather than assuming one.
        if (pStyle.y2color) {
          secondaryConfig.color = pStyle.y2color;
          secondaryConfig.title = withTitleColor(secondaryConfig.title, pStyle.y2color);
        }
        layout[secondaryKey] = secondaryConfig;
      }
    });

    // responsive stretches the plot to fill its container on resize --
    // exactly what a fixed-inches canvas must NOT do, or the pixel size
    // just computed gets silently overridden right back to "fill whatever
    // space is available" (the width/height "doesn't properly fit in"
    // symptom from before the canvas was mandatory).
    await Plotly.newPlot('plotly-panels', traces, layout, { displaylogo: false, responsive: false });
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
    // panelIdx + 1 there -- since each panel's own pane (not axis
    // position) carries where it actually sits on the page.
    const idx = PlotWorkspace.state().panels.findIndex(p => p.id === panelId);
    const n = idx + 1;
    const axis = gd.layout[n === 1 ? `${letter}axis` : `${letter}axis${n}`];
    return axis && axis.range ? [axis.range[0], axis.range[1]] : null;
  }

  // The secondary (Y2) axis's own current range, for the same tick-step
  // guard and lock use as currentYRange -- resolved the same way render()
  // numbers it (past every panel's own primary slot), not read back from
  // Plotly's own axis-assignment guesses.
  function currentY2Range(panelId, swap) {
    const gd = document.getElementById('plotly-panels');
    if (!gd || !gd.layout) return null;
    const panels = PlotWorkspace.state().panels;
    const idx = panels.findIndex(p => p.id === panelId);
    if (idx === -1) return null;
    const num = panels.length + (idx + 1);
    const axis = gd.layout[`${swap ? 'x' : 'y'}axis${num}`];
    return axis && axis.range ? [axis.range[0], axis.range[1]] : null;
  }

  return {
    render, placeholder, currentYRange, currentXRange, currentY2Range, ensureMathJax, paneRect, autoLabel,
  };
})();

// Layout -> Export: POSTs the workspace, matplotlib renders it server-side
// (§Phase 3 -- no client-side path from the raw arrays), as either PNG (a
// chosen dpi) or PDF (vector -- no dpi to choose, so that field is only
// shown for PNG).
const Export = (() => {
  const DEFAULT_DPI = 300;

  function open() {
    const ws = PlotWorkspace.state();
    if (!ws.panels.length) {
      alert('No panels to export -- Plot → New first.');
      return;
    }
    Menu.openDialog(`
      <h2>Layout &rarr; Export</h2>
      <label for="export-format">Format</label>
      <select id="export-format" class="style-panel-select">
        <option value="png">PNG (raster)</option>
        <option value="pdf">PDF (vector)</option>
      </select>
      <div id="export-format-options"></div>
      <div class="btn-row">
        <button id="export-cancel">Cancel</button>
        <button id="export-go" class="primary">Export</button>
      </div>
    `);
    document.getElementById('export-cancel').addEventListener('click', Menu.closeDialog);
    document.getElementById('export-format').addEventListener('change', renderFormatOptions);
    document.getElementById('export-go').addEventListener('click', runExport);
    renderFormatOptions();
  }

  function renderFormatOptions() {
    const box = document.getElementById('export-format-options');
    const format = document.getElementById('export-format').value;
    box.innerHTML = format === 'png'
      ? `<div class="style-row">
           <label for="export-dpi">DPI</label>
           <input type="number" id="export-dpi" value="${DEFAULT_DPI}" min="50" max="1200" step="1">
         </div>`
      : `<div class="empty">PDF is a vector format -- lines and text stay sharp at any zoom, so there's no DPI to set.</div>`;
  }

  async function runExport() {
    const format = document.getElementById('export-format').value;
    let dpi = DEFAULT_DPI;
    if (format === 'png') {
      const raw = parseInt(document.getElementById('export-dpi').value, 10);
      dpi = Number.isFinite(raw) ? Math.max(50, Math.min(1200, raw)) : DEFAULT_DPI;
    }
    try {
      await doExport(format, dpi);
      Menu.closeDialog();
    } catch (e) {
      alert(e.message);
    }
  }

  async function doExport(format, dpi) {
    const ws = PlotWorkspace.state();
    if (!ws.panels.length) throw new Error('No panels to export -- Plot → New first.');
    const res = await fetch('/api/export', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ panels: ws.panels, style: ws.style, layout: ws.layout, format, dpi }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: 'export failed' }));
      throw new Error(err.error);
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `flexflow_plot.${format}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  return { open };
})();
