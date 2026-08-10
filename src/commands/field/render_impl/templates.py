"""YAML config templates for `field render`, one per mode.

Two templates rather than one with a `mode:` key: the mode is already the
command's first positional, so a key in the file would be a second source of
truth the CLI has to override. And a combined template carrying both `contour:`
and `slice:` would teach the reader that both apply to both modes, when in fact
each mode ignores the other's section entirely.

Everything except that one section is common to both, deliberately kept
byte-identical so a config written for one mode can be adapted to the other by
swapping the block.
"""

_COMMON_HEAD = """\
input:
  vtu: null                      # set, or let `<case> --timestep N` make one

output:
  prefix: {prefix}                 # writes <prefix>.vtp and <prefix>_<view>.png
  save_vtp: true

image:
  resolution: [1600, 1000]
  background: white              # name (white/black/gray) or RGB [r,g,b] in 0-1
  transparent: false
"""

_COMMON_TAIL = """\
color:
  variable: U                    # flow in z -> W ; flow in x -> U
  preset: coolwarm               # matplotlib cmap, or a ParaView preset name
  range: null                    # [min, max] or null = auto
  log_scale: false
  title: null
  show_scalar_bar: true
  text_color: black

domain:                          # crop to a box before cutting; null = no limit
  xmin: null
  xmax: null
  ymin: null
  ymax: null
  zmin: null
  zmax: null

threshold:                       # keep cells with scalar in [min,max]; null disables
  variable: null
  min: null
  max: null

surface:
  opacity: 1.0
  show_edges: false

axes:
  orientation_axes: true
"""

ISO_TEMPLATE = """\
# flexflow field render iso -- configuration
""" + _COMMON_HEAD.format(prefix="iso") + """
contour:
  variable: QCriterion
  isosurfaces: [20]

""" + _COMMON_TAIL + """
# One PNG per view. Pick ONE camera style: camera_file / direction / position / azimuth.
views:
  - {name: iso, azimuth: 30, elevation: 20, zoom: 1.0}
  - {name: top, direction: "+z", up: [0, 1, 0]}
  # - {name: saved, camera_file: mystate.pvsm}   # reuse a ParaView Save State frame
"""

SLICE_TEMPLATE = """\
# flexflow field render slice -- configuration
""" + _COMMON_HEAD.format(prefix="slice") + """
slice:
  normal: z                      # axis (x/y/z, -x/-y/-z) or a vector [nx, ny, nz]
  origin: null                   # null = the mesh centre
  count: 1                       # >1: that many planes evenly spaced along the normal

""" + _COMMON_TAIL + """
# A plane is invisible edge-on, so the default is a single view looking straight
# down the normal, in parallel projection. Override freely -- an explicit views:
# block always wins over what --normal would have chosen.
views:
  - {name: plane, direction: "+z", parallel: true}
  # - {name: saved, camera_file: mystate.pvsm}   # reuse a ParaView Save State frame
"""

TEMPLATES = {"iso": ISO_TEMPLATE, "slice": SLICE_TEMPLATE}
