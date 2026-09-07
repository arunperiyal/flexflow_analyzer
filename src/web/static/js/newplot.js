// The Plot -> New dialog: case, map, picker, View selector, discovered
// components, and routing into the workspace (§6-§8 of the plan).
const NewPlot = (() => {
  let selectedRows = new Set();
  let currentMapData = null;
  let currentCaseMeta = null;
  let currentCaseName = null;
  let currentMapFile = null;

  async function open() {
    selectedRows = new Set();
    currentMapData = null;
    currentCaseMeta = null;
    currentMapFile = null;

    const cases = await App.fetchCases();
    const options = cases
      .map(c => `<option value="${c.name}">${c.name}${c.exists ? '' : ' (missing)'}</option>`)
      .join('');

    Menu.openDialog(`
      <h2>Plot &rarr; New</h2>
      <label for="np-case">Case</label>
      <select id="np-case">
        <option value="">Select a case&hellip;</option>
        ${options}
      </select>
      <div id="np-map-section"></div>
      <div id="np-detail-section"></div>
      <div class="btn-row"><button id="np-cancel">Close</button></div>
    `, { wide: true });

    document.getElementById('np-cancel').addEventListener('click', Menu.closeDialog);
    document.getElementById('np-case').addEventListener('change', onCaseChange);
  }

  async function onCaseChange(e) {
    currentCaseName = e.target.value;
    document.getElementById('np-detail-section').innerHTML = '';
    const mapSection = document.getElementById('np-map-section');
    if (!currentCaseName) { mapSection.innerHTML = ''; return; }

    mapSection.innerHTML = '<div class="empty">Loading maps&hellip;</div>';
    const [maps, meta] = await Promise.all([
      fetch(`/api/cases/${encodeURIComponent(currentCaseName)}/maps`).then(r => r.json()),
      fetch(`/api/cases/${encodeURIComponent(currentCaseName)}/meta`).then(r => r.ok ? r.json() : null),
    ]);
    currentCaseMeta = meta;
    renderMapSection(maps);
  }

  function badge(ok, okTitle, warnTitle) {
    if (ok === null || ok === undefined) return '';
    return ok
      ? `<span class="badge ok" title="${okTitle}">&#10003;</span>`
      : `<span class="badge warn" title="${warnTitle}">&#9888;</span>`;
  }

  function renderMapSection(maps) {
    const mapSection = document.getElementById('np-map-section');
    const writeBtn = `<div class="btn-row"><button id="np-write-map">Write map now</button></div>`;

    if (!maps.length) {
      mapSection.innerHTML = `<div class="error">No maps written for this case yet.</div>${writeBtn}`;
      document.getElementById('np-write-map').addEventListener('click', writeMapNow);
      return;
    }

    const rows = maps.map(m => `
      <div class="candidate-row map-row">
        <input type="radio" name="np-map" value="${m.file}" id="map-${m.file}">
        <label for="map-${m.file}">
          <span class="map-file">${m.file}</span>
          <span class="map-meta">${m.probe || 'probe?'} &middot; ${m.rows} row(s) &middot; othId ${m.oth_id ?? '?'}</span>
          ${badge(m.oth_id_ok, 'othId matches the othd', "othId does not match the othd's real groups — read them before trusting rows")}
          ${badge(m.rows_match, 'row count matches the group', 'row count does not match nodes_of(group) — the map may be stale')}
        </label>
      </div>
    `).join('');

    mapSection.innerHTML = `<label>Map</label><div class="candidate-list">${rows}</div>${writeBtn}`;
    document.getElementById('np-write-map').addEventListener('click', writeMapNow);
    mapSection.querySelectorAll('input[name="np-map"]').forEach(input => {
      input.addEventListener('change', () => onMapChange(input.value));
    });
  }

  async function writeMapNow() {
    if (!confirm(`Write node maps for ${currentCaseName}? This reads the coordinates file once and ` +
                'can take a while for a large case.')) {
      return;
    }
    const mapSection = document.getElementById('np-map-section');
    mapSection.insertAdjacentHTML('beforeend',
      '<div id="np-write-status" class="empty">Writing maps&hellip;</div>');

    const res = await fetch(`/api/cases/${encodeURIComponent(currentCaseName)}/maps`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}),
    });
    if (res.status !== 202) {
      const err = await res.json().catch(() => ({ error: 'could not start the write job' }));
      document.getElementById('np-write-status').textContent = err.error;
      return;
    }
    const { job_id } = await res.json();

    try {
      const maps = await pollJob(job_id);
      renderMapSection(maps);
    } catch (e) {
      const status = document.getElementById('np-write-status');
      if (status) status.textContent = e.message;
    }
  }

  async function pollJob(jobId, intervalMs = 500) {
    while (true) {
      const res = await fetch(`/api/jobs/${jobId}`);
      const data = await res.json();
      if (data.status === 'done') return data.result;
      if (data.status === 'error') throw new Error(data.error || 'job failed');
      await new Promise(resolve => setTimeout(resolve, intervalMs));
    }
  }

  async function onMapChange(file) {
    currentMapFile = file;
    selectedRows = new Set();
    const detail = document.getElementById('np-detail-section');
    detail.innerHTML = '<div class="empty">Loading&hellip;</div>';
    currentMapData = await fetch(
      `/api/cases/${encodeURIComponent(currentCaseName)}/maps/${encodeURIComponent(file)}`
    ).then(r => r.json());
    renderDetail();
  }

  function groupForMap() {
    if (!currentCaseMeta || !currentCaseMeta.groups.length) return null;
    const wanted = currentMapData.header.oth_id;
    return currentCaseMeta.groups.find(g => g.othId === wanted) || currentCaseMeta.groups[0];
  }

  function renderDetail() {
    const detail = document.getElementById('np-detail-section');
    const header = currentMapData.header;
    const group = groupForMap();

    if (header.probe === 'point' || !currentMapData.views.length) {
      const row = currentMapData.rows[0];
      selectedRows = new Set(row ? [row.row] : []);
      detail.innerHTML = `
        <label>Point</label>
        <div class="empty">Single row &mdash; row ${row ? row.row : '?'}${row && row.node != null ? ` (node ${row.node})` : ''}</div>
        ${renderVariablesHtml(group, false)}
      `;
      wireVariablesAndAdd(group);
      updateAddButton();
      return;
    }

    const viewOptions = currentMapData.views.map(v => `<option value="${v.id}">${v.label}</option>`).join('');
    detail.innerHTML = `
      <label for="np-view">View</label>
      <div class="view-row">
        <select id="np-view">${viewOptions}</select>
        <label class="var-check"><input type="checkbox" id="np-3d"> 3-D</label>
      </div>
      <div id="np-picker"></div>
      <div id="np-row-count" class="empty">0 row(s) selected &mdash; click, or box/lasso-select, points to add rows</div>
      <div class="coord-snap">
        <label>Snap to coordinate</label>
        <div class="coord-inputs">
          <input type="text" id="np-snap-x" placeholder="x">
          <input type="text" id="np-snap-y" placeholder="y">
          <input type="text" id="np-snap-z" placeholder="z">
          <button id="np-snap-go">Snap</button>
        </div>
        <div id="np-snap-result" class="empty"></div>
      </div>
      ${renderVariablesHtml(group, true)}
    `;

    document.getElementById('np-view').addEventListener('change', (e) => loadView(e.target.value));
    document.getElementById('np-3d').addEventListener('change', (e) => toggle3d(e.target.checked));
    wireVariablesAndAdd(group);
    wireSnap();
    updateAddButton();
    drawPicker(currentMapData.projection);
  }

  async function toggle3d(on) {
    const viewSelect = document.getElementById('np-view');
    viewSelect.disabled = on;
    if (!on) {
      drawPicker(currentMapData.projection);
      return;
    }
    document.getElementById('np-picker').innerHTML = '<div class="empty">Loading 3-D renderer&hellip;</div>';
    await Picker.ensureGl3d();
    const rows = currentMapData.rows.map(r => r.row);
    const points = currentMapData.rows.map(r => [r.x, r.y, r.z]);
    Picker.render3d('np-picker', { rows, points }, selectedRows, onRowsChanged);
  }

  function wireSnap() {
    document.getElementById('np-snap-go').addEventListener('click', () => {
      const x = parseFloat(document.getElementById('np-snap-x').value);
      const y = parseFloat(document.getElementById('np-snap-y').value);
      const z = parseFloat(document.getElementById('np-snap-z').value);
      const result = document.getElementById('np-snap-result');
      if ([x, y, z].some(Number.isNaN)) {
        result.textContent = 'Enter numeric x, y, z.';
        return;
      }
      let best = null;
      let bestDist = Infinity;
      for (const r of currentMapData.rows) {
        const d = Math.hypot(r.x - x, r.y - y, r.z - z);
        if (d < bestDist) { bestDist = d; best = r; }
      }
      if (!best) return;
      selectedRows.add(best.row);
      result.textContent = `row ${best.row}${best.node != null ? ` (node ${best.node})` : ''} — distance ${bestDist.toFixed(4)} m`;
      drawPicker(currentMapData.projection);
      onRowsChanged();
    });
  }

  function drawPicker(projection) {
    const header = currentMapData.header;
    const rows = currentMapData.rows.map(r => r.row);
    Picker.render('np-picker', {
      points: projection.pts, rows, ax: projection.ax, ay: projection.ay,
      connect: header.probe === 'line' || header.probe === 'helix',
      closed: header.closed,
    }, selectedRows, onRowsChanged);
  }

  async function loadView(viewId) {
    currentMapData = await fetch(
      `/api/cases/${encodeURIComponent(currentCaseName)}/maps/${encodeURIComponent(currentMapFile)}` +
      `?view=${encodeURIComponent(viewId)}`
    ).then(r => r.json());
    drawPicker(currentMapData.projection);
  }

  function onRowsChanged() {
    const label = document.getElementById('np-row-count');
    if (label) label.textContent = `${selectedRows.size} row(s) selected`;
    updateAddButton();
  }

  // Plot kind chooses the x-axis: 'time' (a node's value over time, the
  // usual case) or 'spatial' (one statistic/snapshot per node, plotted
  // against position along the probe -- e.g. RMS displacement per node,
  // to see where along the structure the response is largest). A single
  // row (a point probe) has no "position" axis worth plotting, so spatial
  // is only offered when allowSpatial is true.
  const STATS = [
    ['rms', 'RMS'], ['mean', 'Mean'], ['peak_abs', 'Peak absolute'], ['peak_to_peak', 'Peak-to-peak'],
  ];

  function renderVariablesHtml(group, allowSpatial) {
    if (!group) return '<div class="error">No time-history group found for this case.</div>';
    const header = currentMapData.header;
    const mismatch = (header.oth_id !== null && header.oth_id !== group.othId)
      ? `<div class="error">Map predicts othId ${header.oth_id}, but the othd only wrote ` +
        `group ${group.othId} &mdash; using that instead.</div>`
      : '';
    const cols = group.columns
      .map(c => `<label class="var-check"><input type="checkbox" class="np-column" value="${c}"> ${c}</label>`)
      .join('');
    const kindRow = allowSpatial ? `
      <label>Plot kind</label>
      <div class="plot-kind-row">
        <label class="var-check"><input type="radio" name="np-kind" value="time" checked> Time series</label>
        <label class="var-check"><input type="radio" name="np-kind" value="spatial"> Spatial (per-node)</label>
      </div>
    ` : '';
    return `
      ${mismatch}
      ${kindRow}
      <label>Variables (othId ${group.othId})</label>
      <div class="var-list">${cols}</div>
      <div id="np-spatial-options"></div>
      <label for="np-panel">Panel</label>
      <select id="np-panel"></select>
      <div class="btn-row"><button id="np-add" class="primary" disabled>Add to plot</button></div>
    `;
  }

  function currentKind() {
    const checked = document.querySelector('input[name="np-kind"]:checked');
    return checked ? checked.value : 'time';
  }

  function renderPanelOptions(kind) {
    const select = document.getElementById('np-panel');
    if (!select) return;
    const matching = PlotWorkspace.state().panels.filter(p => (p.kind === 'spatial') === (kind === 'spatial'));
    const options = matching.map(p => `<option value="${p.id}">${p.title} (overlay)</option>`).join('');
    select.innerHTML = kind === 'spatial'
      ? `<option value="">Auto &mdash; one panel per case</option><option value="__new__">New panel</option>${options}`
      : `<option value="">Auto &mdash; new panel per case, shared panel per row</option>` +
        `<option value="__new__">New panel</option>${options}`;
  }

  function renderSpatialOptions() {
    const box = document.getElementById('np-spatial-options');
    if (!box) return;
    if (currentKind() !== 'spatial') { box.innerHTML = ''; return; }

    const stats = STATS.map(([id, label]) =>
      `<label class="var-check"><input type="checkbox" class="np-stat" value="${id}"> ${label}</label>`
    ).join('');

    box.innerHTML = `
      <label>Time frame</label>
      <div class="plot-kind-row">
        <label class="var-check"><input type="radio" name="np-frame" value="single" checked> Single time</label>
        <label class="var-check"><input type="radio" name="np-frame" value="multi"> Multi time (statistic)</label>
      </div>
      <div id="np-frame-options"></div>
    `;
    document.querySelectorAll('input[name="np-frame"]').forEach(r => r.addEventListener('change', renderFrameOptions));
    renderFrameOptions();

    function renderFrameOptions() {
      const frameBox = document.getElementById('np-frame-options');
      const frame = document.querySelector('input[name="np-frame"]:checked').value;
      frameBox.innerHTML = frame === 'single'
        ? `<div class="coord-inputs"><input type="text" id="np-time" placeholder="time"></div>`
        : `<div class="coord-inputs">
             <input type="text" id="np-t1" placeholder="t1 (blank = start)">
             <input type="text" id="np-t2" placeholder="t2 (blank = end)">
           </div>
           <div class="var-list">${stats}</div>`;
      frameBox.querySelectorAll('input').forEach(el => el.addEventListener('input', updateAddButton));
      frameBox.querySelectorAll('input[type=checkbox]').forEach(el => el.addEventListener('change', updateAddButton));
      updateAddButton();
    }
  }

  function wireVariablesAndAdd(group) {
    document.querySelectorAll('.np-column').forEach(cb => cb.addEventListener('change', updateAddButton));
    document.querySelectorAll('input[name="np-kind"]').forEach(r => r.addEventListener('change', () => {
      renderPanelOptions(currentKind());
      renderSpatialOptions();
      updateAddButton();
    }));
    renderPanelOptions(currentKind());
    renderSpatialOptions();
    const addBtn = document.getElementById('np-add');
    if (addBtn) addBtn.addEventListener('click', () => addToPlot(group));
  }

  function updateAddButton() {
    const addBtn = document.getElementById('np-add');
    if (!addBtn) return;
    const anyColumn = document.querySelectorAll('.np-column:checked').length > 0;
    let ready = selectedRows.size && anyColumn;

    if (currentKind() === 'spatial') {
      const frame = document.querySelector('input[name="np-frame"]:checked');
      if (!frame || frame.value === 'single') {
        const time = document.getElementById('np-time');
        ready = ready && !!time && time.value.trim() !== '' && !Number.isNaN(parseFloat(time.value));
      } else {
        const anyStat = document.querySelectorAll('.np-stat:checked').length > 0;
        ready = ready && anyStat;
      }
    }
    addBtn.disabled = !ready;
  }

  function spatialPointsForSelection() {
    const proj = currentMapData.projection;
    return Array.from(selectedRows).map(row => {
      const idx = currentMapData.rows.findIndex(r => r.row === row);
      const node = idx >= 0 && currentMapData.rows[idx].node != null ? currentMapData.rows[idx].node : null;
      return { row, x: proj.pts[idx][0], node };
    });
  }

  function addToPlot(group) {
    const columns = Array.from(document.querySelectorAll('.np-column:checked')).map(cb => cb.value);
    if (!columns.length || !selectedRows.size || !group) return;

    const panelChoice = document.getElementById('np-panel').value;   // '' | '__new__' | a panel id

    if (currentKind() === 'spatial') {
      const points = spatialPointsForSelection();
      const axLabel = currentMapData.projection.ax;
      const frame = document.querySelector('input[name="np-frame"]:checked').value;

      for (const column of columns) {
        if (frame === 'single') {
          const time = parseFloat(document.getElementById('np-time').value);
          PlotWorkspace.addSpatialTrace(currentCaseName, group.othId, points, column, 'snapshot',
            { time, axLabel }, panelChoice);
        } else {
          const t1raw = document.getElementById('np-t1').value.trim();
          const t2raw = document.getElementById('np-t2').value.trim();
          const t1 = t1raw === '' ? null : parseFloat(t1raw);
          const t2 = t2raw === '' ? null : parseFloat(t2raw);
          const stats = Array.from(document.querySelectorAll('.np-stat:checked')).map(cb => cb.value);
          for (const stat of stats) {
            PlotWorkspace.addSpatialTrace(currentCaseName, group.othId, points, column, 'stat',
              { stat, t1, t2, axLabel }, panelChoice);
          }
        }
      }
    } else {
      const nodeOf = (row) => {
        const r = currentMapData.rows.find(rr => rr.row === row);
        return r && r.node != null ? r.node : null;
      };
      for (const column of columns) {
        PlotWorkspace.addTraces(currentCaseName, group.othId, Array.from(selectedRows), nodeOf, column, panelChoice);
      }
    }

    refreshWorkspace();
    Menu.closeDialog();
  }

  return { open };
})();
