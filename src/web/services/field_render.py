"""services/field_render.py -- iso-surface / slice-plane PNG rendering from
PLT field data, for the Field -> Render dialog.

A trimmed v1 of `field render iso|slice`
(src/commands/field/render_impl/command.py): one timestep, a PNG gallery
(one file per configured camera view) as the only output -- no HTML/geometry
export, no --pick-camera (an interactive desktop concept that doesn't map to
a stateless HTTP request; see the plan's own "Deferred" section for where
that idea goes next). Reuses render.py's own render_iso/render_slice/
default_config/deep_merge, and the CLI's PLT->VTU sidecar-cache conversion
(_convert_zone), so a re-render of the same timestep never reconverts.
"""

import os
from pathlib import Path

from ...commands.field.locate import find_plt, zone_index
from ...plt import render
from ...plt.convert import to_vtu
from ...plt.fxplt import PltFile

MODES = ('iso', 'slice')


def _vtu_complete(path):
    """Is this .vtu whole? A complete file closes its root </VTKFile>
    element; a conversion cut short does not. Ported from
    render_impl/command.py's own helper of the same name."""
    try:
        with open(path, 'rb') as f:
            f.seek(max(0, os.path.getsize(path) - 200))
            return f.read().rstrip().endswith(b'</VTKFile>')
    except OSError:
        return False


def convert_zone_to_vtu(plt_path, zone_name=None, nen=None):
    """A PLT zone -> a cached .vtu sidecar beside it, converting if needed.

    Ported from render_impl/command.py's _convert_zone, minus its CLI logger
    -- the sidecar naming (plain .vtu, or .zN.vtu for a named zone) and the
    convert-to-a-temp-name-then-rename dance (so a run killed mid-conversion
    leaves no sidecar, rather than a corrupt one a later mtime check would
    trust) are both kept exactly as-is.
    """
    plt_path = Path(plt_path)
    zone = None
    if zone_name:
        plt = PltFile(str(plt_path))
        zone = zone_index(plt, zone_name)
        if zone is None:
            names = ', '.join(z['name'] for z in plt.zones)
            raise ValueError(f"zone '{zone_name}' not found in {plt_path.name}. Available: {names}")

    suffix = '.vtu' if zone is None else f'.z{zone}.vtu'
    sidecar = Path(str(plt_path)[:-4] + suffix)

    if (sidecar.exists() and sidecar.stat().st_mtime >= plt_path.stat().st_mtime
            and _vtu_complete(sidecar)):
        return str(sidecar)

    tmp = sidecar.with_name(sidecar.stem + '.partial.vtu')
    tmp.unlink(missing_ok=True)
    try:
        to_vtu(str(plt_path), str(tmp), zone=zone, nen=nen)
        os.replace(tmp, sidecar)
    except BaseException:      # a kill mid-conversion must not leave a corrupt sidecar
        tmp.unlink(missing_ok=True)
        raise
    return str(sidecar)


def render_field(binary_dir, problem, zone_name, mode, step, overrides, view_names, out_dir, nen=None):
    """Render one timestep's iso-surface or slice to PNG(s) under out_dir,
    one per name in view_names (a subset of the mode's default view names,
    or all of them if view_names is empty). `overrides` is a partial config
    dict in render.py's own shape (color/contour/slice/... -- the same shape
    a --config YAML file has), merged onto default_config(mode) exactly as
    the CLI's own --config does.

    Returns the list of written PNG paths (absolute). Raises ValueError for
    anything that stops the render outright (bad zone, no PLT for that step,
    an unknown view name, an empty surface).
    """
    if mode not in MODES:
        raise ValueError(f"mode must be 'iso' or 'slice', got '{mode}'")

    plt_path = find_plt(binary_dir, problem, step)
    if plt_path is None:
        raise ValueError(f'no PLT file for timestep {step}')
    vtu_path = convert_zone_to_vtu(plt_path, zone_name, nen=nen)

    cfg = render.default_config(mode)
    cfg = render.deep_merge(cfg, overrides or {})

    all_views = {v['name']: v for v in cfg['views']}
    if view_names:
        chosen = [all_views[n] for n in view_names if n in all_views]
        if not chosen:
            raise ValueError(f"none of the requested views {view_names} exist for mode "
                             f"'{mode}'. available: {', '.join(all_views)}")
        cfg['views'] = chosen

    cfg['input']['vtu'] = vtu_path
    cfg['output']['prefix'] = str(Path(out_dir) / f'{mode}_{step}')
    cfg['output']['save_vtp'] = False

    renderer = render.render_iso if mode == 'iso' else render.render_slice
    outs = renderer(cfg, log=lambda *a, **k: None, warn=lambda *a, **k: None, state={})
    if not outs:
        raise ValueError('nothing rendered -- check the contour variable/value or slice position')
    return outs
