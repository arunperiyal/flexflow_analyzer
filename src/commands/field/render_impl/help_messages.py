"""Help text for `field render` and its modes."""

from ....utils.colors import Colors


_COMMON_INPUT = f"""\
{Colors.BOLD}INPUT (one of):{Colors.RESET}
    {Colors.YELLOW}<case> [--timestep N]{Colors.RESET}   Convert the case's PLT (latest, or step N) and render
    {Colors.YELLOW}<case> --t1 A --t2 B{Colors.RESET}   {Colors.BOLD}One figure per timestep{Colors.RESET} in the range
                           {Colors.YELLOW}--freq N{Colors.RESET} keeps only steps that are multiples of N
                           {Colors.DIM}(the t1/t2/freq context supplies these: use t1:100 t2:500){Colors.RESET}
    {Colors.YELLOW}--vtu PATH{Colors.RESET}             Render an existing .vtu directly
    {Colors.YELLOW}--config FILE{Colors.RESET}          YAML config (input.vtu may be set there)"""

_COMMON_COLOR = f"""\
    {Colors.YELLOW}--color NAME{Colors.RESET}           Scalar to colour by          (default: U; use W for z-flow)
    {Colors.YELLOW}--color-range MIN MAX{Colors.RESET}  Fix the colour scale to this span (two numbers,
                           space-separated, so a negative MIN works)
                           {Colors.DIM}Without it the scale is taken from each surface, so the
                           same variable gets a different scale at every timestep
                           and two frames cannot be compared -- or animated.
                           Rendering a range without it is warned about.{Colors.RESET}"""

_COMMON_OUTPUT = f"""\
{Colors.BOLD}OUTPUT:{Colors.RESET}
    Everything goes in a {Colors.BOLD}directory under the case{Colors.RESET}: one run writes a file per
    camera view, and a timestep range multiplies that by the number of steps.

    {Colors.YELLOW}--output NAME{Colors.RESET}          The directory <case>/NAME/  (default: render_<mode>/)
    {Colors.YELLOW}--output NAME.png{Colors.RESET}      ... holding PNGs only, no .vtp (single view)
    {Colors.YELLOW}--output NAME.vtp{Colors.RESET}      ... holding the cut surface -- {Colors.BOLD}no image is rendered{Colors.RESET}
    {Colors.YELLOW}          NAME.vtu{Colors.RESET}      the same, as an unstructured grid
    {Colors.YELLOW}          NAME.csv{Colors.RESET}      the same, as an x,y,z + variables point table

    {Colors.DIM}Files inside are named <NAME>_<step>_<view>.png, so a range sorts by step.{Colors.RESET}"""

_COMMON_MISC = f"""\
{Colors.BOLD}MISC:{Colors.RESET}
    {Colors.YELLOW}--zone NAME{Colors.RESET}            Zone to render (default: first volume zone)
    {Colors.YELLOW}--nen N{Colors.RESET}                Force nodes-per-element when converting (e.g. 8 for bricks)
    {Colors.YELLOW}--camera FILE{Colors.RESET}          Render from a saved view: {Colors.BOLD}one{Colors.RESET} image per step, the
                           camera pinned across every one of them. Takes a .yml
                           written by --pick-camera, or a ParaView .pvsm/.py state
    {Colors.YELLOW}--pick-camera FILE{Colors.RESET}     Open a window, orbit to the view you want, close it,
                           and that view is saved to FILE. Needs a display
    {Colors.YELLOW}--config FILE{Colors.RESET}          YAML config for full control: background, resolution,
                           domain crop, threshold, camera views, saved-camera reuse
    {Colors.YELLOW}--write-template PATH{Colors.RESET}  Write this mode's YAML config template and exit
    {Colors.YELLOW}--verbose, -v{Colors.RESET}          Verbose output
    {Colors.YELLOW}--help, -h{Colors.RESET}             Show this help message"""


