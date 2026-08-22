# FlexFlow Changelog

## Unreleased

### ✨ `field compute wall_shear` / `separation`: where the flow leaves the surface

- **`field compute wall_shear` *(new)*** — viscous wall shear on every surface
  element, read straight out of the vorticity the solver already wrote. At a
  no-slip wall the velocity vanishes on the surface, so every tangential
  derivative of it does too and the stress collapses to an **identity**,
  `tau_w = mu_eff * (omega x n)` — exact, not a reconstruction. `xVor/yVor/zVor`
  are in the PLT, so nothing is differentiated at the one place an unstructured
  mesh is worst conditioned, and nothing outside numpy is loaded to do it.
  `mu` comes from the .def through the same chain as the density; `mu_eff` is
  `mu + rho*eddy`, and every table records the largest eddy viscosity actually
  seen at the wall, so "mu_eff = mu here" is a measurement rather than a hope.
  Writes `<body>.wall_shear/elements_<step>.csv` with the same leading columns as
  a force table, so one reader serves both.
- **`field compute separation` *(new)*** — the separation angle per spanwise
  section per timestep, plus a per-bin azimuthal table. A **reduction over what
  wall_shear wrote**, opening no PLT: the expensive part is reading a 162 MB file
  per step, and re-binning it at a different `--azimuthal`/`--sectional` costs
  nothing.
- **Two conventions, written into every header** because a reader that guesses
  them will guess one wrong. `theta = 0` at the forward stagnation point,
  increasing towards the lift direction, in (-180, 180]. And a section's centre is
  the **declared** axis (domain.yml origin + station × axis) plus the mean
  displacement around that ring — not the mean of the ring's own coordinates. On a
  round body the two agree; on a grooved one the facets are not symmetric about
  the axis, so the coordinate mean drifts with angle and reads as a separation
  shift that is not there.
- **The first zero is not separation.** `Cf_theta` vanishes at the forward
  stagnation point too, and on a deflecting, shedding body that point is not at
  `theta = 0` either. Each branch is walked outward from the front, its peak
  found, and the first sign change taken *after* it — interpolated between bins,
  since quantising puts a 10-degree staircase in a quantity whose interest is that
  it moves a degree or two along the span. A side that never reverses is `nan`,
  and `reversed_fraction` (area-weighted, so a grooved section's uneven facets
  cannot vote twice) is one number per section that survives an ambiguous crossing.
- **`DefConfig.viscosity()` *(new)***, sharing the material-chain walk with
  `density()`.

### 🐛 Sections were anchored to the mesh, not to the body

- `force_coeff --sectional` binned from the **first element centroid** rather than
  from the body's declared origin. That makes the slice edges a property of the
  discretisation: on a mesh whose element layers do not begin half a slice in, 96
  uniform layers land in slices of 1, 2 and 3 — measured at **252–756 elements
  against a uniform 504**, with about half the elements in the wrong slice, which
  reads as a spanwise variation and is not one. It also means two meshes of the
  same body get different slices, so their tables cannot be compared. Sections are
  now anchored at `domain.yml`'s origin, and a body that declares none says so.
  Unchanged on a mesh that happens to start half a slice in, which is why it was
  invisible on the bare cylinder.

### ✨ `field compute force_coeff`: Cd and Cl, normalised by what the case says

- **`field compute force_coeff` *(new)*** — the same pressure force `force`
  integrates, divided by a reference state: whole-body Cd/Cl per timestep, and
  with **`--sectional N`** the body cut into N spanwise slices with Cd/Cl for
  each, one table per timestep. This is the calculation that until now lived as a
  five-module script in a case's `binary/` directory, re-copied and re-edited per
  case.
- **The reference state is read, not typed.** `Cd = Fd / (½ρU²A)` needs four
  things no PLT holds, and the case already says all of them:
  - **ρ** from the .def, followed through its own chain of names —
    `elementGroup` → `elementProperty` → `materialModel` → `densityModel`;
  - **U and the flow direction** from `domain.yml` — the field's declared
    `velocity`, whose magnitude is U and whose direction is what drag is measured
    along; lift is perpendicular to it and to the span (`flow × span`);
  - **D, L and the span axis** from `domain.yml` — which is what `case domain` was
    for.

  The free stream is **declared, not read from the .def**. The nearest thing the
  .def has is `initField( velocity )`, and that is the *initial condition*: a case
  started from rest, or ramped up at the inlet, has one that says nothing about the
  flow the body ends up in — right often enough to be trusted, wrong quietly enough
  to matter.

- **Headers carry values, and the common block sits in `summary.csv`.** Each table
  states what a Cd was divided by as a number — `rho: 1000`, `q = 0.5*rho*U^2: 500`
  — rather than naming the file it was read from, since a `domain.yml` can be
  edited afterwards and a pointer to one says nothing about the numbers beneath
  it. The full reference block goes on `summary.csv`, which the run produces once;
  a `sectional_<step>.csv` carries four lines instead of twelve — which run, which
  step, and the single line needed to read its own rows. Each table names the area
  *it* used, so a one-file `--output NAME.csv` of sections says `D * dx` rather
  than the whole-body `D * L`. Where each number was read from is reported by `-v`.
  `--direction` and `--flow` override the two directions (`--flow` re-aims drag;
  U stays the declared magnitude); nothing else is overridable and **nothing is
  defaulted**. A body with no radius, or a field with no velocity, is an error
  naming the command that sets it, because a Cd normalised by a guessed diameter
  is wrong by exactly the factor nobody notices. Every number and its origin goes
  into the `#` header of each table written.
- **Validated against the case's own reference implementation.** `examples/`
  ships `sectional_Cd_Cl_<step>.csv` produced by the hand-rolled `binary/main.py`;
  the new command reproduces them to ~1e-9 relative — sectioning, axes, sign of
  lift and reference areas all agree. That comparison is a test.
- **`--zone` now resolves through `domain.yml`** for every `field compute`
  quantity: a body has three names and only the plttag is what a PLT calls it, so
  a name that is not a zone is looked up as a body before being called missing.
