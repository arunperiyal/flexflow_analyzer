"""
`data stats` -- one row per variable instead of one row per timestep.

The functions are the ones asked of a vibration signal: how far it swings, how
hard, and -- the one that is not a number about the signal but a pointer back
into the run -- where the swing happened.
"""

import sys

import numpy as np
from rich.console import Console
from rich import box
from rich.table import Table

from ....utils.logger import Logger
from .. import shared

# Every function is over the selected window, on the selected node.
FUNCS = {
    "min":    ("smallest value", lambda v: float(np.nanmin(v))),
    "max":    ("largest value", lambda v: float(np.nanmax(v))),
    "mean":   ("arithmetic mean", lambda v: float(np.nanmean(v))),
    "rms":    ("root mean square", lambda v: float(np.sqrt(np.nanmean(v ** 2)))),
    "std":    ("standard deviation", lambda v: float(np.nanstd(v))),
    "range":  ("max - min, the peak-to-peak swing", lambda v: float(np.nanmax(v) - np.nanmin(v))),
    "maxloc": ("where the maximum occurs, and which PLT shows it", None),
    "minloc": ("where the minimum occurs, and which PLT shows it", None),
    "zeroloc": ("where the signal crosses zero, and which PLT shows it", None),
}
# maxloc answers a different question from the rest -- a location, not a value --
# so it is computed against the tsIds rather than the samples alone.
LOCATORS = ("maxloc", "minloc", "zeroloc")


def plt_rows(tsids, freq):
    """Indices of the rows that also have a PLT written for them.

    Taken from the steps the data actually covers rather than from arithmetic
    on freq, so a run that stopped between two outputs never offers a file that
    was never written.
    """
    if not freq:
        return np.zeros(len(tsids), dtype=bool)
    return (np.asarray(tsids) % freq) == 0


def _locate(values, tsids, times, freq, direction, runners=3):
    """Where the extreme is, and which PLT file comes closest to it.

    `direction` is "max" or "min", and it means the signed extreme, not the
    largest excursion either way. Asking for the max and being sent to a file
    holding a large negative is the opposite half of the cycle, whatever its
    magnitude; the other end of the swing has its own question.

    The PLT to render is the one whose own value is most extreme in that
    direction, not the one nearest the peak. Distance is only a proxy for
    amplitude and a poor one: over this repo's sample case the nearest file is
    not the strongest in about three windows out of four. The peak almost
    always falls between two outputs, so the question is never "where is the
    extreme" but "which of the files I have comes closest to it" -- and that is
    read off the files rather than inferred.

    The runners-up come back too, because a frame is also chosen on what else
    is in it, and the second-best file is often as good a picture.
    """
    high = direction == "max"
    idx = int(np.nanargmax(values) if high else np.nanargmin(values))
    found = {
        "direction": direction,
        "value": float(values[idx]),
        "tsId": int(tsids[idx]),
        "time": float(times[idx]),
        "plt_tsId": None,
        "plt_value": None,
        "plt_count": 0,
        "plt_ranked": [],
    }
    rows = plt_rows(tsids, freq)
    if not rows.any():
        return found

    plt_ts = np.asarray(tsids)[rows]
    plt_v = np.asarray(values)[rows]
    # Most extreme first; ties to the earlier file so the answer is stable.
    order = sorted(range(len(plt_ts)),
                   key=lambda i: (-plt_v[i] if high else plt_v[i], plt_ts[i]))
    found["plt_count"] = len(plt_ts)
    found["plt_ranked"] = [(int(plt_ts[i]), float(plt_v[i]))
                           for i in order[:1 + runners]]
    found["plt_tsId"] = int(plt_ts[order[0]])
    found["plt_value"] = float(plt_v[order[0]])
    return found


def _maxloc(values, tsids, times, freq, runners=3):
    return _locate(values, tsids, times, freq, "max", runners)


def _minloc(values, tsids, times, freq, runners=3):
    return _locate(values, tsids, times, freq, "min", runners)


