"""YAML config templates for `field render`, one per mode.

Two templates rather than one with a `mode:` key: the mode is already the
command's first positional, so a key in the file would be a second source of
truth the CLI has to override. And a combined template carrying both `contour:`
and `slice:` would teach the reader that both apply to both modes, when in fact
each mode ignores the other's section entirely.

Most of the file is shared. The `surface:` block is not, because the advice
genuinely inverts between the modes: an isosurface is a curved tube whose form
lives in its shading, and a cut plane is flat and facing the camera, where
lighting can only dim it. A shared block would have to recommend one and be
wrong for the other, so each mode carries its own.

The strings are concatenated, never `.format()`-ed: a YAML comment showing a
mapping is full of braces, and every one would have to be doubled.
"""

_COMMON_HEAD = """\
input:
  vtu: null                      # set, or let `<case> --timestep N` make one

output:
  # prefix is ignored: paths come from --output and the case directory.
  # Images are filed per camera view: <case>/NAME/<view>/NAME_<step>.png
  save_vtp: true                 # also write the cut surface as .vtp beside each
                                 # image -- one per timestep, so a long sweep
                                 # leaves a lot of them. false, or --no-vtp,
                                 # gives images alone.

image:
  resolution: [1600, 1000]       # match it to the domain's aspect or the render
                                 # is letterboxed: a 10-wide by 12-tall crop
                                 # wants something near [1000, 1200]
  background: white              # name (white/black/gray) or RGB [r,g,b] in 0-1
  transparent: false             # true drops the background, for a figure that
                                 # sits on a coloured page
  ssao: null                     # true, or a mapping of its options --
                                 #   ssao:
                                 #     radius: 0.05
                                 #     bias: 0.005
                                 #     blur: true
                                 # Ambient occlusion: darkens crevices, so a
                                 # groove shows even on a face lit head-on where
                                 # ordinary shading gives up. radius is in world
                                 # units -- set it near the feature's own size,
                                 # not the body's. Much smaller and nothing
                                 # darkens; much larger and everything does.
"""

_BODY_AND_COLOR = """\
body:                            # a surface zone drawn alongside, for context
  zone: null                     # e.g. cyl -- the body the wake comes off; null = none
                                 # Re-read every timestep, so a deforming body
                                 # follows the flow. Not cropped by domain:
                                 # below, so the whole span stays in frame and
                                 # keeps driving the camera fit.
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
  opacity: 1.0                   # the body hides the cut where they overlap,
                                 # which is usually wanted: the plane passes
                                 # through the body's middle
  show_edges: false              # every cell boundary. A diagnostic, not a
                                 # finish -- see feature_edges below
  # Shading. On a solid colour this is the only thing that shows the body's
  # shape, and it does that work only when the light is off to one side: see
  # lights: below. Measured on a 4-groove cylinder, these settings WITH a
  # raking light took the groove contrast from 2 grey levels to 139. Without
  # one they made it worse than leaving the block alone.
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
  variable: U                    # flow in z -> W ; flow in x -> U ; xVor/yVor/
                                 # zVor for vorticity about each axis
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
                                 # two end colours, which is exactly what you
                                 # want when colouring by the SIGN of a variable
                                 # and a mistake otherwise
  log_scale: false
  title: null                    # the scalar bar's label; default is the
                                 # variable's own name
  show_scalar_bar: true
  text_color: black

domain:                          # crop to a box before cutting; null = no limit
  xmin: null                     # The biggest lever on how long a sweep takes:
  xmax: null                     # a far field 30 diameters across contributes
  ymin: null                     # nothing to a wake picture but is cut, framed
  ymax: null                     # and rendered all the same. Cropping also
  zmin: null                     # frames the camera on what is left.
  zmax: null

threshold:                       # keep cells with scalar in [min,max]; null disables
  variable: null
  min: null
  max: null
"""

_SURFACE_SLICE = """\
surface:
  opacity: 1.0
  show_edges: false
  # A cut plane is flat and faces the camera, so every point on it is lit
  # identically and lighting can only scale the colours down: ambient 0.3 plus
  # diffuse 0.6 renders the whole plane at 90% and a pure red comes out at 229
  # instead of 254. false gives exactly what the colormap defines, which is
  # what a figure sitting beside a Tecplot one needs.
  lighting: false
  ambient: null                  # only reached when lighting is true; on a flat
  diffuse: null                  # cut there is nothing for them to reveal
  specular: null
  specular_power: null
  smooth_shading: null
"""

_SURFACE_ISO = """\
surface:
  opacity: 1.0
  show_edges: false
  # An isosurface is curved, so its shading is what gives it form -- but a lit
  # tube is darker than the same colour in the flat legend swatch, because the
  # shading follows the angle to the light.
  lighting: null                 # false = no shading: exactly the legend's
                                 # colours, but tubes go flat with no depth
  ambient: null                  # 0..1, try 0.3 -- lifts the shadowed side
                                 # while keeping the form. The better fix.
  diffuse: null                  # 0..1, lower it as ambient goes up (try 0.8)
  specular: null                 # 0..1, highlights; 0 kills the shine
  specular_power: null
  smooth_shading: null           # true rounds off the marching-cubes facets
"""

