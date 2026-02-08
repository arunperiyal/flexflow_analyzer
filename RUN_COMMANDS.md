# FlexFlow Run Commands

## Overview

The `run` command provides a streamlined interface to submit and manage FlexFlow simulation jobs on HPC clusters. It wraps the SLURM job submission scripts and automates common tasks like file archiving and validation.

## Command Structure

```bash
run <subcommand> [case_directory] [options]
```

### Subcommands

- `check` - Validate case directory structure before running jobs
- `pre` - Submit preprocessing job (mesh generation, conversion)
- `main` - Submit main simulation job (with automatic archiving)
- `post` - Submit postprocessing job (PLT file generation)

---

## Subcommand Details

### `run check` - Validate Case Directory

**Purpose:** Verify that the case directory has all required files, directories, and executables before submitting jobs.

**What it checks:**

1. **Required Files:**
   
   - `simflow.config` - Simulation configuration
   - `<problem>.geo` - Geometry file for mesh generation
   - `<problem>.def` - Problem definition file
   - `<problem>.srfs` - Surface definitions
   - `<problem>.vols` - Volume definitions

2. **Required Directories:**
   
   - `othd_files/` - Storage for OTHD output files
   - `oisd_files/` - Storage for OISD output files
   - `binary/` - Binary data files
   - `rundir/` - Run directory (if specified in config)

3. **Job Scripts:**
   
   - `preFlex.sh` - Preprocessing script
   - `mainFlex.sh` (or `submit.sh`) - Main simulation script
   - `postFlex.sh` (or `PostSubmit.sh`) - Postprocessing script

4. **Executable Paths in Scripts:**
   
   - `gmsh` (or `gmsh*`) - Mesh generator
   - `simGmshCnvt` - Mesh converter
   - `mpiSimflow` - Main simulation executable
   - `simPlt` - PLT file generator
   - `simPlt2Bin` - Binary PLT converter

**Usage:**

```bash
# Check current case
run check

# Check specific case
run check Case001

# With context
use case:Case001
run check
```

**Example Output:**

```
✓ simflow.config found
✓ riser.geo found
✓ riser.def found
✗ riser.srfs not found
✓ othd_files/ directory exists
✓ preFlex.sh found and executable
✓ gmsh path valid: /usr/bin/gmsh
✗ simGmshCnvt not found in PATH

Validation failed: 2 errors found
```

---

### `run pre` - Preprocessing

**Purpose:** Submit preprocessing job for mesh generation and format conversion.

**What it does:**

1. **Pre-submission Checks:**
   
   - Verify `preFlex.sh` exists and is executable
   - Check that `<problem>.geo` file exists
   - Validate job name matches case (e.g., `preCase001` for `Case001`)
   - Verify SLURM partition and resource flags are correct

2. **Mesh Generation Workflow:**
   
   a. **gmsh** creates `<problem>.msh` from `<problem>.geo`
   
   - The `.geo` file contains Physical Entities (Surfaces, Volumes, etc.)
   - The `.msh` file is a mesh file with all geometric entities
   
   b. **simGmshCnvt** converts `.msh` to FlexFlow format:
   
   - `<problem>.crd` - Coordinate file
   - `*.nbc` files - One for each Physical Entity (boundary conditions)
   - `*.cnn` files - One for each Physical Volume (connectivity)
   - `*.srf` files - One for each Physical Surface

**Script Naming:**

The command looks for preprocessing scripts in this order:

1. `preFlex.sh` (preferred)
2. `pre.sh`
3. `preprocessing.sh`

**Example Script:**

```bash
#!/bin/bash
#SBATCH -J preCase001        # Job name matches case
#SBATCH -p shared            # Use shared partition (recommended)
#SBATCH -n 8                 # 8 tasks
#SBATCH --cpus-per-task=4    # 4 CPUs per task
#SBATCH -t 24:00:00          # 24 hour limit

module load apps/matlab/R2022a

# Generate mesh from geometry
gmsh -3 riser.geo -o riser.msh

# Convert mesh to FlexFlow format
simGmshCnvt -n $SLURM_NTASKS -msh riser.msh

# Optional: Process coordinates
matlab -batch writeBeamLineCrd
```

**Usage:**

```bash
# Basic usage
run pre Case001

# With context
use case:Case001
run pre

# Check script before submitting
run pre Case001 --show

# Dry run (don't actually submit)
run pre Case001 --dry-run
```

**Recommended SLURM Partition:** `shared` (up to 36 workers, 24 hour limit)

---

### `run main` - Main Simulation

**Purpose:** Submit the main FlexFlow simulation job with automatic archiving of previous results.

