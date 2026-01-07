"""Help messages for compare command."""

from flexflow.utils.colors import Colors

def print_compare_help():
    """Print compare command help."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow Compare Command{Colors.RESET}

Compare data from multiple FlexFlow cases on a single plot.

{Colors.BOLD}USAGE:{Colors.RESET}
    flexflow compare {Colors.YELLOW}<case1> <case2>{Colors.RESET} [...] [options]
    flexflow compare {Colors.YELLOW}--input-file{Colors.RESET} <yaml_file>

{Colors.BOLD}REQUIRED OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--node{Colors.RESET} N              Node number to compare
    {Colors.YELLOW}--data-type{Colors.RESET} TYPE     Data type: displacement or force

{Colors.BOLD}PLOT OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--plot-type{Colors.RESET} TYPE     Plot type: time, fft, traj2d, traj3d (default: time)
    {Colors.YELLOW}--component{Colors.RESET} X [Y Z]  Components to plot (x, y, z)
    {Colors.YELLOW}--start-time{Colors.RESET} T       Start time for plot
    {Colors.YELLOW}--end-time{Colors.RESET} T         End time for plot

{Colors.BOLD}STYLING OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--plot-style{Colors.RESET} STYLES  Plot styles for each case, separated by |
                          Format per case: color,width,linestyle,marker
                          Example: "blue,2,-,o|red,2,--,s|green,2,-.,^"
                          Available linestyles: - (solid), -- (dashed), -. (dashdot), : (dotted)
                          Common markers: o, s, ^, v, *, +, x, D
    {Colors.YELLOW}--legend{Colors.RESET} LABELS      Custom legend labels separated by |
                          Example: "Case 1|Case 2|Case 3"
    {Colors.YELLOW}--legend-style{Colors.RESET} STYLE Legend style: position|fontsize|frameon|latex
                          Position: best, upper right, upper left, lower left, lower right,
                                   north, south, east, west, northeast, northwest, etc.
                          Example: "best|12|on|False" or "northeast|14|off|True"
    {Colors.YELLOW}--title{Colors.RESET} TEXT         Plot title (supports: "text|fontsize" or "text|fontsize|latex")
    {Colors.YELLOW}--xlabel{Colors.RESET} TEXT        X-axis label (supports: "text|fontsize" or "text|fontsize|latex")
    {Colors.YELLOW}--ylabel{Colors.RESET} TEXT        Y-axis label (supports: "text|fontsize" or "text|fontsize|latex")
    {Colors.YELLOW}--fontsize{Colors.RESET} N         Font size (default: 12)
    {Colors.YELLOW}--fontname{Colors.RESET} NAME      Font family (e.g., "Times New Roman", serif, Arial)

{Colors.BOLD}LAYOUT OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--subplot{Colors.RESET} LAYOUT      Create subplots instead of overlaying cases
                           Format: rows,columns (e.g., "2,2" for 2x2 grid)
                           Each case will be plotted in a separate subplot
    {Colors.YELLOW}--separate{Colors.RESET}            Create separate plot files for each case (overrides --subplot)
    {Colors.YELLOW}--output-prefix{Colors.RESET} TEXT  Prefix for separate plot filenames (default: "case_")
                           Example: "comparison_" → comparison_CS4SG1U1.png, etc.
    {Colors.YELLOW}--output-format{Colors.RESET} FMT   Output format for separate plots: png, pdf, svg
                           Default: png

{Colors.BOLD}OUTPUT OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--output{Colors.RESET} FILE        Save plot to file (auto-enables headless mode)
                           For combined plot mode only
    {Colors.YELLOW}--no-display{Colors.RESET}          Don't display plot (useful for SSH/remote)
    {Colors.YELLOW}--verbose, -v{Colors.RESET}         Show detailed information
    {Colors.YELLOW}--examples{Colors.RESET}            Show usage examples
    {Colors.YELLOW}--help, -h{Colors.RESET}            Show this help message
""")


def print_compare_examples():
    """Print compare command examples."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}Compare Command Examples{Colors.RESET}

{Colors.BOLD}Basic Comparison:{Colors.RESET}
    flexflow compare CS4SG1U1 CS4SG2U1 --node 100 --data-type displacement

{Colors.BOLD}Multiple Cases:{Colors.RESET}
    flexflow compare CS4SG1U1 CS4SG2U1 CS4SG3U1 --node 100 --data-type force

{Colors.BOLD}With Styling:{Colors.RESET}
    flexflow compare CS4SG1U1 CS4SG2U1 --node 100 --data-type displacement \\
        --component y --plot-style "blue,2,-,o|red,2,--,s" \\
        --legend "Configuration 1|Configuration 2" \\
        --title "Case Comparison|16" --fontname "Times New Roman"

{Colors.BOLD}Three Cases with Different Styles:{Colors.RESET}
    flexflow compare CS4SG1U1 CS4SG2U1 CS4SG3U1 --node 100 \\
        --data-type displacement --component y \\
        --plot-style "blue,2,-,o|red,2,--,s|green,2,-.,^" \\
        --legend "Case A|Case B|Case C" \\
        --output comparison.pdf

{Colors.BOLD}Save to File (Remote/SSH):{Colors.RESET}
    flexflow compare CS4SG1U1 CS4SG2U1 --node 100 --data-type displacement \\
        --component y --output comparison.png --no-display

{Colors.BOLD}Subplot Layout:{Colors.RESET}
    flexflow compare CS4SG1U1 CS4SG2U1 CS4SG3U1 CS4SG4U1 --node 100 \\
        --data-type displacement --component y --subplot "2,2" \\
        --legend "Case 1|Case 2|Case 3|Case 4" \\
        --output comparison_subplots.pdf

{Colors.BOLD}Separate Plots for Each Case:{Colors.RESET}
    flexflow compare CS4SG1U1 CS4SG2U1 CS4SG3U1 --node 100 \\
        --data-type displacement --component y --separate \\
        --output-prefix "result_" --output-format pdf
    # Creates: result_CS4SG1U1.pdf, result_CS4SG2U1.pdf, result_CS4SG3U1.pdf

{Colors.BOLD}Using YAML Configuration:{Colors.RESET}
    flexflow compare --input-file comparison.yaml
""")
