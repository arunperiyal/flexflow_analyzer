# FlexFlow OTHD/OISD Reader - Change Log

## Version 2.3.0 - Current (2026-01-05)

### New Features - Case Management
- **New Command**: Added `new` command for creating case directories from reference templates
  - Create new FlexFlow simulation cases from a reference case template
  - Automatic file copying and configuration updates
  - Support for custom problem names, processor counts, and output frequencies
  - YAML configuration support for single case or batch generation
  - Parametric substitution in .geo files (e.g., `#groove_depth`, `#groove_width`)
  - Parametric substitution in .def files (e.g., `Ur`, `Re` values)
  - Automatic SLURM job name updates in shell scripts
  - Dry-run mode for previewing changes without creating files
  - Force flag to overwrite existing directories
  - List variables feature (`--list-vars`) to see available parameters
  - Command-line flags: `--ref-case`, `--problem-name`, `--np`, `--freq`, `--from-config`, `--force`, `--dry-run`, `--list-vars`

### Documentation
- Updated README.md with 'new' command in commands list and examples
- Updated docs/USAGE.md with 'new' command in available commands
- Added comprehensive documentation in docs/usage/commands/new.md
- Added help messages and examples for 'new' command

## Version 2.2.0 - (2025-12-19)

### New Features - Compare Command
- **Separate Plots Mode**: Create individual plot files for each case
  - New flag: `--separate` to enable separate plots mode
  - New flag: `--output-prefix` to set filename prefix (default: "case_")
  - New flag: `--output-format` to specify format: png, pdf, svg (default: png)
  - YAML support: `separate: true`, `output_prefix`, `output_format` fields
  - Overrides `--subplot` flag when enabled
  - Generates files as: `{prefix}{case_basename}.{format}`
  
- **Enhanced Time Range Support**: Proper handling of FlexFlow time step IDs (tsId)
  - Time step IDs (tsId) start from 1, not 0
  - `start_step`/`end_step` interpret values as tsId (1-based)
  - Time calculation: `time = step_id × dt`
  - Both plot and compare commands now support step ID and time value specifications
  - Consistent filtering across all commands using `filter_data_by_time_range`

### Improvements
- **Plot Command**: 
  - Fixed YAML configuration support for `case_dir` (was only checking `case`)
  - Proper extraction of `plot_properties` section from YAML
  - Time range filtering now works correctly with both step IDs and time values
  
- **Template System**:
  - Updated all templates with correct step ID documentation
  - Added comprehensive comments explaining tsId vs array indexing
  - Examples showing both step ID and time value approaches
  - Updated `example_multi_config.yaml` with separate plots documentation

### Bug Fixes
- Fixed step index interpretation (was using 0-based array indices instead of 1-based tsId)
- Corrected time range filtering in compare command
- Fixed YAML configuration parsing for nested plot_properties

### Documentation
- Updated `docs/usage/commands/compare.md` with separate plots mode
- Added output modes comparison table
- Enhanced YAML configuration examples
- Documented time range specification methods (step IDs vs time values)
- Added tips for batch processing and publication-quality outputs

### Technical Changes
- New function: `execute_separate_plots()` for command-line separate mode
- New function: `execute_separate_plots_from_yaml()` for YAML separate mode
- Refactored time range handling to use step IDs (tsId) consistently
- Updated help messages with new flags and examples

## Version 2.1.0 - (2025-12-19)

### New Features
- **Shell Autocompletion**: Comprehensive tab completion support for bash, zsh, and fish shells
  - Command completion (info, plot, compare, etc.)
  - Option/flag completion (--data-type, --plot-type, etc.)
  - Value completion (displacement, force, x, y, z, etc.)
  - Dynamic case directory completion
  - Context-aware suggestions
  - File path completion for --output and --input-file

### Installation Improvements
- Autocompletion automatically installed during setup
- Detection of current shell and automatic configuration
- Manual completion script generation: `flexflow --completion <shell>`
- Completion scripts uninstalled with `flexflow --uninstall`

### Documentation
- Added comprehensive autocompletion guide: `docs/AUTOCOMPLETION.md`
- Added quick start guide: `COMPLETION_QUICKSTART.md`
- Updated README with autocompletion section
- Enhanced help messages with TAB completion hints

### Technical Changes
- New module: `module/cli/completion.py` for completion script generation
- Support for bash-completion, zsh compdef, and fish completion systems
- Integration with installer for automatic setup
- Shell detection utilities

## Version 2.0.0 - (2025-12-18)

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
