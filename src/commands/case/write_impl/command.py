"""
Case write command: generate small derived files from a case's inputs.

`--othd-map` is the first of them. A nodal outputTimeHistory writes its records
positionally -- row k of every aleDisp block is the k-th node of the node file it
was given, with no id and no coordinate in the othd itself. Reading one back
therefore needs the node file *and* the mesh coordinates, and the coordinates
file is the largest input in the case (137 MB for a 1.8M-node riser) even when
only a few dozen nodes are wanted.

This writes those few dozen out as `othd.<set>.map`, so the coordinates file can
be deleted and the othd stays readable.
"""

import sys
from pathlib import Path

from ....utils.logger import Logger
from ....utils.progress import progress_enabled, spinner
from ....core.parsers.def_parser import (find_def_file, parse_output_time_history,
                                         parse_node_coordinates)

MAP_HEADER = ["row", "node", "x", "y", "z"]


def _problem_name(case_dir):
    try:
        from ....core.simflow_config import SimflowConfig
        return SimflowConfig.find(case_dir).problem
    except Exception:
        return None


def _read_node_list(path, logger):
    """Node ids from a .nbc, in file order -- that order indexes the othd."""
    ids = []
    for lineno, raw in enumerate(open(path), start=1):
        line = raw.split('#', 1)[0].strip()
        if not line:
            continue
        for token in line.split():
            try:
                ids.append(int(token))
            except ValueError:
                logger.error(f"{Path(path).name}:{lineno}: '{token}' is not a node id")
                sys.exit(1)
    if not ids:
        logger.error(f"{Path(path).name} lists no nodes")
        sys.exit(1)
    return ids


def _read_coordinates(crd_path, wanted, logger):
    """Coordinates of `wanted` node ids, in one streamed pass over the .crd.

    The file is far too big to hold, and every map in a case is served from this
    single pass, so the ids of all of them are collected before it starts.
    """
    found = {}
    remaining = set(wanted)
    with open(crd_path) as fh:
        for raw in fh:
            parts = raw.split()
            if len(parts) < 4:
                continue
            try:
                node = int(parts[0])
            except ValueError:
                continue
            if node in remaining:
                found[node] = (parts[1], parts[2], parts[3])
                remaining.discard(node)
                if not remaining:
                    break
    if remaining:
        missing = sorted(remaining)
        shown = ", ".join(str(n) for n in missing[:8])
        logger.error(f"{len(missing)} node(s) listed in the node file are not in "
                     f"{Path(crd_path).name}: {shown}"
                     f"{' ...' if len(missing) > 8 else ''}")
        sys.exit(1)
    return found


def _write_map(path, block, node_file, crd_name, ids, coords, case_name, problem):
    """Write one map: othd row -> node id -> undeformed coordinates."""
    lines = [
        "# FlexFlow othd node map",
        f"# case: {case_name}   problem: {problem or '?'}",
        f"# outputTimeHistory: \"{block['name']}\"   type: {block['type']}"
        + (f"   outputFrequency: {block['outputFrequency']}"
           if block['outputFrequency'] is not None else ""),
        f"# nodes: {node_file} ({len(ids)})   coordinates: {crd_name}",
        "# row = index of the record within each aleDisp block of the othd file",
        "# coordinates are undeformed: add the othd displacement for the moved position",
        ",".join(MAP_HEADER),
    ]
    for row, node in enumerate(ids):
        x, y, z = coords[node]
        lines.append(f"{row},{node},{x},{y},{z}")
    Path(path).write_text("\n".join(lines) + "\n")


def execute_write(args):
    from .help_messages import print_write_help

    if getattr(args, "help", False):
        print_write_help(); return

    logger = Logger(verbose=getattr(args, "verbose", False))
    # --othd-map alone is True; --othd-map NAME carries the selector as its value.
    selector = getattr(args, "othd_map", False)
    if not selector:
        logger.error("Nothing to write. Pass --othd-map to build node maps for the "
                     "case's nodal outputTimeHistory blocks.")
        print(); print_write_help(); sys.exit(1)
    if not args.case:
        print_write_help(); sys.exit(1)

    case_dir = Path(args.case)
    if not case_dir.is_dir():
        logger.error(f"Case directory not found: {case_dir}"); sys.exit(1)
    problem = _problem_name(case_dir)

    def_file = find_def_file(str(case_dir), problem)
    if not def_file:
        logger.error(f"No .def file in {case_dir}"); sys.exit(1)
    logger.info(f"Reading {Path(def_file).name}")

    blocks = parse_output_time_history(def_file)
    nodal = [b for b in blocks if (b.get("type") or "").lower() == "nodal" and b.get("nodes")]
    skipped = [b for b in blocks if b not in nodal]
    if not nodal:
        logger.error(f"{Path(def_file).name} has no nodal outputTimeHistory block with a "
                     "node file; nothing to map."
                     + (f" ({len(skipped)} other block(s) present)" if skipped else ""))
        sys.exit(1)
    for block in skipped:
        logger.info(f"skipping outputTimeHistory \"{block['name']}\" "
                    f"(type {block.get('type')}) -- only nodal blocks are mapped")

    wanted = selector if isinstance(selector, str) else None
    if wanted:
        nodal = [b for b in nodal if wanted in (b["name"], _set_name(b["nodes"], problem))]
        if not nodal:
            logger.error(f"No nodal outputTimeHistory matches '{wanted}'.")
            sys.exit(1)

    crd_name = parse_node_coordinates(def_file)
    if not crd_name:
        logger.error(f"{Path(def_file).name} has no nodeCoordinates{{ coordinates = File(..) }}")
        sys.exit(1)
    crd_path = case_dir / crd_name
    if not crd_path.exists():
        logger.error(f"Coordinates file not found: {crd_path}. It is needed once to "
                     "build the maps; after that it can be removed.")
        sys.exit(1)

    # Every map is served from one pass over the coordinates file.
    per_block = {}
    for block in nodal:
        node_path = case_dir / block["nodes"]
        if not node_path.exists():
            logger.error(f"Node file not found: {node_path} "
                         f"(from outputTimeHistory \"{block['name']}\")")
            sys.exit(1)
        per_block[block["name"]] = _read_node_list(node_path, logger)

    every = sorted({n for ids in per_block.values() for n in ids})
    size_mb = crd_path.stat().st_size / 1e6
    logger.info(f"Looking up {len(every):,} node(s) in {crd_name} ({size_mb:,.0f} MB)")
    with spinner(f"Reading {crd_name}", enabled=progress_enabled(args, 1)):
        coords = _read_coordinates(crd_path, every, logger)

    written = []
    for block in nodal:
        ids = per_block[block["name"]]
        out = case_dir / f"othd.{_set_name(block['nodes'], problem)}.map"
        _write_map(out, block, block["nodes"], crd_name, ids, coords,
                   case_dir.name, problem)
        written.append((out, len(ids)))
        print(f"Wrote {len(ids)} row(s) -> {out}")

    total = sum(n for _, n in written)
    print(f"{len(written)} map(s), {total} node(s). "
          f"{crd_name} ({size_mb:,.0f} MB) is no longer needed to read these othd records.")


def _set_name(node_file, problem):
    """'riser.cyl_nodes.nbc' -> 'cyl_nodes' (the part naming the node set)."""
    stem = Path(node_file).name
    for suffix in (".nbc", ".txt", ".dat"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    if problem and stem.startswith(problem + "."):
        stem = stem[len(problem) + 1:]
    return stem or "nodes"
