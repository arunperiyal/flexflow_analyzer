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

Accepts the `*` wildcard case, in which case every case in the `.cases` registry
is done in turn -- and a case that cannot be done is reported and stepped over
rather than ending the batch.
"""

import sys
from pathlib import Path

from ....utils.logger import Logger
from ....utils.progress import progress_enabled, spinner
from ....core.parsers.def_parser import (find_def_file, parse_output_time_history,
                                         parse_node_coordinates)
from ...case_iteration import is_wildcard_case, load_cases_from_directory

MAP_HEADER = ["row", "node", "x", "y", "z"]
POINT_MAP_HEADER = ["row", "x", "y", "z"]


class WriteError(Exception):
    """A case could not be mapped. `skip` marks the harmless kind: nothing to do."""

    def __init__(self, message, skip=False):
        super().__init__(message)
        self.skip = skip


def _problem_name(case_dir):
    try:
        from ....core.simflow_config import SimflowConfig
        return SimflowConfig.find(case_dir).problem
    except Exception:
        return None


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


def _oth_ids(blocks, case_dir):
    """Predict each block's othId -- its position among the outputs actually written.

    Declaration order in the .def does not give it. An output whose input file is
    missing or empty is not written at all, and every id after it shifts down: on
    BR0SG0U1P0 `probe_dat.txt` is absent, so "riser_probe" lands on othId 0 rather
    than 1. A reader holding two maps and no id cannot tell them apart except by
    node count, which collides the moment two probes are the same size.

    Returns {block name: othId or None}, None meaning the solver writes no record
    for it. A block naming no input file is assumed to be written, since there is
    nothing that could be missing.
    """
    ids, next_id = {}, 0
    for block in blocks:
        source = block.get("nodes") or block.get("coordinates")
        if source:
            path = Path(case_dir) / source
            if not path.exists() or path.stat().st_size == 0:
                ids[block["name"]] = None
                continue
        ids[block["name"]] = next_id
        next_id += 1
    return ids


def _read_coordinate_list(path):
    """Points from a `type = coordinates` probe file, in file order.

    That order indexes the othd exactly as a node file's does. The format is one
    point per line as x y z; anything that does not start with three numbers (a
    count header, a comment, a blank) is passed over, and the count of skipped
    lines is returned so the caller can say so rather than quietly losing rows.
    """
    points, skipped = [], 0
    for raw in open(path):
        line = raw.split('#', 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        try:
            points.append(tuple(f"{float(v):.16e}" for v in parts[:3]))
        except (ValueError, IndexError):
            skipped += 1
            continue
        if len(parts) < 3:
            points.pop()
            skipped += 1
    if not points:
        raise WriteError(f"{Path(path).name} lists no coordinates")
    return points, skipped


def _read_node_list(path):
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
                raise WriteError(f"{Path(path).name}:{lineno}: '{token}' is not a node id")
    if not ids:
        raise WriteError(f"{Path(path).name} lists no nodes")
    return ids


def _read_coordinates(crd_path, wanted):
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
        raise WriteError(f"{len(missing)} node(s) listed in the node file are not in "
                         f"{Path(crd_path).name}: {shown}"
                         f"{' ...' if len(missing) > 8 else ''}")
    return found


def _map_header(block, source, source_count, case_name, problem, provenance, note,
                oth_id=None, skipped_before=0):
    """The '#' block every map carries, saying where its rows came from.

    `othId` says which output within the othd this map describes. It is predicted
    from the .def, not read from an othd, so its basis is stated alongside it: a
    reader that trusts a wrong id is worse off than one that has none.
    """
    lines = [
        "# FlexFlow othd map",
        f"# case: {case_name}   problem: {problem or '?'}",
        f"# outputTimeHistory: \"{block['name']}\"   type: {block['type']}"
        + (f"   outputFrequency: {block['outputFrequency']}"
           if block['outputFrequency'] is not None else ""),
    ]
    if oth_id is not None:
        basis = (f"{skipped_before} earlier output(s) not written (input file missing "
                 "or empty)" if skipped_before else "no earlier output is skipped")
        lines += [f"# othId: {oth_id}",
                  f"# othId predicted from the .def, not read from an othd: {basis}"]
    lines += [
        f"# {provenance}: {source} ({source_count})",
        "# row = index of the record within each output block of the othd file",
        f"# {note}",
    ]
    return lines


def _write_node_map(path, block, node_file, crd_name, ids, coords, case_name, problem,
                    oth_id=None, skipped_before=0):
    """A nodal block's map: othd row -> node id -> undeformed coordinates."""
    lines = _map_header(
        block, node_file, len(ids), case_name, problem,
        "nodes", "coordinates are undeformed (from " + crd_name
        + "): add the othd displacement for the moved position",
        oth_id, skipped_before)
    lines.append(",".join(MAP_HEADER))
    for row, node in enumerate(ids):
        x, y, z = coords[node]
        lines.append(f"{row},{node},{x},{y},{z}")
    Path(path).write_text("\n".join(lines) + "\n")


