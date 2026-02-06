# Case Organise Command - Clarification Questions

## Overview

Implementing `ff case organise` command to clean up redundant files in case directories.

## Questions for Clarification

### 1. OTHD/OISD File Organization

Looking at your example:

```
othd_files/
├── riser1.othd   26.9MB   2025-01-29
├── riser2.othd   26.9MB   2025-01-27
├── riser3.othd   12.5MB   2025-02-03
├── riser4.othd    94.6KB  2025-02-05
├── riser5.othd    2.1MB   2025-02-07
├── riser6.othd   12.5MB   2025-02-16
├── riser7.othd    8.3MB   2025-02-26
├── riser8.othd    8.3MB   2025-02-21
└── riser9.othd   14.2MB   2026-01-29
```

**Questions:**

- **Q1.1**: How do I determine the time step range for each file?
  
  - Parse the binary file header?
  - Use the `check` command internally?
  - Other method?
  
  **Ans:** I think we can use check command internally. Suggest if there is a better alternative

- **Q1.2**: What's the naming convention?
  
  - Are these sequential writes (riser1, riser2, ...) or arbitrary names?
  - Does the number suffix indicate anything about time ranges?
  
  **Ans:** These are sequential write. The number suffix does not indicate anything about time range.

- **Q1.3**: When identifying redundant files, which file should I keep?
  
  - Keep the **largest** file (assuming it has more data)?
  - Keep the **most recent** file (by modification time)?
  - Keep **lowest numbered** file (riser1 over riser2)?
  
  **Ans:** We should consider keeping the recent file. But main thing is we don't lose information.

- **Q1.4**: What defines "redundant"?
  
  - Exact same time step range → delete duplicate
  - Subset time range → delete subset file
  - Overlapping ranges → keep both or merge logic?
  
  **Ans:**  Delete duplicates. Delete subset files. Keep files with overlapping ranges. Ask questions if you have doubt.

**Example scenario:**

```
riser1.othd covers steps 0-1000
riser2.othd covers steps 0-1000    ← Duplicate: delete?
riser3.othd covers steps 0-500     ← Subset: delete?
riser4.othd covers steps 500-1500  ← Overlap: keep both?
```

### 2. Output Directory Organization

**Q2.1**: What's the directory structure?

```
Option A:
CS4SG1U1P0/
├── RUN_1/
│   ├── binary/
│   │   └── riser.1000.plt
│   ├── riser.1000.out
│   └── riser.1000.rst

Option B:
CS4SG1U1P0/
├── RUN_1/
│   ├── riser.1000.out
│   └── riser.1000.rst
├── binary/
│   └── riser.1000.plt

Option C:
Other structure?
```

**Ans:** Option B.

**Q2.2**: File naming patterns:

- Are PLT files always: `{prefix}.{step}.plt`?
- Are OUT files always: `{prefix}.{step}.out`?
  - `{prefix}.{step}_*.out`
- Are RST files always: `{prefix}.{step}.rst`?
  - Same as out file
- What is `{prefix}`? (e.g., "riser", problem name, other?)
  - prefix is problem name.

**Q2.3**: Retention logic when freq=50:

- Keep files at steps: 0, 500, 1000, 1500, 2000, ... (multiples of 500)?
  - We can work with freq * 10, where freq is the value provided in simflow.config
- Delete files at steps: 50, 100, 150, 200, ... (non-multiples)?
  - Delete files at steps of multiples of freq mentioned in simflow.config
- **Why 500?** Is this formula: `keep_interval = freq * 10` or configurable?

**Q2.4**: Which files to clean?

- `.out` files ✓
- `.rst` files ✓
- `.plt` files? (Or only out/rst?)
- Other extensions? (`.log`, `.dat`, `.csv`, etc.)

### 3. Configuration & Frequency

**Q3.1**: Where to read `freq` value?

- From `simflow.config` file?
- Command line argument `--freq 50`?
- Both (command line overrides config)?

**Q3.2**: Default behavior if freq not found?

- Use default value (e.g., 50)?
- Skip output directory cleaning?
- Ask user?

**Q3.3**: Keep interval calculation:

```bash
# If freq = 50, keep files at which intervals?
Option A: keep_interval = freq * 10 = 500
Option B: keep_interval = freq * 5 = 250
Option C: User specifies: --keep-every 10 (meaning every 10th output)
Option D: User specifies: --keep-interval 500 (explicit interval)
```

### 4. Safety & User Interaction

**Q4.1**: Dry run behavior:

```bash
ff case organise CS4SG1U1 --dry-run
# Should show:
# - Files to be deleted
# - Space to be freed
# - No actual deletion
```

