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
# Install dependencies
pip install numpy matplotlib pyyaml

# Install FlexFlow CLI (creates 'flexflow' alias)
python main.py --install
```

### Basic Usage

```bash
# Preview case data
flexflow info CS4SG2U1

# Plot displacement
flexflow plot CS4SG2U1 --data-type displacement --plot-type time --node 10 --component y

# Plot force
flexflow plot CS4SG2U1 --data-type force --plot-type time --component tz

# Compare multiple cases
flexflow compare --input-file comparison.yaml

# Generate template configuration
flexflow template --type multi --output my_config.yaml
```

### Commands

FlexFlow uses a git-style command structure:

- **`info`** - Preview case data and timesteps
- **`plot`** - Create plots from a single case
- **`compare`** - Compare multiple cases using YAML config
- **`template`** - Generate YAML configuration templates

For detailed help:
```bash
flexflow --help
flexflow plot --help
flexflow plot --examples
```

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
- Customizable plot styling (colors, line styles, markers)
- Time/timestep range filtering
- Server mode for headless operation
- Pipeline-friendly output modes

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
│   ├── commands/              # Command implementations
│   │   ├── info.py           # Info command
│   │   ├── plot.py           # Plot command
│   │   ├── compare.py        # Compare command
│   │   └── template.py       # Template generation
│   ├── cli/                   # CLI interface
│   │   ├── parser.py         # Argument parser
│   │   └── help_messages.py  # Help text and examples
│   ├── installer/             # Installation management
│   │   └── install.py        # Install/uninstall utilities
│   ├── utils/                 # Utilities
│   │   ├── plot_utils.py     # Plotting functions
│   │   ├── logger.py         # Logging utility
│   │   ├── colors.py         # Terminal colors
│   │   ├── config.py         # App configuration
│   │   └── file_utils.py     # File utilities
│   └── templates/             # YAML templates
│       ├── example_single_config.yaml
│       ├── example_multi_config.yaml
│       └── example_fft_config.yaml
├── docs/
│   └── USAGE.md              # Complete usage guide
└── CS4SG*/                    # Example cases
```

## Documentation

- **[Complete Usage Guide](docs/USAGE.md)** - Comprehensive documentation with examples
- **[Quick Start](QUICKSTART.md)** - Get started quickly
- **[API Reference](#python-api)** - Python API documentation

## Examples

### Single Case Plot

```bash
flexflow plot CS4SG2U1 \
  --data-type displacement \
  --plot-type time \
  --node 10 \
  --component y \
  --plot-style "blue,2,-,o" \
  --title "Node 10 Y-Displacement" \
  --output displacement.png
```

### Multi-Case Comparison

Create `comparison.yaml`:
```yaml
data_type: displacement
plot_type: time

plot:
  title: "Multi-Case Comparison"
  ylabel: "Y Displacement (m)"

cases:
  - directory: CS4SG1U1
    label: "Case 1"
    node: 10
    component: y
    style: "blue,2,-,o"
  
  - directory: CS4SG2U1
    label: "Case 2"
    node: 10
    component: y
    style: "red,2,--,s"

output: comparison.png
```

Run:
```bash
flexflow compare --input-file comparison.yaml
```

## Python API

Use FlexFlow in your Python scripts:

```python
from module.core.case import FlexFlowCase
from module.utils.plot_utils import plot_node_displacements
import matplotlib.pyplot as plt

# Load case
case = FlexFlowCase('CS4SG2U1')
reader = case.load_othd_data()

# Get displacement data
data = reader.get_node_displacements(node_id=10)
print(f"Max Y displacement: {data['dy'].max():.6f}")

# Create plot
fig, ax = plot_node_displacements(reader, node_id=10, component='y')
plt.savefig('displacement.png')
```

For more examples, see [docs/USAGE.md](docs/USAGE.md#python-api).

## FlexFlow Case Structure

A FlexFlow case directory should contain:

```
CS4SG2U1/
├── simflow.config        # Configuration file (problem name)
├── riser.def             # Definition file (time parameters)
├── othd_files/           # Displacement output files
│   ├── riser1.othd
│   └── riser2.othd
└── oisd_files/           # Force/pressure output files
    ├── riser1.oisd
    └── riser2.oisd
```

## Requirements

- Python 3.6+
- NumPy
- Matplotlib
- PyYAML

## Installation

```bash
# Install dependencies
pip install numpy matplotlib pyyaml

# Install FlexFlow CLI globally
python main.py --install

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