def print_render_help():
    print(f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow Field Render Command{Colors.RESET}

Make pictures from PLT field data using {Colors.BOLD}pyvista{Colors.RESET} (no Tecplot, no ParaView).
Given a case, the PLT is auto-converted to a cached .vtu first.

{Colors.BOLD}USAGE:{Colors.RESET}
    flexflow field render <mode> [<case>] [options]

{Colors.BOLD}MODES:{Colors.RESET}
    {Colors.YELLOW}iso{Colors.RESET}     An isosurface of a scalar -- Q-criterion for vortex tubes,
              coloured by another variable
    {Colors.YELLOW}slice{Colors.RESET}   A cut plane through the volume, or a series of them
              evenly spaced along a normal

    {Colors.DIM}Both share the input, colouring, camera and output options; they differ
    only in the surface they cut out of the volume. Run a mode with -h for its
    own help.{Colors.RESET}

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    flexflow field render iso myCase --timestep 100 --values 20 --color W
    flexflow field render slice myCase --normal z --color Pressure
    flexflow field render iso myCase --t1 100 --t2 500 --color-range -1 1
    flexflow field render slice myCase --normal x --output cut.vtp

{Colors.BOLD}OUTPUT:{Colors.RESET}
    {Colors.DIM}Always a directory under the case -- <case>/render_<mode>/ by default, or
    <case>/NAME/ with --output NAME. One run writes a file per camera view, and
    a --t1/--t2 range writes that many per timestep.{Colors.RESET}

{Colors.BOLD}NOTES:{Colors.RESET}
    {Colors.DIM}- A flag belonging to the other mode is an error, not a no-op: --values
      only works on iso, --normal only on slice.
    - Give the case before a list-valued flag: `--values 20 myCase` reads
      myCase as another isosurface value.
    - A range without --color-range scales every frame to its own data, so the
      frames are not comparable. It is warned about.{Colors.RESET}
""")


def print_iso_help():
    print(f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow Field Render Iso{Colors.RESET}

Render isosurface PNGs from PLT field data (Q-criterion or any scalar), coloured
by another variable.

{Colors.BOLD}USAGE:{Colors.RESET}
    flexflow field render iso [<case>] [options]

{_COMMON_INPUT}

{Colors.BOLD}THE SURFACE:{Colors.RESET}
    {Colors.YELLOW}--contour NAME{Colors.RESET}         Scalar to contour            (default: QCriterion)
    {Colors.YELLOW}--values V [V ...]{Colors.RESET}     Isosurface value(s)          (default: 20)
{_COMMON_COLOR}

{_COMMON_OUTPUT}

{_COMMON_MISC}

{Colors.BOLD}EXAMPLES:{Colors.RESET}

  {Colors.BOLD}Render a case timestep:{Colors.RESET}
    flexflow field render iso myCase --timestep 100 --values 20 --color W

  {Colors.BOLD}An existing .vtu with several iso values:{Colors.RESET}
    flexflow field render iso --vtu field.vtu --contour QCriterion --values 5 50 --output wake

  {Colors.BOLD}A whole range on one fixed scale, so the frames can be compared:{Colors.RESET}
    flexflow field render iso myCase --t1 100 --t2 500 --color W --color-range -0.5 0.5
    {Colors.DIM}(one figure per step in 100..500, all on the same scale, in myCase/render_iso/){Colors.RESET}

  {Colors.BOLD}Write then use a config template:{Colors.RESET}
    flexflow field render iso --write-template iso.yml
    flexflow field render iso myCase --config iso.yml

{Colors.BOLD}CAMERA REUSE:{Colors.RESET}  ({Colors.DIM}what a Tecplot .sty is for, without Tecplot{Colors.RESET})

    Set the view once by eye, then pin it for every timestep:

        flexflow field render iso myCase --timestep 100 --pick-camera cam.yml
        flexflow field render iso myCase --t1 100 --t2 500 --camera cam.yml \\
                --color-range -1 1

    {Colors.DIM}--pick-camera needs a screen; --camera does not. So pick it on your own
    machine or over `ssh -X`, copy the .yml to the cluster, and render there.
    A view's `camera_file:` in a --config file takes the same .yml, and also a
    ParaView "Save State" .pvsm or .py -- so a view set up in ParaView works too.{Colors.RESET}

{Colors.BOLD}NOTES:{Colors.RESET}
    {Colors.DIM}- QCriterion is unnormalised; pick --values a couple orders below its max
      for clean vortex tubes (a value near 0 yields a dense, domain-filling sheet).
    - Flow in z -> colour by W; flow in x -> colour by U.
    - --values takes a list, so put the case before it: `--values 20 myCase`
      reads myCase as another value and fails.{Colors.RESET}
""")


