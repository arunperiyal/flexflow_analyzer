"""Help messages for field extract command."""

from ....utils.colors import Colors


def print_extract_help():
    """Print field extract command help."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow Field Extract Command{Colors.RESET}

Extract nodal data from binary PLT files to CSV (Tecplot-free; pure numpy).

{Colors.BOLD}USAGE:{Colors.RESET}
    flexflow field extract <case_dir> [options]

{Colors.BOLD}ARGUMENTS:{Colors.RESET}
    {Colors.YELLOW}case_dir{Colors.RESET}              Path to case directory containing binary/ folder

{Colors.BOLD}REQUIRED OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--variables VAR1,VAR2{Colors.RESET}  Comma-separated list of variables to extract
                             (e.g., Y, X,Y,Z, U,V,W)
    {Colors.YELLOW}--zone ZONE{Colors.RESET}            Zone name to extract from (e.g., FIELD, BODY)

{Colors.BOLD}TIMESTEP SELECTION (one of):{Colors.RESET}
    {Colors.YELLOW}--timestep STEP{Colors.RESET}        A single timestep (e.g., 1000)
    {Colors.YELLOW}--t1 STEP{Colors.RESET}              A single step (alone), or the start of a range
    {Colors.YELLOW}--t2 STEP{Colors.RESET}              End of a range; --t1..--t2 extracts every PLT in
                             that range into ONE file with a 'timestep' column/array
    {Colors.YELLOW}--freq N{Colors.RESET}               With --t1/--t2: keep only steps that are multiples of N
    {Colors.DIM}Setting the t1/t2/freq context (use t1:.. t2:.. freq:..) supplies these automatically.{Colors.RESET}

    {Colors.YELLOW}--output NAME{Colors.RESET}          (required, except with --probe) Output; format from the extension:
                             .csv      tabular point values (range -> 'timestep' column)
                             .vtu/.vtk a trimmed MESH with only the selected vars
                                       (cells kept -> contourable in ParaView; one step)
                             .pvd      time series: one <stem>_<step>.vtu per step
                                       + the .pvd collection (for a --t1/--t2 range)
                             {Colors.DIM}A bare NAME (no extension) makes a directory NAME/ holding the
                             outputs (NAME/NAME.pvd + per-step .vtu for a range, else
                             NAME/NAME.vtu). Relative paths go under the case directory.
                             Alias: --output-file{Colors.RESET}

{Colors.BOLD}OPTIONAL:{Colors.RESET}
    {Colors.YELLOW}--nen N{Colors.RESET}                Force nodes-per-element when the PLT header
                             mislabels the element type (e.g. --nen 8 for bricks)
    {Colors.YELLOW}--verbose, -v{Colors.RESET}          Show detailed extraction progress (per-step lines
                             instead of the progress bar)
    {Colors.YELLOW}--no-progress{Colors.RESET}          Do not draw the progress bar
    {Colors.YELLOW}--help, -h{Colors.RESET}             Show this help message

    {Colors.DIM}A progress bar is drawn while stepping through timesteps (a spinner for a
    single step), so a long extraction visibly makes headway. It is skipped when
    output is redirected, with --no-progress, and with --verbose.{Colors.RESET}

{Colors.BOLD}POINT PROBES:{Colors.RESET}
    Sample the variables at fixed points instead of over a region -- the usual
    way to pull a time signal (velocity in the wake, pressure at a gauge point)
    out of a run.

    {Colors.YELLOW}--probe X,Y,Z{Colors.RESET}          Sample at a point; repeat the flag for more probes,
                             or separate them with ';' in one flag. Give X,Y only
                             for a 2D mesh -- Z is then ignored when matching.
    {Colors.YELLOW}--interpolate{Colors.RESET}          Interpolate inside the element containing the probe
                             instead of taking the nearest node (needs pyvista)
    {Colors.YELLOW}--probe-tol TOL{Colors.RESET}        Slack on the inside-domain check, for a probe meant
                             to sit exactly on a boundary (default 0)

    Each probe is checked against the zone's coordinate bounds before any data is
    read, and the requested variables are checked against the zone. Points are
    located again at every step, so a moving or deforming mesh is followed.

    {Colors.BOLD}Nearest node{Colors.RESET} (default) reports the value at the closest mesh node, and
    the output carries that node's index, coordinates and its distance from the
    probe -- so you can see exactly what was sampled.
    {Colors.BOLD}--interpolate{Colors.RESET} reports the value at the point itself, linearly
    interpolated inside the element holding it (the same as ParaView's "Probe
    Location"). It needs connectivity, so a volume zone, and replaces the node
    columns with {Colors.YELLOW}source{Colors.RESET}, which says per row where the value came from:
        {Colors.YELLOW}cell{Colors.RESET}    interpolated inside the element containing the probe
        {Colors.YELLOW}nudged{Colors.RESET}  the probe sat on a wall, a hair outside the faceted
                boundary, so it was stepped a fraction of a cell inward to land
                inside an element (the displacement is reported)
        {Colors.YELLOW}node{Colors.RESET}    no element contains the point -- it is in a hole of the
                mesh, usually inside the structure -- so the nearest node's
                value was used instead

    A probe returning {Colors.YELLOW}node{Colors.RESET} for every step is the sign of a point placed
    inside a body rather than in the fluid. Check the warning: it reports how far
    the nearest node is in units of the mean node spacing.

    Output is a table of point values: {Colors.YELLOW}--output NAME.csv{Colors.RESET}, or no --output at all to
    print the table on screen. The probe coordinates are not repeated on every
    row; they head the file as '#' comment lines together with the case, zone and
    sampling method. Load it with {Colors.YELLOW}pandas.read_csv(path, comment='#'){Colors.RESET};
    numpy's loadtxt needs {Colors.YELLOW}skiprows{Colors.RESET} set past the block, as it counts the '#'
    lines. The x/y/z box flags do not apply to probes.

{Colors.BOLD}SUBDOMAIN EXTRACTION:{Colors.RESET}
    Extract data only from a specific spatial region using coordinate bounds.
    Supports 2D (X,Y) and 3D (X,Y,Z) filtering.

    {Colors.YELLOW}--xmin VALUE{Colors.RESET}           Minimum X coordinate
    {Colors.YELLOW}--xmax VALUE{Colors.RESET}           Maximum X coordinate
    {Colors.YELLOW}--ymin VALUE{Colors.RESET}           Minimum Y coordinate
    {Colors.YELLOW}--ymax VALUE{Colors.RESET}           Maximum Y coordinate
    {Colors.YELLOW}--zmin VALUE{Colors.RESET}           Minimum Z coordinate (for 3D)
    {Colors.YELLOW}--zmax VALUE{Colors.RESET}           Maximum Z coordinate (for 3D)

    Note: Coordinate variables (X,Y,Z) are only included in output if
          explicitly specified in --variables flag.

{Colors.BOLD}EXAMPLES:{Colors.RESET}  ({Colors.DIM}--output is required{Colors.RESET})

  {Colors.BOLD}Single variable to CSV:{Colors.RESET}
    flexflow field extract CS4SG1U1 --timestep 1000 --variables Y --zone FIELD --output y.csv

  {Colors.BOLD}Single timestep to a contourable mesh (.vtu):{Colors.RESET}
    flexflow field extract CS4SG1U1 --timestep 1000 --variables U,QCriterion --zone FIELD --output snap.vtu

  {Colors.BOLD}Range to a CSV table (one file, 'timestep' column):{Colors.RESET}
    flexflow field extract CS4SG1U1 --t1 1000 --t2 5000 --variables U,V --zone FIELD --output range.csv

  {Colors.BOLD}Range to a ParaView time series of meshes (.pvd):{Colors.RESET}
    flexflow field extract CS4SG1U1 --t1 1000 --t2 5000 --freq 1000 --variables U,QCriterion \\
      --zone FIELD --output wake.pvd     # -> wake_1000.vtu, wake_2000.vtu, ... + wake.pvd

  {Colors.BOLD}3D subdomain box:{Colors.RESET}
    flexflow field extract CS4SG1U1 --timestep 1000 --variables U,V --zone FIELD --output box.csv \\
      --xmin -1.0 --xmax 1.0 --ymin -2.0 --ymax 2.0 --zmin -3.0 --zmax 3.0

  {Colors.BOLD}Probe one point, printed on screen:{Colors.RESET}
    flexflow field extract CS4SG1U1 --timestep 1000 --variables U,V --zone FIELD --probe 2.5,0,0

  {Colors.BOLD}Time signal at three probes -> CSV:{Colors.RESET}
    flexflow field extract CS4SG1U1 --t1 1000 --t2 5000 --variables U,V,Pressure --zone FIELD \\
      --probe 2.5,0,0 --probe 5,0,0 --probe 10,0,0 --output wake_probes.csv

  {Colors.BOLD}Interpolated at the exact point rather than the nearest node:{Colors.RESET}
    flexflow field extract CS4SG1U1 --t1 1000 --t2 5000 --variables Pressure --zone FIELD \\
      --probe 0,0,3 --interpolate --output wake_pressure.csv

{Colors.BOLD}WORKFLOW:{Colors.RESET}

  1. Discover variables and zones:
     {Colors.YELLOW}flexflow field info CS4SG1U1 --variables --zones{Colors.RESET}

  2. Optionally set context once, then extract without repeating flags:
     {Colors.YELLOW}use zone:FIELD var:U,V t1:1000 t2:5000{Colors.RESET}
     {Colors.YELLOW}flexflow field extract CS4SG1U1 --output range.csv{Colors.RESET}

{Colors.BOLD}NOTES:{Colors.RESET}

  - No Tecplot license or pytecplot needed; reads the .plt binary directly
  - Works on Python 3.13+
  - Extracts nodal (point) data; subdomain filtering is by node coordinates
  - --probe reports the nearest node's value unless --interpolate is given; check
    the 'distance' column to see how far that node was from the point you asked
    for, and use --interpolate when that offset matters
  - --interpolate trusts the mesh connectivity. It checks itself once per run --
    an interpolated value cannot leave the range of its own element's nodal
    values -- and warns if that fails. Pass {Colors.YELLOW}--nen 8{Colors.RESET} when an 8-node brick
    mesh is labelled as tetrahedra (`field info --checks` reports this)
  - Output CSV header is the comma-separated variable names
  - Coordinate variables (X,Y,Z) are available but only written if requested
    in --variables

""")
