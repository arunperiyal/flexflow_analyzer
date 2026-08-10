"""
Case out command: what a case declares as output, and small files derived from it.

`--map` writes a node map per output block. A nodal outputTimeHistory writes its records
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

# How a reader should parameterise a probe set: arc length along a line, two
# coordinates on a surface, nothing shared between independent points. It cannot
# be derived from the coordinates -- a dense square grid snakes into a path with
# perfectly uniform steps, indistinguishable from a curve, and rank alone does not
# separate a ring from a grid. Nor is it in the .def or the .nbc, which carry only
# node ids and whether the block is nodal or coordinates. So it is declared.
PROBE_TYPES = ("point", "line", "helix", "surface", "cloud")
# Types that trace a curve, and so can be asked whether they join up. A helix is
# not merely a line: it wraps a body, so a reader may parameterise it by axial
# position and angle rather than by arc length alone.
CURVE_TYPES = ("line", "helix")


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


def _map_stem(block_name):
    """'riser_probe' -> 'riser_probe', the name a map file is built on.

    The block name, not its input file: two blocks may read the same node file at
    different frequencies, and naming maps after the file would put both on one
    path with the second overwriting the first. The name is also what the map
    header and the .def call the output, so the file agrees with its contents.
    """
    safe = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in block_name)
    return safe.strip("._") or "output"


def _set_name(node_file, problem):
    """'riser.cyl_nodes.nbc' -> 'cyl_nodes' (the part naming the node set).

    Only used to let --map NAME be given as the node set, which reads naturally
    even though maps are named after the block.
    """
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


def _is_index_column(values):
    """True if `values` read as a row index: whole numbers, strictly increasing."""
    numbers = []
    for value in values:
        try:
            number = float(value)
        except ValueError:
            return False
        if number != int(number):
            return False
        numbers.append(int(number))
    return all(b > a for a, b in zip(numbers, numbers[1:]))


def _stale_prediction(case_dir, blocks):
    """Input files added after the case's othd files were written, if any.

    A predicted othId describes what the solver *would* write now. If an input
    file appeared after the existing othd files, those files were written without
    it and their ids are one short -- exactly the case on BR0SG0U1P0, where
    probe_dat.txt arrived after the runs. Comparing timestamps cannot prove the
    ids are wrong, but it catches the arrangement that makes them wrong, which is
    otherwise silent.
    """
    case_dir = Path(case_dir)
    othd = list(case_dir.glob("othd_files/*.othd")) + list(case_dir.glob("*.othd"))
    if not othd:
        return []
    newest = max(f.stat().st_mtime for f in othd)
    later = []
    for block in blocks:
        source = block.get("nodes") or block.get("coordinates")
        path = case_dir / source if source else None
        if path and path.exists() and path.stat().st_mtime > newest:
            later.append(source)
    return later


def _read_coordinate_list(path):
    """Points from a `type = coordinates` probe file, in file order.

    That order indexes the othd exactly as a node file's does.

    The column layout is *established, not assumed*. A four-column file is
    `index x y z` -- but only once the leading column has been checked to read as
    an index, because taking the first three fields of such a file yields
    (1, 0, 0) where the point is (0, 0, 3): a wrong answer with nothing to show
    for it. A three-column file is `x y z`. Anything else raises rather than
    guesses, since being wrong here is silent and cheap to avoid.
    """
    rows, skipped = [], 0
    for raw in open(path):
        line = raw.split('#', 1)[0].strip()
        if not line:
            continue
        fields = line.split()
        if len(fields) in (3, 4):
            rows.append(fields)
        else:
            skipped += 1

    if not rows:
        raise WriteError(f"{Path(path).name} lists no coordinates")
    widths = {len(fields) for fields in rows}
    if len(widths) != 1:
        raise WriteError(f"{Path(path).name} mixes {sorted(widths)}-column rows; "
                         "expected every point on its own line as 'x y z' or "
                         "'index x y z'")

    if widths == {4}:
        if not _is_index_column([fields[0] for fields in rows]):
            raise WriteError(
                f"{Path(path).name} has 4 columns but the first does not read as a "
                "row index, so which three hold the coordinates is unclear. Expected "
                "'index x y z'.")
        columns = slice(1, 4)
    else:
        columns = slice(0, 3)

    points = []
    for fields in rows:
        try:
            points.append(tuple(f"{float(v):.16e}" for v in fields[columns]))
        except ValueError:
            raise WriteError(f"{Path(path).name}: '{' '.join(fields)}' does not hold "
                             "three coordinates")
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
                oth_id=None, skipped_before=0, stale=(), probe=None, closed=None):
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
        if stale:
            lines.append(
                "# WARNING: " + ", ".join(stale) + " is newer than this case's othd "
                "files, which were written without it -- ids there will be lower")
    if probe:
        lines.append(f"# probe: {probe}")
        if closed is not None:
            lines.append(f"# closed: {'yes' if closed else 'no'}")
        lines.append("# probe geometry declared with --probe-type; it is not derived "
                     "from the coordinates, which cannot distinguish these")
    lines += [
        f"# {provenance}: {source} ({source_count})",
        "# row = index of the record within each output block of the othd file",
        f"# {note}",
    ]
    return lines


def _write_node_map(path, block, node_file, crd_name, ids, coords, case_name, problem,
                    oth_id=None, skipped_before=0, stale=(), probe=None, closed=None):
    """A nodal block's map: othd row -> node id -> undeformed coordinates."""
    lines = _map_header(
        block, node_file, len(ids), case_name, problem,
        "nodes", "coordinates are undeformed (from " + crd_name
        + "): add the othd displacement for the moved position",
        oth_id, skipped_before, stale, probe, closed)
    lines.append(",".join(MAP_HEADER))
    for row, node in enumerate(ids):
        x, y, z = coords[node]
        lines.append(f"{row},{node},{x},{y},{z}")
    Path(path).write_text("\n".join(lines) + "\n")


