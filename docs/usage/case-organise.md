# Case Organise Command Steps

## Overview

`case organise` manages FlexFlow case directories through four subcommands:
`history`, `out`, `rst`, `plt` and `vtu`. Running without a subcommand shows help.

```bash
case organise <subcommand> [case_directory] [options]
```

## Subcommands

### `history`

Keeps the OTHD/OISD history of the case in three stages, the same under
`othd_files/` and `oisd_files/`:

```
othd_files/archive/{problem}N.othd   as job N wrote it          (--update, mainFlex.sh)
othd_files/cleaned/{problem}N.othd   run N without the steps a   (--clean)
                                     later run redid
othd_files/{problem}.othd            cleaned/ joined: one file   (--compile)
```

N numbers the jobs in the order they ran, and one N is the same run in
`archive/`, `cleaned/` and `rcv_files/`. "The later run wins" is the later N:
the same rule the readers apply when they take several files in name order.

Pass at least one of `--update`, `--clean`, `--compile`, `--verify`,
`--prune`; they combine and always run in the order
**update → clean → compile → verify → prune**. `history` with no flag prints
a "nothing to do" message.

Parts still in the layout from before `archive/` (`othd_files/{problem}N.othd`)
are moved into `archive/` first, by every `history` call — a job script from
before keeps writing them there. A number already taken moves to the next
free one, OTHD and OISD of one run together. An old `compiled/` directory is
left alone and no longer read.

#### `history --update`

Moves `.othd`/`.oisd` from the run directory (`dir` in `simflow.config`) into
`archive/` as the next run — one past every number in `archive/`, `cleaned/`
and `rcv_files/` — and `.rcv` into `rcv_files/` under the same number
(`riser.othd` → `othd_files/archive/riser6.othd`). `mainFlex.sh` does the same
at the start of every job.

With `--t1`/`--t2`, only run-dir files whose timestep range overlaps that
window are moved (RCV files have no reader to determine their range, so they
are always moved in full). With `--dry-run`, the moves are only listed.

#### `history --clean`

Writes `cleaned/{problem}N` for every run. The runs are read in run order
(from `archive/`, or from `cleaned/` once pruned); a tsId at or below one
already taken is a restart, and everything from that tsId on is dropped in
favour of the later run. This also covers a restart appended inside one file.

- A last step cut off by a killed job is left out (and reported)
- A run with nothing left — every step redone later — has no cleaned file
- A run that starts on the step right after a later-numbered run ends, and
  is wiped by it, is warned about: the two are most likely numbered in the
  wrong order. The number still decides; swap them in `archive/` and clean
  again if the warning is right
- Runs whose headers differ (`mask`/`nOths`, `nOsfs`: different probe or
  surface sets) cannot be joined: nothing is written
- Any other problem in a file (a step with a different layout in the middle,
  non-numeric values) stops the clean: fix or remove the file first
- Records where each run took over in `.restarts` (lines only ever added, so
  the record outlives `--prune`)
- Files already holding exactly what would be written are left as they are;
  the rest are written through a temporary file
- Once `archive/` is pruned, a cleaned file is its run's only copy: cutting
  one shorter (a new run restarted inside it) asks first, unless
  `--no-confirm`

#### `history --compile`

Joins `cleaned/` in run order into `othd_files/{problem}.othd` and
`oisd_files/{problem}.oisd`. Only from a `cleaned/` that is up to date with
`archive/` (run `--clean` first, or together). A compiled file already
holding exactly that is left, with its time brought up to now.

The readers (`plot`, `case show/check/report`, the web app, …) take the
compiled file while it is newer than `archive/`, `cleaned/` and every file in
them; otherwise they read every run (`archive/`, or `cleaned/` once pruned) in
run order, after any parts still in the old flat layout.

#### `history --verify`

Reads every file to the end. Every timestep block has the same layout (the
same keyword lines with the same number of values), so it reports, per file,
a cut-off last step, steps with a different layout, non-numeric values and a
missing final newline. Also:

- `archive/`: a cut-off last step is only noted — `--clean` leaves it out
- `cleaned/`: a file must follow on from the runs before it and be what
  `--clean` would write now (else "out of date — run --clean")
- the compiled file must be `cleaned/` joined (else "run --compile")
- tsIds in no run at all — a run restarted from later than the one before
  reached — are reported as lost, but do not fail the check

Restarts inside an archived file are listed but are not a problem. If
anything else is wrong, `--prune` does not run.

#### `history --prune`

Deletes `archive/` for each type whose `cleaned/` reads through and is up to
date with it — every step that counts is then in `cleaned/`. It checks this
itself, with or without `--verify`. Lists the files and asks once, unless
`--no-confirm`; `--dry-run` only lists them. `rcv_files/` is not touched.