- **Output directories are named after the body**: with no `--output` (or one
  given with no name), a run writes to `<body>.forces` / `<body>.force_coeff` in
  the case directory. One place per body, so a case holding several does not have
  their tables collide, and a case organises itself without anyone inventing a
  name. The body is the one `--zone` names, resolved through `domain.yml` where
  there is one, so a zone `cyl` belonging to a body called `riser_body` writes to
  `riser_body.forces`. `--output NAME` is unchanged.
  *(Behaviour change: `field compute force` used to write nothing without
  `--output`. It now always writes; the totals still print either way.)*
- **`parse_blocks` reads unquoted block labels.** `initField( velocity )` writes
  its label bare where most of the .def quotes it; reading only the quoted form
  skipped the block silently, which is how the free-stream velocity went missing.
- **`DefConfig.density()` *(new)*** — the .def reader the above needs, following
  the chain rather than assuming a fixed key and returning `None` rather than a
  stand-in when a link is broken. There is deliberately no free-stream reader: see
  above.

### ✨ `case domain`: one name for a body, instead of four

- **`case domain` *(new)*** — a case names the same cylinder four times, in four
  vocabularies, and joins none of them up: `beamSolid( "beam_1" )` in the .def,
  `riser.cyl.srf` / `riser.cyl_BL.nbc` on disk, zone `cyl` in the PLT, and
  `outputTimeHistory( "riser_probe" )` writing along `riser.cyl_nodes.nbc`. So
  `field compute --zone cyl`, `case out --map cyl_nodes` and the beamSolid the
  displacements belong to are four names for one body, and only the person at the
  keyboard knows it. The command writes that join down once, in a **`domain.yml`**
  beside the .def, as a `field` and a list of `bodies` each carrying a **`name`**,
  a **`type`** (`beam` / `rigid` / `fixed`, the field is `fluid`), a **`geotag`**
  (the token in its geometry file names) and a **`plttag`** (its zone in a PLT);
  a body also carries **`geometry`** and **`outputs`** (the outputTimeHistory
  blocks written along it, each with the node file that orders its records), and
  the field a **`velocity`**. An entry resolves by *any* of its names, so
  whichever one a caller has to hand will find it.
- **It says where a thing is, not what it is made of.** A beam's stiffnesses and
  the fluid's density are not in it: the .def has them and the solver reads them
  from there, and a second copy would only drift. What *is* in it is what the case
  states nowhere — a body's **radius** and the field's **velocity**. Neither is a
  copy: the mesh has the shape but no number saying which diameter to normalise
  by, and the .def has no free stream at all, only an initial condition. Both are
  declared, and both start out `null`.
- **`--init` derives it from the case's own files.** The field is the first
  `elementGroup`, tagged from the element file it names (`riser.fluid.cnn` →
  `fluid`). Every `beamSolid` becomes a body, with origin, length and axis from
  `pnt1`/`pnt2`; its geotag comes from `surfaceOutputs` → `outputSurface` → the
  `.srf` that block names, and its outputs are the nodal `outputTimeHistory`
  blocks whose node file carries the body's tag (`riser.cyl_nodes.nbc` belongs to
  `cyl`; `riser.cylinder2.nbc` does not). plttags come from the zone names in the
  newest PLT under `binary/` — volume zone to the field, surface zone to a body —
  reading the header only, so it stays fast on a 500 MB file. A beam's **radius**
  is in the mesh, not the .def, so it is written `null` rather than guessed: a
  guessed radius silently rescales every coefficient normalised by it. Everything
  `--init` could not work out is printed as a note, including a body nothing
  records a history for and the velocity it will not guess at.
- **Editing:** `case domain body --list / --show NAME / --add / --remove NAME`,
  `case domain field --list / --show / --set`, with `--set key=value` taking
  dotted keys (`geometry.radius=0.5`) and reading the value as YAML, so `0.5` is a
  number and `[0, 0, 0]` is a vector. Anything else you want on an entry can be
  set by hand or with `--set`; `--init` simply does not invent it. Shorthands `--type --geotag --plttag
  --radius --length --origin --axis` write the same places. On `--add`, geotag and
  plttag default to the body's name and it says so.
- **Refusing to overwrite says when the existing file is from an older shape.**
  `--init` never overwrites, so a domain.yml written before `properties`/`source`
  were dropped stays as it was, and a fresh one looks different for no visible
  reason. The refusal now names the retired keys it still carries and says
  `--force` rewrites it.
- **`--check`** validates the file against the case: geotags against the geometry
  files present, plttags against the real PLT zones, every output's node file
  against what is on disk, types against the closed vocabulary, and every name/tag
  for collisions. Exits non-zero on an error. The
  errors it would raise are also reported straight after any edit.
- The `*` wildcard case works for `--list` and `--init` across the `.cases`
  registry; it is refused for edits, which would write the same body into every
  case.
- **`DefConfig.evaluate()` / `.resolved_variables` *(new)*** — `define{}` values are
  written in terms of each other (`SPAN = 12*DIA`, `EI = (4*PI^2 * ...)/(...)`), so
  a caller wanting a number has to follow the chain. It now can — which is what
  turns `pnt2 = {SPAN, 0, 0}` into a body 12 long — with `^` read as
  exponentiation rather than Python's xor, over an AST whitelist rather than
  `eval`. Non-arithmetic values (`fixFix`) and cycles give `None` rather than
  raising.
- **`parse_blocks()` *(new, in `def_parser`)*** — reads any `kind( "name" ) { ... }`
  block by matching braces by depth. The existing `\{([^}]*)\}` regexes cannot:
  a `beamSolid` body holds `pnt1 = {0, 0, 0}`, so the first `}` closes a vector and
  the parse ends four lines in, losing `bcType`, `activeDof` and `surfaceOutputs`.

### ♻️ Field command: Tecplot-free backend

- **Removed the Tecplot/pytecplot dependency** from `field`. PLT files are now
  read by a pure-numpy parser (`src/plt/fxplt.py`) — no Tecplot 360 license,
  and it works on Python 3.13+. Deleted `src/tecplot/`, the old
  `TecplotConverter`, and the duplicate `src/commands/field.py`.
