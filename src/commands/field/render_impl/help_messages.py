"""Help text for `field render` and its modes."""

from ....utils.colors import Colors


_COMMON_INPUT = f"""\
{Colors.BOLD}INPUT (one of):{Colors.RESET}
    {Colors.YELLOW}<case> [--timestep N]{Colors.RESET}   Convert the case's PLT (latest, or step N) and render
    {Colors.YELLOW}--vtu PATH{Colors.RESET}             Render an existing .vtu directly
    {Colors.YELLOW}--config FILE{Colors.RESET}          YAML config (input.vtu may be set there)"""

_COMMON_OUTPUT = f"""\
{Colors.BOLD}OUTPUT:{Colors.RESET}  ({Colors.DIM}--output picks the format by extension{Colors.RESET})
    {Colors.YELLOW}--output NAME{Colors.RESET}          Prefix: NAME_<view>.png per view, plus NAME.vtp
    {Colors.YELLOW}--output NAME.png{Colors.RESET}      That one image (single view only)
    {Colors.YELLOW}--output NAME.vtp{Colors.RESET}      The cut surface itself -- {Colors.BOLD}no image is rendered{Colors.RESET}
    {Colors.YELLOW}          NAME.vtu{Colors.RESET}      the same, as an unstructured grid
    {Colors.YELLOW}          NAME.csv{Colors.RESET}      the same, as an x,y,z + variables point table
    {Colors.DIM}Omitted: the prefix is taken from the .vtu name.{Colors.RESET}"""

_COMMON_MISC = f"""\
{Colors.BOLD}MISC:{Colors.RESET}
    {Colors.YELLOW}--zone NAME{Colors.RESET}            Zone to render (default: first volume zone)
    {Colors.YELLOW}--nen N{Colors.RESET}                Force nodes-per-element when converting (e.g. 8 for bricks)
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
    flexflow field render slice myCase --normal z --slices 10
    flexflow field render slice myCase --normal x --output cut.vtp

{Colors.BOLD}NOTES:{Colors.RESET}
    {Colors.DIM}- A flag belonging to the other mode is an error, not a no-op: --values
      only works on iso, --normal only on slice.
    - Give the case before a list-valued flag: `--values 20 myCase` reads
      myCase as another isosurface value.{Colors.RESET}
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
    {Colors.YELLOW}--color NAME{Colors.RESET}           Scalar to colour by          (default: U; use W for z-flow)

{_COMMON_OUTPUT}

{_COMMON_MISC}

{Colors.BOLD}EXAMPLES:{Colors.RESET}

  {Colors.BOLD}Render a case timestep:{Colors.RESET}
    flexflow field render iso myCase --timestep 100 --values 20 --color W

  {Colors.BOLD}An existing .vtu with several iso values:{Colors.RESET}
    flexflow field render iso --vtu field.vtu --contour QCriterion --values 5 50 --output wake

  {Colors.BOLD}Write then use a config template:{Colors.RESET}
    flexflow field render iso --write-template iso.yml
    flexflow field render iso myCase --config iso.yml

{Colors.BOLD}CAMERA REUSE:{Colors.RESET}
    {Colors.DIM}A view's `camera_file:` accepts a ParaView "Save State" .pvsm/.py or a
    saved-frame .yml, so a view set up on one file applies to any other.{Colors.RESET}

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
    {Colors.YELLOW}--color NAME{Colors.RESET}           Scalar to colour by          (default: U)

{_COMMON_OUTPUT}

{_COMMON_MISC}

{Colors.BOLD}EXAMPLES:{Colors.RESET}

  {Colors.BOLD}A plane through the middle of the case:{Colors.RESET}
    flexflow field render slice myCase --timestep 100 --normal z --color Pressure

  {Colors.BOLD}At a chosen height:{Colors.RESET}
    flexflow field render slice myCase --normal z --origin 0,0,3

  {Colors.BOLD}Ten stations down the riser:{Colors.RESET}
    flexflow field render slice myCase --normal z --slices 10 --output stations

  {Colors.BOLD}The cut itself, for ParaView or pandas:{Colors.RESET}
    flexflow field render slice myCase --normal x --output cut.vtp
    flexflow field render slice myCase --normal x --output cut.csv

{Colors.BOLD}CAMERA:{Colors.RESET}
    {Colors.DIM}A plane is invisible edge-on, so the default is a single view looking
    straight down the normal, in parallel projection -- not the four views iso
    uses. Set a `views:` block in a --config file to override, and it wins over
    whatever --normal would have chosen.{Colors.RESET}

{Colors.BOLD}NOTES:{Colors.RESET}
    {Colors.DIM}- --slices puts the planes strictly inside the mesh: one sitting exactly on
      a bounding face would cut nothing. They land in a single output, not one
      file per plane.
    - An oblique --normal (a vector rather than an axis) works, but keeps the
      configured camera: there is no named direction to aim at.{Colors.RESET}
""")