def print_slice_help():
    print(f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow Field Render Slice{Colors.RESET}

Cut a plane through the volume and colour it -- the other picture you routinely
want out of a run. Or cut a series of planes along one normal.

{Colors.BOLD}USAGE:{Colors.RESET}
    flexflow field render slice [<case>] [options]

{_COMMON_INPUT}

{Colors.BOLD}THE PLANE:{Colors.RESET}
    {Colors.YELLOW}--normal AXIS{Colors.RESET}          Plane normal: {Colors.YELLOW}x{Colors.RESET} / {Colors.YELLOW}y{Colors.RESET} / {Colors.YELLOW}z{Colors.RESET} / {Colors.YELLOW}-x{Colors.RESET} / {Colors.YELLOW}-y{Colors.RESET} / {Colors.YELLOW}-z{Colors.RESET},
                           or a vector {Colors.YELLOW}NX,NY,NZ{Colors.RESET}      (default: z)
    {Colors.YELLOW}--origin X,Y,Z{Colors.RESET}         A point the plane passes through (default: mesh centre)
    {Colors.YELLOW}--slices N{Colors.RESET}             Cut N planes evenly spaced along the normal
                           instead of one, spanning the mesh
{_COMMON_COLOR}

{_COMMON_OUTPUT}

{_COMMON_MISC}

{Colors.BOLD}EXAMPLES:{Colors.RESET}

  {Colors.BOLD}A plane through the middle of the case:{Colors.RESET}
    flexflow field render slice myCase --timestep 100 --normal z --color Pressure

  {Colors.BOLD}At a chosen height:{Colors.RESET}
    flexflow field render slice myCase --normal z --origin 0,0,3

  {Colors.BOLD}Ten stations down the riser, all on one scale:{Colors.RESET}
    flexflow field render slice myCase --normal z --slices 10 --color-range -1 1 --output stations

  {Colors.BOLD}The cut itself, for ParaView or pandas:{Colors.RESET}
    flexflow field render slice myCase --normal x --output cut.vtp
    flexflow field render slice myCase --normal x --output cut.csv

{Colors.BOLD}CAMERA:{Colors.RESET}
    {Colors.DIM}A plane is invisible edge-on, so the default is a single view looking
    straight down the normal, in parallel projection -- not the four views iso
    uses. Set a `views:` block in a --config file to override, and it wins over
    whatever --normal would have chosen.

    To set the view by eye and pin it across a sweep (what a Tecplot .sty does):
        flexflow field render slice myCase --timestep 100 --pick-camera cam.yml
        flexflow field render slice myCase --t1 100 --t2 500 --camera cam.yml
    --pick-camera needs a screen; --camera does not.{Colors.RESET}

{Colors.BOLD}NOTES:{Colors.RESET}
    {Colors.DIM}- --slices puts the planes strictly inside the mesh: one sitting exactly on
      a bounding face would cut nothing. They land in a single output, not one
      file per plane.
    - An oblique --normal (a vector rather than an axis) works, but keeps the
      configured camera: there is no named direction to aim at.{Colors.RESET}
""")
