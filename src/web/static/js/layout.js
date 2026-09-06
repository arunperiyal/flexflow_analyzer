// Layout -> New/Edit (the grid's shape and overall size) and
// Plot -> Clear panel.
const Layout = (() => {
  function openForm(mode) {
    const ws = PlotWorkspace.state();
    const current = mode === 'edit' ? ws.layout : { rows: 1, columns: 1, width: null, height: null };
    const heading = mode === 'edit' ? 'Layout &rarr; Edit' : 'Layout &rarr; New';
    const actionLabel = mode === 'edit' ? 'Save' : 'Create';
    // A brand new grid clears every panel's pane (see
    // PlotWorkspace.setLayout) -- panels/traces aren't touched, they just
    // fall back to auto-placement, so this is a note, not a confirm()
    // gate: nothing is actually destroyed.
    const resetNote = (mode === 'new' && ws.panels.length)
      ? `<div class="empty">This resets every panel's pane -- they fall back to auto-placement in the new grid.</div>`
      : '';

    Menu.openDialog(`
      <h2>${heading}</h2>
      <div class="style-limit-row">
        <div>
          <label for="layout-rows">Rows</label>
          <input type="number" id="layout-rows" min="1" max="12" value="${current.rows}">
        </div>
        <div>
          <label for="layout-columns">Columns</label>
          <input type="number" id="layout-columns" min="1" max="12" value="${current.columns}">
        </div>
      </div>
      <div class="style-limit-row">
        <div>
          <label for="layout-width">Width (px)</label>
          <input type="number" id="layout-width" placeholder="auto" min="200" value="${current.width ?? ''}">
        </div>
        <div>
          <label for="layout-height">Height (px)</label>
          <input type="number" id="layout-height" placeholder="auto" min="150" value="${current.height ?? ''}">
        </div>
      </div>
      ${resetNote}
      <div class="btn-row">
        <button id="layout-cancel">Cancel</button>
        <button id="layout-submit" class="primary">${actionLabel}</button>
      </div>
    `, { wide: true });

    document.getElementById('layout-cancel').addEventListener('click', Menu.closeDialog);
    document.getElementById('layout-submit').addEventListener('click', () => {
      const rows = Math.max(1, parseInt(document.getElementById('layout-rows').value, 10) || 1);
      const columns = Math.max(1, parseInt(document.getElementById('layout-columns').value, 10) || 1);
      const widthRaw = document.getElementById('layout-width').value.trim();
      const heightRaw = document.getElementById('layout-height').value.trim();
      const width = widthRaw === '' ? null : parseInt(widthRaw, 10);
      const height = heightRaw === '' ? null : parseInt(heightRaw, 10);
      const spec = { rows, columns, width, height };

      if (mode === 'new') {
        PlotWorkspace.setLayout(spec);
      } else {
        PlotWorkspace.updateLayout(spec);
      }
      refreshWorkspace();
      Menu.closeDialog();
    });
  }

  function openNew() { openForm('new'); }
  function openEdit() { openForm('edit'); }

  function openClear() {
    const ws = PlotWorkspace.state();
    if (!ws.panels.length) {
      Menu.openDialog(`
        <h2>Plot &rarr; Clear panel</h2>
        <div class="empty">No panels yet.</div>
        <div class="btn-row"><button id="clear-close">Close</button></div>
      `);
      document.getElementById('clear-close').addEventListener('click', Menu.closeDialog);
      return;
    }

    const options = ws.panels
      .map(p => `<option value="${p.id}">${p.title} (${p.traces.length} trace(s))</option>`)
      .join('');

    Menu.openDialog(`
      <h2>Plot &rarr; Clear panel</h2>
      <label for="clear-panel">Panel</label>
      <select id="clear-panel">${options}</select>
      <div class="btn-row">
        <button id="clear-cancel">Cancel</button>
        <button id="clear-go" class="primary">Clear</button>
      </div>
    `);
    document.getElementById('clear-cancel').addEventListener('click', Menu.closeDialog);
    document.getElementById('clear-go').addEventListener('click', () => {
      PlotWorkspace.clearPanel(document.getElementById('clear-panel').value);
      refreshWorkspace();
      Menu.closeDialog();
    });
  }

  return { openNew, openEdit, openClear };
})();
