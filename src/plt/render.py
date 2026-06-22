"""
render.py  --  Isosurface PNGs from a .vtu, via pyvista (config-driven).

Pure-pip replacement for the old ParaView/pvpython renderer: read a VTU, crop
the domain, contour a scalar, colour it, and write offscreen PNGs from one or
more camera views. pyvista (and vtk) are imported lazily so the rest of the
`plt` package works without them.

Config schema (dict; missing keys fall back to DEFAULTS):
    input    : vtu
    output   : prefix, save_vtp
    image    : resolution [W,H], background (name or RGB 0-1), transparent
    contour  : variable, isosurfaces [..]
    color    : variable, preset (matplotlib cmap or ParaView preset name),
               range [min,max], log_scale, title, show_scalar_bar, text_color
    domain   : xmin/xmax/ymin/ymax/zmin/zmax   (box crop before contouring)
    threshold: variable, min, max
    surface  : opacity, show_edges
    axes     : orientation_axes
    views    : list; each view picks ONE of camera_file / direction /
               position+focal+up / azimuth+elevation+roll ; optional zoom, parallel
"""
import copy
import os

from .camera import load_camera

DEFAULTS = {
    "input":   {"vtu": None},
    "output":  {"prefix": "iso", "save_vtp": True},
    "image":   {"resolution": [1600, 1000], "background": [1, 1, 1], "transparent": False},
    "contour": {"variable": "QCriterion", "isosurfaces": [0.25]},
    "color":   {"variable": "U", "preset": "coolwarm", "range": None,
                "log_scale": False, "title": None, "show_scalar_bar": True,
                "text_color": [0, 0, 0]},
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

NAMED_COLORS = {
    "white": [1, 1, 1], "black": [0, 0, 0], "gray": [0.5, 0.5, 0.5],
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


def default_config():
    return copy.deepcopy(DEFAULTS)


def deep_merge(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        out[k] = deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def to_rgb(c):
    if isinstance(c, str):
        return NAMED_COLORS.get(c.lower().replace(" ", ""), [1, 1, 1])
    return list(c)


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


def render_iso(cfg, log=print):
    """Render isosurface PNGs from a .vtu. Returns the list of written files."""
    import pyvista as pv

    cfg = deep_merge(DEFAULTS, cfg or {})
    vtu = cfg["input"]["vtu"]
    if not vtu:
        raise ValueError("no input .vtu (set input.vtu)")
    prefix = cfg["output"]["prefix"]
    os.makedirs(os.path.dirname(prefix) or ".", exist_ok=True)

    cvar = cfg["contour"]["variable"]
    color = cfg["color"]["variable"]
    mesh = pv.read(vtu)
    log("contour '%s' range: %s" % (cvar, mesh.get_data_range(cvar)))
    log("colour  '%s' range: %s" % (color, mesh.get_data_range(color)))

    mesh = _apply_domain_clip(mesh, cfg["domain"])
    mesh = _apply_threshold(mesh, cfg["threshold"])
    surf = mesh.contour(isosurfaces=list(cfg["contour"]["isosurfaces"]), scalars=cvar)
    log("isosurface: %d points, %d cells" % (surf.n_points, surf.n_cells))
    if surf.n_points == 0:
        log("EMPTY isosurface -- adjust contour.isosurfaces / domain / threshold.")
        return []

    if cfg["output"].get("save_vtp", True):
        vtp = prefix + ".vtp"
        surf.save(vtp)
        log("saved %s" % vtp)

    crange = cfg["color"].get("range") or list(surf.get_data_range(color))
    b = surf.bounds  # (xmin,xmax,ymin,ymax,zmin,zmax)
    center = [(b[0] + b[1]) / 2, (b[2] + b[3]) / 2, (b[4] + b[5]) / 2]
    span = max(b[1] - b[0], b[3] - b[2], b[5] - b[4]) or 1.0
    res = list(cfg["image"].get("resolution", [1600, 1000]))
    transparent = bool(cfg["image"].get("transparent"))
    text_color = to_rgb(cfg["color"].get("text_color", [0, 0, 0]))
    outputs = []

    for view in cfg.get("views", []):
        p = pv.Plotter(off_screen=True, window_size=res)
        p.set_background(to_rgb(cfg["image"].get("background", [1, 1, 1])))
        p.add_mesh(surf, scalars=color, cmap=to_cmap(cfg["color"].get("preset", "coolwarm")),
                   clim=crange, opacity=float(cfg["surface"].get("opacity", 1.0)),
                   show_edges=bool(cfg["surface"].get("show_edges")),
                   log_scale=bool(cfg["color"].get("log_scale")),
                   show_scalar_bar=bool(cfg["color"].get("show_scalar_bar", True)),
                   scalar_bar_args={"title": cfg["color"].get("title") or color,
                                    "color": text_color})
        if cfg["axes"].get("orientation_axes", True):
            p.add_axes(color=text_color)
        _setup_camera(p, view, center, span)
        fn = "%s_%s.png" % (prefix, view.get("name", "view"))
        p.screenshot(fn, transparent_background=transparent)
        p.close()
        log("saved %s" % fn)
        outputs.append(fn)
    return outputs
