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
    "maxloc": ("where the largest |value| occurs, as a tsId", None),
}
# maxloc answers a different question from the rest -- a location, not a value --
# so it is computed against the tsIds rather than the samples alone.
LOCATORS = {"maxloc"}


def _maxloc(values, tsids, times, freq):
    """The step of the largest swing, and the PLT step at or before it.

    Largest by magnitude, not by signed value: the biggest excursion of a
    vibration is as likely to be a trough as a crest, and either is the frame
    worth looking at.

    A PLT exists only every `freq` steps, so the nearest one at or *below* the
    peak is the file to open -- rounding up would name a file past the end of
    the run.
    """
    idx = int(np.nanargmax(np.abs(values)))
    tsid = int(tsids[idx])
    plt_step = (tsid // freq) * freq if freq else None
    return {
        "value": float(values[idx]),
        "tsId": tsid,
        "time": float(times[idx]),
        "plt_tsId": plt_step if plt_step else None,
    }


def execute_statistics(args):
    """Execute `data stats`."""
    from .help_messages import print_statistics_help, print_statistics_examples

    if getattr(args, "help", False):
        print_statistics_help()
        return
    if getattr(args, "examples", False):
        print_statistics_examples()
        return
    if not getattr(args, "case", None):
        print_statistics_help()
        return

    logger = Logger(verbose=getattr(args, "verbose", False))
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

    from ..table_impl.command import _known
    matched = {k: [r for r in requested if _known(m, r)] for k, m in metas.items()}
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
    columns = shared.resolve_columns(meta, requested, logger)
    node = shared.resolve_node(meta, getattr(args, "node", None), logger)
    mask = shared.step_mask(meta, getattr(args, "t1", None),
                            getattr(args, "t2", None), logger)
    freq = getattr(args, "freq", None) or shared.out_freq(case_dir)

    times, tsids, values = shared.gather(meta, columns, node, mask)

    value_funcs = [f for f in funcs if f not in LOCATORS]
    console = Console()
    console.print()
    where = f"node {node}" if not meta.integrated else "integrated"
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

    if "maxloc" in funcs:
        loc = Table(box=box.SIMPLE, show_header=True, header_style="bold yellow",
                    title="maxloc -- the largest swing, and the PLT to open for it",
                    title_justify="left", title_style="dim")
        loc.add_column("Variable", style="cyan")
        loc.add_column("|max|", justify="right", style="green")
        loc.add_column("at tsId", justify="right", style="white")
        loc.add_column("time", justify="right", style="white")
        loc.add_column(f"PLT tsId" + (f" (every {freq})" if freq else ""),
                       justify="right", style="magenta")
        for label, series_values in values.items():
            found = _maxloc(series_values, tsids, times, freq)
            loc.add_row(label, f"{found['value']:.6e}", str(found["tsId"]),
                        f"{found['time']:.6g}",
                        str(found["plt_tsId"]) if found["plt_tsId"] else "-")
        console.print(loc)
        if not freq:
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
    if "maxloc" in funcs:
        header += ["maxloc_value", "maxloc_tsId", "maxloc_time", "maxloc_plt_tsId"]
    with open(path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        for label, series_values in values.items():
            row = [label] + [f"{FUNCS[f][1](series_values):.10g}" for f in value_funcs]
            if "maxloc" in funcs:
                found = _maxloc(series_values, tsids, times, freq)
                row += [f"{found['value']:.10g}", found["tsId"],
                        f"{found['time']:.10g}", found["plt_tsId"] or ""]
            writer.writerow(row)
    logger.success(f"wrote {len(values)} row(s) -> {path}")
