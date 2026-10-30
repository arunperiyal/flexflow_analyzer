"""
`data check steady` -- whether the history has settled, per variable, and
from which tsId it has (the transient to discard). The algorithm is in
steady.py.
"""

import sys

from rich import box
from rich.console import Console
from rich.table import Table

from ....utils.logger import Logger
from .. import shared
from . import steady


def execute_check(args):
    from .help_messages import print_check_help, print_steady_help, print_steady_examples

    sub = getattr(args, "data_check_subcommand", None)
    if sub != "steady":
        print_check_help()
        return
    if getattr(args, "help", False):
        print_steady_help()
        return
    if getattr(args, "examples", False):
        print_steady_examples()
        return
    logger = Logger(verbose=getattr(args, "verbose", False))
    if not getattr(args, "case", None):
        shared.no_case(args, logger, print_steady_help,
                       ('var', 't1', 't2', 'last', 'node', 'othid', 'osgid', 'group'))
        return

    limits = dict(blocks=args.blocks, tol=args.tol, mean_tol=args.mean_tol,
                  min_cycles=args.min_cycles)
    problem = _check_limits(limits)
    if problem:
        logger.error(problem)
        sys.exit(1)

    requested = shared.split_vars(getattr(args, "var", None))
    if not requested:
        logger.error("--var says which variable to check.\n"
                     "        `data show` lists what this case has.")
        sys.exit(1)

    def run_one(case_dir, case_args):
        _run_steady(case_dir, case_args, logger, requested, limits)

    shared.for_each_case(args, logger, run_one)


def _check_limits(limits):
    if limits['blocks'] < 2:
        return "--blocks must be 2 or more (one block has nothing to compare with)"
    if limits['min_cycles'] < limits['blocks']:
        return "--min-cycles must be at least --blocks (a cycle per block)"
    for name in ('tol', 'mean_tol'):
        if limits[name] <= 0:
            return f"--{name.replace('_', '-')} must be positive"
    return None


def _run_steady(case_dir, args, logger, requested, limits):
    kinds = shared.which_kinds(args)
    metas = shared.scan_kinds(case_dir, kinds, logger)
    if not metas:
        logger.error(f"No othd/oisd data found under {case_dir}")
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
                     "check one kind at a time.")
        sys.exit(1)

    kind = next(iter(matched))
    meta = metas[kind]
    group = shared.resolve_group(meta, args, logger)
    columns = shared.resolve_columns(meta, requested, logger, group)
    node = shared.resolve_node(meta, getattr(args, "node", None), logger, group)
    mask = shared.step_mask(meta, getattr(args, "t1", None),
                            getattr(args, "t2", None), logger, getattr(args, "last", None))
    times, tsids, values = shared.gather(meta, columns, node, mask, group)
    order = tsids.argsort(kind="stable")
    times, tsids = times[order], tsids[order]

    console = Console()
    console.print()
    console.print(f"[bold cyan]{case_dir.name}[/bold cyan]  [dim]{kind} | "
                  f"{meta.group_label} {group} | node {node} | "
                  f"tsId {tsids.min()}..{tsids.max()} ({len(times)} steps)[/dim]")

    # Narrow headers and padding, so the row fits 80 columns: the reasons a
    # variable fails go on lines of their own below.
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold yellow",
                  padding=(0, 1), pad_edge=False)
    table.add_column("Variable", style="cyan", no_wrap=True)
    for name in ("cycles", "period", "mean Δ", "amp Δ", "period Δ"):
        table.add_column(name, justify="right", no_wrap=True)
    table.add_column("verdict", no_wrap=True)
    table.add_column("from", justify="right", no_wrap=True)

    details = []
    for label, series_values in values.items():
        x = series_values[order]
        verdict = steady.analyse(times, x, **limits)
        start = steady.steady_from(times, x, verdict, **limits)
        table.add_row(label, *_cells(verdict, limits),
                      "-" if start is None else str(tsids[start]))
        details.append((label, verdict))
    console.print(table)
    for label, verdict in details:
        if verdict.failures and not verdict.steady:
            console.print(f"  [cyan]{label}[/cyan]: {', '.join(verdict.failures)}")
    console.print(f"[dim]steady: {limits['min_cycles']}+ cycles in {limits['blocks']} blocks; "
                  f"mean Δ (block means' spread) <= {limits['mean_tol']:g} std, amp Δ "
                  f"and period Δ (spread over their mean) <= {limits['tol']:g}. from: "
                  f"the tsId from which the rest of the window is steady.[/dim]")

    if getattr(args, "verbose", False):
        for label, verdict in details:
            _print_blocks(console, label, verdict, tsids)
    console.print()


def _fmt(value, limit, text):
    if value != value:                    # nan: not measured
        return "-"
    return f"[red]{text} ✗[/red]" if value > limit else text


def _cells(v, limits):
    if v.kind == 'flat':
        shift = _fmt(v.mean_shift, limits['tol'], f"{v.mean_shift:.2f} of mean")
        amp = per = "-"
        period = "-"
    else:
        shift = _fmt(v.mean_shift, limits['mean_tol'], f"{v.mean_shift:.2f}σ")
        amp = _fmt(v.amp_spread, limits['tol'], f"{v.amp_spread:.2f}")
        per = _fmt(v.period_spread, limits['tol'], f"{v.period_spread:.2f}")
        period = "-" if v.period != v.period else f"{v.period:.4g}"
    colour = {steady.STEADY: "green", steady.NOT_STEADY: "red",
              steady.TOO_SHORT: "yellow"}[v.verdict]
    word = v.verdict + (" (flat)" if v.kind == 'flat' and v.steady else "")
    cycles = "-" if v.kind == 'flat' else str(v.cycles)
    return cycles, period, shift, amp, per, f"[{colour}]{word}[/{colour}]"


def _print_blocks(console, label, v, tsids):
    if not v.blocks:
        return
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold yellow",
                  title=f"{label}: blocks", title_justify="left", title_style="dim")
    for name in ("block", "tsId", "mean", "amplitude", "period"):
        table.add_column(name, justify="right")
    for i, b in enumerate(v.blocks, 1):
        table.add_row(str(i), f"{tsids[b.start]}..{tsids[b.end - 1]}", f"{b.mean:.6g}",
                      "-" if b.amplitude != b.amplitude else f"{b.amplitude:.6g}",
                      "-" if b.period != b.period else f"{b.period:.6g}")
    console.print(table)
