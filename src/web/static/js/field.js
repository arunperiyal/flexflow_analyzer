// The Field menu: Info (Extract and Render land here in later phases).
const FieldMenu = (() => {
  function escapeHtml(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  async function openInfo() {
    teardownRenderConfigIfOpen();
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
    teardownRenderConfigIfOpen();
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
  // Iso-surface/slice geometry for one timestep, extracted server-side via
  // pyvista (the same extraction `field render iso|slice` uses, stopping
  // before the screenshot step -- see services/field_render.py's
  // render_field_mesh) and handed to an interactive vtk.js viewer -- not in
  // the layout directly, but in its own configuration window
  // (openRenderConfig) where the camera, colormap, contour and surface
  // appearance are all worked out live. Only once that window's "Add to
  // Layout" is clicked does anything reach the workspace, and what lands
  // there is a snapshot PNG, not the live mesh: a layout panel is a picture
  // of one finished camera angle, never something still being posed.
  // Extraction runs as a background job since the PLT -> VTU conversion and
  // the extraction itself take real wall-clock time.
  //
  // Closing over any still-open configuration window's own teardown, so a
  // second Field menu action taken before "Add to Layout"/"Cancel" doesn't
  // strand its vtk.js instance (WebGL context, RAF loop) when openDialog
  // overwrites its DOM out from under it.
  let closeOpenRenderConfig = null;

  function teardownRenderConfigIfOpen() {
    if (closeOpenRenderConfig) {
      closeOpenRenderConfig();
      closeOpenRenderConfig = null;
    }
  }

  async function openRender() {
    teardownRenderConfigIfOpen();
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
    // /field/info alone doesn't carry every available timestep (it reports on
    // one PLT, defaulting to the latest) -- /field/steps is the same list
    // Field -> Info's own timestep dropdown uses, fetched alongside it here
    // to drive the slider below.
    const [infoRes, stepsRes] = await Promise.all([
      fetch(`/api/cases/${encodeURIComponent(caseName)}/field/info`),
      fetch(`/api/cases/${encodeURIComponent(caseName)}/field/steps`),
    ]);
    const info = await infoRes.json();
    if (!document.getElementById('fr-form')) return;
    if (!infoRes.ok) {
      form.innerHTML = `<div class="error">${escapeHtml(info.error || 'could not load this case')}</div>`;
      return;
    }
    const stepsData = await stepsRes.json();
    const steps = stepsRes.ok ? (stepsData.steps || []) : [];
    renderRenderForm(caseName, info, steps);
  }

  function renderRenderForm(caseName, info, steps) {
    loadedStyleExtras = null;
    const form = document.getElementById('fr-form');
    const volumeZones = info.zones.filter(z => !z.shared_from.length);
    const zoneOptions = volumeZones.map(z =>
      `<option value="${escapeHtml(z.name)}">${escapeHtml(z.name)} (${z.type})</option>`
    ).join('');
    const varOptions = info.variables.map(v =>
      `<option value="${escapeHtml(v)}">${escapeHtml(v)}</option>`
    ).join('');
    // Defaults to the latest step, same convention Field -> Info's own
    // timestep dropdown uses -- so the slider (and the "Render" button,
    // which needs a valid timestep to enable) both start somewhere real
    // instead of empty.
    const hasSteps = steps && steps.length > 0;
    const defaultStep = hasSteps ? steps[steps.length - 1] : '';

    form.innerHTML = `
      <label for="fr-zone">Zone</label>
      <select id="fr-zone">${zoneOptions}</select>
      <label for="fr-timestep">Timestep</label>
      <div class="coord-inputs">
        <input type="text" id="fr-timestep" placeholder="timestep" value="${defaultStep}">
        ${hasSteps ? `<span class="empty">of ${steps.length} available</span>` : ''}
      </div>
      ${hasSteps ? `<input type="range" id="fr-timestep-slider" min="0" max="${steps.length - 1}" step="1" value="${steps.length - 1}">` : ''}
      <label>Mode</label>
      <div class="plot-kind-row">
        <label class="var-check"><input type="radio" name="fr-mode" value="iso" checked> Iso-surface</label>
        <label class="var-check"><input type="radio" name="fr-mode" value="slice"> Slice</label>
      </div>
      <label for="fr-load-style">Load style (optional)</label>
      <input type="file" id="fr-load-style" accept=".yml,.yaml">
      <div id="fr-load-style-status"></div>
      <div id="fr-mode-options"></div>
      <label for="fr-color-var">Color by</label>
      <select id="fr-color-var">${varOptions}</select>
      <label>Color range (optional)</label>
      <div class="coord-inputs">
        <input type="text" id="fr-color-min" placeholder="min (blank = auto)">
        <input type="text" id="fr-color-max" placeholder="max (blank = auto)">
      </div>
      <div class="btn-row"><button id="fr-go" class="primary" disabled>Render</button></div>
    `;

    document.getElementById('fr-color-var').value = 'U';
    document.querySelectorAll('input[name="fr-mode"]').forEach(r =>
      r.addEventListener('change', () => { renderModeOptions(info); updateRenderGoButton(); }));

    const timestepInput = document.getElementById('fr-timestep');
    timestepInput.addEventListener('input', () => {
      // Best-effort sync: snaps the slider to the nearest known step so it
      // stays a useful picker even while free typing a value of its own --
      // that value still goes through untouched (the server is the real
      // validator, same as before this existed).
      const slider = hasSteps ? document.getElementById('fr-timestep-slider') : null;
      if (slider) {
        const typed = parseInt(timestepInput.value, 10);
        if (!Number.isNaN(typed)) {
          let nearestIdx = 0, nearestDist = Infinity;
          steps.forEach((s, i) => {
            const d = Math.abs(s - typed);
            if (d < nearestDist) { nearestDist = d; nearestIdx = i; }
          });
          slider.value = nearestIdx;
        }
      }
      updateRenderGoButton();
    });
    if (hasSteps) {
      document.getElementById('fr-timestep-slider').addEventListener('input', (e) => {
        timestepInput.value = steps[parseInt(e.target.value, 10)];
        updateRenderGoButton();
      });
    }
    document.getElementById('fr-load-style').addEventListener('change', (e) => onLoadStyleFile(e));
    document.getElementById('fr-go').addEventListener('click', () => runRender(caseName));
    renderModeOptions(info);
  }

  // Everything a loaded style file carries beyond the two fields the dialog
  // itself shows (color-by/range, updated in the form directly) -- preset,
  // levels, log scale, and the surface: block. Threaded through to the
  // created panel's initial style (PlotWorkspace.addRenderPanel's
  // styleOverrides) since adding a full second copy of the Style sidebar's
  // controls to this dialog just to show them again before creation isn't
  // worth it -- they're all still editable in the sidebar right after.
  let loadedStyleExtras = null;

  async function onLoadStyleFile(e) {
    const file = e.target.files[0];
    const status = document.getElementById('fr-load-style-status');
    loadedStyleExtras = null;
    if (!file) { status.innerHTML = ''; return; }
    let parsed;
    try {
      parsed = parseStyleYaml(await file.text());
    } catch (err) {
      status.innerHTML = `<div class="error">Could not read ${escapeHtml(file.name)}: ${escapeHtml(err.message)}</div>`;
      return;
    }
    const c = parsed.color || {};
    const colorVarSelect = document.getElementById('fr-color-var');
    if (c.variable && Array.from(colorVarSelect.options).some(o => o.value === c.variable)) {
      colorVarSelect.value = c.variable;
    }
    if (Array.isArray(c.range) && c.range.length === 2) {
      document.getElementById('fr-color-min').value = c.range[0];
      document.getElementById('fr-color-max').value = c.range[1];
    }
    loadedStyleExtras = styleFromParsedYaml(parsed);
    status.innerHTML = `<div class="empty">Loaded ${escapeHtml(file.name)} -- colormap: ${escapeHtml(c.preset || 'default')},`
      + ` edges: ${loadedStyleExtras.showEdges ? 'on' : 'off'}, lighting: ${loadedStyleExtras.lighting ? 'on' : 'off'}</div>`;
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
    updateRenderGoButton();
  }

  function updateRenderGoButton() {
    const btn = document.getElementById('fr-go');
    if (!btn) return;
    const ts = document.getElementById('fr-timestep');
    const validTs = ts && ts.value.trim() !== '' && !Number.isNaN(parseInt(ts.value, 10));
    btn.disabled = !validTs;
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

  // Shared by the Render dialog (a new panel) and the Style sidebar's
  // editable contour variable/value (re-extracting an existing panel's
  // mesh): POST render-mesh, poll the job, then POST it into the persistent
  // render cache (field_render_save) so the result survives a page reload or
  // server restart the way the job's own tempdir/in-memory registry entry
  // don't. Returns { token, jobResult }; throws Error(message) on any
  // failure so callers just try/catch instead of repeating this three ways.
  async function extractMesh(caseName, body, onProgress) {
    if (onProgress) onProgress('Extracting geometry…');
    const res = await fetch(`/api/cases/${encodeURIComponent(caseName)}/field/render-mesh`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    });
    const started = await res.json();
    if (!res.ok) throw new Error(started.error || 'could not start render');

    const outcome = await pollRenderJob(started.job_id);
    if (!outcome.ok) throw new Error(outcome.error);

    if (onProgress) onProgress('Adding to layout…');
    const filename = outcome.result.files[0];
    const saveRes = await fetch(`/api/cases/${encodeURIComponent(caseName)}/field/render/${started.job_id}/save`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ filename }),
    });
    if (!saveRes.ok) {
      const err = await saveRes.json().catch(() => ({}));
      throw new Error(err.error || 'could not save the render to the layout');
    }
    const saved = await saveRes.json();
    return { token: saved.token, jobResult: outcome.result };
  }

  async function runRender(caseName) {
    const result = document.getElementById('fr-result');
    const mode = currentRenderMode();
    const zone = document.getElementById('fr-zone').value;
    const timestep = parseInt(document.getElementById('fr-timestep').value, 10);

    const colorMin = document.getElementById('fr-color-min').value.trim();
    const colorMax = document.getElementById('fr-color-max').value.trim();
    const color = { variable: document.getElementById('fr-color-var').value };
    if (colorMin !== '' && colorMax !== '') color.range = [parseFloat(colorMin), parseFloat(colorMax)];

    const body = { mode, zone, timestep, color };
    if (mode === 'iso') {
      body.contour = { variable: document.getElementById('fr-contour-var').value };
      const value = document.getElementById('fr-contour-value').value.trim();
      if (value !== '') body.contour.isosurfaces = [parseFloat(value)];
    } else {
      body.slice = { normal: document.getElementById('fr-slice-normal').value };
      const count = document.getElementById('fr-slice-count').value.trim();
      if (count !== '') body.slice.count = parseInt(count, 10);
    }

    let extracted;
    try {
      extracted = await extractMesh(caseName, body,
        (msg) => { result.innerHTML = `<div class="empty">${escapeHtml(msg)}</div>`; });
    } catch (err) {
      if (document.getElementById('fr-result')) result.innerHTML = `<div class="error">${escapeHtml(err.message)}</div>`;
      return;
    }
    if (!document.getElementById('fr-result')) return;

    // colorRange: the range the dialog's own fields asked for, if any -- the
    // server has no use for it when extracting a mesh (there's no image to
    // color, only geometry), so it never comes back in jobResult and has to
    // be threaded through from here instead. styleOverrides: a loaded style
    // file's preset/levels/log-scale/surface fields (Load style), seeding
    // the configuration window's initial style.
    // openRenderConfig calls Menu.openDialog itself, replacing this form in
    // the same dialog element -- no separate close first (there's only one
    // dialog slot; opening a new one already discards this one's content).
    openRenderConfig(caseName, mode, zone, timestep, extracted.token, extracted.jobResult, {
      colorVar: color.variable, colorRange: color.range || null,
      styleOverrides: loadedStyleExtras || undefined,
    });
  }

  // -- Render configuration window -------------------------------------
  // Opened once extraction finishes (runRender, above): a live vtk.js view
  // of the mesh, with a sidebar carrying every camera/color/contour/surface
  // control, kept in a closure-local `cfg` object rather than PlotWorkspace
  // -- there is no panel yet, and never will be unless "Add to Layout" is
  // clicked. All of it -- rotate, recolor, re-contour, load a saved camera
  // -- only ever touches this one instance (CFG_ID); "Add to Layout"
  // rasterizes whatever it currently shows into a snapshot PNG and that
  // becomes the actual, permanent, un-editable layout panel. "Cancel"
  // (or opening any other Field dialog -- see teardownRenderConfigIfOpen)
  // discards the instance with nothing added.
  const CFG_ID = 'render-config';

  const RENDER_PRESETS = [
    ['', 'Default'], ['coolwarm', 'Cool to warm'], ['small_rainbow', 'Small rainbow (Tecplot)'],
    ['viridis', 'Viridis'], ['jet', 'Jet'], ['turbo', 'Turbo'], ['inferno', 'Inferno'],
  ];

  // The biggest box the viewport wrapper (.render-config-viewport-wrap,
  // 600px tall) can offer a preview at, before scaling down to fit --
  // matches its CSS height, with room either side for the wrapper's own
  // centering. Only the *shape* (aspect ratio) has to be accurate for
  // framing a shot to make sense; the preview itself never needs to be
  // literal-inches-to-pixels since Plotly's sizing:'contain' will fit
  // whatever resolution was captured into the pane at export/display time
  // regardless.
  const VIEWPORT_MAX_W = 900;
  const VIEWPORT_MAX_H = 580;

  function applyViewportSize(widthIn, heightIn) {
    const el = document.getElementById('rc-viewport');
    if (!el) return;
    const aspect = widthIn / heightIn;
    let w = VIEWPORT_MAX_W, h = w / aspect;
    if (h > VIEWPORT_MAX_H) { h = VIEWPORT_MAX_H; w = h * aspect; }
    el.style.width = `${w}px`;
    el.style.height = `${h}px`;
  }

  // The dpi the saved snapshot is actually captured at -- deliberately
  // decoupled from the on-screen preview above, which is capped small
  // (VIEWPORT_MAX_W/H) purely so the dialog fits on screen. Capturing at
  // that same low resolution would bake it permanently into the panel: it
  // would still look soft once placed at the pane's real (often larger)
  // size, and especially once Layout -> Export scales it up towards its
  // own dpi setting (up to 1200) -- exactly the "looks nothing like the
  // preview" gap this fixes. 300 dpi matches Export's own PDF/PNG default
  // (see export.py's `dpi = 300 if dpi is None else ...`) so the common
  // case -- export at the default setting -- embeds this PNG at its native
  // resolution instead of upscaling (and softening) it; a render panel
  // still caps out below that if someone raises Export's own dpi past 300,
  // same tradeoff as before, just recalibrated to the default rather than
  // matching Export's max (1200) on every render panel regardless of
  // whether it's ever printed that large. CAPTURE_MAX_PX caps the memory/
  // time/cache-size cost for a pane sized well beyond a normal figure,
  // scaled up from before to preserve the same ~16in max side at the new,
  // doubled dpi.
  const CAPTURE_DPI = 300;
  const CAPTURE_MAX_PX = 4800;

  function captureResolution(widthIn, heightIn) {
    let w = widthIn * CAPTURE_DPI;
    let h = heightIn * CAPTURE_DPI;
    const longest = Math.max(w, h);
    if (longest > CAPTURE_MAX_PX) {
      const scale = CAPTURE_MAX_PX / longest;
      w *= scale;
      h *= scale;
    }
    return { w: Math.round(w), h: Math.round(h) };
  }

  // Blows the viewport up to capture resolution just long enough to grab
  // the snapshot, then restores the on-screen preview size -- done off-
  // screen (fixed position, pushed far left) rather than in place, so nothing
  // visibly jumps in the dialog for the moment that takes. A WebGL canvas
  // renders correctly while positioned off-screen; it just isn't seen.
  async function captureAtFullResolution(cfg, viewportEl, syncViewer) {
    const size = captureResolution(cfg.pane.w, cfg.pane.h);
    const prev = {
      position: viewportEl.style.position, left: viewportEl.style.left,
      top: viewportEl.style.top, width: viewportEl.style.width, height: viewportEl.style.height,
    };
    viewportEl.style.position = 'fixed';
    viewportEl.style.left = '-100000px';
    viewportEl.style.top = '0';
    viewportEl.style.width = `${size.w}px`;
    viewportEl.style.height = `${size.h}px`;
    await syncViewer();
    try {
      return await MeshViewer.captureImage(CFG_ID);
    } finally {
      Object.assign(viewportEl.style, prev);
      await syncViewer();
    }
  }

  function openRenderConfig(caseName, mode, zone, timestep, meshToken, jobResult, initial) {
    initial = initial || {};
    // Defaults to the active layout's own canvas size -- the same size a
    // freshly added panel with no pane of its own would fill (panels.js's
    // defaultPane) -- so leaving Panel size alone reproduces today's
    // behavior exactly.
    const activeLayout = PlotWorkspace.state().layout || {};
    const cfg = {
      meshToken,
      variables: jobResult.variables || [],
      contourVariable: jobResult.contourVariable || null,
      contourValue: jobResult.contourValue == null ? null : jobResult.contourValue,
      pane: { w: activeLayout.width || 6.5, h: activeLayout.height || 4.5 },
      // Set by "Load camera" (renderConfigSidebar) and cleared by "Reset
      // camera": while true, a Panel size change must not re-fit the camera
      // (resizeAndFit, below) -- otherwise the whole point of loading a
      // specific saved pose is silently undone the moment the panel is
      // resized to its intended final placement, which is exactly the
      // sequence someone loading a camera before sizing the panel would hit.
      cameraCustom: false,
      style: {
        colorVar: initial.colorVar || jobResult.colorVar || null,
        colorRange: initial.colorRange || null,
        background: [1, 1, 1], showBorder: false, opacity: 1,
        preset: null, levels: null, logScale: false,
        showEdges: false, lighting: true,
        ambient: null, diffuse: null, specular: null, specularPower: null,
        ...(initial.styleOverrides || {}),
      },
    };

    Menu.openDialog(`
      <h2>Field &rarr; Render &mdash; ${escapeHtml(caseName)} (${escapeHtml(mode)} ${escapeHtml(String(timestep))})</h2>
      <div class="render-config-body">
        <div class="render-config-viewport-wrap">
          <div class="render-config-viewport" id="rc-viewport"></div>
        </div>
        <div class="render-config-sidebar" id="rc-sidebar"></div>
      </div>
      <div class="btn-row">
        <button id="rc-cancel">Cancel</button>
        <button id="rc-add" class="primary">Add to Layout</button>
      </div>
    `);
    // Not { wide: true }: .wide and .render-config both set #dialog's width
    // at equal CSS specificity, so whichever rule comes second in app.css
    // would otherwise win regardless of which class actually applies here.
    document.getElementById('dialog').classList.add('render-config');

    applyViewportSize(cfg.pane.w, cfg.pane.h);
    const viewportEl = document.getElementById('rc-viewport');
    // pane: null -- the live preview always fills its own viewport div
    // completely (applyViewportSize already gave that div the right shape);
    // there's no freeform x/y to speak of until this becomes a real layout
    // panel (Add to Layout, below, is what actually places it via pane).
    const panelShape = () => ({ id: CFG_ID, case: caseName, meshToken: cfg.meshToken, pane: null, style: cfg.style });
    const syncViewer = () => MeshViewer.sync([panelShape()], viewportEl);
    syncViewer();

    const teardown = () => { MeshViewer.sync([], viewportEl); };
    closeOpenRenderConfig = teardown;

    document.getElementById('rc-cancel').addEventListener('click', () => {
      teardown();
      closeOpenRenderConfig = null;
      Menu.closeDialog();
    });
    document.getElementById('rc-add').addEventListener('click', async () => {
      const btn = document.getElementById('rc-add');
      btn.disabled = true;
      try {
        const camera = MeshViewer.getCamera(CFG_ID);
        const image = await captureAtFullResolution(cfg, viewportEl, syncViewer);
        const res = await fetch(`/api/cases/${encodeURIComponent(caseName)}/field/snapshot`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ image }),
        });
        const saved = await res.json();
        if (!res.ok) throw new Error(saved.error || 'could not save the snapshot');
        const title = `${caseName} — ${mode} ${timestep}`;
        PlotWorkspace.addRenderPanel(caseName, title, saved.token, {
          mode, zone, timestep, variables: cfg.variables,
          contourVariable: cfg.contourVariable, contourValue: cfg.contourValue,
          style: cfg.style, camera, pane: { x: 0, y: 0, w: cfg.pane.w, h: cfg.pane.h },
        });
        teardown();
        closeOpenRenderConfig = null;
        Menu.closeDialog();
        refreshWorkspace();
      } catch (err) {
        btn.disabled = false;
        alert(err.message || 'could not add this panel to the layout');
      }
    });

    // zone/timestep never change once the window is open (only contour
    // variable/value do) -- closed over here rather than threaded through
    // renderConfigSidebar's own params.
    const contourApply = (newVar, newValue, onProgress) => {
      const body = {
        mode: 'iso', zone, timestep,
        color: { variable: cfg.style.colorVar || undefined, range: cfg.style.colorRange || undefined },
        contour: { variable: newVar },
      };
      if (newValue != null) body.contour.isosurfaces = [newValue];
      return extractMesh(caseName, body, onProgress);
    };

    renderConfigSidebar(caseName, mode, timestep, cfg, syncViewer, contourApply);
  }

  function renderConfigSidebar(caseName, mode, timestep, cfg, syncViewer, contourApply) {
    const sidebar = document.getElementById('rc-sidebar');
    if (!sidebar) return;
    const s = cfg.style;
    const varOptions = (v) => cfg.variables.map(name =>
      `<option value="${escapeHtml(name)}" ${name === v ? 'selected' : ''}>${escapeHtml(name)}</option>`
    ).join('');

    const contourBlock = cfg.contourVariable ? `
      <h3>Contour</h3>
      <label for="rc-contour-var">Variable</label>
      <select id="rc-contour-var">${varOptions(cfg.contourVariable)}</select>
      <label for="rc-contour-value">Value</label>
      <input type="number" id="rc-contour-value" placeholder="auto" value="${cfg.contourValue ?? ''}">
      <div class="btn-row" style="justify-content:flex-start"><button id="rc-contour-apply">Apply</button></div>
      <div id="rc-contour-status"></div>
    ` : '';

    sidebar.innerHTML = `
      <h3>Panel size</h3>
      <label>Width &times; Height (in)</label>
      <div class="coord-inputs">
        <input type="number" id="rc-panel-width" min="0.5" step="0.1" value="${cfg.pane.w}">
        <input type="number" id="rc-panel-height" min="0.5" step="0.1" value="${cfg.pane.h}">
      </div>
      <div class="empty">How this panel will actually be sized in the layout --
        matters for framing, since a wider/taller pane shows more of the shot.</div>
      ${contourBlock}
      <h3>Camera</h3>
      <div class="btn-row" style="justify-content:flex-start">
        <button id="rc-reset-camera">Reset camera</button>
      </div>
      <label for="rc-load-camera">Load camera</label>
      <input type="file" id="rc-load-camera" accept=".yml,.yaml">
      <div id="rc-load-camera-status"></div>
      <h3>Color</h3>
      <label for="rc-colorvar">Color by</label>
      <select id="rc-colorvar">
        <option value="">(none)</option>
        ${varOptions(s.colorVar)}
      </select>
      <label>Color range (blank = auto)</label>
      <div class="coord-inputs">
        <input type="number" id="rc-range-min" placeholder="min" value="${s.colorRange ? s.colorRange[0] : ''}">
        <input type="number" id="rc-range-max" placeholder="max" value="${s.colorRange ? s.colorRange[1] : ''}">
      </div>
      <label for="rc-preset">Colormap</label>
      <select id="rc-preset">${RENDER_PRESETS.map(([v, l]) =>
        `<option value="${v}" ${v === (s.preset || '') ? 'selected' : ''}>${l}</option>`).join('')}</select>
      <label for="rc-levels">Levels</label>
      <input type="number" id="rc-levels" placeholder="continuous" min="2" step="1" value="${s.levels ?? ''}">
      <label class="var-check"><input type="checkbox" id="rc-logscale" ${s.logScale ? 'checked' : ''}> Log scale</label>
      <h3>Appearance</h3>
      <label for="rc-background">Background</label>
      <input type="color" id="rc-background" value="${rgbToHex(s.background || [1, 1, 1])}">
      <label class="var-check"><input type="checkbox" id="rc-border" ${s.showBorder ? 'checked' : ''}> Border</label>
      <label for="rc-opacity">Opacity</label>
      <input type="range" id="rc-opacity" min="0" max="1" step="0.05" value="${s.opacity == null ? 1 : s.opacity}">
      <label class="var-check"><input type="checkbox" id="rc-edges" ${s.showEdges ? 'checked' : ''}> Show edges</label>
      <label class="var-check"><input type="checkbox" id="rc-lighting" ${s.lighting !== false ? 'checked' : ''}> Lighting</label>
      <label for="rc-ambient">Ambient</label>
      <input type="number" id="rc-ambient" placeholder="auto" min="0" max="1" step="0.05" value="${s.ambient ?? ''}">
      <label for="rc-diffuse">Diffuse</label>
      <input type="number" id="rc-diffuse" placeholder="auto" min="0" max="1" step="0.05" value="${s.diffuse ?? ''}">
      <label for="rc-specular">Specular</label>
      <input type="number" id="rc-specular" placeholder="auto" min="0" max="1" step="0.05" value="${s.specular ?? ''}">
      <label for="rc-specular-power">Specular power</label>
      <input type="number" id="rc-specular-power" placeholder="auto" min="0" step="1" value="${s.specularPower ?? ''}">
      <h3>Save</h3>
      <div class="btn-row" style="justify-content:flex-start">
        <button id="rc-save-style">Save style&hellip;</button>
        <button id="rc-save-camera">Save camera&hellip;</button>
      </div>
    `;

    // Changing the pane's shape means the mesh's existing zoom -- fit to the
    // OLD aspect ratio -- fits the new one by coincidence at best; without a
    // re-fit here, a pane widened specifically to cut down on empty space
    // around a long, thin mesh instead shrinks it to a dot in the middle of
    // a much wider frame. fitCamera keeps whatever rotation is already
    // applied and just re-fits the zoom/framing to the new shape.
    //
    // Skipped once a camera has been explicitly loaded (cfg.cameraCustom):
    // that pose is the whole point of "Load camera" -- typically to match
    // several renders' framing exactly -- and a Panel size change is a
    // completely separate, unrelated action from the user's point of view.
    // Silently re-fitting here would throw the loaded pose away the moment
    // the panel is resized to its intended final placement, which is
    // exactly the order someone loading a camera *then* sizing the panel
    // would hit. "Reset camera" (below) is what clears the flag again.
    const resizeAndFit = async () => {
      applyViewportSize(cfg.pane.w, cfg.pane.h);
      await syncViewer();
      if (!cfg.cameraCustom) MeshViewer.fitCamera(CFG_ID);
    };
    document.getElementById('rc-panel-width').addEventListener('change', (e) => {
      const w = numberOrNull(e.target.value);
      if (w && w > 0) cfg.pane.w = w;
      resizeAndFit();
    });
    document.getElementById('rc-panel-height').addEventListener('change', (e) => {
      const h = numberOrNull(e.target.value);
      if (h && h > 0) cfg.pane.h = h;
      resizeAndFit();
    });
    document.getElementById('rc-save-style').addEventListener('click', () => {
      // downloadStyleYaml only reads .style/.title off whatever it's given
      // -- a real workspace panel isn't needed for that, just something
      // shaped like one.
      downloadStyleYaml({ style: s, title: `${caseName}_${mode}_${timestep}` });
    });
    document.getElementById('rc-save-camera').addEventListener('click', () => {
      const camera = MeshViewer.getCamera(CFG_ID);
      if (!camera) return;
      downloadCameraYaml({ camera, title: `${caseName}_${mode}_${timestep}` });
    });

    const restyle = (patch) => { Object.assign(s, patch); syncViewer(); };
    const bindNumber = (id, key) => document.getElementById(id).addEventListener('change', (e) =>
      restyle({ [key]: numberOrNull(e.target.value) }));
    const bindCheckbox = (id, key) => document.getElementById(id).addEventListener('change', (e) =>
      restyle({ [key]: e.target.checked }));

    if (cfg.contourVariable) {
      document.getElementById('rc-contour-apply').addEventListener('click', async () => {
        const btn = document.getElementById('rc-contour-apply');
        const status = document.getElementById('rc-contour-status');
        const newVar = document.getElementById('rc-contour-var').value;
        const raw = document.getElementById('rc-contour-value').value.trim();
        const newValue = raw === '' ? null : parseFloat(raw);
        btn.disabled = true;
        status.innerHTML = '<div class="empty">Extracting geometry…</div>';
        try {
          const outcome = await contourApply(newVar, newValue,
            (msg) => { status.innerHTML = `<div class="empty">${escapeHtml(msg)}</div>`; });
          cfg.meshToken = outcome.token;
          cfg.variables = outcome.jobResult.variables;
          cfg.contourVariable = outcome.jobResult.contourVariable;
          cfg.contourValue = outcome.jobResult.contourValue;
          await MeshViewer.reloadMesh({ id: CFG_ID, case: caseName, meshToken: cfg.meshToken, style: s }, cfg.cameraCustom);
          renderConfigSidebar(caseName, mode, timestep, cfg, syncViewer, contourApply);
        } catch (err) {
          status.innerHTML = `<div class="error">${escapeHtml(err.message)}</div>`;
          btn.disabled = false;
        }
      });
    }

    document.getElementById('rc-reset-camera').addEventListener('click', () => {
      MeshViewer.resetCamera(CFG_ID);
      cfg.cameraCustom = false;
    });
    document.getElementById('rc-load-camera').addEventListener('change', async (e) => {
      const file = e.target.files[0];
      const status = document.getElementById('rc-load-camera-status');
      if (!file) return;
      try {
        const camera = parseCameraYaml(await file.text());
        MeshViewer.setCamera(CFG_ID, camera);
        cfg.cameraCustom = true;
        status.innerHTML = `<div class="empty">Loaded ${escapeHtml(file.name)}</div>`;
      } catch (err) {
        status.innerHTML = `<div class="error">Could not read ${escapeHtml(file.name)}: ${escapeHtml(err.message)}</div>`;
      }
    });

    document.getElementById('rc-colorvar').addEventListener('change', (e) => restyle({ colorVar: e.target.value || null }));
    const commitRange = () => {
      const minV = document.getElementById('rc-range-min').value.trim();
      const maxV = document.getElementById('rc-range-max').value.trim();
      restyle({ colorRange: (minV === '' || maxV === '') ? null : [parseFloat(minV), parseFloat(maxV)] });
    };
    document.getElementById('rc-range-min').addEventListener('change', commitRange);
    document.getElementById('rc-range-max').addEventListener('change', commitRange);
    document.getElementById('rc-preset').addEventListener('change', (e) => restyle({ preset: e.target.value || null }));
    document.getElementById('rc-levels').addEventListener('change', (e) => {
      const v = e.target.value.trim();
      restyle({ levels: v === '' ? null : Math.max(2, Math.round(parseFloat(v))) });
    });
    bindCheckbox('rc-logscale', 'logScale');
    document.getElementById('rc-background').addEventListener('input', (e) => restyle({ background: hexToRgb(e.target.value) }));
    bindCheckbox('rc-border', 'showBorder');
    document.getElementById('rc-opacity').addEventListener('input', (e) => restyle({ opacity: numberOrNull(e.target.value) ?? 1 }));
    bindCheckbox('rc-edges', 'showEdges');
    bindCheckbox('rc-lighting', 'lighting');
    bindNumber('rc-ambient', 'ambient');
    bindNumber('rc-diffuse', 'diffuse');
    bindNumber('rc-specular', 'specular');
    bindNumber('rc-specular-power', 'specularPower');
  }

  const numberOrNull = (v) => (v.trim() === '' ? null : parseFloat(v));

  // A render panel's background is [r, g, b] floats 0-1 (vtk.js's own
  // setBackground(r, g, b) convention), but <input type="color"> only
  // speaks #rrggbb -- converted at the edges, never stored as hex. Mirrors
  // styles.js's own copies of these two (kept local rather than shared: the
  // sidebar module and this one don't otherwise depend on each other).
  function rgbToHex(rgb) {
    const c = (v) => Math.round(Math.max(0, Math.min(1, v)) * 255).toString(16).padStart(2, '0');
    return `#${c(rgb[0])}${c(rgb[1])}${c(rgb[2])}`;
  }
  function hexToRgb(hex) {
    const n = parseInt(hex.slice(1), 16);
    return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
  }

  // -- Save Style / Load style ----------------------------------------
  // Round-trips a render panel's color/surface style as a small YAML file --
  // matching the `color:`/`surface:` blocks of render.py's own config shape
  // (see `field render iso --write-template`), so a saved file also works
  // as-is with `field render iso|slice --config`. Saved to the user's own
  // machine (a download, like Extract's CSV) rather than the server: nothing
  // here needs a case's filesystem, and it keeps this independent of which
  // case a style was first picked on.

  function fmtYamlValue(v) {
    if (v === null || v === undefined) return 'null';
    if (typeof v === 'boolean') return v ? 'true' : 'false';
    if (Array.isArray(v)) return `[${v.join(', ')}]`;
    return String(v);
  }

  function styleToYaml(panel) {
    const s = panel.style || {};
    // A live panel's preset is null until someone picks one (vtk.js's own
    // default map, which has no render.py-side equivalent) -- written out
    // explicitly as render.py's own default (coolwarm) instead of null, so
    // `field render --config` this file produces the same colors the
    // interactive view was actually showing, not matplotlib's own default.
    const lines = [
      "# FlexFlow render style -- the color:/surface: blocks of render.py's",
      '# own config shape (see `field render iso --write-template`). Usable',
      '# as-is in `field render iso|slice --config style.yml`, or reloaded',
      '# here via Field -> Render\'s "Load style".',
      '',
      'color:',
      `  variable: ${fmtYamlValue(s.colorVar)}`,
      `  preset: ${fmtYamlValue(s.preset || 'coolwarm')}`,
      `  range: ${fmtYamlValue(s.colorRange)}`,
      `  levels: ${fmtYamlValue(s.levels)}`,
      `  log_scale: ${fmtYamlValue(!!s.logScale)}`,
      '  show_scalar_bar: true   # the interactive viewer has no legend yet; field render PNGs do',
      '',
      'surface:',
      `  opacity: ${fmtYamlValue(s.opacity == null ? 1 : s.opacity)}`,
      `  show_edges: ${fmtYamlValue(!!s.showEdges)}`,
      `  lighting: ${fmtYamlValue(s.lighting !== false)}`,
      `  ambient: ${fmtYamlValue(s.ambient)}`,
      `  diffuse: ${fmtYamlValue(s.diffuse)}`,
      `  specular: ${fmtYamlValue(s.specular)}`,
      `  specular_power: ${fmtYamlValue(s.specularPower)}`,
      '',
      // Not one of render.py's own sections -- `field render` never reads
      // this block and just ignores it -- since a border is FlexFlow's own
      // layout chrome around the panel (see Layout -> Panes), not anything
      // pyvista draws into the PNG itself. Kept here anyway, rather than
      // dropped from Save/Load style entirely, since the sidebar presents
      // it right alongside every other style field this file round-trips.
      'panel:',
      `  border: ${fmtYamlValue(!!s.showBorder)}`,
      '',
    ];
    return lines.join('\n');
  }

  // A narrow, purpose-built reader for exactly the shape styleToYaml emits --
  // two top-level sections (color/surface), one scalar per line -- not a
  // general YAML parser. This app is self-hosted for an air-gapped compute
  // node (see vendor/vtkjs/VENDORED.md), so a full YAML library is a real
  // dependency to vendor for a format this small and this fully controlled
  // by the writer above; a hand-edited file that stays in this same flat
  // shape still reads fine.
  function parseStyleYaml(text) {
    const result = { color: {}, surface: {}, panel: {} };
    let section = null;
    for (const raw of text.split('\n')) {
      const line = raw.replace(/#.*$/, '').replace(/\s+$/, '');
      if (!line.trim()) continue;
      const topMatch = line.match(/^(\w+):\s*$/);
      if (topMatch) { section = topMatch[1]; continue; }
      const fieldMatch = line.match(/^\s+(\w+):\s*(.*)$/);
      if (!fieldMatch || !result[section]) continue;
      result[section][fieldMatch[1]] = parseYamlScalar(fieldMatch[2].trim());
    }
    return result;
  }

  function parseYamlScalar(v) {
    if (v === '' || v === 'null' || v === '~') return null;
    if (v === 'true') return true;
    if (v === 'false') return false;
    if (/^\[.*\]$/.test(v)) {
      const inner = v.slice(1, -1).trim();
      return inner ? inner.split(',').map(s => parseFloat(s.trim())) : [];
    }
    if (/^-?\d+(\.\d+)?([eE][-+]?\d+)?$/.test(v)) return parseFloat(v);
    return v.replace(/^["']|["']$/g, '');
  }

  // Everything a loaded file carries EXCEPT color.variable/range: those two
  // are surfaced as the dialog's own visible fields (onLoadStyleFile fills
  // them in directly), so keeping them here too would silently overwrite a
  // value the user retyped after loading, once this gets merged into the
  // panel's style on creation.
  function styleFromParsedYaml(parsed) {
    const c = parsed.color || {};
    const s = parsed.surface || {};
    const p = parsed.panel || {};
    return {
      preset: c.preset ?? null,
      levels: c.levels ?? null,
      logScale: !!c.log_scale,
      opacity: s.opacity ?? 1,
      showEdges: !!s.show_edges,
      lighting: s.lighting !== false,
      ambient: s.ambient ?? null,
      diffuse: s.diffuse ?? null,
      specular: s.specular ?? null,
      specularPower: s.specular_power ?? null,
      showBorder: !!p.border,
    };
  }

  function downloadStyleYaml(panel) {
    const blob = new Blob([styleToYaml(panel)], { type: 'text/yaml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${panel.title.replace(/[^\w.-]+/g, '_')}_style.yml`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  // -- Save Camera / Load camera ---------------------------------------
  // Both Save Style and Save Camera live as buttons in the configuration
  // window's own sidebar (renderConfigSidebar, above) rather than as
  // separate Field menu items -- a render panel is a fixed snapshot once
  // it exists, so saving what made it is only ever useful *while still
  // configuring it*, not afterward. Load Camera is there too, for the same
  // reason: only a live vtk.js view -- one that exists only while that
  // window is open -- has a camera to apply one to.

  function cameraToYaml(camera) {
    const fmt = (n) => n.toFixed(6);
    return [
      '# FlexFlow render camera -- position/focalPoint/viewUp for the vtk.js',
      '# view a Field -> Render panel was saved from. Reload it in another',
      '# configuration window\'s "Load camera" to frame a different timestep',
      '# or contour the same way.',
      '',
      `position: [${camera.position.map(fmt).join(', ')}]`,
      `focal_point: [${camera.focalPoint.map(fmt).join(', ')}]`,
      `view_up: [${camera.viewUp.map(fmt).join(', ')}]`,
      '',
    ].join('\n');
  }

  // Narrow reader matching cameraToYaml's own shape -- three top-level
  // `key: [a, b, c]` lines -- same reasoning as parseStyleYaml (this app is
  // self-hosted for an air-gapped compute node; a full YAML library is a
  // real dependency to vendor for a format this small and this controlled).
  function parseCameraYaml(text) {
    const get = (key) => {
      const m = text.match(new RegExp(`^${key}:\\s*\\[([^\\]]*)\\]`, 'm'));
      if (!m) return null;
      const parts = m[1].split(',').map(s => parseFloat(s.trim()));
      if (parts.length !== 3 || parts.some(Number.isNaN)) return null;
      return parts;
    };
    const position = get('position');
    const focalPoint = get('focal_point');
    const viewUp = get('view_up');
    if (!position || !focalPoint || !viewUp) {
      throw new Error('expected position:/focal_point:/view_up: each as [x, y, z]');
    }
    return { position, focalPoint, viewUp };
  }

  function downloadCameraYaml(panel) {
    const blob = new Blob([cameraToYaml(panel.camera)], { type: 'text/yaml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${panel.title.replace(/[^\w.-]+/g, '_')}_camera.yml`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  return { openInfo, openExtract, openRender };
})();
