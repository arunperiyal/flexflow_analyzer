// Layout -> New/Edit (the grid's shape and overall size) and
// Plot -> Clear panel.
const Layout = (() => {
  // Does `rect` cut across an existing area (overlap it without fully
  // containing it)? A rect that fully contains an area is fine -- merging
  // absorbs it into the bigger block -- but one that only partially
  // overlaps would leave that area straddling two panes, which has no
  // sane rendering.
  function overlapsPartially(rect, areas) {
    return areas.some(a => {
      const overlaps = a.row < rect.row + rect.rowSpan && rect.row < a.row + a.rowSpan &&
                        a.col < rect.col + rect.colSpan && rect.col < a.col + a.colSpan;
      if (!overlaps) return false;
      const rectContainsArea = rect.row <= a.row && rect.col <= a.col &&
                                rect.row + rect.rowSpan >= a.row + a.rowSpan &&
                                rect.col + rect.colSpan >= a.col + a.colSpan;
      return !rectContainsArea;
    });
  }

  function sameRect(a, b) {
    return a.row === b.row && a.col === b.col && a.rowSpan === b.rowSpan && a.colSpan === b.colSpan;
  }

  function openForm(mode) {
    const ws = PlotWorkspace.state();
    const initial = mode === 'edit' ? ws.layout : { rows: 1, columns: 1, width: null, height: null, areas: [] };
    const state = {
      rows: initial.rows,
      columns: initial.columns,
      areas: (initial.areas || []).map(a => ({ ...a })),
      selection: null,   // {row, col, rowSpan, colSpan} -- a drag rectangle, or an existing area picked for splitting
    };
    let dragAnchor = null;

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
          <input type="number" id="layout-rows" min="1" max="12" value="${state.rows}">
        </div>
        <div>
          <label for="layout-columns">Columns</label>
          <input type="number" id="layout-columns" min="1" max="12" value="${state.columns}">
        </div>
      </div>
      <div class="style-limit-row">
        <div>
          <label for="layout-width">Width (px)</label>
          <input type="number" id="layout-width" placeholder="auto" min="200" value="${initial.width ?? ''}">
        </div>
        <div>
          <label for="layout-height">Height (px)</label>
          <input type="number" id="layout-height" placeholder="auto" min="150" value="${initial.height ?? ''}">
        </div>
      </div>
      <label>Drag across cells to merge them into one pane -- click an already-merged block to split it back apart.</label>
      <div id="layout-grid-editor"></div>
      <div class="btn-row-left">
        <button id="layout-merge" disabled>Merge selected</button>
        <button id="layout-split" disabled>Split</button>
      </div>
      ${resetNote}
      <div class="btn-row">
        <button id="layout-cancel">Cancel</button>
        <button id="layout-submit" class="primary">${actionLabel}</button>
      </div>
    `, { wide: true });

    const gridBox = document.getElementById('layout-grid-editor');
    const mergeBtn = document.getElementById('layout-merge');
    const splitBtn = document.getElementById('layout-split');

    function areaAt(row, col) {
      return state.areas.find(a => row >= a.row && row < a.row + a.rowSpan &&
                                    col >= a.col && col < a.col + a.colSpan) || null;
    }

    function rectFromDrag(a, b) {
      return {
        row: Math.min(a.row, b.row), col: Math.min(a.col, b.col),
        rowSpan: Math.abs(a.row - b.row) + 1, colSpan: Math.abs(a.col - b.col) + 1,
      };
    }

    function renderGridStructure() {
      let html = '';
      for (let r = 0; r < state.rows; r++) {
        for (let c = 0; c < state.columns; c++) {
          html += `<div class="layout-unit-cell" data-row="${r}" data-col="${c}"
            style="grid-row:${r + 1}; grid-column:${c + 1};"></div>`;
        }
      }
      for (const a of state.areas) {
        html += `<div class="layout-merge-overlay"
          style="grid-row:${a.row + 1} / span ${a.rowSpan}; grid-column:${a.col + 1} / span ${a.colSpan};">merged</div>`;
      }
      html += `<div id="layout-selection-overlay" class="layout-selection-overlay" hidden></div>`;
      gridBox.innerHTML = html;
      gridBox.style.gridTemplateRows = `repeat(${state.rows}, 34px)`;
      gridBox.style.gridTemplateColumns = `repeat(${state.columns}, 40px)`;
      updateSelectionOverlay();
    }

    function updateSelectionOverlay() {
      const overlay = document.getElementById('layout-selection-overlay');
      if (!overlay) return;
      if (!state.selection) {
        overlay.hidden = true;
        return;
      }
      overlay.hidden = false;
      overlay.style.gridRow = `${state.selection.row + 1} / span ${state.selection.rowSpan}`;
      overlay.style.gridColumn = `${state.selection.col + 1} / span ${state.selection.colSpan}`;
    }

    function updateButtons() {
      const rect = state.selection;
      const isSingleExisting = !!rect && state.areas.some(a => sameRect(a, rect));
      const canMerge = !!rect && (rect.rowSpan > 1 || rect.colSpan > 1) &&
                        !isSingleExisting && !overlapsPartially(rect, state.areas);
      mergeBtn.disabled = !canMerge;
      splitBtn.disabled = !isSingleExisting;
    }

    function setSelection(rect) {
      state.selection = rect;
      updateSelectionOverlay();
      updateButtons();
    }

    gridBox.addEventListener('mousedown', (e) => {
      const cell = e.target.closest('.layout-unit-cell');
      if (!cell) return;
      e.preventDefault();
      dragAnchor = { row: Number(cell.dataset.row), col: Number(cell.dataset.col) };
      setSelection(rectFromDrag(dragAnchor, dragAnchor));
    });
    gridBox.addEventListener('mouseover', (e) => {
      if (!dragAnchor) return;
      const cell = e.target.closest('.layout-unit-cell');
      if (!cell) return;
      setSelection(rectFromDrag(dragAnchor, { row: Number(cell.dataset.row), col: Number(cell.dataset.col) }));
    });
    // A plain click (drag never left its starting cell) landing inside an
    // existing merged area re-targets the selection at that whole area --
    // a Split candidate -- rather than leaving it as a bare 1x1 selection.
    function onDocMouseUp() {
      if (!dragAnchor) return;
      dragAnchor = null;
      const rect = state.selection;
      if (rect && rect.rowSpan === 1 && rect.colSpan === 1) {
        const existing = areaAt(rect.row, rect.col);
        if (existing) setSelection({ ...existing });
      }
    }
    document.addEventListener('mouseup', onDocMouseUp);

    mergeBtn.addEventListener('click', () => {
      const rect = state.selection;
      if (!rect) return;
      // A smaller area fully inside the new rectangle is absorbed into it
      // rather than left behind as a stale, now-overlapping merge.
      state.areas = state.areas.filter(a => !(rect.row <= a.row && rect.col <= a.col &&
        rect.row + rect.rowSpan >= a.row + a.rowSpan && rect.col + rect.colSpan >= a.col + a.colSpan));
      state.areas.push({ row: rect.row, col: rect.col, rowSpan: rect.rowSpan, colSpan: rect.colSpan });
      setSelection(null);
      renderGridStructure();
    });

    splitBtn.addEventListener('click', () => {
      const rect = state.selection;
      if (!rect) return;
      state.areas = state.areas.filter(a => !sameRect(a, rect));
      setSelection(null);
      renderGridStructure();
    });

    function onDimsChange() {
      state.rows = Math.max(1, Math.min(12, parseInt(document.getElementById('layout-rows').value, 10) || 1));
      state.columns = Math.max(1, Math.min(12, parseInt(document.getElementById('layout-columns').value, 10) || 1));
      state.areas = PlotArea.clampAreas(state.areas, state.rows, state.columns);
      setSelection(null);
      renderGridStructure();
    }
    document.getElementById('layout-rows').addEventListener('change', onDimsChange);
    document.getElementById('layout-columns').addEventListener('change', onDimsChange);

    function cleanup() {
      document.removeEventListener('mouseup', onDocMouseUp);
    }

    document.getElementById('layout-cancel').addEventListener('click', () => {
      cleanup();
      Menu.closeDialog();
    });
    document.getElementById('layout-submit').addEventListener('click', () => {
      const widthRaw = document.getElementById('layout-width').value.trim();
      const heightRaw = document.getElementById('layout-height').value.trim();
      const width = widthRaw === '' ? null : parseInt(widthRaw, 10);
      const height = heightRaw === '' ? null : parseInt(heightRaw, 10);
      const spec = { rows: state.rows, columns: state.columns, width, height, areas: state.areas };

      if (mode === 'new') {
        PlotWorkspace.setLayout(spec);
      } else {
        PlotWorkspace.updateLayout(spec);
      }
      cleanup();
      refreshWorkspace();
      Menu.closeDialog();
    });

    renderGridStructure();
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
