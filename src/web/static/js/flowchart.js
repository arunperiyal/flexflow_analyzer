// Help -> Flowchart: a plain, linear walkthrough of the real end-to-end
// workflow -- from a blank template to a plot in hand -- as a sequence of
// clickable steps (left) with the selected one's detail shown on the
// right. Deliberately not a real diagram with branches/connectors (see
// app.css's own comment on .flowchart-editor): a few steps that are
// genuinely "pick one of two" (single vs. multi case creation; the web UI
// vs. the CLI's one-shot plot) are folded into that one step's own detail
// text instead of forking the sequence.
const FlowChart = (() => {
  const STEPS = [
    {
      title: 'Create the template case directory',
      command: 'mkdir refCase',
      detail: `Make a directory (any name -- refCase here) that holds the
        template files for this problem. Every real case created later is
        derived from this one, so it's never run directly itself.`,
    },
    {
      title: 'Decide the problem name',
      command: null,
      detail: `Pick a short, consistent name for the problem -- e.g.
        "riser", "plate". Every template file in the next step is named
        after it, and that name stays consistent across every real case
        created from this template.`,
    },
    {
      title: 'Create the template .geo and .def files',
      command: '<problem>.geo\n<problem>.def',
      detail: `Named consistently after the problem (riser.geo,
        riser.def). Any parameter that should vary per real case gets a
        placeholder instead of a fixed value -- e.g. depth = #depth --
        filled in later from each case's own config.`,
    },
    {
      title: 'Create simflow.config',
      command: 'simflow.config',
      detail: `The solver config file the flexflow solver itself reads.
        Same idea as the .geo/.def files -- placeholders here for anything
        that should vary per case.`,
    },
    {
      title: 'Place the files in the template directory',
      command: null,
      detail: `Put <problem>.geo, <problem>.def, and simflow.config inside
        refCase. The template case directory is now complete -- nothing in
        it is ever run as-is, it's only ever a source for "case create"
        later.`,
    },
    {
      title: 'Generate the Slurm job scripts',
      command: 'use case:refCase\ntemplate script pre\ntemplate script main\ntemplate script post',
      detail: `Generates preFlex.sh, mainFlex.sh, and postFlex.sh -- the
        scripts "run pre/main/post" (further down) actually submit to
        Slurm. Each "template script" call takes optional flags to steer
        what it generates, and every generated script can also be edited
        by hand afterward.`,
    },
    {
      title: 'Generate the case config YAML',
      command: 'template case single\n# or\ntemplate case multi',
      optional: true,
      detail: `"single" writes a YAML for one real case; "multi" writes
        one for a parameter sweep (many cases at once). Either way, the
        result is a YAML file you edit to fill in the placeholder values
        (#depth and friends) -- without ever touching refCase or its
        files directly.`,
    },
    {
      title: 'Create the real case directory',
      command: 'case create myCase --ref-case refCase --from-config case_config.yaml',
      detail: `Builds the actual case directory from refCase, with every
        #placeholder filled in from case_config.yaml. This is the
        directory that actually gets run.`,
    },
    {
      title: 'Check the case before running anything',
      command: 'run check myCase',
      detail: `Validates the files a run needs (simflow.config, .geo,
        .def, job scripts, expected directories) and reports the last
        Slurm job's status if there was one. Cheap, and catches a missing
        or malformed file before it wastes a queue slot.`,
    },
    {
      title: 'Submit mesh generation (pre)',
      command: 'run pre myCase',
      detail: `Submits preFlex.sh to Slurm -- mesh generation (gmsh) and
        conversion. Returns a job ID, needed by the next step to queue
        the main run behind it.`,
    },
    {
      title: 'Submit the main simulation',
      command: 'run main myCase --dependency <preJobID>',
      detail: `Submits mainFlex.sh -- the actual solver run (mpiSimflow).
        --dependency queues it behind the pre job (afterok) so it waits
        for meshing to finish rather than racing it.`,
    },
    {
      title: 'Watch the queue',
      command: 'run sq --watch\n# run sc <id|name>  to cancel',
      optional: true,
      detail: `Polls Slurm for pre/main/post progress instead of raw
        squeue. "run sc" cancels a job if something needs to stop.`,
    },
    {
      title: 'Submit post-processing',
      command: 'run post myCase --dependency <mainJobID>',
      detail: `Submits postFlex.sh, turning the raw ASCII solver output
        into binary PLT files. Needed before the output is usable for
        anything downstream.`,
    },
    {
      title: 'Organise the output',
      command: 'case organise myCase --archive',
      optional: true,
      detail: `Housekeeping once post-processing is done: moves
        .othd/.oisd/.rcv into othd_files/oisd_files, dedupes overlapping
        files, and prunes intermediate .out/.rst/.plt files.`,
    },
    {
      title: 'Check the output is sound',
      command: 'case check myCase --all\n# or: case status myCase',
      optional: true,
      detail: `Validates OTHD/OISD ranges, simflow.config consistency,
        PLT completeness against the expected timesteps, and .def
        references. Worth running before trusting a plot.`,
    },
    {
      title: "Build the case's domain info",
      command: 'case domain myCase --init',
      optional: true,
      detail: `Derives domain.yml (bodies/field, geotags, plttags) from
        the .def file and PLT zones. Not required, but the web UI's
        picker uses it for an arc-length/axis-aware layout instead of
        generic coordinates -- worth doing before Plot -> New.`,
    },
    {
      title: 'Write the node maps',
      command: 'case out myCase --map',
      detail: `Writes one othd.<block>.map file per mappable block --
        row -> node/coordinate lookups. This is what the web UI's picker
        actually reads, and is required before a case shows any pickable
        points there ("Write map now" in Plot -> New does the same
        thing, from inside the app).`,
    },
    {
      title: 'Visualize: web UI or a one-shot CLI plot',
      command: 'ff --ui\n# or: python main.py --ui',
      detail: `Web UI (interactive, multi-panel, pick nodes visually):
        start it, then Case -> Add to register myCase, Plot -> New to
        build panels from the map/domain data, Layout -> Export to save
        a PNG or PDF.

        CLI one-shot (headless/SSH/scripted, or batch comparisons):
        "plot myCase --node N --data-type displacement --output foo.png",
        or "compare case1 case2 ... --node N --output cmp.png".`,
    },
  ];

  let activeIndex = 0;

  function escapeHtml(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function open() {
    Menu.openDialog(`
      <h2>Help &rarr; Flowchart</h2>
      <div class="flowchart-editor">
        <div id="flowchart-steps" class="flowchart-steps"></div>
        <div id="flowchart-detail" class="flowchart-detail"></div>
      </div>
      <div class="btn-row"><button id="flowchart-close" class="primary">Close</button></div>
    `, { wide: true });
    document.getElementById('flowchart-close').addEventListener('click', Menu.closeDialog);
    activeIndex = 0;
    renderSteps();
    renderDetail();
  }

  function renderSteps() {
    const box = document.getElementById('flowchart-steps');
    box.innerHTML = STEPS.map((step, i) => {
      const classes = ['flowchart-step'];
      if (i === activeIndex) classes.push('active');
      if (step.optional) classes.push('optional');
      const arrow = i < STEPS.length - 1 ? '<div class="flowchart-arrow">&darr;</div>' : '';
      return `<button type="button" class="${classes.join(' ')}" data-index="${i}">
        <span class="flowchart-step-num">${i + 1}.</span>${step.title}
      </button>${arrow}`;
    }).join('');
    box.querySelectorAll('.flowchart-step').forEach(btn => {
      btn.addEventListener('click', () => {
        activeIndex = Number(btn.dataset.index);
        renderSteps();
        renderDetail();
      });
    });
  }

  function renderDetail() {
    const step = STEPS[activeIndex];
    const box = document.getElementById('flowchart-detail');
    box.innerHTML = `
      <h3>${activeIndex + 1}. ${step.title}</h3>
      ${step.optional ? '<div class="flowchart-optional-tag">Optional</div>' : ''}
      ${step.command ? `<pre class="flowchart-command">${escapeHtml(step.command)}</pre>` : ''}
      ${step.detail.trim().split(/\n[ \t]*\n/).map(p => `<p>${p.trim()}</p>`).join('')}
    `;
  }

  return { open };
})();
