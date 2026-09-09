// The Data menu: Info (Table and Stats land here in later phases).
const DataMenu = (() => {
  function escapeHtml(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  async function openInfo() {
    const cases = await App.fetchCases();
    const options = cases
      .map(c => `<option value="${c.name}">${c.name}${c.exists ? '' : ' (missing)'}</option>`)
      .join('');

    Menu.openDialog(`
      <h2>Data &rarr; Info</h2>
      <label for="di-case">Case</label>
      <select id="di-case">
        <option value="">Select a case&hellip;</option>
        ${options}
      </select>
      <div id="di-body"></div>
      <div class="btn-row"><button id="di-close">Close</button></div>
    `, { wide: true });

    document.getElementById('di-close').addEventListener('click', Menu.closeDialog);
    document.getElementById('di-case').addEventListener('change', (e) => loadInfo(e.target.value));
  }

  async function loadInfo(caseName) {
    const body = document.getElementById('di-body');
    if (!caseName) { body.innerHTML = ''; return; }
    body.innerHTML = '<div class="empty">Loading&hellip;</div>';

    const res = await fetch(`/api/cases/${encodeURIComponent(caseName)}/data/info`);
    const data = await res.json();
    if (!document.getElementById('di-body')) return;   // dialog moved on
    if (!res.ok) {
      body.innerHTML = `<div class="error">${escapeHtml(data.error || 'could not load this case')}</div>`;
      return;
    }
    body.innerHTML = renderInfo(data);
  }

  function renderKindSection(kind, label, info) {
    if (!info) {
      return `<h3>${label}</h3><div class="empty">no ${kind}_files/ in this case</div>`;
    }
    const groupRows = info.groups.map(g => `
      <tr><td>${info.group_label} ${g.group}</td><td>${g.nodes} node${g.nodes === 1 ? '' : 's'}</td></tr>
    `).join('');

    const alignment = info.plt_alignment
      ? `<tr><td>tsId every ${info.plt_alignment.freq}</td>
          <td>${info.plt_alignment.min} .. ${info.plt_alignment.max}
              <span class="empty">(${info.plt_alignment.count} with a PLT)</span></td></tr>`
      : '';

    const varRows = info.groups.flatMap(g => g.variables.map(v => `
      <tr>
        <td>${escapeHtml(v.name)}</td>
        <td>${v.ncomp}</td>
        <td>${escapeHtml(v.columns.join(', '))}</td>
        <td>${escapeHtml(v.short || '')}</td>
      </tr>
    `)).join('');

    return `
      <h3>${label}</h3>
      <table class="info-table">
        <tr><td>Files</td><td>${info.files}</td></tr>
        ${groupRows}
        <tr><td>Timesteps</td><td>${info.timesteps}</td></tr>
        <tr><td>Time</td><td>${info.time_min.toPrecision(6)} .. ${info.time_max.toPrecision(6)}</td></tr>
        <tr><td>tsId</td><td>${info.tsid_min} .. ${info.tsid_max}</td></tr>
        ${alignment}
      </table>
      <table class="info-table">
        <tr><th>Variable</th><th>Components</th><th>Columns</th><th>Short</th></tr>
        ${varRows}
      </table>
    `;
  }

  function renderInfo(data) {
    const warning = data.warning
      ? `<div class="error">${escapeHtml(data.warning)}</div>` : '';
    return `
      ${warning}
      ${renderKindSection('othd', 'OTHD', data.othd)}
      ${renderKindSection('oisd', 'OISD', data.oisd)}
    `;
  }

  return { openInfo };
})();