**What it does:**

1. **Pre-submission Checks:**

   - Verify `mainFlex.sh` (or `submit.sh`) exists and is executable
   - Validate job name matches case (e.g., `mainCase001` for `Case001`)
   - Check SLURM partition and resource flags
   - Verify required input files exist (from preprocessing):
     - `<problem>.crd` - Coordinate file
     - `*.nbc`, `*.cnn`, `*.srf` files - Mesh connectivity files
   - Verify all filenames referenced in `<problem>.def` file exist:
     ```bash
     # Extract filenames from .def file
     awk -F'"' '/File[[:space:]]*\(/ {print $2}' <problem>.def
     ```

2. **Automatic Archiving:**
   
   The `run main` command handles archiving automatically, so you don't need archiving code in `mainFlex.sh`:
   
   - If `<output_dir>/<problem>.othd` exists:
     - Count files in `othd_files/` to get next number
     - Move `<problem>.othd` to `othd_files/<problem>N.othd`
     - Move `<problem>.oisd` to `oisd_files/<problem>N.oisd`
   
   This allows you to restart simulations without manually managing files.

3. **Restart Handling:**

   - **Fresh simulation** (no existing output):
     - If no `.out` files exist in output directory, start from time step 0
     - Restart lines in `simflow.config` are ignored

   - **Automatic restart** (default):
     - If `.out` files exist, find the latest restart (`.rst`) file
     - Resume simulation from last available restart file

   - **Manual restart** (with `--restart` option):
     - Use `run main --restart <tsId>` to restart from specific time step
     - Runs the restart algorithm (see Restart Algorithm section below)

4. **Simulation Execution:**
   
   - Runs `mpiSimflow` with specified number of tasks
   - Creates output files in directory specified by `simflow.config`
   - Generates `.out`, `.rst`, `.othd`, `.oisd` files

**Script Naming:**

The command looks for main simulation scripts in this order:

1. `mainFlex.sh` (preferred)
2. `submit.sh` (common alternative)
3. `main.sh`

**Example Script (Simplified - No Archiving Needed):**

```bash
#!/bin/bash
#SBATCH -J mainCase001       # Job name matches case
#SBATCH -p medium            # Use medium partition (recommended)
#SBATCH -n 120               # 120 tasks
#SBATCH --ntasks-per-node=40 # 40 tasks per node (3 nodes)
#SBATCH -t 72:00:00          # 72 hour limit

module load compiler/openmpi/4.0.2

# Run simulation (archiving handled by 'run main' command)
mpiSimflow -n $SLURM_NTASKS
```

**Note:** The archiving code shown below is handled automatically by the `run main` command and should be removed from your script:

```bash
# OLD WAY (remove from mainFlex.sh):
if [ -f SIMFLOW_DATA/riser.othd ]; then
    file_count=$(ls -p othd_files | grep -v / | wc -l)
    ((file_count++))
    mv "SIMFLOW_DATA/riser.othd" "othd_files/riser${file_count}.othd"
    mv "SIMFLOW_DATA/riser.oisd" "oisd_files/riser${file_count}.oisd"
fi
```

**Usage:**

```bash
# Basic usage (fresh start or auto-restart)
run main Case001

# With context
use case:Case001
run main

# Restart from specific time step
run main Case001 --restart 5000

# With dependency on previous job
run main Case001 --dependency <job_id>
```

**Recommended SLURM Partition:** `medium` (up to 120 workers, 72 hour limit)

---

### `run post` - Postprocessing

**Purpose:** Submit postprocessing job to generate PLT files for visualization and clean up output directory.

**What it does:**

1. **Pre-submission Checks:**

   - Verify `postFlex.sh` (or `PostSubmit.sh`, `post.sh`) exists and is executable
   - Check that output files exist in the output directory

2. **PLT File Generation (Single SLURM Job):**

   Submits `postFlex.sh` which runs sequentially:

   **Step 1: ASCII PLT Generation**
   - Runs `simPlt` to convert binary `.out` files to ASCII `.plt` files
   - Can take significant time for large datasets (minutes to hours)

   **Step 2: Binary PLT Conversion**
   - Runs `simPlt2Bin` to convert ASCII to binary PLT format
   - Files saved in `binary/` directory
   - Also can take considerable time

3. **Automatic Cleanup (Optional):**

   Cleanup happens BEFORE submitting the postprocessing job:

   **With `--cleanup` option:**
   - `run post` first identifies files that already have binary PLT files in `binary/`
   - Deletes `.out`, `.rst`, `.plt` files that have corresponding binary PLT
   - Then submits `postFlex.sh` to process remaining files
   - Avoids reprocessing already archived data

   **Without `--cleanup` option (default):**
   - No cleanup performed
   - All files processed (even if already have binary PLT)
   - User can run `run post --cleanup-only` later if needed

