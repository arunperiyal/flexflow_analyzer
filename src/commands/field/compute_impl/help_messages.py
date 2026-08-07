"""Help messages for field compute command."""

from ....utils.colors import Colors


def print_compute_help():
    """Print field compute command help."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow Field Compute Command{Colors.RESET}

Quantities derived from a surface zone's own elements (Tecplot-free).

{Colors.BOLD}USAGE:{Colors.RESET}
    flexflow field compute <quantity> <case_dir> --zone ZONE [options]

{Colors.BOLD}QUANTITIES:{Colors.RESET}
    {Colors.YELLOW}force{Colors.RESET}                 Pressure force on every surface element:
                          its area, its outward normal, and -p n dA

{Colors.BOLD}REQUIRED:{Colors.RESET}
    {Colors.YELLOW}--zone ZONE{Colors.RESET}           Surface zone to integrate over (e.g. cyl).
                          Must be a triangle/quad zone -- a volume zone is refused.

{Colors.BOLD}TIMESTEP SELECTION (one of):{Colors.RESET}
    {Colors.YELLOW}--timestep STEP{Colors.RESET}       A single timestep
    {Colors.YELLOW}--t1 STEP{Colors.RESET}             A single step (alone), or the start of a range
    {Colors.YELLOW}--t2 STEP{Colors.RESET}             End of a range (one row per element per step)
    {Colors.YELLOW}--freq N{Colors.RESET}              With --t1/--t2: keep steps that are multiples of N

{Colors.BOLD}OPTIONAL:{Colors.RESET}
    {Colors.YELLOW}--output NAME{Colors.RESET}         .csv (per-element table), .vtu/.vtk (surface mesh
                          carrying the values as cell data, one step), or .pvd
                          (a mesh series for a range). Without it you still get
                          the integrated totals per timestep on screen.
    {Colors.YELLOW}--pressure VAR{Colors.RESET}        Pressure variable name (default: Pressure)
    {Colors.YELLOW}--nen N{Colors.RESET}               Force nodes-per-element on the volume zone
    {Colors.YELLOW}--no-progress{Colors.RESET}         Do not draw the progress bar
    {Colors.YELLOW}--verbose, -v{Colors.RESET}         Show what was matched and how normals were oriented
    {Colors.YELLOW}--help, -h{Colors.RESET}            Show this help message

{Colors.BOLD}OUTPUT COLUMNS (.csv):{Colors.RESET}

    timestep, element, x, y, z, area, nx, ny, nz, <Pressure>, Fx, Fy, Fz

    {Colors.YELLOW}element{Colors.RESET}     index into the zone's element list -- stable across
                timesteps, so a facet can be followed through the run
    {Colors.YELLOW}x, y, z{Colors.RESET}     element centroid (it moves: the mesh deforms)
    {Colors.YELLOW}area{Colors.RESET}        element area, from the mesh -- no assumed cross-section
    {Colors.YELLOW}nx, ny, nz{Colors.RESET}  unit normal pointing OUT of the body
    {Colors.YELLOW}Fx, Fy, Fz{Colors.RESET}  pressure force on the element, -p n dA

{Colors.BOLD}WHAT THIS DELIBERATELY DOES NOT DO:{Colors.RESET}

    No Cd/Cl, no sectional binning, no reference length. Those need a flow
    direction and a reference area that are yours to choose, and every one of
    them is a sum over these rows:

      Cd = sum(Fz) / (0.5 rho U^2 * A_ref)        drag along the flow direction
      sectional: group rows by element centroid along the span, then the same

{Colors.BOLD}HOW NORMALS ARE ORIENTED:{Colors.RESET}

    A body is a hole in the volume mesh, so each surface element belongs to
    exactly one volume cell and that cell is on the fluid side -- the normal
    facing it points out of the body. Elements with no adjacent cell fall back to
    orienting the whole zone by its enclosed volume, and that is reported.

{Colors.BOLD}EXAMPLES:{Colors.RESET}

  {Colors.BOLD}Totals on screen, nothing written:{Colors.RESET}
    flexflow field compute force BR0SG0U1P0 --zone cyl --timestep 100

  {Colors.BOLD}Per-element forces over a run:{Colors.RESET}
    flexflow field compute force BR0SG0U1P0 --zone cyl --t1 50 --t2 5000 --freq 50 \\
      --output cyl_forces.csv

  {Colors.BOLD}Force distribution to view in ParaView:{Colors.RESET}
    flexflow field compute force BR0SG0U1P0 --zone cyl --t1 50 --t2 5000 \\
      --output cyl_forces.pvd

{Colors.BOLD}NOTES:{Colors.RESET}

  - Pressure force only. Viscous skin friction needs wall-normal velocity
    gradients from the volume zone and is not included.
  - Areas and normals come from the mesh, so a grooved or otherwise non-circular
    section needs no special handling.
  - Fx is ~0 for a plain cylinder whose facets all face radially; it carries
    information only where facets tilt along the span.
  - The surface-to-volume mapping is built once and reused, since the element
    list does not change between timesteps; if it ever does, that is reported.

""")
