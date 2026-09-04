// Plot -> Layout... (panel order, column count) and Plot -> Clear panel.
const Layout = (() => {
  function open() {
    const ws = PlotWorkspace.state();
    if (!ws.panels.length) {
      Menu.openDialog(`
        <h2>Plot &rarr; Layout</h2>
        <div class="empty">No panels yet -- Plot &rarr; New first.</div>
        <div class="btn-row"><button id="layout-close">Close</button></div>
      `);
      document.getElementById('layout-close').addEventListener('click', Menu.closeDialog);
      return;
    }
    renderDialog();
  }

  function renderDialog() {
    const ws = PlotWorkspace.state();
    const rows = ws.panels.map(p => `
      <div class="candidate-row layout-row">
        <span class="layout-title">${p.title}</span>
        <span class="layout-move" data-id="${p.id}" data-dir="up" title="Move up">&uarr;</span>
        <span class="layout-move" data-id="${p.id}" data-dir="down" title="Move down">&darr;</span>
      </div>
    `).join('');

    Menu.openDialog(`
      <h2>Plot &rarr; Layout</h2>
      <label for="layout-columns">Columns</label>
      <select id="layout-columns">
        <option value="1" ${ws.layout.columns === 1 ? 'selected' : ''}>1 (stacked)</option>
        <option value="2" ${ws.layout.columns === 2 ? 'selected' : ''}>2</option>
        <option value="3" ${ws.layout.columns === 3 ? 'selected' : ''}>3</option>
      </select>
      <label>Panel order</label>
      <div class="candidate-list">${rows}</div>
      <div class="btn-row"><button id="layout-close">Close</button></div>
    `, { wide: true });

    document.getElementById('layout-close').addEventListener('click', Menu.closeDialog);
    document.getElementById('layout-columns').addEventListener('change', (e) => {
      PlotWorkspace.setColumns(parseInt(e.target.value, 10));
      refreshWorkspace();
    });
    document.querySelectorAll('.layout-move').forEach(el => {
      el.addEventListener('click', () => {
        PlotWorkspace.movePanel(el.dataset.id, el.dataset.dir);
        refreshWorkspace();
        renderDialog();
      });
    });
  }

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

  return { open, openClear };
})();
