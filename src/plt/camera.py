"""
camera.py  --  Load a camera "frame" so a view set up on one file can be reused.

Supported sources (auto-detected by extension):
  .yml / .yaml   a flat frame written by the GUI helper (save_camera)
  .pvsm          a ParaView "Save State" XML file (first RenderView's camera)
  .py            a ParaView Python state file (camera assignments, by regex)

A frame is a dict: position, focal, up, parallel, parallel_scale, view_angle.
Pure-Python -- no ParaView/pyvista needed to read these.
"""
import os
import re
import xml.etree.ElementTree as ET


def _from_pvsm(path):
    root = ET.parse(path).getroot()
    for proxy in root.iter("Proxy"):
        if proxy.get("group") == "views" and "RenderView" in (proxy.get("type") or ""):
            props = {p.get("name"): [e.get("value") for e in p.findall("Element")]
                     for p in proxy.findall("Property")}
            if "CameraPosition" in props:
                def vec(n):
                    return [float(x) for x in props[n]] if props.get(n) else None

                def scal(n):
                    return float(props[n][0]) if props.get(n) else None

                par = scal("CameraParallelProjection")
                return {"position": vec("CameraPosition"),
                        "focal": vec("CameraFocalPoint"),
                        "up": vec("CameraViewUp"),
                        "parallel": bool(par) if par is not None else False,
                        "parallel_scale": scal("CameraParallelScale"),
                        "view_angle": scal("CameraViewAngle")}
    raise ValueError("no RenderView camera found in %s" % path)


def _from_pystate(path):
    txt = open(path).read()

    def vec(n):
        m = re.search(n + r"\s*=\s*\[([^\]]+)\]", txt)
        return [float(x) for x in m.group(1).split(",")] if m else None

    def scal(n):
        m = re.search(n + r"\s*=\s*([-+0-9.eE]+)", txt)
        return float(m.group(1)) if m else None

    if vec("CameraPosition") is None:
        raise ValueError("no CameraPosition found in %s" % path)
    par = scal("CameraParallelProjection")
    return {"position": vec("CameraPosition"),
            "focal": vec("CameraFocalPoint"),
            "up": vec("CameraViewUp"),
            "parallel": bool(par) if par is not None else False,
            "parallel_scale": scal("CameraParallelScale"),
            "view_angle": scal("CameraViewAngle")}


def load_camera(path):
    """Load a camera frame from a .yml/.yaml, ParaView .pvsm, or ParaView .py state."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pvsm":
        return _from_pvsm(path)
    if ext == ".py":
        return _from_pystate(path)
    import yaml
    return yaml.safe_load(open(path)) or {}