Later jobs add to `archive/` again; the next `--clean` folds them into
`cleaned/`, reading the pruned runs from `cleaned/` itself.

### `out`

Deletes `.out` files from the run directory, at any step, keep-freq steps
included, once the next file in the chain can stand in for them (see "The
deletion chain" below): the step's ASCII PLT, whole and written after every
`.out` part; else its binary PLT, whole and written after them; else, when
`binary/` no longer holds it, its verified copy on the remote (`--remote
NAME`). A restart reads only `.rst` (and the `.sgd` subgrid files); `.out` is
read only by the conversion that writes the `.plt`. A step with nothing to
stand in keeps its `.out` and is listed with the reason; the other steps go.
The `.rst` files are not looked at.

With `--t1`/`--t2`, only files whose timestep falls in that window are
considered; the rest are left untouched (either bound alone is a one-sided
limit).

### `rst`

Thins the `.rst` files (restart points) of the run directory: a set is
deleted if its time step is NOT divisible by `--keep-freq N`.

- Without `--keep-freq` it keeps the multiples of `freq * 10`, where freq is
  read from `simflow.config` (`outFreq` field) or auto-detected from the
  existing output files.
- Always kept, whatever `--keep-freq` says: the step of `restartTsId` in
  `simflow.config`, the newest `--keep-newest N` complete sets (default 2),
  and a newest set that is still incomplete.
- `--t1`/`--t2` limit it as for `out`.

The `.out` and PLT files are not touched by `rst`. (`case organise output`,
which did both, is gone.)

### The deletion chain

Field data of a step exists in up to four forms, each made from the one
before. A file may be deleted only when the next one stands in for it:

| File | May be deleted when |
|---|---|
| `.out` of a step | its ASCII PLT is whole and was written after every `.out` part |
| ASCII PLT (run directory) | its binary PLT is whole and was written after the ASCII PLT |
| binary PLT (`binary/`) | its copy on the remote has the same size and md5, read at that moment |

- A missing link is passed over: with no ASCII PLT the `.out` stand on the
  binary PLT, and with no binary PLT in `binary/` on its verified copy on the
  remote.
- "Written after" guards against a restart: the resumed run writes its steps
  again, and a PLT older than them was made from the earlier run's output.
- When one step of a range has nothing to stand in for it, that step is kept
  and reported; the others are deleted.
- Repair goes the other way: a broken binary PLT is made again from its
  ASCII PLT (`run post convert`), a broken ASCII PLT from the `.out` (`run
  post full`). `case check plt --verify` says which.

The natural order is therefore `case organise out`, then `plt
--delete-ascii`, then `plt --delete-binary`.

### `plt`

Pass at least one of `--delete-ascii` / `--delete-binary`; running `plt` with
neither prints a "nothing to do" message.

#### `plt --delete-ascii`

Deletes the ASCII PLT files of the run directory whose binary PLT stands in
for them:

- `binary/` holds the binary PLT whole (as long as its header says) and
  written after the ASCII file; or
- `binary/` no longer holds it, and the remote (`--remote NAME`) holds its
  verified copy, written after the ASCII file
- The others are kept and listed with the reason
- Shows a per-file table before asking confirmation

With `--t1`/`--t2`, only PLT files whose timestep falls in that window are
considered; with `--freq N`, only the steps divisible by N.

#### `plt --delete-binary`

Deletes the PLT files of `binary/` within `--t1`/`--t2` that have a copy on
the remote with the same size and md5, both read at that moment (the check
`case check plt --verify` makes):

- Needs `--remote NAME` (or `use remote:NAME`); the remote's folder comes
  from the case folder's `.cases.yml`
- A file whose copy is missing or differs, or that is cut short locally, is
  kept and listed
- When the remote cannot be asked, nothing is deleted
- It reads every file in full on both sides, so it takes time

Two plain flags narrow it (the `freq` context does not fill them):

- `--freq N`: only the steps divisible by N are candidates
- `--keep-freq N`: the steps divisible by N are kept

```
case organise plt --delete-binary --t1 4000 --t2 5000 --freq 1 --keep-freq 5
```

deletes 4001–4004, 4006–4009, … and keeps 4000, 4005, …, 5000.

`--delete-ascii` and `--delete-binary` can be combined in one `plt` call; each
runs as its own step with its own entry in the confirmation summary.

## Execution Flow

### Running `history`

0. Move parts in the old flat layout into `archive/`
1. If `--update`: resolve the run directory from `simflow.config['dir']`,
   find `.othd`, `.oisd`, `.rcv` files there, drop OTHD/OISD files outside
   `--t1`/`--t2` if given (RCV files are never filtered), and move the rest
   to the next run number
2. If `--clean`: plan every run's surviving steps (not filtered by
   `--t1`/`--t2`), record the restarts, write or remove the cleaned files