def _crossings(values, direction):
    """Indices i where the signal crosses zero between sample i and i+1.

    Literal zero, not the window's mean: "the displacement is zero" is a
    statement about the cylinder's undeflected position, and a signal with a
    steady offset crossing its own mean is a different question from crossing
    the axis.
    """
    v = np.asarray(values, dtype=float)
    if len(v) < 2:
        return np.array([], dtype=int)
    if direction == "descending":
        return np.where((v[:-1] > 0) & (v[1:] <= 0))[0]
    return np.where((v[:-1] < 0) & (v[1:] >= 0))[0]


def _zeroloc(values, tsids, times, freq, direction, runners=3):
    """The zero crossing best captured by an existing PLT, and the runners-up.

    A settled run crosses zero once per half cycle -- six times in a window
    that holds three cycles -- so "the crossing" has to be chosen. It is chosen
    the way maxloc chooses: by which of the files on disk comes closest to
    showing it. A crossing no PLT sits near cannot be rendered, whatever its
    other merits.

    Candidates are the PLT steps moving in the right direction, ranked by how
    close to zero they are. Direction is read off the local slope, so a step at
    the top of the swing on its way down is descending even though its value is
    nowhere near zero -- it simply ranks last.

    No sample lands exactly on zero, so a crossing is reported as whichever of
    the two straddling samples is nearer to it.
    """
    v = np.asarray(values, dtype=float)
    found = {
        "direction": direction,
        "count": 0,
        "tsId": None, "time": None, "value": None,
        "plt_tsId": None, "plt_value": None, "plt_ranked": [], "plt_offset": None,
    }
    cross = _crossings(v, direction)
    found["count"] = len(cross)
    if not len(cross):
        return found

    # Each crossing stands at whichever of its two samples is nearer zero.
    reps = np.array([i if abs(v[i]) <= abs(v[i + 1]) else i + 1 for i in cross])

    def stand_at(idx):
        found["tsId"] = int(tsids[idx])
        found["time"] = float(times[idx])
        found["value"] = float(v[idx])

    slope = np.gradient(v) if len(v) > 1 else np.zeros_like(v)
    moving = slope < 0 if direction == "descending" else slope > 0
    candidates = np.where(plt_rows(tsids, freq) & moving)[0]
    if not len(candidates):
        # Nothing on disk to render it with; the last crossing is the most
        # settled one, which is the best that can be said without files.
        stand_at(reps[-1])
        return found

    order = sorted(candidates, key=lambda i: (abs(v[i]), int(tsids[i])))
    found["plt_ranked"] = [(int(tsids[i]), float(v[i])) for i in order[:1 + runners]]
    best = order[0]
    found["plt_tsId"] = int(tsids[best])
    found["plt_value"] = float(v[best])
    # How near zero the best file actually is, as a fraction of the swing. When
    # the output frequency is coarse against the period every file can land on
    # a peak, and the closest descending one is then a crest -- the right answer
    # to the question asked, and a poor picture of a crossing. Say so.
    amplitude = float(np.nanmax(np.abs(v))) or 1.0
    found["plt_offset"] = abs(found["plt_value"]) / amplitude
    # Report the crossing that file actually sits on.
    stand_at(reps[int(np.argmin(np.abs(tsids[reps] - tsids[best])))])
    return found


def _runners_up(found):
    """The PLT steps behind the best one, with what each would show."""
    rest = found["plt_ranked"][1:]
    if not rest:
        return "-"
    return ", ".join(f"{ts} ({value:.3e})" for ts, value in rest)


