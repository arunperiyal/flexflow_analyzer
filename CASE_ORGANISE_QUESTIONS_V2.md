# Case Organise Command - Additional Clarification Questions (V2)

## Overview

Based on your previous answers, I need clarification on a few more details before implementing the `case organise` command.

---

## Additional Questions

### 1. File Naming Patterns - OUT/RST Files

You mentioned:

- OUT files: `{prefix}.{step}_*.out`
- RST files: Same as out file

**Question 1.1:** What does the `_*` part represent?

Examples:

- `riser.1000.out` (simple format)
- `riser.1000_001.out` (with suffix)
- `riser.1000_rank0.out` (with rank identifier)
- Other format?

**Question 1.2:** How should I match these files?

Options:

- **Option A**: Match pattern `{problem}.{step}.out` (exact match)
- **Option B**: Match pattern `{problem}.{step}*.out` (with glob, catches suffixes)
- **Option C**: Match pattern `{problem}.{step}_*.out` (requires underscore)

**Your Answer:**

```
riser.1000_0.out
Option C
```

---

### 2. Frequency Configuration

**Question 2.1:** Where to read `freq` from simflow.config?

What is the exact key name in simflow.config?

- `freq`
- `frequency`
- `output_freq`
- `writeInterval`
- Other?

**Example from simflow.config:**

```
>> cat simflow.config
problem = riser
np      = 120
nsg     = 120
fmt     = ascii
pDir    = .
dir     = ./RUN_1
#=========================================================================
# CNN AND CRD FILES USED FOR PLOTTING
#=========================================================================
#vols   = riser.vols
srfs    = riser.srfs
cnn     = riser.fluid.cnn
nen     = 8
outFreq = 50
verbose = 1

aleLinearElastic = 1
aleUpdLagrangian = 0

restartTsId = 1000
restartFlag = 1
```

**Question 2.2:** Default behavior if freq not found

If `freq` is not in simflow.config:

- **Option A**: Fail the operation with error message
- **Option B**: Skip output directory cleaning (only clean OTHD/OISD)
- **Option C**: Use default value (e.g., 50)
- **Option D**: Ask user for freq value interactively

**Your Answer:**

```
We can identify this from the output directory itself if there is no simflow.config file.
```

**Question 2.3:** Command line override

Should users be able to override freq?

- `--freq 50` (override freq value)
- `--keep-every 10` (keep every 10th output)
- Both options?
- Neither (always use simflow.config)?

**Your Answer:**

```
Both options
```

---

### 3. Logging

**Question 3.1:** Should deleted files be logged to a file?

- **Option A**: Create log file `organise_log_20260207_153045.txt` in case directory
  - Contents: file paths, sizes, reasons for deletion, timestamp
- **Option B**: No log file, only console output
- **Option C**: Log file only with `--log` flag

**Your Answer:**

```
Option C
```

**Question 3.2:** If logging is enabled, what should be included?

Check all that apply:

- [x] File path
- [x] File size
- [x] Deletion reason (duplicate/subset/retention policy)
- [x] Time step range
- [x] Timestamp of deletion
- [x] Modification time of file

---

### 4. Renaming OTHD/OISD Files After Cleanup

You mentioned: "But we can also rename the othd files finally to in the proper order."

**Question 4.1:** Should renaming happen automatically?

**Scenario:**

```
Before cleanup:
  riser1.othd [steps: 0-1000]
  riser2.othd [steps: 0-1000]     ← Delete (duplicate)
  riser4.othd [steps: 1000-2000]
  riser7.othd [steps: 2000-3000]
  riser9.othd [steps: 3000-4000]

After cleanup (no rename):
  riser1.othd [steps: 0-1000]
  riser4.othd [steps: 1000-2000]
  riser7.othd [steps: 2000-3000]
  riser9.othd [steps: 3000-4000]

After cleanup + rename:
  riser1.othd [steps: 0-1000]
  riser2.othd [steps: 1000-2000]  ← was riser4
  riser3.othd [steps: 2000-3000]  ← was riser7
  riser4.othd [steps: 3000-4000]  ← was riser9
```

