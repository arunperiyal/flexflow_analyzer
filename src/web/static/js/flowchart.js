// Help -> Flowchart: the end-to-end workflow as a branching diagram, from a
// blank template to a plot in hand, with the selected step's detail on the
// right. After the jobs are queued it splits: by hand down the middle, or
// the planned `auto` command on the right (docs/AUTO_PLAN.md). NODES holds the steps (placed by hand on a col/row grid, so a new
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
      id: 'mode', kind: 'decision', col: 1, row: 11, label: ['By hand', 'or with auto?'],
      title: 'By hand or with auto?',
      command: null,
      detail: `From here on there are two ways. Down the middle, by hand: the
        steps you run yourself, case by case. On the right, the auto command
        runs the same steps for every case in the folder, each only when its
        check passes.

        Both use the same commands and the same files, so they mix: auto
        skips what you have already done by hand.`,
    },
    {
      id: 'running', kind: 'decision', col: 1, row: 12, label: ['Main job still', 'running or queued?'],
      title: 'Is the main job still running or queued?',
      command: 'run sq find <case>\ncase status',
      detail: `A case's jobs are the ones submitted from its directory,
        whatever they are called. "case status" points out a job named for
        another case, which happens when a job script is copied without
        renaming it.

        A running or queued case can still be post-processed (right). Its
        history stays where it is until the run has ended.`,
    },
    {
      id: 'liveWindow', kind: 'step', col: 2, row: 12, label: ['Window from the', 'live .othd'],
      title: 'Window from the live .othd',
      command: 'case report --run --size\nuse t1:<first tsId> t2:<last settled step>',
      detail: `Start with the cases that take the most disk: at outFreq 5 a
        run writes many .out and .rst files.

        t1 is the first tsId of the .othd in the run directory. t2 is the
        last step whose .out files are all there and that the solver has
        moved past, never the last tsId, which is the step being computed.
        Stop before a queued restart's restartTsId: the steps after it will
        be computed again.

        Do not run "case organise history --update" on a running case: it
        would move the file the solver is writing.`,
    },
    {
      id: 'ended', kind: 'decision', col: 1, row: 13, label: ['How did', 'the run end?'],
      title: 'How did the run end?',
      command: 'run list log\nsacct -X -S now-3days --format=JobID,JobName%30,State,End',
      detail: `Most runs stop at the walltime (TIMEOUT) and go on with a
        restart. Their output is handled the same way as a finished run's.
        A run that failed needs its cause found first.

        A job leaves "run sq" five minutes after it ends; sacct still shows
        how it ended.`,
    },
    {
      id: 'fix', kind: 'step', col: 0, row: 13, label: ['Find the cause', 'and fix it'],
      title: 'Find the cause and fix it',
      command: 'run list log\ncase check run\ncase status update -m "<what happened>" --state failed',
      detail: `Read the job's slurm-* log and check the run directory, then
        fix the case and go back to choose a new run or a restart.`,
    },
    {
      id: 'history', kind: 'step', col: 1, row: 14, label: ['Organise the history'],
      title: 'Organise the history',
      command: 'case check run\ncase organise history --update --clean --compile',
      detail: `"case check run" shows whether the run directory still holds
        .othd and .oisd files. --update moves them into othd_files/archive/
        and oisd_files/archive/, --clean writes each run without the steps a
        later run computed again into cleaned/, and --compile joins them into
        one file.

        Only when no main job of the case is running or queued: a queued
        job's mainFlex.sh archives the same files when it starts.`,
    },
    {
      id: 'uploadHistory', kind: 'step', col: 1, row: 15, label: ['Upload the history'],
      title: 'Upload the history',
      command: 'use remote:cloud\ncase upload history',
      detail: `Sends archive/, cleaned/ and the compiled file to the case's
        folder on the remote. "use remote:cloud" is set once; remotes are set
        up with "remote add".`,
    },
    {
      id: 'post', kind: 'step', col: 1, row: 16, label: ['Submit post-processing'],
      title: 'Submit post-processing',
      command: 'case check out --t1 <first> --t2 <last>\nuse t1:<first> t2:<last>\nrun post full',
      detail: `t1 and t2 are the first and last tsId of the newest part in
        othd_files/archive/, or the window picked on the right for a running
        case.

        Before submitting, check two things. Every step needs its .out files
        ("case check out"): a post job fails without them. And the PLTs of
        those steps should not be on the remote already.

        "run post convert" only converts, for steps whose ASCII .plt files
        already exist.`,
    },
    {
      id: 'outputCheck', kind: 'step', col: 1, row: 17, label: ['Check the PLTs'],
      title: 'Check the PLTs',
      command: "case check plt\nmissing binary 'riser.{}.plt' --empty",
      detail: `Once the post job has ended. Every step of the window should
        have a non-empty binary PLT. "missing" lists the gaps and takes its
        range from the t1, t2 and freq contexts.`,
    },
    {
      id: 'complete', kind: 'decision', col: 1, row: 18, label: ['Are the PLTs', 'complete?'],
      title: 'Are the PLTs complete?',
      command: null,
      detail: `Gaps or empty files go back through post-processing for those
        steps.`,
    },
    {
      id: 'gaps', kind: 'step', col: 0, row: 18, label: ['Pick the steps to redo'],
      title: 'Pick the steps to redo',
      command: 'use t1:<first> t2:<last>',
      detail: `Sets the window "run post full" works on, so only the missing
        steps are processed again. Clear it with "unuse" afterwards.`,
    },
    {
      id: 'uploadPlt', kind: 'step', col: 1, row: 19, label: ['Upload the binary PLTs'],
      title: 'Upload the binary PLTs',
      command: 'case upload binary\ncase upload binary --missing',
      detail: `Sends the window's binary PLTs (t1 and t2 from the contexts).
        Run it again with --missing: it sends only what the remote lacks or
        holds at another size, so when it finds nothing to send, every file
        is there.

        Transfers are planned against the session timeout at "set
        transfer_speed". Stay logged in until they finish.`,
    },
    {
      id: 'cleanup', kind: 'step', col: 1, row: 20, label: ['Delete what is', 'safely copied'],
      title: 'Delete what is safely copied',
      command: 'case organise output --keep-freq 500\ncase organise plt --delete-ascii\ncase organise plt --delete-binary',
      detail: `Only after the upload check above: --delete-binary does not
        look at the remote.

        In this order. "organise output" deletes each step's .out once its
        .plt exists, so it has to run while the PLTs are still here; it keeps
        the .rst of the steps divisible by 500, plus the restart point in
        simflow.config, the newest complete set and a set still being
        written. --delete-ascii deletes the ASCII PLTs that have a newer
        binary copy, so it goes before --delete-binary.`,
    },
    {
      id: 'uploadRst', kind: 'step', col: 1, row: 21, label: ['Upload the newest', 'restart set'],
      title: 'Upload the newest restart set',
      command: 'case upload rst --t1 <newest complete step>',
      detail: `Only the newest complete set (all nsg parts), and only if the
        remote does not have it: the older ones may be there already. It is
        what a later restart, here or elsewhere, needs.`,
    },
    {
      id: 'goOn', kind: 'decision', col: 1, row: 22, label: ['Does the run', 'go on?'],
      title: 'Does the run go on?',
      command: null,
      detail: `Not yet at maxTimeSteps: queue a restart from the newest
        restart set ("run main restart <tsId>"), often before the current job
        has ended. A finished case goes on to its record and the analysis.`,
    },
    {
      id: 'track', kind: 'step', col: 1, row: 23, label: ['Record where the case stands'],
      title: 'Record where the case stands',
      command: 'case status update -m "<note>" --state done\ncase report --run --size',
      optional: true,
      detail: `"case status" keeps the case's notes in .casestatus.md.
        "case report" is one table of every case in .cases, with the last
        step in each place.`,
    },
    {
      id: 'prepare', kind: 'step', col: 1, row: 24, label: ['Prepare the web UI data'],
      title: 'Prepare the web UI data',
      command: 'case domain --init\ncase out --map',
      optional: true,
      detail: `Only for the web UI. "case domain" derives domain.yml from the
        .def file and PLT zones for the picker's layout. "case out --map"
        writes the othd.<block>.map files, without which a case shows no
        pickable points.`,
    },
    {
      id: 'analyse', kind: 'terminal', col: 1, row: 25, label: ['Analyse and plot'],
      title: 'Analyse and plot',
      command: 'use var:dy node:24 t1:1000 t2:2000\ndata table\ndata stats\nplot --output dy.png',
      detail: `In the shell, the var and window contexts drive "data table",
        "data stats" and "plot". "compare --config compare.yaml" puts several
        cases on one plot.

        For the web UI, start "ff --ui", then Case -> Add, Plot -> New, and
        Layout -> Export for a PNG or PDF.`,
    },
    {
      id: 'autoShow', kind: 'step', col: 3, row: 11, label: ['See the plan'], planned: true,
      title: 'See the plan (auto)',
      command: 'auto show',
      detail: `For every case in this folder's .cases: where it stands, the
        next step and the check it waits for, what will be uploaded and how
        long that takes. It changes nothing.

        Settings live in .auto.conf next to .cases: the remote and the
        folder there, and the .rst grid to keep (500).`,
    },
    {
      id: 'autoApply', kind: 'step', col: 3, row: 12, label: ['Carry it out'], planned: true,
      title: 'Carry it out (auto)',
      command: 'auto apply',
      detail: `Runs the steps in the middle for each case, each only when
        its check passes. History is organised when no main job is running
        or queued. A post job is submitted when the run's PLTs are not on the
        remote and its .out files are all there. Uploads are checked by md5,
        and a local file is deleted only when its copy on the remote
        matches.

        It asks once, at the start, before deleting anything. Post jobs still
        go through Slurm, so run it again at the next login to carry on from
        where each case stopped.`,
    },
    {
      id: 'autoNeeds', kind: 'step', col: 3, row: 13, label: ['Handle what', 'it left to you'],
      planned: true, optional: true,
      title: 'Handle what it left to you (auto)',
      command: 'auto show',
      detail: `Cases listed under "needs you": a post job that failed, PLTs
        missing on the remote with no .out left to remake them, a run that
        stopped short with nothing queued. Each one names the step in the
        middle that deals with it.`,
    },
    {
      id: 'autoLog', kind: 'step', col: 3, row: 14, label: ['Check what it did'], planned: true,
      title: 'Check what it did (auto)',
      command: 'auto log\nauto status',
      detail: `"auto log" lists what earlier runs did and why; "auto status"
        shows the stage each case has reached. Restarts are not queued by
        auto: that stays with you.`,
    },
  ];

  // from/to are [node id, side]; side is t, r, b or l. A `back` edge is a
  // loop to an earlier step and is drawn dashed. An edge with `lane` runs
  // down that x position, clear of the boxes, between its two ends.
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
    { from: ['watch', 'b'], to: ['mode', 't'] },
    { from: ['mode', 'b'], to: ['running', 't'], label: 'By hand' },
    { from: ['mode', 'r'], to: ['autoShow', 'l'], label: 'auto' },
    { from: ['running', 'r'], to: ['liveWindow', 'l'], label: 'Yes' },
    { from: ['running', 'b'], to: ['ended', 't'], label: 'No' },
    { from: ['liveWindow', 'b'], to: ['post', 'r'] },
    { from: ['ended', 'l'], to: ['fix', 'r'], label: 'Failed' },
    { from: ['ended', 'b'], to: ['history', 't'], label: 'Out of time, or done' },
    { from: ['fix', 't'], to: ['restart', 'l'], back: true },
    { from: ['history', 'b'], to: ['uploadHistory', 't'] },
    { from: ['uploadHistory', 'b'], to: ['post', 't'] },
    { from: ['post', 'b'], to: ['outputCheck', 't'] },
    { from: ['outputCheck', 'b'], to: ['complete', 't'] },
    { from: ['complete', 'b'], to: ['uploadPlt', 't'], label: 'Yes' },
    { from: ['complete', 'l'], to: ['gaps', 'r'], label: 'No' },
    { from: ['gaps', 't'], to: ['post', 'l'], back: true },
    { from: ['uploadPlt', 'b'], to: ['cleanup', 't'] },
    { from: ['cleanup', 'b'], to: ['uploadRst', 't'] },
    { from: ['uploadRst', 'b'], to: ['goOn', 't'] },
    { from: ['goOn', 'l'], to: ['restart', 'l'], label: 'Yes', back: true, lane: 14 },
    { from: ['goOn', 'b'], to: ['track', 't'], label: 'No' },
    { from: ['track', 'b'], to: ['prepare', 't'] },
    { from: ['prepare', 'b'], to: ['analyse', 't'] },
    { from: ['autoShow', 'b'], to: ['autoApply', 't'] },
    { from: ['autoApply', 'b'], to: ['autoNeeds', 't'] },
    { from: ['autoNeeds', 'b'], to: ['autoLog', 't'] },
    { from: ['autoLog', 'b'], to: ['goOn', 'r'] },
  ];

  const COL_X = [130, 370, 610, 850];
  const ROW_Y = 84;
  const TOP = 40;
  const WIDTH = 950;
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
    if (edge.lane !== undefined) return [[x1, y1], [edge.lane, y1], [edge.lane, y2], [x2, y2]];
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
    return `<g class="flowchart-node ${node.kind}${node.planned ? ' planned' : ''}" data-id="${node.id}" role="button"
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
      [swatch('<rect class="flowchart-key planned" x="2" y="3" width="30" height="14" rx="2"/>'), 'auto: planned, not built yet'],
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
    const height = TOP + Math.max(...NODES.map(n => n.row)) * ROW_Y + 40;
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
      ${step.planned ? '<div class="flowchart-optional-tag planned">Planned: not built yet</div>' : ''}
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