**Important:** Cleanup is synchronous (happens before job submission), but `postFlex.sh` job is asynchronous. Use `squeue -u $USER` to monitor the job.

**Script Naming:**

The command looks for postprocessing scripts in this order:

1. `postFlex.sh` (preferred)
2. `PostSubmit.sh` (common alternative)
3. `post.sh`

**Example Script:**

**postFlex.sh (Standard script - no cleanup):**
```bash
#!/bin/bash
#SBATCH -J postCase001       # Job name matches case
#SBATCH -p shared            # Use shared partition (recommended)
#SBATCH -n 8                 # 8 tasks for simPlt (parallel)
#SBATCH --cpus-per-task=4    # 4 CPUs per task
#SBATCH -t 24:00:00          # 24 hour limit (adjust based on data size)

module load compiler/openmpi/4.0.2

# Generate ASCII PLT files
echo "Starting ASCII PLT generation..."
simPlt -n $SLURM_NTASKS -pb riser -outFreq 100 -last 2500

# Convert ASCII PLT to binary format
echo "Starting binary PLT conversion..."
simPlt2Bin -pb riser

echo "Postprocessing complete"
```

**Note:** When using `run post --cleanup`:
1. `run post` identifies files to clean BEFORE submitting the job
2. Deletes identified `.out`, `.rst`, `.plt` files immediately
3. Then submits `postFlex.sh` to SLURM queue
4. Script runs: simPlt → simPlt2Bin (on remaining files)
5. Result: Only processes files that weren't already archived

**Usage:**

```bash
# Basic usage (submits postprocessing job, returns immediately)
run post Case001
# This submits postFlex.sh to SLURM queue and returns
# Job runs asynchronously
# Monitor with: squeue -u $USER

# With context
use case:Case001
run post

# Process specific time range
run post Case001 --last 2500 --freq 100

# With automatic cleanup after job completes
run post Case001 --cleanup
# This submits a cleanup job with dependency on postFlex.sh

# Keep original files (no cleanup)
run post Case001 --no-cleanup

# Monitor job progress (run post returns immediately)
squeue -u $USER
```

**Timeline Example (with `--cleanup` option):**
```
Time 0:00 → run post Case001 --cleanup
Time 0:00 → Identify files with existing binary PLT in binary/
Time 0:00 → Delete identified .out, .rst, .plt files (immediate)
Time 0:01 → Cleanup complete (before job submission)
Time 0:01 → Submit postFlex.sh (Job ID: 123456)
Time 0:01 → run post returns
Time 0:05 → Job 123456 starts
Time 0:05 → simPlt starts (only processes remaining files)
Time 1:15 → simPlt completes (faster - fewer files to process)
Time 1:15 → simPlt2Bin starts (only new PLT files)
Time 2:00 → simPlt2Bin completes
Time 2:00 → Job 123456 completes
Time 2:00 → All done - disk already cleaned at start
```

**Timeline Example (without `--cleanup`):**
```
Time 0:00 → run post Case001
Time 0:00 → Submit postFlex.sh (Job ID: 123456)
Time 0:00 → run post returns immediately
Time 0:05 → Job 123456 starts
Time 0:05 → simPlt starts (processes ALL .out files)
Time 2:30 → simPlt completes
Time 2:30 → simPlt2Bin starts (converts ALL PLT files)
Time 3:45 → simPlt2Bin completes
Time 3:45 → Job 123456 completes
Time 3:45 → All .out, .rst, .plt files still present (no cleanup)
         → May have duplicate binary PLT files
         → User can run: run post --cleanup-only Case001 (later)
```

**Recommended SLURM Partition:** `shared` (up to 36 workers, 24 hour limit)

---

## Executables Reference

### gmsh

**Purpose:** Mesh generation from geometry files

**Input:** `<problem>.geo` - Geometry file with Physical Entities
**Output:** `<problem>.msh` - Mesh file

**Physical Entities in .geo file:**

- Physical Surfaces - Boundary surfaces
- Physical Volumes - 3D domains
- Physical Curves - 1D edges
- Physical Points - 0D points

### simGmshCnvt

**Purpose:** Convert Gmsh mesh format to FlexFlow format

**Input:** `<problem>.msh` - Gmsh mesh file
**Output:**

