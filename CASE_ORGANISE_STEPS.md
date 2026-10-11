# Case Organise Command Steps

## Overview

`case organise` manages FlexFlow case directories through three subcommands:
`archive`, `output` and `plt`. Running without a subcommand shows help.

```bash
case organise <subcommand> [case_directory] [options]
```

## Subcommands

### `archive`

Manages the OTHD/OISD archive (`othd_files/`, `oisd_files/`, `rcv_files/`).
Pass at least one of `--update`, `--clean`, `--compile`; they combine and
always run in the order **update → clean → compile**. `archive` with no flag
prints a "nothing to do" message.

#### `archive --update`

Moves output data files from the run directory (specified in `simflow.config`
`dir` field) into the archive directories under the next free number:

- `.othd` files → `othd_files/` (e.g. `riser.othd` → `riser6.othd`)
- `.oisd` files → `oisd_files/`
- `.rcv` files → `rcv_files/` (only if present)

With `--t1`/`--t2`, only run-dir files whose timestep range overlaps that
window are moved (RCV files have no reader to determine their range, so they
are always moved in full). With `--dry-run`, the moves are only listed.

**No confirmation required** — it only moves files, never deletes.

#### `archive --clean`

Deduplicates `othd_files/` and `oisd_files/` under manual supervision. It
works on the archive only; it never touches the run directory.

1. Reads **every** `.othd` / `.oisd` file in those directories and extracts
   their time step ranges
2. Proposes redundant files:
   - **Duplicates**: Same time step range → keeps larger/newer file
   - **Subsets**: Time range fully covered by another file
   - **Overlaps**: Partial overlaps → **both kept**
3. Shows a table per type: every file, its tsId range, size and proposed
   action with the reason
4. Asks about each proposed deletion in turn:
   `y` delete, `n` keep, `a` delete this and all remaining, `q` abort the
   whole clean (nothing deleted or renamed)
5. Shows the renumbering of the surviving files (including any the user
   kept), sorted by starting time step — `{problem}1.othd`,
   `{problem}2.othd`, … — and asks once before renaming
6. Deletes the confirmed files and applies the renames

`--no-confirm` accepts the whole plan without asking; `--dry-run` shows the
tables and stops.

`--clean` always inspects the **complete** archived set — `--t1`/`--t2` do
**not** scope it. Excluding a file by timestep would risk hiding the very
superset file that makes another file redundant, silently leaving it
uncleaned. (This was a real bug: with a `t1`/`t2` context left over from
something unrelated, e.g. `use t1:50 t2:2800`, `archive --clean` used to skip
analyzing any file outside that window — so a subset file whose superset
happened to fall outside the window was never detected as redundant, and
nothing got deleted. Fixed by always dedup-ing the full set regardless of
`--t1`/`--t2`; only the `--update` move step respects the timestep window.)

#### `archive --compile`

Combines the archived parts into one file per type:

- `othd_files/*.othd` → `othd_files/compiled/{problem}.othd`
- `oisd_files/*.oisd` → `oisd_files/compiled/{problem}.oisd`

The parts are kept. Parts are taken in order of their first tsId; a tsId at
or below one already taken is a restart, and everything from that tsId on is
replaced by the restarted run's data (the same "later run wins" rule the
readers use when given several files). This also covers a restart appended
inside a single file. Gaps in the combined tsIds are reported. Parts whose
headers differ (`mask`/`nOths`, `nOsfs` — different probe or surface sets)
are not combined. The compiled file is rewritten on every run, through a
temporary file, so an interrupted run never leaves a half-written result.
`--t1`/`--t2` are ignored, for the same reason as `--clean`; `--dry-run`
reports what would be written.

### `output`

Removes intermediate output files from the run directory:

- **`.out` and `.rst` files**: deleted if their time step is NOT a multiple of
  `freq * keep_every`
  - Default `keep_every = 10`, so keeps steps at multiples of `freq * 10`

Frequency is read from `simflow.config` (`outFreq` field) or auto-detected
from existing output files.

With `--t1`/`--t2`, only files whose timestep falls in that window are
considered; the rest are left untouched (either bound alone is a one-sided
limit — `--t2` alone behaves like the old `--upto`).

PLT files are not touched by `output` — see `plt` below.

### `plt`

Pass at least one of `--delete-ascii` / `--delete-binary`; running `plt` with
neither prints a "nothing to do" message.

#### `plt --delete-ascii`

Deletes PLT files from the run directory where `binary/` has a corresponding
file (exact filename match) with a newer mtime:

- Safe: only deletes if the binary copy is confirmed newer
- Skips files with no binary copy
- Skips files where the binary copy is the same age or older
- Shows a per-file table before asking confirmation

With `--t1`/`--t2`, only PLT files whose timestep falls in that window are
considered.

#### `plt --delete-binary`

