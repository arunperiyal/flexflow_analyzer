// The command window and the "working" spinner (webapp.md 4, 8).
// The window is read only: it asks /api/log for new lines, it sends nothing.
// While any request is in flight it asks once a second and the spinner shows;
// a request that takes under 300 ms never flashes it.
const CommandLog = (() => {
  let last = 0, inFlight = 0, timer = null, showTimer = null, count = 0;
  const el = (id) => document.getElementById(id);

  function add(rows) {
    const box = el('command-lines');
    const atEnd = box.scrollTop + box.clientHeight >= box.scrollHeight - 8;
    for (const r of rows) {
      const line = document.createElement('div');
      if (r.level === 'error') line.className = 'err';
      const when = document.createElement('span');
      when.className = 'when';
      when.textContent = r.time;
      line.append(when, document.createTextNode(r.text));
      box.appendChild(line);
      count++;
    }
    while (box.childElementCount > 500) box.removeChild(box.firstChild);
    el('command-count').textContent = count ? `(${count})` : '';
    if (atEnd) box.scrollTop = box.scrollHeight;
  }

  async function poll(rawFetch) {
    try {
      const res = await rawFetch(`/api/log?since=${last}`);
      if (!res.ok) return;
      const body = await res.json();
      last = body.next;
      add(body.lines);
    } catch (e) { /* the server is busy or gone: the next poll tries again */ }
  }

  function start(rawFetch) {
    if (!showTimer) showTimer = setTimeout(() => { el('busy').hidden = false; }, 300);
    if (!timer) timer = setInterval(() => poll(rawFetch), 1000);
  }

  function stop(rawFetch) {
    clearTimeout(showTimer); showTimer = null;
    el('busy').hidden = true;
    clearInterval(timer); timer = null;
    poll(rawFetch);                        // the last lines of what just finished
  }

  function init() {
    const rawFetch = window.fetch.bind(window);
    window.fetch = (url, ...rest) => {
      const mine = typeof url === 'string' && url.startsWith('/api/log');
      if (mine) return rawFetch(url, ...rest);
      if (inFlight++ === 0) start(rawFetch);
      return rawFetch(url, ...rest).finally(() => { if (--inFlight === 0) stop(rawFetch); });
    };
    el('command-bar').addEventListener('click', () => {
      el('command-window').classList.toggle('collapsed');
      el('command-lines').scrollTop = el('command-lines').scrollHeight;
    });
    poll(rawFetch);
  }

  document.addEventListener('DOMContentLoaded', init);
  return { add };
})();