- `<problem>.crd` - Node coordinates
- `<entity>.nbc` - Boundary condition files (one per Physical Entity)
- `<volume>.cnn` - Connectivity files (one per Physical Volume)
- `<surface>.srf` - Surface files (one per Physical Surface)

### mpiSimflow

**Purpose:** Main FlexFlow simulation executable (MPI parallel)

**Input:**

- `simflow.config` - Configuration file
- `<problem>.crd` - Coordinates
- `*.nbc`, `*.cnn`, `*.srf` files

**Output (in directory specified by simflow.config):**

- `*.out` - Solution output files
- `*.rst` - Restart files
- `*.othd` - Nodal time history data
- `*.oisd` - Elemental time history data

### simPlt

**Purpose:** Generate ASCII PLT files from binary output

**Input:** `*.out` files from simulation
**Output:** ASCII `.plt` files for visualization (Tecplot/ParaView)

### simPlt2Bin

**Purpose:** Convert ASCII PLT files to binary format

**Input:** ASCII `.plt` files
**Output:** Binary PLT files in `binary/` directory

---

## Restart Algorithm

When using `run main --restart <tsId>`, the following automated workflow is executed:

### 1. Pre-restart Organization

Run `case organise` to prepare the case directory:
- Organize OTHD/OISD files
- Clean up output directory structure
- Prepare for new simulation run

### 2. Archive Completed Results

When using `run main --restart <tsId>`, the system automatically runs `run post --upto <tsId> --cleanup`:

**What happens:**
```bash
# 1. Identify files to clean (before job submission)
#    - Find all files with tsId < restart point that have binary PLT
#    - Check binary/ directory for existing binary PLT files
#    - Create list of files safe to delete

# 2. Clean up identified files (immediate, synchronous)
#    - Delete <problem>.<tsId>.out for files with binary PLT
#    - Delete <problem>.<tsId>.rst for files with binary PLT
#    - Delete <problem>.<tsId>.plt for files with binary PLT
#    - Keep files >= restart point (needed for restart)
#    - Disk space freed immediately

# 3. Submit postFlex.sh to SLURM queue
#    - Returns job ID (e.g., 123456)
#    - run post returns immediately
#    - Job runs on SLURM cluster (can take hours for large datasets)

# 4. Within postFlex.sh job, runs sequentially:
#    a. simPlt - Convert remaining .out files to ASCII .plt files
#       (Faster - only processes files not already cleaned)
#
#    b. simPlt2Bin - Convert new ASCII PLT to binary format
#       Save to binary/ directory
#       (Only new files, not duplicates)
```

This ensures:
- Cleanup happens first, before postprocessing
- Avoids reprocessing already archived data
- Faster postprocessing (fewer files to process)
- Disk space freed early (before long-running job)
- Visualization data safely preserved in binary/ before cleanup
- Output directory only contains files needed for restart
- Main simulation waits for postprocessing job to complete via SLURM dependency

### 3. Submit Main Simulation

Submit `mainFlex.sh` with SLURM dependency:

```bash
# Job starts only after postprocessing job completes
# Uses --dependency=afterok:<job_id> to ensure proper execution order
# Waits for cleanup to finish before starting simulation
# Simulation resumes from specified time step
```

### Workflow Diagram

```
run main --restart 5000
    ↓
[1] case organise (immediate)
    ↓
[2] run post --upto 5000 --cleanup (cleanup first, then submit)
    ↓
    ├─ Identify files with tsId < 5000 that have binary PLT (immediate)
    ├─ Delete .out, .rst, .plt files for those tsId (immediate)
    ├─ Cleanup complete, disk space freed (immediate)
    ├─ Submit postFlex.sh → Job 123456 (SLURM queue)
    ├─ Submit mainFlex.sh → Job 123457 (depends on 123456)
    └─ run main --restart returns immediately


Job 123456 (postFlex.sh - processes remaining files):
    ├─ Status: PENDING
    ├─ Status: RUNNING
    │   ├─ Step 1: simPlt running (only files >= tsId 5000)
    │   │   (Faster - cleaned files already archived)
    │   ├─ Step 1: Complete (ASCII PLT files created)
    │   ├─ Step 2: simPlt2Bin running (only new PLT files)
    │   │   (No duplicates - cleaned files already in binary/)
    │   └─ Step 2: Complete (binary PLT files created in binary/)
    └─ Status: COMPLETED (job finished)
    ↓
Job 123457 (mainFlex.sh):
    ├─ Status: PENDING (waiting for 123456)
    ├─ Status: RUNNING (simulation from step 5000)
    └─ Simulation continues...

Total elapsed time: Potentially shorter - less data to process
Only 2 jobs total - simple dependency chain
Disk space freed early (at start, not at end)
```

