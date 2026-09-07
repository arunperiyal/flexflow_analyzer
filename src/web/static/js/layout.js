// Layout -> New/Edit (the canvas size), Layout -> Panes (each panel's own
// position/size on it), and Plot -> Clear panel.
const Layout = (() => {
  function openForm(mode) {
    const ws = PlotWorkspace.state();
    const initial = mode === 'edit' ? ws.layout : { width: 6.5, height: 4.5 };
    const heading = mode === 'edit' ? 'Layout &rarr; Edit' : 'Layout &rarr; New';
    const actionLabel = mode === 'edit' ? 'Save' : 'Create';

    Menu.openDialog(`
      <h2>${heading}</h2>
      <div class="style-limit-row">
        <div>
          <label for="layout-width">Width (in)</label>
          <input type="number" id="layout-width" min="1" step="0.1" value="${initial.width}">
        </div>
        <div>
          <label for="layout-height">Height (in)</label>
          <input type="number" id="layout-height" min="1" step="0.1" value="${initial.height}">
        </div>
      </div>
      <div class="btn-row">
        <button id="layout-cancel">Cancel</button>
        <button id="layout-submit" class="primary">${actionLabel}</button>
      </div>
    `);

    document.getElementById('layout-cancel').addEventListener('click', Menu.closeDialog);
    document.getElementById('layout-submit').addEventListener('click', () => {
      const width = Math.max(1, parseFloat(document.getElementById('layout-width').value) || 6.5);
      const height = Math.max(1, parseFloat(document.getElementById('layout-height').value) || 4.5);
      const spec = { width, height };

      if (mode === 'new') {
        PlotWorkspace.createLayout(spec);
      } else {
        PlotWorkspace.updateLayout(spec);
      }
      refreshWorkspace();
      Menu.closeDialog();
    });
  }

  function openNew() { openForm('new'); }
  function openEdit() { openForm('edit'); }

  // Layout -> Panes: every panel's position/size (inches) on the canvas,
  // typed in directly rather than dragged on the rendered figure -- a
  // to-scale preview on the left mirrors the numbers on the right as they
  // change, so misplacing (or overlapping) a pane is visible immediately.
  const PREVIEW_MAX_PX = 320;

  function openPanes() {
    const ws = PlotWorkspace.state();
    if (!ws.panels.length) {
      Menu.openDialog(`
        <h2>Layout &rarr; Panes</h2>
        <div class="empty">No panels yet -- Plot &rarr; New first.</div>
        <div class="btn-row"><button id="panes-close">Close</button></div>
      `, { wide: true });
      document.getElementById('panes-close').addEventListener('click', Menu.closeDialog);
      return;
    }

    Menu.openDialog(`
      <h2>Layout &rarr; Panes</h2>
      <div class="panes-editor">
        <div id="panes-preview" class="panes-preview"></div>
        <div id="panes-controls" class="panes-controls"></div>
      </div>
      <div class="btn-row"><button id="panes-close" class="primary">Close</button></div>
    `, { wide: true });
    document.getElementById('panes-close').addEventListener('click', Menu.closeDialog);
    renderPanes();
  }

  function renderPanes() {
    const ws = PlotWorkspace.state();
    const preview = document.getElementById('panes-preview');
    const controls = document.getElementById('panes-controls');
    if (!preview || !controls) return;

    const { width, height } = ws.layout;
    const scale = Math.min(PREVIEW_MAX_PX / width, PREVIEW_MAX_PX / height);
    const boxW = width * scale;
    const boxH = height * scale;

    const rects = ws.panels.map((panel, i) => {
      const pane = PlotArea.paneRect(ws, panel);
      const style = `left:${pane.x * scale}px; top:${pane.y * scale}px; ` +
        `width:${Math.max(pane.w * scale, 1)}px; height:${Math.max(pane.h * scale, 1)}px;`;
      const active = panel.id === ws.activePanelId ? ' active' : '';
      return `<div class="pane-preview-rect${active}" style="${style}">${i + 1}</div>`;
    }).join('');
    preview.innerHTML = `<div class="panes-canvas" style="width:${boxW}px; height:${boxH}px;">${rects}</div>`;

    controls.innerHTML = ws.panels.map((panel, i) => {
      const pane = PlotArea.paneRect(ws, panel);
      return `
        <div class="pane-control-row">
          <div class="pane-control-title">${i + 1}. ${panel.title}</div>
          <div class="style-limit-row">
            <div><label>X (in)</label><input type="number" step="0.1" data-id="${panel.id}" data-field="x" value="${pane.x}"></div>
            <div><label>Y (in)</label><input type="number" step="0.1" data-id="${panel.id}" data-field="y" value="${pane.y}"></div>
          </div>
          <div class="style-limit-row">
            <div><label>Width (in)</label><input type="number" step="0.1" min="0.1" data-id="${panel.id}" data-field="w" value="${pane.w}"></div>
            <div><label>Height (in)</label><input type="number" step="0.1" min="0.1" data-id="${panel.id}" data-field="h" value="${pane.h}"></div>
          </div>
        </div>`;
    }).join('');

    controls.querySelectorAll('input').forEach(input => {
      input.addEventListener('change', (e) => {
        const { id, field } = e.target.dataset;
        const raw = parseFloat(e.target.value);
        const value = Number.isFinite(raw) ? raw : 0;
        PlotWorkspace.setPanelPane(id, { [field]: value });
        refreshWorkspace();
        renderPanes();
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

  // The tab strip at the top of the page: one tab per layout, a "+" to
  // create another. Each layout is an independent workspace (panels,
  // canvas, style) -- switching tabs swaps out everything below the strip,
  // which is why refreshWorkspace() re-renders this first.
  function renderTabs() {
    const container = document.getElementById('layout-tabs');
    if (!container) return;
    const layouts = PlotWorkspace.listLayouts();
    const activeId = PlotWorkspace.activeLayoutId();
    container.innerHTML = '';

    for (const l of layouts) {
      const tab = document.createElement('div');
      tab.className = 'layout-tab' + (l.id === activeId ? ' active' : '');

      const label = document.createElement('span');
      label.className = 'layout-tab-label';
      label.textContent = l.name;
      label.title = 'Click to switch -- double-click to rename';
      label.addEventListener('click', () => {
        if (l.id === activeId) return;
        PlotWorkspace.setActiveLayout(l.id);
        refreshWorkspace();
      });
      label.addEventListener('dblclick', () => startRenameTab(tab, label, l));
      tab.appendChild(label);

      // Deleting the last layout has no sane empty state to fall back to
      // (PlotWorkspace.deleteLayout already refuses it), so the control
      // for it is simply not shown rather than present-but-disabled.
      if (layouts.length > 1) {
        const close = document.createElement('span');
        close.className = 'layout-tab-remove';
        close.textContent = '×';
        close.title = 'Delete this layout';
        close.addEventListener('click', (e) => {
          e.stopPropagation();
          PlotWorkspace.deleteLayout(l.id);
          refreshWorkspace();
        });
        tab.appendChild(close);
      }

      container.appendChild(tab);
    }

    const addTab = document.createElement('div');
    addTab.className = 'layout-tab-add';
    addTab.textContent = '+';
    addTab.title = 'New layout';
    addTab.addEventListener('click', openNew);
    container.appendChild(addTab);
  }

  function startRenameTab(tab, labelEl, l) {
    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'layout-tab-edit';
    input.value = l.name;
    input.addEventListener('click', (e) => e.stopPropagation());
    tab.replaceChild(input, labelEl);
    input.focus();
    input.select();

    const commit = () => {
      PlotWorkspace.renameLayout(l.id, input.value);
      refreshWorkspace();
    };
    input.addEventListener('blur', commit);
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') input.blur();
      if (e.key === 'Escape') { input.value = l.name; input.blur(); }
    });
  }

  return { openNew, openEdit, openPanes, openClear, renderTabs };
})();
