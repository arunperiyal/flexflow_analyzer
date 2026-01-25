# FlexFlow Documentation

## Getting Started

### Installation
- [INSTALL.md](../INSTALL.md) - Quick installation guide
- [setup/INSTALL_INTERACTIVE.md](setup/INSTALL_INTERACTIVE.md) - Detailed installation

### Quick Reference

```bash
# Installation
./install.sh

# Basic usage
ff -v                        # Version
ff case show CS4SG1U1       # Case info
ff field info CS4SG1U1      # Field info
ff plot CS4SG1U1 --node 10  # Plot data
```

## Command Reference

### Case Commands

```bash
ff case show <case>         # Display case information
ff case create <name>       # Create new case from template
ff case run <case>          # Submit and monitor SLURM simulation jobs
ff case list                # List all available cases
```

### Field Commands

```bash
ff field info <case>        # Show field information
ff field list <case>        # List available fields
ff field extract <case>     # Extract field data
```

### Data Commands

```bash
ff data compare <cases>     # Compare multiple cases
ff data export <case>       # Export data
ff data statistics <case>   # Show statistics
```

### Plot Commands

```bash
ff plot <case> [options]    # Create plots
  --node N                  # Select node
  --component x|y|z         # Select component
  --output FILE             # Save to file
  --show                    # Display plot
```

### Tecplot Commands

```bash
ff tecplot convert <file>   # Convert PLT files
  --format hdf5|szplt       # Output format
ff tecplot info <file>      # Show PLT file info
```

## Technical Documentation

- [technical/STARTUP_PERFORMANCE.md](technical/STARTUP_PERFORMANCE.md) - Performance guide
- [technical/STANDALONE_BUILD.md](technical/STANDALONE_BUILD.md) - Building standalone

## Examples

### Run a Simulation

```bash
# Submit simulation jobs (first run)
ff case run CS4SG1U1

# Monitor progress automatically
# Press Ctrl+C to stop monitoring (jobs continue)

# Submit without monitoring
ff case run CS4SG1U1 --no-monitor

# Clean start (removes existing OTHD files)
ff case run CS4SG1U1 --clean

# Restart from specific timestep
ff case run CS4SG1U1 --from-step 5000

# Dry run (preview without submitting)
ff case run CS4SG1U1 --dry-run
```

### Analyze a Case

```bash
# Show case overview
ff case show CS4SG1U1

# Expected output:
# Loading OTHD files...
# Loaded: 49 nodes, 4430 timesteps
# Time range: 0.05 to 221.50
# ...
```

### Extract Field Data

```bash
# Get field information
ff field info CS4SG1U1

# Extract specific field
ff field extract CS4SG1U1 --field displacement --node 10
```

### Compare Cases

```bash
# Compare two cases
ff data compare CS4SG1U1 CS4SG2U1 --component y

# With custom output
ff data compare CS4SG1U1 CS4SG2U1 --output comparison.png
```

### Create Plots

```bash
# Simple time series plot
ff plot CS4SG1U1 --node 10 --component y

# Save to file
ff plot CS4SG1U1 --node 10 --component y --output displacement.png

# Multiple components
ff plot CS4SG1U1 --node 10 --component xyz --show
```

### Convert Tecplot Files

```bash
# Convert to HDF5
ff tecplot convert CS4SG1U1/binary/riser.1000.plt --format hdf5

# Convert to SZPLT
ff tecplot convert CS4SG1U1/binary/riser.1000.plt --format szplt
```

## Tips

### Fast Startup

Use the alias installation for fastest startup:
```bash
./install.sh
# Choose Option 1: Fast Alias
# Result: 0.4s startup time
```

### Tab Completion

Enable tab completion during installation for easier use:
```bash
ff case <TAB>       # Shows: show, create, list
ff field <TAB>      # Shows: info, list, extract
```

### Help

Get help for any command:
```bash
ff --help           # Main help
ff case --help      # Case command help
ff plot --help      # Plot command help
```

## Troubleshooting

### Command not found

```bash
# Reload shell
source ~/.bashrc

# Check if alias exists
alias | grep ff
```

### Import errors

```bash
# Activate environment manually
conda activate flexflow_env

# Check packages
pip list | grep pytecplot
```

### Tecplot errors

```bash
# Check Tecplot installation
which tec360

# Test pytecplot
python -c "import tecplot; print('OK')"
```

## Version

Current version: **2.0.0**

Check version:
```bash
ff -v
```

## Support

- GitHub: https://github.com/arunperiyal/flexflow_analyzer
- Issues: https://github.com/arunperiyal/flexflow_analyzer/issues

---

**Documentation Structure:**
- README.md - Project overview
- INSTALL.md - Quick install
- docs/INDEX.md - This file (command reference)
- docs/setup/ - Installation guides
- docs/technical/ - Technical details
