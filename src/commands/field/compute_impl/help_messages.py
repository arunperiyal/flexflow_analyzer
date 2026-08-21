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
    {Colors.YELLOW}force_coeff{Colors.RESET}           Cd and Cl for the body, and for each spanwise
                          section of it with --sectional. Same forces, divided
                          by a reference state taken from domain.yml and the .def
    {Colors.YELLOW}lambda2{Colors.RESET}               Vortex criterion as a nodal field over the volume
                          (needs --output; writes a mesh, not a table)

{Colors.BOLD}REQUIRED:{Colors.RESET}
    {Colors.YELLOW}--zone ZONE{Colors.RESET}           Surface zone to integrate over (e.g. cyl).
                          Must be a triangle/quad zone -- a volume zone is refused.

{Colors.BOLD}TIMESTEP SELECTION (one of):{Colors.RESET}
    {Colors.YELLOW}--timestep STEP{Colors.RESET}       A single timestep
    {Colors.YELLOW}--t1 STEP{Colors.RESET}             A single step (alone), or the start of a range
    {Colors.YELLOW}--t2 STEP{Colors.RESET}             End of a range (one row per element per step)
    {Colors.YELLOW}--freq N{Colors.RESET}              With --t1/--t2: keep steps that are multiples of N

{Colors.BOLD}FOR force_coeff:{Colors.RESET}
    {Colors.YELLOW}--sectional N{Colors.RESET}         Cut the body into N equal slices along its span and
                          write Cd/Cl for each, one table per timestep. Without
                          it you get the whole-body Cd/Cl series only.
    {Colors.YELLOW}--direction AXIS{Colors.RESET}      Axis the slices are cut along.
                          {Colors.DIM}Default: the body's own axis from domain.yml{Colors.RESET}
    {Colors.YELLOW}--flow AXIS{Colors.RESET}           Free-stream direction -- the one drag is measured
                          along; lift is perpendicular to it and to the span.
                          {Colors.DIM}Default: the field's velocity in domain.yml{Colors.RESET}
                          Both take an axis ({Colors.YELLOW}x -x y -y z -z{Colors.RESET}) or a vector '[1, 0, 0]'.

{Colors.BOLD}OPTIONAL:{Colors.RESET}
    {Colors.YELLOW}--output [NAME]{Colors.RESET}       A bare NAME makes a directory under the case holding
                          one table per timestep plus summary.csv -- the whole run
                          split up, with nothing to script. Or give an extension
                          for a single file: .csv (one combined table), and for
                          force also .vtu/.vtk (surface mesh carrying the values
                          as cell data) or .pvd (a mesh series).
                          Given with {Colors.BOLD}no NAME{Colors.RESET} it is {Colors.YELLOW}<body>.forces{Colors.RESET} /
                          {Colors.YELLOW}<body>.force_coeff{Colors.RESET} in the case directory -- one place
                          per body, so a case with several does not collide.
                          force_coeff writes there by default, since its tables
                          are the result; force without --output prints the
                          totals per timestep and writes nothing.
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

{Colors.BOLD}OUTPUT COLUMNS (force_coeff):{Colors.RESET}

    {Colors.BOLD}sectional_<step>.csv{Colors.RESET}, one row per slice:

    section, station, Fx, Fy, Fz, Fd, Fl, Cd, Cl, area, elements

    {Colors.YELLOW}station{Colors.RESET}     where the slice's elements actually sit along the span --
                not the nominal slice centre, which differs by half a width
    {Colors.YELLOW}Fd, Fl{Colors.RESET}      force resolved along the flow, and perpendicular to it
    {Colors.YELLOW}Cd, Cl{Colors.RESET}      Fd, Fl / (q * D * dx), with q = 0.5 rho U^2
    {Colors.YELLOW}area{Colors.RESET}        wetted area of the slice, from the mesh. The coefficients
                use the {Colors.BOLD}frontal{Colors.RESET} area D*dx, not this
    {Colors.YELLOW}elements{Colors.RESET}    facets in the slice; a warning is printed if any is empty

    {Colors.BOLD}summary.csv{Colors.RESET}, one row per timestep, is the whole body:
    timestep, elements, area, Fx, Fy, Fz, Fd, Fl, Cd, Cl -- normalised by D*L.

