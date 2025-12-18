# FlexFlow OTHD/OISD Reader - Change Log

## Version 2.0.0 - Current (2025-12-18)

### Major Refactoring
- Complete code reorganization into modular structure
- Git-style CLI with subcommands (info, plot, compare, template)
- YAML configuration file support for batch plotting
- Template generation for easy configuration

### New Directory Structure
```
flexflow/
├── cli/                    # Command-line interface
│   ├── parser.py          # Argument parsing
│   └── help_messages.py   # Colored help text
├── commands/              # Command implementations
│   ├── info.py           # Case information
│   ├── plot.py           # Plotting functionality
│   ├── compare.py        # Multi-case comparison
│   └── template.py       # YAML template generation
├── core/                  # Core functionality
│   ├── case.py           # FlexFlowCase class
│   ├── readers/          # Data readers
│   │   ├── othd_reader.py
│   │   └── oisd_reader.py
│   └── parsers/          # File parsers
│       └── def_parser.py
├── utils/                 # Utilities
│   ├── colors.py         # Terminal colors
│   ├── config.py         # App configuration
│   ├── logger.py         # Logging utility
│   └── plot_utils.py     # Plotting utilities
└── templates/            # YAML templates
    ├── example_single_config.yaml
    ├── example_multi_config.yaml
    └── example_fft_config.yaml
```

### New Features

#### CLI Enhancements
- **Subcommands**: `info`, `plot`, `compare`, `template`
- **Installation**: `--install`, `--uninstall`, `--update` flags
- **Colored Help**: Beautiful, readable help messages
- **Examples Flag**: `--examples` shows usage examples for each command

#### Plotting Features
- Multiple plot types: `time`, `fft`, `traj2d`, `traj3d`
- Component selection: `--component x y z`
- Plot styling: `--plot-style color,width,linestyle,marker`
- Plot properties: `--title`, `--xlabel`, `--ylabel`, `--fontsize`, `--fontname`
- Server mode: `--output` for saving without display
- Time range: `--start-time`, `--end-time`, `--start-step`, `--end-step`

#### YAML Configuration
- Batch plotting with YAML files
- Template generation: `flexflow template <type>`
- Multi-case comparison support
- Reusable configurations

#### Data Preview
- `--preview` flag for quick data inspection
- Shows first 20 timesteps by default
- Respects time range flags

### Removed Files
- Cleaned up old development files
- Removed redundant scripts and utilities
- Consolidated documentation

## Version 1.0.0 - (Previous)

### New Features

#### 1. Problem Name from simflow.config
- `FlexFlowCase` now reads the `problem` field from `simflow.config`
- Uses problem name to find the correct `.def` file: `<problem>.def`
- Example: If `problem = riser` in simflow.config, looks for `riser.def`

#### 2. OISD File Support
- Added new `OISDReader` class for reading OISD (Output Integrated Surface Data) files
- Reads total traction data under `totTrac` lines
- Reads total moment data under `totMoment` lines
- Reads average pressure under `avePres` lines
- Reads total surface area under `totArea` lines

#### 3. Enhanced Case Validation
- Validates presence of `simflow.config` (required)
- Checks for `othd_files/` directory (warns if missing)
- Checks for `oisd_files/` directory (warns if missing)
- More flexible validation for different case configurations

#### 4. FlexFlowCase Enhancements
- `problem_name` property to access problem name
- `find_oisd_files()` method to discover OISD files
- `load_oisd_data()` method to load OISD data
- `get_total_traction()` method for traction data
- `get_total_moment()` method for moment data
- `get_average_pressure()` method for pressure data
- `oisd_reader` property for lazy loading

### File Structure

```
flexflow/
├── __init__.py              # Package exports
├── flexflow_case.py         # FlexFlowCase class (11K) - UPDATED
├── othd_reader.py           # OTHDReader class (6.3K)
├── oisd_reader.py           # OISDReader class (9.1K) - NEW
├── def_parser.py            # .def parsing (3.2K) - UPDATED
├── plot_utils.py            # Plotting utilities (3.6K)
├── main.py                  # CLI interface (4.4K)
├── README.md                # Documentation (6.7K)
├── QUICKSTART.md            # Quick start guide (5.2K)
├── CHANGELOG.md             # This file
└── plot_othd_displacements.py  # Original monolithic (18K)
```

### Usage Examples

#### Using Problem Name
```python
from flexflow_case import FlexFlowCase

case = FlexFlowCase('CS4SG2U1')
print(case.problem_name)  # 'riser'
# Automatically finds riser.def
```

#### Reading OISD Data
```python
from flexflow_case import FlexFlowCase

case = FlexFlowCase('CS4SG2U1')

# Load OISD data
oisd_reader = case.load_oisd_data()

# Get total traction
traction = case.get_total_traction()
times = traction['times']
ty = traction['ty']
tz = traction['tz']
magnitude = traction['magnitude']

# Get total moment
moment = case.get_total_moment()

# Get average pressure
pressure = case.get_average_pressure()
```

#### Both OTHD and OISD
```python
from flexflow_case import FlexFlowCase
import matplotlib.pyplot as plt

case = FlexFlowCase('CS4SG2U1')

# Load both types of data
othd_reader = case.load_othd_data()
oisd_reader = case.load_oisd_data()

# Plot displacement and traction together
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

# Node displacement
node_data = case.get_node_displacements(10)
ax1.plot(node_data['times'], node_data['dy'])
ax1.set_ylabel('Displacement (m)')

# Total traction
traction = case.get_total_traction()
ax2.plot(traction['times'], traction['ty'])
ax2.set_ylabel('Traction (N)')
ax2.set_xlabel('Time (s)')

plt.tight_layout()
plt.savefig('combined.png')
```

### API Changes

#### FlexFlowCase
- **New property**: `problem_name` - Name of the problem from simflow.config
- **New property**: `oisd_dir` - Path to oisd_files directory
- **New property**: `oisd_reader` - Lazy-loaded OISD reader
- **New method**: `find_oisd_files()` - Find OISD files in case
- **New method**: `load_oisd_data()` - Load OISD files
- **New method**: `get_total_traction()` - Get traction data
- **New method**: `get_total_moment()` - Get moment data
- **New method**: `get_average_pressure()` - Get pressure data

#### def_parser
- **Updated**: `find_def_file()` - Now accepts `problem_name` parameter
- **Updated**: `parse_def_file()` - Now accepts `problem_name` parameter

#### OISDReader (New Class)
- `__init__(filenames, tsId_filter=None)` - Initialize reader
- `recalculate_times(time_increment)` - Recalculate time vector
- `get_total_traction()` - Get traction time history
- `get_total_moment()` - Get moment time history
- `get_average_pressure()` - Get pressure time history
- `get_total_area()` - Get surface area time history

### Backward Compatibility

All existing code remains compatible. The changes are additive:
- Existing OTHD functionality unchanged
- New OISD functionality is optional
- Case validation is more flexible (warns instead of errors for missing dirs)

### Testing

All features tested with CS4SG2U1 case:
- ✅ Problem name detection (riser)
- ✅ .def file finding (riser.def)
- ✅ OTHD data loading (6 files, 4322 timesteps)
- ✅ OISD data loading (6 files, 4322 timesteps)
- ✅ Node displacements
- ✅ Total traction
- ✅ Total moment
- ✅ Average pressure

### Future Enhancements (Potential)

- [ ] Additional OISD data fields (totMassFlux, totMomFlux, etc.)
- [ ] Plotting utilities for traction/moment data
- [ ] CLI support for OISD plotting
- [ ] Multiple surface groups handling
- [ ] Export to common formats (CSV, HDF5, etc.)
