# FlexFlow Documentation Index

Complete documentation for FlexFlow Manager - a tool for analyzing offshore riser simulation data.

## Documentation Structure

### Getting Started
- **[README.md](../README.md)** - Project overview and quick start
- **[INSTALL.md](../INSTALL.md)** - Complete installation guide
- **[USAGE.md](USAGE.md)** - Comprehensive usage guide with examples

### Setup Guides
- [setup/INSTALL_INTERACTIVE.md](setup/INSTALL_INTERACTIVE.md) - Interactive installation details
- [INSTALL_QUICKREF.md](../INSTALL_QUICKREF.md) - Installation quick reference

### Technical Documentation
- [technical/STARTUP_PERFORMANCE.md](technical/STARTUP_PERFORMANCE.md) - Performance optimization
- [technical/STANDALONE_BUILD.md](technical/STANDALONE_BUILD.md) - Building standalone executables

## Quick Navigation

### For New Users

**First time using FlexFlow?** Start here:

1. **Installation:** [INSTALL.md](../INSTALL.md)
2. **Quick start:** [README.md](../README.md#quick-start)
3. **Basic usage:** [USAGE.md](USAGE.md#getting-started)
4. **Examples:** Run `ff --examples`

### For Regular Users

**Looking for command help?**

- **Command reference:** [USAGE.md](USAGE.md#command-structure)
- **Case management:** [USAGE.md](USAGE.md#case-management)
- **Data inspection:** [USAGE.md](USAGE.md#data-inspection)
- **Plotting:** [USAGE.md](USAGE.md#visualization)

### For Developers

**Working on FlexFlow?**

- **Performance guide:** [technical/STARTUP_PERFORMANCE.md](technical/STARTUP_PERFORMANCE.md)
- **Build guide:** [technical/STANDALONE_BUILD.md](technical/STANDALONE_BUILD.md)
- **Installation internals:** [setup/INSTALL_INTERACTIVE.md](setup/INSTALL_INTERACTIVE.md)

## Command Quick Reference

### Domain Commands

```bash
# Case Management
ff case show <case>          # Display case information
ff case create <name>        # Create new case from template
ff case run <case>           # Submit and monitor SLURM jobs

# Data Operations
ff data show <case>          # Preview time-series data
ff data stats <case>         # Calculate statistics

# Field Operations (PLT files)
ff field info <case>         # Show PLT file information
ff field extract <case>      # Extract field data to CSV

# Templates
ff template plot             # Generate plot configuration
ff template case             # Generate case configuration
```

### File Inspection

```bash
ff check <file>              # Inspect OTHD/OISD files
```

### Visualization

```bash
ff plot <case> [options]     # Create time-series plots
ff compare <case1> <case2>   # Compare multiple cases
```

### Utilities

```bash
ff --help                    # Show help
ff --version                 # Show version
ff --examples                # Show comprehensive examples
ff --completion <shell>      # Generate shell completion
```

## Common Tasks

### Installation

```bash
# Quick install
./install.sh

# Verify installation
source ~/.bashrc
ff --version
```

See [INSTALL.md](../INSTALL.md) for detailed installation options.

### Analyzing a Case

```bash
# Show case information
ff case show CS4SG1U1

# Inspect data files
ff check CS4SG1U1/output/riser.othd

# Preview data
ff data show CS4SG1U1 --node 24 --limit 10

# Create plot
ff plot CS4SG1U1 --node 10 --component y
```

See [USAGE.md](USAGE.md#case-management) for detailed workflow.

### Running Simulations

```bash
# Create new case
ff case create MY_SIMULATION

# Submit jobs
ff case run MY_SIMULATION

# Monitor progress
# (automatic, press Ctrl+C to stop monitoring)
```

See [USAGE.md](USAGE.md#run-simulations) for job management options.

### Creating Visualizations

```bash
# Single case plot
ff plot CS4SG1U1 --node 10 --component y --output plot.png

# Compare cases
ff compare CS4SG1U1 CS4SG2U1 --node 10 --output comparison.png

# Multiple nodes
ff plot CS4SG1U1 --nodes 10 20 30 --component y
```

See [USAGE.md](USAGE.md#visualization) for advanced plotting.

## Troubleshooting

### Installation Issues

- **Conda not found:** [INSTALL.md](../INSTALL.md#conda-not-found)
- **Command not found:** [INSTALL.md](../INSTALL.md#command-not-found-after-installation)
- **Import errors:** [INSTALL.md](../INSTALL.md#import-errors)
- **Permission denied:** [INSTALL.md](../INSTALL.md#permission-denied)

### Usage Issues

- **Command help:** [USAGE.md](USAGE.md#troubleshooting)
- **Performance tips:** [technical/STARTUP_PERFORMANCE.md](technical/STARTUP_PERFORMANCE.md)

### Getting Help

```bash
# Command-specific help
ff <command> --help
ff <command> <subcommand> --help

# Examples
ff --examples

# Documentation
ff docs
```

## Features by Category

### Case Management
- Create cases from templates
- Submit SLURM jobs
- Monitor job progress
- Display case information

### Data Analysis
- Inspect OTHD/OISD files
- Preview time-series data
- Calculate statistics
- Export to CSV

### Tecplot Integration
- Read PLT files via PyTecplot
- Extract field data
- Convert file formats
- Fast binary operations

### Visualization
- Time-series plots
- Multi-case comparison
- Component selection
- Custom styling

### Developer Tools
- Fast startup (0.4s)
- Tab completion
- Configuration templates
- Scripting support

## Version Information

**Current Version:** 2.0.0

**Check version:**
```bash
ff --version
```

**Release notes:** See [GitHub releases](https://github.com/arunperiyal/flexflow_analyzer/releases)

## Support

### Documentation
- **This index:** Overview and navigation
- **[USAGE.md](USAGE.md):** Detailed command reference
- **[INSTALL.md](../INSTALL.md):** Installation guide

### Community
- **Issues:** https://github.com/arunperiyal/flexflow_analyzer/issues
- **Repository:** https://github.com/arunperiyal/flexflow_analyzer

### Quick Help

```bash
# Built-in help
ff --help

# Command help
ff case --help

# Examples
ff --examples

# View this documentation
ff docs
```

## Contributing

FlexFlow is an internal tool. For feature requests or bug reports:

1. Check existing issues
2. Create detailed issue report
3. Include version, OS, and error messages
4. Provide minimal reproduction steps

## License

Internal tool for simulation analysis.

---

**Quick Links:**
- [Installation Guide](../INSTALL.md)
- [Usage Guide](USAGE.md)
- [README](../README.md)
- [GitHub](https://github.com/arunperiyal/flexflow_analyzer)
