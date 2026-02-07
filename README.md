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
- **Data Analysis** - Inspect OTHD/OISD files and PLT files via PyTecplot
- **Case Management** - Create, organize, and manage simulation cases
- **SLURM Integration** - Submit and monitor simulation jobs
- **Visualization** - Generate time-series plots and comparisons

## Requirements

- Linux (Ubuntu 20.04+)
- Anaconda/Miniconda
- Tecplot 360 EX (for PLT operations)

## Documentation

- [Installation Guide](docs/INSTALL.md)
- [Usage Guide](docs/USAGE.md)
- [Command Reference](docs/REFERENCE.md)
- [Changelog](CHANGELOG.md)

## Main Commands

```bash
# Case operations
case show <case>           # Show case info
case create <name>         # Create new case
case run <case>            # Submit jobs
case organise <case>       # Clean up case files

# Data inspection
check <file>               # Inspect OTHD/OISD files
data show <case>           # Preview data
field info <case>          # Show PLT info

# Visualization
plot <case> [options]      # Create plots
compare <case1> <case2>    # Compare cases
```

Run `ff --help` for all commands.

## Version

Current: **2.0.0** | Check: `ff -v`

## Links

- [Repository](https://github.com/arunperiyal/flexflow_analyzer)
- [Issues](https://github.com/arunperiyal/flexflow_analyzer/issues)