### Manual Workflow (if needed)

If you need to manually perform restart steps:

```bash
# 1. Organize case
case organise

# 2. Run postprocessing up to restart point
# This submits jobs - returns immediately
run post --upto 5000

# 3. Monitor jobs until completion
squeue -u $USER
# Wait for all jobs to complete (could take hours)

# 4. Verify cleanup completed
ls SIMFLOW_DATA/  # Should see fewer files
ls binary/         # Should see new PLT files

# 5. Submit main simulation
run main
```

**Or with explicit control:**

```bash
# 1. Organize case
case organise

# 2. Generate PLT files only (no cleanup)
run post --upto 5000 --no-cleanup

# 3. Monitor postprocessing jobs
watch -n 30 'squeue -u $USER'  # Check every 30 seconds

# 4. Wait for jobs to complete (may take hours)
# Check job output for completion
tail -f slurm-*.out

# 5. Manually clean specific files if needed
# (Only if you need custom cleanup behavior)
rm SIMFLOW_DATA/riser.{1..4999}.out

# 6. Submit main simulation
run main
```

**Monitoring Tips:**

```bash
# Check job status
squeue -u $USER

# Check estimated start time
squeue -u $USER --start

# Check job details
scontrol show job <job_id>

# Monitor output in real-time
tail -f slurm-<job_id>.out

# Check if job completed successfully
sacct -j <job_id> --format=JobID,JobName,State,ExitCode
```

### Benefits of This Approach

- **Data Safety:** Only deletes files that already have binary PLT files in `binary/`
- **Efficiency:** Avoids reprocessing already archived data
- **Faster Postprocessing:** Fewer files to process = shorter job time
- **Early Disk Cleanup:** Frees space before submitting long-running job
- **No Duplicate Work:** Won't regenerate binary PLT files that already exist
- **Simplicity:** Cleanup is synchronous (immediate), postprocessing is asynchronous (SLURM)
- **Single Postprocessing Job:** Only simPlt and simPlt2Bin in the SLURM job
- **Easier Monitoring:** One postprocessing job to track
- **Automation:** Single command (`run main --restart`) handles entire restart workflow
- **Reusability:** `run post --cleanup` can be used independently to clean and update PLT files

---

## SLURM Partitions

### shared

- **Nodes:** 1 node maximum
- **Workers:** Up to 36 workers
- **Wall Time:** 24 hours maximum
- **Recommended for:** `preFlex.sh`, `postFlex.sh`
- **Typical Duration:**
  - Preprocessing: 10 minutes to 2 hours (mesh generation)
  - Postprocessing (simPlt + simPlt2Bin combined): 1 hour to 10 hours (depends on data size)

### medium

- **Nodes:** Up to 3 nodes
- **Workers:** Up to 120 workers (typically 40 per node)
- **Wall Time:** 72 hours maximum
- **Recommended for:** `mainFlex.sh`
- **Typical Duration:** Varies widely (hours to days depending on simulation)

---

## Job Timing Considerations

### Postprocessing Time Estimates

The time required for `run post` depends on several factors:

**Factors affecting total postprocessing duration:**
- Number of time steps to process
- Size of mesh (number of nodes/elements)
- Output frequency requested
- Number of MPI tasks allocated (for simPlt)
- Number of PLT files to convert (for simPlt2Bin)
- I/O performance of storage system

**Example timings (simPlt + simPlt2Bin combined):**
```
Small case (10K nodes, 1000 steps):
  simPlt: ~30 min + simPlt2Bin: ~15 min = Total: ~45 minutes

Medium case (50K nodes, 5000 steps):
  simPlt: ~2 hours + simPlt2Bin: ~1 hour = Total: ~3 hours

Large case (200K nodes, 10000 steps):
  simPlt: ~6 hours + simPlt2Bin: ~3 hours = Total: ~9 hours
```

### Resource Allocation Recommendations

**For postFlex.sh (combined script):**
```bash
#SBATCH -n 8              # 4-8 tasks optimal for simPlt
#SBATCH --cpus-per-task=4
#SBATCH -t 12:00:00       # 12 hours for large datasets
                          # Needs to cover both simPlt and simPlt2Bin
```

**Important:**
- Allocate wall time for BOTH simPlt and simPlt2Bin combined
- simPlt uses multiple tasks (parallel), simPlt2Bin runs after (sequential)
- Jobs killed by wall time limit will need to be resubmitted
- For very large datasets, consider requesting up to 24 hours

---

## Command Options

### Common Options (all subcommands)

