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
        <div id="scan-error"></div>
        <div class="btn-row">
          <button id="scan-cancel">Cancel</button>
          <button id="scan-go" class="primary">Scan</button>
        </div>
      `);
      document.getElementById('scan-cancel').addEventListener('click', closeDialog);
      document.getElementById('scan-go').addEventListener('click', runScan);
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
        CommandLog.prompt(`case add ${dir}`);
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
    document.getElementById('plot-layout').addEventListener('click', () => {
      closeAll();
      Layout.open();
    });
    document.getElementById('plot-clear').addEventListener('click', () => {
      closeAll();
      Layout.openClear();
    });
    document.getElementById('plot-export').addEventListener('click', () => {
      closeAll();
      Export.run();
    });
  }

  function init(root) {
    wireMenuBar();
    wireAddDialog(root);
    wireDeleteDialog();
    wirePlotMenu();
  }

  return { init, openDialog, closeDialog };
})();
