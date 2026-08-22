# FlexFlow Manager

Fast command-line tool for analyzing offshore riser simulation data.

## Quick Start

```bash
# Install
./install.sh

# Start interactive shell
ff

# Example commands
flexflow → case show CS4SG1U1
flexflow → check riser.othd
flexflow → plot CS4SG1U1 --node 10
```

## Features

- **Interactive Shell** - REPL mode with tab completion and command history
- **Command Chaining** - Chain multiple commands with semicolon (e.g., `use case:C1; data show`)
- **Unix Piping** - Pipe commands with `|` operator (e.g., `case show | grep status | head -10`)
- **Context** - Set a case, node, timestep range, variables or zone once with `use`
  and every command picks them up
- **Data Analysis** - Inspect OTHD/OISD files and PLT volume/surface data
- **PLT without Tecplot** - Binary PLT files are read by a pure-numpy parser, so no
  Tecplot license is needed and Python 3.13+ works
- **Case Management** - Create, organize, and manage simulation cases with time parameters
- **Remote Transfers** - Configure remote machines and upload/download case data over SFTP
- **SLURM Integration** - Submit and monitor simulation jobs
- **Visualization** - Time-series plots, comparisons, and VTK/ParaView output

## Requirements

- Linux (Ubuntu 20.04+)
- Anaconda/Miniconda (Python 3.12+)
- ParaView (optional — for viewing the `.vtu`/`.pvd` files `field` writes)

## Documentation

- [Installation Guide](docs/INSTALL.md)
- [Usage Guide](docs/USAGE.md)
- [Command Reference](docs/REFERENCE.md)
- [Case Creation with Time Parameters](CASE_CREATE_TIME_PARAMETERS.md)
- [Changelog](CHANGELOG.md)

## Main Commands

```bash
# Case operations
case show <case>           # Show case info
case create <name>         # Create new case
case run <case>            # Submit jobs
case organise <case>       # Clean up case files
case out <case> --map      # Write othd maps (row → node/point coordinates)
case out <case> --list     # Table of the case's outputTimeHistory blocks
case domain <case> --init  # Declare the field and bodies, in domain.yml
case domain body --list    # What the domain is made of
case upload <case> --to R  # Send case data/files to a remote
case download <case> --from R

# Data inspection
check <file>               # Inspect OTHD/OISD files
data show <case>           # Preview data
field info <case>          # Show PLT info (zones, variables, mesh audit)

# Field data (PLT)
field extract <case> --variables U,V,W --zone FIELD --output out.csv
field extract <case> --probe 1,2,3    # Sample a point over time
field compute force <case> --zone cyl # Per-element force -> <case>/cyl.forces/
field compute force_coeff <case> --zone cyl --sectional 48   # Cd/Cl, per section
field convert <case> --output mesh.vtu
field check <file>         # Validate a produced .vtu/.pvd
field render iso <case>    # Isosurface PNGs
field render slice <case> --normal z   # Cut-plane PNGs (or .vtp/.csv)

# Remotes
remote add <name> --user U --ip IP --password P --path /base
remote list

# Visualization
plot <case> [options]      # Create plots
compare <case1> <case2>    # Compare cases
```

Run `ff --help` for all commands, or `<command> --help` for one.

## Version

Current: **2.0.0** | Check: `ff -v`

## Links

- [Repository](https://github.com/arunperiyal/flexflow_analyzer)
- [Issues](https://github.com/arunperiyal/flexflow_analyzer/issues)