- **`field info`** rewritten on the new backend; adds an **element-type / `nen`
  audit** that flags an 8-node brick mesh mis-written as 4-node tetrahedra
  (`simflow.config nen=4` → advises `nen=8`) and checks file-size consistency.
- **`field extract`** rewritten Tecplot-free: nodal variables with x/y/z
  subdomain filtering. Output by extension: **`.csv`** (tabular), **`.vtu`/`.vtk`**
  (a trimmed *mesh* carrying only the selected variables — cells kept, so it is
  contourable in ParaView), or **`.pvd`** (a time series of per-step trimmed
  meshes for a range). A bare `--output NAME` (no extension) creates a directory
  `NAME/` and writes the outputs inside it (`NAME/NAME.pvd` + per-step `.vtu`, or
  `NAME/NAME.vtu`); relative output paths are placed under the case directory.
  Supports a **timestep range** via
  `--t1`/`--t2` (or the `t1`/`t2` context): all PLTs in the range are
  consolidated into a single output with a `timestep` column/array; `--t1`
  alone (or `--timestep`) extracts one step. `--freq N` sub-samples the range to
  steps that are multiples of N. `--output` (alias `--output-file`) is required.
- **`field convert`** *(new)* — PLT volume zone → VTK `.vtu` (meshio), with
  `--nen` override, `--audit-only`, and an `--xmin…--zmax` **box crop** that
  exports a sub-region mesh (cells preserved).
- **`field check`** *(new)* — validate a produced file (`.vtu`/`.vtk`/`.vtp`, or
  a `.pvd` time-series collection): reports points, cells, bounds, and per-array
  ranges; for `.pvd` it lists timesteps, verifies every member file exists, and
  summarises one member. Flags empty files / NaN/Inf and exits non-zero on problems.
- **`field render <mode>`** *(new)* — pictures via **pyvista**, in two modes that
  differ only in the surface they cut out of the volume:
  - **`iso`** — an isosurface of a scalar (`--contour`, `--values`), the usual
    Q-criterion view of vortex tubes, coloured by another variable.
  - **`slice`** — a cut plane (`--normal` as an axis or a vector, `--origin`), or
    **`--slices N`** planes evenly spaced along that normal, placed strictly
    inside the mesh since a plane on a bounding face cuts nothing. A plane is
    invisible edge-on, so a slice defaults to a single view straight down its
    normal in parallel projection rather than iso's four.
  Both share the config-driven YAML (background, resolution, domain crop,
  threshold, camera orientation, and reusable camera frames from ParaView
  `.pvsm`/`.py` Save State or a saved `.yml`), and both auto-convert a case's PLT
  to a cached `.vtu`. `--write-template` writes the template for the mode asked
  for; a section belonging to the other mode is warned about rather than
  silently ignored, and a flag belonging to the other mode is an error.
  **`--output`** picks the format by extension: a bare `NAME` is the image
  prefix, `NAME.png` is that one image, and `.vtp`/`.vtu`/`.csv` write the cut
  surface itself with **no image rendered** — that path never constructs a
  plotter, so it works on a headless box without OSMesa.
- **`lambda2` as a contour variable, computed when the solver did not write it.**
  A vortex criterion is a function of the velocity gradient, so `lambda2` is
  derivable from U/V/W: the middle eigenvalue of S²+Ω² (Jeong & Hussain).
  `field render iso --contour lambda2 --values -1` computes it on demand — note
  it is **negative** in a vortex core, the opposite convention from
  `QCriterion`. Validated against the case's own QCriterion: correlation with
  −Q is 0.994, and 9.7% of nodes fall inside cores. It costs ~15s per timestep
  on 1.8M nodes, so it is **written back into the cached `.vtu`** (+5 MB) and a
  re-render is free; `input.cache_derived: false` turns that off.
- **`field compute lambda2 CASE --output NAME.vtu`** materialises it instead, for
  ParaView or anything outside FlexFlow. A nodal volume field, so unlike
  `compute force` it takes no `--zone`; a step range writes one file per step.
- **`field list`** *(new)* — the names you must know before you can use them, and
  which are not discoverable from your data. **`--color`** lists colormaps
  grouped by the kind of field they suit (diverging for signed quantities like
  velocity or lambda2, sequential for magnitudes, cyclic for phase), names the
  qualitative ones to avoid because a continuous field reads as banding, and
  gives the ParaView preset names that are accepted and translated. **`-v`**
  adds every installed colormap. **`--variables`** lists what can be computed.
- **`body:` / `--body ZONE`** — draw a surface zone alongside the isosurface, so
  the vortex tubes are seen against the body they shed from
  (`field render iso CASE --body cyl`). Colour, opacity and edges via the
  `body:` block in a config; a solid colour by default, since a second scalar
  bar competing with the isosurface's is rarely what was meant, or
  `body.variable` to colour it by a scalar. The zone is re-read **at every
  timestep** — a deforming riser moves, so a surface cached from one step would
  be drawn in the wrong place at the next. The camera frames the union of both,
  or a body spanning the domain would be cut off. When the isosurface comes out
  empty but a body is set, the body alone is still drawn: over a sweep those
  steps would otherwise be holes in the sequence.
- **`background: white` produced a black background.** `NAMED_COLORS["white"]`
  was `[1, 1, 1]` — *integers* — and pyvista reads an integer triple as 0-255,
  so white came out as RGB(1,1,1). `black` worked only because 0 is 0 either
  way, and `gray` only because it happened to be written as floats. The default
  background was the same literal, so **every render ever made had a black
  background**. Colours are floats throughout now, and `to_rgb` accepts either
  convention: anything above 1 is treated as 0-255, so `[255, 255, 255]` and
  `[1.0, 1.0, 1.0]` both give white.
- **`--no-vtp`** — images only. A `.vtp` of the cut surface is written beside
  each image by default (`output.save_vtp`), which is one more file per timestep
  and adds up over a sweep. The flag only turns it *off*, so it overrides a
  config that left it on without needing a config edit. The template now says
  what the setting costs, and notes that `output.prefix` is ignored — paths come
  from `--output` and the case directory.
