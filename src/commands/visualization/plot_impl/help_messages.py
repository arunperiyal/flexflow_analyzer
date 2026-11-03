"""Help messages for plot command."""

from src.utils.colors import Colors

def print_plot_help():
    """Print plot command help."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow Plot Command{Colors.RESET}

Plot the history of a variable -- the columns `data table` shows for the
same --var, node and window.

{Colors.BOLD}USAGE:{Colors.RESET}
    plot {Colors.YELLOW}<case_directory>{Colors.RESET} --var NAME [options]
    use case:CS4SG1U1 var:dy; plot          {Colors.DIM}# case and var from the context{Colors.RESET}
    plot {Colors.YELLOW}--input-file{Colors.RESET} <yaml_file>

{Colors.BOLD}WHAT TO PLOT:{Colors.RESET}
    {Colors.YELLOW}--var{Colors.RESET} NAME           Variable or component, as in data table (default: use var:)
                            {Colors.DIM}dy, aleDisp_y      one component{Colors.RESET}
                            {Colors.DIM}d, aleDisp         every component, one panel each{Colors.RESET}
                            {Colors.DIM}tty, totTrac_y     surface (oisd) output{Colors.RESET}
                            {Colors.DIM}pd, pv, pa         pendulum pendDisp, pendVel, pendAccel{Colors.RESET}
                            Repeat or comma-separate: --var dx,dy. `data show` lists the names.
    {Colors.YELLOW}--node{Colors.RESET} N              Node to read (default: 0; use node:N)
    {Colors.YELLOW}--othid{Colors.RESET} ID            othId in the othd files (default: the first; use othid:N)
    {Colors.YELLOW}--osgid{Colors.RESET} ID            osgId in the oisd files (default: the first; use osgid:N)
    {Colors.YELLOW}--othd{Colors.RESET} / {Colors.YELLOW}--oisd{Colors.RESET}       Look in one kind of file only

{Colors.BOLD}PLOT OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--plot-type{Colors.RESET} TYPE     time (default), fft, traj2d, traj3d
                            {Colors.DIM}fft:{Colors.RESET} amplitude spectrum per column, peak in the legend
                            {Colors.DIM}traj2d/traj3d:{Colors.RESET} the first 2/3 columns against each other
                            (--var d, or --var dx,dy)
    {Colors.YELLOW}--t1{Colors.RESET} TSID            First tsId, also --start-step (use t1:)
    {Colors.YELLOW}--t2{Colors.RESET} TSID            Last tsId, also --end-step (use t2:)
    {Colors.YELLOW}--last{Colors.RESET} N             Only the last N steps of that window (use last:N)
    {Colors.YELLOW}--start-time{Colors.RESET} T       Start time, on top of the tsIds
    {Colors.YELLOW}--end-time{Colors.RESET} T         End time
    {Colors.YELLOW}--restart{Colors.RESET}             Mark each restart recorded in .restarts (by case
                            organise history) with a grey dashed line (time plots)

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
    plot CS4SG1U1 --var dy --node 100
    plot CS4SG1U1 --var d --node 100           # dx, dy, dz in three panels
    plot CS4SG1U1 --var tty                    # totTrac_y from the oisd
    use case:CS4SG1U1 node:100 var:dy; plot    # the same from the context

{Colors.BOLD}A Window:{Colors.RESET}
    plot CS4SG1U1 --var dy --t1 2000 --t2 4000
    plot CS4SG1U1 --var dy --last 1000
    plot CS4SG1U1 --var dy --start-time 10.0 --end-time 50.0

{Colors.BOLD}FFT and Trajectories:{Colors.RESET}
    plot CS4SG1U1 --var dy --plot-type fft --last 2000
    plot CS4SG1U1 --var d --plot-type traj2d    # dx against dy
    plot CS4SG1U1 --var d --plot-type traj3d

{Colors.BOLD}Pendulum:{Colors.RESET}
    plot CS4SG1U1 --var pd                      # pendDisp
    plot CS4SG1U1 --var pd,pv,pa                # all three, one panel each
    plot CS4SG1U1 --var pd --plot-type fft

{Colors.BOLD}Styled Plots:{Colors.RESET}
    # Red solid line with circles, width 2
    plot CS4SG1U1 --var dy --plot-style "red,2,-,o" --title "Node 100|16"
    # Custom hex color with stars
    plot CS4SG1U1 --var dy --plot-style "#FF5733,1.5,-,*"

{Colors.BOLD}Labels with LaTeX:{Colors.RESET}
    plot CS4SG1U1 --var dy \\
        --title "Node Displacement $\\Delta y$|16|True" \\
        --xlabel 'Time $t$ (s)|14|True' \\
        --ylabel 'Displacement $\\delta$ (m)|14|True'

{Colors.BOLD}Fonts:{Colors.RESET}
    plot CS4SG1U1 --var dy --fontname serif --title "Case Study|16"
    plot CS4SG1U1 --var dy --fontname "Liberation Serif"

{Colors.BOLD}Output:{Colors.RESET}
    plot CS4SG1U1 --var dy --output plot.pdf    # .png, .pdf, .svg, .eps
    plot CS4SG1U1 --var dy --gnu                # in the terminal (plotext)
    plot CS4SG1U1 --var dy --no-display

{Colors.BOLD}Using YAML Configuration:{Colors.RESET}
    plot --input-file plot_config.yaml
""")