{Colors.BOLD}WHERE A COEFFICIENT'S NUMBERS COME FROM:{Colors.RESET}

    Cd = Fd / (0.5 rho U^2 A) needs four things the PLT does not hold. None of
    them has to be typed, because the case already says all of them:

      {Colors.YELLOW}rho{Colors.RESET}          the .def, followed through its own chain of model names:
                   elementGroup -> elementProperty -> materialModel -> densityModel
      {Colors.YELLOW}U, flow{Colors.RESET}      domain.yml, the field's declared {Colors.YELLOW}velocity{Colors.RESET} -- its magnitude
                   is U, its direction is what drag is measured along.
                   --flow re-aims the direction; U stays the magnitude declared
      {Colors.YELLOW}D, L, axis{Colors.RESET}   domain.yml, the body's own geometry

    The free stream is {Colors.BOLD}declared, not read from the .def{Colors.RESET}. The nearest thing the
    .def has is initField( velocity ), and that is the initial condition: a case
    started from rest, or ramped up at the inlet, has one that says nothing about
    the flow the body ends up in. Right often enough to be trusted, wrong quietly
    enough to matter.

    Which body is decided by --zone, resolved through domain.yml -- by name,
    geotag or plttag, so any of the three finds it.

    Every one of those, and where it came from, is written into the '#' header of
    each table. A Cd without them cannot be checked; with them it can, years later.

    Nothing is defaulted. A missing radius or velocity is an error naming the
    command that sets it, because a Cd normalised by a guessed diameter is wrong
    by exactly the factor nobody notices.

{Colors.BOLD}HOW NORMALS ARE ORIENTED:{Colors.RESET}

    A body is a hole in the volume mesh, so each surface element belongs to
    exactly one volume cell and that cell is on the fluid side -- the normal
    facing it points out of the body. Elements with no adjacent cell fall back to
    orienting the whole zone by its enclosed volume, and that is reported.

{Colors.BOLD}EXAMPLES:{Colors.RESET}

  {Colors.BOLD}Totals on screen, nothing written:{Colors.RESET}
    flexflow field compute force BR0SG0U1P0 --zone cyl --timestep 100

  {Colors.BOLD}A run split into one file per timestep:{Colors.RESET}
    flexflow field compute force BR0SG0U1P0 --zone cyl --t1 50 --t2 5000 --freq 50 \\
      --output loads          # -> <case>/loads/elements_50.csv .. + summary.csv

  {Colors.BOLD}The same run as one combined table:{Colors.RESET}
    flexflow field compute force BR0SG0U1P0 --zone cyl --t1 50 --t2 5000 --freq 50 \\
      --output cyl_forces.csv

  {Colors.BOLD}Force distribution to view in ParaView:{Colors.RESET}
    flexflow field compute force BR0SG0U1P0 --zone cyl --t1 50 --t2 5000 \\
      --output cyl_forces.pvd

  {Colors.BOLD}Sectional Cd/Cl, one table per timestep:{Colors.RESET}
    flexflow case domain BR0SG0U1P0 --init            {Colors.DIM}# once{Colors.RESET}
    flexflow case domain body --name cyl --radius 0.5 {Colors.DIM}# the case states neither{Colors.RESET}
    flexflow case domain field --velocity 0,0,1
    flexflow field compute force_coeff BR0SG0U1P0 --zone cyl \\
      --t1 50 --t2 5000 --freq 50 --sectional 48
      {Colors.DIM}# -> <case>/cyl.force_coeff/sectional_50.csv .. + summary.csv{Colors.RESET}

  {Colors.BOLD}Whole-body Cd/Cl over time, nothing sectional:{Colors.RESET}
    flexflow field compute force_coeff BR0SG0U1P0 --zone cyl --t1 50 --t2 5000

  {Colors.BOLD}Section across the flow instead of along the body:{Colors.RESET}
    flexflow field compute force_coeff BR0SG0U1P0 --zone cyl --timestep 100 \\
      --sectional 20 --direction z --flow x

{Colors.BOLD}NOTES:{Colors.RESET}

  - Pressure force only. Viscous skin friction needs wall-normal velocity
    gradients from the volume zone and is not included.
  - Areas and normals come from the mesh, so a grooved or otherwise non-circular
    section needs no special handling.
  - Fx is ~0 for a plain cylinder whose facets all face radially; it carries
    information only where facets tilt along the span.
  - The surface-to-volume mapping is built once and reused, since the element
    list does not change between timesteps; if it ever does, that is reported.
  - So are the sections: element ids are stable, so a slice keeps the same facets
    as the body deflects, and the time series stays a series of one thing.
  - {Colors.BOLD}Cd and Cl are from pressure alone.{Colors.RESET} At low Reynolds number the missing
    skin friction is a real fraction of the drag; the tables say so in their
    header rather than leaving it to be remembered.

""")
