# Case Organise Command Steps

## Overview

The `case organise` command manages FlexFlow case directories through three independent action flags. Running without a flag shows help.

## Action Flags

### `--archive`

Moves output data files from the run directory (specified in `simflow.config` `dir` field) into dedicated archive directories:

- `.othd` files → `othd_files/`
- `.oisd` files → `oisd_files/`
- `.rcv` files → `rcv_files/` (only if present)

Files are numbered using sequential suffixes (e.g., `riser1.othd`, `riser2.othd`) to avoid overwriting existing archived files.

**No confirmation required** — archive only moves files, does not delete.

### `--organise`

Deduplicates and cleans redundant OTHD/OISD files in `othd_files/` and `oisd_files/`:

1. Reads all `.othd` / `.oisd` files and extracts their time step ranges
2. Identifies redundant files:
   - **Duplicates**: Same time step range → keeps larger/newer file
   - **Subsets**: Time range fully covered by another file → marks for deletion
   - **Overlaps**: Partial overlaps → **both kept**
3. Shows summary and asks for confirmation
4. Deletes redundant files
5. Renames remaining files sequentially sorted by starting time step:
   - `{problem}1.othd`, `{problem}2.othd`, etc.

### `--clean-output`

Removes intermediate output files from the run directory:

- **`.out` and `.rst` files**: deleted if their time step is NOT a multiple of `freq * keep_every`
  - Default `keep_every = 10`, so keeps steps at multiples of `freq * 10`
- **`.plt` files**: deleted if a corresponding binary file exists in `binary/{problem}.{step}.plt`

Frequency is read from `simflow.config` (`outFreq` field) or auto-detected from existing output files.

## Execution Flow

### Running with `--archive`

1. Resolve run directory from `simflow.config['dir']`
2. Find `.othd`, `.oisd`, `.rcv` files in run directory
3. Create `othd_files/`, `oisd_files/`, `rcv_files/` if needed
4. Move files with numbered suffixes
5. Print summary of moved files

### Running with `--organise`

1. Read all files in `othd_files/` and `oisd_files/`
2. Parse time step ranges from each file
3. Mark duplicates and subsets as redundant
4. Show cleanup summary table
5. Ask for confirmation (unless `--no-confirm`)
6. Delete redundant files
7. Rename remaining files sequentially

### Running with `--clean-output`

1. Determine frequency (from config or auto-detect)
2. Calculate keep interval = `freq × keep_every`
3. Find all `.out`, `.rst`, `.plt` files in run directory
4. Mark for deletion:
   - `.out`/`.rst`: if step not a multiple of keep interval
   - `.plt`: if binary version exists in `binary/`
5. Show summary and ask for confirmation
6. Delete marked files

## Combined Usage

All three flags can be combined in one command:

```bash
case organise CS4SG1U1 --archive --organise --clean-output
```

Order of execution: archive → organise → clean-output

## Options

```bash
case organise --archive                    # Move data files to archive dirs
case organise --organise                   # Deduplicate OTHD/OISD files
case organise --clean-output               # Clean intermediate output files
case organise --archive --organise         # Archive then deduplicate
case organise --archive --organise --clean-output  # Full cleanup
case organise --clean-output --keep-every 5        # Custom retention
case organise --organise --no-confirm              # Skip confirmation
case organise --organise --log                     # Log deletions to file
```

## Default Behavior

Running without any action flag shows help:

```bash
case organise          # → shows help
case organise CS4SG1U1 # → shows help (no action flag given)
```

## Safety

- `--archive` is non-destructive (moves, does not delete)
- `--organise` and `--clean-output` show a summary before acting
- Confirmation prompt can be skipped with `--no-confirm`
- If any OTHD/OISD file cannot be read, `--organise` aborts (prevents data loss)
