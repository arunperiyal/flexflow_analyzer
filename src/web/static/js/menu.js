// Menu bar dropdowns and the Case → Add / Delete dialogs.
const Menu = (() => {
  function closeAll() {
    document.querySelectorAll('.menu-item.open').forEach(el => el.classList.remove('open'));
  }

  function wireMenuBar() {
    document.querySelectorAll('.menu-item[data-menu]').forEach(item => {
      item.addEventListener('click', (e) => {
        if (e.target.closest('.menu-option')) return;
        const wasOpen = item.classList.contains('open');
        closeAll();
        if (!wasOpen) item.classList.add('open');
      });
    });
    document.addEventListener('click', (e) => {
      if (!e.target.closest('.menu-item')) closeAll();
    });
  }

  function openDialog(html, opts) {
    opts = opts || {};
    const backdrop = document.getElementById('dialog-backdrop');
    const dialog = document.getElementById('dialog');
    dialog.innerHTML = html;
    dialog.classList.toggle('wide', !!opts.wide);
    backdrop.hidden = false;
  }

  function closeDialog() {
    document.getElementById('dialog-backdrop').hidden = true;
  }

  function wireAddDialog(root) {
    document.getElementById('case-add').addEventListener('click', () => {
      closeAll();
      openDialog(`
        <h2>Case &rarr; Add</h2>
        <label for="scan-dir">Directory to scan</label>
        <input type="text" id="scan-dir" value="${root}">
        <div id="dir-breadcrumbs" class="dir-breadcrumbs"></div>
        <div id="dir-browser-list" class="candidate-list"></div>
        <div id="scan-error"></div>
        <div class="btn-row">
          <button id="scan-cancel">Cancel</button>
          <button id="scan-go" class="primary">Scan</button>
        </div>
      `, { wide: true });
      document.getElementById('scan-cancel').addEventListener('click', closeDialog);
      document.getElementById('scan-go').addEventListener('click', runScan);
      document.getElementById('scan-dir').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') { e.preventDefault(); browseTo(e.target.value.trim()); }
      });
      browseTo(root);
    });
  }

  // Case -> Add's directory browser: click a subdirectory to step into it,
  // click a breadcrumb segment to jump back up to it -- an alternative to
  // typing the exact absolute path from memory, which the text field
  // above still takes directly (Enter re-browses to whatever's typed), so
  // pasting a known path still works exactly as before.
  function renderBreadcrumbs(dir) {
    const parts = dir.split('/').filter(Boolean);
    let acc = '';
    const segments = [{ label: '/', path: '/' }];
    for (const part of parts) {
      acc += `/${part}`;
      segments.push({ label: part, path: acc });
    }
    return segments.map((seg, i) => {
      const isLast = i === segments.length - 1;
      const cls = 'dir-breadcrumb-seg' + (isLast ? ' current' : '');
      const sep = isLast ? '' : '<span class="dir-breadcrumb-sep">/</span>';
      return `<span class="${cls}" data-path="${seg.path}">${seg.label}</span>${sep}`;
    }).join('');
  }

  async function browseTo(dir) {
    const list = document.getElementById('dir-browser-list');
    if (!list) return;   // the dialog moved on (Scan clicked, or closed) while this was in flight
    list.innerHTML = '<div class="candidate-row empty">Loading&hellip;</div>';
    const res = await fetch(`/api/cases/browse?dir=${encodeURIComponent(dir)}`);
    const data = await res.json();
    // Re-check after the await -- the dialog can easily have moved on by
    // the time this resolves (Scan clicked, Cancel, or a faster second
    // browseTo already landed from clicking around quickly).
    if (!document.getElementById('dir-browser-list')) return;
    const errBox = document.getElementById('scan-error');
    if (!res.ok) {
      errBox.innerHTML = `<div class="error">${data.error || 'could not open that directory'}</div>`;
      list.innerHTML = '';
      return;
    }
    errBox.innerHTML = '';
    document.getElementById('scan-dir').value = data.dir;
    document.getElementById('dir-breadcrumbs').innerHTML = renderBreadcrumbs(data.dir);
    document.querySelectorAll('.dir-breadcrumb-seg').forEach(seg => {
      seg.addEventListener('click', () => browseTo(seg.dataset.path));
    });

    list.innerHTML = data.entries.length
      ? data.entries.map(name => `<div class="candidate-row dir-browser-row">${name}</div>`).join('')
      : '<div class="candidate-row empty">No subdirectories</div>';
    const base = data.dir === '/' ? '' : data.dir;
    list.querySelectorAll('.dir-browser-row').forEach(row => {
      row.addEventListener('click', () => browseTo(`${base}/${row.textContent}`));
    });
  }

  async function runScan() {
    const dir = document.getElementById('scan-dir').value.trim();
    const errBox = document.getElementById('scan-error');
    errBox.innerHTML = '';
    const res = await fetch('/api/cases/scan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dir }),
    });
    const data = await res.json();
    if (!res.ok) {
      errBox.innerHTML = `<div class="error">${data.error || 'scan failed'}</div>`;
      return;
    }
    renderCandidates(dir, data.candidates);
  }

  function renderCandidates(dir, candidates) {
    const rows = candidates.length
      ? candidates.map(c => `
          <div class="candidate-row">
            <input type="checkbox" class="cand-check" data-name="${c.name}" checked>
            <span>${c.name}</span>
          </div>`).join('')
      : '<div class="candidate-row">No case directories found here.</div>';

    openDialog(`
      <h2>Case &rarr; Add</h2>
      <label>Found in ${dir}</label>
      <div class="candidate-list">${rows}</div>
      <div class="btn-row">
        <button id="scan-cancel">Cancel</button>
        <button id="add-go" class="primary" ${candidates.length ? '' : 'disabled'}>Add selected</button>
      </div>
    `);
    document.getElementById('scan-cancel').addEventListener('click', closeDialog);
    const addBtn = document.getElementById('add-go');
    if (addBtn) {
      addBtn.addEventListener('click', async () => {
        const checked = new Set(
          Array.from(document.querySelectorAll('.cand-check:checked')).map(el => el.dataset.name)
        );
        const exclude = candidates.map(c => c.name).filter(n => !checked.has(n));
        const res = await fetch('/api/cases', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ dir, exclude }),
        });
        if (res.ok) {
          closeDialog();
          App.refreshCases();
        }
      });
    }
  }

  function wireDeleteDialog() {
    document.getElementById('case-delete').addEventListener('click', async () => {
      closeAll();
      const cases = await App.fetchCases();
      const rows = cases.length
        ? cases.map(c => `
            <div class="candidate-row">
              <input type="checkbox" class="del-check" data-name="${c.name}">
              <span>${c.name}${c.exists ? '' : ' (missing)'}</span>
            </div>`).join('')
        : '<div class="candidate-row">No cases registered.</div>';

      openDialog(`
        <h2>Case &rarr; Delete</h2>
        <label>Remove from the registry (case data on disk is untouched)</label>
        <div class="candidate-list">${rows}</div>
        <div class="btn-row">
          <button id="del-cancel">Cancel</button>
          <button id="del-go" class="primary" ${cases.length ? '' : 'disabled'}>Remove selected</button>
        </div>
      `);
      document.getElementById('del-cancel').addEventListener('click', closeDialog);
      const goBtn = document.getElementById('del-go');
      if (goBtn) {
        goBtn.addEventListener('click', async () => {
          const names = Array.from(document.querySelectorAll('.del-check:checked')).map(el => el.dataset.name);
          for (const name of names) {
            await App.removeCase(name);
          }
          closeDialog();
        });
      }
    });
  }

  function wirePlotMenu() {
    document.getElementById('plot-new').addEventListener('click', () => {
      closeAll();
      NewPlot.open();
    });
    document.getElementById('plot-clear').addEventListener('click', () => {
      closeAll();
      Layout.openClear();
    });
  }

  function wireLayoutMenu() {
    document.getElementById('layout-new').addEventListener('click', () => {
      closeAll();
      Layout.openNew();
    });
    document.getElementById('layout-edit').addEventListener('click', () => {
      closeAll();
      Layout.openEdit();
    });
    document.getElementById('layout-panes').addEventListener('click', () => {
      closeAll();
      Layout.openPanes();
    });
    document.getElementById('layout-export').addEventListener('click', () => {
      closeAll();
      Export.open();
    });
  }

  // Settings -> Units: just "inches" for now (every layout/pane dimension
  // is already always inches) -- the dropdown exists so a later unit
  // doesn't need new menu plumbing, only a new <option>.
  const UNITS_KEY = 'flexflow.units';

  function wireSettingsMenu() {
    document.getElementById('settings-units').addEventListener('click', () => {
      closeAll();
      let current = 'in';
      try { current = localStorage.getItem(UNITS_KEY) || 'in'; } catch (e) { /* private mode, etc. */ }
      openDialog(`
        <h2>Settings &rarr; Units</h2>
        <label for="settings-units-select">Units</label>
        <select id="settings-units-select">
          <option value="in" ${current === 'in' ? 'selected' : ''}>Inches</option>
        </select>
        <div class="btn-row">
          <button id="settings-units-close" class="primary">Close</button>
        </div>
      `);
      document.getElementById('settings-units-close').addEventListener('click', () => {
        const value = document.getElementById('settings-units-select').value;
        try { localStorage.setItem(UNITS_KEY, value); } catch (e) { /* ignore */ }
        closeDialog();
      });
    });

    // Settings -> Clear Cache: server-side caches that can go stale
    // independent of anything changed in the app itself -- matplotlib's
    // installed-font list (built once; a font installed on the system
    // afterward, like a Times New Roman package, isn't picked up until
    // this runs) and the per-case data loader's cache. Never touches this
    // workspace's own panels/layouts/style (that's not a cache, it's the
    // user's work) -- only /api/settings/clear-cache's own two things.
    document.getElementById('settings-clear-cache').addEventListener('click', () => {
      closeAll();
      openDialog(`
        <h2>Settings &rarr; Clear Cache</h2>
        <label>Rescans installed fonts and drops the per-case data cache -- use this if a
          font you just installed, or simulation output you just re-ran, still looks stale.</label>
        <div id="clear-cache-status"></div>
        <div class="btn-row">
          <button id="clear-cache-close">Close</button>
          <button id="clear-cache-go" class="primary">Clear Cache</button>
        </div>
      `);
      document.getElementById('clear-cache-close').addEventListener('click', closeDialog);
      document.getElementById('clear-cache-go').addEventListener('click', async (e) => {
        const btn = e.target;
        const status = document.getElementById('clear-cache-status');
        btn.disabled = true;
        status.innerHTML = '<div class="empty">Clearing&hellip;</div>';
        try {
          const res = await fetch('/api/settings/clear-cache', { method: 'POST' });
          const data = await res.json();
          if (!res.ok) throw new Error(data.error || 'clear failed');
          status.innerHTML = `<div class="empty">Done -- ${data.fonts} font(s) found.</div>`;
        } catch (err) {
          status.innerHTML = `<div class="error">${err.message}</div>`;
        }
        btn.disabled = false;
      });
    });
  }

  function wireDataMenu() {
    document.getElementById('data-info').addEventListener('click', () => {
      closeAll();
      DataMenu.openInfo();
    });
  }

  function wireHelpMenu() {
    document.getElementById('help-flowchart').addEventListener('click', () => {
      closeAll();
      FlowChart.open();
    });
  }

  function init(root) {
    wireMenuBar();
    wireAddDialog(root);
    wireDeleteDialog();
    wirePlotMenu();
    wireLayoutMenu();
    wireDataMenu();
    wireSettingsMenu();
    wireHelpMenu();
  }

  return { init, openDialog, closeDialog };
})();
