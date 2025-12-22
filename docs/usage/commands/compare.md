# `compare` Command

Compare multiple FlexFlow cases on a single plot or create separate plots for each case.

## Usage

```bash
flexflow compare <case1> <case2> [...] [options]
flexflow compare --input-file <yaml_file>
```

## Description

The `compare` command allows you to analyze and visualize data from multiple FlexFlow cases. It supports three output modes:

1. **Combined Plot** (default) - Overlay all cases on a single plot
2. **Subplot Layout** - Display cases in a grid of subplots
3. **Separate Plots** - Create individual plot files for each case

This is useful for:
- Parameter studies
- Design optimization comparisons
- Validation against experimental data
- Sensitivity analysis
- Batch processing multiple cases

## Required Options

```
<case1> <case2> [...]  Case directories to compare (when not using --input-file)
--node INT             Node number to compare
--data-type TYPE       Data type: displacement or force
--component STR        Component(s) to plot: x, y, z
```

## Plot Options

```
--plot-type TYPE       Plot type: time, fft, traj2d, traj3d (default: time)
--start-time T         Start time for plot
--end-time T           End time for plot
--start-step N         Start step ID (tsId, starting from 1)
--end-step N           End step ID (tsId)
```

## Layout Options

```
--subplot LAYOUT       Create subplots instead of overlaying cases
                       Format: rows,columns (e.g., "2,2" for 2x2 grid)
--separate             Create separate plot files for each case (overrides --subplot)
--output-prefix TEXT   Prefix for separate plot filenames (default: "case_")
                       Example: "comparison_" → comparison_CS4SG1U1.png
--output-format FMT    Output format for separate plots: png, pdf, svg (default: png)
```

## Styling Options

```
--plot-style STYLES    Plot styles for each case, separated by |
                       Format per case: color,width,linestyle,marker
                       Example: "blue,2,-,o|red,2,--,s|green,2,-.,^"
--legend LABELS        Custom legend labels separated by |
                       Example: "Case 1|Case 2|Case 3"
--legend-style STYLE   Legend style: position|fontsize|frameon|latex
--title TEXT           Plot title
--xlabel TEXT          X-axis label
--ylabel TEXT          Y-axis label
--fontsize N           Font size (default: 12)
--fontname NAME        Font family (default: sans-serif)
```

## Output Options

```
--output FILE          Save plot to file (for combined/subplot mode)
--no-display           Don't display plot (useful for SSH/remote)
-v, --verbose          Show detailed information
--examples             Show usage examples
-h, --help             Show this help message
```

## Alternative Input

```
--input-file FILE      Load configuration from YAML file
```

## Examples

### Basic Comparison

Compare displacement between two cases:
```bash
flexflow compare CS4SG1U1 CS4SG2U1 --node 100 --data-type displacement \
    --component y
```

### Multiple Cases with Styling

Compare three cases with custom styles:
```bash
flexflow compare CS4SG1U1 CS4SG2U1 CS4SG3U1 --node 100 \
    --data-type displacement --component y \
    --plot-style "blue,2,-,o|red,2,--,s|green,2,-.,^" \
    --legend "Baseline|Modified A|Modified B"
```

### Subplot Layout

Display cases in a 2x2 grid:
```bash
flexflow compare CS4SG1U1 CS4SG2U1 CS4SG3U1 CS4SG4U1 --node 100 \
    --data-type displacement --component y --subplot "2,2" \
    --output comparison_subplots.pdf
```

### Separate Plots for Each Case

Create individual plot files:
```bash
flexflow compare CS4SG1U1 CS4SG2U1 CS4SG3U1 --node 100 \
    --data-type displacement --component y --separate \
    --output-prefix "result_" --output-format pdf
```
Creates: `result_CS4SG1U1.pdf`, `result_CS4SG2U1.pdf`, `result_CS4SG3U1.pdf`

### Time Range with Step IDs

Compare specific time range using step IDs:
```bash
flexflow compare CS4SG1U1 CS4SG2U1 --node 100 --data-type displacement \
    --component y --start-step 1 --end-step 100
```
Note: Step IDs (tsId) start from 1, and time = step_id × dt