def _write_point_map(path, block, point_file, points, case_name, problem,
                     oth_id=None, skipped_before=0, stale=(), probe=None, closed=None):
    """A coordinates block's map: othd row -> the point that was asked for.

    No mesh lookup: the points are in the probe file itself. There is no node
    column because a requested point need not sit on one.
    """
    lines = _map_header(
        block, point_file, len(points), case_name, problem, "coordinates",
        "coordinates are the points the block asked for, taken from " + point_file,
        oth_id, skipped_before, stale, probe, closed)
    lines.append(",".join(POINT_MAP_HEADER))
    for row, (x, y, z) in enumerate(points):
        lines.append(f"{row},{x},{y},{z}")
    Path(path).write_text("\n".join(lines) + "\n")


def write_case_maps(case_dir, wanted, logger, show_progress=False,
                    probe=None, closed=None):
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

    stale = _stale_prediction(case_dir, [b for b, _, _ in mappable])
    if stale:
        logger.warning(
            f"{', '.join(stale)} is newer than this case's othd files. Those were "
            "written without it, so their ids are lower than the ones predicted "
            "here -- read the ids from the othd and prefer them.")
    order = [b["name"] for b in blocks]
    written = []
    for block, key, source in mappable:
        rows = resolved[block["name"]]
        oth_id = oth_ids[block["name"]]
        # how many outputs declared before this one the solver does not write
        skipped_before = sum(1 for name in order[:order.index(block["name"])]
                             if oth_ids[name] is None)
        out = case_dir / f"othd.{_map_stem(block['name'])}.map"
        if key == "nodes":
            _write_node_map(out, block, source, crd_name, rows, coords,
                            case_dir.name, problem, oth_id, skipped_before, stale,
                            probe, closed)
        else:
            _write_point_map(out, block, source, rows, case_dir.name, problem,
                             oth_id, skipped_before, stale, probe, closed)
        written.append((out, len(rows)))
    return {"written": written, "crd": crd_name, "crd_mb": crd_mb}


def _read_map_declaration(path):
    """(probe, closed) declared in an existing map, or (None, None).

    The probe geometry lives in the map rather than the .def, because it is
    declared by a person -- so listing it means reading back what was written.
    """
    probe = closed = None
    try:
        for line in open(path):
            if not line.startswith("#"):
                break
            if line.startswith("# probe:"):
                probe = line.split(":", 1)[1].strip()
            elif line.startswith("# closed:"):
                closed = line.split(":", 1)[1].strip()
    except OSError:
        return None, None
    return probe, closed


