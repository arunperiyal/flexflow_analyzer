# FlexFlow Post-Processing Toolkit

A powerful Python toolkit for reading, analyzing, and visualizing FlexFlow simulation output files (OTHD and OISD).

## Overview

FlexFlow is a command-line tool and Python library for post-processing FlexFlow CFD simulation results. It provides:

- **Displacement Analysis** (OTHD files): Node displacements, trajectories, frequency analysis
- **Force/Pressure Analysis** (OISD files): Forces, moments, and pressure distributions
- **Multi-Case Comparison**: Compare multiple simulation cases on a single plot
- **Flexible Plotting**: Time-domain, FFT, 2D/3D trajectories
- **Server-Friendly**: Headless operation for remote HPC clusters
- **YAML Configuration**: Complex plots defined in configuration files

## Quick Start

### Installation

```bash
# Install FlexFlow CLI (creates 'flexflow' alias and installs dependencies)
python main.py --install
```

This will:
- Install Python dependencies (numpy, matplotlib, pyyaml, markdown)
- Create 'flexflow' command alias
- Set up shell autocompletion (bash/zsh/fish)
- Optionally install Microsoft fonts for publication-quality plots
- Convert and install HTML documentation
- Configure your shell environment

### Basic Usage

```bash
# Get case information
flexflow info CS4SG2U1

# Plot displacement
flexflow plot CS4SG2U1 --data-type displacement --plot-type time --node 10 --component y

# Compare multiple cases
flexflow compare CS4SG1U1 CS4SG2U1 --node 10 --data-type displacement --component y

# View documentation
flexflow docs
```

### Commands

- **`info`** - Display case information
- **`preview`** - Preview displacement data in table format
- **`statistics`** - Show statistical analysis of data
- **`plot`** - Create plots from a single case
- **`compare`** - Compare multiple cases on a single plot
- **`template`** - Generate YAML configuration templates
- **`tecplot`** - Inspect and work with Tecplot PLT binary files
- **`docs`** - View documentation

For detailed help on any command:
```bash
flexflow <command> --help
flexflow <command> --examples
```

## Shell Autocompletion

FlexFlow includes powerful tab completion for bash, zsh, and fish shells:

```bash
# Press TAB to see available commands
flexflow <TAB>

# Press TAB to complete options
flexflow plot --<TAB>

# Complete data types, components, and more
flexflow plot CS4SG1U1 --data-type <TAB>
```

See [Autocompletion Guide](docs/AUTOCOMPLETION.md) for detailed setup and usage.

## Features

### Data Types
- **Displacement** (OTHD): Node displacements (dx, dy, dz, magnitude)
- **Force** (OISD): Total traction forces (tx, ty, tz)
- **Moment** (OISD): Moment components
- **Pressure** (OISD): Pressure distributions

### Plot Types
- **Time-domain**: Data vs time or timestep index
- **FFT**: Frequency domain analysis
- **2D Trajectory**: Plot two components against each other
- **3D Trajectory**: 3D visualization of motion

### Key Features
- Automatic handling of FlexFlow case directory structure
- Smart merging of multiple OTHD/OISD output files
- Restart simulation handling (overlapping time ranges)
- Time calculation from .def file parameters
- Advanced plot styling (colors, line styles, markers, fonts)
- LaTeX rendering support for labels and titles
- Custom legend positioning and styling
- Time range filtering for focused analysis
- Automatic headless mode for SSH/remote systems
- Publication-quality output (PDF, SVG, PNG)
- Built-in documentation viewer

## Project Structure

```
flexflow/
├── main.py                    # CLI entry point
├── module/                    # Main package
│   ├── core/                  # Core functionality
│   │   ├── case.py           # FlexFlow case management
│   │   ├── readers/          # File readers
│   │   │   ├── othd_reader.py   # OTHD displacement reader
│   │   │   └── oisd_reader.py   # OISD force/pressure reader
│   │   └── parsers/          # Configuration parsers
│   │       └── def_parser.py    # .def file parser
│   ├── commands/              # Command implementations (restructured)
│   │   ├── info_cmd/         # Info command
│   │   ├── preview_cmd/      # Preview command
│   │   ├── statistics_cmd/   # Statistics command
│   │   ├── plot_cmd/         # Plot command
│   │   ├── compare_cmd/      # Compare command
│   │   ├── template_cmd/     # Template generation
│   │   └── docs_cmd/         # Documentation viewer
│   ├── cli/                   # CLI interface
│   │   ├── parser.py         # Argument parser
│   │   └── help_messages/    # Help messages per command
│   ├── installer/             # Installation management
│   │   └── install.py        # Install/uninstall/update utilities
│   ├── utils/                 # Utilities
│   │   ├── plot_utils.py     # Plotting functions
│   │   ├── data_utils.py     # Data manipulation utilities
│   │   ├── logger.py         # Logging utility
│   │   ├── colors.py         # Terminal colors
│   │   ├── config.py         # App configuration
│   │   └── file_utils.py     # File utilities
│   └── templates/             # YAML templates
│       ├── example_single_config.yaml
│       ├── example_multi_config.yaml
│       └── example_fft_config.yaml
├── docs/                      # Documentation
│   ├── USAGE.md              # Complete usage guide
│   └── usage/                # Per-command documentation
│       ├── cli/              # CLI documentation
│       ├── commands/         # Command-specific docs
│       ├── core/             # Core functionality docs
│       └── utils/            # Utility documentation
└── CS4SG*/                    # Example cases
```

## Documentation

For comprehensive documentation with examples:
```bash
flexflow docs
```

Or view the documentation files:
- **[Complete Usage Guide](docs/USAGE.md)** - Detailed documentation with examples
- Command-specific documentation in `docs/usage/commands/`

## FlexFlow Case Structure

A FlexFlow case directory should contain:

```
CS4SG2U1/
├── simflow.config        # Configuration file (problem name)
├── riser.def             # Definition file (time parameters)
├── othd_files/           # Displacement output files
│   ├── riser1.othd
│   └── riser2.othd
├── oisd_files/           # Force/pressure output files
│   ├── riser1.oisd
│   └── riser2.oisd
└── binary/               # Tecplot binary files (optional)
    ├── riser.100.plt
    ├── riser.200.plt
    └── riser.300.plt
```

## Requirements

- Python 3.6+
- NumPy
- Matplotlib  
- PyYAML
- Markdown (for documentation conversion)

## Installation

```bash
# Install FlexFlow CLI globally (installs dependencies automatically)
python main.py --install

# During installation, you'll be prompted to:
# - Install Python dependencies (numpy, matplotlib, pyyaml, markdown)
# - Install Microsoft fonts (optional, for Times New Roman, Arial, etc.)
# - The tool will create 'flexflow' command alias in your shell

# Update installation
flexflow --update

# Uninstall
flexflow --uninstall
```

## Contributing

This tool is developed for FlexFlow post-processing. Contributions and suggestions are welcome.

## License

This project is provided as-is for use with FlexFlow simulations.

## See Also

- [Complete Usage Guide](docs/USAGE.md)
- [Quick Start Guide](QUICKSTART.md)
- Example YAML configurations in the repository root