def _write_point_map(path, block, point_file, points, case_name, problem,
                     oth_id=None, skipped_before=0):
    """A coordinates block's map: othd row -> the point that was asked for.

    No mesh lookup: the points are in the probe file itself. There is no node
    column because a requested point need not sit on one.
    """
    lines = _map_header(
        block, point_file, len(points), case_name, problem, "coordinates",
        "coordinates are the points the block asked for, taken from " + point_file,
        oth_id, skipped_before)
    lines.append(",".join(POINT_MAP_HEADER))
    for row, (x, y, z) in enumerate(points):
        lines.append(f"{row},{x},{y},{z}")
    Path(path).write_text("\n".join(lines) + "\n")


def write_case_maps(case_dir, wanted, logger, show_progress=False):
    """Build every requested othd map for one case.

    Returns {'written': [(path, rows), ...], 'crd': name, 'crd_mb': size}.
    Raises WriteError -- with skip=True when the case simply has nothing to map.
    """
    case_dir = Path(case_dir)
    if not case_dir.is_dir():
        raise WriteError(f"Case directory not found: {case_dir}")
    problem = _problem_name(case_dir)

    def_file = find_def_file(str(case_dir), problem)
    if not def_file:
        raise WriteError(f"No .def file in {case_dir}", skip=True)
    logger.info(f"Reading {Path(def_file).name}")

    blocks = parse_output_time_history(def_file)
    oth_ids = _oth_ids(blocks, case_dir)
    mappable = []
    for block in blocks:
        kind = (block.get("type") or "").lower()
        source = None
        if kind == "nodal" and block.get("nodes"):
            source = ("nodes", block["nodes"])
        elif kind == "coordinates" and block.get("coordinates"):
            source = ("coordinates", block["coordinates"])
        if source is None:
            logger.info(f"skipping outputTimeHistory \"{block['name']}\": type "
                        f"{block.get('type') or 'unset'} names no file to index its "
                        "records by")
            continue
        if oth_ids[block["name"]] is None:
            # The solver writes no record for it, so there is nothing to map onto.
            logger.info(f"skipping outputTimeHistory \"{block['name']}\": "
                        f"{source[1]} is missing or empty, so the solver writes no "
                        "record for it")
            continue
        mappable.append((block, source[0], source[1]))
    if not mappable:
        raise WriteError(f"{Path(def_file).name} has no outputTimeHistory block whose "
                         "records can be mapped", skip=True)

    if wanted:
        named = [entry for entry in mappable
                 if wanted in (entry[0]["name"], _set_name(entry[2], problem))]
        if not named:
            # Naming a block whose input file is absent is a mistake worth reporting,
            # rather than the silent skip that scanning every block gets.
            for block in blocks:
                src = block.get("nodes") or block.get("coordinates")
                if src and wanted in (block["name"], _set_name(src, problem)):
                    raise WriteError(
                        f"outputTimeHistory \"{block['name']}\" names {src}, which is "
                        "missing or empty; the solver writes no record for it")
            raise WriteError(f"No outputTimeHistory matches '{wanted}'", skip=True)
        mappable = named

    # The mesh is only needed if a nodal block is in play; a case of nothing but
    # coordinates blocks maps fine without it.
    nodal = [(block, source) for block, key, source in mappable if key == "nodes"]
    crd_name, crd_path, crd_mb = None, None, 0.0
    if nodal:
        crd_name = parse_node_coordinates(def_file)
        if not crd_name:
            raise WriteError(f"{Path(def_file).name} has no "
                             "nodeCoordinates{ coordinates = File(..) }")
        crd_path = case_dir / crd_name
        if not crd_path.exists():
            raise WriteError(f"Coordinates file not found: {crd_path}. It is needed "
                             "once to build the maps; after that it can be removed.")
        crd_mb = crd_path.stat().st_size / 1e6

    resolved = {}
    for block, key, source in mappable:
        source_path = case_dir / source
        if not source_path.exists():
            raise WriteError(f"{key.capitalize()} file not found: {source_path} "
                             f"(from outputTimeHistory \"{block['name']}\")")
        if key == "nodes":
            resolved[block["name"]] = _read_node_list(source_path)
        else:
            points, dropped = _read_coordinate_list(source_path)
            if dropped:
                logger.info(f"{source}: {dropped} line(s) held no x y z and were passed over")
            resolved[block["name"]] = points

    coords = {}
    if nodal:
        # Every nodal map in this case is served from one pass over the mesh.
        every = sorted({n for block, _ in nodal for n in resolved[block["name"]]})
        logger.info(f"Looking up {len(every):,} node(s) in {crd_name} ({crd_mb:,.0f} MB)")
        with spinner(f"Reading {crd_name}", enabled=show_progress):
            coords = _read_coordinates(crd_path, every)

    order = [b["name"] for b in blocks]
    written = []
    for block, key, source in mappable:
        rows = resolved[block["name"]]
        oth_id = oth_ids[block["name"]]
        # how many outputs declared before this one the solver does not write
        skipped_before = sum(1 for name in order[:order.index(block["name"])]
                             if oth_ids[name] is None)
        out = case_dir / f"othd.{_set_name(source, problem)}.map"
        if key == "nodes":
            _write_node_map(out, block, source, crd_name, rows, coords,
                            case_dir.name, problem, oth_id, skipped_before)
        else:
            _write_point_map(out, block, source, rows, case_dir.name, problem,
                             oth_id, skipped_before)
        written.append((out, len(rows)))
    return {"written": written, "crd": crd_name, "crd_mb": crd_mb}


