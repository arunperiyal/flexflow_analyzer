# `compare` Command

Compare multiple FlexFlow cases on a single plot using YAML configuration.

## Usage

```bash
flexflow compare <case1> <case2> [...] [options]
flexflow compare --input-file <yaml_file>
```

## Description

The `compare` command allows you to overlay data from multiple FlexFlow cases on a single plot for direct comparison. This is useful for:
- Parameter studies
- Design optimization comparisons
- Validation against experimental data
- Sensitivity analysis

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
```

## Styling Options

```
--title TEXT           Plot title
--xlabel TEXT          X-axis label
--ylabel TEXT          Y-axis label
--fontsize N           Font size (default: 12)
--fontname NAME        Font family (default: sans-serif)
```

## Output Options

```
--output FILE          Save plot to file (auto-enables headless mode)
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

### Multiple Cases

Compare three or more cases:
```bash
flexflow compare CS4SG1U1 CS4SG2U1 CS4SG3U1 --node 100 \
    --data-type displacement --component y
```

### With Styling

Add custom title and styling:
```bash
flexflow compare CS4SG1U1 CS4SG2U1 --node 100 --data-type displacement \
    --component y --title "Case Comparison" --fontsize 14
```

### Time Range

Compare specific time window:
```bash
flexflow compare CS4SG1U1 CS4SG2U1 --node 100 --data-type displacement \
    --component y --start-time 50.0 --end-time 100.0
```

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

## YAML Configuration Example

```yaml
cases:
  - case: CS4SG1U1
    label: "Case 1: Baseline"
    plot_style:
      color: blue
      linewidth: 2
      linestyle: "-"
  
  - case: CS4SG2U1
    label: "Case 2: Modified"
    plot_style:
      color: red
      linewidth: 2
      linestyle: "--"

plot:
  node: 100
  data_type: displacement
  plot_type: time
  component: y

time_range:
  start_time: 10.0
  end_time: 100.0

style:
  title: "Displacement Comparison"
  xlabel: "Time (s)"
  ylabel: "Y Displacement (m)"
  fontsize: 14
  fontname: "Arial"

output:
  file: comparison.png
  dpi: 300
  no_display: true
```

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
5. **Time history comparison** - Compare response under different conditions
6. **Frequency analysis comparison** - Compare FFT results

## Tips

- Use YAML configuration for complex comparisons with many cases
- Each case can have custom labels and plot styles
- Use `--start-time` and `--end-time` to focus on regions of interest
- Use `--output` for automatic headless mode on servers
- Legend labels are automatically generated from case directories unless specified

## Automatic Features

- **Legend generation** - Automatically creates legend from case names
- **Color cycling** - Automatically assigns different colors to each case
- **Label formatting** - Smart formatting of case names for readability

## See Also

- [plot command](../plot/README.md) - Plot single cases
- [template command](../template/README.md) - Generate comparison templates
- [YAML Configuration](../../USAGE.md#yaml-configuration) - Detailed YAML syntax
- [Main Usage Guide](../../USAGE.md)
