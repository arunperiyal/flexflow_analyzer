// Help -> Flowchart: the end-to-end workflow as a branching diagram, from a
// blank template to a plot in hand, with the selected step's detail on the
// right. After the jobs are queued it splits: by hand down the middle, or
// the `auto` command on the right (docs/AUTO_PLAN.md); steps not built yet
// are drawn dashed. NODES holds the steps (placed by hand on a col/row grid, so a new
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
      command: 'run main restart --time <tsId>',
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

        A job that is COMPLETING (ending, still writing its files) counts
        as running. A running or queued case can still be post-processed
        (right). Its history stays where it is until the run has ended.`,
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

        Only when no main job of the case is running, queued or
        completing: a queued job's mainFlex.sh archives the same files when
        it starts.`,
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
        othd_files/archive/, never cleaned/: --clean rewrites a cleaned part
        and cuts the steps a later run computed again. For a running case,
        the window picked on the right.

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
      command: 'case organise output --keep-freq <N>\ncase organise plt --delete-ascii\ncase organise plt --delete-binary',
      detail: `Only after the upload check above: --delete-binary does not
        look at the remote.

        In this order. "organise output" deletes each step's .out once its
        .plt exists, so it has to run while the PLTs are still here; it keeps
        the .rst of the steps divisible by N (your choice, e.g. 500), plus
        the restart point in simflow.config, the two newest complete sets
        (--keep-newest, default 2: if the newest was cut short when the job
        was killed, the one before it restarts the run) and a set still being
        written. --delete-ascii deletes the ASCII PLTs that have a newer
        binary copy, so it goes before --delete-binary.`,
    },
    {
      id: 'uploadRst', kind: 'step', col: 1, row: 21, label: ['Upload the restart sets', 'on the upload grid'],
      title: 'Upload the restart sets on the upload grid',
      command: 'case upload rst --t1 5000 --t2 5000',
      detail: `Restart sets have two jobs. The ones kept here (every 500, say)
        are insurance against a failed run. The ones on the remote are to
        resume the run in the future, so a coarser grid is enough: the steps
        divisible by upload_rst (say 1000), only the ones the remote lacks,
        one command per step. The newest set is not needed while the run
        goes on, but a finished run's final set is, to extend it later.`,
    },
    {
      id: 'goOn', kind: 'decision', col: 1, row: 22, label: ['Does the run', 'go on?'],
      title: 'Does the run go on?',
      command: null,
      detail: `Not yet at maxTimeSteps: queue a restart from the newest
        restart set ("run main restart --time <tsId>"), often before the current job
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
      id: 'autoInit', kind: 'step', col: 3, row: 11, label: ['Set up .cases.yml'],
      title: 'Set up .cases.yml (auto)',
      command: 'auto init --remote cloud --path /shares/.../bare --keep-rst 500\nuse remote:cloud',
      detail: `Once per folder of cases and remote. .cases.yml (made by "case
        add") lists the cases, and under "remotes" the folder these cases have
        on each remote. "auto init --remote NAME" adds that folder (--path,
        default: the remote's "remote set-path") and auto's settings: the .rst
        grid to keep (--keep-rst) and the size above which a running case is
        flagged (--disk-alert).

        A folder it cannot know is left as EDIT_ME: "auto show" will not run
        until it is set. An existing folder is kept unless --force. Several
        remotes can be listed; "use remote:NAME" or --remote picks one.`,
    },
    {
      id: 'autoShow', kind: 'step', col: 3, row: 12, label: ['See the plan'],
      title: 'See the plan (auto)',
      command: 'auto show <case>\nuse case:*\nauto status\nauto commands',
      detail: `For the case (the argument or "use case:"), or every case in
        .cases with "use case:*", like case check: its state, then what "auto
        apply" would do and why: organise the history, a post job and its
        steps, uploads, and what is deleted once its copy on the remote is
        checked, as labelled sections (State, History, PLT, OUT and RST files,
        Inputs) with numbered Action commands. Several cases show a summary
        table (each in full with --detail); "auto status" is one line per
        case, "auto commands" just the commands. It changes nothing.

        Each case uses the .auto.conf of its parent folder.

        If the queue cannot be read, no case is looked at: one that looks
        idle may be running.`,
    },
    {
      id: 'autoApply', kind: 'step', col: 3, row: 13, label: ['Carry it out'],
      title: 'Carry it out (auto)',
      command: 'auto apply --dry-run\nauto apply\nauto apply --only upload',
      detail: `Does the additive steps for each case, in this order, planned
        again from the files and the queue right before each: organise the
        history (when no main job is active), upload what the remote lacks
        (to a temporary name, checked by md5, then renamed; recorded in
        auto_logs/ledger.json), submit a post job for the first stretch of
        steps with no PLT yet. It shows what it will do and asks once.
        Nothing is deleted. A step that fails stops that case; the record of
        the run is auto_logs/auto_<time>.log.

        Post jobs still go through Slurm, so run it again at the next login
        to carry on. Deleting what is safely copied (.out, PLTs, .rst
        thinning) is not built yet: those steps stay by hand.`,
    },
    {
      id: 'autoNeeds', kind: 'step', col: 3, row: 14, label: ['Handle what', 'it left to you'],
      optional: true,
      title: 'Handle what it left to you (auto)',
      command: 'auto show',
      detail: `The cases "auto show" lists under "needs you", which auto
        does not guess at: a main job that failed; a post job that ended
        badly, or completed without making the PLTs of its steps; holes on
        the remote; PLTs missing with no .out left to remake them; archive/
        pruned (every case keeps archive/ and cleaned/); a run stopped short
        with nothing queued. Each is handled by the step in the middle that
        fits.`,
    },
    {
      id: 'autoLog', kind: 'step', col: 3, row: 15, label: ['Check what it did'], planned: true,
      title: 'Check what it did (auto)',
      command: 'auto log',
      detail: `Lists what earlier runs of "auto apply" did and why. Restarts
        are not queued by auto: that stays with you.`,
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
    { from: ['mode', 'r'], to: ['autoInit', 'l'], label: 'auto' },
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
    { from: ['autoInit', 'b'], to: ['autoShow', 't'] },
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
      [swatch('<rect class="flowchart-key planned" x="2" y="3" width="30" height="14" rx="2"/>'), 'Planned, not built yet'],
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
