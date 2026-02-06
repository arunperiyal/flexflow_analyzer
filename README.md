# FlexFlow Manager

Fast and efficient tool for analyzing FlexFlow simulation data with PyTecplot integration.

## What is FlexFlow?

FlexFlow Manager is a command-line tool designed for analyzing offshore riser simulation data. It provides:
- Fast data inspection and visualization for OTHD/OISD files
- Tecplot PLT file integration via PyTecplot
- SLURM job submission and monitoring for simulations
- Case management and comparison tools

## Quick Start

```bash
# 1. Install (creates conda environment and ff command)
./install.sh

# 2. Reload shell
source ~/.bashrc

# 3. Start FlexFlow Interactive Shell
ff

# Now in interactive mode:
flexflow → case show CS4SG1U1       # Show case information
flexflow → check riser.othd          # Inspect data files
flexflow → plot CS4SG1U1 --node 10   # Create plots
flexflow → exit                      # Exit shell
```

## Key Features

- **Interactive Shell**: Always-on REPL mode - no startup overhead between commands
- **Instant Execution**: Commands run immediately without Python reload
- **Smart Completion**: Tab completion for commands, subcommands, and options
- **Command History**: Persistent history across sessions with arrow key navigation
- **Domain Commands**: Intuitive structure - `case`, `field`, `data`, `check`, `plot`
- **SLURM Integration**: Submit and monitor simulation jobs
- **Template System**: Quick case creation from templates

## Requirements

- Linux (tested on Ubuntu 20.04+)
- Anaconda or Miniconda
- Tecplot 360 EX (for PLT file operations)

## Documentation

- **[Installation Guide](INSTALL.md)** - Setup and configuration
- **[Usage Guide](docs/USAGE.md)** - Commands, examples, and workflows
- **[Documentation Index](docs/INDEX.md)** - Complete documentation reference

## Common Commands

```bash
# Case management
ff case show <case>          # Display case information
ff case create <name>        # Create new case from template
ff case run <case>           # Submit SLURM jobs

# Data inspection
ff check <file>              # Inspect OTHD/OISD files
ff data show <case>          # Preview time-series data

# Field operations
ff field info <case>         # Show PLT file information

# Visualization
ff plot <case> [options]     # Create plots
ff compare <case1> <case2>   # Compare cases
```

Run `ff --help` or `ff <command> --help` for detailed options.

## Version

Current version: **2.0.0**

Check version: `ff -v`

## Support

- **Issues**: https://github.com/arunperiyal/flexflow_analyzer/issues
- **Repository**: https://github.com/arunperiyal/flexflow_analyzer

## License

Internal tool for simulation analysis.
