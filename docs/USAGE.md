# FlexFlow Usage Guide

Complete guide for using FlexFlow CLI tool for post-processing FlexFlow simulation data.

## Table of Contents

1. [Installation](#installation)
2. [Quick Start](#quick-start)
3. [Command Reference](#command-reference)
4. [Detailed Documentation](#detailed-documentation)

---

## Installation

See detailed setup guides:
- [Installation Guide](./setup/INSTALL.md)
- [Update Guide](./setup/UPDATE.md)
- [Uninstallation Guide](./setup/UNINSTALL.md)

### Quick Install

```bash
flexflow --install
```

This will:
- Create a `flexflow` alias in your shell configuration
- Install Python dependencies (numpy, matplotlib, pyyaml, markdown)
- Optionally install Microsoft fonts for publication-quality plots
- Convert and copy HTML documentation

### Verify Installation

```bash
flexflow --version
```

---

## Quick Start

### 1. Preview Case Data

```bash
flexflow info CS4SG2U1
flexflow info CS4SG2U1 --preview
```

### 2. Plot Single Case

```bash
flexflow plot CS4SG2U1 --data-type displacement --plot-type time --node 10 --component y
```

### 3. Compare Multiple Cases

```bash
flexflow compare comparison.yaml
```

### 4. Generate Template

```bash
flexflow template --type single --output my_config.yaml
```

---

## Command Reference

FlexFlow CLI uses a git-style command structure:

```
flexflow <command> [options]
```

### Available Commands

- **`info`** - Display case information and preview timesteps
- **`plot`** - Create plots from a single case
- **`compare`** - Compare multiple cases on one plot
- **`template`** - Generate template YAML configuration files
- **`docs`** - View documentation in browser

### Global Options

```
--install           Install FlexFlow CLI (create alias in shell)
--uninstall         Uninstall FlexFlow CLI (remove alias)
--update            Update FlexFlow CLI installation
--version           Show version information
-h, --help          Show help message
```

---

## Detailed Documentation

For comprehensive documentation on each command, see:
- [info command](./usage/commands/info.md) - Display case information
- [plot command](./usage/commands/plot.md) - Create plots from single cases
- [compare command](./usage/commands/compare.md) - Compare multiple cases
- [template command](./usage/commands/template.md) - Generate YAML templates

Or use the built-in documentation viewer:

```bash
flexflow docs           # View main documentation
flexflow docs plot      # View plot command docs
flexflow docs compare   # View compare command docs
```

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

For remote servers without display (SSH sessions):

```bash
# Automatically uses headless mode when --output is specified
flexflow plot CS4SG2U1 --data-type displacement --plot-type time --node 10 --component y \
  --output output.png

# Explicitly disable display
flexflow plot CS4SG2U1 --data-type displacement --plot-type time --node 10 --component y \
  --output output.pdf --no-display
```

### Advanced Styling Examples

With LaTeX rendering and custom fonts:

```bash
# Publication-quality plot with Times-like font and LaTeX labels
flexflow plot CS4SG1U1 --node 10 --data-type displacement \
  --plot-type time --component y --start-time 100 --end-time 200 \
  --output figure.pdf --plot-style "green,2,--,None" \
  --title "Case 1|16" --ylabel '$y$|15|latex' --xlabel '$\tau$|12|latex' \
  --fontname "serif" --legend "Node 10|12"

# With legend positioning
flexflow plot CS4SG1U1 --node 10 --data-type displacement \
  --plot-type time --component y \
  --legend "Displacement" --legend-style "northeast|14|on|False"
```

---

## `compare` Command

Compare data from multiple FlexFlow cases on a single plot.

### Usage

```bash
flexflow compare <case1> <case2> [...] [options]
flexflow compare --input-file <yaml_file>
```

### Required Options

```
--node N              Node number to compare
--data-type TYPE     Data type: displacement or force
```

### Plot Options

```
--plot-type TYPE     Plot type: time, fft, traj2d, traj3d (default: time)
--component X [Y Z]  Components to plot (x, y, z)
--start-time T       Start time for plot
--end-time T         End time for plot
```

### Styling Options

```
--plot-style STYLES  Plot styles for each case, separated by |
                     Format per case: color,width,linestyle,marker
                     Example: "blue,2,-,o|red,2,--,s|green,2,-.,^"
--legend LABELS      Custom legend labels separated by |
                     Example: "Case 1|Case 2|Case 3"
--legend-style STYLE Legend style: position|fontsize|frameon|latex
                     Example: "best|12|on|False" or "northeast|14|off|True"
--title TEXT         Plot title (format: "text|fontsize|latex")
--xlabel TEXT        X-axis label (format: "text|fontsize|latex")
--ylabel TEXT        Y-axis label (format: "text|fontsize|latex")
--fontsize N         Font size (default: 12)
--fontname NAME      Font family (e.g., serif, sans-serif)
```

### Output Options

```
--output FILE        Save plot to file (auto-enables headless mode)
--no-display         Don't display plot (useful for SSH/remote)
-v, --verbose        Show detailed information
--examples           Show usage examples
```

### Examples

Compare two cases:
```bash
flexflow compare CS4SG1U1 CS4SG2U1 --node 100 --data-type displacement \
  --component y --plot-style "blue,2,-,o|red,2,--,s" \
  --legend "Case 1|Case 2" --output comparison.png
```

With custom styling:
```bash
flexflow compare CS4SG1U1 CS4SG2U1 CS4SG3U1 \
  --node 100 --data-type displacement --component y \
  --plot-style "blue,2,-,None|red,2,--,None|green,2,-.,None" \
  --legend "Uniform|Graded|Optimized" \
  --legend-style "best|14|on|False" \
  --title "Displacement Comparison|16" \
  --ylabel '$y$ (m)|14|latex' --xlabel 'Time (s)|14' \
  --fontname "serif" --output compare.pdf
```

---

## `docs` Command

View FlexFlow documentation in your default browser.

### Usage

```bash
flexflow docs [command]
```

### Options

```
command         Optional: Specify command to view docs for
                Options: info, plot, compare, template
                If not specified, opens main documentation
```

### Examples

View main documentation:
```bash
flexflow docs
```

---

## Additional Resources

For detailed examples and more information:
- See individual command documentation in [docs/usage/commands/](./usage/commands/)
- YAML configuration examples in project templates
- Python API usage in command-specific docs

Use the built-in help system for more details:

```bash
flexflow docs           # Open main documentation
flexflow docs plot      # Open plot command documentation
flexflow docs compare   # Open compare command documentation
flexflow --help         # Show global options
flexflow plot --help    # Show plot command options
```