### Save to File (Remote/SSH)

Generate comparison plot on remote server:
```bash
flexflow compare CS4SG1U1 CS4SG2U1 --node 100 --data-type displacement \
    --component y --output comparison.png
```

### Using YAML Configuration

For complex comparisons, use YAML:
```bash
flexflow compare --input-file comparison.yaml
```

## YAML Configuration Examples

### Combined Plot (Default)

```yaml
cases:
- case_dir: CS4SG1U1
  node: 10
  data_type: displacement
  component: y
  label: Baseline
  style:
    color: blue
    linewidth: 2.0
    linestyle: '-'
    marker: o

- case_dir: CS4SG2U1
  node: 10
  data_type: displacement
  component: y
  label: Modified
  style:
    color: red
    linewidth: 2.0
    linestyle: '--'
    marker: s

plot_type: time
output: comparison.png

plot_properties:
  title: Case Comparison
  xlabel: Time (s)
  ylabel: Displacement (mm)
  fontsize: 12
  fontname: Arial
  legend: true
  grid: true

time_range:
  start_step: 1
  end_step: 100
```

### Separate Plots Mode

```yaml
cases:
- case_dir: CS4SG1U1
  node: 10
  data_type: displacement
  component: y
  label: Configuration A
  style:
    color: blue
    linewidth: 2.5

- case_dir: CS4SG2U1
  node: 10
  data_type: displacement
  component: y
  label: Configuration B
  style:
    color: red
    linewidth: 2.5

plot_type: time
separate: true
output_prefix: comparison_
output_format: pdf

plot_properties:
  title: Displacement Analysis
  xlabel: Time (s)
  ylabel: Displacement (mm)

time_range:
  start_step: 1
  end_step: 100
```

This creates: `comparison_CS4SG1U1.pdf`, `comparison_CS4SG2U1.pdf`

## Time Range Specification

You can specify time ranges in two ways:

1. **Step IDs** (tsId, starting from 1):
   ```yaml
   time_range:
     start_step: 1    # First time step (tsId = 1)
     end_step: 100    # 100th time step (tsId = 100)
   ```
   Time is calculated as: `time = step_id × dt`

2. **Direct Time Values**:
   ```yaml
   time_range:
     start_time: 0.05  # Start time in seconds
     end_time: 5.0     # End time in seconds
   ```

## Output Modes Comparison

| Mode | Command Flag | Best For |
|------|--------------|----------|
| Combined | (default) | Direct visual comparison, overlaying curves |
| Subplot | `--subplot "2,2"` | Organized grid layout, many cases |
| Separate | `--separate` | Individual analysis, batch processing, reports |

## Remote/SSH Usage

When working on remote servers without display:

```bash
# Automatically headless when using --output
flexflow compare CS4SG1U1 CS4SG2U1 --node 100 --data-type displacement \
    --component y --output result.png

# Or explicitly use --no-display
flexflow compare CS4SG1U1 CS4SG2U1 --node 100 --data-type displacement \
    --component y --no-display
```

## Use Cases

1. **Parameter studies** - Compare different simulation parameters
2. **Design optimization** - Evaluate design alternatives
3. **Validation** - Compare simulation vs. experimental data
4. **Sensitivity analysis** - Assess impact of input variations
5. **Batch processing** - Generate reports for multiple cases with `--separate`
6. **Publication figures** - High-quality PDF outputs with custom styling

## Tips

- Use YAML configuration for complex comparisons with many cases
- Use `--separate` mode for generating individual reports or presentations
- Specify `--output-format pdf` for publication-quality vector graphics
- Use step IDs (`start_step`/`end_step`) when you know the step numbers
- Use time values (`start_time`/`end_time`) for specific time windows
- Combine `--output-prefix` with descriptive names for organized output

## Automatic Features

- **Legend generation** - Automatically creates legend from case names
- **Color cycling** - Automatically assigns different colors to each case
- **Time filtering** - Supports both step IDs and time values
- **Format handling** - Supports PNG, PDF, and SVG output formats

## See Also

- [plot command](plot.md) - Plot single cases
- [template command](template.md) - Generate comparison templates
- [Main Usage Guide](../../USAGE.md)
