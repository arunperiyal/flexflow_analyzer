# `plot` Command

Create plots from a single FlexFlow case with various plot types and customization options.

## Usage

```bash
flexflow plot <case_directory> [options]
flexflow plot --input-file <yaml_file>
```

## Description

The `plot` command creates various types of plots from FlexFlow simulation data, including:
- Time series plots (displacement, force, moment, pressure)
- FFT frequency analysis
- 2D and 3D trajectory plots

Plots can be customized with colors, line styles, markers, labels, and more.

## Required Options

```
--node INT          Node number to plot (required for displacement data)
--data-type TYPE    Data type: displacement, force, moment, pressure
--component STR     Component(s) to plot: x, y, z, magnitude, all
```

## Plot Options

```
--plot-type TYPE    Plot type: time, fft, traj2d, traj3d (default: time)
--start-time T      Start time for plot
--end-time T        End time for plot
```

## Styling Options

```
--plot-style STR    Style: "<color>,<width>,<linestyle>,<marker>"
                    color: red, blue, green, orange, purple, black,
                           cyan, magenta, yellow, #FF5733, etc.
                    width: 1, 1.5, 2, 2.5, etc.
                    linestyle: - (solid), -- (dashed), -. (dashdot), : (dotted)
                    marker: o (circle), s (square), ^ (triangle), v (down)
                           * (star), + (plus), x (cross), None (no marker)
--title TEXT        Plot title: "<text>|<fontsize>|<latex>"
                    Format: text|fontsize|latex_flag
                    Examples: "My Title|16|True" or "Simple Title" or "Title|14"
--xlabel TEXT       X-axis label (same format as title)
                    Examples: "Time (s)|14" or "Time $t$ (s)|12|True"
--ylabel TEXT       Y-axis label (same format as title)
                    Examples: "Displacement (m)|14" or "Force $F$ (N)|14|True"
--legend TEXT       Legend label (same format as title)
--fontsize N        Global font size (default: 12) [DEPRECATED - use label format]
--fontname NAME     Font family (default: sans-serif)
                    Common: serif, sans-serif, monospace
                    Academic: DejaVu Serif, Liberation Serif
                    Modern: DejaVu Sans, Liberation Sans
                    Note: 'serif' gives Times New Roman-like font
```

### Enhanced Label Format

Labels now support an enhanced format: `"<text>|<fontsize>|<latex>"`

- **text**: The label text (required)
- **fontsize**: Font size for this specific label (optional)
- **latex**: Enable LaTeX rendering - True/False/latex (optional)

**Examples:**
- `"Simple Text"` - Basic label
- `"My Label|16"` - Label with size 16
- `"Time $t$|14|True"` - LaTeX label with size 14
- `"Force $F_x$ (N)|12|latex"` - LaTeX with size 12
```

## Output Options

```
--output FILE       Save plot to file (auto-enables headless mode)
--no-display        Don't display plot (useful for SSH/remote)
-v, --verbose       Show detailed information
--examples          Show usage examples
-h, --help          Show this help message
```

## Alternative Input

```
--input-file FILE   Load configuration from YAML file
```

## Plot Types

### 1. Time Domain Plot (`--plot-type time`)

Plot data vs time or timestep index.

**Example - Displacement vs time:**
```bash
flexflow plot CS4SG1U1 --node 100 --data-type displacement --component y
```

**Example - Force vs time:**
```bash
flexflow plot CS4SG1U1 --data-type force --component tz
```

**Example - All components:**
```bash
flexflow plot CS4SG1U1 --node 100 --data-type displacement --component all
```

### 2. FFT Plot (`--plot-type fft`)

Frequency domain analysis.

**Example:**
```bash
flexflow plot CS4SG1U1 --node 100 --data-type displacement \
    --plot-type fft --component y
```

### 3. 2D Trajectory (`--plot-type traj2d`)

Plot two components against each other.

**Example - X-Y trajectory:**
```bash
flexflow plot CS4SG1U1 --node 100 --data-type displacement \
    --plot-type traj2d --component x y
```

### 4. 3D Trajectory (`--plot-type traj3d`)

Plot three components in 3D space.

**Example - X-Y-Z trajectory:**
```bash
flexflow plot CS4SG1U1 --node 100 --data-type displacement \
    --plot-type traj3d --component x y z
```

## Time Range Filtering

Filter data to specific time windows:

```bash
flexflow plot CS4SG1U1 --node 100 --data-type displacement \
    --component y --start-time 10.0 --end-time 50.0
```

## Plot Styling

Customize plot appearance with `--plot-style`:

**Format:** `"color,width,linestyle,marker"`

### Color Options
- **Named colors:** `red`, `blue`, `green`, `orange`, `purple`, `black`, `cyan`, `magenta`, `yellow`, `brown`, `pink`, `gray`
- **Hex colors:** `#FF5733`, `#3498DB`, `#2ECC71`
- **RGB tuples:** `(0.5, 0.3, 0.8)`

### Line Width
Any positive number:
- Thin: `0.5`, `1`
- Medium: `1.5`, `2`
- Thick: `2.5`, `3`, `4`

### Line Styles
- `-` : solid line (default)
- `--` : dashed line
- `-.` : dash-dot line
- `:` : dotted line

### Markers
- `o` : circle
- `s` : square
- `^` : triangle up
- `v` : triangle down
- `*` : star (5-pointed)
- `+` : plus sign
- `x` : x mark (cross)
- `D` : diamond
- `p` : pentagon
- `h` : hexagon
- `.` : point
- `None` : no marker

### Styling Examples

