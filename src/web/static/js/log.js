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

  // Shell's own command output -- as opposed to render(), which only ever
  // shows lines that came from the server's logbuf (case add/delete etc.
  // already write there, so a shell command that just wraps one of those
  // doesn't need to print anything of its own -- the polled line covers it).
  function print(text) {
    for (const line of String(text).split('\n')) {
      const el = document.createElement('div');
      el.className = 'line';
      el.textContent = line;
      document.getElementById('command-log').appendChild(el);
    }
    scrollToEnd();
  }

  function error(text) {
    const el = document.createElement('div');
    el.className = 'err';
    el.textContent = text;
    document.getElementById('command-log').appendChild(el);
    scrollToEnd();
  }

  function clear() {
    document.getElementById('command-log').innerHTML = '';
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

  return { start, prompt, print, error, clear };
})();