Options:

- **Option A**: Always rename automatically after cleanup
- **Option B**: Only rename with `--rename` flag
- **Option C**: Ask user after showing cleanup summary: "Rename files? [y/N]"
- **Option D**: Never rename (user does it manually if needed)

**Your Answer:**

```
Option A
```

**Question 4.2:** Should OISD files also be renamed?

- Yes, same logic as OTHD files
- No, only OTHD files
- Make it configurable

**Your Answer:**

```
Yes
```

**Question 4.3:** Renaming order

Should files be renamed based on:

- **Option A**: Time step order (file with earliest steps becomes riser1)
- **Option B**: Alphabetical order of original filenames
- **Option C**: Modification time (oldest file becomes riser1)

**Your Answer:**

```
Option A
```

---

### 5. Reading Time Step Ranges

**Question 5.1:** Better alternative to `check` command

You asked: "Suggest if there is a better alternative"

Instead of calling `check` command as subprocess, I can use the reader classes directly:

```python
from src.readers.othd_reader import OTHDReader

reader = OTHDReader(othd_file)
time_steps = reader.times  # Get time step array
start_step = time_steps[0]
end_step = time_steps[-1]
```

**Benefits:**

- Faster (no subprocess overhead)
- More reliable (direct API)
- Better error handling
- Can reuse existing code

**Should I:**

- **Option A**: Use reader classes directly (recommended)
- **Option B**: Use `check` command as subprocess
- **Option C**: Implement new parser specifically for this

**Your Answer:**

```
Option A
```

**Question 5.2:** If using reader classes, which method to use?

Looking at the existing code, which approach:

- `reader.times` - array of all time steps
- `reader.get_time_range()` - if such method exists
- Parse header directly
- Other method?

**Your Answer:**

```
[Specify the method or I'll check the code]
```

---

### 6. Duplicate Detection - Which File to Keep

For files with **exact same time step range** (duplicates):

You said: "We should consider keeping the recent file. But main thing is we don't lose information."

**Question 6.1:** How to determine which file to keep?

**Scenario:**

```
riser1.othd [steps: 0-1000, size: 26.9MB, modified: 2025-01-29]
riser2.othd [steps: 0-1000, size: 26.9MB, modified: 2025-01-27]
```

Options:

- **Option A**: Keep most recent by modification time → Keep riser1
- **Option B**: Keep largest file size → Keep either (same size)
- **Option C**: Keep lowest numbered file → Keep riser1
- **Option D**: Keep highest numbered file → Keep riser2

**Your Answer:**

```
Option A
```

**Question 6.2:** What if files have same range but different sizes?

```
riser1.othd [steps: 0-1000, size: 26.9MB, modified: 2025-01-29]
riser2.othd [steps: 0-1000, size: 25.1MB, modified: 2025-01-30]
```

Should I:

- Keep larger file (more data)
- Keep more recent file
- Keep both and warn user
- Use priority rule (e.g., "size > recent > number")

**Your Answer:**

```
Keep larger file
```

---

### 7. Output Directory Structure

**Question 7.1:** Confirm binary directory location

You said structure is Option B:

```
CS4SG1U1P0/
├── RUN_1/
│   ├── riser.1000.out
│   └── riser.1000.rst
├── binary/
│   └── riser.1000.plt
```

Is `binary/` at the **same level** as `RUN_1/`? Or is it:

```
CS4SG1U1P0/
├── binary/
│   └── riser.1000.plt
└── RUN_1/
    ├── riser.1000.out
    └── riser.1000.rst
```

**Your Answer:**

```
╭─ /scratch/ritwikna/short_flex/CS4SG1U1P0 [c:CS4SG1U1P0 | p:riser | d:RUN_1]
╰─❯ ll
                                                                      
   Type           Size     Modified             Name                  
 ──────────────────────────────────────────────────────────────────── 
   DIR               -     2025-02-21 19:13     binary/               
   DIR               -     2026-02-02 06:12     oisd_files/           
   DIR               -     2026-02-02 06:12     othd_files/           
   DIR               -     2026-02-05 02:28     RUN_1/   
```

