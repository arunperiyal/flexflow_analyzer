"""
Field check command implementation -- validate a VTK file produced by
`field convert` / `field extract`:

  .vtu / .vtk / .vtp   a single mesh or point cloud
  .pvd                 a time-series collection (checks the referenced members)
"""

import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

from ....utils.logger import Logger
from ....utils.colors import Colors


def _read(path):
    """Return (points, [(cell_type, count)], {array: values}, backend).

    meshio handles .vtu/.vtk; .vtp (and anything meshio can't) goes via pyvista.
    """
    ext = path.suffix.lower()
    if ext != ".vtp":
        try:
            import meshio
            m = meshio.read(str(path))
            cells = [(cb.type, len(cb.data)) for cb in m.cells]
            pdata = {k: np.asarray(v) for k, v in m.point_data.items()}
            return np.asarray(m.points), cells, pdata, "meshio"
        except ImportError:
            raise
        except Exception:
            pass  # fall through to pyvista
    import pyvista as pv
    m = pv.read(str(path))
    try:
        counts = {}
        for ct in m.celltypes:
            counts[int(ct)] = counts.get(int(ct), 0) + 1
        cells = [("vtk_type_%d" % t, c) for t, c in counts.items()]
    except Exception:
        cells = [("cells", m.n_cells)]
    pdata = {k: np.asarray(m.point_data[k]) for k in m.point_data.keys()}
    return np.asarray(m.points), cells, pdata, "pyvista"


def _report_file(path, logger):
    """Print a summary for one VTK file; return a list of problem strings."""
    try:
        pts, cells, pdata, backend = _read(path)
    except ImportError:
        logger.error(".vtp files need pyvista (pip install pyvista)"); sys.exit(1)
    except Exception as e:
        logger.error(f"Could not read {path.name}: {e}"); sys.exit(1)

    print(f"\n{Colors.BOLD}{Colors.CYAN}File{Colors.RESET}")
    print(f"  {Colors.BOLD}File:{Colors.RESET} {path.name}  ({os.path.getsize(path) / 1e6:.1f} MB)")
    print(f"  {Colors.BOLD}Read by:{Colors.RESET} {backend}")
    print(f"  {Colors.BOLD}Points:{Colors.RESET} {len(pts):,}")
    print(f"  {Colors.BOLD}Cells:{Colors.RESET} " +
          (", ".join(f"{t}={n:,}" for t, n in cells) if cells else "(none — point cloud)"))

    problems = []
    if len(pts) == 0:
        problems.append("file has 0 points")
    if pts.size:
        lo = pts.min(axis=0); hi = pts.max(axis=0)
        print(f"  {Colors.BOLD}Bounds:{Colors.RESET} "
              f"x[{lo[0]:.4g}, {hi[0]:.4g}]  y[{lo[1]:.4g}, {hi[1]:.4g}]  z[{lo[2]:.4g}, {hi[2]:.4g}]")
        if not np.isfinite(pts).all():
            problems.append("non-finite point coordinates")

    print(f"\n{Colors.BOLD}{Colors.CYAN}Point data{Colors.RESET}")
    if not pdata:
        print("  (no point-data arrays)")
    for name, arr in pdata.items():
        flags = ""
        if arr.size and not np.isfinite(arr).all():
            nbad = int((~np.isfinite(arr)).sum())
            flags = f"  {Colors.RED}[{nbad} NaN/Inf]{Colors.RESET}"
            problems.append(f"array '{name}' has {nbad} NaN/Inf values")
        if arr.ndim == 1 and arr.size:
            fin = arr[np.isfinite(arr)]
            rng = f"{fin.min():.6g} .. {fin.max():.6g}" if fin.size else "n/a"
        else:
            rng = f"shape {arr.shape}"
        print(f"  {name:<14s} {rng}{flags}")
    return problems


def _check_pvd(path, logger):
    """Validate a .pvd collection: list timesteps, verify members, summarise one."""
    try:
        root = ET.parse(path).getroot()
    except Exception as e:
        logger.error(f"Could not parse collection {path.name}: {e}"); sys.exit(1)
    datasets = [(ds.get("timestep"), ds.get("file")) for ds in root.iter("DataSet")]

    print(f"\n{Colors.BOLD}{Colors.CYAN}Collection (.pvd){Colors.RESET}")
    print(f"  {Colors.BOLD}File:{Colors.RESET} {path.name}")
    print(f"  {Colors.BOLD}Timesteps:{Colors.RESET} {len(datasets)}"
          + (f"  ({', '.join(t for t, _ in datasets)})" if datasets else ""))

    problems = []
    if not datasets:
        problems.append("collection has no DataSet entries")
        return problems

    missing = [f for _, f in datasets if not (path.parent / f).exists()]
    if missing:
        problems.append(f"{len(missing)} referenced file(s) missing: {', '.join(missing[:5])}"
                        + (" …" if len(missing) > 5 else ""))
        print(f"  {Colors.RED}Missing:{Colors.RESET} {len(missing)} of {len(datasets)} members")
    else:
        print(f"  {Colors.GREEN}✓{Colors.RESET} all {len(datasets)} member files present")

    member = next(((t, f) for t, f in datasets if (path.parent / f).exists()), None)
    if member:
        print(f"  {Colors.BOLD}Representative member:{Colors.RESET} timestep {member[0]} → {member[1]}")
        problems += _report_file(path.parent / member[1], logger)
    return problems


def execute_check(args):
    from .help_messages import print_check_help

    if getattr(args, "help", False):
        print_check_help(); return

    logger = Logger(verbose=getattr(args, "verbose", False))
    if not getattr(args, "file", None):
        print_check_help(); sys.exit(1)

    path = Path(args.file)
    if not path.exists():
        logger.error(f"File not found: {path}"); sys.exit(1)

    ext = path.suffix.lower()
    if ext == ".pvd":
        problems = _check_pvd(path, logger)
        label = f"{path.name} (time series)"
    else:
        if ext not in (".vtu", ".vtk", ".vtp"):
            logger.warning(f"'{path.suffix}' is not a recognised extension "
                           "(.vtu/.vtk/.vtp/.pvd); trying anyway")
        problems = _report_file(path, logger)
        label = path.name

    print()
    if problems:
        for p in problems:
            logger.warning(p)
        logger.error(f"{label}: has issues (see above)")
        sys.exit(1)
    logger.success(f"{label}: valid")
