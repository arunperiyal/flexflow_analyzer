// The node picker: a Plotly scatter of a map's projected rows. Click toggles
// a row; box/lasso select toggles a span. A `point` probe has one row and
// collapses to a label instead (§6 of the plan) -- handled by the caller.
const Picker = (() => {
  const SELECTED = '#2563eb';
  const UNSELECTED = '#94a3b8';

  // The base bundle (plotly-basic) has no scatter3d. Loaded once, on demand,
  // the first time a 3-D view is requested (§Phase 3: "lazy-loading a
  // vendored gl3d bundle") -- it is a superset, so it replaces window.Plotly
  // and every existing 2-D chart keeps working.
  let gl3dPromise = null;
  function ensureGl3d() {
    if (gl3dPromise) return gl3dPromise;
    gl3dPromise = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = '/static/vendor/plotly-gl3d.min.js';
      script.onload = resolve;
      script.onerror = () => { gl3dPromise = null; reject(new Error('could not load the 3-D renderer')); };
      document.head.appendChild(script);
    });
    return gl3dPromise;
  }

  function render3d(containerId, { rows, points }, selected, onChange) {
    const el = document.getElementById(containerId);
    el.innerHTML = '';

    const trace = {
      x: points.map(p => p[0]), y: points.map(p => p[1]), z: points.map(p => p[2]),
      mode: 'markers', type: 'scatter3d',
      marker: { size: 4, color: rows.map(r => selected.has(r) ? SELECTED : UNSELECTED) },
      text: rows.map(r => `row ${r}`), hoverinfo: 'text',
    };
    const layout = {
      margin: { t: 8, r: 8, b: 8, l: 8 }, height: 320,
      scene: { xaxis: { title: 'x [m]' }, yaxis: { title: 'y [m]' }, zaxis: { title: 'z [m]' } },
    };

    Plotly.newPlot(el, [trace], layout, { displaylogo: false, responsive: true }).then(() => {
      const restyle = () => {
        Plotly.restyle(el, { 'marker.color': [rows.map(r => selected.has(r) ? SELECTED : UNSELECTED)] }, [0]);
      };
      el.on('plotly_click', (ev) => {
        const pt = ev.points && ev.points[0];
        if (!pt) return;
        const row = rows[pt.pointNumber];
        if (selected.has(row)) selected.delete(row); else selected.add(row);
        restyle();
        onChange(selected);
      });
    });
  }

  function render(containerId, { points, rows, ax, ay, connect, closed }, selected, onChange) {
    const el = document.getElementById(containerId);
    el.innerHTML = '';

    const xs = points.map(p => p[0]);
    const ys = points.map(p => p[1]);
    const traces = [];

    if (connect && xs.length > 1) {
      const lx = xs.slice();
      const ly = ys.slice();
      if (closed) { lx.push(xs[0]); ly.push(ys[0]); }
      traces.push({ x: lx, y: ly, mode: 'lines', type: 'scatter',
                    line: { color: '#cbd5e1', width: 1 }, hoverinfo: 'skip' });
    }

    const markerIndex = traces.length;
    traces.push({
      x: xs, y: ys, mode: 'markers', type: 'scatter',
      marker: {
        color: rows.map(r => selected.has(r) ? SELECTED : UNSELECTED),
        size: 9,
      },
      text: rows.map(r => `row ${r}`),
      hoverinfo: 'text',
    });

    const layout = {
      margin: { t: 8, r: 8, b: 36, l: 48 },
      xaxis: { title: ax, zeroline: false },
      yaxis: { title: ay, zeroline: false },
      dragmode: 'select',
      height: 280,
    };

    Plotly.newPlot(el, traces, layout, { displaylogo: false, responsive: true }).then(() => {
      const restyle = () => {
        Plotly.restyle(el, { 'marker.color': [rows.map(r => selected.has(r) ? SELECTED : UNSELECTED)] },
                       [markerIndex]);
      };

      el.on('plotly_click', (ev) => {
        const pt = ev.points.find(p => p.curveNumber === markerIndex);
        if (!pt) return;
        const row = rows[pt.pointIndex];
        if (selected.has(row)) selected.delete(row); else selected.add(row);
        restyle();
        onChange(selected);
      });

      el.on('plotly_selected', (ev) => {
        if (!ev || !ev.points) return;
        for (const p of ev.points) {
          if (p.curveNumber !== markerIndex) continue;
          selected.add(rows[p.pointIndex]);
        }
        restyle();
        onChange(selected);
      });
    });
  }

  return { render, render3d, ensureGl3d };
})();
