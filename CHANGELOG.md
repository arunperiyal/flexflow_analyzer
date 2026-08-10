# FlexFlow Changelog

## Unreleased

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
- **`field iso`** *(new)* — isosurface PNGs via **pyvista** (config-driven YAML:
  background, resolution, domain crop, threshold, camera orientation, and
  reusable camera frames from ParaView `.pvsm`/`.py` Save State or a saved
  `.yml`). Auto-converts a case's PLT to a cached `.vtu`.
- **`use var:` / `use zone:` context** — set a default variable list / zone once
  and they're auto-injected into `field extract` (`--variables`, `--zone`) and
  `--zone` into `field convert`/`iso`. A **`freq`** context injects `--freq`
  into `field extract` and `run post`. Shown in `pwd`, cleared via
  `unuse var`/`zone`/`freq`/`all`, with tab completion.
- **Fixed context injection scope**: `node`/`t1`/`t2` are now injected only where
  the target actually defines those flags — `data show` (node/t1/t2),
  `data stats` (node only), `plot` (node/t1/t2). They are no longer pushed into
  `field` commands (which don't accept them), and `t1`/`t2` are no longer pushed
  into `data stats`.
- **Dependencies**: removed `pytecplot`; added `meshio`, `pyvista`.

### ✨ New Features

#### `case out` — a case's declared outputs, and maps that keep othd readable
- New **`case out`** subcommand (listed in `case --help`). **`--map`** writes
  one `othd.<set>.map` per `outputTimeHistory` block in the case's `.def` that
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