def execute_statistics(args):
    """Execute `data stats`."""
    from .help_messages import print_statistics_help, print_statistics_examples

    if getattr(args, "help", False):
        print_statistics_help()
        return
    if getattr(args, "examples", False):
        print_statistics_examples()
        return
    logger = Logger(verbose=getattr(args, "verbose", False))
    if not getattr(args, "case", None):
        shared.no_case(args, logger, print_statistics_help, ('var', 'func', 't1', 't2', 'node', 'output', 'group'))
        return

    case_dir = shared.resolve_case(args.case, logger)

    funcs = shared.split_vars(getattr(args, "func", None))
    if not funcs:
        logger.error("--func says what to work out. One or more of:\n"
                     + "\n".join(f"          {name:<8} {why}"
                                 for name, (why, _) in FUNCS.items())
                     + "\n        e.g. --func max,rms  or  --func maxloc")
        sys.exit(1)
    unknown = [f for f in funcs if f.lower() not in FUNCS]
    if unknown:
        logger.error(f"unknown --func: {', '.join(unknown)}. "
                     f"Available: {', '.join(FUNCS)}")
        sys.exit(1)
    funcs = [f.lower() for f in funcs]

    kinds = shared.which_kinds(args)
    metas = shared.scan_kinds(case_dir, kinds, logger)
    if not metas:
        logger.error(f"No othd/oisd data found under {case_dir}")
        sys.exit(1)

    requested = shared.split_vars(getattr(args, "var", None))
    if not requested:
        logger.error("--var says which variable to summarise.\n"
                     "        `data show` lists what this case has.")
        sys.exit(1)

    matched = {k: [r for r in requested if shared.known_name(m, r)]
               for k, m in metas.items()}
    matched = {k: v for k, v in matched.items() if v}
    if not matched:
        available = ", ".join(sorted(
            name for meta in metas.values() for name in meta.variables))
        logger.error(f"None of {', '.join(requested)} is in this case's data.\n"
                     f"        Available: {available}")
        sys.exit(1)
    if len(matched) > 1:
        logger.error("those variables live in different files; "
                     "summarise one kind at a time.")
        sys.exit(1)

    kind = next(iter(matched))
    meta = metas[kind]
    group = shared.resolve_group(meta, getattr(args, "group", None), logger)
    columns = shared.resolve_columns(meta, requested, logger, group)
    node = shared.resolve_node(meta, getattr(args, "node", None), logger, group)
    mask = shared.step_mask(meta, getattr(args, "t1", None),
                            getattr(args, "t2", None), logger)
    freq = getattr(args, "freq", None) or shared.out_freq(case_dir)

    times, tsids, values = shared.gather(meta, columns, node, mask, group)

    value_funcs = [f for f in funcs if f not in LOCATORS]
    console = Console()
    console.print()
    where = f"{meta.group_label} {group} | node {node}"
    console.print(f"[bold cyan]{case_dir.name}[/bold cyan]  [dim]{kind} | {where} | "
                  f"tsId {tsids.min()}..{tsids.max()} ({len(times)} steps)[/dim]")

    rows = []
    if value_funcs:
        table = Table(box=box.SIMPLE, show_header=True, header_style="bold yellow")
        table.add_column("Variable", style="cyan")
        for name in value_funcs:
            table.add_column(name, justify="right", style="green")
        for label, series_values in values.items():
            table.add_row(label, *[f"{FUNCS[name][1](series_values):.5g}"
                                   for name in value_funcs])
            rows.append((label, [FUNCS[name][1](series_values) for name in value_funcs]))
        console.print(table)

    for direction in ("max", "min"):
        name = direction + "loc"
        if name not in funcs:
            continue
        n_plt = int(plt_rows(tsids, freq).sum())
        word = "maximum" if direction == "max" else "minimum"
        loc = Table(box=box.SIMPLE, show_header=True, header_style="bold yellow",
                    title=(f"{name} -- the {word}, and which of the "
                           f"{n_plt} PLT file(s) in range comes closest to it"),
                    title_justify="left", title_style="dim")
        loc.add_column("Variable", style="cyan")
        loc.add_column(direction, justify="right", style="green")
        loc.add_column("at tsId", justify="right", style="white")
        loc.add_column("time", justify="right", style="white")
        loc.add_column("PLT to open", justify="right", style="magenta")
        loc.add_column("value there", justify="right", style="magenta")
        loc.add_column("runners-up", style="dim")
        for label, series_values in values.items():
            found = _locate(series_values, tsids, times, freq, direction)
            loc.add_row(label, f"{found['value']:.6e}", str(found["tsId"]),
                        f"{found['time']:.6g}",
                        str(found["plt_tsId"]) if found["plt_tsId"] else "-",
                        f"{found['plt_value']:.6e}" if found["plt_value"] is not None else "-",
                        _runners_up(found))
        console.print(loc)
    if "zeroloc" in funcs:
        n_plt = int(plt_rows(tsids, freq).sum())
        zl = Table(box=box.SIMPLE, show_header=True, header_style="bold yellow",
                   title=("zeroloc -- the zero crossing best caught by one of "
                          f"the {n_plt} PLT file(s) in range"),
                   title_justify="left", title_style="dim")
        zl.add_column("Variable", style="cyan")
        zl.add_column("direction", style="white")
        zl.add_column("crossing", justify="right", style="green")
        zl.add_column("time", justify="right", style="white")
        zl.add_column("value", justify="right", style="green")
        zl.add_column("PLT to open", justify="right", style="magenta")
        zl.add_column("value there", justify="right", style="magenta")
        zl.add_column("runners-up", style="dim")
        empty, far = [], []
        for label, series_values in values.items():
            for direction in ("descending", "ascending"):
                found = _zeroloc(series_values, tsids, times, freq, direction)
                if not found["count"]:
                    empty.append(f"{label} {direction}")
                    continue
                if (found["plt_offset"] or 0) > 0.25:
                    far.append(
                        f"{label} {direction}: the closest PLT holds "
                        f"{found['plt_value']:.3g}, {100 * found['plt_offset']:.0f}% "
                        f"of the swing from zero -- no file lands near a crossing "
                        f"at this frequency")
                zl.add_row(
                    label, direction, str(found["tsId"]),
                    f"{found['time']:.6g}", f"{found['value']:.6e}",
                    str(found["plt_tsId"]) if found["plt_tsId"] else "-",
                    f"{found['plt_value']:.6e}" if found["plt_value"] is not None else "-",
                    _runners_up(found))
        if zl.row_count:
            console.print(zl)
        for note in far:
            logger.warning(note)
        for what in empty:
            logger.warning(f"{what}: the signal never crosses zero in this window")

    if any(name in funcs for name in LOCATORS) and not freq:
        logger.warning("no outFreq in simflow.config, so the PLT step could "
                       "not be worked out; pass --freq N")

    output = getattr(args, "output", None)
    if output:
        _write_csv(output, values, funcs, tsids, times, freq, logger)
    console.print()


