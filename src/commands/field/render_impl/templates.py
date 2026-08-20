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
  ssao: null                     # true, or a mapping of its options --
                                 #   ssao:
                                 #     radius: 0.05
                                 #     bias: 0.005
                                 #     blur: true
                                 # Ambient occlusion: darkens crevices, so relief
                                 # shows even on a face lit head-on, where
                                 # ordinary shading gives up. radius is in world
                                 # units -- set it near the feature's own size.
"""

_COMMON_TAIL = """\
body:                            # a surface zone drawn alongside, for context
  zone: null                     # e.g. cyl -- the body the wake comes off; null = none
  color: lightgray               # solid colour, used when `variable` is null
  variable: null                 # or colour the body by a scalar (e.g. Pressure).
                                 # `relief` is computed from the body's own
                                 # geometry: 0 on the land, negative in a groove,
                                 # positive on a strake. It shows shape as colour,
                                 # so unlike shading it does not depend on where
                                 # the light is or which way a feature faces --
                                 # the one reliable way to show a groove.
                                 # Greys_r and no scalar bar by default; set
                                 # preset:, range: and show_scalar_bar: to change
  opacity: 1.0
  show_edges: false
  # Shading. On a solid colour this is the only thing that shows the body's
  # shape -- grooves, strakes, a fairing. But it does the work only when the
  # light is off to one side: see lights: below. Measured on a 4-groove
  # cylinder, these settings with a raking light took the groove contrast from
  # 2 grey levels to 139.
  lighting: null                 # false = flat, and relief disappears entirely
  ambient: null                  # 0..1, try 0.35 -- keeps the shadow side
                                 # readable without filling the grooves in
  diffuse: null                  # 0..1, try 0.75
  specular: null                 # 0..1, 0 for a matte body. A highlight sits
                                 # on the lands and washes the grooves out
  specular_power: null
  smooth_shading: null           # false: true interpolates normals across the
                                 # groove edges and rounds them away
  feature_edges: null            # N degrees: outline the creases sharper than
                                 # this -- a groove's lip and root, and nothing
                                 # else. Not show_edges, which draws every cell
                                 # boundary and hides what it meant to show.
                                 # try 30. A smooth body has none, and draws none
  edge_color: null               # default: the text colour
  edge_width: 2.0

color:
  variable: U                    # flow in z -> W ; flow in x -> U
  preset: coolwarm               # matplotlib cmap, or a ParaView preset name
                                 # bwr gives pure blue/red ends, coolwarm muted
                                 # small_rainbow is Tecplot's Small Rainbow, for
                                 # a figure that sits beside an existing one
                                 # `field list --color` lists them all
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
  # Shading. A lit, curved tube is darker than the same colour in the flat
  # legend swatch, because the shading follows the angle to the light.
  lighting: null                 # false = no shading: exactly the legend's
                                 # colours, but tubes go flat with no depth
  ambient: null                  # 0..1, try 0.3 -- lifts the shadowed side
                                 # while keeping the form. The better fix.
  diffuse: null                  # 0..1, lower it as ambient goes up (try 0.8)
  specular: null                 # 0..1, highlights; 0 kills the shine
  specular_power: null
  smooth_shading: null           # true rounds off the marching-cubes facets

axes:
  orientation_axes: true
  bounds_grid: false             # a labelled box around the data -- use it to
                                 # read off the coordinates for a ruler below

lights: []                       # empty keeps VTK's default kit, which lights
                                 # from the camera -- and a groove seen head-on
                                 # is then lit as evenly as the land beside it.
                                 # A raking light off to one side is what makes
                                 # relief read. One strong light, not two:
                                 # lights on both sides fill each other's
                                 # shadows and the contrast collapses.
                                 # - direction: [0, 0.574, 0.819]   # 55 deg off
                                 #   intensity: 1.0                 # the view axis
                                 # direction is a vector from the subject toward
                                 # the light, scaled to the scene, so it carries
                                 # between cases; position: is absolute instead.
                                 # Pair it with body ambient ~0.35, diffuse ~0.75,
                                 # specular 0, smooth_shading false.

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
