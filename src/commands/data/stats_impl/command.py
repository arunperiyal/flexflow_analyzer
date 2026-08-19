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
}
# maxloc answers a different question from the rest -- a location, not a value --
# so it is computed against the tsIds rather than the samples alone.
LOCATORS = ("maxloc", "minloc")


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
    located = [name for name in LOCATORS if name in funcs]
    for name in located:
        header += [f"{name}_value", f"{name}_tsId", f"{name}_time",
                   f"{name}_plt_tsId", f"{name}_plt_value", f"{name}_plt_ranked"]
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
            writer.writerow(row)
    logger.success(f"wrote {len(values)} row(s) -> {path}")
