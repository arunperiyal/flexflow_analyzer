"""Help messages for plot command."""

from src.utils.colors import Colors

def print_plot_help():
    """Print plot command help."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow Plot Command{Colors.RESET}

Plot displacement or force data for a specific node.

{Colors.BOLD}USAGE:{Colors.RESET}
    plot {Colors.YELLOW}<case_directory>{Colors.RESET} [options]
    plot {Colors.YELLOW}--input-file{Colors.RESET} <yaml_file>

{Colors.BOLD}REQUIRED OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--node{Colors.RESET} N              Node number to plot
    {Colors.YELLOW}--data-type{Colors.RESET} TYPE     Data type: displacement or force

{Colors.BOLD}PLOT OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--plot-type{Colors.RESET} TYPE     Plot type: time, fft, traj2d, traj3d (default: time)
    {Colors.YELLOW}--component{Colors.RESET} X [Y Z]  Components to plot (x, y, z)
    {Colors.YELLOW}--start-time{Colors.RESET} T       Start time for plot
    {Colors.YELLOW}--end-time{Colors.RESET} T         End time for plot

{Colors.BOLD}STYLING OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--plot-style{Colors.RESET} STR     Style: "<color>,<width>,<linestyle>,<marker>"
                            {Colors.DIM}color:{Colors.RESET} red, blue, green, orange, purple, black
                                   cyan, magenta, yellow, #FF5733, etc.
                            {Colors.DIM}width:{Colors.RESET} 1, 1.5, 2, 2.5, etc.
                            {Colors.DIM}linestyle:{Colors.RESET} - (solid), -- (dashed), -. (dashdot), : (dotted)
                            {Colors.DIM}marker:{Colors.RESET} o (circle), s (square), ^ (triangle), v (down)
                                   * (star), + (plus), x (cross), None (no marker)
    {Colors.YELLOW}--title{Colors.RESET} TEXT         Plot title: "<text>|<fontsize>|<latex>"
                            Example: "My Title|16|True" or just "My Title"
    {Colors.YELLOW}--xlabel{Colors.RESET} TEXT        X-axis label: "<text>|<fontsize>|<latex>"
                            Example: "Time (s)|14" or "Time ($s$)|12|True"
    {Colors.YELLOW}--ylabel{Colors.RESET} TEXT        Y-axis label: "<text>|<fontsize>|<latex>"
                            Example: "Displacement ($m$)|14|True"
    {Colors.YELLOW}--legend{Colors.RESET} TEXT        Legend label (same format)
    {Colors.YELLOW}--legend-style{Colors.RESET} STYLE Legend style: position|fontsize|frameon|latex
                            Position: best, upper right, upper left, lower left, lower right,
                                     north, south, east, west, northeast, northwest, etc.
                            Example: "best|12|on|False" or "northeast|14|off|True"
    {Colors.YELLOW}--fontsize{Colors.RESET} N         Global font size (default: 12) [deprecated]
    {Colors.YELLOW}--fontname{Colors.RESET} NAME      Font family (default: sans-serif)
                            {Colors.DIM}Common:{Colors.RESET} serif, sans-serif, monospace
                            {Colors.DIM}Academic:{Colors.RESET} DejaVu Serif, Liberation Serif
                            {Colors.DIM}Modern:{Colors.RESET} DejaVu Sans, Liberation Sans
                            {Colors.DIM}Note:{Colors.RESET} 'serif' gives Times-like font

{Colors.BOLD}OUTPUT OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--output{Colors.RESET} FILE        Save plot to file (supports .png, .pdf, .svg, .eps)
    {Colors.YELLOW}--gnu{Colors.RESET}                 Display plot in terminal (gnuplot-style, useful for HPC)
    {Colors.YELLOW}--no-display{Colors.RESET}          Don't display plot (useful for SSH/remote)
    {Colors.YELLOW}--verbose, -v{Colors.RESET}         Show detailed information
    {Colors.YELLOW}--examples{Colors.RESET}            Show usage examples
    {Colors.YELLOW}--help, -h{Colors.RESET}            Show this help message
""")