- **An interrupted conversion no longer poisons the .vtu cache.** A render
  converts each PLT to a `.vtu` sidecar and reuses it when it is newer than the
  PLT — but a run killed mid-conversion left a *half-written* sidecar that was
  also newer, so every later run trusted it and failed inside VTK with
  `Error parsing XML ... no element found` followed by a misleading
  `Data array (U) not present`. Conversions now write to a temporary name and
  rename into place, so an interrupted one leaves nothing; an existing
  half-written sidecar is detected (a complete `.vtu` closes its `</VTKFile>`)
  and rebuilt rather than trusted.
- **A render error no longer gets blamed on the display.** The headless handler
  replaced *any* exception with "no display, and no working off-screen GL"
  whenever `DISPLAY` was unset — so a malformed config, a missing variable and a
  dead X server all read as the same problem, and the real cause was thrown
  away. The actual error is now always reported, with the headless note added
  underneath only as a possible contributing factor.
- **`--camera` given a render config is an error**, not a silent wrong picture.
  `load_camera` returned the whole config dict, whose `position`/`focal`/`up`
  are all absent, so the camera was left at VTK's default and a plausible-looking
  image came out of the wrong viewpoint with no warning. A frame without a
  `position:` is now rejected, and a file carrying config sections is named as
  such and pointed at `--config`. It is checked when the flag is read, so a bad
  camera stops the run before it converts a hundred PLT files.
- **`color.range` from a config is validated.** `range: [-0.5 0.5]` is valid
  YAML for a one-element list holding the *string* `"-0.5 0.5"`, which reached
  pyvista and failed there as `IndexError` with nothing pointing back at the
  file. The missing comma is now named.
- **A multi-step render says where it is** (`[7/100] timestep 350`). A hundred
  steps each converting a PLT and rendering can run for many minutes, and
  silence looks like a hang.
- **`--pick-camera FILE` / `--camera FILE`** — set the view once by eye and pin
  it across every timestep, which is what a Tecplot `.sty` is for.
  `--pick-camera` opens a window on one step; orbit to the view you want, close
  it, and that camera is written as a `.yml`. `--camera` renders from a saved
  frame: **one** image per step instead of the mode's default views, the camera
  identical in all of them. Picking needs a display and says so plainly when
  there is none (a virtual framebuffer does not help — you have to see it), so
  pick locally or over `ssh -X` and carry the file to the cluster.
  `--camera` also takes a ParaView **`.pvsm`**/`.py` Save State, and a view's
  `camera_file:` in a `--config` file takes any of the three.
- **`save_camera()` now exists.** `src/plt/camera.py` could read a `.yml` frame
  and its docstring advertised one "written by the GUI helper (save_camera)" —
  which was never written, so the format had no producer and the round trip was
  half a feature.
- **`--t1`/`--t2`/`--freq` render a whole range** — one figure per timestep in
  it, rather than a single step. The `t1`/`t2`/`freq` context feeds them, so
  `use t1:100 t2:500` then `field render iso` draws the sweep. (`--timestep`
  still takes one step; `field convert` keeps taking `--timestep` from `t1`.)
- **Output always goes in a directory under the case.** One run writes a file
  per camera view and a range multiplies that by the number of steps, so loose
  files named after the `.vtu` landed in the case's `binary/` among the PLTs.
  `--output NAME` now names the directory (`<case>/NAME/`, default
  `render_<mode>/`) and its extension picks what goes inside — `.png` for images
  only, `.vtp`/`.vtu`/`.csv` for the cut surface. Files inside are
  `<NAME>_<step>_<view>.png`, so a range sorts by step.
- **`--color-range MIN MAX`** fixes the colour scale. Without it the scale is
  taken from each surface as it is built, so the same variable gets a different
  scale at every timestep — two frames cannot be compared, and a sequence of
  them cannot be animated. Rendering a range without it is **warned about**.
  It applies to `slice` as well as `iso`, since the colouring is shared. Two
  space-separated numbers rather than `MIN,MAX`: argparse reads a lone `-0.5` as
  a value but `-0.5,0.5` as an option name, so the comma form would have
  rejected every range with a negative minimum. *(The same trap still applies to
  `field extract --probe -2.5,0,0`, which predates this and is not fixed here.)*
- **A case context no longer lands in the mode slot.** With `use case:X` set, a
  bare `field render` had the case injected at position 3 — but position 2, the
  mode word, was still empty, so the case slid into it and the command answered
  *"Unknown render mode /path/to/case"* instead of showing help. `field compute`
  had the same bug for its `quantity`, and `template script` for its type.
  Injection now requires every slot *before* the case to be filled.
- **A headless box gets a virtual framebuffer** when one is available: off-screen
  rendering still needs a GL context, and VTK prints *"bad X server connection"*
  without one. `xvfb` is started automatically if installed. The warning is
  cosmetic on a VTK that can fall back — images still come out — and when it
  genuinely cannot render, the error now names the ways out rather than leaving
  a raw VTK warning, including `--output NAME.vtp`, which needs no GL at all.
- **Nothing to render shows the mode's help**, not just a one-line complaint:
  `field render iso` with no case, no `--vtu` and no `input.vtu` is someone
  finding their way.
- **`field render --zone` now does something.** It was accepted and dropped on
  the floor: the conversion call never passed it on, so every render used the
  first volume zone whatever was asked for. The cached `.vtu` sidecar is named
  per zone (`<plt>.z<N>.vtu`), since a zone-specific conversion must not be
  handed back for the default one.
- **`use var:` / `use zone:` context** — set a default variable list / zone once
  and they're auto-injected into `field extract` (`--variables`, `--zone`) and
  `--zone` into `field convert`/`render`. A **`freq`** context injects `--freq`
  into `field extract` and `run post`. Shown in `pwd`, cleared via
  `unuse var`/`zone`/`freq`/`all`, with tab completion.
