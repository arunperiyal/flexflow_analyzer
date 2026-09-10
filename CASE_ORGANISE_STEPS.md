# Case Organise Command Steps

## Overview

`case organise` manages FlexFlow case directories through three subcommands:
`archive`, `output` and `plt`. Running without a subcommand shows help.

```bash
case organise <subcommand> [case_directory] [options]
```

## Subcommands

### `archive`

Moves output data files from the run directory (specified in `simflow.config`
`dir` field) into dedicated archive directories:

- `.othd` files → `othd_files/`
- `.oisd` files → `oisd_files/`
- `.rcv` files → `rcv_files/` (only if present)

Files are numbered using sequential suffixes (e.g., `riser1.othd`,
`riser2.othd`) to avoid overwriting existing archived files.

With `--t1`/`--t2`, only run-dir files whose timestep range overlaps that
window are moved (RCV files have no reader to determine their range, so they
are always moved in full).

**No confirmation required** — the move step only moves files, does not delete.

#### `archive --clean`

After archiving, deduplicates and cleans redundant OTHD/OISD files in
`othd_files/` and `oisd_files/`:

1. Reads **every** `.othd` / `.oisd` file in those directories and extracts
   their time step ranges
2. Identifies redundant files:
   - **Duplicates**: Same time step range → keeps larger/newer file
   - **Subsets**: Time range fully covered by another file → marks for deletion
   - **Overlaps**: Partial overlaps → **both kept**
3. Shows summary and asks for confirmation (unless `--no-confirm`)
4. Deletes redundant files
5. Renames remaining files sequentially sorted by starting time step:
   - `{problem}1.othd`, `{problem}2.othd`, etc.

`--clean` always inspects the **complete** archived set — `--t1`/`--t2` do
**not** scope it. Excluding a file by timestep would risk hiding the very
superset file that makes another file redundant, silently leaving it
uncleaned. (This was a real bug: with a `t1`/`t2` context left over from
something unrelated, e.g. `use t1:50 t2:2800`, `archive --clean` used to skip
analyzing any file outside that window — so a subset file whose superset
happened to fall outside the window was never detected as redundant, and
nothing got deleted. Fixed by always dedup-ing the full set regardless of
`--t1`/`--t2`; only the `archive` move step respects the timestep window.)

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

1. Resolve run directory from `simflow.config['dir']`
2. Find `.othd`, `.oisd`, `.rcv` files in the run directory
3. If `--t1`/`--t2` given, drop OTHD/OISD files whose range doesn't overlap
   the window (RCV files are never filtered)
4. Create `othd_files/`, `oisd_files/`, `rcv_files/` if needed
5. Move files with numbered suffixes
6. If `--clean`: read **all** files in `othd_files/`/`oisd_files/` (not just
   the ones just archived, and not filtered by `--t1`/`--t2`), mark
   duplicates/subsets, show a summary, confirm, delete, and renumber

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
Available on the `archive` move step, `output` and `plt`. **Not** applied to
`archive --clean`, which always dedupes everything (see above).

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
case organise archive CS4SG1U1                                  # Move data files to archive dirs
case organise archive CS4SG1U1 --clean                          # Move, then deduplicate OTHD/OISD files
case organise output CS4SG1U1                                   # Clean intermediate output files
case organise archive CS4SG1U1 --t1 0 --t2 1000                 # Only archive files in [0, 1000]
case organise output CS4SG1U1 --keep-every 5                    # Custom retention
case organise output CS4SG1U1 --t2 5000                         # Only clean up to timestep 5000
case organise archive CS4SG1U1 --clean --no-confirm             # Skip confirmation
case organise archive CS4SG1U1 --clean --log                    # Log deletions to file
case organise plt CS4SG1U1 --delete-ascii                       # Delete run-dir PLT with newer binary/ copy
case organise plt CS4SG1U1 --delete-binary --t1 0 --t2 1000     # Delete binary/ PLT for a timestep range
case organise plt CS4SG1U1 --delete-ascii --delete-binary       # Both directions in one call
```

## Default Behavior

Running without a subcommand, or `plt` without either delete flag, shows help
or a "nothing to do" message:

```bash
case organise                    # → shows help
case organise archive            # → still runs (archive needs no flag)
case organise plt CS4SG1U1       # → "Nothing to do — pass --delete-ascii and/or --delete-binary"
```

## Safety

- `archive` (without `--clean`) is non-destructive (moves, does not delete)
  and does not currently honor `--dry-run`
- `archive --clean`, `output` and `plt` show a summary before acting and ask
  for confirmation unless `--no-confirm` is given
- `--delete-binary` is unconditional: it does not check the run directory
  first, and can remove the last surviving copy of a timestep's PLT data
- A `t1`/`t2` context left over from something else never silently narrows
  `archive --clean` — it always cleans the complete archived set
- If any OTHD/OISD file cannot be read, `archive --clean` aborts (prevents
  data loss)
