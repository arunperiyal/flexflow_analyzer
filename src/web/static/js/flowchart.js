// Help -> Flowchart: the end-to-end workflow as a branching diagram, from a
// blank template to a plot in hand, with the selected step's detail on the
// right. NODES holds the steps (placed by hand on a col/row grid, so a new
// step means choosing where it goes) and EDGES the connectors between them.
// Commands lean on the shell's contexts: `use case:myCase` is set once and
// the steps after it name no case.
const FlowChart = (() => {
  const NODES = [
    {
      id: 'template', kind: 'terminal', col: 1, row: 0, label: ['Build the template case'],
      title: 'Build the template case',
      command: 'mkdir refCase\n# in it: <problem>.geo, <problem>.def, simflow.config',
      detail: `Pick a short problem name (riser, plate) and name the files
        after it. refCase is never run: it is the source every real case is
        made from. Anything that varies per case gets a placeholder instead
        of a value, such as depth = #depth.`,
    },
    {
      id: 'scripts', kind: 'step', col: 1, row: 1, label: ['Generate the job scripts'],
      title: 'Generate the job scripts',
      command: 'use case:refCase\ntemplate script pre\ntemplate script main\ntemplate script post',
      detail: `Writes preFlex.sh, mainFlex.sh and postFlex.sh, the scripts
        "run pre/main/post" submit to Slurm. They can be edited by hand
        afterwards.`,
    },
    {
      id: 'sweep', kind: 'decision', col: 1, row: 2, label: ['One case', 'or a sweep?'],
      title: 'One case or a sweep?',
      command: null,
      detail: `A single case, or a parameter sweep that creates many cases
        from one YAML file.`,
    },
    {
      id: 'single', kind: 'step', col: 1, row: 3, label: ['Write the case YAML'],
      title: 'Write the case YAML',
      command: 'template case single',
      detail: `Writes case_single.yaml. Fill in the placeholder values
        there, without touching refCase.`,
    },
    {
      id: 'multi', kind: 'step', col: 2, row: 3, label: ['Write the sweep YAML'],
      title: 'Write the sweep YAML',
      command: 'template case multi',
      detail: `Writes case_multi.yaml, whose cases section lists every case
        of the sweep and its values.`,
    },
    {
      id: 'create', kind: 'step', col: 1, row: 4, label: ['Create the case'],
      title: 'Create the case',
      command: 'case create myCase --ref-case refCase --from-config case_single.yaml',
      detail: `Builds the case directory from refCase, with every
        placeholder filled in. A sweep's YAML creates all of its cases at
        once. --dry-run shows what would be created.`,
    },
    {
      id: 'register', kind: 'step', col: 1, row: 5, label: ['Register it and set the context'],
      title: 'Register it and set the context',
      command: 'case add\nuse case:myCase',
      detail: `"case add" scans this directory and builds the .cases
        registry, which "case report" and "use case:*" go over.

        "use case:myCase" means the commands below need no case name.
        Contexts also hold var, node, t1, t2, freq, last and remote;
        "use list" shows them.`,
    },
    {
      id: 'check', kind: 'step', col: 1, row: 6, label: ['Check the case'],
      title: 'Check the case',
      command: 'run check',
      detail: `Validates the files a run needs (simflow.config, .geo, .def,
        job scripts, expected directories) and reports the last Slurm job's
        status, if there was one. It catches a missing file before it
        wastes a queue slot.`,
    },
    {
      id: 'restart', kind: 'decision', col: 1, row: 7, label: ['New run', 'or restart?'],
      title: 'New run or restart?',
      command: null,
      detail: `A new run meshes first. A restart picks up from a saved step
        and needs no new mesh. A failed job comes back here too.`,
    },
    {
      id: 'pre', kind: 'step', col: 1, row: 8, label: ['Submit meshing'],
      title: 'Submit meshing',
      command: 'run pre',
      detail: `Submits preFlex.sh: mesh generation (gmsh) and conversion. It
        returns a job ID for the main run to wait on.`,
    },
    {
      id: 'main', kind: 'step', col: 1, row: 9, label: ['Submit the simulation'],
      title: 'Submit the simulation',
      command: 'run main --dependency <preJobID>',
      detail: `Submits mainFlex.sh, the solver run. --dependency queues it
        behind the pre job so it waits for the mesh. "run main reset"
        comments out restartFlag/restartTsId to start fresh.`,
    },
    {
      id: 'restartRun', kind: 'step', col: 2, row: 9, label: ['Restart from a step'],
      title: 'Restart from a step',
      command: 'run main restart <tsId>',
      detail: `Sets the restart in simflow.config and submits mainFlex.sh,
        which first moves the previous run's .othd and .oisd into
        othd_files/archive/ and oisd_files/archive/.`,
    },
    {
      id: 'watch', kind: 'step', col: 1, row: 10, label: ['Watch the queue'],
      title: 'Watch the queue',
      command: 'run sq watch\n# run sc <id|name> cancels a job',
      optional: true,
      detail: `Refreshes the Slurm queue. "run sq find <key>" looks for jobs
        by name or work directory.`,
    },
    {
      id: 'finished', kind: 'decision', col: 1, row: 11, label: ['Did the job', 'finish?'],
      title: 'Did the job finish?',
      command: null,
      detail: `Finished runs go on to post-processing. A failed or stopped
        one needs its cause found first.`,
    },
    {
      id: 'fix', kind: 'step', col: 0, row: 11, label: ['Find the cause', 'and fix it'],
      title: 'Find the cause and fix it',
      command: 'run list log\ncase check run\ncase status update -m "<what happened>" --state failed',
      detail: `Read the job's slurm-* log and check the run directory, then
        fix the case and go back to choose a new run or a restart.`,
    },
    {
      id: 'post', kind: 'step', col: 1, row: 12, label: ['Submit post-processing'],
      title: 'Submit post-processing',
      command: 'run post full --dependency <mainJobID>',
      detail: `Submits postFlex.sh, which turns the solver's ASCII output
        into binary PLT files. "run post convert" does only the conversion,
        when the .plt files already exist.`,
    },
    {
      id: 'history', kind: 'step', col: 1, row: 13, label: ['Organise the history'],
      title: 'Organise the history',
      command: 'case organise history --update --clean --compile',
      detail: `Moves .othd and .oisd into archive/, writes each run without
        the steps a later run redid into cleaned/, and joins them into one
        file.`,
    },
    {
      id: 'outputCheck', kind: 'step', col: 1, row: 14, label: ['Check the output'],
      title: 'Check the output',
      command: "case check all\nmissing binary 'riser.{}.plt' --empty",
      detail: `"case check all" covers the OTHD/OISD ranges, simflow.config,
        PLT completeness and .def references. "missing" lists the gaps in a
        numbered series, and takes its range from the t1, t2 and freq
        contexts.`,
    },
    {
      id: 'complete', kind: 'decision', col: 1, row: 15, label: ['Is the output', 'complete?'],
      title: 'Is the output complete?',
      command: null,
      detail: `Gaps or empty files go back through post-processing for those
        steps.`,
    },
    {
      id: 'gaps', kind: 'step', col: 0, row: 15, label: ['Pick the steps to redo'],
      title: 'Pick the steps to redo',
      command: 'use t1:<first> t2:<last>',
      detail: `Sets the window "run post full" works on, so only the missing
        steps are processed again. Clear it with "unuse" afterwards.`,
    },
    {
      id: 'thin', kind: 'step', col: 1, row: 16, label: ['Thin the output'],
      title: 'Thin the output',
      command: 'case organise output --keep-out\ncase organise plt',
      optional: true,
      detail: `Prunes what is no longer needed. --keep-out deletes no .out
        and only thins the .rst to the steps divisible by --keep-freq.
        "case organise plt" prunes intermediate PLT files.`,
    },
    {
      id: 'transfer', kind: 'step', col: 1, row: 17, label: ['Transfer the results'],
      title: 'Transfer the results',
      command: 'use remote:nas\ncase upload binary --t1 2000 --t2 3000\ncase download binary --missing',
      optional: true,
      detail: `Sends results to a machine set up with "remote add". --missing
        sends only the files the other side does not have.

        In the shell, binary transfers are planned against the session
        timeout at "set transfer_speed". If one will not fit, it offers the
        --t2 that does; --fit takes that cut without asking.`,
    },
    {
      id: 'track', kind: 'step', col: 1, row: 18, label: ['Record where the case stands'],
      title: 'Record where the case stands',
      command: 'case status update -m "<note>" --state done\ncase report --run --size',
      optional: true,
      detail: `"case status" keeps the case's notes in .casestatus.md.
        "case report" is one table of every case in .cases, with the last
        step in each place.`,
    },
    {
      id: 'prepare', kind: 'step', col: 1, row: 19, label: ['Prepare the web UI data'],
      title: 'Prepare the web UI data',
      command: 'case domain --init\ncase out --map',
      optional: true,
      detail: `Only for the web UI. "case domain" derives domain.yml from the
        .def file and PLT zones for the picker's layout. "case out --map"
        writes the othd.<block>.map files, without which a case shows no
        pickable points.`,
    },
    {
      id: 'analyse', kind: 'terminal', col: 1, row: 20, label: ['Analyse and plot'],
      title: 'Analyse and plot',
      command: 'use var:dy node:24 t1:1000 t2:2000\ndata table\ndata stats\nplot --output dy.png',
      detail: `In the shell, the var and window contexts drive "data table",
        "data stats" and "plot". "compare --config compare.yaml" puts several
        cases on one plot.

        For the web UI, start "ff --ui", then Case -> Add, Plot -> New, and
        Layout -> Export for a PNG or PDF.`,
    },
  ];

  // from/to are [node id, side]; side is t, r, b or l. A `back` edge is a
  // loop to an earlier step and is drawn dashed.
  const EDGES = [
    { from: ['template', 'b'], to: ['scripts', 't'] },
    { from: ['scripts', 'b'], to: ['sweep', 't'] },
    { from: ['sweep', 'b'], to: ['single', 't'], label: 'One' },
    { from: ['sweep', 'r'], to: ['multi', 't'], label: 'Sweep' },
    { from: ['single', 'b'], to: ['create', 't'] },
    { from: ['multi', 'b'], to: ['create', 'r'] },
    { from: ['create', 'b'], to: ['register', 't'] },
    { from: ['register', 'b'], to: ['check', 't'] },
    { from: ['check', 'b'], to: ['restart', 't'] },
    { from: ['restart', 'b'], to: ['pre', 't'], label: 'New' },
    { from: ['restart', 'r'], to: ['restartRun', 't'], label: 'Restart' },
    { from: ['pre', 'b'], to: ['main', 't'] },
    { from: ['main', 'b'], to: ['watch', 't'] },
    { from: ['restartRun', 'b'], to: ['watch', 'r'] },
    { from: ['watch', 'b'], to: ['finished', 't'] },
    { from: ['finished', 'b'], to: ['post', 't'], label: 'Yes' },
    { from: ['finished', 'l'], to: ['fix', 'r'], label: 'No' },
    { from: ['fix', 't'], to: ['restart', 'l'], back: true },
    { from: ['post', 'b'], to: ['history', 't'] },
    { from: ['history', 'b'], to: ['outputCheck', 't'] },
    { from: ['outputCheck', 'b'], to: ['complete', 't'] },
    { from: ['complete', 'b'], to: ['thin', 't'], label: 'Yes' },
    { from: ['complete', 'l'], to: ['gaps', 'r'], label: 'No' },
    { from: ['gaps', 't'], to: ['post', 'l'], back: true },
    { from: ['thin', 'b'], to: ['transfer', 't'] },
    { from: ['transfer', 'b'], to: ['track', 't'] },
    { from: ['track', 'b'], to: ['prepare', 't'] },
    { from: ['prepare', 'b'], to: ['analyse', 't'] },
  ];

  const COL_X = [110, 350, 590];
  const ROW_Y = 84;
  const TOP = 40;
  const WIDTH = 700;
  const SIZE = { step: [190, 46], terminal: [190, 46], decision: [190, 66] };

  const byId = Object.fromEntries(NODES.map(n => [n.id, n]));
  let activeId = NODES[0].id;

  function escapeHtml(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function center(node) {
    return [COL_X[node.col], TOP + node.row * ROW_Y];
  }

  function port([id, side]) {
    const node = byId[id];
    const [x, y] = center(node);
    const [w, h] = SIZE[node.kind];
    return {
      t: [x, y - h / 2], b: [x, y + h / 2], l: [x - w / 2, y], r: [x + w / 2, y],
    }[side];
  }

  // Straight when the ends line up, otherwise one bend: leaving a side runs
  // along that side's axis first, so a connector leaves its box squarely.
  function edgePoints(edge) {
    const [x1, y1] = port(edge.from);
    const [x2, y2] = port(edge.to);
    if (x1 === x2 || y1 === y2) return [[x1, y1], [x2, y2]];
    const leavesSideways = edge.from[1] === 'l' || edge.from[1] === 'r';
    return [[x1, y1], leavesSideways ? [x2, y1] : [x1, y2], [x2, y2]];
  }

  function edgeLabel(edge, [x, y]) {
    if (!edge.label) return '';
    const side = edge.from[1];
    const at = {
      b: [x + 7, y + 13, 'start'],
      r: [x + 8, y - 6, 'start'],
      l: [x - 8, y - 6, 'end'],
    }[side];
    return `<text class="flowchart-edge-label" x="${at[0]}" y="${at[1]}"
      text-anchor="${at[2]}">${escapeHtml(edge.label)}</text>`;
  }

  function edgeSvg(edge) {
    const points = edgePoints(edge);
    const path = points.map(p => p.join(',')).join(' ');
    return `<polyline class="flowchart-edge${edge.back ? ' back' : ''}" points="${path}"
      marker-end="url(#flowchart-arrow)"/>${edgeLabel(edge, points[0])}`;
  }

  function shapeSvg(kind, x, y) {
    const [w, h] = SIZE[kind];
    if (kind === 'decision') {
      return `<polygon points="${x},${y - h / 2} ${x + w / 2},${y} ${x},${y + h / 2} ${x - w / 2},${y}"/>`;
    }
    const radius = kind === 'terminal' ? h / 2 : 6;
    return `<rect x="${x - w / 2}" y="${y - h / 2}" width="${w}" height="${h}" rx="${radius}"/>`;
  }

  function nodeSvg(node) {
    const [x, y] = center(node);
    const lineHeight = 14;
    const first = y - (node.label.length - 1) * lineHeight / 2;
    const text = node.label.map((line, i) =>
      `<text x="${x}" y="${first + i * lineHeight}">${escapeHtml(line)}</text>`).join('');
    return `<g class="flowchart-node ${node.kind}" data-id="${node.id}" role="button"
      tabindex="0" aria-label="${escapeHtml(node.title)}">${shapeSvg(node.kind, x, y)}${text}</g>`;
  }

  function legendHtml() {
    const swatch = (body) => `<svg width="34" height="20" viewBox="0 0 34 20"
      aria-hidden="true">${body}</svg>`;
    const items = [
      [swatch('<rect class="flowchart-key" x="2" y="4" width="30" height="12" rx="6"/>'), 'Start or end'],
      [swatch('<rect class="flowchart-key" x="2" y="3" width="30" height="14" rx="2"/>'), 'Step'],
      [swatch('<polygon class="flowchart-key" points="17,1 33,10 17,19 1,10"/>'), 'Decision'],
      [swatch('<line class="flowchart-edge" x1="2" y1="10" x2="26" y2="10" marker-end="url(#flowchart-arrow)"/>'), 'Next step'],
      [swatch('<line class="flowchart-edge back" x1="2" y1="10" x2="26" y2="10" marker-end="url(#flowchart-arrow)"/>'), 'Loop back'],
    ];
    return items.map(([icon, text]) => `<span class="flowchart-legend-item">${icon}${text}</span>`).join('');
  }

  function open() {
    Menu.openDialog(`
      <h2>Help &rarr; Flowchart</h2>
      <div class="flowchart-legend">${legendHtml()}</div>
      <div class="flowchart-editor">
        <div id="flowchart-graph" class="flowchart-graph"></div>
        <div id="flowchart-detail" class="flowchart-detail"></div>
      </div>
      <div class="btn-row"><button id="flowchart-close" class="primary">Close</button></div>
    `, { wide: true });
    document.getElementById('flowchart-close').addEventListener('click', Menu.closeDialog);
    activeId = NODES[0].id;
    renderGraph();
    renderDetail();
  }

  function renderGraph() {
    const height = center(NODES[NODES.length - 1])[1] + 40;
    const box = document.getElementById('flowchart-graph');
    box.innerHTML = `
      <svg width="${WIDTH}" height="${height}" viewBox="0 0 ${WIDTH} ${height}"
           role="group" aria-label="Workflow flowchart">
        <defs>
          <marker id="flowchart-arrow" viewBox="0 0 8 8" refX="7" refY="4"
                  markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0,0 L8,4 L0,8 z" fill="#64748b"/>
          </marker>
        </defs>
        ${EDGES.map(edgeSvg).join('')}
        ${NODES.map(nodeSvg).join('')}
      </svg>`;
    box.querySelectorAll('.flowchart-node').forEach(g => {
      g.addEventListener('click', () => select(g.dataset.id));
      g.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          select(g.dataset.id);
        }
      });
    });
    markActive();
  }

  function select(id) {
    activeId = id;
    markActive();
    renderDetail();
  }

  function markActive() {
    document.querySelectorAll('#flowchart-graph .flowchart-node').forEach(g => {
      g.classList.toggle('active', g.dataset.id === activeId);
    });
  }

  function renderDetail() {
    const step = byId[activeId];
    const box = document.getElementById('flowchart-detail');
    const paragraphs = step.detail.trim().split(/\n[ \t]*\n/)
      .map(p => `<p>${escapeHtml(p.trim())}</p>`).join('');
    box.innerHTML = `
      <h3>${escapeHtml(step.title)}</h3>
      ${step.optional ? '<div class="flowchart-optional-tag">Optional</div>' : ''}
      ${step.command ? `<div class="flowchart-command-wrap">
        <pre class="flowchart-command">${escapeHtml(step.command)}</pre>
        <button type="button" id="flowchart-copy" class="flowchart-copy">Copy</button>
      </div>` : ''}
      ${paragraphs}
    `;
    const copy = document.getElementById('flowchart-copy');
    if (copy) copy.addEventListener('click', () => copyCommand(step.command, copy));
  }

  // The async clipboard exists only on https or localhost, and the UI may be
  // reached over plain http, so fall back to a hidden textarea.
  function writeClipboard(text) {
    if (navigator.clipboard) return navigator.clipboard.writeText(text);
    const area = document.createElement('textarea');
    area.value = text;
    area.style.position = 'fixed';
    area.style.opacity = '0';
    document.body.appendChild(area);
    area.select();
    const done = document.execCommand('copy');
    area.remove();
    return done ? Promise.resolve() : Promise.reject(new Error('copy refused'));
  }

  function copyCommand(text, button) {
    writeClipboard(text).then(
      () => { button.textContent = 'Copied'; },
      () => { button.textContent = 'Copy failed'; },
    );
    setTimeout(() => { button.textContent = 'Copy'; }, 1500);
  }

  return { open };
})();
