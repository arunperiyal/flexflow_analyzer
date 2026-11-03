# FlexFlow Usage Guide

Complete guide to using FlexFlow Manager for simulation analysis.

## Table of Contents

- [Getting Started](#getting-started)
- [Command Structure](#command-structure)
- [Case Management](#case-management)
- [Data Inspection](#data-inspection)
- [Field Operations](#field-operations)
- [Visualization](#visualization)
- [Templates](#templates)
- [Advanced Usage](#advanced-usage)
- [Tips and Best Practices](#tips-and-best-practices)

## Getting Started

After installation, FlexFlow is available via the `ff` command:

```bash
# Check installation
ff --version

# Get help
ff --help

# View examples
ff --examples
```

### Command Help

Every command has built-in help:

```bash
ff --help                    # Main help
ff case --help               # Case command help
ff case show --help          # Specific subcommand help
ff plot --help               # Plot command help
```

### Tab Completion

Tab completion works for commands, subcommands, and options:

```bash
ff <TAB>                     # Shows all commands
ff case <TAB>                # Shows: show, create, run
ff plot --plot-type <TAB>    # Shows: time, fft, traj2d, traj3d
```

### Command Chaining

Chain multiple commands with semicolon (`;`) for efficient workflows:

```bash
# Set context and run commands
use case:Case005; data show --pendulum

# Multiple operations
use case:Case005 node:24 var:dy; data show; plot

# Works with quotes
plot --title "Analysis; Results"; data stats
```

**Features:**
- Tab completion works after semicolons
- Context persists across chained commands
- Errors don't stop subsequent commands
- Empty commands (;;) are skipped automatically

### Def File Parameters

```bash
def var                  # define{} variables;  def var Ur 2.0 sets one
def time                 # timeSteppingControl{};  def time maxTime 7000
def freq                 # outFreq of outputSimulation{} (out) and outputRestart{} (rst)
def freq out 50          # write output every 50 steps
def freq rst 500         # write a restart every 500 steps
```

### Version and Comments

```bash
version                      # version, commit, local changes, available updates
version --offline            # the same without fetching (as of the last fetch)
version comment "data table should sort by time"   # note a bug or a wanted feature
version comment              # list the notes
version comment --remove 3   # drop note 3 once dealt with
```

`version` fetches GitHub and lists the commits (and newer release tags) this
checkout does not have yet; on a branch with no upstream it compares with
`origin/main`. It installs nothing: update with `git pull` and
`pip install -r requirements.txt`. A comment is saved in
`~/.flexflow/comments.json` with the version, commit, time, directory,
context and the command run before it.

## Command Structure

FlexFlow uses a domain-driven command structure:

```
ff <command> <subcommand> [options] [arguments]
```

### Available Commands

**Domain Commands:**
- `case` - Manage simulation cases
- `data` - Work with time-series data
- `field` - Work with Tecplot PLT files
- `template` - Generate configuration templates

**File Inspection:**
- `check` - Inspect OTHD/OISD data files

**Visualization:**
- `plot` - Create plots
- `compare` - Compare multiple cases

**Utilities:**
- `docs` - View documentation

## Case Management

### Show Case Information

Display comprehensive information about a simulation case:

```bash
ff case show CS4SG1U1
```

**Output includes:**
- Number of nodes and timesteps
- Time range
- Available data files
- Node statistics

**Options:**
```bash
ff case show CS4SG1U1 --verbose    # Detailed output
ff case show CS4SG1U1 --json       # JSON format
```

### Create New Case

Create a new case directory from a template:

```bash
ff case create MY_NEW_CASE
```

**Interactive prompts:**
- Template selection (standard, custom)
- Configuration options
- Directory structure creation

**Options:**
```bash
ff case create MY_CASE --template standard    # Use specific template
ff case create MY_CASE --no-interactive       # Use defaults
```

**What gets created:**
```
MY_NEW_CASE/
├── input/              # Input files
├── output/             # Output directory
├── scripts/            # Job scripts
├── config.yaml         # Configuration
└── README.md           # Case documentation
```

### Run Simulations

Submit and monitor SLURM simulation jobs:

```bash
ff case run CS4SG1U1
```

**First run:**
- Submits SLURM jobs based on case configuration
- Automatically monitors job progress
- Shows real-time status updates

**Options:**

```bash
# Monitor automatically (default)
ff case run CS4SG1U1

# Submit without monitoring
ff case run CS4SG1U1 --no-monitor

# Clean start (removes existing OTHD files)
ff case run CS4SG1U1 --clean

# Restart from specific timestep
ff case run CS4SG1U1 --from-step 5000

# Dry run (preview without submitting)
ff case run CS4SG1U1 --dry-run

# Custom job parameters
ff case run CS4SG1U1 --nodes 4 --ntasks 128
```

**Monitoring:**
- Press `Ctrl+C` to stop monitoring (jobs continue running)
- Use `run sq` to check job status in the CLI
- Use `squeue -u $USER` to check jobs manually
- Logs are saved in case directory

**Check Job Queue:**

View your running jobs:
```bash
ff run sq                  # Show your jobs
ff run sq --all            # Show all users' jobs
ff run sq --by-dir         # Group jobs by parent directory (case name level)
ff run sq --sort submitted # Sort jobs by submit time
ff run sq watch            # Auto-refresh every 10 seconds (run sq watch 30 for 30s)
ff run sq find CS4SG3U3P0  # Jobs whose name or work directory contains the key, grouped by directory
ff run sq <job_id>         # Show detailed info for a job
ff run sq <job_id> --out -n 50  # Show last 50 lines from job StdOut
```

The `--by-dir` flag is useful when running multiple simulations:
- Groups jobs by parent directory (removes case name from the path)
- Helps identify which domain/geometry configurations share jobs
- Handy when you have jobs with the same name in different cases under the same parent directory

**Example workflow:**
```bash
# Create case
ff case create MY_SIMULATION

# Review and edit configuration
cd MY_SIMULATION
vim config.yaml

# Submit jobs
ff case run MY_SIMULATION

# Check progress (if monitoring was stopped)
ff run sq                  # View all jobs
ff run sq --by-dir         # View jobs grouped by directory
```

### Remote Machine Management

Manage remote machines for file transfer operations:

```bash
# Add a new remote machine
ff remote add myserver --user john --ip 192.168.1.100 --password secret123

# List all configured remotes
ff remote list

# Update remote settings
ff remote modify myserver --port 2222 --password newpass

# Set base path for case uploads
ff remote set-path myserver /home/john/simulations

# Remove a remote
ff remote delete myserver
```

**Remote Configuration:**
- Credentials are stored in `~/.flexflow/remotes.json` (read/write permissions only by owner)
- Supports custom SSH ports (default: 22)
- Base path can be overridden per upload operation

### Upload Cases to Remote

Transfer case directories from your local machine to remote servers:

```bash
# Basic upload (uploads othd_files, oisd_files, binary by default)
ff case upload ./mycase --to myserver

# Upload specific directories only
ff case upload ./mycase --to myserver --dir othd_files,oisd_files

# Override the remote path for this upload
ff case upload ./mycase --to myserver --remote-path /scratch/simulations

# Create missing remote directories before upload
ff case upload ./mycase --to myserver --dir othd_files --force

# Only the OTHD/OISD history (`case organise history`): archive/, cleaned/,
# the compiled file -- or the sets named with --archive/--cleaned/--compiled
ff case upload history ./mycase --to myserver
ff case download history ./mycase --from myserver --cleaned --compiled

# Specify relative path
ff case upload mycase --to myserver
```

**Upload behavior:**
- Uses local case directory as source
- Uploads only specified directories (default: othd_files, oisd_files, binary)
- `--force` creates missing remote directories before uploading
- Shows transfer progress with file counts
- Preserves local directory structure on remote

**Binary transfers and the session timeout:**

In the shell, `case upload|download binary` is set against the time the
session has left (the `ttl` in the prompt), at `set transfer_speed` Mbps
(default 10). When it will not finish, it says so and offers the steps that
fit:

```
Session timeout: 412 file(s), 6.8 GB: about 1 h 37 min at 10 Mbps, and 5 min is left in this session.
    Up to --t2 2350 fits: steps 2000..2350, 38 file(s), 410 MB, about 5 min.
    --t1 2000 --t2 2350 now; the rest later with --t1 2351, or --missing.
    Send all anyway [y], only up to --t2 2350 [t], or stop [N]?
```

```bash
set transfer_speed 8                              # plan with the speed the link really gets
ff case upload binary mycase --to myserver --fit  # take the cut without asking
ff case upload binary mycase --to myserver --no-time-check
```

A finished transfer of 50 MB or more prints the rate it reached, and the
`set transfer_speed` to use when it is far from the planned one. A one-shot
command (`flexflow case upload ...` from bash) has no timeout and is not
checked.
- Supports tilde expansion (`~/cases/mycase`)

**Example workflow:**
```bash
# Configure remote once
ff remote add hpc-cluster --user jane --ip 192.168.10.50 --password xyz
ff remote set-path hpc-cluster /home/jane/projects

# Later: Upload completed simulation
ff case upload mySimulation --to hpc-cluster

# Upload specific output files only
ff case upload mySimulation --to hpc-cluster --dir othd_files

# Upload to different remote base location
cd /local/storage
ff case upload ../mySimulation --to hpc-cluster --remote-path /alternate/path
```

## Data Inspection

### Check Data Files

Quickly inspect OTHD or OISD files:

```bash
ff check riser.othd
ff check CS4SG1U1/output/riser.othd
```

**Output includes:**
- File format and version
- Number of nodes and timesteps
- Time range and step size
- Data dimensions

**Options:**
```bash
ff check riser.othd --time-steps 0 5000    # Specific time range
ff check riser.othd --nodes 1 10 20        # Specific nodes
```

### Show Data

Preview time-series data in table format:

```bash
ff data show CS4SG1U1
```

**Options:**
```bash
ff data show CS4SG1U1 --node 24            # Specific node
ff data show CS4SG1U1 --limit 100          # First 100 rows
ff data show CS4SG1U1 --format csv         # CSV output
```

**Example output:**
```
Time      Node  Displacement_X  Displacement_Y  Displacement_Z
0.05      24    0.001          -0.003           0.000
0.10      24    0.002          -0.005           0.001
...
```

### Data Statistics

Calculate statistics for time-series data:

```bash
ff data stats CS4SG1U1
```

**Output includes:**
- Min, max, mean, std dev
- Per node and component
- Time-averaged values

## Field Operations

Work with Tecplot PLT files using PyTecplot integration.

### Field Information

Show information about PLT files:

```bash
ff field info CS4SG1U1
```

**Output includes:**
- Available zones
- Variable names
- Grid dimensions
- Time values

**Options:**
```bash
ff field info CS4SG1U1 --file riser.1000.plt    # Specific file
ff field info CS4SG1U1 --verbose                # Detailed output
```

### Extract Field Data

Extract specific field data to CSV:

```bash
ff field extract CS4SG1U1 --field displacement --node 10
```

**Options:**
```bash
ff field extract CS4SG1U1 \
  --field velocity \
  --node 10 \
  --output velocity_node10.csv
```

## Visualization

### Plot Data

`plot` draws the columns `data table` reads for the same `--var`, node and
window. The variable comes from `--var` or the `var` context:

```bash
ff plot CS4SG1U1 --var dy --node 10
use case:CS4SG1U1 node:10 var:dy; plot          # the same from the context
```

**What to plot:**
```bash
ff plot CS4SG1U1 --var dy            # one component (aleDisp_y)
ff plot CS4SG1U1 --var d             # every component, one panel each
ff plot CS4SG1U1 --var dx,dy         # some of them
ff plot CS4SG1U1 --var tty           # surface output (totTrac_y, oisd)
ff plot CS4SG1U1 --var pd            # pendulum pendDisp (pv, pa: velocity, acceleration)
```
`data show` lists every variable and its short name. Variables from the othd
and oisd files cannot share a plot; `--othid`/`--osgid` pick the group.

**Window and plot type:**
```bash
ff plot CS4SG1U1 --var dy --t1 2000 --t2 4000     # tsIds, as in data table
ff plot CS4SG1U1 --var dy --last 1000             # or use last:1000
ff plot CS4SG1U1 --var dy --plot-type fft --last 2000   # spectrum, peak in the legend
ff plot CS4SG1U1 --var d --plot-type traj2d       # dx against dy (traj3d: all three)
```

**Styling and output:**
```bash
ff plot CS4SG1U1 --var dy \
  --title "Node 10 Displacement" --xlabel "Time (s)" --ylabel "Displacement (m)"
ff plot CS4SG1U1 --var dy --output displacement.png   # .png, .pdf, .svg, .eps
ff plot CS4SG1U1 --var dy --gnu                       # in the terminal
```

### Compare Cases

Compare multiple cases side-by-side:

```bash
ff compare CS4SG1U1 CS4SG2U1
```

**Options:**
```bash
# Specific component
ff compare CS4SG1U1 CS4SG2U1 --component y

# Specific node
ff compare CS4SG1U1 CS4SG2U1 --node 10

# Save comparison
ff compare CS4SG1U1 CS4SG2U1 --output comparison.png

# Multiple nodes
ff compare CS4SG1U1 CS4SG2U1 --nodes 10 20 30
```

**Example output:**
- Overlay plots of both cases
- Legend with case names
- Statistical comparison table

## Templates

### Plot Configuration

Generate plot configuration templates:

```bash
ff template plot
```

**Creates:** `plot_config.yaml`

**Example content:**
```yaml
plot:
  type: time-series
  data_type: displacement
  component: y
  nodes: [10, 20, 30]
  output: plot.png
```

**Use template:**
```bash
ff plot CS4SG1U1 --config plot_config.yaml
```

### Case Configuration

Generate case creation templates:

```bash
ff template case
```

**Creates:** `case_template.yaml`

**Example content:**
```yaml
case:
  name: MY_CASE
  description: Simulation case
  slurm:
    nodes: 2
    ntasks: 64
    time: "24:00:00"
```

## Advanced Usage

### Command Chaining in Interactive Mode

Chain multiple commands for efficient workflows:

```bash
# Quick analysis workflow
use case:Case005; data show; data stats

# Set context and plot
use case:Case005 node:24 var:dy t1:1000 t2:2000; plot

# Pendulum analysis
use case:Case005 var:pv; data show --pendulum; plot

# Multiple operations
cd ~/simulations; use case:Case005 var:pd; data show; plot --output result.png
```

**Benefits:**
- Faster than typing separate commands
- Context persists across chain
- Tab completion works after semicolons
- Errors don't stop subsequent commands

### Batch Processing

Process multiple cases:

```bash
# Loop through cases
for case in CS4SG1U1 CS4SG2U1 CS4SG3U1; do
  ff case show $case
  ff plot $case --node 10 --output ${case}_plot.png
done
```

### Scripting

Use FlexFlow in scripts:

```bash
#!/bin/bash
# analyze_cases.sh

CASES="CS4SG1U1 CS4SG2U1"

for case in $CASES; do
  echo "Analyzing $case..."

  # Get case info
  ff case show $case > ${case}_info.txt

  # Create plots
  ff plot $case --node 10 --output ${case}_node10.png

  # Export data
  ff data show $case --format csv > ${case}_data.csv
done

echo "Analysis complete!"
```

### Python Integration

Use FlexFlow from Python:

```python
import subprocess
import json

# Run command and get output
result = subprocess.run(
    ['ff', 'case', 'show', 'CS4SG1U1', '--json'],
    capture_output=True,
    text=True
)

data = json.loads(result.stdout)
print(f"Nodes: {data['nodes']}")
print(f"Timesteps: {data['timesteps']}")
```

### Environment Variables

Configure FlexFlow behavior:

```bash
# Set default case directory
export FLEXFLOW_CASE_DIR=/path/to/cases

# Set default output directory
export FLEXFLOW_OUTPUT_DIR=/path/to/output

# Enable debug mode
export FLEXFLOW_DEBUG=1

ff case show CS4SG1U1
```

## Tips and Best Practices

### Performance

**Fast startup:**
- Use alias installation for 0.4s startup
- Avoid user/system install if speed is critical

**Data processing:**
- Use `--limit` flag for large datasets
- Filter by time range when possible
- Use PyTecplot for PLT file operations

### Workflow Optimization

**Case creation:**
1. Use templates for consistency
2. Keep standard naming conventions
3. Document cases with README files

**Data analysis:**
1. Start with `ff check` to understand file structure
2. Use `ff data show` for quick preview
3. Create plots for visualization
4. Export to CSV for external analysis

**Job management:**
1. Use `--dry-run` first to verify configuration
2. Monitor initial runs, then use `--no-monitor`
3. Check logs regularly
4. Use `--clean` for fresh starts

### Common Patterns

**Quick case inspection:**
```bash
ff case show CS4SG1U1 && \
ff check CS4SG1U1/output/riser.othd && \
ff data show CS4SG1U1 --limit 10
```

**Create and run simulation:**
```bash
ff case create NEW_CASE && \
cd NEW_CASE && \
# Edit config.yaml \
ff case run NEW_CASE --dry-run && \
ff case run NEW_CASE
```

**Compare and export:**
```bash
ff compare CS4SG1U1 CS4SG2U1 --output comparison.png
ff data show CS4SG1U1 --format csv > case1.csv
ff data show CS4SG2U1 --format csv > case2.csv
```

### Troubleshooting

**Command not found:**
```bash
# Reload shell
source ~/.bashrc

# Check alias
alias | grep ff

# Manual activation
conda activate flexflow_env
python /path/to/main.py --help
```

**Import errors:**
```bash
# Check environment
conda activate flexflow_env
pip list | grep pytecplot

# Reinstall dependencies
conda activate flexflow_env
pip install -r requirements.txt
```

**Tecplot errors:**
```bash
# Check Tecplot
which tec360
echo $TECPLOT_360

# Test PyTecplot
python -c "import tecplot; print('OK')"
```

**Permission errors:**
```bash
# Check file permissions
ls -la /path/to/case

# Fix if needed
chmod -R u+rw /path/to/case
```

## Further Reading

- [Installation Guide](../INSTALL.md) - Setup and configuration
- [Documentation Index](INDEX.md) - Complete reference
- [Performance Guide](technical/STARTUP_PERFORMANCE.md) - Optimization tips
- [GitHub Repository](https://github.com/arunperiyal/flexflow_analyzer) - Source code and issues
