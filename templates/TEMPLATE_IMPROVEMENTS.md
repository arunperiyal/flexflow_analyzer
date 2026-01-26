# FlexFlow Template Scripts - Improved Version

## Overview

The FlexFlow template scripts have been improved with better error handling, logging, configuration management, and reusable functions.

## Files

```
templates/
├── standard/
│   ├── config.sh         # Configuration file (paths, settings)
│   ├── common.sh         # Reusable functions library
│   ├── preFlex.sh        # Pre-processing script
│   ├── mainFlex.sh       # Main simulation script
│   ├── postFlex.sh       # Post-processing script
│   ├── *.sh.old          # Backup of original scripts
│   └── ...
└── myCase/
    └── (same structure)
```

## Key Improvements

### 1. **Critical Bug Fixes**
- ✅ Fixed `${RISER}` → `${PROBLEM}` in postFlex.sh line 19
- ✅ Fixed `${OURFREQ}` → `${OUTFREQ}` in postFlex.sh line 24

### 2. **Configuration Management (config.sh)**
- Centralized configuration in one file
- User-customizable paths for executables
- Default settings for all parameters
- Environment variables for flexibility

### 3. **Reusable Functions (common.sh)**
- Logging with timestamps and colors
- Error handling and validation
- Directory management
- File counting and archiving
- Module loading with fallbacks
- SLURM job information display

### 4. **Error Handling**
- `set -euo pipefail` for strict error handling
- Validation of executables and input files
- Clear error messages with colors
- Automatic cleanup on exit

### 5. **Better Logging**
- Timestamped log files in `logs/` directory
- Color-coded console output
- Structured logging (info, success, warning, error)
- Job summary with duration

### 6. **Improved File Management**
- Creates required directories automatically
- Robust file counting (handles spaces, special chars)
- Sequential file archiving with proper numbering
- File size reporting

### 7. **SLURM Enhancements**
- Better SLURM parameter organization
- Job information display
- Optional email notifications
- Separate output/error files per job

## Usage

### Quick Start

1. **Edit configuration:**
   ```bash
   vi config.sh
   # Set FLEXFLOW_BIN, GMSH_BIN, and other paths
   ```

2. **Run scripts:**
   ```bash
   sbatch preFlex.sh    # Pre-processing
   sbatch mainFlex.sh   # Main simulation
   sbatch postFlex.sh   # Post-processing
   ```

### Configuration

Edit `config.sh` to customize:

```bash
# Executable paths
export FLEXFLOW_BIN="/home/${USER}/modalFlexFlow/bin"
export GMSH_BIN="/home/${USER}/gmsh-4.4.1/bin/gmsh4"

# Simulation settings
export PROBLEM="riser"
export OUTDIR="RUN_1"
export OUTFREQ=50
export LAST_TIME=4000

# Module settings
export MPI_MODULE="compiler/openmpi/4.0.2"
export MATLAB_MODULE="apps/matlab/R2022a"
```

### Template Variables

When creating new cases, FlexFlow can replace these placeholders:

- `__JOBNAME__` - Job name for SLURM
- `__PROBLEM_NAME__` - Problem/case name
- `__OUTPUT_DIR__` - Output directory
- `__FLEXFLOW_BIN__` - Binary path
- `__NTASKS__` - Number of tasks

## Features

### Logging

All scripts create timestamped log files in `logs/`:
```
logs/
├── preFlex_20260126_123456.log
├── mainFlex_20260126_134567.log
└── postFlex_20260126_145678.log
```

### Output Organization

```
case_directory/
├── othd_files/        # OTHD displacement files
├── oisd_files/        # OISD surface data files
├── rcv_files/         # RCV restart files
├── plt_files/         # Tecplot PLT files
├── logs/              # Execution logs
└── RUN_1/             # Simulation output
```

### Error Handling Example

```bash
# Validates executable before running
check_executable "${FLEXFLOW_BIN}/mpiSimflow" "mpiSimflow" || exit 1

# If not found, shows:
[✗] Executable not found or not executable: /path/to/mpiSimflow
[✗] Please check your config.sh file
```

### Module Loading with Fallback

```bash
# Tries primary module, falls back to alternative
load_module_safe "${MPI_MODULE}" "${MPI_MODULE_ALT}" || exit 1

# If neither found, shows:
[!] Module compiler/openmpi/4.0.2 not available, trying openmpi/4.0.2...
[✗] Module not found: compiler/openmpi/4.0.2
```

## Migration from Old Scripts

### Automatic Backup

Original scripts are automatically backed up with `.old` extension:
- `preFlex.sh.old`
- `mainFlex.sh.old`
- `postFlex.sh.old`

### Key Differences

| Old Script | New Script |
|-----------|-----------|
| Hardcoded paths | Configurable via `config.sh` |
| No error checking | Strict error handling |
| Basic output | Structured logging with colors |
| Manual directory creation | Automatic directory setup |
| Fragile file counting | Robust file handling |
| Bug: `${RISER}`, `${OURFREQ}` | Fixed: `${PROBLEM}`, `${OUTFREQ}` |

### To Revert

If needed, restore original scripts:
```bash
mv preFlex.sh.old preFlex.sh
mv mainFlex.sh.old mainFlex.sh
mv postFlex.sh.old postFlex.sh
```

## Customization

### Adding Custom Functions

Add to `common.sh`:
```bash
# Custom function
my_custom_task() {
    log_info "Running custom task..."
    # Your code here
}
```

Use in scripts:
```bash
# In preFlex.sh, mainFlex.sh, or postFlex.sh
my_custom_task
```

### Adjusting Logging Level

In `config.sh`:
```bash
# Disable logging
export ENABLE_LOGGING=0

# Enable verbose logging (future feature)
export LOG_LEVEL="DEBUG"
```

### Email Notifications

Uncomment in scripts:
```bash
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=your.email@domain.com
```

Or set in `config.sh`:
```bash
export SLURM_EMAIL="your.email@domain.com"
```

## Best Practices

1. **Always edit config.sh first** - Don't modify scripts directly
2. **Check logs** - Review log files in `logs/` directory
3. **Validate before running** - Test configuration on small cases
4. **Use FlexFlow check** - Verify output files: `ff check *.othd`
5. **Monitor SLURM** - Check job status: `squeue -u $USER`

## Troubleshooting

### Problem: Executable not found

```bash
# Check config.sh paths
echo $FLEXFLOW_BIN
ls -la $FLEXFLOW_BIN/mpiSimflow

# Update config.sh if needed
export FLEXFLOW_BIN="/correct/path/to/bin"
```

### Problem: Module not loading

```bash
# Check available modules
module avail openmpi

# Update config.sh with correct module name
export MPI_MODULE="actual/module/name"
```

### Problem: Permission denied

```bash
# Make scripts executable
chmod +x *.sh

# Check file permissions
ls -la *.sh
```

## Future Enhancements

Planned improvements:
- JSON/YAML configuration support
- Parallel job dependency chains
- Automatic restart detection
- Progress monitoring
- Resource usage reporting

## Support

For issues or questions:
- Check log files in `logs/` directory
- Review SLURM output: `slurm-*.out` and `slurm-*.err`
- Use FlexFlow: `ff check` and `ff case show`

---

**Version:** 2.0 (Improved)  
**Date:** 2026-01-26  
**Compatible with:** FlexFlow 2.0+