- `--dry-run` - Show job script path without submitting
- `--show` - Display job script contents
- `--edit` - Open job script in editor before submitting
- `-v, --verbose` - Show detailed submission information
- `-h, --help` - Show help message

### Main Simulation Options (`run main`)

- `--restart <tsId>` - Restart from specific time step (runs restart algorithm)
- `--dependency <job_id>` - Submit with SLURM dependency on another job

### Postprocessing Options (`run post`)

- `--upto <tsId>` - Process output files up to specific time step
- `--last <N>` - Process last N time steps
- `--freq <N>` - Output frequency for PLT files (every N steps)
- `--cleanup` - Submit cleanup job with dependency (runs after postFlex.sh completes)
- `--no-cleanup` - Do not submit cleanup job (default for standalone `run post`)
- `--cleanup-only` - Only run cleanup (assumes binary PLT files already exist)

**Examples:**

```bash
# Show what would be submitted
run pre Case001 --dry-run

# View the job script
run main Case001 --show

# Edit job script before submission
run pre Case001 --edit

# Verbose output
run post Case001 --verbose

# Postprocessing with specific options
run post Case001 --upto 5000 --freq 100
run post Case001 --last 2500 --no-cleanup

# Restart from specific time step
run main Case001 --restart 5000
```

---

## Complete Workflow

### First-Time Setup and Simulation

```bash
# 1. Verify case structure
use case:Case001
run check

# 2. Submit preprocessing
run pre
# Monitor: squeue -u $USER

# 3. Submit main simulation
run main
# Monitor: squeue -u $USER
# Check progress: case status

# 4. Submit postprocessing jobs
run post
# Note: This submits jobs and returns immediately
# Jobs may take hours to complete

# 5. Monitor postprocessing
squeue -u $USER
# Wait for jobs to complete

# 6. After jobs complete, check results
case status
du -sh SIMFLOW_DATA/  # Should be smaller after cleanup
ls -lh binary/         # Binary PLT files created

# 7. Analyze results
data show
plot --data-type displacement --component y --gnu
```

### Restart Simulation

**Automatic Restart (resume from last time step):**

```bash
# Set context
use case:Case001

# Submit main job again
# Previous OTHD/OISD files will be archived automatically
# Simulation resumes from last available restart file
run main

# Check archived files
ls -l othd_files/ oisd_files/
```

**Manual Restart (from specific time step):**

```bash
# Set context
use case:Case001

# Restart from time step 5000
# This will:
# 1. Run case organise (immediate)
# 2. Submit postprocessing jobs (asynchronous, may take hours)
# 3. Clean output directory (after jobs complete)
# 4. Submit simulation to resume from step 5000 (with dependency)
run main --restart 5000

# Monitor progress - you'll see two jobs in the queue
squeue -u $USER
# Output:
#   JOBID    NAME           STATE     TIME
#   123456   postCase001    RUNNING   1:23:45  (simPlt, simPlt2Bin, cleanup)
#   123457   mainCase001    PENDING   0:00     (waiting for 123456)

# Check when jobs will start
squeue -u $USER --start

# Monitor postprocessing job output in real-time
tail -f slurm-123456.out
# You'll see output from simPlt, simPlt2Bin, and cleanup

# Wait for all jobs to complete (could take several hours)
watch -n 60 'squeue -u $USER'
```

### Complete Analysis Workflow

```bash
# Setup with multiple contexts
use case:Case015 problem:riser node:24 t1:50.0 t2:150.0

# Run simulation stages
run check
run pre
run main
run post

# Organize data
case clean --keep-every 10

# Postprocessing (submits jobs - may take hours)
run post

# Monitor postprocessing jobs
squeue -u $USER

# After jobs complete, analyze
case status
data show
data stats

# Visualize
plot --data-type displacement --component y --output result.pdf
plot --data-type displacement --component y --gnu
```

### Long Simulation with Restart Workflow

For simulations that exceed wall time limits:

```bash
# Setup
use case:Case015

# 1. Initial run (0 to 72 hours worth of simulation)
run check
run pre
run main

# Wait for wall time to expire (72 hours for medium partition)
# Check what time step was reached
case status

# 2. First restart (from time step 10000)
# Automatically archives results and resumes
run main --restart 10000

# 3. Second restart (from time step 20000)
run main --restart 20000

# 4. Final postprocessing after simulation completes
# This submits jobs to create binary PLT files and clean up
run post

# 5. Monitor postprocessing jobs (may take hours)
watch -n 60 'squeue -u $USER'
# Or check periodically:
squeue -u $USER

# 6. After jobs complete, verify cleanup and archiving
ls -lh binary/           # Binary PLT files should be present
du -sh SIMFLOW_DATA/     # Should be much smaller now

# 7. Analyze complete dataset
case status
data show --node 24
plot --data-type displacement --component y --gnu
```

