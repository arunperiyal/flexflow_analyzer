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
    {Colors.YELLOW}wall_shear{Colors.RESET}            Viscous wall shear on every surface element, read
                          straight out of the vorticity the solver wrote
    {Colors.YELLOW}separation{Colors.RESET}            Where the flow leaves the surface, per spanwise
                          section per timestep. A reduction over what
                          wall_shear wrote -- no PLT is opened
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

{Colors.BOLD}FOR separation:{Colors.RESET}
    {Colors.YELLOW}--body NAME{Colors.RESET}           Whose {Colors.YELLOW}<body>.wall_shear/{Colors.RESET} tables to reduce. {Colors.YELLOW}--zone{Colors.RESET}
                          works too; both resolve through domain.yml.
    {Colors.YELLOW}--azimuthal N{Colors.RESET}         Bins around each section (default 36, i.e. 10 deg),
                          with theta = 0 at a bin {Colors.BOLD}centre{Colors.RESET}. The bare mesh has 128
                          facets a ring, so 36 gives ~3.5 a bin; 72 needs a
                          finer surface than that to mean anything.
    {Colors.YELLOW}--sectional N{Colors.RESET}         Spanwise sections (default 48). Use the same count
                          as force_coeff and the two tables line up row for row.
                          Takes no timestep range: it reduces every
                          elements_<step>.csv it finds.

{Colors.BOLD}OPTIONAL:{Colors.RESET}
    {Colors.YELLOW}--output [NAME]{Colors.RESET}       A bare NAME makes a directory under the case holding
                          one table per timestep plus summary.csv -- the whole run
                          split up, with nothing to script. Or give an extension
                          for a single file: .csv (one combined table), and for
                          force also .vtu/.vtk (surface mesh carrying the values
                          as cell data) or .pvd (a mesh series).
                          {Colors.BOLD}Left out entirely{Colors.RESET} -- or given with no NAME -- it is
                          {Colors.YELLOW}<body>.forces{Colors.RESET} / {Colors.YELLOW}<body>.force_coeff{Colors.RESET} in the case
                          directory. One place per body, so a case with several
                          does not collide, and a case organises itself without
                          anyone having to choose a name. The body is the one
                          --zone names, through domain.yml where there is one.
                          The totals per timestep are printed either way.
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

    It also carries the run's {Colors.BOLD}'#' header{Colors.RESET}: rho, U, q, D, L, the three axes
    and what each table divides by, all as {Colors.BOLD}values{Colors.RESET}. The per-timestep
    tables do not repeat it -- the reference state belongs to the run, not to a
    timestep -- but each carries the one line needed to read its own numbers.

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

    Every one of those is written into summary.csv's '#' header as a {Colors.BOLD}value{Colors.RESET} --
    `rho: 1000`, not `rho: from domain.yml`. The two are different claims: a
    domain.yml can be edited afterwards, and a header pointing at one says nothing
    about the numbers underneath it. Which file each was read from is reported by
    {Colors.YELLOW}-v{Colors.RESET} instead, where it is a question about this run rather than about
    the table.

    A Cd without those numbers cannot be checked; with them it can, years later.

    Nothing is defaulted. A missing radius or velocity is an error naming the
    command that sets it, because a Cd normalised by a guessed diameter is wrong
    by exactly the factor nobody notices.

{Colors.BOLD}WALL SHEAR, AND WHY IT NEEDS NO GRADIENT:{Colors.RESET}

    At a no-slip wall the velocity vanishes on the surface, so every tangential
    derivative of it vanishes too and the only surviving gradient is the one
    normal to the wall. The stress collapses to an {Colors.BOLD}identity{Colors.RESET}:

        tau_w = mu_eff * (omega x n)

    which is exact, not a reconstruction. `xVor`, `yVor` and `zVor` are already
    in the PLT, so nothing has to be differentiated at the one place an
    unstructured mesh is worst conditioned -- and nothing outside numpy is loaded
    to do it.

    mu comes from the .def, through the same chain as the density. mu_eff is
    mu + rho*eddy, and every table says what the largest eddy viscosity at the
    wall actually was, so "mu_eff = mu here" is a measurement rather than a hope.

{Colors.BOLD}THETA, AND WHERE A SECTION'S CENTRE IS:{Colors.RESET}

    {Colors.YELLOW}theta = 0{Colors.RESET} at the forward stagnation point -- the upstream side, facing
    the free stream -- increasing towards the lift direction, in (-180, 180].
    So the two shear layers come out as a positive and a negative branch.

    A section's centre is the {Colors.BOLD}declared{Colors.RESET} axis (domain.yml origin + station *
    axis) plus the mean displacement around that ring, not the mean of the ring's
    own coordinates. On a round body the two agree. On a grooved one the facets
    are not symmetric about the axis, so the coordinate mean drifts off it by an
    amount that varies with angle -- which reads as a separation shift that is not
    there. The displacement field is smooth whatever the surface looks like.

    Both conventions are written into every table's header, because a reader that
    has to guess them will guess one of them wrong.

{Colors.BOLD}FINDING THE SEPARATION ANGLE:{Colors.RESET}

    Cf_theta is zero at the forward stagnation point as well as at separation, so
    the first zero going outward is the {Colors.BOLD}wrong one{Colors.RESET}. Each branch is walked
    outward from the front, its peak found, and the first sign change taken
    {Colors.BOLD}after{Colors.RESET} that -- which also survives the stagnation point not sitting at
    theta = 0, as it does not on a body that is deflecting and shedding.

    The crossing is interpolated between bins: quantising it to the bin width
    puts a 10-degree staircase in a quantity whose whole interest is that it moves
    a degree or two along the span.

    A side that never reverses is {Colors.YELLOW}nan{Colors.RESET}, which is an answer. Alongside it,
    {Colors.YELLOW}reversed_fraction{Colors.RESET} -- the area-weighted share of the perimeter with
    Cf_theta < 0 -- is one number per section that survives an ambiguous crossing.

{Colors.BOLD}HOW NORMALS ARE ORIENTED:{Colors.RESET}

    A body is a hole in the volume mesh, so each surface element belongs to
    exactly one volume cell and that cell is on the fluid side -- the normal
    facing it points out of the body. Elements with no adjacent cell fall back to
    orienting the whole zone by its enclosed volume, and that is reported.

{Colors.BOLD}EXAMPLES:{Colors.RESET}

  {Colors.BOLD}One element table per timestep, named after the body:{Colors.RESET}
    flexflow field compute force BR0SG0U1P0 --zone cyl --t1 50 --t2 5000 --freq 50
      # -> <case>/cyl.forces/elements_50.csv .. + summary.csv

  {Colors.BOLD}Somewhere else instead:{Colors.RESET}
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

  {Colors.BOLD}Separation angle along the span:{Colors.RESET}
    flexflow field compute wall_shear BR0SG0U1P0 --zone cyl --t1 50 --t2 5000 --freq 50
      {Colors.DIM}# -> <case>/cyl.wall_shear/elements_50.csv .. + summary.csv{Colors.RESET}
    flexflow field compute separation BR0SG0U1P0 --body cyl --sectional 48
      {Colors.DIM}# -> <case>/cyl.separation/azimuthal_50.csv .. + separation.csv{Colors.RESET}
    {Colors.DIM}(re-bin as often as you like: separation opens no PLT){Colors.RESET}

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
