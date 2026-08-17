"""
render.py  --  PNGs from a .vtu, via pyvista (config-driven).

Pure-pip replacement for the old ParaView/pvpython renderer: read a VTU, crop
the domain, cut a surface out of it, colour that, and write offscreen PNGs from
one or more camera views. pyvista (and vtk) are imported lazily so the rest of
the `plt` package works without them.

Two surfaces are offered, and they differ in one step only -- `contour` versus
`slice`. Everything on either side of that (the crop, the threshold, the colour
map, the cameras, the screenshots) is shared, so the pipeline is written once as
_prepare -> <surface> -> render_surface and the two entry points below just pick
the middle.

Config schema (dict; missing keys fall back to DEFAULTS):
    input    : vtu
    output   : prefix, save_vtp, html
    image    : resolution [W,H], background (name or RGB 0-1), transparent
    contour  : variable, isosurfaces [..] (null: taken from the data)  (iso mode)
    slice    : normal, origin, count              (slice mode)
    color    : variable, preset (matplotlib cmap or ParaView preset name),
               range [min,max], levels, log_scale, title, show_scalar_bar,
               text_color
    domain   : xmin/xmax/ymin/ymax/zmin/zmax   (box crop before contouring)
    threshold: variable, min, max
    surface  : opacity, show_edges
    axes     : orientation_axes, bounds_grid
    annotations: rulers [{from: [x,y,z], to: [x,y,z], title}]
    views    : list; each view picks ONE of camera_file / direction /
               position+focal+up / azimuth+elevation+roll ; optional zoom, parallel

The section for the mode you are not in is simply unused -- `contour` means
nothing to a slice and `slice` nothing to an isosurface, and neither is an error.
"""
import copy
import os
import sys

from .camera import load_camera, save_camera

NO_DISPLAY_HELP = """\
picking a camera needs a window to orbit in, and there is no display here.
    A virtual framebuffer does not help -- you have to see it.
    Do it where there is a screen, then carry the file:
      - on your own machine, or over `ssh -X`, run the --pick-camera above
      - copy the .yml next to the case on this machine
      - render the sweep headless with --camera <that file>"""

HEADLESS_HELP = """\
    There is also no display on this machine, which *may* be the cause if the
    error above does not explain itself. Off-screen rendering still needs a GL
    context. Ways out:
      - write the surface instead of a picture: --output NAME.vtp (or .vtu/.csv),
        which opens no plotter and needs no GL at all
      - install xvfb (apt install xvfb); it is picked up automatically
      - run over `ssh -X`, or on a machine with a display"""

DEFAULTS = {
    # cache_derived: write a computed variable (lambda2) back into the .vtu,
    # so a re-render costs nothing instead of the ~15s it takes to work out.
    "input":   {"vtu": None, "cache_derived": True},
    # geometry: an explicit path for the cut surface (set by --output NAME.vtp);
    # images: False writes only that, and never constructs a Plotter.
    # html: an orbitable page instead of PNGs (set by --output NAME.html).
    "output":  {"prefix": "iso", "save_vtp": True, "geometry": None,
                "images": True, "image_path": None, "html": None},
    "image":   {"resolution": [1600, 1000], "background": [1.0, 1.0, 1.0], "transparent": False},
    # isosurfaces: null lets the value be taken from the data. No constant can
    # serve as a default here -- see _default_isovalue.
    "contour": {"variable": "QCriterion", "isosurfaces": None},
    # normal: an axis name or a vector; origin: null = the mesh centre;
    # count > 1: that many planes evenly spaced along the normal instead of one.
    "slice":   {"normal": "z", "origin": None, "count": 1},
    # A surface zone drawn alongside for context -- the body the vortices are
    # shedding from. `vtu` is filled in per timestep by the command layer,
    # because a deforming body moves and cannot be converted once and reused.
    "body":    {"zone": None, "vtu": None, "color": "lightgray", "variable": None,
                "opacity": 1.0, "show_edges": False},
    # levels: N discrete colour bands instead of a continuous ramp, the way
    # Tecplot and ParaView band a contour legend. null = continuous.
    "color":   {"variable": "U", "preset": "coolwarm", "range": None,
                "levels": None, "log_scale": False, "title": None,
                "show_scalar_bar": True, "text_color": [0.0, 0.0, 0.0]},
    "domain":  {"xmin": None, "xmax": None, "ymin": None, "ymax": None,
                "zmin": None, "zmax": None},
    "threshold": {"variable": None, "min": None, "max": None},
    "surface": {"opacity": 1.0, "show_edges": False},
    # bounds_grid: a labelled box around the data, to read coordinates off when
    # you do not yet know where to put a ruler.
    "axes":    {"orientation_axes": True, "bounds_grid": False},
    # Dimension lines: each {from: [x,y,z], to: [x,y,z]} draws a ruler between
    # two points of the mesh's own coordinates, with the distance labelled.
    "annotations": {"rulers": []},
    "views": [
        {"name": "iso", "azimuth": 30, "elevation": 20, "roll": 0, "zoom": 1.0},
        {"name": "xy",  "direction": "+z", "up": [0, 1, 0]},
        {"name": "xz",  "direction": "-y", "up": [0, 0, 1]},
        {"name": "yz",  "direction": "+x", "up": [0, 0, 1]},
    ],
}