3. If `--compile`: join `cleaned/` into `{problem}.ext`
4. If `--verify`: check `archive/`, `cleaned/` and the compiled file; stop
   here if anything is wrong
5. If `--prune`: for each type whose `cleaned/` is current and reads
   through, confirm and delete `archive/`

### Running `out` and `rst`

1. Determine frequency (from config or auto-detect)
2. Keep interval = `--keep-freq`, or `freq × 10` without it
3. Find all `.out`/`.rst` files in the run directory
4. Skip files outside `--t1`/`--t2`, if given
5. Mark `.rst` files for deletion if their step is not a multiple of the keep
   interval, and `.out` files if their step has a `.plt` (in `binary/` or the
   run directory); list the steps whose `.out` stay for want of one
6. Show summary and ask for confirmation (unless `--no-confirm`)
7. Delete marked files

### Running `plt`

1. For `--delete-ascii`: find run-dir PLT files, skip those outside
   `--t1`/`--t2`/`--freq`, mark for deletion only those whose binary PLT (or
   its verified remote copy) stands in for them
2. For `--delete-binary`: find `binary/` PLT files, skip those outside
   `--t1`/`--t2`/`--freq` (or take all of them if no bound is given), compare
   each with its copy on the remote, mark for deletion only those that match
3. Show summary (both steps' file counts, if both ran) and ask for
   confirmation (unless `--no-confirm`)
4. Delete marked files

## Timestep Targeting (`--t1`/`--t2`)

```bash
--t1 STEP     # only target timesteps >= STEP
--t2 STEP     # only target timesteps <= STEP
```

Either alone is a one-sided bound; both together is an inclusive range.
Available on `history --update`, `out`, `rst`, `plt` and `vtu`. **Not** applied
to the other `history` flags, which always use the whole history: which
steps a run keeps depends on every later run, and a `t1`/`t2` context left
over from something else would silently cut the cleaned and compiled files
short.

Both flags can also come from context instead of being typed explicitly:

```bash
use t1:0 t2:1000
case organise out          # --t1/--t2 injected from context
case organise plt --delete-ascii
```

A single `use time:<N>` (or the `time` context) is injected as the one-step
window `--t1 N --t2 N`, the same way it works for `case upload/download plt`.

## Options

```bash
case organise history CS4SG1U1 --update                         # Move the run's data into archive/
case organise history CS4SG1U1 --clean                          # Each run without what later runs redid
case organise history CS4SG1U1 --clean --compile                # ... and one joined file per type
case organise history CS4SG1U1 --verify                         # Check archive/, cleaned/, compiled
case organise history CS4SG1U1 --clean --compile --verify --prune   # ... then delete archive/
case organise out CS4SG1U1                                      # Delete the .out a PLT stands in for
case organise rst CS4SG1U1                                      # Thin the .rst
case organise history CS4SG1U1 --update --t1 0 --t2 1000        # Only archive files in [0, 1000]
case organise rst CS4SG1U1 --keep-freq 5000                   # Custom retention
case organise out CS4SG1U1 --t2 5000                            # Only clean up to timestep 5000
case organise history CS4SG1U1 --prune --no-confirm             # Skip confirmation
case organise history CS4SG1U1 --prune --log                    # Log deletions to file
case organise plt CS4SG1U1 --delete-ascii                       # Delete run-dir PLT with newer binary/ copy
case organise plt CS4SG1U1 --delete-binary --t1 0 --t2 1000     # Delete binary/ PLT for a timestep range
case organise plt CS4SG1U1 --delete-ascii --delete-binary       # Both directions in one call
```

## Default Behavior

Running without a subcommand, `history` without a flag, or `plt` without
either delete flag, shows help or a "nothing to do" message:

```bash
case organise                    # → shows help
case organise history CS4SG1U1   # → "Nothing to do — pass --update, --clean, --compile, --verify and/or --prune"
case organise plt CS4SG1U1       # → "Nothing to do — pass --delete-ascii and/or --delete-binary"
```

## Safety

- `history --update`, `--clean`, `--compile` and `--verify` never delete a
  job's data (`--clean` asks before cutting a run's only copy) and honor
  `--dry-run`
- `history --prune` only deletes `archive/` when `cleaned/` holds every step
  that counts, and asks first
- `out`, `rst` and `plt` show a summary before acting and ask for confirmation —
  all unless `--no-confirm` is given
- `--delete-binary` deletes a file only when its copy on the remote has the
  same md5; with no remote to ask it deletes nothing
- A `t1`/`t2` context left over from something else never silently narrows
  `history --clean` — it always cleans the whole history
- If an OTHD/OISD file has a problem other than a cut-off last step,
  `history --clean` stops (prevents data loss)
