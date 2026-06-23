"""Help text for `field iso`."""

from ....utils.colors import Colors


def print_iso_help():
    print(f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow Field Iso Command{Colors.RESET}

Render isosurface PNGs from PLT field data (Q-criterion or any scalar), coloured
by another variable. Uses {Colors.BOLD}pyvista{Colors.RESET} (no Tecplot/ParaView). Given a case,
the PLT is auto-converted to a cached .vtu first.

{Colors.BOLD}USAGE:{Colors.RESET}
    flexflow field iso [<case>] [options]

{Colors.BOLD}INPUT (one of):{Colors.RESET}
    {Colors.YELLOW}<case> [--timestep N]{Colors.RESET}   Convert the case's PLT (latest, or step N) and render
    {Colors.YELLOW}--vtu PATH{Colors.RESET}             Render an existing .vtu directly
    {Colors.YELLOW}--config FILE{Colors.RESET}          YAML config (input.vtu may be set there)

{Colors.BOLD}OPTIONS:{Colors.RESET}  ({Colors.DIM}override the config{Colors.RESET})
    {Colors.YELLOW}--contour NAME{Colors.RESET}         Scalar to contour            (default: QCriterion)
    {Colors.YELLOW}--iso V [V ...]{Colors.RESET}        Isosurface value(s)          (default: 20)
    {Colors.YELLOW}--color NAME{Colors.RESET}           Scalar to colour by          (default: U; use W for z-flow)
    {Colors.YELLOW}--out PREFIX{Colors.RESET}           Output prefix for .vtp + PNGs
    {Colors.YELLOW}--nen N{Colors.RESET}                Force nodes-per-element when converting (e.g. 8 for bricks)
    {Colors.YELLOW}--zone NAME{Colors.RESET}            Zone to render (default: first volume zone)

{Colors.BOLD}CONFIG:{Colors.RESET}
    {Colors.YELLOW}--config FILE{Colors.RESET}          YAML config for full control: background, resolution,
                           domain crop, threshold, camera views, saved-camera reuse
    {Colors.YELLOW}--write-template PATH{Colors.RESET}  Write a documented YAML config template and exit

{Colors.BOLD}MISC:{Colors.RESET}
    {Colors.YELLOW}--verbose, -v{Colors.RESET}          Verbose output
    {Colors.YELLOW}--help, -h{Colors.RESET}             Show this help message

{Colors.BOLD}EXAMPLES:{Colors.RESET}

  {Colors.BOLD}Render a case timestep:{Colors.RESET}
    flexflow field iso myCase --timestep 100 --iso 20 --color W

  {Colors.BOLD}Render an existing .vtu with several iso values:{Colors.RESET}
    flexflow field iso --vtu field.vtu --contour QCriterion --iso 5 50 --out wake

  {Colors.BOLD}Write then use a config template:{Colors.RESET}
    flexflow field iso --write-template iso.yml
    flexflow field iso myCase --config iso.yml

{Colors.BOLD}CAMERA REUSE:{Colors.RESET}
    {Colors.DIM}A view's `camera_file:` accepts a ParaView "Save State" .pvsm/.py or a
    saved-frame .yml, so a view set up on one file applies to any other.{Colors.RESET}

{Colors.BOLD}NOTES:{Colors.RESET}
    {Colors.DIM}- QCriterion is unnormalised; pick --iso a couple orders below its max for
      clean vortex tubes (a value near 0 yields a dense, domain-filling sheet).
    - Flow in z -> colour by W; flow in x -> colour by U.{Colors.RESET}
""")