# Floats throughout, deliberately: these are 0-1 fractions, and pyvista reads an
# *integer* triple as 0-255 instead. [1, 1, 1] therefore renders as near-black
# rather than white -- which is exactly what "background: white" used to do.
NAMED_COLORS = {
    "white": [1.0, 1.0, 1.0], "black": [0.0, 0.0, 0.0], "gray": [0.5, 0.5, 0.5],
    "grey": [0.5, 0.5, 0.5], "lightgray": [0.82, 0.82, 0.82],
    "lightgrey": [0.82, 0.82, 0.82],
}
# ParaView preset name -> matplotlib colormap (fall through to the given name)
PRESET_CMAP = {
    "Cool to Warm": "coolwarm", "Cool to Warm (Extended)": "coolwarm",
    "Viridis (matplotlib)": "viridis", "Jet": "jet",
    "Rainbow Desaturated": "turbo", "Black-Body Radiation": "inferno",
}
# Vortex criteria that are NEGATIVE inside a core. QCriterion and its relatives
# are positive there, and lambda2 is the odd one out: contouring it at a
# positive value picks out the fluid *outside* every vortex in the domain.
NEGATIVE_IN_CORE = ("lambda2",)

DIRS = {"+x": [1, 0, 0], "-x": [-1, 0, 0], "+y": [0, 1, 0],
        "-y": [0, -1, 0], "+z": [0, 0, 1], "-z": [0, 0, -1]}
DEFAULT_UP = {"+z": [0, 1, 0], "-z": [0, 1, 0], "+x": [0, 0, 1],
              "-x": [0, 0, 1], "+y": [0, 0, 1], "-y": [0, 0, 1]}


# A plane is invisible edge-on, so the stock four views are wrong for a slice:
# a cut with normal +z shows nothing from the xz and yz views. One view down the
# normal, in parallel projection, is the picture a slice is actually for.
SLICE_VIEWS = [{"name": "plane", "direction": "+z", "parallel": True}]


def default_config(mode="iso"):
    """The default config, with the views that suit the mode."""
    cfg = copy.deepcopy(DEFAULTS)
    if mode == "slice":
        cfg["output"]["prefix"] = "slice"
        cfg["views"] = copy.deepcopy(SLICE_VIEWS)
    return cfg


def view_direction_for(normal):
    """The camera direction that looks a plane of this normal in the face.

    Axis-aligned normals only; an oblique cut keeps whatever view is configured,
    since there is no named direction for it.
    """
    vec = _normal_vector(normal)
    nonzero = [i for i, c in enumerate(vec) if c]
    if len(nonzero) != 1:
        return None
    i = nonzero[0]
    return ("+" if vec[i] > 0 else "-") + "xyz"[i]