- **Fixed context injection scope**: `node`/`t1`/`t2` are now injected only where
  the target actually defines those flags — `data show` (node/t1/t2),
  `data stats` (node only), `plot` (node/t1/t2). They are no longer pushed into
  `field` commands (which don't accept them), and `t1`/`t2` are no longer pushed
  into `data stats`.
- **Dependencies**: removed `pytecplot`; added `meshio`, `pyvista`.

### ✨ New Features

#### `remote` — help per subcommand
- Every `remote` subcommand now has **its own help**, in a new
  `remote_impl/help_messages.py`: what the arguments mean, what is required,
  examples, and the notes that matter (remotes live in
  `~/.flexflow/remotes.json` with the **password in plain text**; nothing is
  contacted when a remote is added, so a wrong password only shows up on the
  first transfer; `remote modify` does not touch the base path).
- **A bare `remote add` prints that help** instead of `Error: remote name is
  required` — the error said what was missing but not what the command wants,
  and there was nowhere to read the flags. Same for `modify`, `delete` and
  `set-path`. An *incomplete* command (a name but no `--user`) still leads with
  what is missing, now naming each flag, and prints the help after it.
- **`remote add -h` showed the group help**, which listed all five subcommands
  and every flag any of them takes; it now shows `add`'s own.
- Both paths exit non-zero, so a command that did nothing does not report success.
- `--ip` is documented as an **IPv4 address**: the validator has always required
  four dotted octets, while the old help offered "IP address or hostname".
- Interactive tab completion knew the flags of `case out` and `field compute`
  but not the subcommand names themselves, so neither completed after `case ` /
  `field `. `field compute <TAB>` now offers `force` and `field render <TAB>`
  offers `iso`/`slice`, via the `_POSITIONAL_CHOICES` hook that already existed
  for `template` and had no `field` rows.

#### `case out` — a case's declared outputs, and maps that keep othd readable
- New **`case out`** subcommand (listed in `case --help`). **`--map`** writes
  one `othd.<block>.map` per `outputTimeHistory` block in the case's `.def` that
  names a file its records are indexed by:
  - **`type = nodal`** → `row, node, x, y, z` — the record's index, the mesh node
    it belongs to, and that node's **undeformed** coordinates from the mesh.
  - **`type = coordinates`** → `row, x, y, z` — the points the block asked for,
    read straight from its own probe file. No mesh is touched, and there is no
    node column: a requested point need not sit on one.
  - Any other type names no file to index its records by, so it is reported and
    skipped. The mesh file is only required when a nodal block is present, so a
    case of nothing but coordinates blocks maps without it.
- Why: a nodal history is written *positionally* — row k is the k-th node of the
  block's node file, with no id and no coordinate in the othd itself. Reading one
  back has therefore required the node file **and** the mesh coordinates, and the
  coordinates file is usually the largest input in a case (137 MB for a 1.8M-node
  riser) even when the output covers 49 nodes. With the map written, it can be
  deleted.
- Maps are named after the **block**, not its input file: two blocks may read the
  same node file at different frequencies, and naming by file put both on one
  path with the second silently overwriting the first. The name is also what the
  `.def` and the map header call the output, so the file agrees with its contents.
- Rows keep the source file's order, because that order is what indexes the othd —
  they are deliberately not sorted.
- Each map carries **`# othId: <n>`**, the output's index within the othd, so a
  reader holding two maps can tell which belongs to which block. Declaration order
  does not give it: an output whose input file is **missing or empty is not written
  at all**, and every id after it shifts down — on `BR0SG0U1P0`, `probe_dat.txt` is
  absent, so `"riser_probe"` is othId 0 rather than 1. The id is *predicted* from
  the `.def` and the files present rather than read from an othd, and the header
  states that basis: a reader that trusts a wrong id is worse off than one with
  none. When an input file is **newer than the case's othd files** — those were
  written without it, so their ids are lower — that is warned about and noted in
  the map.
- A `coordinates` point file is read as **`index x y z`** when it has four columns
  and the first reads as a row index, or `x y z` when it has three; the layout is
  checked rather than assumed, and anything else errors. Taking the first three
  fields of a four-column file turns the point `(0, 0, 3)` into `(1, 0, 0)` with
  nothing downstream able to detect it.
- A block whose input file is missing or empty is now **skipped rather than fatal**
  when scanning every block, matching what the solver does — naming it explicitly
  with `--map NAME` still errors. This also fixes a regression from mapping
  coordinates blocks: `case write --othd-map` had started failing outright on
  `BR0SG0U1P0`, whose `.def` references an absent `probe_dat.txt`.
- The coordinates file is read from the `.def`'s `nodeCoordinates` block rather
  than assumed to be `<problem>.crd`, and every map in a case is built from a
  single streamed pass over it. `--othd-map NAME` restricts it to one block, by
  block name or node/point-set name.
- **`--list`** prints a table of the case's `outputTimeHistory` blocks — *Name, File,
  OthId, Type, MapFile, Probe* — answering which blocks have maps yet and what
  each othId holds. It reads both sides: the blocks from the `.def`, the probe
  geometry back out of any map already written, since that is declared rather
  than derived. A missing input file is marked and its OthId shown as `--`,
  because the solver writes no record for it and later ids shift down. The table
  states that OthId is predicted, never presenting it as measured. `outputSurface`
  (which feeds the `.oisd`) is not covered yet.
  With the **`*` wildcard** (or `use case:*`) it surveys every case in the
  `.cases` registry as **one table with a Case column**, rather than one table
  per case: the question `*` asks is which cases still need mapping, and that
  is answered by scanning a column. A case it cannot read is reported under
  the table and does not end the run, and the title says how many of the
  registry actually made it in.
- Accepts the **`*` wildcard case** (including via `use case:*`), mapping every
  case in the `.cases` registry in turn. A case with nothing to map is *skipped*
  and one that genuinely fails is *reported*, and neither ends the batch — so a
  registry holding cases at different stages still gets the ones it can. The run
  exits non-zero only when no case could be mapped at all.
- **`--probe-type point|line|helix|surface|cloud`** declares how a probe set should
  be read — arc length along a line, axial position and angle along a helix, two
  coordinates on a surface, nothing shared between independent points — with
  **`--closed`** marking a curve that joins up.
  Recorded in the map as `# probe:` / `# closed:` and explicitly marked
  **declared, not derived**: it cannot be inferred from the coordinates (a dense
  grid snakes into a uniform-step path indistinguishable from a curve; rank alone
  does not separate a ring from a grid) and it is not in the `.def` or `.nbc`
  either. It applies to the maps a run writes, so `--othd-map NAME` gives
  different sets different types.
- `def_parser` gained `parse_output_time_history()` and `parse_node_coordinates()`,
  both of which strip `#` comments first so a commented-out block is never read
  as live.

#### `field compute force` — per-element pressure force on a surface zone
- New **`field compute <quantity> <case> --zone ZONE`** subcommand. `force` writes,
  for every surface element and every selected timestep, its centroid, **area**,
  **outward unit normal**, face pressure and the pressure force **−p n dA**:
  `timestep, element, x, y, z, area, nx, ny, nz, <Pressure>, Fx, Fy, Fz`.
  Without `--output` it prints the integrated totals per timestep instead.
- Areas and normals come from the **mesh itself**, so a grooved or otherwise
  non-circular section needs no special handling — no assumed cross-section, no
  `πD·dx` per-node area, no equal-chunk station binning. On the bare-riser case
  this removes a **2.1% bias**: allocating `πD·dx` across 49 stations covers 12.25
  units of span instead of 12.0, so the ends are double-counted.
- Normals are oriented **against the volume zone**: a body is a hole in the mesh,
  so each surface element belongs to exactly one volume cell, and that cell is on
  the fluid side. Verified unanimous over all 6,144 faces of the riser. Elements
  with no adjacent cell fall back to orienting the zone by its enclosed volume,
  and that is reported rather than assumed.
- The surface-to-volume mapping is built **once** and reused, since the element
  list does not change between timesteps (checked: byte-identical connectivity
  across `riser.100`…`riser.500`). If it ever does change, the command says so and
  rebuilds instead of silently trusting it.
- A bare **`--output NAME`** writes a directory under the case holding one
  `elements_<step>.csv` per timestep plus `summary.csv` (the per-timestep totals),
  instead of one combined table — the per-step split that post-processing scripts
  were doing by hand, and the part of that work which is general to any structure.
  Each file is written as its step is computed, so a long run is never held in
  memory. An extension still selects a single file: `.csv`, `.vtu`/`.vtk`, `.pvd`.
- **No Cd/Cl, no sectional binning, no reference length** — those need a flow
  direction and a reference area that belong to the user, and each is a sum over
  these rows. `.vtu`/`.pvd` output carries the values as **cell data** for viewing
  the force distribution on the deflecting surface in ParaView.
- Deliberate limitation, stated in the help and the CSV header: this is the
  **pressure (form) contribution only**. Viscous skin friction needs wall-normal
  velocity gradients from the volume mesh and is not included.
- New `src/plt/surface.py` (element geometry, face→cell matching, orientation) and
  `PltFile.load_connectivity()`, which reads a zone's elements without touching
  variable data.

#### Shared-variable (surface) zones — no Tecplot needed for surface data
- The PLT reader now **follows Tecplot variable sharing**. A zone that stores no
  data of its own — every variable flagged as shared from another zone, which is
  how FlexFlow writes a cylinder-surface zone riding on the volume zone's node
  array — is read by pulling each variable from the zone that owns it. Nothing has
  to be declared: the share is recorded per variable in the file's own data-section
  header, so `PltFile.variable_owner()` / `shared_from()` just read it.
- Such a zone is **compacted to the nodes its own elements cover** and its
  connectivity renumbered, so `field extract --zone cyl` yields the surface nodes
  (6,272 for the bare-riser case) rather than the whole 1.8M-node volume. This
  works for CSV, probes, and `.vtu` (a quad surface mesh for ParaView).
  `field extract --zone cyl` previously failed outright with *"carries no own data
  (variables are shared)"*; that error is now reserved for a zone whose variables
  are genuinely passive.
- **`field info --zones`** marks a zone that stores nothing of its own and names
  the zone it borrows from, so the arrangement is discoverable.
- A CSV extraction with **many nodes per timestep and no coordinate variable** now
  warns: without X/Y/Z a row cannot be tied to a point. Coordinates are still only
  written when asked for (`--variables X,Y,Z,Pressure`), and `.pvd` remains the
  option that keeps geometry and connectivity with the values.

#### `field extract --probe` — point probes and progress feedback
- New **`--probe X,Y,Z`** on `field extract`: instead of a box, sample the
  selected variables at fixed points — the usual way to pull a time signal
  (velocity in the wake, pressure at a gauge point) out of a run. Repeat the flag
  (or separate points with `;`) for several probes; give `X,Y` only on a 2D mesh
  and Z is ignored when matching.
- Each probe is **validated before any bulk data is read**: the coordinates are
  checked against the zone's bounds taken from the PLT header (the error names
  the offending axis and prints the domain box), and the requested variables are
  checked against the zone, which now says *"not available in zone 'X'"* and
  points at the volume zone when the variable exists but carries no data there.
  **`--probe-tol TOL`** allows slack for a probe sitting exactly on a boundary.
