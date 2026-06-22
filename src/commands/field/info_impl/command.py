"""
Field info command implementation (Tecplot-free, uses src/plt/fxplt).
"""

import re
import sys
from pathlib import Path

from ....utils.logger import Logger
from ....utils.colors import Colors
from ....plt.fxplt import PltFile, ZTYPE_VTK
from ....plt.convert import audit


def _hdr(text):
    print(f"\n{Colors.BOLD}{Colors.CYAN}{text}{Colors.RESET}")


def _pick_plt(binary_dir, problem, sample_file):
    """Choose which PLT file to inspect (a given step, else the latest)."""
    plt_files = sorted(binary_dir.glob("*.plt"))
    if not plt_files:
        return None, plt_files
    if sample_file is not None:
        for f in plt_files:
            m = re.search(r"\.(\d+)\.plt$", f.name)
            if m and int(m.group(1)) == sample_file:
                return f, plt_files
        return None, plt_files
    # latest timestep
    def step(f):
        m = re.search(r"\.(\d+)\.plt$", f.name)
        return int(m.group(1)) if m else -1
    return max(plt_files, key=step), plt_files


def execute_info(args):
    """Show PLT file information."""
    from .help_messages import print_info_help

    if getattr(args, "help", False):
        print_info_help()
        return

    logger = Logger(verbose=getattr(args, "verbose", False))
    if not args.case:
        print_info_help(); sys.exit(1)

    case_dir = Path(args.case)
    binary_dir = case_dir / "binary"
    if not binary_dir.exists():
        logger.error(f"Binary directory not found: {binary_dir}"); sys.exit(1)

    try:
        from ....core.simflow_config import SimflowConfig
        problem = SimflowConfig.find(case_dir).problem
    except Exception:
        problem = None

    plt_path, all_plt = _pick_plt(binary_dir, problem, getattr(args, "sample_file", None))
    if not all_plt:
        logger.error(f"No PLT files found in {binary_dir}"); sys.exit(1)
    if plt_path is None:
        logger.error(f"Timestep {args.sample_file} not found in {binary_dir}"); sys.exit(1)

    try:
        plt = PltFile(plt_path)
    except Exception as e:
        logger.error(f"Failed to parse {plt_path.name}: {e}"); sys.exit(1)

    # which sections to show
    flags = ["basic", "variables", "zones", "checks", "stats"]
    chosen = [f for f in flags if getattr(args, f, False)]
    show = (lambda s: True) if not chosen else (lambda s: s in chosen)
    detailed = getattr(args, "detailed", False)

    if show("basic"):
        _hdr("File")
        import os
        print(f"  {Colors.BOLD}File:{Colors.RESET} {plt_path.name}")
        print(f"  {Colors.BOLD}Path:{Colors.RESET} {plt_path}")
        print(f"  {Colors.BOLD}Size:{Colors.RESET} {os.path.getsize(plt_path) / 1e6:.1f} MB")
        print(f"  {Colors.BOLD}Problem:{Colors.RESET} {problem or '(unknown)'}")
        print(f"  {Colors.BOLD}Variables:{Colors.RESET} {len(plt.vars)}")
        print(f"  {Colors.BOLD}Zones:{Colors.RESET} {len(plt.zones)}")
        print(f"  {Colors.BOLD}PLT files in case:{Colors.RESET} {len(all_plt)}")

    if show("variables"):
        _hdr("Variables")
        for i, v in enumerate(plt.vars):
            print(f"  {i + 1:2d}. {v}")

    if show("zones"):
        _hdr("Zones")
        for z in plt.zones:
            npe = {1: 2, 2: 3, 3: 4, 4: 4, 5: 8}.get(z["ztype"], 8)
            print(f"  {Colors.BOLD}{z['name']}{Colors.RESET}: "
                  f"{ZTYPE_VTK.get(z['ztype'], 'type%d' % z['ztype'])}, "
                  f"{npe} nodes/elem, nodes={z['npts']:,}, elements={z['nelem']:,}")

    if show("checks"):
        _hdr("Consistency checks")
        # naming convention
        if problem:
            pat = re.compile(rf"^{re.escape(problem)}\.\d+\.plt$")
            bad = [f.name for f in all_plt if not pat.match(f.name)]
            if bad:
                print(f"  {Colors.YELLOW}!{Colors.RESET} {len(bad)} file(s) off naming "
                      f"pattern {problem}.NNNN.plt (e.g. {bad[0]})")
            else:
                print(f"  {Colors.GREEN}✓{Colors.RESET} naming follows {problem}.NNNN.plt")
        else:
            print(f"  {Colors.YELLOW}!{Colors.RESET} problem name unknown (simflow.config)")

        # element-type / size audit for the volume zone
        zi = plt.first_volume_zone()
        a = audit(plt, zi)
        zname = a["zone_name"]
        print(f"  zone '{zname}': {a['cell']} ({a['npe']} nodes/elem), "
              f"{a['nelem']:,} elements, {a['npts']:,} nodes")
        if a["truncated"]:
            print(f"  {Colors.RED}✗ file is SHORT by {a['short_by'] / 1e6:.1f} MB for this "
                  f"zone -- likely truncated, or wrong nodes/elem{Colors.RESET}")
        else:
            print(f"  {Colors.GREEN}✓{Colors.RESET} file size consistent with "
                  f"{a['cell']} connectivity")
        if a["ztype"] == 4:
            print(f"  {Colors.YELLOW}!{Colors.RESET} volume zone is FETETRAHEDRON (4-node). "
                  f"If the mesh is 8-node bricks this means simflow.config "
                  f"{Colors.BOLD}nen=4{Colors.RESET}; set {Colors.BOLD}nen=8{Colors.RESET} and re-run simPlt.")

    if show("stats"):
        _hdr("Data ranges (min / max)")
        try:
            mm = plt.minmax(plt.first_volume_zone())
            for v, rng in mm.items():
                if rng is None:
                    print(f"  {v:<12s} (shared)")
                else:
                    print(f"  {v:<12s} {rng[0]:14.6g}  {rng[1]:14.6g}")
                    if detailed and (abs(rng[0]) > 1e6 or abs(rng[1]) > 1e6):
                        print(f"  {Colors.YELLOW}    ^ very large magnitude{Colors.RESET}")
        except Exception as e:
            print(f"  {Colors.YELLOW}!{Colors.RESET} could not read data ranges: {e}")

    print()
