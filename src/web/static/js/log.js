// Polls /api/log and appends new lines to the command window.
const CommandLog = (() => {
  let seq = 0;
  let timer = null;

  function render(entry) {
    const el = document.createElement('div');
    el.className = 'line';
    el.textContent = entry.line;
    document.getElementById('command-log').appendChild(el);
  }

  function prompt(text) {
    const wrap = document.createElement('div');
    const p = document.createElement('span');
    p.className = 'prompt';
    p.textContent = 'flexflow › ';
    wrap.appendChild(p);
    wrap.appendChild(document.createTextNode(text));
    document.getElementById('command-log').appendChild(wrap);
    scrollToEnd();
  }

  function scrollToEnd() {
    const log = document.getElementById('command-log');
    log.scrollTop = log.scrollHeight;
  }

  async function poll() {
    try {
      const res = await fetch(`/api/log?since=${seq}`);
      if (res.ok) {
        const data = await res.json();
        for (const entry of data.lines) render(entry);
        if (data.lines.length) scrollToEnd();
        seq = data.seq;
      }
    } catch (e) {
      // transient network error; next poll retries
    }
  }

  function start() {
    poll();
    timer = setInterval(poll, 1500);
  }

  return { start, prompt };
})();
