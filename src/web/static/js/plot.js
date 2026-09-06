// Renders the plot workspace: one Plotly figure, panels as stacked subplots
// sharing an x-axis when linked (§5 of the plan).
const PlotArea = (() => {
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
  // step / axis limits / flip -- shared by both the time and spatial
  // branches below so they stay in sync rather than duplicating this per
  // branch. `dataRange` is the actual plotted extent, used only as a
  // fallback when there is no explicit `lim` to check the tick step
  // against or to flip.
  function applyAxisStyle(axisLayout, style, tickStep, lim, dataRange, flip) {
    if (style.labelFontSize && axisLayout.title) {
      axisLayout.title = { text: axisLayout.title, font: { size: style.labelFontSize } };
    }
    if (style.tickFontSize) axisLayout.tickfont = { size: style.tickFontSize };
    axisLayout.showgrid = style.showGrid !== false;

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
      axisLayout.range = flip ? [lim[1], lim[0]] : lim;
    } else if (flip) {
      axisLayout.autorange = 'reversed';
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
  // exact same Plotly bug, one level up.
  function addMarker(trace, t, symbol, size) {
    if (symbol) trace.marker = { color: t.color, size, symbol };
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

    document.getElementById('plotarea').innerHTML = '<div id="plotly-panels" style="width:100%"></div>';

    const style = ws.style || {};
    const columns = (ws.layout && ws.layout.columns) || 1;
    const rows = Math.ceil(ws.panels.length / columns);
    const traces = [];
    const layout = {
      grid: { rows, columns, pattern: 'independent', roworder: 'top to bottom' },
      margin: { t: style.title ? 44 : 24, r: 20, b: 40, l: 60 },
      showlegend: !!style.showLegend,
      height: Math.max(240, rows * 220),
      paper_bgcolor: '#ffffff',
      plot_bgcolor: '#ffffff',
    };
    if (style.fontFamily) layout.font = { family: style.fontFamily };
    if (style.title) layout.title = { text: style.title };
    if (style.showLegend) layout.legend = legendLayout(style);

    ws.panels.forEach((panel, pIdx) => {
      const n = pIdx + 1;
      const xref = n === 1 ? 'x' : `x${n}`;
      const yref = n === 1 ? 'y' : `y${n}`;
      const isSpatial = panel.kind === 'spatial';
      const tracesStart = traces.length;

      if (isSpatial) {
        panel.traces.forEach(t => {
          const byRow = spatialResults.get(t) || new Map();
          const symbol = markerSymbolFor(t, true);
          const trace = {
            x: t.points.map(p => p.x), y: t.points.map(p => byRow.get(p.row)),
            xaxis: xref, yaxis: yref, mode: symbol ? 'lines+markers' : 'lines', type: 'scatter',
            name: spatialTraceName(t),
            line: lineFor(t),
          };
          addMarker(trace, t, symbol, 5);
          traces.push(trace);
        });
      } else {
        panel.traces.forEach(t => {
          const data = results.get(groupKey(t));
          const s = data && data.series.find(s => s.row === t.row && s.column === t.col);
          const symbol = markerSymbolFor(t, false);
          const trace = {
            x: data ? data.times : [], y: s ? s.values : [],
            xaxis: xref, yaxis: yref, mode: symbol ? 'lines+markers' : 'lines', type: 'scatter',
            name: `${t.case} r${t.row} ${t.col}`,
            line: lineFor(t),
          };
          addMarker(trace, t, symbol, 6);
          traces.push(trace);
        });
      }

      const xKey = n === 1 ? 'xaxis' : `xaxis${n}`;
      const yKey = n === 1 ? 'yaxis' : `yaxis${n}`;
      const pStyle = panel.style || {};

      if (isSpatial) {
        // Its own coordinate, not time -- never shares an axis with a time
        // panel (ws.linkX doesn't apply here).
        const axLabel = (panel.traces[0] && panel.traces[0].axLabel) || 'position';
        layout[xKey] = { title: axLabel };
        layout[yKey] = { title: panel.title };
      } else {
        // A grid with several columns shows every column's own bottom axis;
        // a single stacked column only labels its last one.
        layout[xKey] = {
          title: (columns > 1 || pIdx === ws.panels.length - 1) ? 'time [s]' : '',
          matches: ws.linkX ? 'x' : undefined,
        };
        layout[yKey] = { title: panel.title };
      }

      const panelTraces = traces.slice(tracesStart);
      const xRange = extent(panelTraces.flatMap(tr => tr.x));
      const yRange = extent(panelTraces.flatMap(tr => tr.y));
      applyAxisStyle(layout[xKey], style, pStyle.xtick, pStyle.xlim, xRange, pStyle.flipX);
      applyAxisStyle(layout[yKey], style, pStyle.ytick, pStyle.ylim, yRange, pStyle.flipY);
    });

    Plotly.newPlot('plotly-panels', traces, layout, { displaylogo: false, responsive: true });
  }

  function currentYRange(index) {
    const gd = document.getElementById('plotly-panels');
    if (!gd || !gd.layout) return null;
    const n = index + 1;
    const axis = gd.layout[n === 1 ? 'yaxis' : `yaxis${n}`];
    return axis && axis.range ? [axis.range[0], axis.range[1]] : null;
  }

  function currentXRange(index) {
    const gd = document.getElementById('plotly-panels');
    if (!gd || !gd.layout) return null;
    const n = index + 1;
    const axis = gd.layout[n === 1 ? 'xaxis' : `xaxis${n}`];
    return axis && axis.range ? [axis.range[0], axis.range[1]] : null;
  }

  return { render, placeholder, currentYRange, currentXRange };
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
      body: JSON.stringify({ panels: ws.panels, linkX: ws.linkX, style: ws.style }),
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