- Values come from the **nearest mesh node** by default; the output carries that
  node's index, coordinates and its distance from the probe, so what was sampled
  is visible. A warning fires when the nearest node is much farther than the mean
  node spacing (probe in a hole of the mesh). Points are located again every
  timestep, so moving/deforming meshes are followed correctly.
- **`--interpolate`** reports the value at the point itself instead, linearly
  interpolated inside the element containing it (VTK's probe filter via pyvista —
  the same as ParaView's *Probe Location*). Only a small box of mesh around the
  probes is handed to VTK, which keeps a time series 5–9x quicker than probing the
  whole zone. Needs connectivity, so a volume zone.
- Interpolated rows carry **`source`** in place of the nearest-node columns,
  saying where each value actually came from: `cell` (inside the containing
  element), `nudged`, or `node`. A probe meant to sit on a wall lands a hair
  *outside* the faceted boundary, where VTK finds no element at all and none of
  its tolerance settings help; such a probe is now stepped a fraction of a cell
  toward the interior until it lands inside one, and the displacement is
  reported rather than silently applied. A probe in a genuine hole of the mesh
  still falls back to its nearest node, and the warning now says so plainly —
  inside the bounds but in no element means inside the structure — with the
  nearest-node distance in units of mean node spacing.
- `--interpolate` **checks itself once per run**: a linear interpolant cannot
  leave the range of its own element's nodal values, so a violation means the
  cells are not what the file claims. New **`--nen`** on `extract` (as on
  `convert`) forces nodes-per-element for a brick mesh written as tetrahedra;
  it applies to the mesh outputs too.
- Probe output is a table of point values: `--output NAME.csv`, or **no
  `--output` at all** to print it on screen (the only mode where `--output` is
  optional). The probe coordinates are not repeated on every row — the case,
  zone, variables, sampling method and probe list head the file as `#` comment
  lines (`pandas.read_csv(path, comment='#')`), and the rows carry a plain probe
  number.
- **Progress bar** across timesteps for every `field extract` mode (csv, `.pvd`
  series, probes), and a spinner for a single large step, so a long extraction
  visibly makes headway. Skipped when output is redirected, with `--no-progress`,
  and with `--verbose` (which prints per-step lines instead).

#### `case upload/download --files` — carry a case's definition, not just its data
- New **`--files [PATTERNS]`** on `case upload` **and `case download`**, for the
  loose files in a case root rather than its data directories. On its own it takes the defaults
  `simflow.config,*.def,*.geo,*.map` — what defines the run, its settings, and any
  `othd.<set>.map` written by `case write`. They are globs, so the defaults hold
  whatever a case calls its problem.
- **`--files` without `--dir` uploads only those files.** The default directories
  include `binary/`, which is the opposite of a quick definition push; give both
  flags to send data and files together.
- Only files sitting **directly in the case root** are matched — a recursive glob
  would sweep up the very data `--files` exists to avoid (`binary/nested.map`
  matches `*.map` but is correctly left alone).
- Downloading matches the patterns against the **remote** listing, and drops
  remote subdirectories so a directory named like a pattern is never fetched as a
  file. The local case directory is created for the incoming files.
- Matching nothing is reported but not treated as a failure: a case that has no
  maps yet is not an error. File patterns are carried in the resumable transfer
  state, so `--resume` does not silently drop them, and the file target is counted
  alongside the directory targets so a files-only transfer reports as complete.

#### `case download` — fetch case directories from a remote
- New **`case download [case] --from REMOTE`** that pulls case directories
  (default `othd_files,oisd_files,binary`, override with `--dir`) from a
  configured remote server down to the local case via SFTP — the mirror image of
  `case upload`. Supports wildcard mode (`case download *` over `.cases`),
  `--remote-path` to override the remote base, and `--force` to create the local
  case directory when it does not exist. Honours the `use remote:<name>` context
  (injected as `--from`).

#### `set` command — program settings
- New interactive **`set`** command for program settings (separate from the
  data/analysis commands), extensible with future subcommands.
- **`set prompt --level N`** — show only the last N path components in the
  prompt (`0` = full path); `set prompt` shows the current value.
- Persisted to `~/.flexflow/settings.json`; tab completion for `set` / `prompt` /
  `--level`.

#### Command Chaining with Semicolons
- **Semicolon separator** - Chain multiple commands on one line
  - Example: `use case:Case005; data show --pendulum; plot --data-type pendulum`
  - Supports quoted strings: `plot --title "A; B"; data show`
  - Empty commands ignored (e.g., `cmd1;; cmd2`)
- **Smart tab completion** - Tab works correctly after semicolons
- **Context persistence** - Context set by `use` applies to all chained commands
- **Error handling** - Errors in one command don't stop the chain

#### Pendulum Data Support
- **`--pendulum` flag** - Added to `data show` command to display pendulum data
- **`pendulum` data type** - Added to `plot` command's `--data-type` option
- **New components** - Pendulum: displacement, velocity, acceleration, all
- **Pendulum plotting** - Time-series and FFT plots for pendulum data
- **Full documentation** - Help messages and examples updated

## Version 2.0.0 - Interactive Shell Release (2026-02-06)

### 🎉 Major Features

#### Interactive Shell Mode
- **Always-on REPL interface** - No more startup overhead between commands
- **Instant command execution** - Commands run 20x faster after initial load
- **Persistent command history** - History saved across sessions in `~/.flexflow/history`
- **Smart tab completion** - Complete commands, subcommands, and options
- **Professional UI** - Rich terminal formatting with colors, tables, and panels

#### File System Browsing
- **`ls` command** - List files with color coding and multiple formats
  - `ls` - Simple column view
  - `ls -l` - Long format with size, date, and type
  - `ls -a` - Show hidden files
  - `ll` - Alias for `ls -l`
  - `la` - Alias for `ls -a`
- **`cd` command** - Navigate directories
  - `cd <path>` - Change to any directory
  - `cd ~` or `cd` - Go to home directory
  - `cd ..` - Go to parent directory
- **`pwd` command** - Show current directory and case context
- **`find` command** - Search for FlexFlow case directories recursively
- **`tree` command** - Display directory structure with visual guides
  - `tree` - Show tree with depth 2 (default)
  - `tree <depth>` - Show tree with custom depth

#### Smart Case Detection
- Automatically identifies FlexFlow case directories
- Color codes cases in green in listings
- Detects based on:
  - Presence of `input/`, `output/`, `binary/` directories
  - Configuration files (`simflow.config`, `case.config`)
  - Data files (`.othd`, `.oisd`, `.plt`)

#### Case Context Management
- **`use <case>` command** - Set current case context
  - Automatically resolves relative and absolute paths
  - Injects case into commands when appropriate
  - Shows case name in shell prompt
- **Smart case injection** - Commands automatically use current case when set
  - `case show` - Uses current case
  - `data show` - Uses current case
  - `plot` - Uses current case
  - `field info` - Uses current case

#### Enhanced Shell Commands
- **`help` or `?`** - Show all available commands with descriptions
- **`exit` or `quit`** - Exit FlexFlow (also Ctrl+D)
- **`clear`** - Clear the screen (also Ctrl+L)
- **`history`** - Show command history (last 20 commands)

### 🏗️ Architecture Improvements

#### Code Refactoring
- **Minimal `main.py`** - Reduced from 133 to 32 lines
- **`src/cli/app.py`** - New application class with clean separation
- **`src/cli/interactive.py`** - Complete interactive shell implementation
- **Style guide compliance** - Following PEP 8 + Google Style Guide

#### Documentation
- **`STYLE_GUIDE.md`** - Comprehensive Python coding standards (400+ lines)
- **`INTERACTIVE_MODE.md`** - Complete interactive mode guide (500+ lines)
- **`BROWSING_GUIDE.md`** - File system browsing documentation (600+ lines)
- **Updated README.md** - Reflects new interactive mode
- **Updated docs/USAGE.md** - Enhanced with interactive examples

### 📦 Dependencies
- Added `prompt_toolkit>=3.0.43` - Powers the interactive shell

### 🎨 User Experience

#### Visual Enhancements
- **Color-coded file types**:
  - Blue - Directories
  - Green - Case directories
  - Magenta - Data files (`.othd`, `.oisd`, `.plt`)
  - White - Regular files
- **Smart prompt** - Shows current directory and case
  - Abbreviated paths for long directories
  - Home directory shown as `~`
  - Current case in brackets `[CS4SG1U1]`
- **Human-readable file sizes** - KB, MB, GB formatting
- **Formatted tables** - Rich tables for listings and information

#### Keyboard Shortcuts
- `Tab` - Auto-complete commands (partial path completion planned)
- `↑/↓` - Navigate command history
- `Ctrl+R` - Reverse search history
- `Ctrl+C` - Cancel current line (doesn't exit)
- `Ctrl+D` - Exit shell
- `Ctrl+L` - Clear screen

### 🚀 Performance
- **First command**: ~2 seconds (same as before)
- **Subsequent commands**: <0.1 seconds (20x faster)
- **Memory**: ~150 MB (persistent, more efficient overall)
- **No reload overhead**: All modules stay loaded

### 📝 Workflows Enabled

#### Quick Analysis
```bash
$ ff
flexflow → cd ~/simulations
flexflow ~/simulations → find CS4
flexflow ~/simulations → use CS4SG1U1
flexflow ~/simulations [CS4SG1U1] → case show
flexflow ~/simulations [CS4SG1U1] → plot --node 10
```

#### Cross-Project Comparison
```bash
flexflow /project1 → case show CS4SG1U1
flexflow /project1 → cd /project2
flexflow /project2 → case show CS4SG2U1
```

#### Exploration
```bash
flexflow → cd /data/new_simulations
flexflow /data/new_simulations → tree 2
flexflow /data/new_simulations → find
flexflow /data/new_simulations → ls -l
```

### 🔧 Technical Details

#### File Structure
```
src/
├── cli/
│   ├── app.py              # Application class
│   ├── interactive.py      # Interactive shell (900+ lines)
│   ├── registry.py         # Command registry
│   ├── help_messages.py    # Help system
│   └── completion.py       # Shell completion
├── commands/               # Command implementations
├── core/                   # Core data structures
└── utils/                  # Utilities

docs/
├── INDEX.md               # Documentation hub
├── USAGE.md               # Usage guide
└── technical/             # Technical docs

Root:
├── main.py                # Minimal entry point
├── STYLE_GUIDE.md         # Coding standards
├── INTERACTIVE_MODE.md    # Interactive guide
├── BROWSING_GUIDE.md      # Browsing guide
└── README.md              # Project overview
```

### 🔄 Migration

#### For Users
**Old way:**
```bash
ff case show CS4SG1U1
ff data show CS4SG1U1
```

**New way:**
```bash
ff
flexflow → use CS4SG1U1
flexflow [CS4SG1U1] → case show
flexflow [CS4SG1U1] → data show
```

#### For Scripts
**Old script:**
```bash
#!/bin/bash
ff case show CS4SG1U1
ff data show CS4SG1U1
```

**New script:**
```bash
#!/bin/bash
ff << EOF
use CS4SG1U1
case show
data show
exit
EOF
```

### ⚠️ Breaking Changes
- FlexFlow now always runs in interactive mode
- Direct command execution (`ff case show CS4SG1U1`) no longer supported
  - Must use heredoc or pipe for scripting
- Command history now in `~/.flexflow/history` instead of shell history

### 🎯 Future Enhancements

#### Planned for v2.1.0
- [ ] Tab completion for file paths
- [ ] Tab completion for case names
- [ ] `cd -` to return to previous directory
- [ ] Directory bookmarks
- [ ] Command aliases (custom shortcuts)

#### Planned for v2.2.0
- [ ] Multi-line command editing
- [ ] Syntax highlighting in commands
- [ ] Plugins system
- [ ] Custom themes
- [ ] Configuration file (`~/.flexflow/config.yaml`)

#### Under Consideration
- [ ] Scripting mini-language
- [ ] Batch operations
- [ ] Remote case access
- [ ] Case templates management
- [ ] Integrated plotting preview

### 🐛 Bug Fixes
- Fixed: Parser creation logic moved out of `main.py`
- Fixed: Module-level instantiation removed (style guide compliance)
- Fixed: Case context now properly resolved to full paths
- Fixed: System exit codes properly handled in interactive mode

### 📚 Documentation

#### New Documents
- `STYLE_GUIDE.md` - Python coding standards
- `INTERACTIVE_MODE.md` - Interactive shell guide
- `BROWSING_GUIDE.md` - File browsing guide
- `CHANGELOG.md` - This file

#### Updated Documents
- `README.md` - Now reflects interactive mode
- `docs/USAGE.md` - Enhanced with interactive examples
- `docs/INDEX.md` - Updated structure

### 👥 Contributors
- Architecture design and implementation
- Interactive shell with prompt_toolkit
- File system browsing commands
- Smart case detection
- Comprehensive documentation

### 🙏 Acknowledgments
- **prompt_toolkit** - Excellent readline replacement
- **rich** - Beautiful terminal formatting
- **Python community** - For PEP 8 and style guidelines

---

## Version 1.x (Previous)

### Version 1.0.0 - Initial Release
- Basic command-line interface
- Case analysis commands
- Data inspection
- Plotting capabilities
- SLURM job submission

---

**For complete documentation, see:**
- [Interactive Mode Guide](INTERACTIVE_MODE.md)
- [Browsing Guide](BROWSING_GUIDE.md)
- [Usage Guide](docs/USAGE.md)
- [Style Guide](STYLE_GUIDE.md)