Deletes PLT files from `binary/` within `--t1`/`--t2`:

- **Unconditional** — no check against the run directory
- Omitting both `--t1` and `--t2` deletes every PLT file in `binary/`
- Can leave no surviving copy of that timestep's PLT data — this is the most
  destructive of the three subcommands

`--delete-ascii` and `--delete-binary` can be combined in one `plt` call; each
runs as its own step with its own entry in the confirmation summary.

## Execution Flow

### Running `archive`

1. If `--update`: resolve the run directory from `simflow.config['dir']`,
   find `.othd`, `.oisd`, `.rcv` files there, drop OTHD/OISD files outside
   `--t1`/`--t2` if given (RCV files are never filtered), and move the rest
   into the archive directories under the next free number
2. If `--clean`: read **all** files in `othd_files/`/`oisd_files/` (not
   filtered by `--t1`/`--t2`), propose duplicates/subsets, show the plan,
   confirm each deletion, confirm the renumbering, then delete and rename
3. If `--compile`: combine each type's parts into `compiled/{problem}.ext`,
   resolving restarts in favour of the later run

### Running `output`

1. Determine frequency (from config or auto-detect)
2. Calculate keep interval = `freq × keep_every`
3. Find all `.out`/`.rst` files in the run directory
4. Skip files outside `--t1`/`--t2`, if given
5. Mark remaining files for deletion if their step is not a multiple of the
   keep interval
6. Show summary and ask for confirmation (unless `--no-confirm`)
7. Delete marked files

### Running `plt`

1. For `--delete-ascii`: find run-dir PLT files, skip those outside
   `--t1`/`--t2`, mark for deletion only if `binary/` has a newer copy
2. For `--delete-binary`: find `binary/` PLT files, skip those outside
   `--t1`/`--t2` (or take all of them if neither bound is given), mark all of
   them for deletion unconditionally
3. Show summary (both steps' file counts, if both ran) and ask for
   confirmation (unless `--no-confirm`)
4. Delete marked files

## Timestep Targeting (`--t1`/`--t2`)

```bash
--t1 STEP     # only target timesteps >= STEP
--t2 STEP     # only target timesteps <= STEP
```

Either alone is a one-sided bound; both together is an inclusive range.
Available on `archive --update`, `output` and `plt`. **Not** applied to
`archive --clean` or `archive --compile`, which always use the complete
archive (see above).

Both flags can also come from context instead of being typed explicitly:

```bash
use t1:0 t2:1000
case organise output          # --t1/--t2 injected from context
case organise plt --delete-ascii
```

A single `use time:<N>` (or the `time` context) is injected as the one-step
window `--t1 N --t2 N`, the same way it works for `case upload/download --binary`.

## Options

```bash
case organise archive CS4SG1U1 --update                         # Move data files to archive dirs
case organise archive CS4SG1U1 --clean                          # Deduplicate, asking per file
case organise archive CS4SG1U1 --compile                        # One combined file per type
case organise archive CS4SG1U1 --update --clean --compile       # All three, in that order
case organise output CS4SG1U1                                   # Clean intermediate output files
case organise archive CS4SG1U1 --update --t1 0 --t2 1000        # Only archive files in [0, 1000]
case organise output CS4SG1U1 --keep-every 5                    # Custom retention
case organise output CS4SG1U1 --t2 5000                         # Only clean up to timestep 5000
case organise archive CS4SG1U1 --clean --no-confirm             # Skip confirmation
case organise archive CS4SG1U1 --clean --log                    # Log deletions to file
case organise plt CS4SG1U1 --delete-ascii                       # Delete run-dir PLT with newer binary/ copy
case organise plt CS4SG1U1 --delete-binary --t1 0 --t2 1000     # Delete binary/ PLT for a timestep range
case organise plt CS4SG1U1 --delete-ascii --delete-binary       # Both directions in one call
```

## Default Behavior

Running without a subcommand, `archive` without a flag, or `plt` without
either delete flag, shows help or a "nothing to do" message:

```bash
case organise                    # → shows help
case organise archive CS4SG1U1   # → "Nothing to do — pass --update, --clean and/or --compile"
case organise plt CS4SG1U1       # → "Nothing to do — pass --delete-ascii and/or --delete-binary"
```

## Safety

- `archive --update` and `archive --compile` are non-destructive (they move
  or write, never delete) and honor `--dry-run`
- `archive --clean` asks about each deletion and about the renumbering;
  `output` and `plt` show a summary before acting and ask for confirmation —
  all unless `--no-confirm` is given
- `--delete-binary` is unconditional: it does not check the run directory
  first, and can remove the last surviving copy of a timestep's PLT data
- A `t1`/`t2` context left over from something else never silently narrows
  `archive --clean` — it always cleans the complete archived set
- If any OTHD/OISD file cannot be read, `archive --clean` aborts (prevents
  data loss)
