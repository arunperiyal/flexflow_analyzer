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

  return { openInfo };
})();
