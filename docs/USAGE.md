# FlexFlow Usage Guide

Complete guide for using FlexFlow CLI tool for post-processing FlexFlow simulation data.

## Detailed Command Documentation

For detailed documentation on each command, see:
- [info command](./usage/info/README.md) - Display case information
- [plot command](./usage/plot/README.md) - Create plots from single cases
- [compare command](./usage/compare/README.md) - Compare multiple cases
- [template command](./usage/template/README.md) - Generate YAML templates

## Table of Contents

1. [Installation](#installation)
2. [Quick Start](#quick-start)
3. [Command Reference](#command-reference)
4. [YAML Configuration](#yaml-configuration)
5. [Examples](#examples)
6. [Python API](#python-api)

---

## Installation

### Install FlexFlow CLI

```bash
python main.py --install
```

This will:
- Create a `flexflow` alias in your shell configuration
- Make the tool accessible from anywhere using `flexflow` command
- Optionally install Microsoft fonts (Times New Roman, Arial, etc.)
- Source your shell configuration automatically

**Note:** During installation, you'll be prompted to install Microsoft fonts. This is optional but recommended for academic publications.

### Verify Installation

```bash
flexflow --version
```

### Update FlexFlow CLI

```bash
flexflow --update
```

### Uninstall FlexFlow CLI

```bash
flexflow --uninstall
```

---

## Quick Start

### 1. Preview Case Data

View timestep information without plotting:

```bash
flexflow info CS4SG2U1
```

Preview specific time range:

```bash
flexflow info CS4SG2U1 --start-time 10.0 --end-time 50.0
```

### 2. Plot Single Case

Plot displacement vs time:

```bash
flexflow plot CS4SG2U1 --data-type displacement --plot-type time --node 10 --component y
```

Plot force vs time:

```bash
flexflow plot CS4SG2U1 --data-type force --plot-type time --component tz
```

### 3. Compare Multiple Cases

Create a YAML configuration file and run:

```bash
flexflow compare comparison.yaml
```

### 4. Generate Template

Create a template YAML configuration:

```bash
flexflow template --type single --output my_config.yaml
```

---

## Command Reference

### Main Commands

FlexFlow CLI uses a git-style command structure:

```
flexflow <command> [options]
```

Available commands:
- `info` - Display case information and preview timesteps
- `plot` - Plot data from a single case
- `compare` - Compare multiple cases on one plot
- `template` - Generate template YAML configuration files

### Global Options

```
--install           Install FlexFlow CLI (create alias in shell)
--uninstall         Uninstall FlexFlow CLI (remove alias)
--update            Update FlexFlow CLI installation
--version           Show version information
-h, --help          Show help message
```

---

## `info` Command

Display case information and preview timestep data.

### Usage

```bash
flexflow info <case_directory> [options]
```

### Options

```
<case_directory>    Path to FlexFlow case directory (required)
--start-time FLOAT  Filter from this time value
--end-time FLOAT    Filter to this time value
--start-step INT    Filter from this timestep index
--end-step INT      Filter to this timestep index
-v, --verbose       Show detailed information
--examples          Show usage examples
-h, --help          Show help message
```

### Examples

Preview first 20 timesteps:
```bash
flexflow info CS4SG2U1
```

Preview specific time range:
```bash
flexflow info CS4SG2U1 --start-time 10.0 --end-time 50.0
```

Preview with verbose output:
```bash
flexflow info CS4SG2U1 -v
```

---

## `plot` Command

Create plots from a single FlexFlow case.

### Usage

```bash
flexflow plot <case_directory> [options]
```

### Options

#### Required Options

```
<case_directory>    Path to FlexFlow case directory (required)
--data-type TYPE    Type of data: displacement, force, moment, pressure
--plot-type TYPE    Type of plot: time, fft, traj2d, traj3d
```

#### Data Selection Options

```
--node INT          Node ID for displacement data
--component STR     Component(s) to plot: x, y, z, magnitude, all
                    (for traj2d: two components; for traj3d: three components)
```

#### Plot Customization Options

```
--plot-style STR    Plot style as "color,width,linestyle,marker"
                    Examples: "blue,2,-,o" or "red,1.5,--,^"
--title STR         Plot title
--xlabel STR        X-axis label
--ylabel STR        Y-axis label
--legend STR        Legend label
--fontsize INT      Font size for labels and title
--fontname STR      Font family name
```

#### Time/Step Filtering Options

```
--start-time FLOAT  Filter from this time value
--end-time FLOAT    Filter to this time value
--start-step INT    Filter from this timestep index
--end-step INT      Filter to this timestep index
--use-index         Use timestep index instead of time for x-axis
--no-def-time       Don't use time increment from .def file
```

#### Output Options

```
-o, --output FILE   Output filename (default: auto-generated)
--no-display        Don't display plot (save only, for servers)
-v, --verbose       Show detailed information
-q, --quiet         Minimal output (for scripts/pipelines)
```

#### Alternative Input

```
--input-file FILE   Read plot configuration from YAML file
                    (overrides all other options)
```

### Plot Types

#### 1. Time Domain Plot (`--plot-type time`)

Plot data vs time or timestep index.

**Examples:**

Displacement vs time:
```bash
flexflow plot CS4SG2U1 --data-type displacement --plot-type time --node 10 --component y
```

Force vs time:
```bash
flexflow plot CS4SG2U1 --data-type force --plot-type time --component tz
```

All components:
```bash
flexflow plot CS4SG2U1 --data-type displacement --plot-type time --node 10 --component all
```

#### 2. FFT Plot (`--plot-type fft`)

Frequency domain analysis.

**Examples:**

```bash
flexflow plot CS4SG2U1 --data-type displacement --plot-type fft --node 10 --component y
```

#### 3. 2D Trajectory (`--plot-type traj2d`)

Plot two components against each other.

**Examples:**

X-Y trajectory:
```bash
flexflow plot CS4SG2U1 --data-type displacement --plot-type traj2d --node 10 --component x y
```

#### 4. 3D Trajectory (`--plot-type traj3d`)

Plot three components in 3D space.

**Examples:**

X-Y-Z trajectory:
```bash
flexflow plot CS4SG2U1 --data-type displacement --plot-type traj3d --node 10 --component x y z
```

### Plot Styling

Customize plot appearance with `--plot-style`:

Format: `"color,width,linestyle,marker"`

**Color options:**
- Named colors: `red`, `blue`, `green`, `orange`, `purple`, etc.
- Hex colors: `#FF5733`
- RGB tuples: `(0.5, 0.3, 0.8)`

**Line width:** Any positive number (e.g., `1`, `1.5`, `2`)

**Line styles:**
- `-` : solid line
- `--` : dashed line
- `-.` : dash-dot line
- `:` : dotted line

**Markers:**
- `o` : circle
- `s` : square
- `^` : triangle up
- `v` : triangle down
- `*` : star
- `+` : plus
- `x` : x mark
- `None` : no marker

**Examples:**

```bash
# Blue solid line with circles, width 2
flexflow plot CS4SG2U1 --data-type displacement --plot-type time --node 10 --component y \
  --plot-style "blue,2,-,o"

# Red dashed line, no markers, width 1.5
flexflow plot CS4SG2U1 --data-type force --plot-type time --component tz \
  --plot-style "red,1.5,--,None"

# Custom color, dash-dot line with squares
flexflow plot CS4SG2U1 --data-type displacement --plot-type time --node 10 --component y \
  --plot-style "#FF5733,2,-.,s"
```

### Server Mode (Headless)

For remote servers without display:

```bash
flexflow plot CS4SG2U1 --data-type displacement --plot-type time --node 10 --component y \
  --no-display -o output.png
```

---

## `compare` Command

Compare multiple cases on a single plot using YAML configuration.

### Usage

```bash
flexflow compare <config.yaml> [options]
```

### Options

```
--input-file FILE   YAML configuration file (required)
-v, --verbose       Show detailed information
-q, --quiet         Minimal output (only show output filename)
--examples          Show usage examples
-h, --help          Show help message
```

### Examples

Compare multiple cases:
```bash
flexflow compare comparison.yaml
```

Quiet mode for scripts:
```bash
flexflow compare comparison.yaml -q
```

---

## `template` Command

Generate template YAML configuration files.

### Usage

```bash
flexflow template [options]
```

### Options

```
--type TYPE         Template type: single, multi, fft (required)
-o, --output FILE   Output filename (default: example_<type>_config.yaml)
--examples          Show usage examples
-h, --help          Show help message
```

### Template Types

1. **single** - Single case plot template
2. **multi** - Multi-case comparison template
3. **fft** - FFT analysis template

### Examples

Generate single case template:
```bash
flexflow template --type single --output my_config.yaml
```

Generate multi-case template:
```bash
flexflow template --type multi --output comparison.yaml
```

Generate FFT template:
```bash
flexflow template --type fft --output fft_analysis.yaml
```

---

## YAML Configuration

### Structure

```yaml
# Data and plot type
data_type: displacement  # displacement, force, moment, pressure
plot_type: time          # time, fft, traj2d, traj3d

# Plot properties
plot:
  title: "My Plot Title"
  xlabel: "Time (s)"
  ylabel: "Displacement (m)"
  fontsize: 12
  fontname: "Arial"

# Global options
use_index: false      # Use timestep index instead of time
no_def_time: false    # Don't use .def file for time calculation

# Cases to plot
cases:
  - directory: CS4SG2U1
    label: "Case 1"
    node: 10
    component: y
    style: "blue,2,-,o"
    start_time: 10.0
    end_time: 50.0

  - directory: CS4SG3U2
    label: "Case 2"
    node: 10
    component: y
    style: "red,2,--,s"

# Output
output: comparison.png
no_display: false
```

### Case Configuration Options

**Required:**
- `directory`: Path to case directory

**Optional:**
- `label`: Legend label (default: directory name)
- `node`: Node ID for displacement data (default: 10)
- `component`: Component to plot (default: based on data type)
- `style`: Plot style as `"color,width,linestyle,marker"`
- `start_time`: Filter start time
- `end_time`: Filter end time
- `start_step`: Filter start timestep
- `end_step`: Filter end timestep

### Complete Example

```yaml
data_type: displacement
plot_type: time

plot:
  title: "Riser Top Node Displacement Comparison"
  xlabel: "Time (s)"
  ylabel: "Y Displacement (m)"
  fontsize: 14
  fontname: "Times New Roman"

use_index: false
no_def_time: false

cases:
  - directory: CS4SG1U1
    label: "Baseline - U = 1 m/s"
    node: 10
    component: y
    style: "blue,2,-,o"
    start_time: 10.0
    end_time: 50.0

  - directory: CS4SG2U1
    label: "Modified - U = 1.5 m/s"
    node: 10
    component: y
    style: "red,2,--,s"
    start_time: 10.0
    end_time: 50.0

  - directory: CS4SG3U1
    label: "Optimized - U = 2 m/s"
    node: 10
    component: y
    style: "green,2,-.,^"
    start_time: 10.0
    end_time: 50.0

output: riser_comparison.png
no_display: false
```

---

## Examples

### Example 1: Basic Displacement Plot

```bash
flexflow plot CS4SG2U1 --data-type displacement --plot-type time --node 10 --component y
```

### Example 2: Custom Styled Plot

```bash
flexflow plot CS4SG2U1 \
  --data-type displacement \
  --plot-type time \
  --node 10 \
  --component y \
  --plot-style "red,2,--,o" \
  --title "Node 10 Y-Displacement" \
  --xlabel "Time (s)" \
  --ylabel "Displacement (m)" \
  --output node10_disp.png
```

### Example 3: FFT Analysis

```bash
flexflow plot CS4SG2U1 \
  --data-type displacement \
  --plot-type fft \
  --node 10 \
  --component y \
  --title "Frequency Analysis" \
  --output fft_node10.png
```

### Example 4: Force Plot with Time Range

```bash
flexflow plot CS4SG2U1 \
  --data-type force \
  --plot-type time \
  --component tz \
  --start-time 20.0 \
  --end-time 60.0 \
  --output force_tz.png
```

### Example 5: 2D Trajectory

```bash
flexflow plot CS4SG2U1 \
  --data-type displacement \
  --plot-type traj2d \
  --node 10 \
  --component x y \
  --title "Node 10 X-Y Trajectory" \
  --output trajectory_2d.png
```

### Example 6: Multi-Case Comparison

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
flexflow compare comparison.yaml
```

### Example 7: Server Mode (No Display)

```bash
flexflow plot CS4SG2U1 \
  --data-type displacement \
  --plot-type time \
  --node 10 \
  --component y \
  --no-display \
  --output result.png
```

### Example 8: Pipeline Mode (Quiet)

```bash
# Get only the output filename for further processing
output=$(flexflow plot CS4SG2U1 --data-type displacement --plot-type time --node 10 --component y -q)
echo "Plot saved to: $output"
```

### Example 9: All Components at Once

```bash
flexflow plot CS4SG2U1 \
  --data-type displacement \
  --plot-type time \
  --node 10 \
  --component all \
  --output all_components.png
```

---

## Python API

For advanced users who want to integrate FlexFlow into their own Python scripts.

### Basic Usage

```python
from flexflow_case import FlexFlowCase
from plot_utils import plot_node_displacements
import matplotlib.pyplot as plt

# Load case
case = FlexFlowCase('CS4SG2U1')

# Load OTHD data
reader = case.load_othd_data()

# Plot displacement
fig, ax = plot_node_displacements(reader, node_id=10, component='y')
plt.savefig('displacement.png')
plt.show()
```

### Access Case Information

```python
from flexflow_case import FlexFlowCase

case = FlexFlowCase('CS4SG2U1')

# Case configuration
print(f"Problem: {case.config['problem']}")
print(f"Time increment: {case.get_time_increment()}")
print(f"Max timesteps: {case.get_max_timesteps()}")

# Find data files
othd_files = case.find_othd_files()
oisd_files = case.find_oisd_files()
```

### Work with Displacement Data

```python
from flexflow_case import FlexFlowCase

case = FlexFlowCase('CS4SG2U1')
reader = case.load_othd_data()

# Get node data
data = reader.get_node_displacements(node_id=10)

times = data['times']
dx = data['dx']
dy = data['dy']
dz = data['dz']
magnitude = data['magnitude']

# Statistics
print(f"Max Y displacement: {dy.max():.6f}")
print(f"Min Y displacement: {dy.min():.6f}")
print(f"Mean Y displacement: {dy.mean():.6f}")
```

### Work with Force Data

```python
from flexflow_case import FlexFlowCase

case = FlexFlowCase('CS4SG2U1')
reader = case.load_oisd_data()

# Get force data
data = reader.get_force_data()

times = data['times']
tx = data['tx']
ty = data['ty']
tz = data['tz']

# Analyze
import numpy as np
print(f"Max total force: {np.sqrt(tx**2 + ty**2 + tz**2).max():.6f}")
```

### Multi-Node Analysis

```python
from flexflow_case import FlexFlowCase
import matplotlib.pyplot as plt

case = FlexFlowCase('CS4SG2U1')
reader = case.load_othd_data()

# Plot multiple nodes
fig, ax = plt.subplots(figsize=(12, 6))

for node_id in [5, 10, 15, 20, 25]:
    data = reader.get_node_displacements(node_id)
    ax.plot(data['times'], data['dy'], label=f'Node {node_id}')

ax.set_xlabel('Time (s)')
ax.set_ylabel('Y Displacement (m)')
ax.legend()
ax.grid(True)
plt.savefig('multi_node.png')
```

### Custom FFT Analysis

```python
from flexflow_case import FlexFlowCase
import numpy as np
import matplotlib.pyplot as plt

case = FlexFlowCase('CS4SG2U1')
reader = case.load_othd_data()

data = reader.get_node_displacements(node_id=10)
times = data['times']
signal = data['dy']

# Perform FFT
n = len(signal)
dt = times[1] - times[0]
freq = np.fft.rfftfreq(n, dt)
fft = np.fft.rfft(signal)
amplitude = np.abs(fft) / n

# Plot
fig, ax = plt.subplots()
ax.plot(freq, amplitude)
ax.set_xlabel('Frequency (Hz)')
ax.set_ylabel('Amplitude')
ax.set_title('FFT Analysis')
ax.grid(True)
plt.savefig('custom_fft.png')
```

### Time Range Filtering

```python
from flexflow_case import FlexFlowCase
import numpy as np

case = FlexFlowCase('CS4SG2U1')
reader = case.load_othd_data()

data = reader.get_node_displacements(node_id=10)
times = data['times']
dy = data['dy']

# Filter time range
mask = (times >= 10.0) & (times <= 50.0)
times_filtered = times[mask]
dy_filtered = dy[mask]

print(f"Original length: {len(times)}")
print(f"Filtered length: {len(times_filtered)}")
```

---

## Troubleshooting

### Common Issues

**Issue: "No OTHD files found"**
- Check that `othd_files/` directory exists in case directory
- Verify OTHD files have `.othd` extension

**Issue: "No .def file found"**
- Ensure case directory contains a `.def` file
- Check `simflow.config` for correct problem name

**Issue: "Time discontinuities detected"**
- This is normal for restart simulations
- The tool automatically handles overlapping time ranges

**Issue: "Node not found"**
- Verify node ID exists in OTHD files
- Check node numbering in geometry file

**Issue: Plot not displaying (server mode)**
- Use `--no-display` flag
- Ensure output file is specified with `-o`

### Getting Help

Show help for any command:
```bash
flexflow --help
flexflow info --help
flexflow plot --help
flexflow compare --help
flexflow template --help
```

Show examples:
```bash
flexflow plot --examples
flexflow compare --examples
flexflow template --examples
```

---

## Advanced Topics

### Batch Processing

Process multiple cases in a loop:

```bash
#!/bin/bash
for case in CS4SG1U1 CS4SG2U1 CS4SG3U1; do
  flexflow plot $case \
    --data-type displacement \
    --plot-type time \
    --node 10 \
    --component y \
    --no-display \
    -o ${case}_result.png \
    -q
done
```

### Pipeline Integration

Use quiet mode to capture output:

```bash
output=$(flexflow plot CS4SG2U1 --data-type displacement --plot-type time --node 10 --component y -q)
echo "Generated: $output"

# Upload to server, send email, etc.
scp $output user@server:/path/
```

### Custom Analysis Scripts

Combine FlexFlow API with your analysis:

```python
from flexflow_case import FlexFlowCase
import numpy as np

# Your custom analysis function
def analyze_displacement(case_dir, node_id):
    case = FlexFlowCase(case_dir)
    reader = case.load_othd_data()
    data = reader.get_node_displacements(node_id)
    
    # Custom metrics
    max_disp = data['magnitude'].max()
    rms_disp = np.sqrt(np.mean(data['magnitude']**2))
    
    return {
        'case': case_dir,
        'node': node_id,
        'max_displacement': max_disp,
        'rms_displacement': rms_disp
    }

# Analyze multiple cases
cases = ['CS4SG1U1', 'CS4SG2U1', 'CS4SG3U1']
results = [analyze_displacement(c, 10) for c in cases]

for r in results:
    print(f"{r['case']}: max={r['max_displacement']:.6f}, rms={r['rms_displacement']:.6f}")
```

---

## Best Practices

1. **Use YAML for complex plots**: For multi-case comparisons or plots with many customizations
2. **Use quiet mode in scripts**: Add `-q` flag for cleaner output in automated workflows
3. **Use verbose mode for debugging**: Add `-v` flag when troubleshooting issues
4. **Server mode for remote work**: Use `--no-display` when working on servers without display
5. **Preview before plotting**: Use `info` command to check data before creating plots
6. **Generate templates**: Use `template` command to quickly create YAML configurations
7. **Consistent naming**: Use descriptive output filenames that indicate the plot content

---

## See Also

- [README.md](../README.md) - Project overview
- Example YAML files in project root