---

## Job Management

### Check Job Status

```bash
# List your jobs
squeue -u $USER

# Check specific job
squeue -j <job_id>

# View detailed job info
scontrol show job <job_id>

# Check job efficiency after completion
seff <job_id>
```

### Cancel Jobs

```bash
# Cancel specific job
scancel <job_id>

# Cancel all your jobs
scancel -u $USER

# Cancel by name
scancel -n preCase001
```

### Monitor Job Output

```bash
# List output files
ls -l slurm-*.out

# View latest output
tail -f slurm-<job_id>.out

# Search for errors
grep -i error slurm-*.out
```

---

## Configuration Files

### simflow.config

Key parameters:

```ini
problem = riser          # Problem name (base name for files)
np      = 4              # Number of processors
nsg     = 4              # Number of subgrids
fmt     = ascii          # Output format (ascii or binary)
dir     = ./SIMFLOW_DATA # Output directory (relative or absolute)
outFreq = 5              # Output frequency (every N steps)
```

### SLURM Directives

Common directives used in job scripts:

```bash
#SBATCH -J <job_name>           # Job name
#SBATCH -p <partition>          # Partition (shared, medium, standard, gpu)
#SBATCH -n <ntasks>             # Number of tasks/processes
#SBATCH --ntasks-per-node=<n>   # Tasks per node
#SBATCH --cpus-per-task=<n>     # CPUs per task
#SBATCH -t <HH:MM:SS>           # Wall time limit
#SBATCH --mem=<size>            # Memory per node (e.g., 64G)
#SBATCH -o <output_file>        # Standard output file
#SBATCH -e <error_file>         # Standard error file
```

---

## Best Practices

### 1. Always Check Before Submitting

```bash
# Verify case structure
run check

# Review job scripts
run pre --show
run main --show
run post --show

# Check case status
case status
```

### 2. Use Context for Efficiency

```bash
# Set all contexts at once
use case:Case015 problem:riser node:24 t1:0.0 t2:200.0

# Submit without repeating case name
run check
run pre
run main
run post
```

### 3. Monitor and Organize

```bash
# Monitor running jobs
squeue -u $USER

# Monitor postprocessing job progress in real-time
tail -f slurm-<job_id>.out

# Check resource usage after completion
seff <job_id>

# Organize output files
case clean --keep-every 10

# Verify data completeness
case status
```

**For long-running postprocessing jobs:**

```bash
# Submit postprocessing
run post Case001

# Get job IDs
squeue -u $USER
# Note the job IDs (e.g., 123456, 123457)

# Monitor first job (simPlt) progress
tail -f slurm-123456.out

# Check estimated completion time
squeue -j 123456 --start

# Set up email notifications (optional)
# Edit job script to add:
# #SBATCH --mail-type=END,FAIL
# #SBATCH --mail-user=your.email@domain.com

# If you disconnect from SSH, jobs continue running
# Check status later with:
squeue -u $USER
sacct -j 123456 --format=JobID,JobName,State,Elapsed,ExitCode
```

### 4. Archive and Disk Management

**OTHD/OISD Archiving** (`run main`):
- ✓ Remove archiving code from your `mainFlex.sh`
- ✓ Let the `run main` command handle OTHD/OISD file management
- ✓ Restart simulations freely without manual cleanup

**Output Directory Cleanup** (`run post`):
- ✓ Automatically archives visualization data as binary PLT files
- ✓ Removes redundant `.out`, `.rst`, `.plt` files after binary creation
- ✓ Frees up significant disk space
- ✓ Use `--no-cleanup` if you need to keep original files

---

## Troubleshooting

### Script Not Found

```
Error: No preprocessing script found in Case001
Looking for: preFlex.sh, pre.sh, preprocessing.sh
```

**Solution:** Create the appropriate script or use symlink:

```bash
ln -s my_custom_pre.sh preFlex.sh
```

### Permission Denied

```
Error: preFlex.sh is not executable
```

**Solution:**

```bash
chmod +x preFlex.sh mainFlex.sh postFlex.sh
```

### Job Fails Immediately

**Debugging steps:**

1. Check SLURM output: `cat slurm-<job_id>.out`
2. Verify module loads: `module list`
3. Check file paths in script
4. Verify partition and resource limits
5. Check disk space: `df -h`

### Output Directory Not Found

```
Error: SIMFLOW_DATA directory not found
```

**Solution:**

