"""Help text for `field iso`."""


def print_iso_help():
    print("""
flexflow field iso [<case>] [options]

Render Q-criterion (or any scalar) isosurface PNGs from PLT field data, coloured
by another variable. Uses pyvista (no Tecplot/ParaView needed). If given a case,
the PLT is auto-converted to a cached .vtu first.

Input (one of):
  <case> [--timestep N]   convert the case's PLT (latest, or step N) and render
  --vtu PATH              render an existing .vtu directly
  --config FILE           YAML config (input.vtu may be set there)

Common options (override the config):
  --contour NAME     scalar to contour            (default QCriterion)
  --iso V [V ...]    isosurface value(s)           (default 20)
  --color NAME       scalar to colour by           (default U; use W for z-flow)
  --out PREFIX       output prefix for .vtp + PNGs
  --nen N            force nodes-per-element when converting (e.g. 8 for bricks)
  --config FILE      YAML config for full control (background, resolution,
                     domain crop, threshold, camera views, saved-camera reuse)
  --write-template PATH   write a documented YAML config template and exit
  -v, --verbose / -h, --help

Examples:
  flexflow field iso myCase --timestep 100 --iso 20 --color W
  flexflow field iso --vtu field.vtu --contour QCriterion --iso 5 50 --out wake
  flexflow field iso --write-template iso.yml
  flexflow field iso myCase --config iso.yml

Camera reuse: a view's `camera_file:` accepts a ParaView "Save State" .pvsm/.py
or a saved-frame .yml, so a view set up on one file applies to any other.
""")
