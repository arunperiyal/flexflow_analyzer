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
ff plot --data-type <TAB>    # Shows: displacement, force, moment, pressure
```

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
- Use `squeue` to check job status manually
- Logs are saved in case directory

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
squeue -u $USER
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

Create time-series plots:

```bash
ff plot CS4SG1U1 --node 10 --component y
```

**Common options:**
```bash
# Basic plot
ff plot CS4SG1U1 --node 10

# Specific component
ff plot CS4SG1U1 --node 10 --component y

# Multiple components
ff plot CS4SG1U1 --node 10 --component xyz

# Data type
ff plot CS4SG1U1 --node 10 --data-type displacement
ff plot CS4SG1U1 --node 10 --data-type force

# Save to file
ff plot CS4SG1U1 --node 10 --output displacement.png

# Show interactively
ff plot CS4SG1U1 --node 10 --show
```

**Advanced options:**
```bash
# Time range
ff plot CS4SG1U1 --node 10 --time-start 0 --time-end 100

# Custom styling
ff plot CS4SG1U1 --node 10 \
  --title "Node 10 Displacement" \
  --xlabel "Time (s)" \
  --ylabel "Displacement (m)"

# Multiple nodes
ff plot CS4SG1U1 --nodes 10 20 30 --component y
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