```bash
# Check simflow.config
cat simflow.config | grep dir

# Create if needed
mkdir -p SIMFLOW_DATA
```

### Missing Input Files

```
Error: riser.crd not found
```

**Solution:** Run preprocessing first:

```bash
run pre Case001
# Wait for completion
run main Case001
```

### Disk Space Issues

```
Error: No space left on device
```

**Solution:** Use `run post` to clean up output directory:

```bash
# Archive results as binary PLT files and clean up
run post Case001

# Check space saved
du -sh SIMFLOW_DATA/
du -sh binary/

# For manual cleanup (if needed)
case clean --keep-every 10
```

**Prevention:** Run `run post` regularly during long simulations to avoid filling up disk:

```bash
# After each major milestone
run main Case001
# ... wait for completion ...
run post Case001  # Archives and cleans up
```

### Postprocessing Job Timeout

```
Error: Job 123456 exceeded time limit and was terminated
SLURM State: TIMEOUT
```

**Solution:** Increase wall time in postprocessing scripts

```bash
# Edit postSubmit.sh
#SBATCH -t 12:00:00  # Increase from 6:00:00 to 12:00:00

# Or process in smaller chunks
run post --last 5000  # Process last 5000 steps only
# Wait for completion
run post --last 5000 --start 5001  # Process next batch
```

**Check job efficiency to estimate needed time:**

```bash
# After a job completes (or times out)
seff <job_id>

# Shows:
# - Job Wall-clock time
# - CPU Efficiency
# - Memory usage

# Use this info to adjust resource requests
```

### Postprocessing Jobs Stuck in Queue

```
JOBID    NAME           STATE     TIME
123456   postCase001    PENDING   0:00
```

**Solution:** Check queue and dependencies

```bash
# Check why job is pending
squeue -j 123456 --start

# Check job dependencies
scontrol show job 123456 | grep Dependency

# If dependency failed, resubmit
scancel 123456
run post Case001
```

---

## Advanced Usage

### Batch Job Submission

Submit multiple cases automatically:

```bash
#!/bin/bash
# submit_all.sh

for case in Case001 Case002 Case003; do
    echo "Submitting $case..."
    run check $case || continue
    run pre $case
    sleep 2
done
```

### Conditional Submission

```bash
# Submit main only if preprocessing succeeds
run pre Case001 && run main Case001

# Full pipeline
run check && run pre && run main && run post
```

### Custom Script Names

Use symlinks for non-standard naming:

```bash
ln -s my_preprocessing.sh preFlex.sh
ln -s my_simulation.sh mainFlex.sh
ln -s my_postprocessing.sh postFlex.sh
```

---

## Integration with Other Commands

The `run` command integrates seamlessly with other FlexFlow Manager commands:

- `use` - Set case and context before running
- `case status` - Check simulation progress
- `case clean` - Organize output files
- `data show` - Preview results
- `data stats` - Statistical analysis
- `plot` - Visualize data

---

## Command Reference

| Command                          | Description                               | Example                        |
| -------------------------------- | ----------------------------------------- | ------------------------------ |
| `run check [case]`               | Validate case directory                   | `run check Case001`            |
| `run pre [case]`                 | Submit preprocessing job                  | `run pre Case001`              |
| `run main [case]`                | Submit main simulation                    | `run main Case001`             |
| `run main --restart <tsId>`      | Restart from specific time step           | `run main --restart 5000`      |
| `run main --dependency <job_id>` | Submit with SLURM dependency              | `run main --dependency 123456` |
| `run post [case]`                | Submit postprocessing (no auto cleanup)   | `run post Case001`             |
| `run post --cleanup`             | Submit postprocessing with cleanup job    | `run post --cleanup`           |
| `run post --upto <tsId>`         | Process up to specific time step          | `run post --upto 5000`         |
| `run post --last <N>`            | Process last N time steps                 | `run post --last 2500`         |
| `run post --cleanup-only`        | Only run cleanup (PLT files must exist)   | `run post --cleanup-only`      |
| `run --help`                     | Show help message                         | `run --help`                   |
| `run pre --show`                 | Display preprocessing script              | `run pre --show`               |
| `run main --dry-run`             | Preview without submitting                | `run main --dry-run`           |
| `run check --verbose`            | Detailed validation output                | `run check -v`                 |

---

## See Also

- [CASE_STRUCTURE.md](CASE_STRUCTURE.md) - Case directory structure details
- `case status` - Check case data completeness
- `case clean` - Organize output files
- `data show` - Preview simulation data
- `plot` - Visualize results
- `use` - Set case and analysis contexts
