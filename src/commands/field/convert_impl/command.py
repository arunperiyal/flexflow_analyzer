"""
Field convert command implementation -- PLT -> VTU (Tecplot-free).
"""

import sys
from pathlib import Path

from ....utils.logger import Logger
from ....plt.fxplt import PltFile
from ....plt.convert import audit, to_vtu
from ..locate import problem_name, find_plt, zone_index


def execute_convert(args):
    from .help_messages import print_convert_help

    if getattr(args, "help", False):
        print_convert_help(); return

    logger = Logger(verbose=getattr(args, "verbose", False))
    if not args.case:
        print_convert_help(); sys.exit(1)

    case_dir = Path(args.case)
    binary_dir = case_dir / "binary"
    if not binary_dir.exists():
        logger.error(f"Binary directory not found: {binary_dir}"); sys.exit(1)

    problem = problem_name(case_dir)
    plt_path = find_plt(binary_dir, problem, getattr(args, "timestep", None))
    if not plt_path:
        which = f"timestep {args.timestep}" if getattr(args, "timestep", None) else "any timestep"
        logger.error(f"No PLT file for {which} in {binary_dir}"); sys.exit(1)

    plt = PltFile(plt_path)
    zi = plt.first_volume_zone()
    if getattr(args, "zone", None):
        zi = zone_index(plt, args.zone)
        if zi is None:
            logger.error(f"Zone '{args.zone}' not found. Available: "
                         f"{', '.join(z['name'] for z in plt.zones)}"); sys.exit(1)

    nen = getattr(args, "nen", None)

    if getattr(args, "audit_only", False):
        a = audit(plt, zi, nen=nen)
        logger.info(f"{plt_path.name}  zone '{a['zone_name']}'")
        print(f"  element type      : {a['cell']} ({a['npe']} nodes/elem; "
              f"declared {a['declared_npe']})")
        print(f"  nodes / elements  : {a['npts']:,} / {a['nelem']:,}")
        print(f"  file size         : {a['file_size'] / 1e6:.1f} MB")
        print(f"  zone needs        : {a['zone_need'] / 1e6:.1f} MB")
        if a["truncated"]:
            logger.warning(f"SHORT by {a['short_by'] / 1e6:.1f} MB -> truncated, "
                           "or wrong nodes/elem (try --nen)")
        else:
            logger.success("file size consistent for this zone")
        return

    domain = {k: getattr(args, k, None) for k in ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")}
    out = args.output if getattr(args, "output", None) else None
    try:
        out_path, info = to_vtu(str(plt_path), out, zone=zi, nen=nen, domain=domain)
    except Exception as e:
        logger.error(f"Conversion failed: {e}"); sys.exit(1)

    if info.get("truncated"):
        logger.warning(f"connectivity incomplete: kept {info['nhex_valid']:,} of "
                       f"{info['nelem']:,} cells ({100.0 * info['nhex_valid'] / info['nelem']:.1f}%)")
    if info.get("cropped"):
        logger.info(f"cropped to box {{{', '.join(f'{k}={v}' for k, v in domain.items() if v is not None)}}}")
    import os
    logger.success(f"wrote {out_path} ({os.path.getsize(out_path) / 1e6:.0f} MB, "
                   f"{info['cell']}, {info['cells_out']:,} cells)")
