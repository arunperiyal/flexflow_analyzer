# `template` Command

Generate template YAML configuration files for plotting and comparison.

## Usage

```bash
flexflow template <type> <output_file>
```

## Description

The `template` command generates pre-filled YAML configuration files that serve as starting points for creating complex plots and comparisons. These templates include:
- All available configuration options with comments
- Example values showing proper syntax
- Best practices for each plot type

## Template Types

```
single    Generate single case plot configuration
multi     Generate multi-case comparison configuration
```

## Options

```
--examples    Show usage examples
-h, --help    Show this help message
```

## Examples

### Generate Single Case Template

Create a template for single case plotting:
```bash
flexflow template single my_plot.yaml
```

### Generate Multi-Case Template

Create a template for comparing multiple cases:
```bash
flexflow template multi comparison.yaml
```

### Use Generated Template

After generating a template, edit it and use it:
```bash
# Generate template
flexflow template single my_plot.yaml

# Edit the YAML file with your preferred editor
nano my_plot.yaml

# Use the configuration
flexflow plot --input-file my_plot.yaml
```

## Single Case Template

The single case template includes:

```yaml
# Single case plot configuration
case: CS4SG1U1

# Node and data type
node: 10
data_type: displacement
plot_type: time
component: y

# Time range filtering
time_range:
  start_time: 0.0
  end_time: 100.0

# Plot styling
plot_style:
  color: blue
  linewidth: 2
  linestyle: "-"
  marker: ""

# Labels and title
style:
  title: "Displacement vs Time"
  xlabel: "Time (s)"
  ylabel: "Displacement (m)"
  legend: "Node 10"
  fontsize: 12
  fontname: "sans-serif"

# Output options
output:
  file: output.png
  dpi: 300
  no_display: false
```

## Multi-Case Template

The multi-case comparison template includes:

```yaml
# Multi-case comparison configuration
cases:
  - case: CS4SG1U1
    label: "Case 1"
    plot_style:
      color: blue
      linewidth: 2
      linestyle: "-"
  
  - case: CS4SG2U1
    label: "Case 2"
    plot_style:
      color: red
      linewidth: 2
      linestyle: "--"

# Plot configuration
plot:
  node: 10
  data_type: displacement
  plot_type: time
  component: y

# Time range
time_range:
  start_time: 0.0
  end_time: 100.0

# Styling
style:
  title: "Case Comparison"
  xlabel: "Time (s)"
  ylabel: "Displacement (m)"
  fontsize: 14
  fontname: "Arial"

# Output
output:
  file: comparison.png
  dpi: 300
  no_display: false
```

## Template Structure

### Common Sections

All templates include these sections:

1. **Case Information** - Which case(s) to plot
2. **Data Selection** - Node, data type, component
3. **Time Range** - Optional filtering
4. **Plot Styling** - Colors, line styles, markers
5. **Labels** - Title, axis labels, legend
6. **Output Options** - File name, DPI, display mode

### YAML Syntax Tips

- Use spaces (not tabs) for indentation
- Indent consistently (2 or 4 spaces)
- Strings with spaces need quotes: `"My Title"`
- Lists use `- ` prefix
- Comments start with `#`
- Booleans: `true` or `false` (lowercase)

## Workflow

### 1. Generate Template
```bash
flexflow template single my_config.yaml
```

### 2. Edit Template
Open in your editor and modify values:
- Change case directory
- Adjust node number
- Customize colors and styles
- Set time range
- Configure output

### 3. Validate (Optional)
Test with verbose mode:
```bash
flexflow plot --input-file my_config.yaml --verbose
```

### 4. Use in Production
```bash
flexflow plot --input-file my_config.yaml
```

### 5. Reuse and Version Control
- Save templates for common plots
- Version control YAML files with your project
- Share templates with team members
- Create template library for standard analyses

## Use Cases

1. **Batch processing** - Create multiple similar plots
2. **Reproducibility** - Document exact plot settings
3. **Team collaboration** - Share plot configurations
4. **Report generation** - Standardized plot formatting
5. **Complex plots** - Easier than long command lines
6. **Version control** - Track plot configuration changes

## Benefits Over Command Line

- **Readability** - Easier to understand than long commands
- **Repeatability** - Same plot every time
- **Documentation** - Self-documenting configurations
- **Version control** - Track changes in git
- **Collaboration** - Easy to share and review
- **Complexity** - Handle complex plots easily

## Advanced Usage

### Custom Templates

Create your own template library:
```bash
# Create templates directory
mkdir ~/flexflow_templates

# Generate base templates
flexflow template single ~/flexflow_templates/time_series.yaml
flexflow template multi ~/flexflow_templates/comparison.yaml

# Customize templates for your project
# Use as starting point for new analyses
```

### Batch Plotting

Use templates with shell scripts:
```bash
#!/bin/bash
# Generate plots for all cases

for case in CS4SG1U1 CS4SG2U1 CS4SG3U1; do
    # Copy template
    cp template.yaml ${case}_plot.yaml
    
    # Modify case name in YAML
    sed -i "s/case: .*/case: $case/" ${case}_plot.yaml
    
    # Generate plot
    flexflow plot --input-file ${case}_plot.yaml
done
```

## Tips

- Start with a generated template and modify incrementally
- Keep a library of templates for common plot types
- Use version control for YAML files
- Add comments to document why specific settings were chosen
- Test templates with `--verbose` to catch errors early

## See Also

- [plot command](../plot/README.md) - Use templates with plot
- [compare command](../compare/README.md) - Use templates with compare
- [YAML Configuration](../../USAGE.md#yaml-configuration) - Detailed YAML reference
- [Main Usage Guide](../../USAGE.md)
