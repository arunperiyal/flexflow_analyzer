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

    const columns = (ws.layout && ws.layout.columns) || 1;
    const rows = Math.ceil(ws.panels.length / columns);
    const traces = [];
    const layout = {
      grid: { rows, columns, pattern: 'independent', roworder: 'top to bottom' },
      margin: { t: 24, r: 20, b: 40, l: 60 },
      showlegend: false,
      height: Math.max(240, rows * 220),
      paper_bgcolor: '#ffffff',
      plot_bgcolor: '#ffffff',
    };

    ws.panels.forEach((panel, pIdx) => {
      const n = pIdx + 1;
      const xref = n === 1 ? 'x' : `x${n}`;
      const yref = n === 1 ? 'y' : `y${n}`;
      const isSpatial = panel.kind === 'spatial';

      if (isSpatial) {
        panel.traces.forEach(t => {
          const byRow = spatialResults.get(t) || new Map();
          traces.push({
            x: t.points.map(p => p.x), y: t.points.map(p => byRow.get(p.row)),
            xaxis: xref, yaxis: yref, mode: 'lines+markers', type: 'scatter',
            name: spatialTraceName(t),
            line: { color: t.color, width: 1.4 },
            marker: { color: t.color, size: 5 },
          });
        });
      } else {
        panel.traces.forEach(t => {
          const data = results.get(groupKey(t));
          const s = data && data.series.find(s => s.row === t.row && s.column === t.col);
          traces.push({
            x: data ? data.times : [], y: s ? s.values : [],
            xaxis: xref, yaxis: yref, mode: 'lines', type: 'scatter',
            name: `${t.case} r${t.row} ${t.col}`,
            line: { color: t.color, width: 1.4 },
          });
        });
      }

      const xKey = n === 1 ? 'xaxis' : `xaxis${n}`;
      const yKey = n === 1 ? 'yaxis' : `yaxis${n}`;
      if (isSpatial) {
        // Its own coordinate, not time -- never shares an axis with a time
        // panel (ws.linkX doesn't apply here).
        const axLabel = (panel.traces[0] && panel.traces[0].axLabel) || 'position';
        layout[xKey] = { title: axLabel };
        layout[yKey] = { title: panel.title };
        if (panel.yLock) {
          layout[yKey].autorange = false;
          layout[yKey].range = panel.yLock;
        }
        return;
      }
      // A grid with several columns shows every column's own bottom axis;
      // a single stacked column only labels its last one.
      layout[xKey] = {
        title: (columns > 1 || pIdx === ws.panels.length - 1) ? 'time [s]' : '',
        matches: ws.linkX ? 'x' : undefined,
      };
      layout[yKey] = { title: panel.title };
      if (panel.yLock) {
        layout[yKey].autorange = false;
        layout[yKey].range = panel.yLock;
      }
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

  return { render, placeholder, currentYRange };
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
      body: JSON.stringify({ panels: ws.panels, linkX: ws.linkX }),
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