**Blue solid line with circles, width 2:**
```bash
flexflow plot CS4SG1U1 --node 100 --data-type displacement \
    --component y --plot-style "blue,2,-,o"
```

**Red dashed line, no markers, width 1.5:**
```bash
flexflow plot CS4SG1U1 --data-type force --component tz \
    --plot-style "red,1.5,--,None"
```

**Green dash-dot line with squares:**
```bash
flexflow plot CS4SG1U1 --node 100 --data-type displacement \
    --component y --plot-style "green,2,-.,s"
```

**Custom hex color with stars:**
```bash
flexflow plot CS4SG1U1 --node 100 --data-type displacement \
    --component y --plot-style "#FF5733,1.5,-,*"
```

**Purple dotted line with diamonds:**
```bash
flexflow plot CS4SG1U1 --node 100 --data-type displacement \
    --component y --plot-style "purple,2,:,D"
```

**Cyan solid line with triangles, thick:**
```bash
flexflow plot CS4SG1U1 --node 100 --data-type displacement \
    --component y --plot-style "cyan,3,-,^"
```

## Remote/SSH Usage (Headless Mode)

For remote servers without display, use `--output` which automatically enables headless mode:

```bash
flexflow plot CS4SG1U1 --node 100 --data-type displacement \
    --component y --output result.png
```

Or explicitly use `--no-display`:
```bash
flexflow plot CS4SG1U1 --node 100 --data-type displacement \
    --component y --no-display
```

## Custom Labels and Titles

### Simple Labels with Custom Font Size

```bash
flexflow plot CS4SG1U1 --node 100 --data-type displacement \
    --component y --title "Node 100 Displacement|16" \
    --xlabel "Time (s)|14" --ylabel "Displacement (m)|14"
```

### LaTeX Rendering for Mathematical Expressions

```bash
# Greek letters and subscripts
flexflow plot CS4SG1U1 --node 100 --data-type displacement \
    --component y --title "Displacement $\\Delta x$|16|True" \
    --xlabel "Time $t$ (s)|14|True" \
    --ylabel "Displacement $\\delta$ (m)|14|True"

# Complex mathematical expressions
flexflow plot CS4SG1U1 --node 100 --data-type displacement \
    --component y --title "Response Analysis|18|True" \
    --ylabel "$F_x = m \\ddot{x}$ (N)|14|True"

# Mixed: LaTeX for some labels only
flexflow plot CS4SG1U1 --node 100 --data-type displacement \
    --component y --title "Force Analysis|16" \
    --ylabel "Force $F_x$ (N)|14|True"
```

### Legacy Format (Still Supported)

```bash
# Old way - still works but deprecated
flexflow plot CS4SG1U1 --node 100 --data-type displacement \
    --component y --title "Node 100 Displacement" \
    --xlabel "Time (s)" --ylabel "Displacement (m)" \
    --fontsize 14
```

## Font Customization

### Available Font Families

**Generic Families (Always Available):**
- `serif` - Times-like fonts (recommended for academic publications)
- `sans-serif` - Arial-like fonts (clean, modern look)
- `monospace` - Fixed-width fonts (for code/data)

**Specific Fonts (Linux):**
- `DejaVu Serif` - Excellent Times New Roman alternative
- `Liberation Serif` - Metrically compatible with Times New Roman
- `DejaVu Sans` - Clean sans-serif font
- `Liberation Sans` - Metrically compatible with Arial

### Font Examples

**Times New Roman Style (Academic):**
```bash
flexflow plot CS4SG1U1 --node 100 --data-type displacement \
    --component y --fontname serif \
    --title "Case Study|16" --ylabel "Displacement (m)|14"
```

**Using DejaVu Serif:**
```bash
flexflow plot CS4SG1U1 --node 100 --data-type displacement \
    --component y --fontname "DejaVu Serif" \
    --title "Analysis Results|16"
```

**Modern Sans-Serif:**
```bash
flexflow plot CS4SG1U1 --node 100 --data-type displacement \
    --component y --fontname "DejaVu Sans"
```

### Installing Microsoft Fonts (Optional)

To use actual Times New Roman, Arial, etc.:
```bash
sudo apt-get install ttf-mscorefonts-installer
fc-cache -fv  # Refresh font cache
```

Then use:
```bash
flexflow plot CS4SG1U1 --node 100 --data-type displacement \
    --component y --fontname "Times New Roman"
```

## Save to File

```bash
flexflow plot CS4SG1U1 --node 100 --data-type displacement \
    --component y --output plot.png
```

## Using YAML Configuration

Create a configuration file and use it:

```bash
flexflow plot --input-file plot_config.yaml
```

See [YAML Configuration](../../USAGE.md#yaml-configuration) for details.

## Use Cases

1. **Quick visualization** - View displacement or force data
2. **Frequency analysis** - Identify dominant frequencies with FFT
3. **Trajectory analysis** - Visualize motion paths in 2D or 3D
4. **Time window analysis** - Focus on specific time ranges
5. **Report generation** - Create publication-quality plots with custom styling
6. **Batch processing** - Generate multiple plots on remote servers

## Tips

- Use `--verbose` to see what data is being loaded
- Use `--output` for headless operation on servers
- Use `--plot-style` for custom colors and line styles
- Use `--start-time` and `--end-time` to zoom into specific time windows
- Use YAML configuration files for complex plots or batch processing

## See Also

- [compare command](../compare/README.md) - Compare multiple cases
- [template command](../template/README.md) - Generate YAML templates
- [Main Usage Guide](../../USAGE.md)
