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

  // -- Table -----------------------------------------------------------------
  // The on-screen values are exactly what /history already returns for one
  // node -- no new read endpoint, just a dialog that fetches it and renders
  // an HTML table instead of a Plotly trace. Unlike the CLI's terminal-width
  // head/tail, the whole table just scrolls (a browser table handles a few
  // thousand rows fine), so there is no separate "show more" step -- Download
  // CSV covers what --output covered on the CLI side.

  let tableRows = null;   // the last-loaded {columns, rows} -- what Download CSV writes

  async function openTable() {
    const cases = await App.fetchCases();
    const options = cases
      .map(c => `<option value="${c.name}">${c.name}${c.exists ? '' : ' (missing)'}</option>`)
      .join('');
    tableRows = null;

    Menu.openDialog(`
      <h2>Data &rarr; Table</h2>
      <label for="dt-case">Case</label>
      <select id="dt-case">
        <option value="">Select a case&hellip;</option>
        ${options}
      </select>
      <div id="dt-form"></div>
      <div id="dt-result"></div>
      <div class="btn-row"><button id="dt-close">Close</button></div>
    `, { wide: true });

    document.getElementById('dt-close').addEventListener('click', Menu.closeDialog);
    document.getElementById('dt-case').addEventListener('change', (e) => onTableCaseChange(e.target.value));
  }

  async function onTableCaseChange(caseName) {
    const form = document.getElementById('dt-form');
    document.getElementById('dt-result').innerHTML = '';
    tableRows = null;
    if (!caseName) { form.innerHTML = ''; return; }

    form.innerHTML = '<div class="empty">Loading&hellip;</div>';
    const res = await fetch(`/api/cases/${encodeURIComponent(caseName)}/data/info`);
    const info = await res.json();
    if (!document.getElementById('dt-form')) return;
    if (!res.ok) {
      form.innerHTML = `<div class="error">${escapeHtml(info.error || 'could not load this case')}</div>`;
      return;
    }
    renderTableForm(caseName, info);
  }

  function renderTableForm(caseName, info) {
    const form = document.getElementById('dt-form');
    const kinds = ['othd', 'oisd'].filter(k => info[k]);
    if (!kinds.length) {
      form.innerHTML = '<div class="error">No othd/oisd data in this case.</div>';
      return;
    }
    const kindRow = kinds.length > 1 ? `
      <label>Kind</label>
      <div class="plot-kind-row">
        ${kinds.map((k, i) => `
          <label class="var-check">
            <input type="radio" name="dt-kind" value="${k}" ${i === 0 ? 'checked' : ''}> ${k.toUpperCase()}
          </label>
        `).join('')}
      </div>
    ` : `<input type="hidden" id="dt-kind-fixed" value="${kinds[0]}">`;

    form.innerHTML = `${kindRow}<div id="dt-kind-body"></div>`;
    document.querySelectorAll('input[name="dt-kind"]').forEach(r =>
      r.addEventListener('change', () => renderKindBody(caseName, info, currentTableKind())));
    renderKindBody(caseName, info, currentTableKind());
  }

  function currentTableKind() {
    const checked = document.querySelector('input[name="dt-kind"]:checked');
    if (checked) return checked.value;
    const fixed = document.getElementById('dt-kind-fixed');
    return fixed ? fixed.value : 'othd';
  }

  function renderKindBody(caseName, info, kind) {
    const box = document.getElementById('dt-kind-body');
    const kindInfo = info[kind];
    if (!box || !kindInfo) return;

    const groupOptions = kindInfo.groups.map(g => `
      <option value="${g.group}">${kindInfo.group_label} ${g.group} (${g.nodes} node${g.nodes === 1 ? '' : 's'})</option>
    `).join('');

    box.innerHTML = `
      <label for="dt-group">${kindInfo.group_label}</label>
      <select id="dt-group">${groupOptions}</select>
      <label for="dt-node">Node</label>
      <input type="number" id="dt-node" min="0" value="0" step="1">
      <label>Variables</label>
      <div id="dt-var-list" class="var-list"></div>
      <label>Time window (optional)</label>
      <div class="coord-inputs">
        <input type="text" id="dt-t1" placeholder="t1 (blank = start)">
        <input type="text" id="dt-t2" placeholder="t2 (blank = end)">
      </div>
      <div class="btn-row"><button id="dt-load" class="primary" disabled>Load table</button></div>
    `;

    document.getElementById('dt-group').addEventListener('change', () => renderVarList(kindInfo));
    document.getElementById('dt-load').addEventListener('click', () =>
      loadTable(caseName, kind, kindInfo.group_label));
    renderVarList(kindInfo);
  }

  function renderVarList(kindInfo) {
    const groupSel = document.getElementById('dt-group');
    const list = document.getElementById('dt-var-list');
    const nodeInput = document.getElementById('dt-node');
    if (!groupSel || !list) return;
    const group = kindInfo.groups.find(g => String(g.group) === groupSel.value);
    if (!group) return;
    nodeInput.max = String(Math.max(0, group.nodes - 1));

    const cols = group.variables.flatMap(v => v.columns);
    list.innerHTML = cols.map(c => `
      <label class="var-check"><input type="checkbox" class="dt-column" value="${c}"> ${c}</label>
    `).join('');
    document.querySelectorAll('.dt-column').forEach(cb => cb.addEventListener('change', updateTableLoadButton));
    updateTableLoadButton();
  }

  function updateTableLoadButton() {
    const btn = document.getElementById('dt-load');
    if (btn) btn.disabled = document.querySelectorAll('.dt-column:checked').length === 0;
  }

  async function loadTable(caseName, kind, groupLabel) {
    const result = document.getElementById('dt-result');
    const group = document.getElementById('dt-group').value;
    const node = parseInt(document.getElementById('dt-node').value, 10) || 0;
    const columns = Array.from(document.querySelectorAll('.dt-column:checked')).map(cb => cb.value);
    if (!columns.length) return;

    result.innerHTML = '<div class="empty">Loading&hellip;</div>';
    const params = new URLSearchParams({ group, columns: columns.join(','), rows: String(node), kind });
    const res = await fetch(`/api/cases/${encodeURIComponent(caseName)}/history?${params}`);
    const data = await res.json();
    if (!document.getElementById('dt-result')) return;
    if (!res.ok) {
      result.innerHTML = `<div class="error">${escapeHtml(data.error || 'could not load history')}</div>`;
      return;
    }

    const t1raw = document.getElementById('dt-t1').value.trim();
    const t2raw = document.getElementById('dt-t2').value.trim();
    const t1 = t1raw === '' ? null : parseFloat(t1raw);
    const t2 = t2raw === '' ? null : parseFloat(t2raw);

    const times = data.times;
    const indices = times.map((_, i) => i)
      .filter(i => (t1 == null || times[i] >= t1) && (t2 == null || times[i] <= t2));
    const rows = indices.map(i => {
      const row = { time: times[i] };
      for (const s of data.series) row[s.column] = s.values[i];
      return row;
    });
    tableRows = { columns, rows };

    result.innerHTML = renderTableHtml(kind, groupLabel, group, node, columns, rows);
    const dl = document.getElementById('dt-download');
    if (dl) dl.addEventListener('click', () => downloadTableCsv(caseName));
  }

  function renderTableHtml(kind, groupLabel, group, node, columns, rows) {
    const header = `<tr><th>time</th>${columns.map(c => `<th>${escapeHtml(c)}</th>`).join('')}</tr>`;
    const body = rows.map(r => `
      <tr><td>${r.time.toPrecision(6)}</td>${columns.map(c => `<td>${r[c].toExponential(6)}</td>`).join('')}</tr>
    `).join('');

    return `
      <div class="empty">${kind} | ${groupLabel} ${group} | node ${node} | ${rows.length} row(s)</div>
      <div class="table-scroll"><table class="info-table">${header}${body}</table></div>
      <div class="btn-row"><button id="dt-download">Download CSV</button></div>
    `;
  }

  function downloadTableCsv(caseName) {
    if (!tableRows) return;
    const { columns, rows } = tableRows;
    const header = ['time', ...columns].join(',');
    const lines = rows.map(r => [r.time, ...columns.map(c => r[c])].join(','));
    const blob = new Blob([[header, ...lines].join('\n')], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${caseName}_table.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  // -- Stats -------------------------------------------------------------
  // Reductions (min/max/mean/rms/std/range) over a tsId window, plus the two
  // "locator" functions that point at *which PLT file* best captures an
  // extreme or a zero crossing -- the web equivalent of `data stats`
  // (src/commands/data/stats_impl/command.py), computed by
  // services/data_stats.py. The window here is tsId-based (not time-based
  // like Table's), matching data stats --t1/--t2: a locator's answer is
  // already in the units of a PLT filename, and the window that finds it
  // should be too.

  const STAT_FUNCS = [
    ['min', 'Min'], ['max', 'Max'], ['mean', 'Mean'], ['rms', 'RMS'],
    ['std', 'Std dev'], ['range', 'Range'],
    ['maxloc', 'Max + PLT frame'], ['minloc', 'Min + PLT frame'],
    ['zeroloc', 'Zero crossing + PLT frame'],
  ];

  async function openStats() {
    const cases = await App.fetchCases();
    const options = cases
      .map(c => `<option value="${c.name}">${c.name}${c.exists ? '' : ' (missing)'}</option>`)
      .join('');

    Menu.openDialog(`
      <h2>Data &rarr; Stats</h2>
      <label for="ds-case">Case</label>
      <select id="ds-case">
        <option value="">Select a case&hellip;</option>
        ${options}
      </select>
      <div id="ds-form"></div>
      <div id="ds-result"></div>
      <div class="btn-row"><button id="ds-close">Close</button></div>
    `, { wide: true });

    document.getElementById('ds-close').addEventListener('click', Menu.closeDialog);
    document.getElementById('ds-case').addEventListener('change', (e) => onStatsCaseChange(e.target.value));
  }

  async function onStatsCaseChange(caseName) {
    const form = document.getElementById('ds-form');
    document.getElementById('ds-result').innerHTML = '';
    if (!caseName) { form.innerHTML = ''; return; }

    form.innerHTML = '<div class="empty">Loading&hellip;</div>';
    const res = await fetch(`/api/cases/${encodeURIComponent(caseName)}/data/info`);
    const info = await res.json();
    if (!document.getElementById('ds-form')) return;
    if (!res.ok) {
      form.innerHTML = `<div class="error">${escapeHtml(info.error || 'could not load this case')}</div>`;
      return;
    }
    renderStatsForm(caseName, info);
  }

  function renderStatsForm(caseName, info) {
    const form = document.getElementById('ds-form');
    const kinds = ['othd', 'oisd'].filter(k => info[k]);
    if (!kinds.length) {
      form.innerHTML = '<div class="error">No othd/oisd data in this case.</div>';
      return;
    }
    const kindRow = kinds.length > 1 ? `
      <label>Kind</label>
      <div class="plot-kind-row">
        ${kinds.map((k, i) => `
          <label class="var-check">
            <input type="radio" name="ds-kind" value="${k}" ${i === 0 ? 'checked' : ''}> ${k.toUpperCase()}
          </label>
        `).join('')}
      </div>
    ` : `<input type="hidden" id="ds-kind-fixed" value="${kinds[0]}">`;

    form.innerHTML = `${kindRow}<div id="ds-kind-body"></div>`;
    document.querySelectorAll('input[name="ds-kind"]').forEach(r =>
      r.addEventListener('change', () => renderStatsKindBody(caseName, info, currentStatsKind())));
    renderStatsKindBody(caseName, info, currentStatsKind());
  }

  function currentStatsKind() {
    const checked = document.querySelector('input[name="ds-kind"]:checked');
    if (checked) return checked.value;
    const fixed = document.getElementById('ds-kind-fixed');
    return fixed ? fixed.value : 'othd';
  }

  function renderStatsKindBody(caseName, info, kind) {
    const box = document.getElementById('ds-kind-body');
    const kindInfo = info[kind];
    if (!box || !kindInfo) return;

    const groupOptions = kindInfo.groups.map(g => `
      <option value="${g.group}">${kindInfo.group_label} ${g.group} (${g.nodes} node${g.nodes === 1 ? '' : 's'})</option>
    `).join('');
    const funcRow = STAT_FUNCS.map(([id, label]) => `
      <label class="var-check"><input type="checkbox" class="ds-func" value="${id}"> ${label}</label>
    `).join('');

    box.innerHTML = `
      <label for="ds-group">${kindInfo.group_label}</label>
      <select id="ds-group">${groupOptions}</select>
      <label for="ds-node">Node</label>
      <input type="number" id="ds-node" min="0" value="0" step="1">
      <label>Variables</label>
      <div id="ds-var-list" class="var-list"></div>
      <label>Functions</label>
      <div class="var-list">${funcRow}</div>
      <label>tsId window (optional)</label>
      <div class="coord-inputs">
        <input type="text" id="ds-t1" placeholder="t1 (blank = start)">
        <input type="text" id="ds-t2" placeholder="t2 (blank = end)">
      </div>
      <div class="btn-row"><button id="ds-go" class="primary" disabled>Compute stats</button></div>
    `;

    document.getElementById('ds-group').addEventListener('change', () => renderStatsVarList(kindInfo));
    document.querySelectorAll('.ds-func').forEach(cb => cb.addEventListener('change', updateStatsGoButton));
    document.getElementById('ds-go').addEventListener('click', () =>
      computeStats(caseName, kind, kindInfo.group_label));
    renderStatsVarList(kindInfo);
  }

  function renderStatsVarList(kindInfo) {
    const groupSel = document.getElementById('ds-group');
    const list = document.getElementById('ds-var-list');
    const nodeInput = document.getElementById('ds-node');
    if (!groupSel || !list) return;
    const group = kindInfo.groups.find(g => String(g.group) === groupSel.value);
    if (!group) return;
    nodeInput.max = String(Math.max(0, group.nodes - 1));

    const cols = group.variables.flatMap(v => v.columns);
    list.innerHTML = cols.map(c => `
      <label class="var-check"><input type="checkbox" class="ds-column" value="${c}"> ${c}</label>
    `).join('');
    document.querySelectorAll('.ds-column').forEach(cb => cb.addEventListener('change', updateStatsGoButton));
    updateStatsGoButton();
  }

  function updateStatsGoButton() {
    const btn = document.getElementById('ds-go');
    if (!btn) return;
    const anyColumn = document.querySelectorAll('.ds-column:checked').length > 0;
    const anyFunc = document.querySelectorAll('.ds-func:checked').length > 0;
    btn.disabled = !(anyColumn && anyFunc);
  }

  async function computeStats(caseName, kind, groupLabel) {
    const result = document.getElementById('ds-result');
    const group = document.getElementById('ds-group').value;
    const node = document.getElementById('ds-node').value;
    const columns = Array.from(document.querySelectorAll('.ds-column:checked')).map(cb => cb.value);
    const funcs = Array.from(document.querySelectorAll('.ds-func:checked')).map(cb => cb.value);
    if (!columns.length || !funcs.length) return;

    result.innerHTML = '<div class="empty">Loading&hellip;</div>';
    const params = new URLSearchParams({
      group, node, kind, columns: columns.join(','), funcs: funcs.join(','),
    });
    const t1 = document.getElementById('ds-t1').value.trim();
    const t2 = document.getElementById('ds-t2').value.trim();
    if (t1 !== '') params.set('t1', t1);
    if (t2 !== '') params.set('t2', t2);

    const res = await fetch(`/api/cases/${encodeURIComponent(caseName)}/data/stats?${params}`);
    const data = await res.json();
    if (!document.getElementById('ds-result')) return;
    if (!res.ok) {
      result.innerHTML = `<div class="error">${escapeHtml(data.error || 'could not compute stats')}</div>`;
      return;
    }
    result.innerHTML = renderStatsResult(kind, groupLabel, data);
  }

  function runnersUp(ranked) {
    const rest = ranked.slice(1);
    if (!rest.length) return '-';
    return rest.map(([ts, v]) => `${ts} (${v.toExponential(3)})`).join(', ');
  }

  function renderStatsResult(kind, groupLabel, data) {
    const header = `<div class="empty">${kind} | ${groupLabel} ${data.group} | node ${data.node} | `
      + `tsId ${data.tsid_min}..${data.tsid_max} (${data.steps} step(s))</div>`;

    let valueTable = '';
    if (data.values.length && Object.keys(data.values[0]).length > 1) {
      const funcNames = Object.keys(data.values[0]).filter(k => k !== 'column');
      valueTable = `
        <table class="info-table">
          <tr><th>Variable</th>${funcNames.map(f => `<th>${f}</th>`).join('')}</tr>
          ${data.values.map(row => `
            <tr><td>${escapeHtml(row.column)}</td>${funcNames.map(f => `<td>${row[f].toPrecision(6)}</td>`).join('')}</tr>
          `).join('')}
        </table>
      `;
    }

    const locTable = (rows, word) => rows.length ? `
      <h3>${word} -- the extreme, and which PLT file comes closest to it</h3>
      <table class="info-table">
        <tr><th>Variable</th><th>${word}</th><th>at tsId</th><th>time</th>
            <th>PLT to open</th><th>value there</th><th>runners-up</th></tr>
        ${rows.map(r => `
          <tr>
            <td>${escapeHtml(r.column)}</td><td>${r.value.toExponential(6)}</td>
            <td>${r.tsId}</td><td>${r.time.toPrecision(6)}</td>
            <td>${r.plt_tsId ?? '-'}</td>
            <td>${r.plt_value != null ? r.plt_value.toExponential(6) : '-'}</td>
            <td>${runnersUp(r.plt_ranked)}</td>
          </tr>
        `).join('')}
      </table>
    ` : '';

    const zeroTable = data.zeroloc && data.zeroloc.length ? `
      <h3>zeroloc -- the zero crossing best caught by a PLT file</h3>
      <table class="info-table">
        <tr><th>Variable</th><th>direction</th><th>crossing tsId</th><th>time</th><th>value</th>
            <th>PLT to open</th><th>value there</th><th>runners-up</th></tr>
        ${data.zeroloc.map(r => r.count ? `
          <tr>
            <td>${escapeHtml(r.column)}</td><td>${r.direction}</td>
            <td>${r.tsId}</td><td>${r.time.toPrecision(6)}</td><td>${r.value.toExponential(6)}</td>
            <td>${r.plt_tsId ?? '-'}</td>
            <td>${r.plt_value != null ? r.plt_value.toExponential(6) : '-'}</td>
            <td>${runnersUp(r.plt_ranked)}</td>
          </tr>
        ` : `
          <tr><td>${escapeHtml(r.column)}</td><td>${r.direction}</td>
              <td colspan="6" class="empty">never crosses zero in this window</td></tr>
        `).join('')}
      </table>
    ` : '';

    return header + valueTable + locTable(data.maxloc || [], 'maxloc')
      + locTable(data.minloc || [], 'minloc') + zeroTable;
  }

  return { openInfo, openTable, openStats };
})();
