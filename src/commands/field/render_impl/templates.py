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
  # prefix is ignored: paths come from --output and the case directory.
  save_vtp: true                 # also write the cut surface as .vtp beside each
                                 # image -- one per timestep, so a long sweep
                                 # leaves a lot of them. false, or --no-vtp,
                                 # gives images alone.

image:
  resolution: [1600, 1000]
  background: white              # name (white/black/gray) or RGB [r,g,b] in 0-1
  transparent: false
"""

_COMMON_TAIL = """\
body:                            # a surface zone drawn alongside, for context
  zone: null                     # e.g. cyl -- the body the wake comes off; null = none
  color: lightgray               # solid colour, used when `variable` is null
  variable: null                 # or colour the body by a scalar (e.g. Pressure)
  opacity: 1.0
  show_edges: false

color:
  variable: U                    # flow in z -> W ; flow in x -> U
  preset: coolwarm               # matplotlib cmap, or a ParaView preset name
                                 # bwr gives pure blue/red ends, coolwarm muted
  levels: null                   # N discrete colour bands, as Tecplot bands a
                                 # legend; null = a continuous ramp
  range: null                    # [min, max], or null to take it from the data
                                 # (over a sweep: from the first step, then held
                                 # for the rest so the frames can be compared).
                                 # A range narrower than the data is warned
                                 # about -- outside it everything clamps to the
                                 # two end colours.
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
  bounds_grid: false             # a labelled box around the data -- use it to
                                 # read off the coordinates for a ruler below

annotations:
  rulers: []                     # dimension lines, in the mesh's coordinates:
                                 # - {from: [0, -0.5, 2], to: [0, 0.5, 2],
                                 #    title: sheet spacing}
                                 # The distance is labelled at each end. Fixed
                                 # points, so a sweep carries the same
                                 # annotation on every frame.
                                 # Optional per ruler: number_labels,
                                 # label_format (e.g. "%.2f"), font_size_factor
"""

ISO_TEMPLATE = """\
# flexflow field render iso -- configuration
""" + _COMMON_HEAD.format(prefix="iso") + """
contour:
  variable: QCriterion          # or lambda2 -- computed from U,V,W if
                               # the solver did not write it. lambda2 is
                               # NEGATIVE in a vortex core, so contour it at
                               # a small negative value, e.g. [-1]
  isosurfaces: null             # null: taken from the data (the 99% percentile,
                               # or the 1% for a criterion negative in a core).
                               # Reported when it is used -- replace it with a
                               # value picked by eye, e.g. [20] or [-1]

""" + _COMMON_TAIL + """
# One PNG per view. Pick ONE camera style: camera_file / direction / position / azimuth.
views:
  - {name: iso, azimuth: 30, elevation: 20, zoom: 1.0}
  - {name: top, direction: "+z", up: [0, 1, 0]}
  # - {name: saved, camera_file: cam.yml}       # a view saved by --pick-camera
  # - {name: saved, camera_file: mystate.pvsm}  # or a ParaView Save State frame
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
  # - {name: saved, camera_file: cam.yml}       # a view saved by --pick-camera
  # - {name: saved, camera_file: mystate.pvsm}  # or a ParaView Save State frame
"""

TEMPLATES = {"iso": ISO_TEMPLATE, "slice": SLICE_TEMPLATE}
