# FlexFlow - Simulation Analysis Tool

Fast and efficient tool for analyzing FlexFlow simulation data with PyTecplot integration.

## Quick Start

### 1. Install (2 minutes)

```bash
./install.sh
```

The installer will:
- ✅ Check for Anaconda/Miniconda
- ✅ Create Python 3.12 environment
- ✅ Install dependencies (numpy, matplotlib, pytecplot)
- ✅ Setup FlexFlow command

### 2. Use FlexFlow

```bash
# After installation, reload your shell:
source ~/.bashrc

# Analyze a case:
ff case show CS4SG1U1

# Get field information:
ff field info CS4SG1U1

# Plot data:
ff plot CS4SG1U1 --node 10 --component y

# Show version:
ff -v
```

## Features

- **Fast Startup**: 0.4s command startup (7x faster than standalone)
- **PyTecplot Integration**: 2-3x faster PLT file operations
- **Auto Python 3.12**: Automatically uses correct Python version
- **Easy Installation**: One command setup
- **Domain Commands**: Intuitive command structure (case, field, data, plot)
- **Multiple Cases**: Analyze and compare simulation cases

## Command Overview

```bash
ff case show <case>          # Show case information
ff case create <name>        # Create new case from template
ff case run <case>           # Submit and monitor SLURM simulation jobs
ff case list                 # List available cases

ff field info <case>         # Show field information
ff field list <case>         # List available fields
ff field extract <case>      # Extract field data

ff data compare <cases>      # Compare multiple cases
ff data export <case>        # Export data to format

ff plot <case> [options]     # Plot case data
ff tecplot convert <file>    # Convert PLT files
```

## Requirements

- **Anaconda or Miniconda** (for Python 3.12 environment)
- **Tecplot 360 EX** (for PLT file operations)
- **Linux** (tested on Ubuntu 20.04+)

## Installation Options

The installer offers 4 types:

1. **Fast Alias** (Recommended) - Creates `ff` command, 0.4s startup
2. **User Install** - Installs to ~/.local/bin
3. **System Install** - Installs to /usr/local/bin (requires sudo)
4. **Both** - Alias + wrapper for flexibility

## Documentation

- **Installation Guide**: `INSTALL.md`
- **Full Documentation**: `docs/INDEX.md`
- **Performance Guide**: `docs/technical/STARTUP_PERFORMANCE.md`

## Version

Current version: **2.0.0** (Standalone)

Check version: `ff -v`

## Examples

```bash
# Analyze case
ff case show CS4SG1U1

# View available fields
ff field info CS4SG1U1

# Plot node displacement
ff plot CS4SG1U1 --node 10 --component y --output plot.png

# Compare multiple cases
ff data compare CS4SG1U1 CS4SG2U1

# Convert PLT files
ff tecplot convert riser.1000.plt --format hdf5
```

## Project Structure

```
flexflow_manager/
├── README.md              # This file
├── INSTALL.md             # Installation guide
├── install.sh             # Installation script
├── main.py                # Main program
├── __version__.py         # Version information
├── module/                # Source code
├── docs/                  # Documentation
└── releases/              # Release packages
```

## Support

- **Issues**: https://github.com/arunperiyal/flexflow_analyzer/issues
- **Repository**: https://github.com/arunperiyal/flexflow_analyzer

## License

Internal tool for simulation analysis.

---

**Quick Install**: `./install.sh`  
**Quick Start**: `ff case show CS4SG1U1`  
**Version**: 2.0.0