def print_plot_examples():
    """Print plot command examples."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}Plot Command Examples{Colors.RESET}

{Colors.BOLD}Basic Time Series:{Colors.RESET}
    plot CS4SG1U1 --node 100 --data-type displacement
    plot CS4SG1U1 --node 100 --data-type force --component y

{Colors.BOLD}With Time Range:{Colors.RESET}
    plot CS4SG1U1 --node 100 --data-type displacement \\
        --start-time 10.0 --end-time 50.0

{Colors.BOLD}Styled Plots:{Colors.RESET}
    # Red solid line with circles, width 2
    plot CS4SG1U1 --node 100 --data-type displacement \\
        --plot-style "red,2,-,o" --title "Node 100|16"

    # Blue dashed line, no markers
    plot CS4SG1U1 --node 100 --data-type displacement \\
        --plot-style "blue,1.5,--,None"

    # Green dash-dot line with squares
    plot CS4SG1U1 --node 100 --data-type displacement \\
        --plot-style "green,2,-.,s"

    # Custom hex color with stars
    plot CS4SG1U1 --node 100 --data-type displacement \\
        --plot-style "#FF5733,1.5,-,*"

{Colors.BOLD}Enhanced Labels with LaTeX:{Colors.RESET}
    # Simple labels with custom font size
    plot CS4SG1U1 --node 100 --data-type displacement \\
        --title "Displacement Analysis|18" \\
        --xlabel "Time (s)|14" --ylabel "Displacement (m)|14"

    # LaTeX rendering for mathematical expressions
    plot CS4SG1U1 --node 100 --data-type displacement \\
        --title "Node Displacement $\\Delta x$|16|True" \\
        --xlabel 'Time $t$ (s)|14|True' \\
        --ylabel 'Displacement $\\delta$ (m)|14|True'

    # Mixed: LaTeX for ylabel, simple for others
    plot CS4SG1U1 --node 100 --data-type displacement \\
        --title "Analysis Results|16" \\
        --ylabel 'Force $F_x$ (N)|14|True'

{Colors.BOLD}Custom Fonts (Academic Style):{Colors.RESET}
    # Times-like serif font (professional publications)
    plot CS4SG1U1 --node 100 --data-type displacement \\
        --component y --fontname serif \\
        --title "Case Study|16" --ylabel "Displacement (m)|14"

    # DejaVu Serif (Times New Roman alternative)
    plot CS4SG1U1 --node 100 --data-type displacement \\
        --component y --fontname "DejaVu Serif" \\
        --title "Analysis|16"

    # Liberation Serif (metrically compatible with Times New Roman)
    plot CS4SG1U1 --node 100 --data-type displacement \\
        --component y --fontname "Liberation Serif"

{Colors.BOLD}FFT Analysis:{Colors.RESET}
    plot CS4SG1U1 --node 100 --data-type displacement \\
        --plot-type fft --component y

{Colors.BOLD}2D Trajectory:{Colors.RESET}
    plot CS4SG1U1 --node 100 --data-type displacement \\
        --plot-type traj2d --component x y

{Colors.BOLD}3D Trajectory:{Colors.RESET}
    plot CS4SG1U1 --node 100 --data-type displacement \\
        --plot-type traj3d --component x y z

{Colors.BOLD}Save to File (Multiple Formats):{Colors.RESET}
    # PNG (default, good for presentations)
    plot CS4SG1U1 --node 100 --data-type displacement \\
        --output plot.png

    # PDF (vector format, best for publications)
    plot CS4SG1U1 --node 100 --data-type displacement \\
        --output plot.pdf

    # SVG (scalable vector graphics)
    plot CS4SG1U1 --node 100 --data-type displacement \\
        --output plot.svg

{Colors.BOLD}Terminal Plot (HPC/SSH Usage):{Colors.RESET}
    # Display plot directly in terminal (requires plotext)
    plot CS4SG1U1 --node 100 --data-type displacement \\
        --component y --gnu

    # Terminal plot + save to file
    plot CS4SG1U1 --node 100 --data-type displacement \\
        --component y --gnu --output plot.pdf

{Colors.BOLD}Remote/SSH Usage (No Display):{Colors.RESET}
    # Automatically headless when using --output
    plot CS4SG1U1 --node 100 --data-type displacement \\
        --component y --output result.png

    # Or explicitly use --no-display
    plot CS4SG1U1 --node 100 --data-type displacement \\
        --component y --no-display

{Colors.BOLD}Using YAML Configuration:{Colors.RESET}
    plot --input-file plot_config.yaml
""")