def _write_all_cases(args, wanted, logger):
    """Run over every case in the .cases registry, stepping over the ones that fail."""
    from rich.console import Console

    console = Console()
    cases = load_cases_from_directory(Path.cwd())
    if not cases:
        logger.error(f"No cases found. Is there a .cases file in {Path.cwd()}? "
                     "Build one with `case add`.")
        sys.exit(1)

    console.print(f"\n[bold cyan]Writing othd maps for {len(cases)} case(s)[/bold cyan]\n")
    done, skipped, failed, maps = [], [], [], 0
    for entry in cases:
        name = entry.get("name", "?")
        path = entry.get("path")
        if not path:
            failed.append((name, "no path in .cases"))
            continue
        try:
            result = write_case_maps(path, wanted, logger,
                                     show_progress=progress_enabled(args, 1))
        except WriteError as exc:
            (skipped if exc.skip else failed).append((name, str(exc)))
            mark = "[dim]-[/dim]" if exc.skip else "[yellow]![/yellow]"
            console.print(f"  {mark} [bold]{name}[/bold]: {exc}")
            continue
        maps += len(result["written"])
        done.append(name)
        files = ", ".join(p.name for p, _ in result["written"])
        rows = sum(n for _, n in result["written"])
        console.print(f"  [green]+[/green] [bold]{name}[/bold]: {files} ({rows} row(s))")

    console.print()
    console.print(f"[bold]{len(done)} case(s) mapped[/bold], {maps} file(s) written"
                  + (f"; {len(skipped)} skipped" if skipped else "")
                  + (f"; [yellow]{len(failed)} failed[/yellow]" if failed else ""))
    if failed and not done:
        sys.exit(1)


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
    wanted = selector if isinstance(selector, str) else None

    if is_wildcard_case(args.case):
        _write_all_cases(args, wanted, logger)
        return

    try:
        result = write_case_maps(args.case, wanted, logger,
                                 show_progress=progress_enabled(args, 1))
    except WriteError as exc:
        logger.error(str(exc))
        sys.exit(1)

    for path, rows in result["written"]:
        print(f"Wrote {rows} row(s) -> {path}")
    total = sum(n for _, n in result["written"])
    summary = f"{len(result['written'])} map(s), {total} row(s)."
    if result["crd"]:
        summary += (f" {result['crd']} ({result['crd_mb']:,.0f} MB) is no longer needed "
                    "to read these othd records.")
    print(summary)