_COMMON_END = """\
axes:
  orientation_axes: true         # the little xyz triad in the corner
  bounds_grid: false             # a labelled box around the data -- use it to
                                 # read off the coordinates for a ruler below

lights: []                       # empty keeps VTK's default kit, which lights
                                 # from the camera. That is the worst place for
                                 # showing shape: a groove seen head-on is lit
                                 # as evenly as the land beside it, and no
                                 # amount of ambient/diffuse tuning recovers a
                                 # gradient the geometry never produced.
                                 #
                                 # A raking light -- off to one side, the trick
                                 # every photograph of a coin uses -- is what
                                 # makes relief read:
                                 #
                                 #   lights:
                                 #     - direction: [0, 0.574, 0.819]
                                 #       intensity: 1.0
                                 #
                                 # 55 degrees off the view axis measured best on
                                 # a 4-groove cylinder. ONE light, not two:
                                 # lights on both sides fill each other's
                                 # shadows and the contrast collapses from 139
                                 # back to 9. If the shadow side goes too dark,
                                 # raise body.ambient rather than adding a
                                 # second light.
                                 #
                                 # direction is a vector from the subject toward
                                 # the light, scaled to the scene span, so it
                                 # carries between cases; position: is absolute
                                 # instead, and distance: (default 2.5 spans)
                                 # sets how far out a direction reaches.
                                 # A single light may be written as a mapping
                                 # rather than a one-item list.

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
#
# An isosurface of a scalar -- Q-criterion or lambda2 for vortex tubes --
# coloured by another variable, with the body drawn alongside for context.
""" + _COMMON_HEAD + """
contour:
  variable: QCriterion          # or lambda2 -- computed from U,V,W if
                               # the solver did not write it. lambda2 is
                               # NEGATIVE in a vortex core, so contour it at
                               # a small negative value, e.g. [-1]
  isosurfaces: null             # null: taken from the data (the 99% percentile,
                               # or the 1% for a criterion negative in a core).
                               # Reported when it is used -- replace it with a
                               # value picked by eye, e.g. [20] or [-1]

""" + _BODY_AND_COLOR + "\n" + _SURFACE_ISO + "\n" + _COMMON_END + """
# One PNG per view, each in its own directory. Pick ONE camera style per view:
# camera_file / direction / position / azimuth.
views:
  - {name: iso, azimuth: 30, elevation: 20, zoom: 1.0}
  - {name: top, direction: "+z", up: [0, 1, 0]}
  # - {name: saved, camera_file: cam.yml}       # a view saved by --pick-camera
  # - {name: saved, camera_file: mystate.pvsm}  # or a ParaView Save State frame
"""

SLICE_TEMPLATE = """\
# flexflow field render slice -- configuration
#
# A cut plane through the volume, coloured by a scalar, with the body drawn
# beside it for context.
#
# The plane and the body want opposite treatment, and most of the confusion
# here comes from giving them the same:
#
#   the cut plane   is flat and faces the camera. Lighting can only dim it, so
#                   surface.lighting is false below and the colours come out
#                   exactly as the colormap defines them.
#
#   the body        is curved, and on a solid colour its shape exists only in
#                   the shading -- which needs a light off to one side, or the
#                   shape turned into colour instead.
#
# To show a grooved or straked body, in order of how reliably it works:
#
#   1. body.variable: relief     colour from the geometry itself. Independent
#                                of the light and of which way a groove faces.
#   2. lights: one raking light  plus body ambient ~0.35, diffuse ~0.75,
#                                specular 0, smooth_shading false
#   3. image.ssao: true          darkens the crevices
#   4. body.feature_edges: 30    outline the creases, without a wireframe
#
# They compose. 1 alone is usually enough; 2 is what makes a grey body read as
# a solid object rather than a flat band.
""" + _COMMON_HEAD + """
slice:
  normal: z                      # axis (x/y/z, -x/-y/-z) or a vector [nx, ny, nz]
                                 # An axis name also aims the default camera
                                 # down it; a vector cannot, so set views: too
  origin: null                   # null = the mesh centre. [0, 0, 0] to cut
                                 # through the body's own axis
  count: 1                       # >1: that many planes evenly spaced along the
                                 # normal, all in one image -- not one file each

""" + _BODY_AND_COLOR + "\n" + _SURFACE_SLICE + "\n" + _COMMON_END + """
# A plane is invisible edge-on, so the default is a single view looking straight
# down the normal, in parallel projection. An explicit views: block always wins
# over what --normal would have chosen.
#
# `up` sets which way the body's axis runs in the frame: up: [1, 0, 0] puts the
# x axis vertical. Looking straight down the normal is the honest view of a cut
# but the worst one for the body's relief -- add a second, oblique view if the
# body is the point.
views:
  - {name: plane, direction: "+z", parallel: true}
  # - {name: oblique, azimuth: 25, elevation: 15, zoom: 1.4}
  # - {name: saved, camera_file: cam.yml}       # a view saved by --pick-camera
  # - {name: saved, camera_file: mystate.pvsm}  # or a ParaView Save State frame
"""

TEMPLATES = {"iso": ISO_TEMPLATE, "slice": SLICE_TEMPLATE}
