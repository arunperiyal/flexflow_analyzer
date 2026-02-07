# Case Organise Command Steps

## Overview

The `case organise` command cleans up FlexFlow case directories by removing redundant data files and intermediate output files.

## Execution Steps

### 1. Initialize Variables

- Determine what to clean (OTHD, OISD, output):
  - If no --clean-* flags provided: clean everything
  - Otherwise: clean only specified components
- Determine frequency:
  - Read from `simflow.config` (`outFreq` field), or
  - Auto-detect from output file time steps
- Calculate keep interval = freq × keep_every (default: freq × 10)
- Initialize statistics counters
- Create log file path if --log flag provided

### 2. Move OTHD/OISD Files from Output Directory

- Scans output directory (from simflow.config `dir` field)
- Finds all `.othd` and `.oisd` files
- Moves them to `othd_files/` and `oisd_files/` directories
- Uses numbered suffixes if files already exist (e.g., riser1.othd, riser2.othd)

### 3. Analyze OTHD Files (if enabled)

- Reads all OTHD files in `othd_files/` directory
- Extracts time step ranges from each file
- Identifies redundant files:
  - **Duplicates**: Same time step range (keeps larger/newer)
  - **Subsets**: Time range covered by another file
  - **Overlaps**: Partial overlaps are KEPT (both files retained)

### 4. Analyze OISD Files (if enabled)

- Same process as OTHD files
- Reads all OISD files in `oisd_files/` directory
- Identifies duplicates and subsets

### 5. Analyze Output Directory (if enabled)

- Finds all `.out`, `.rst`, and `.plt` files in `RUN_*` directories
- For `.out` and `.rst` files:
  - Marks files for deletion if time step is NOT a multiple of keep_interval
- For `.plt` files:
  - Checks if corresponding binary file exists in `binary/{problem}.{timestep}.plt`
  - If binary file exists, marks ASCII PLT file for deletion

### 6. Show Summary

- Displays table with:
  - Number of OTHD/OISD files to delete
  - Number of output files (.out/.rst) to delete
  - Number of PLT files to delete
  - Total space to be freed

### 7. Confirmation Prompt (unless --no-confirm)

- Asks user to confirm deletion
- Shows total file count and space to free
- User can cancel operation

### 8. Perform Deletions

- Deletes all marked redundant files
- If --log flag provided, writes deletion log to file
- Log includes file path, size, modification time, reason for deletion

### 9. Rename Files

- Renames remaining OTHD/OISD files sequentially
- Sorts by starting time step
- Format: `{problem}1.othd`, `{problem}2.othd`, etc.
- Ensures clean, sequential naming

### 10. Final Summary

- Displays completion message
- Shows final statistics

## Default Behavior

When run without flags:

```bash
case organise
```

- Cleans OTHD, OISD, and output directories
- Uses keep_every = 10 (keeps files at multiples of freq × 10)
- Requires confirmation before deleting

## Selective Cleaning

```bash
case organise --clean-othd          # Only clean OTHD files
case organise --clean-oisd          # Only clean OISD files
case organise --clean-output        # Only clean output directory
case organise --keep-every 20       # Custom retention interval
case organise --no-confirm          # Skip confirmation prompt
case organise --log                 # Create deletion log file
```
