# FlexFlow Standard Template

This directory serves as a **reference template** for creating new simulation cases.

## Purpose

When you run:
```bash
ff case create myNewCase --ref-case examples/standard
```

FlexFlow will copy files from this directory to create your new case with all necessary scripts and configuration files.

## Files in This Template

### Configuration Files
- **config.sh** - Centralized configuration (paths, modules, settings)
- **common.sh** - Reusable functions library (logging, validation, etc.)

### SLURM Scripts
- **preFlex.sh** - Pre-processing (mesh generation, conversion)
- **mainFlex.sh** - Main simulation (FlexFlow solver)
- **postFlex.sh** - Post-processing (PLT extraction, conversion)

### Simulation Files
- **riser.geo** - Gmsh geometry definition
- **riser.def** - FlexFlow definition file
- **simflow.config** - Simulation configuration
- **case_config.yaml** - FlexFlow case configuration

## Quick Start

### 1. Create a New Case

```bash
# Create from this template
ff case create CS1 --ref-case examples/standard --problem-name riser

# Or specify custom settings
ff case create CS1 --ref-case examples/standard --problem-name riser --np 64 --freq 100
```

### 2. Customize Configuration

Edit the configuration file in your new case:
```bash
cd CS1
vi config.sh
```

Update these key settings:
```bash
# Executable paths (required)
export FLEXFLOW_BIN="/path/to/your/modalFlexFlow/bin"
export GMSH_BIN="/path/to/your/gmsh-4.4.1/bin/gmsh4"

# Simulation settings (optional)
export PROBLEM="riser"
export OUTFREQ=50
export LAST_TIME=4000
```

### 3. Run Simulation

```bash
# Submit jobs in sequence
sbatch preFlex.sh    # Preprocessing
sbatch mainFlex.sh   # Main simulation (after pre completes)
sbatch postFlex.sh   # Postprocessing (after main completes)
```

### 4. Monitor and Analyze

```bash
# Check job status
squeue -u $USER

# View logs
tail -f logs/mainFlex_*.log

# Check output files
ff check othd_files/riser1.othd

# Analyze results
ff data show CS1 --node 10
ff plot CS1 --node 10 --component y
```

## Key Features

### ✅ Configuration Management (config.sh)
- **Centralized settings** - Edit once, affects all scripts
- **User-customizable paths** - No hardcoded user directories
- **Environment variables** - Flexible configuration
- **Module settings** - MPI, MATLAB with fallbacks

### ✅ Reusable Functions (common.sh)
- **Logging** - Timestamped logs with colors (info/success/warning/error)
- **Error handling** - Validation of executables and input files
- **File management** - Auto-creates directories, robust file counting
- **SLURM integration** - Job information display
- **Module loading** - Primary + fallback support

### ✅ Improved Scripts
- **Error handling** - `set -euo pipefail`, strict validation
- **Automatic directories** - Creates othd_files/, oisd_files/, rcv_files/, plt_files/
- **Sequential archiving** - Proper file numbering for restarts
- **Progress reporting** - Clear status messages
- **Input validation** - Checks executables and files before running

## File Organization

After running a simulation, your case directory will look like:

```
CS1/
├── config.sh              # Configuration
├── common.sh              # Function library
├── preFlex.sh            # Pre-processing script
├── mainFlex.sh           # Main simulation script
├── postFlex.sh           # Post-processing script
├── riser.geo             # Geometry
├── riser.def             # Definition
├── riser.msh             # Generated mesh
├── simflow.config        # Simulation config
├── case_config.yaml      # FlexFlow config
├── logs/                 # Execution logs
│   ├── preFlex_*.log
│   ├── mainFlex_*.log
│   └── postFlex_*.log
├── othd_files/           # Displacement data
│   └── riser1.othd, riser2.othd, ...
├── oisd_files/           # Surface data
│   └── riser1.oisd, riser2.oisd, ...
├── rcv_files/            # Restart files
├── plt_files/            # Tecplot files
└── RUN_1/                # Simulation output
```

## Customization

### Modify SLURM Parameters

Edit the `#SBATCH` directives in each script:

```bash
# In preFlex.sh, mainFlex.sh, or postFlex.sh
#SBATCH -n 36              # Change number of tasks
#SBATCH -t 72:00:00        # Change walltime
#SBATCH -p medium          # Change partition
```

### Add Custom Functions

Add new functions to `common.sh`:
```bash
# Custom analysis function
my_analysis() {
    log_info "Running custom analysis..."
    # Your code here
}
```

Use in any script:
```bash
source "${SCRIPT_DIR}/common.sh"
my_analysis
```

### Email Notifications

Uncomment in scripts:
```bash
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=your.email@domain.com
```

## Best Practices

1. ✅ **Always edit config.sh first** before running scripts
2. ✅ **Test on small cases** before large simulations
3. ✅ **Check logs** in `logs/` directory for issues
4. ✅ **Validate outputs** using `ff check` command
5. ✅ **Monitor SLURM jobs** with `squeue` and `sacct`

## Troubleshooting

### Executable not found
```bash
# Verify paths in config.sh
echo $FLEXFLOW_BIN
ls -la $FLEXFLOW_BIN/mpiSimflow

# Update config.sh if needed
```

### Module not loading
```bash
# Check available modules
module avail openmpi

# Update config.sh with correct module name
export MPI_MODULE="correct/module/name"
```

### Permission denied
```bash
# Make scripts executable
chmod +x *.sh
```

## Integration with FlexFlow

This template is designed to work seamlessly with FlexFlow commands:

```bash
# Case management
ff case show CS1
ff case create CS2 --ref-case examples/standard

# Data inspection
ff check CS1/othd_files/riser1.othd

# Data analysis
ff data show CS1 --node 10
ff data stats CS1 --node 10

# Visualization
ff plot CS1 --node 10 --component y
ff compare CS1 CS2 --node 10
```

## Version

**Template Version:** 2.0 (Improved)  
**Compatible with:** FlexFlow 2.0+  
**Date:** 2026-01-26

---

For more information, see FlexFlow documentation: `docs/INDEX.md`