def deep_merge(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        out[k] = deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def to_rgb(c):
    """A colour name or triple -> [r, g, b] as 0-1 floats.

    Both conventions are accepted, because both get written in config files:
    0-1 fractions and 0-255 bytes. Anything above 1 must be the latter. The
    result is always floats, since an int triple means 0-255 downstream and
    would turn a white background black.
    """
    if isinstance(c, str):
        c = NAMED_COLORS.get(c.lower().replace(" ", ""), [1.0, 1.0, 1.0])
    vals = [float(v) for v in c][:3]
    return [v / 255.0 for v in vals] if any(v > 1.0 for v in vals) else vals


def to_cmap(name):
    return PRESET_CMAP.get(name, name)


def _apply_domain_clip(mesh, dom):
    # (key, axis, invert): invert=False keeps the +normal side (>= bound),
    #                      invert=True keeps the -normal side (<= bound)
    for key, axis, invert in (("xmin", "x", False), ("ymin", "y", False), ("zmin", "z", False),
                              ("xmax", "x", True), ("ymax", "y", True), ("zmax", "z", True)):
        val = dom.get(key)
        if val is None:
            continue
        origin = [0.0, 0.0, 0.0]
        origin["xyz".index(axis)] = val
        mesh = mesh.clip(normal=axis, origin=origin, invert=invert)
    return mesh


def _apply_threshold(mesh, th):
    var = th.get("variable")
    if not var:
        return mesh
    lo, hi = th.get("min"), th.get("max")
    rng = mesh.get_data_range(var)
    return mesh.threshold(value=(lo if lo is not None else rng[0],
                                 hi if hi is not None else rng[1]), scalars=var)


def _setup_camera(p, view, center, span):
    cam = p.camera
    if view.get("camera_file"):
        cp = load_camera(view["camera_file"])
        if cp.get("position") is not None:
            cam.position = tuple(cp["position"])
        if cp.get("focal") is not None:
            cam.focal_point = tuple(cp["focal"])
        if cp.get("up") is not None:
            cam.up = tuple(cp["up"])
        if cp.get("parallel"):
            p.enable_parallel_projection()
            if cp.get("parallel_scale") is not None:
                cam.parallel_scale = cp["parallel_scale"]
        elif cp.get("view_angle") is not None:
            cam.view_angle = cp["view_angle"]
        return

    if view.get("position") is not None:
        cam.position = tuple(view["position"])
        cam.focal_point = tuple(view.get("focal", center))
        cam.up = tuple(view.get("up", [0, 0, 1]))
        if view.get("fit", True):
            p.reset_camera()
    elif view.get("direction"):
        d = DIRS[view["direction"]]
        D = span * 2.2
        cam.focal_point = tuple(center)
        cam.position = tuple(center[i] + d[i] * D for i in range(3))
        cam.up = tuple(view.get("up", DEFAULT_UP[view["direction"]]))
        p.reset_camera()
    else:
        cam.focal_point = tuple(center)
        cam.position = (center[0] + span, center[1] - span, center[2] + 0.7 * span)
        cam.up = (0, 0, 1)
        p.reset_camera()
        cam.Azimuth(view.get("azimuth", 0))
        cam.Elevation(view.get("elevation", 0))
        cam.Roll(view.get("roll", 0))
        p.reset_camera()

    if view.get("parallel"):
        p.enable_parallel_projection()
    z = view.get("zoom", 1.0) or 1.0
    if z != 1.0:
        cam.zoom(z)
    p.reset_camera_clipping_range()


def _prepare(cfg, mode, log=print):
    """Read the .vtu, add any derived variables asked for, crop and threshold."""
    import pyvista as pv

    vtu = cfg["input"]["vtu"]
    if not vtu:
        raise ValueError("no input .vtu (set input.vtu)")
    mesh = pv.read(vtu)

    # Anything the picture needs that the file does not carry -- lambda2, say --
    # is computed here, before the crop, so the gradient sees whole cells at
    # what would otherwise be a cut face.
    wanted = [cfg["color"]["variable"], cfg["threshold"].get("variable")]
    if mode == "iso":
        wanted.append(cfg["contour"]["variable"])
    if _add_derived(mesh, wanted, log) and cfg["input"].get("cache_derived"):
        _write_back(mesh, vtu, log)

    color = cfg["color"]["variable"]
    log("colour  '%s' range: %s" % (color, mesh.get_data_range(color)))
    mesh = _apply_domain_clip(mesh, cfg["domain"])
    return _apply_threshold(mesh, cfg["threshold"])


def _add_derived(mesh, wanted, log=print):
    """Compute any requested variable the mesh lacks. True if anything was."""
    from . import derive

    added = False
    for name in dict.fromkeys(n for n in wanted if n):
        if name in mesh.point_data:
            continue
        if not derive.is_derived(name):
            continue          # not ours to make; the renderer reports it plainly
        derive.ensure(mesh, name, log)
        added = True
    return added


def _write_back(mesh, vtu, log=print):
    """Save a computed variable into the .vtu, so it is computed once.

    Written beside the original and renamed over it, for the same reason the
    conversion is: a run killed here would otherwise leave a truncated .vtu that
    is newer than its .plt and would be trusted afterwards.
    """
    tmp = os.path.splitext(vtu)[0] + ".deriving.vtu"
    try:
        mesh.save(tmp)
        os.replace(tmp, vtu)
        log("cached the computed variable(s) into %s" % os.path.basename(vtu))
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _default_isovalue(mesh, cvar, log=print, warn=None):
    """An isosurface value taken from the data, for when none was given.

    No constant can serve as the default. A vortex criterion is quadratic in the
    velocity gradient, so its scale follows the flow's: a value that draws clean
    tubes in one case wraps half the domain in another. A far-tail percentile
    follows the data instead -- and which tail depends on the criterion, since
    lambda2 is negative in a core where QCriterion is positive.

    It is a starting point, not a choice: the value is reported so it can be
    replaced with one picked by eye.
    """
    import numpy as np

    warn = warn or log
    negative = cvar in NEGATIVE_IN_CORE
    pct = 1.0 if negative else 99.0
    value = float(np.percentile(np.asarray(mesh.point_data[cvar]), pct))
    warn("no isosurface value given: contouring '%s' at its %g%% percentile, "
         "%.4g. Give contour.isosurfaces (or --values) to choose one."
         % (cvar, pct, value))
    return value


def _iso_surface(mesh, cfg, log=print, warn=None):
    """The isosurface(s) of contour.variable at contour.isosurfaces."""
    cvar = cfg["contour"]["variable"]
    log("contour '%s' range: %s" % (cvar, mesh.get_data_range(cvar)))
    values = cfg["contour"].get("isosurfaces")
    if values is None or (hasattr(values, "__len__") and len(values) == 0):
        values = [_default_isovalue(mesh, cvar, log, warn)]
    elif not hasattr(values, "__len__"):
        # `isosurfaces: 20` in a config is a number, not a list. pyvista reads a
        # bare number as "this many levels, evenly spaced", which is not what
        # anyone writing a single value means.
        values = [values]
    surf = mesh.contour(isosurfaces=list(values), scalars=cvar)
    log("isosurface: %d points, %d cells" % (surf.n_points, surf.n_cells))
    return surf


def _normal_vector(normal):
    """An axis name ('z', '-x') or an [x,y,z] vector -> a unit-ish vector."""
    if isinstance(normal, str):
        key = normal.strip().lower()
        key = key if key.startswith(("+", "-")) else "+" + key
        if key not in DIRS:
            raise ValueError(f"unknown slice normal '{normal}' "
                             f"(use x/y/z, -x/-y/-z, or a vector)")
        return DIRS[key]
    vec = list(normal)
    if len(vec) != 3:
        raise ValueError(f"slice normal needs 3 components, got {len(vec)}")
    if not any(vec):
        raise ValueError("slice normal cannot be the zero vector")
    return vec


def _slice_surface(mesh, cfg, log=print, warn=None):
    """One cut plane, or `count` planes evenly spaced along the normal.

    One loop covers both, and covers an arbitrary normal: pyvista's
    slice_along_axis takes an axis name, so it cannot honour --normal 1,1,0 and
    would need a second code path for the oblique case anyway.
    """
    import numpy as np

    sl = cfg["slice"]
    n = np.array(_normal_vector(sl.get("normal", "z")), dtype=float)
    n /= np.linalg.norm(n)
    count = max(int(sl.get("count") or 1), 1)

    if count == 1:
        origin = sl.get("origin") or list(mesh.center)
        surf = mesh.slice(normal=list(n), origin=list(origin))
        log("slice: normal %s at %s" % (list(n), [round(float(c), 6) for c in origin]))
    else:
        surf = None
        for origin in _plane_origins(mesh, n, count):
            plane = mesh.slice(normal=list(n), origin=list(origin))
            surf = plane if surf is None else surf.merge(plane)
        log("slice: %d planes along %s" % (count, list(n)))

    log("surface: %d points, %d cells" % (surf.n_points, surf.n_cells))
    return surf


def _plane_origins(mesh, n, count):
    """`count` origins evenly spaced along n, spanning the mesh.

    The mesh bounds are projected onto the normal and the planes are placed
    strictly inside that span -- a plane sitting exactly on a bounding face cuts
    nothing, so the ends are trimmed rather than used.
    """
    import numpy as np

    b = mesh.bounds  # (xmin,xmax,ymin,ymax,zmin,zmax)
    corners = np.array([[b[0 + i], b[2 + j], b[4 + k]]
                        for i in (0, 1) for j in (0, 1) for k in (0, 1)])
    proj = corners @ n
    lo, hi = proj.min(), proj.max()
    step = (hi - lo) / (count + 1)
    return [n * (lo + i * step) for i in range(1, count + 1)]


def _load_body(cfg, log=print):
    """The context surface, if one was asked for and converted."""
    import pyvista as pv

    vtu = cfg.get("body", {}).get("vtu")
    if not vtu:
        return None
    body = pv.read(vtu)
    log("body: %d points, %d cells" % (body.n_points, body.n_cells))
    return body


def _union_bounds(*meshes):
    """The box holding every mesh given, ignoring the ones that are absent."""
    boxes = [m.bounds for m in meshes if m is not None and m.n_points]
    if not boxes:
        return (0.0, 1.0, 0.0, 1.0, 0.0, 1.0)
    return tuple(
        min(bx[i] for bx in boxes) if i % 2 == 0 else max(bx[i] for bx in boxes)
        for i in range(6))


def _add_body(p, body, cfg, text_color):
    """Draw the context surface: a solid colour, or coloured by a variable."""
    spec = cfg.get("body", {})
    variable = spec.get("variable")
    common = dict(opacity=float(spec.get("opacity", 1.0)),
                  show_edges=bool(spec.get("show_edges")))
    if variable and variable in body.point_data:
        p.add_mesh(body, scalars=variable, cmap=to_cmap(spec.get("preset", "viridis")),
                   scalar_bar_args={"title": variable, "color": text_color}, **common)
    else:
        # A solid colour is the usual want: the body is context, and a second
        # scalar bar competing with the isosurface's is rarely what you meant.
        p.add_mesh(body, color=to_rgb(spec.get("color", "lightgray")),
                   show_scalar_bar=False, **common)


def save_geometry(surf, path, log=print):
    """Write the cut surface itself: .vtp, .vtu, or a .csv point table."""
    import numpy as np

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    ext = os.path.splitext(path)[1].lower()
    if ext == ".csv":
        names = list(surf.point_data.keys())
        cols = [surf.points[:, 0], surf.points[:, 1], surf.points[:, 2]]
        cols += [np.asarray(surf.point_data[n]).reshape(len(surf.points), -1)[:, 0]
                 for n in names]
        np.savetxt(path, np.column_stack(cols), delimiter=",",
                   header=",".join(["x", "y", "z"] + names), comments="")
    elif ext == ".vtu":
        # A cut surface is PolyData, which cannot be written as .vtu directly.
        surf.cast_to_unstructured_grid().save(path)
    else:
        surf.save(path)
    log("saved %s" % path)
    return path


def _prepare_display(log=print):
    """Give VTK something to draw into when there is no display.

    A VTK built against OSMesa carries its own context and needs nothing; one
    built against X needs a server even off-screen, and on a headless box prints
    "bad X server connection" and renders nothing useful. Start a virtual
    framebuffer when we can, and stay quiet when we cannot -- an OSMesa build
    would still succeed, and the screenshot itself reports the failure if not.
    """
    if sys.platform != "linux" or os.environ.get("DISPLAY"):
        return
    try:
        import pyvista as pv
        pv.start_xvfb()
        log("no DISPLAY -- started a virtual framebuffer (xvfb)")
    except Exception:
        pass


def _no_display():
    """True when a GL context is unlikely to exist -- a hint, not a diagnosis."""
    return sys.platform == "linux" and not os.environ.get("DISPLAY")


def _view_path(prefix, name):
    """Where one view's image goes: <output dir>/<view name>/<stem>.png

    Grouped by view rather than all in one directory, because that is what a
    sweep leaves behind: four views of a hundred steps is four hundred files,
    and interleaved they are neither an image sequence nor readable. One
    directory per view is a sequence in step order -- what ffmpeg wants, and
    what flicking through with an image viewer wants.

    The surface itself (.vtp) and the html page stay at the top level: there is
    one of each per timestep, and the views are views *of* them.
    """
    safe = os.path.basename(str(name or "view").strip()) or "view"
    directory = os.path.join(os.path.dirname(prefix), safe)
    os.makedirs(directory, exist_ok=True)
    return os.path.join(directory, os.path.basename(prefix) + ".png")


def _as_point(value):
    """A sequence of three numbers -> [x, y, z] floats, or None."""
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return None
    try:
        return [float(v) for v in value]
    except (TypeError, ValueError):
        return None


def _kwargs_for(func, wanted):
    """The subset of `wanted` this build of pyvista actually accepts.

    add_ruler and show_bounds have both gained and lost keywords across
    releases. Filtering against the real signature keeps a config working on
    whichever version is installed on the cluster, instead of raising a
    TypeError in the middle of a sweep over a keyword nobody asked about.
    """
    import inspect

    try:
        allowed = set(inspect.signature(func).parameters)
    except (TypeError, ValueError):
        return dict(wanted)
    return {k: v for k, v in wanted.items() if k in allowed}


def _add_annotations(p, cfg, text_color, warn):
    """Dimension lines and a graduated box -- what makes a picture measurable.

    A ruler is given in the mesh's own coordinates, so it sits in the scene and
    holds its place as the view turns. Fixed endpoints are what a sweep wants:
    the same annotation on every frame, so the distance it marks can be read
    across the whole animation rather than re-derived per picture.
    """
    for i, spec in enumerate(cfg.get("annotations", {}).get("rulers") or [], 1):
        if not isinstance(spec, dict):
            warn("annotations.rulers[%d] should be a mapping with `from:` and "
                 "`to:`; skipping it" % i)
            continue
        a, b = _as_point(spec.get("from")), _as_point(spec.get("to"))
        if a is None or b is None:
            warn("annotations.rulers[%d] needs `from:` and `to:`, three numbers "
                 "each; skipping it" % i)
            continue
        actor = p.add_ruler(**_kwargs_for(p.add_ruler, {
            "pointa": a, "pointb": b,
            "title": spec.get("title", ""),
            # Two labels puts one at each end, which is what reads as a
            # dimension line; more turns it into a tick scale.
            "number_labels": spec.get("number_labels", 2),
            "label_format": spec.get("label_format", "%.3f"),
            "font_size_factor": spec.get("font_size_factor", 0.6),
        }))
        try:
            actor.GetProperty().SetColor(*text_color)
        except Exception:
            pass            # colour is cosmetic; never lose the ruler over it

    if cfg.get("axes", {}).get("bounds_grid"):
        p.show_bounds(**_kwargs_for(p.show_bounds, {
            "color": text_color, "grid": "back",
            "location": "outer", "ticks": "both",
        }))


def _check_color_range(surf, color, crange, warn):
    """Warn when the fixed colour range leaves the data outside it.

    A range set orders of magnitude below the data is not a subtle mistake:
    every point clamps to one end of the map or the other, and the surface comes
    out in two flat colours. That reads as a broken render rather than a
    mis-set number, so it is worth saying out loud.
    """
    import numpy as np

    vals = np.asarray(surf.point_data[color], dtype=float).ravel()
    if vals.size == 0:
        return
    inside = float(((vals >= crange[0]) & (vals <= crange[1])).mean())
    if inside >= 0.05:
        return
    warn("colour range [%g, %g] holds %.1f%% of the surface, which spans "
         "[%.4g, %.4g] -- nearly every point clamps to one end of the colour "
         "map, so the picture comes out in two flat colours. That is the point "
         "when colouring by the sign of a variable; widen the range if it is not."
         % (crange[0], crange[1], 100 * inside, vals.min(), vals.max()))


def render_surface(cfg, surf, log=print, warn=None, state=None):
    """Save the surface and write one PNG per view. Returns the written files.

    When color.range is null the scale is taken from this surface and written
    back into cfg, so a caller rendering a sweep can pin it for the rest.
    """
    prefix = cfg["output"]["prefix"]
    color = cfg["color"]["variable"]

    empty = surf is None or surf.n_points == 0
    if empty:
        log("EMPTY surface -- adjust the contour/slice, domain or threshold.")
        # With a body configured the frame is still worth drawing: over a sweep,
        # the steps whose isosurface is below threshold would otherwise be holes
        # in the sequence, and a hole is worse than a picture of just the body.
        if not (cfg.get("body", {}).get("vtu") and cfg["output"].get("images", True)):
            return []
        log("drawing the body alone for this step")

    geometry = cfg["output"].get("geometry")
    if empty:
        pass                                  # nothing to save; body is context
    elif geometry:
        save_geometry(surf, geometry, log)
    elif cfg["output"].get("save_vtp", True):
        os.makedirs(os.path.dirname(prefix) or ".", exist_ok=True)
        save_geometry(surf, prefix + ".vtp", log)

    # Geometry-only: never construct a Plotter, so this path needs no GL at all
    # (it has to work on a headless box without OSMesa).
    if not cfg["output"].get("images", True):
        return [geometry] if geometry else []

    import pyvista as pv

    warn = warn or log
    _prepare_display(log)
    os.makedirs(os.path.dirname(prefix) or ".", exist_ok=True)
    fixed = cfg["color"].get("range")
    crange = fixed or (list(surf.get_data_range(color)) if not empty else [0.0, 1.0])
    if fixed and not empty and not (state or {}).get("range_checked"):
        # Once per run, not once per step: a sweep of 100 frames shares one
        # range, so the same sentence 100 times is noise, not a warning.
        _check_color_range(surf, color, crange, warn)
        if state is not None:
            state["range_checked"] = True
    elif not fixed and not empty:
        log("colour scale taken from the surface: [%.4g, %.4g]" % (crange[0], crange[1]))
    # Record what was used, so a sweep can hold this scale for its later steps.
    cfg["color"]["range"] = list(crange)

    body = _load_body(cfg, log)
    # Frame both, or a body sticking out past the isosurface gets cut off -- and
    # the body is usually the longer of the two, being the whole span of it.
    b = _union_bounds(surf, body)
    center = [(b[0] + b[1]) / 2, (b[2] + b[3]) / 2, (b[4] + b[5]) / 2]
    span = max(b[1] - b[0], b[3] - b[2], b[5] - b[4]) or 1.0
    res = list(cfg["image"].get("resolution", [1600, 1000]))
    transparent = bool(cfg["image"].get("transparent"))
    text_color = to_rgb(cfg["color"].get("text_color", [0.0, 0.0, 0.0]))
    views = cfg.get("views", [])
    # An exact --output NAME.png names the file itself, but only one view can
    # own that name; several still fall back to the per-view suffix.
    exact = cfg["output"].get("image_path") if len(views) == 1 else None
    html = cfg["output"].get("html")
    outputs = []

    # Discrete bands, the way a Tecplot legend is banded. n_labels follows the
    # bands so a tick lands on every boundary rather than at arbitrary values.
    levels = cfg["color"].get("levels")
    bar_args = {"title": cfg["color"].get("title") or color, "color": text_color}
    if levels:
        bar_args["n_labels"] = int(levels) + 1

    def scene(view):
        """The whole scene in a plotter, aimed at one view."""
        p = pv.Plotter(off_screen=True, window_size=res)
        p.set_background(to_rgb(cfg["image"].get("background", [1.0, 1.0, 1.0])))
        if not empty:
            p.add_mesh(surf, scalars=color, cmap=to_cmap(cfg["color"].get("preset", "coolwarm")),
                       clim=crange, opacity=float(cfg["surface"].get("opacity", 1.0)),
                       show_edges=bool(cfg["surface"].get("show_edges")),
                       log_scale=bool(cfg["color"].get("log_scale")),
                       n_colors=int(levels) if levels else 256,
                       show_scalar_bar=bool(cfg["color"].get("show_scalar_bar", True)),
                       scalar_bar_args=bar_args)
        if body is not None:
            _add_body(p, body, cfg, text_color)
        if cfg["axes"].get("orientation_axes", True):
            p.add_axes(color=text_color)
        _add_annotations(p, cfg, text_color, warn)
        _setup_camera(p, view, center, span)
        return p

    try:
        if html:
            # One page for the scene, not one per view: the reader orbits it
            # themselves, so a second page would differ only in where it starts
            # -- and each carries a copy of the whole surface. The first view
            # sets that starting angle.
            p = scene(views[0] if views else {})
            _export_html(p, html, log)
            p.close()
            outputs.append(html)
        else:
            for view in views:
                p = scene(view)
                # An exact --output NAME.png names the file itself and is left
                # exactly there; anything else is filed under its view.
                fn = exact or _view_path(prefix, view.get("name", "view"))
                p.screenshot(fn, transparent_background=transparent)
                p.close()
                log("saved %s" % fn)
                outputs.append(fn)
    except Exception as e:
        # Never replace the real error with a guess: a bad clim, a missing
        # variable and a dead X server all surface here, and only one of
        # them is about the display. Report what actually happened, and add
        # the headless note underneath when it might also be a factor.
        if _no_display():
            raise RuntimeError(f"{type(e).__name__}: {e}\n{HEADLESS_HELP}") from e
        raise
    return outputs


def _export_html(p, path, log):
    """Write the scene as a page that can be orbited in a browser.

    Self-contained: the surface travels inside the file, so it opens on a
    machine with nothing installed. That also makes it as big as the surface is
    -- a dense isosurface runs to tens of MB, and the .vtp of that same surface
    is the smaller thing to send to someone who has ParaView.
    """
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    try:
        p.export_html(path)
    except ImportError as e:
        # pyvista is installed -- it is the HTML exporter that wants trame. Say
        # so, or the caller's ImportError handler blames the wrong package.
        raise RuntimeError(f"writing {path} needs trame alongside pyvista: "
                           f"pip install trame trame-vtk trame-vuetify  ({e})") from e
    log("saved %s" % path)
    return path


def pick_camera(cfg, surf, path, log=print):
    """Show the surface, let the user orbit, and save the camera they settle on.

    The window is the whole point, so this is the one path that refuses to run
    headless rather than falling back to something invisible.
    """
    import pyvista as pv

    if sys.platform == "linux" and not os.environ.get("DISPLAY"):
        raise RuntimeError(NO_DISPLAY_HELP)
    if surf is None or surf.n_points == 0:
        raise ValueError("nothing to look at: the surface came out empty")

    color = cfg["color"]["variable"]
    p = pv.Plotter(window_size=list(cfg["image"].get("resolution", [1600, 1000])))
    p.set_background(to_rgb(cfg["image"].get("background", [1.0, 1.0, 1.0])))
    p.add_mesh(surf, scalars=color, cmap=to_cmap(cfg["color"].get("preset", "coolwarm")),
               clim=cfg["color"].get("range") or list(surf.get_data_range(color)),
               opacity=float(cfg["surface"].get("opacity", 1.0)),
               show_edges=bool(cfg["surface"].get("show_edges")),
               scalar_bar_args={"title": cfg["color"].get("title") or color})
    if cfg["axes"].get("orientation_axes", True):
        p.add_axes()
    # Draw the annotations here too: this is the one window where a ruler's
    # placement can be checked by eye, rather than inferred from a PNG.
    _add_annotations(p, cfg, to_rgb(cfg["color"].get("text_color", [0.0, 0.0, 0.0])), log)
    log("orbit to the view you want, then close the window to save it")
    # auto_close=False keeps the render window alive after show() returns, which
    # is the only way to read the camera the user actually left it on.
    p.show(auto_close=False)
    frame = save_camera(path, p.camera)
    p.close()
    return frame


def build_surface(cfg, mode, log=print, warn=None):
    """The cut surface for a mode, without rendering it. Returns (cfg, surf)."""
    cfg = deep_merge(DEFAULTS, cfg or {})
    mesh = _prepare(cfg, mode, log)
    maker = {"iso": _iso_surface, "slice": _slice_surface}[mode]
    return cfg, maker(mesh, cfg, log, warn)


def _render(cfg, mode, log=print, warn=None, state=None):
    """Build the surface for a mode and render it.

    `state`, when given, comes back holding 'color_range' -- the scale actually
    used. A sweep renders one timestep at a time, so that is how the caller
    learns what an automatic scale came out as and holds it for the rest.
    """
    merged, surf = build_surface(cfg, mode, log, warn)
    outputs = render_surface(merged, surf, log, warn, state)
    if state is not None:
        state["color_range"] = merged["color"].get("range")
    return outputs


def render_iso(cfg, log=print, warn=None, state=None):
    """Render isosurface PNGs from a .vtu. Returns the list of written files."""
    return _render(cfg, "iso", log, warn, state)


def render_slice(cfg, log=print, warn=None, state=None):
    """Render cut-plane PNGs from a .vtu. Returns the list of written files."""
    return _render(cfg, "slice", log, warn, state)