def _write_csv(path, values, funcs, tsids, times, freq, logger):
    """One row per variable, one column per function."""
    import csv
    import os

    directory = os.path.dirname(str(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    value_funcs = [f for f in funcs if f not in LOCATORS]
    header = ["variable"] + value_funcs
    located = [name for name in LOCATORS if name in funcs and name != "zeroloc"]
    for name in located:
        header += [f"{name}_value", f"{name}_tsId", f"{name}_time",
                   f"{name}_plt_tsId", f"{name}_plt_value", f"{name}_plt_ranked"]
    # zeroloc reports a crossing per direction, so it takes a block per side.
    zero_dirs = ("descending", "ascending") if "zeroloc" in funcs else ()
    for direction in zero_dirs:
        tag = f"zeroloc_{direction}"
        header += [f"{tag}_count", f"{tag}_tsId", f"{tag}_time", f"{tag}_value",
                   f"{tag}_plt_tsId", f"{tag}_plt_value"]
    with open(path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        for label, series_values in values.items():
            row = [label] + [f"{FUNCS[f][1](series_values):.10g}" for f in value_funcs]
            for name in located:
                found = _locate(series_values, tsids, times, freq, name[:-3])
                row += [f"{found['value']:.10g}", found["tsId"],
                        f"{found['time']:.10g}", found["plt_tsId"] or "",
                        "" if found["plt_value"] is None else f"{found['plt_value']:.10g}",
                        " ".join(f"{ts}:{v:.6g}" for ts, v in found["plt_ranked"])]
            for direction in zero_dirs:
                z = _zeroloc(series_values, tsids, times, freq, direction)
                row += [z["count"],
                        z["tsId"] if z["tsId"] is not None else "",
                        "" if z["time"] is None else f"{z['time']:.10g}",
                        "" if z["value"] is None else f"{z['value']:.10g}",
                        z["plt_tsId"] if z["plt_tsId"] is not None else "",
                        "" if z["plt_value"] is None else f"{z['plt_value']:.10g}"]
            writer.writerow(row)
    logger.success(f"wrote {len(values)} row(s) -> {path}")