**Question 7.2:** Multiple output directories

If there are multiple output directories:

```
CS4SG1U1P0/
├── binary/
├── RUN_1/
│   ├── riser.1000.out
│   └── riser.1000.rst
├── RUN_2/
│   ├── riser.1000.out
│   └── riser.1000.rst
└── RUN_3/
    ├── riser.1000.out
    └── riser.1000.rst
```

Should the organise command:

- Clean all RUN_* directories
- Only clean the directory specified with `use dir RUN_1`
- Ask user which directories to clean

**Your Answer:**

```
Ask the user.
```

---

### 8. Edge Cases

**Question 8.1:** Empty or incomplete files

What if an OTHD file exists but is corrupted or incomplete (cannot read time steps)?

- Skip the file with warning
- Fail entire operation (you said this earlier)
- Ask user what to do
- List it separately as "cannot process"

**Your Answer:**

```
Fail entire operation
```

**Question 8.2:** Files with no overlaps

If all files have unique time ranges (no duplicates, no subsets):

```
riser1.othd [0-1000]
riser2.othd [1000-2000]
riser3.othd [2000-3000]
```

Should the command:

- Report "No redundant files found" and exit
- Still offer to rename files if they're not sequential
- Do nothing

**Your Answer:**

```
Still have to rename if not in order.
```

---

### 9. Command Interface Final Confirmation

**Proposed command structure:**

```bash
# Basic usage
ff case organise <case>
ff case organise CS4SG1U1P0

# With context
use case CS4SG1U1P0
case organise

# Options
ff case organise CS4SG1U1P0 --dry-run
ff case organise CS4SG1U1P0 --freq 50
ff case organise CS4SG1U1P0 --keep-every 10
ff case organise CS4SG1U1P0 --clean-othd
ff case organise CS4SG1U1P0 --clean-output
ff case organise CS4SG1U1P0 --rename
ff case organise CS4SG1U1P0 --no-confirm
ff case organise CS4SG1U1P0 --verbose
```

**Flags to implement:**

```
--dry-run              Preview changes without deleting
--freq N               Override frequency from simflow.config
--keep-every N         Keep every Nth output (alternative to freq*10)
--clean-othd           Clean OTHD files only
--clean-oisd           Clean OISD files only
--clean-output         Clean output directory only
--rename               Rename files after cleanup
--no-confirm           Skip confirmation prompt
-v, --verbose          Show detailed information
-h, --help             Show help message
--examples             Show usage examples
```

**Is this acceptable?**

**Your Answer:**

```
Yes
```

---

## Summary of Confirmed Decisions

Based on previous answers:

✅ **OTHD/OISD Cleanup:**

- Delete exact duplicates (same time range)
- Delete subset files (smaller range covered by larger file)
- Keep files with overlapping ranges
- Use check command internally (or reader classes)
- Keep most recent file when multiple files have same range

✅ **Output Directory Cleanup:**

- Structure: Binary at case level, output dirs (RUN_1, etc.) at case level
- Delete .out and .rst files at steps that are multiples of freq
- Keep files at steps that are multiples of freq*10 (e.g., 500, 1000, 1500...)
- Prefix is problem name

✅ **Safety:**

- Show summary with file count and space to be freed
- Ask for confirmation: "Delete 150 files (2.3GB)? [y/N]"
- --dry-run shows what would be deleted
- No backup feature (user handles manually)
- Let user handle running simulations (no automatic checks)
- Fail if time step range cannot be determined

✅ **Reporting:**

- Show summary after cleanup with statistics
- Don't show statistics before confirmation

---

## Please Answer

Fill in your answers in the sections marked "Your Answer" above, or provide answers here:

```
[Your consolidated answers here]
```