Is this correct? 

**Ans:** Yes

**Q4.2**: Confirmation prompt:

```bash
ff case organise CS4SG1U1
# Should it:
Option A: Show summary and ask "Delete 150 files (2.3GB)? [y/N]"
Option B: Always delete without asking (use --dry-run first)
Option C: Show each file and ask individually
```

**Ans:** Option A.

**Q4.3**: Backup option:

```bash
ff case organise CS4SG1U1 --backup
# Should it:
Option A: Move to CS4SG1U1/backup_20260207/
Option B: Move to CS4SG1U1/.backup/
Option C: Move to user-specified directory: --backup-dir /path/to/backup
Option D: No backup feature (user should backup manually)
```

**Ans:** Option D

**Q4.4**: Logging:

- Should deleted files be logged to a file (e.g., `organise_log_20260207.txt`)?
- Include file sizes, paths, reasons for deletion?

### 5. Command Interface

**Proposed syntax:**

```bash
ff case organise <case> [options]
ff case organise CS4SG1U1P0 [options]

# When case context is set:
use case CS4SG1U1P0
case organise [options]
```

**Proposed options:**

```bash
Options:
  --dry-run              Preview changes without deleting
  --keep-every N         Keep every Nth output (default: 10)
  --keep-interval STEPS  Keep files at step intervals (e.g., 500)
  --freq N               Override frequency from simflow.config
  --no-confirm           Skip confirmation prompts
  --backup [DIR]         Move files to backup directory
  --clean-othd           Clean OTHD files only
  --clean-oisd           Clean OISD files only
  --clean-output         Clean output directory only
  -v, --verbose          Show detailed information
  -h, --help             Show help message
  --examples             Show usage examples
```

**Is this interface acceptable?**

Yes.

### 6. Error Handling

**Q6.1**: What if files are being written by a running simulation?

- Check for lock files?
- Check modification time (skip if modified in last X minutes)?
- Let user handle (show warning)?

**Ans:** Let the user handle this. 

**Q6.2**: What if time step range cannot be determined?

- Skip the file with warning?
- Fail the entire operation?
- Treat as "unknown" and list separately?

**Ans:** Fail the entire operation.

### 7. Examples to Confirm Understanding

**Example 1: OTHD Cleanup**

```
Before:
  riser1.othd [steps: 0-1000, size: 26.9MB]
  riser2.othd [steps: 0-1000, size: 26.9MB]  ← Duplicate
  riser3.othd [steps: 0-500, size: 12.5MB]   ← Subset
  riser4.othd [steps: 1000-2000, size: 12.5MB]

After (keep):
  riser1.othd [steps: 0-1000, size: 26.9MB]    ← Kept (first of duplicates)
  riser4.othd [steps: 1000-2000, size: 12.5MB] ← Kept (unique range)

Deleted:
  riser2.othd [duplicate of riser1]
  riser3.othd [subset of riser1]
```

**Example 2: Output Directory Cleanup (freq=50)**

```
binary/
  riser.50.plt
  riser.100.plt
  riser.150.plt
  riser.200.plt

output/
  riser.50.out   ← Delete (PLT exists at 500, not multiple of 500)
  riser.100.out  ← Delete
  riser.150.out  ← Delete
  riser.500.out  ← Keep (500 % 500 == 0)
  riser.550.out  ← Delete
  riser.1000.out ← Keep (1000 % 500 == 0)
  riser.1000.rst ← Keep (1000 % 500 == 0)
  riser.1050.rst ← Delete
```

**Is this correct?**

**Ans:** Yes. But we can also rename the othd files finally to in the proper order.

### 8. Additional Features

**Q8.1**: Should there be a report/summary?

```
Organise Summary:
================
OTHD Files:
  - Total files: 9
  - Redundant files: 3
  - Space freed: 51.3MB

OISD Files:
  - Total files: 5
  - Redundant files: 1
  - Space freed: 10.2MB

Output Directory:
  - OUT files deleted: 45
  - RST files deleted: 38
  - Space freed: 2.3GB

Total space freed: 2.36GB
```

**Ans:** Yes.

**Q8.2**: Should statistics be shown before confirmation?

**Ans:** No

**Q8.3**: Should there be a `--force` flag to bypass all confirmations?

**Ans:** No

## Next Steps

Please answer these questions by editing this file or creating a new response. Once I have clarity, I'll implement the `case organise` command with proper error handling and safety checks.

## Notes Section (for your answers)

### Answers:

```
[Add your answers here]
```
