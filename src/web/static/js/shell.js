// The Command Window's input: type a command, press Enter, see the
// result. `case` mirrors the CLI's own case add/delete (src/cli/
// interactive.py) via the same registry endpoints those already use --
// but layout/plot/settings have no CLI equivalent to mirror at all: the
// CLI's own `plot` is a one-shot argparse call with no panel/trace/layout
// workspace behind it, so this vocabulary is web-only, invented for the
// workspace this app actually has.
const Shell = (() => {
  const history = [];

  const HELP = `Commands:
  case add <dir>                 scan <dir> and register every case found there
  case delete <name>             remove a case from the registry
  case list                      list registered cases
  layout new [w] [h]             new layout tab (inches; default 6.5 x 4.5)
  layout edit [w] [h]            resize the active layout's canvas
  layout list                    list layout tabs (* marks the active one)
  layout use <name>               switch to a layout tab
  layout panes                   open Layout -> Panes
  plot new                       open Plot -> New
  plot clear <panel>             clear a panel's traces (name or id)
  plot export [--format png|pdf] [--dpi N]
                                  export the active layout
  settings units                 show the current units
  settings clear-cache           clear server-side caches
  help                           this message
  clear                          clear the command window
  history                        list command history
Up/Down arrow: browse history.`;

  // Splits on whitespace, keeping "quoted" or 'quoted' runs together (a
  // directory path can carry spaces) -- not a full shell-quoting grammar,
  // just enough for `case add "some dir"`.
  function tokenize(input) {
    const tokens = [];
    const re = /"([^"]*)"|'([^']*)'|(\S+)/g;
    let m;
    while ((m = re.exec(input)) !== null) tokens.push(m[1] ?? m[2] ?? m[3]);
    return tokens;
  }

  // {flags: {name: value}, positional: [...]} -- `--name value` consumes
  // the next token as the value unless it's itself another flag, in which
  // case this one is just a boolean switch (true).
  function parseFlags(args) {
    const flags = {};
    const positional = [];
    for (let i = 0; i < args.length; i++) {
      if (args[i].startsWith('--')) {
        const key = args[i].slice(2);
        const next = args[i + 1];
        flags[key] = next && !next.startsWith('--') ? args[++i] : true;
      } else {
        positional.push(args[i]);
      }
    }
    return { flags, positional };
  }

  async function run(raw) {
    const trimmed = raw.trim();
    if (!trimmed) return;
    history.push(trimmed);
    CommandLog.prompt(trimmed);

    const [verb, sub, ...rest] = tokenize(trimmed);
    try {
      const output = await dispatch(verb, sub, rest);
      if (output) CommandLog.print(output);
    } catch (e) {
      CommandLog.error(e.message);
    }
  }

  function dispatch(verb, sub, rest) {
    switch (verb) {
      case 'help': case '?': return HELP;
      case 'clear': CommandLog.clear(); return null;
      case 'history':
        return history.length ? history.map((h, i) => `${i + 1}  ${h}`).join('\n') : '(empty)';
      case 'case': return caseCmd(sub, rest);
      case 'layout': return layoutCmd(sub, rest);
      case 'plot': return plotCmd(sub, rest);
      case 'settings': return settingsCmd(sub);
      case undefined: return null;
      default: throw new Error(`unknown command: ${verb} -- try 'help'`);
    }
  }

  async function caseCmd(sub, rest) {
    if (sub === 'add') {
      const dir = rest.join(' ');
      if (!dir) throw new Error('usage: case add <dir>');
      const res = await fetch('/api/cases', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dir }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || 'case add failed');
      await App.refreshCases();
      return null;   // the server's own logbuf entry ("registered ...") shows up via the usual poll
    }
    if (sub === 'delete') {
      const name = rest.join(' ');
      if (!name) throw new Error('usage: case delete <name>');
      const cases = await App.fetchCases();
      if (!cases.some(c => c.name === name)) throw new Error(`no such case: ${name}`);
      await App.removeCase(name);
      return null;   // ditto -- the server logs "removed <name> from the registry"
    }
    if (sub === 'list') {
      const cases = await App.fetchCases();
      return cases.length
        ? cases.map(c => `${c.name}${c.exists ? '' : ' (missing)'}`).join('\n')
        : '(no cases registered)';
    }
    throw new Error(`unknown case subcommand: ${sub ?? ''} -- try 'help'`);
  }

  function layoutCmd(sub, rest) {
    if (sub === 'new') {
      const [w, h] = rest.map(Number);
      const spec = {};
      if (Number.isFinite(w)) spec.width = w;
      if (Number.isFinite(h)) spec.height = h;
      const id = PlotWorkspace.createLayout(spec);
      refreshWorkspace();
      return `created layout ${id}`;
    }
    if (sub === 'edit') {
      const [w, h] = rest.map(Number);
      const patch = {};
      if (Number.isFinite(w)) patch.width = w;
      if (Number.isFinite(h)) patch.height = h;
      if (!Object.keys(patch).length) throw new Error('usage: layout edit [width] [height]');
      PlotWorkspace.updateLayout(patch);
      refreshWorkspace();
      return 'updated';
    }
    if (sub === 'list') {
      const layouts = PlotWorkspace.listLayouts();
      const activeId = PlotWorkspace.activeLayoutId();
      return layouts.map(l => `${l.id === activeId ? '*' : ' '} ${l.name} (${l.id})`).join('\n');
    }
    if (sub === 'use') {
      const target = rest.join(' ');
      if (!target) throw new Error('usage: layout use <name-or-id>');
      const match = PlotWorkspace.listLayouts().find(l => l.id === target || l.name === target);
      if (!match) throw new Error(`no such layout: ${target}`);
      PlotWorkspace.setActiveLayout(match.id);
      refreshWorkspace();
      return `switched to ${match.name}`;
    }
    if (sub === 'panes') {
      Layout.openPanes();
      return null;
    }
    throw new Error(`unknown layout subcommand: ${sub ?? ''} -- try 'help'`);
  }

  function plotCmd(sub, rest) {
    if (sub === 'new') {
      NewPlot.open();
      return null;
    }
    if (sub === 'clear') {
      const target = rest.join(' ');
      if (!target) throw new Error('usage: plot clear <panel>');
      const panel = PlotWorkspace.state().panels.find(p => p.id === target || p.title === target);
      if (!panel) throw new Error(`no such panel: ${target}`);
      PlotWorkspace.clearPanel(panel.id);
      refreshWorkspace();
      return `cleared ${panel.title}`;
    }
    if (sub === 'export') {
      const { flags } = parseFlags(rest);
      return Export.runFromCommand(flags.format, flags.dpi);
    }
    throw new Error(`unknown plot subcommand: ${sub ?? ''} -- try 'help'`);
  }

  function settingsCmd(sub) {
    if (sub === 'units') {
      let units = 'in';
      try { units = localStorage.getItem('flexflow.units') || 'in'; } catch (e) { /* private mode, etc. */ }
      return `units: ${units === 'in' ? 'inches' : units}`;
    }
    if (sub === 'clear-cache') {
      return fetch('/api/settings/clear-cache', { method: 'POST' })
        .then(async (res) => {
          const data = await res.json().catch(() => ({}));
          if (!res.ok) throw new Error(data.error || 'clear failed');
          return `cleared caches: ${data.fonts} font(s) found`;
        });
    }
    throw new Error(`unknown settings subcommand: ${sub ?? ''} -- try 'help'`);
  }

  // Enter runs the command; Up/Down browses history, same as a real
  // shell -- browseIdx tracks position independent of history's own
  // length so paging up mid-list and then typing something new doesn't
  // disturb what's already been run.
  function wireInput() {
    const input = document.getElementById('command-input');
    let browseIdx = history.length;
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        const value = input.value;
        input.value = '';
        run(value);
        browseIdx = history.length;
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        if (browseIdx > 0) browseIdx--;
        input.value = history[browseIdx] || '';
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (browseIdx < history.length) {
          browseIdx++;
          input.value = history[browseIdx] || '';
        }
      }
    });
  }

  return { wireInput };
})();
