// Wires up the case sidebar; delegates menus to Menu.
const App = (() => {
  async function fetchCases() {
    const res = await fetch('/api/cases');
    return res.ok ? res.json() : [];
  }

  function renderCases(cases) {
    const list = document.getElementById('case-list');
    list.innerHTML = '';
    if (!cases.length) {
      list.innerHTML = '<li class="empty">No cases yet — Case &rarr; Add&hellip;</li>';
      return;
    }
    for (const c of cases) {
      const li = document.createElement('li');
      if (!c.exists) li.classList.add('missing');
      const name = document.createElement('span');
      name.className = 'case-name';
      name.textContent = c.name;
      name.title = c.path;
      const remove = document.createElement('span');
      remove.className = 'case-remove';
      remove.textContent = '×';
      remove.title = 'Remove from list';
      remove.addEventListener('click', () => removeCase(c.name));
      li.appendChild(name);
      li.appendChild(remove);
      list.appendChild(li);
    }
  }

  async function refreshCases() {
    renderCases(await fetchCases());
  }

  async function removeCase(name) {
    await fetch(`/api/cases/${encodeURIComponent(name)}`, { method: 'DELETE' });
    await refreshCases();
  }

  function init() {
    const root = document.getElementById('app').dataset.root;
    Menu.init(root);
    refreshCases();
    refreshWorkspace();
  }

  return { init, fetchCases, refreshCases, removeCase };
})();

document.addEventListener('DOMContentLoaded', App.init);
