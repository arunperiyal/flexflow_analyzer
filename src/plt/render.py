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
    output   : prefix, save_vtp
    image    : resolution [W,H], background (name or RGB 0-1), transparent
    contour  : variable, isosurfaces [..]         (iso mode)
    slice    : normal, origin, count              (slice mode)
    color    : variable, preset (matplotlib cmap or ParaView preset name),
               range [min,max], log_scale, title, show_scalar_bar, text_color
    domain   : xmin/xmax/ymin/ymax/zmin/zmax   (box crop before contouring)
    threshold: variable, min, max
    surface  : opacity, show_edges
    axes     : orientation_axes
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
    "output":  {"prefix": "iso", "save_vtp": True, "geometry": None,
                "images": True, "image_path": None},
    "image":   {"resolution": [1600, 1000], "background": [1.0, 1.0, 1.0], "transparent": False},
    "contour": {"variable": "QCriterion", "isosurfaces": [0.25]},
    # normal: an axis name or a vector; origin: null = the mesh centre;
    # count > 1: that many planes evenly spaced along the normal instead of one.
    "slice":   {"normal": "z", "origin": None, "count": 1},
    # A surface zone drawn alongside for context -- the body the vortices are
    # shedding from. `vtu` is filled in per timestep by the command layer,
    # because a deforming body moves and cannot be converted once and reused.
    "body":    {"zone": None, "vtu": None, "color": "lightgray", "variable": None,
                "opacity": 1.0, "show_edges": False},
    "color":   {"variable": "U", "preset": "coolwarm", "range": None,
                "log_scale": False, "title": None, "show_scalar_bar": True,
                "text_color": [0.0, 0.0, 0.0]},
    "domain":  {"xmin": None, "xmax": None, "ymin": None, "ymax": None,
                "zmin": None, "zmax": None},
    "threshold": {"variable": None, "min": None, "max": None},
    "surface": {"opacity": 1.0, "show_edges": False},
    "axes":    {"orientation_axes": True},
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


def _iso_surface(mesh, cfg, log=print):
    """The isosurface(s) of contour.variable at contour.isosurfaces."""
    cvar = cfg["contour"]["variable"]
    log("contour '%s' range: %s" % (cvar, mesh.get_data_range(cvar)))
    surf = mesh.contour(isosurfaces=list(cfg["contour"]["isosurfaces"]), scalars=cvar)
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


def _slice_surface(mesh, cfg, log=print):
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


def render_surface(cfg, surf, log=print):
    """Save the surface and write one PNG per view. Returns the written files."""
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

    _prepare_display(log)
    os.makedirs(os.path.dirname(prefix) or ".", exist_ok=True)
    crange = (cfg["color"].get("range")
              or (list(surf.get_data_range(color)) if not empty else [0.0, 1.0]))

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
    outputs = []

    for view in views:
        try:
            p = pv.Plotter(off_screen=True, window_size=res)
            p.set_background(to_rgb(cfg["image"].get("background", [1.0, 1.0, 1.0])))
            if not empty:
                p.add_mesh(surf, scalars=color, cmap=to_cmap(cfg["color"].get("preset", "coolwarm")),
                           clim=crange, opacity=float(cfg["surface"].get("opacity", 1.0)),
                           show_edges=bool(cfg["surface"].get("show_edges")),
                           log_scale=bool(cfg["color"].get("log_scale")),
                           show_scalar_bar=bool(cfg["color"].get("show_scalar_bar", True)),
                           scalar_bar_args={"title": cfg["color"].get("title") or color,
                                            "color": text_color})
            if body is not None:
                _add_body(p, body, cfg, text_color)
            if cfg["axes"].get("orientation_axes", True):
                p.add_axes(color=text_color)
            _setup_camera(p, view, center, span)
            fn = exact or "%s_%s.png" % (prefix, view.get("name", "view"))
            p.screenshot(fn, transparent_background=transparent)
            p.close()
        except Exception as e:
            # Never replace the real error with a guess: a bad clim, a missing
            # variable and a dead X server all surface here, and only one of
            # them is about the display. Report what actually happened, and add
            # the headless note underneath when it might also be a factor.
            if _no_display():
                raise RuntimeError(f"{type(e).__name__}: {e}\n{HEADLESS_HELP}") from e
            raise
        log("saved %s" % fn)
        outputs.append(fn)
    return outputs


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
    log("orbit to the view you want, then close the window to save it")
    # auto_close=False keeps the render window alive after show() returns, which
    # is the only way to read the camera the user actually left it on.
    p.show(auto_close=False)
    frame = save_camera(path, p.camera)
    p.close()
    return frame


def build_surface(cfg, mode, log=print):
    """The cut surface for a mode, without rendering it. Returns (cfg, surf)."""
    cfg = deep_merge(DEFAULTS, cfg or {})
    mesh = _prepare(cfg, mode, log)
    maker = {"iso": _iso_surface, "slice": _slice_surface}[mode]
    return cfg, maker(mesh, cfg, log)


def render_iso(cfg, log=print):
    """Render isosurface PNGs from a .vtu. Returns the list of written files."""
    cfg, surf = build_surface(cfg, "iso", log)
    return render_surface(cfg, surf, log)


def render_slice(cfg, log=print):
    """Render cut-plane PNGs from a .vtu. Returns the list of written files."""
    cfg, surf = build_surface(cfg, "slice", log)
    return render_surface(cfg, surf, log)