def survey_time_history(case_dir, logger):
    """What the .def declares for time history, and what has been written for it.

    Reads both sides: the blocks come from the .def, the probe geometry from any
    map already written. Raises WriteError like the map path does, so a wildcard
    run over the registry can step over a case it cannot read.
    """
    case_dir = Path(case_dir)
    if not case_dir.is_dir():
        raise WriteError(f"Case directory not found: {case_dir}")
    problem = _problem_name(case_dir)
    def_file = find_def_file(str(case_dir), problem)
    if not def_file:
        raise WriteError(f"No .def file in {case_dir}", skip=True)

    blocks = parse_output_time_history(def_file)
    if not blocks:
        raise WriteError(f"{Path(def_file).name} declares no outputTimeHistory block",
                         skip=True)
    oth_ids = _oth_ids(blocks, case_dir)

    rows = []
    for block in blocks:
        source = block.get("nodes") or block.get("coordinates")
        source_path = case_dir / source if source else None
        map_path = case_dir / f"othd.{_map_stem(block['name'])}.map" if source else None
        probe, closed = _read_map_declaration(map_path) if (
            map_path and map_path.exists()) else (None, None)
        rows.append({
            "name": block["name"],
            "type": block.get("type") or "?",
            "file": source,
            "file_exists": bool(source_path and source_path.exists()),
            "oth_id": oth_ids[block["name"]],
            "map": map_path.name if map_path else None,
            "map_exists": bool(map_path and map_path.exists()),
            "probe": probe,
            "closed": closed,
        })
    return rows


def _print_survey(case_dir, rows):
    """The output-block table: what is declared, and what has been written for it."""
    from rich.console import Console
    from rich.table import Table
    from rich import box

    console = Console()
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold yellow",
                  title=f"outputTimeHistory in {Path(case_dir).name}",
                  title_justify="left", title_style="bold cyan")
    for name in ("Name", "File", "OthId", "Type", "MapFile", "Probe"):
        table.add_column(name)

    for row in rows:
        if row["file"] is None:
            source = "[dim]none[/dim]"
        elif row["file_exists"]:
            source = row["file"]
        else:
            source = f"[yellow]{row['file']}[/yellow] [dim](missing)[/dim]"
        # None means the solver writes no record for it, so it takes no id at all
        oth_id = str(row["oth_id"]) if row["oth_id"] is not None else "[dim]--[/dim]"
        mapped = (row["map"] if row["map_exists"]
                  else f"[dim]{row['map'] or '--'}[/dim]")
        probe = row["probe"] or "[dim]--[/dim]"
        if row["probe"] and row["closed"]:
            probe += f" [dim]({'closed' if row['closed'] == 'yes' else 'open'})[/dim]"
        table.add_row(row["name"], source, oth_id, row["type"],
                      mapped if row["map_exists"] else mapped, probe)

    console.print()
    console.print(table)
    missing = [r for r in rows if r["oth_id"] is None]
    console.print("[dim]OthId is predicted from the .def, not read from an othd. "
                  "Read it from the othd to be certain.[/dim]")
    if missing:
        console.print("[dim]-- under OthId: the input file is missing or empty, so the "
                      "solver writes no record and later ids shift down.[/dim]")
    if any(not r["map_exists"] for r in rows):
        console.print("[dim]A greyed MapFile has not been written yet; --map writes it. "
                      "Probe is declared with --probe-type and read back from the map.[/dim]")
    console.print()


def _write_all_cases(args, wanted, logger, probe=None, closed=None):
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
                                     show_progress=progress_enabled(args, 1),
                                     probe=probe, closed=closed)
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


def execute_out(args):
    from .help_messages import print_out_help

    if getattr(args, "help", False):
        print_out_help(); return

    logger = Logger(verbose=getattr(args, "verbose", False))
    if not args.case:
        print_out_help(); sys.exit(1)

    if getattr(args, "list", False):
        try:
            rows = survey_time_history(args.case, logger)
        except WriteError as exc:
            logger.error(str(exc))
            sys.exit(1)
        _print_survey(args.case, rows)
        return

    # --map alone is True; --map NAME carries the selector as its value.
    selector = getattr(args, "map", False)
    if not selector:
        logger.error("Nothing to do. Pass --list to see the case's output blocks, or "
                     "--map to write node maps for them.")
        print(); print_out_help(); sys.exit(1)
    wanted = selector if isinstance(selector, str) else None

    probe = getattr(args, "probe_type", None)
    if probe and probe not in PROBE_TYPES:
        logger.error(f"Unknown --probe-type '{probe}'. Choose one of: "
                     f"{', '.join(PROBE_TYPES)}")
        sys.exit(1)
    closed = getattr(args, "closed", False)
    if closed and probe not in CURVE_TYPES:
        logger.error("--closed describes whether a curve joins up, so it needs "
                     f"--probe-type {' or '.join(CURVE_TYPES)}.")
        sys.exit(1)
    closed = closed if probe in CURVE_TYPES else None

    if is_wildcard_case(args.case):
        _write_all_cases(args, wanted, logger, probe, closed)
        return

    try:
        result = write_case_maps(args.case, wanted, logger,
                                 show_progress=progress_enabled(args, 1),
                                 probe=probe, closed=closed)
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
