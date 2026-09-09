// The Field menu: Info (Extract and Render land here in later phases).
const FieldMenu = (() => {
  function escapeHtml(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  async function openInfo() {
    const cases = await App.fetchCases();
    const options = cases
      .map(c => `<option value="${c.name}">${c.name}${c.exists ? '' : ' (missing)'}</option>`)
      .join('');

    Menu.openDialog(`
      <h2>Field &rarr; Info</h2>
      <label for="fi-case">Case</label>
      <select id="fi-case">
        <option value="">Select a case&hellip;</option>
        ${options}
      </select>
      <div id="fi-form"></div>
      <div id="fi-body"></div>
      <div class="btn-row"><button id="fi-close">Close</button></div>
    `, { wide: true });

    document.getElementById('fi-close').addEventListener('click', Menu.closeDialog);
    document.getElementById('fi-case').addEventListener('change', (e) => onFieldCaseChange(e.target.value));
  }

  async function onFieldCaseChange(caseName) {
    const form = document.getElementById('fi-form');
    document.getElementById('fi-body').innerHTML = '';
    if (!caseName) { form.innerHTML = ''; return; }

    form.innerHTML = '<div class="empty">Loading&hellip;</div>';
    const res = await fetch(`/api/cases/${encodeURIComponent(caseName)}/field/steps`);
    const data = await res.json();
    if (!document.getElementById('fi-form')) return;
    if (!res.ok) {
      form.innerHTML = `<div class="error">${escapeHtml(data.error || 'could not load this case')}</div>`;
      return;
    }
    if (!data.steps.length) {
      form.innerHTML = '<div class="error">No PLT files found under binary/.</div>';
      return;
    }
    const latest = data.steps[data.steps.length - 1];
    const stepOptions = data.steps.map(s =>
      `<option value="${s}" ${s === latest ? 'selected' : ''}>${s}</option>`
    ).join('');

    form.innerHTML = `
      <label for="fi-step">Timestep</label>
      <select id="fi-step">${stepOptions}</select>
    `;
    document.getElementById('fi-step').addEventListener('change', (e) =>
      loadFieldInfo(caseName, e.target.value));
    loadFieldInfo(caseName, latest);
  }

  async function loadFieldInfo(caseName, timestep) {
    const body = document.getElementById('fi-body');
    body.innerHTML = '<div class="empty">Loading&hellip;</div>';

    const res = await fetch(`/api/cases/${encodeURIComponent(caseName)}/field/info?timestep=${timestep}`);
    const data = await res.json();
    if (!document.getElementById('fi-body')) return;
    if (!res.ok) {
      body.innerHTML = `<div class="error">${escapeHtml(data.error || 'could not load field info')}</div>`;
      return;
    }
    body.innerHTML = renderFieldInfo(data);
  }

  function renderFieldInfo(data) {
    const b = data.basic;
    const basicTable = `
      <h3>File</h3>
      <table class="info-table">
        <tr><td>File</td><td>${escapeHtml(b.file)}</td></tr>
        <tr><td>Path</td><td>${escapeHtml(b.path)}</td></tr>
        <tr><td>Size</td><td>${b.size_mb.toFixed(1)} MB</td></tr>
        <tr><td>Problem</td><td>${escapeHtml(b.problem || '(unknown)')}</td></tr>
        <tr><td>Variables</td><td>${b.nvars}</td></tr>
        <tr><td>Zones</td><td>${b.nzones}</td></tr>
        <tr><td>PLT files in case</td><td>${b.plt_count}</td></tr>
      </table>
    `;

    const varsTable = `
      <h3>Variables</h3>
      <div class="empty">${data.variables.map(escapeHtml).join(', ')}</div>
    `;

    const zonesTable = `
      <h3>Zones</h3>
      <table class="info-table">
        <tr><th>Zone</th><th>Type</th><th>Nodes/elem</th><th>Nodes</th><th>Elements</th><th></th></tr>
        ${data.zones.map(z => `
          <tr>
            <td>${escapeHtml(z.name)}</td><td>${escapeHtml(z.type)}</td><td>${z.nodes_per_elem}</td>
            <td>${z.npts.toLocaleString()}</td><td>${z.nelem.toLocaleString()}</td>
            <td>${z.shared_from.length
              ? `<span class="empty">shares data from ${z.shared_from.map(escapeHtml).join(', ')}</span>`
              : ''}</td>
          </tr>
        `).join('')}
      </table>
    `;

    const c = data.checks;
    const namingRow = c.naming_ok === null
      ? `<tr><td>Naming</td><td class="empty">problem name unknown (simflow.config)</td></tr>`
      : c.naming_ok
        ? `<tr><td>Naming</td><td>OK -- follows ${escapeHtml(b.problem)}.NNNN.plt</td></tr>`
        : `<tr><td>Naming</td><td class="error">${c.naming_bad_files.length} file(s) off pattern
             (e.g. ${escapeHtml(c.naming_bad_files[0])})</td></tr>`;
    const truncRow = c.truncated
      ? `<tr><td>Size check</td><td class="error">file is SHORT by ${c.short_by_mb.toFixed(1)} MB for
           zone '${escapeHtml(c.zone_name)}' -- likely truncated, or wrong nodes/elem</td></tr>`
      : `<tr><td>Size check</td><td>OK -- consistent with ${escapeHtml(c.cell)} connectivity
           (${c.npts.toLocaleString()} nodes, ${c.nelem.toLocaleString()} elements)</td></tr>`;
    const tetRow = c.tetrahedron_warning
      ? `<tr><td class="error">Element type</td><td class="error">volume zone is FETETRAHEDRON
           (4-node) -- if the mesh is 8-node bricks, set nen=8 in simflow.config and re-run simPlt</td></tr>`
      : '';
    const checksTable = `
      <h3>Consistency checks</h3>
      <table class="info-table">${namingRow}${truncRow}${tetRow}</table>
    `;

    const statsTable = data.stats ? `
      <h3>Data ranges (min / max)</h3>
      <table class="info-table">
        <tr><th>Variable</th><th>Min</th><th>Max</th></tr>
        ${data.stats.map(s => `
          <tr>
            <td>${escapeHtml(s.variable)}</td>
            <td>${s.shared ? '<span class="empty">(shared)</span>' : s.min.toPrecision(6)}</td>
            <td>${s.shared ? '' : s.max.toPrecision(6)}</td>
          </tr>
        `).join('')}
      </table>
    ` : `<div class="error">could not read data ranges: ${escapeHtml(data.stats_error || '')}</div>`;

    return basicTable + varsTable + zonesTable + checksTable + statsTable;
  }

  // -- Extract -------------------------------------------------------------
  // Trimmed v1 of `field extract`: probe points (numeric x/y/z rows, nearest
  // node or --interpolate) sampled over a timestep range, plus a
  // "download this timestep as .vtu" button -- no domain-box crop, no
  // multi-step .pvd export (see the plan's own scoping note). Runs as a
  // background job (services/jobs.py, the same one map-writing already
  // uses) since it can touch several large PLT files.

  let extractPointRow = 0;   // unique ids for point rows, so removal is exact
  let extractResult = null;  // last job result -- what Download CSV writes

  async function openExtract() {
    const cases = await App.fetchCases();
    const options = cases
      .map(c => `<option value="${c.name}">${c.name}${c.exists ? '' : ' (missing)'}</option>`)
      .join('');
    extractResult = null;

    Menu.openDialog(`
      <h2>Field &rarr; Extract</h2>
      <label for="fe-case">Case</label>
      <select id="fe-case">
        <option value="">Select a case&hellip;</option>
        ${options}
      </select>
      <div id="fe-form"></div>
      <div id="fe-result"></div>
      <div class="btn-row"><button id="fe-close">Close</button></div>
    `, { wide: true });

    document.getElementById('fe-close').addEventListener('click', Menu.closeDialog);
    document.getElementById('fe-case').addEventListener('change', (e) => onExtractCaseChange(e.target.value));
  }

  async function onExtractCaseChange(caseName) {
    const form = document.getElementById('fe-form');
    document.getElementById('fe-result').innerHTML = '';
    if (!caseName) { form.innerHTML = ''; return; }

    form.innerHTML = '<div class="empty">Loading&hellip;</div>';
    const res = await fetch(`/api/cases/${encodeURIComponent(caseName)}/field/info`);
    const info = await res.json();
    if (!document.getElementById('fe-form')) return;
    if (!res.ok) {
      form.innerHTML = `<div class="error">${escapeHtml(info.error || 'could not load this case')}</div>`;
      return;
    }
    renderExtractForm(caseName, info);
  }

  function renderExtractForm(caseName, info) {
    const form = document.getElementById('fe-form');
    const zoneOptions = info.zones.map(z =>
      `<option value="${escapeHtml(z.name)}">${escapeHtml(z.name)} (${z.type})</option>`
    ).join('');
    const varRow = info.variables.map(v => `
      <label class="var-check"><input type="checkbox" class="fe-column" value="${escapeHtml(v)}"> ${escapeHtml(v)}</label>
    `).join('');

    extractPointRow = 0;
    form.innerHTML = `
      <label for="fe-zone">Zone</label>
      <select id="fe-zone">${zoneOptions}</select>
      <label>Variables</label>
      <div class="var-list">${varRow}</div>
      <label>Points</label>
      <div id="fe-points"></div>
      <div class="btn-row" style="justify-content:flex-start"><button id="fe-add-point">Add point</button></div>
      <label>Timestep</label>
      <div class="plot-kind-row">
        <label class="var-check"><input type="radio" name="fe-frame" value="single" checked> Single</label>
        <label class="var-check"><input type="radio" name="fe-frame" value="range"> Range (t1..t2)</label>
      </div>
      <div id="fe-frame-options"></div>
      <label class="var-check"><input type="checkbox" id="fe-interpolate"> Interpolate (needs pyvista)</label>
      <div class="btn-row"><button id="fe-go" class="primary" disabled>Extract</button></div>
      <hr>
      <label>Download this timestep's mesh</label>
      <div class="coord-inputs">
        <input type="text" id="fe-mesh-step" placeholder="timestep">
        <button id="fe-mesh-go">Download .vtu</button>
      </div>
      <div id="fe-mesh-error"></div>
    `;

    document.querySelectorAll('.fe-column').forEach(cb => cb.addEventListener('change', updateExtractGoButton));
    document.querySelectorAll('input[name="fe-frame"]').forEach(r =>
      r.addEventListener('change', renderExtractFrameOptions));
    document.getElementById('fe-add-point').addEventListener('click', () => addExtractPointRow());
    document.getElementById('fe-go').addEventListener('click', () => runExtract(caseName));
    document.getElementById('fe-mesh-go').addEventListener('click', () => downloadMesh(caseName));
    renderExtractFrameOptions();
    addExtractPointRow();
  }

  function addExtractPointRow() {
    const box = document.getElementById('fe-points');
    const id = extractPointRow++;
    const row = document.createElement('div');
    row.className = 'coord-inputs fe-point-row';
    row.dataset.id = String(id);
    row.innerHTML = `
      <input type="text" class="fe-x" placeholder="x">
      <input type="text" class="fe-y" placeholder="y">
      <input type="text" class="fe-z" placeholder="z">
      <button type="button" class="fe-remove-point">&times;</button>
    `;
    box.appendChild(row);
    row.querySelector('.fe-remove-point').addEventListener('click', () => {
      row.remove();
      updateExtractGoButton();
    });
    row.querySelectorAll('input').forEach(el => el.addEventListener('input', updateExtractGoButton));
    updateExtractGoButton();
  }

  function renderExtractFrameOptions() {
    const box = document.getElementById('fe-frame-options');
    const frame = document.querySelector('input[name="fe-frame"]:checked').value;
    box.innerHTML = frame === 'single'
      ? `<input type="text" id="fe-timestep" placeholder="timestep">`
      : `<div class="coord-inputs">
           <input type="text" id="fe-t1" placeholder="t1">
           <input type="text" id="fe-t2" placeholder="t2">
         </div>`;
    box.querySelectorAll('input').forEach(el => el.addEventListener('input', updateExtractGoButton));
    updateExtractGoButton();
  }

  function extractPoints() {
    return Array.from(document.querySelectorAll('.fe-point-row')).map(row => ({
      x: parseFloat(row.querySelector('.fe-x').value),
      y: parseFloat(row.querySelector('.fe-y').value),
      z: parseFloat(row.querySelector('.fe-z').value),
    }));
  }

  function updateExtractGoButton() {
    const btn = document.getElementById('fe-go');
    if (!btn) return;
    const anyColumn = document.querySelectorAll('.fe-column:checked').length > 0;
    const points = extractPoints();
    const validPoints = points.length > 0 && points.every(p => !Number.isNaN(p.x) && !Number.isNaN(p.y) && !Number.isNaN(p.z));
    const frame = document.querySelector('input[name="fe-frame"]:checked').value;
    let validFrame;
    if (frame === 'single') {
      const el = document.getElementById('fe-timestep');
      validFrame = el && el.value.trim() !== '' && !Number.isNaN(parseInt(el.value, 10));
    } else {
      const t1 = document.getElementById('fe-t1');
      const t2 = document.getElementById('fe-t2');
      validFrame = t1 && t2 && t1.value.trim() !== '' && t2.value.trim() !== ''
        && !Number.isNaN(parseInt(t1.value, 10)) && !Number.isNaN(parseInt(t2.value, 10));
    }
    btn.disabled = !(anyColumn && validPoints && validFrame);
  }

  async function pollExtractJob(jobId) {
    while (true) {
      const res = await fetch(`/api/jobs/${jobId}`);
      const data = await res.json();
      if (data.status === 'done') return { ok: true, result: data.result };
      if (data.status === 'error') return { ok: false, error: data.error };
      await new Promise(resolve => setTimeout(resolve, 400));
    }
  }

  async function runExtract(caseName) {
    const result = document.getElementById('fe-result');
    const zone = document.getElementById('fe-zone').value;
    const columns = Array.from(document.querySelectorAll('.fe-column:checked')).map(cb => cb.value);
    const points = extractPoints();
    const interpolate = document.getElementById('fe-interpolate').checked;
    const frame = document.querySelector('input[name="fe-frame"]:checked').value;
    const body = { zone, columns, points, interpolate };
    if (frame === 'single') {
      body.timestep = parseInt(document.getElementById('fe-timestep').value, 10);
    } else {
      body.t1 = parseInt(document.getElementById('fe-t1').value, 10);
      body.t2 = parseInt(document.getElementById('fe-t2').value, 10);
    }

    result.innerHTML = '<div class="empty">Extracting&hellip;</div>';
    const res = await fetch(`/api/cases/${encodeURIComponent(caseName)}/field/extract`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    });
    const started = await res.json();
    if (!document.getElementById('fe-result')) return;
    if (!res.ok) {
      result.innerHTML = `<div class="error">${escapeHtml(started.error || 'could not start extraction')}</div>`;
      return;
    }

    const outcome = await pollExtractJob(started.job_id);
    if (!document.getElementById('fe-result')) return;
    if (!outcome.ok) {
      result.innerHTML = `<div class="error">${escapeHtml(outcome.error)}</div>`;
      return;
    }
    extractResult = outcome.result;
    result.innerHTML = renderExtractResult(outcome.result);
    const dl = document.getElementById('fe-download');
    if (dl) dl.addEventListener('click', () => downloadExtractCsv(caseName));
  }

  function renderExtractResult(res) {
    const notes = res.notes.length
      ? `<div class="error">${res.notes.map(escapeHtml).join('<br>')}</div>` : '';
    const header = `<tr>${res.columns.map(c => `<th>${escapeHtml(c)}</th>`).join('')}</tr>`;
    const body = res.rows.map(row => `
      <tr>${res.columns.map(c => `<td>${fmtCell(row[c])}</td>`).join('')}</tr>
    `).join('');
    return `
      ${notes}
      <div class="empty">${res.rows.length} row(s)</div>
      <div class="table-scroll"><table class="info-table">${header}${body}</table></div>
      <div class="btn-row"><button id="fe-download">Download CSV</button></div>
    `;
  }

  function fmtCell(v) {
    if (typeof v === 'number') return Number.isInteger(v) ? String(v) : v.toExponential(6);
    return escapeHtml(String(v));
  }

  function downloadExtractCsv(caseName) {
    if (!extractResult) return;
    const { columns, rows } = extractResult;
    const lines = [columns.join(',')];
    for (const row of rows) lines.push(columns.map(c => row[c]).join(','));
    const blob = new Blob([lines.join('\n')], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${caseName}_probes.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  async function downloadMesh(caseName) {
    const errBox = document.getElementById('fe-mesh-error');
    errBox.innerHTML = '';
    const zone = document.getElementById('fe-zone').value;
    const step = document.getElementById('fe-mesh-step').value.trim();
    if (step === '' || Number.isNaN(parseInt(step, 10))) {
      errBox.innerHTML = '<div class="error">Enter a timestep.</div>';
      return;
    }
    const params = new URLSearchParams({ zone, timestep: step });
    // Fetched (not a direct navigation) so a JSON error response shows inline
    // instead of replacing the whole app with the error page.
    errBox.innerHTML = '<div class="empty">Preparing download&hellip;</div>';
    const res = await fetch(`/api/cases/${encodeURIComponent(caseName)}/field/mesh.vtu?${params}`);
    if (!document.getElementById('fe-mesh-error')) return;
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      errBox.innerHTML = `<div class="error">${escapeHtml(data.error || 'could not export the mesh')}</div>`;
      return;
    }
    errBox.innerHTML = '';
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${caseName}_${zone}_${step}.vtu`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  // -- Render ----------------------------------------------------------
  // Iso-surface / slice-plane PNGs for one timestep, off-screen via pyvista
  // (the same rendering `field render iso|slice` uses server-side) -- a
  // gallery of static images, one per camera view, per the plan's confirmed
  // v1 scope (no live in-browser 3-D viewer; see the plan's own "Deferred"
  // section for that idea). Runs as a background job since a render takes
  // real wall-clock time.

  // Matches render.py's own DEFAULTS['views'] / SLICE_VIEWS names exactly --
  // there is no endpoint for this (it's a fixed, documented default), so it
  // is named here rather than round-tripped from the server.
  const DEFAULT_VIEWS = { iso: ['iso', 'xy', 'xz', 'yz'], slice: ['plane'] };

  async function openRender() {
    const cases = await App.fetchCases();
    const options = cases
      .map(c => `<option value="${c.name}">${c.name}${c.exists ? '' : ' (missing)'}</option>`)
      .join('');

    Menu.openDialog(`
      <h2>Field &rarr; Render</h2>
      <label for="fr-case">Case</label>
      <select id="fr-case">
        <option value="">Select a case&hellip;</option>
        ${options}
      </select>
      <div id="fr-form"></div>
      <div id="fr-result"></div>
      <div class="btn-row"><button id="fr-close">Close</button></div>
    `, { wide: true });

    document.getElementById('fr-close').addEventListener('click', Menu.closeDialog);
    document.getElementById('fr-case').addEventListener('change', (e) => onRenderCaseChange(e.target.value));
  }

  async function onRenderCaseChange(caseName) {
    const form = document.getElementById('fr-form');
    document.getElementById('fr-result').innerHTML = '';
    if (!caseName) { form.innerHTML = ''; return; }

    form.innerHTML = '<div class="empty">Loading&hellip;</div>';
    const res = await fetch(`/api/cases/${encodeURIComponent(caseName)}/field/info`);
    const info = await res.json();
    if (!document.getElementById('fr-form')) return;
    if (!res.ok) {
      form.innerHTML = `<div class="error">${escapeHtml(info.error || 'could not load this case')}</div>`;
      return;
    }
    renderRenderForm(caseName, info);
  }

  function renderRenderForm(caseName, info) {
    const form = document.getElementById('fr-form');
    const volumeZones = info.zones.filter(z => !z.shared_from.length);
    const zoneOptions = volumeZones.map(z =>
      `<option value="${escapeHtml(z.name)}">${escapeHtml(z.name)} (${z.type})</option>`
    ).join('');
    const varOptions = info.variables.map(v =>
      `<option value="${escapeHtml(v)}">${escapeHtml(v)}</option>`
    ).join('');

    form.innerHTML = `
      <label for="fr-zone">Zone</label>
      <select id="fr-zone">${zoneOptions}</select>
      <label for="fr-timestep">Timestep</label>
      <input type="text" id="fr-timestep" placeholder="timestep">
      <label>Mode</label>
      <div class="plot-kind-row">
        <label class="var-check"><input type="radio" name="fr-mode" value="iso" checked> Iso-surface</label>
        <label class="var-check"><input type="radio" name="fr-mode" value="slice"> Slice</label>
      </div>
      <div id="fr-mode-options"></div>
      <label for="fr-color-var">Color by</label>
      <select id="fr-color-var">${varOptions}</select>
      <label>Color range (optional)</label>
      <div class="coord-inputs">
        <input type="text" id="fr-color-min" placeholder="min (blank = auto)">
        <input type="text" id="fr-color-max" placeholder="max (blank = auto)">
      </div>
      <label>Views</label>
      <div id="fr-views" class="var-list"></div>
      <div class="btn-row"><button id="fr-go" class="primary" disabled>Render</button></div>
    `;

    document.getElementById('fr-color-var').value = 'U';
    document.querySelectorAll('input[name="fr-mode"]').forEach(r =>
      r.addEventListener('change', () => { renderModeOptions(info); updateRenderGoButton(); }));
    document.getElementById('fr-timestep').addEventListener('input', updateRenderGoButton);
    document.getElementById('fr-go').addEventListener('click', () => runRender(caseName));
    renderModeOptions(info);
  }

  function currentRenderMode() {
    const checked = document.querySelector('input[name="fr-mode"]:checked');
    return checked ? checked.value : 'iso';
  }

  function renderModeOptions(info) {
    const mode = currentRenderMode();
    const box = document.getElementById('fr-mode-options');
    const varOptions = info.variables.map(v =>
      `<option value="${escapeHtml(v)}" ${v === 'QCriterion' ? 'selected' : ''}>${escapeHtml(v)}</option>`
    ).join('');

    box.innerHTML = mode === 'iso' ? `
      <label for="fr-contour-var">Contour variable</label>
      <select id="fr-contour-var">${varOptions}</select>
      <label for="fr-contour-value">Contour value (optional)</label>
      <input type="text" id="fr-contour-value" placeholder="blank = automatic">
    ` : `
      <label for="fr-slice-normal">Normal</label>
      <select id="fr-slice-normal">
        <option value="x">x</option><option value="y">y</option><option value="z" selected>z</option>
      </select>
      <label for="fr-slice-count">Number of planes</label>
      <input type="text" id="fr-slice-count" placeholder="1">
    `;

    const viewsBox = document.getElementById('fr-views');
    viewsBox.innerHTML = DEFAULT_VIEWS[mode].map((v, i) => `
      <label class="var-check"><input type="checkbox" class="fr-view" value="${v}" ${i === 0 ? 'checked' : ''}> ${v}</label>
    `).join('');
    document.querySelectorAll('.fr-view').forEach(cb => cb.addEventListener('change', updateRenderGoButton));
    updateRenderGoButton();
  }

  function updateRenderGoButton() {
    const btn = document.getElementById('fr-go');
    if (!btn) return;
    const ts = document.getElementById('fr-timestep');
    const validTs = ts && ts.value.trim() !== '' && !Number.isNaN(parseInt(ts.value, 10));
    const anyView = document.querySelectorAll('.fr-view:checked').length > 0;
    btn.disabled = !(validTs && anyView);
  }

  async function pollRenderJob(jobId) {
    while (true) {
      const res = await fetch(`/api/jobs/${jobId}`);
      const data = await res.json();
      if (data.status === 'done') return { ok: true, result: data.result };
      if (data.status === 'error') return { ok: false, error: data.error };
      await new Promise(resolve => setTimeout(resolve, 500));
    }
  }

  async function runRender(caseName) {
    const result = document.getElementById('fr-result');
    const mode = currentRenderMode();
    const zone = document.getElementById('fr-zone').value;
    const timestep = parseInt(document.getElementById('fr-timestep').value, 10);
    const views = Array.from(document.querySelectorAll('.fr-view:checked')).map(cb => cb.value);

    const colorMin = document.getElementById('fr-color-min').value.trim();
    const colorMax = document.getElementById('fr-color-max').value.trim();
    const color = { variable: document.getElementById('fr-color-var').value };
    if (colorMin !== '' && colorMax !== '') color.range = [parseFloat(colorMin), parseFloat(colorMax)];

    const body = { mode, zone, timestep, views, color };
    if (mode === 'iso') {
      body.contour = { variable: document.getElementById('fr-contour-var').value };
      const value = document.getElementById('fr-contour-value').value.trim();
      if (value !== '') body.contour.isosurfaces = [parseFloat(value)];
    } else {
      body.slice = { normal: document.getElementById('fr-slice-normal').value };
      const count = document.getElementById('fr-slice-count').value.trim();
      if (count !== '') body.slice.count = parseInt(count, 10);
    }

    result.innerHTML = '<div class="empty">Rendering&hellip; (this can take a few seconds)</div>';
    const res = await fetch(`/api/cases/${encodeURIComponent(caseName)}/field/render`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    });
    const started = await res.json();
    if (!document.getElementById('fr-result')) return;
    if (!res.ok) {
      result.innerHTML = `<div class="error">${escapeHtml(started.error || 'could not start render')}</div>`;
      return;
    }

    const outcome = await pollRenderJob(started.job_id);
    if (!document.getElementById('fr-result')) return;
    if (!outcome.ok) {
      result.innerHTML = `<div class="error">${escapeHtml(outcome.error)}</div>`;
      return;
    }
    result.innerHTML = renderGallery(caseName, started.job_id, outcome.result.files);
  }

  function renderGallery(caseName, jobId, files) {
    const base = `/api/cases/${encodeURIComponent(caseName)}/field/render/${jobId}`;
    return `
      <div class="render-gallery">
        ${files.map(f => `
          <div class="render-tile">
            <img src="${base}/${f}" alt="${escapeHtml(f)}">
            <a href="${base}/${f}" download="${escapeHtml(f.replace('/', '_'))}">Download</a>
          </div>
        `).join('')}
      </div>
    `;
  }

  return { openInfo, openExtract, openRender };
})();
