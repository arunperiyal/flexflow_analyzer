"""
`data table` -- the time history of chosen variables, as a table.

Time runs down the rows and variables across the columns, always: a row is one
instant of the run, which is the only layout that stays readable as columns are
added and the only one a plotting tool will take without transposing.
"""

import sys

from rich.console import Console
from rich import box
from rich.table import Table

from ....utils.logger import Logger
from .. import shared


def execute_table(args):
    """Execute `data table`."""
    from .help_messages import print_table_help, print_table_examples

    if getattr(args, "help", False):
        print_table_help()
        return
    if getattr(args, "examples", False):
        print_table_examples()
        return
    if not getattr(args, "case", None):
        print_table_help()
        return

    logger = Logger(verbose=getattr(args, "verbose", False))
    case_dir = shared.resolve_case(args.case, logger)
    kinds = shared.which_kinds(args)
    metas = shared.scan_kinds(case_dir, kinds, logger)
    if not metas:
        logger.error(f"No othd/oisd data found under {case_dir}")
        sys.exit(1)

    requested = shared.split_vars(getattr(args, "var", None))
    if not requested:
        logger.error("--var says which variable to tabulate; there is no useful "
                     "default among a dozen of them.\n"
                     "        `data show` lists what this case has.")
        sys.exit(1)

    # A name belongs to whichever kind declares it, so the kind need not be
    # given: `--var vel` is othd, `--var totTrac` is oisd, and asking for both
    # at once is refused rather than silently answered from one of them.
    owners = {kind: [r for r in requested
                     if shared.known_name(metas[kind], r)] for kind in metas}
    matched = {k: v for k, v in owners.items() if v}
    if not matched:
        available = ", ".join(sorted(
            name for meta in metas.values() for name in meta.variables))
        logger.error(f"None of {', '.join(requested)} is in this case's data.\n"
                     f"        Available: {available}")
        sys.exit(1)
    if len(matched) > 1:
        logger.error("those variables live in different files "
                     + "; ".join(f"{k}: {', '.join(v)}" for k, v in matched.items())
                     + ".\n        They are sampled differently, so tabulate one "
                       "kind at a time.")
        sys.exit(1)

    kind = next(iter(matched))
    meta = metas[kind]
    missing = [r for r in requested if r not in matched[kind]]
    if missing:
        logger.error(f"not in the {kind} files: {', '.join(missing)}")
        sys.exit(1)

    group = shared.resolve_group(meta, getattr(args, "group", None), logger)
    columns = shared.resolve_columns(meta, requested, logger, group)
    node = shared.resolve_node(meta, getattr(args, "node", None), logger, group)
    mask = shared.step_mask(meta, getattr(args, "t1", None),
                            getattr(args, "t2", None), logger)

    logger.info(f"reading {len(columns)} column(s) from {len(meta.files)} "
                f"{kind} file(s)")
    times, tsids, values = shared.gather(meta, columns, node, mask, group)

    output = getattr(args, "output", None)
    if output:
        shared.write_csv(output, times, tsids, values, logger)
        return

    rows = shared.slice_rows(len(times), getattr(args, "head", None),
                             getattr(args, "tail", None), False)
    console = Console()
    console.print()
    header = f"{kind} | {meta.group_label} {group} | node {node}"
    if meta.nodes_of(group) == 1:
        header += " [dim](the only one)[/dim]"
    console.print(f"[bold cyan]{case_dir.name}[/bold cyan]  [dim]{header}[/dim]")
    console.print(f"[dim]tsId {tsids.min()}..{tsids.max()}, "
                  f"time {times.min():.6g}..{times.max():.6g}, "
                  f"{len(times)} step(s)[/dim]")

    table = Table(box=box.SIMPLE, show_header=True, header_style="bold yellow")
    table.add_column("tsId", justify="right", style="cyan")
    table.add_column("time", justify="right", style="white")
    for label in values:
        table.add_column(label, justify="right", style="green")

    for i in range(*rows.indices(len(times))):
        table.add_row(str(tsids[i]), f"{times[i]:.6g}",
                      *[f"{values[l][i]:.6e}" for l in values])
    console.print(table)

    shown = len(range(*rows.indices(len(times))))
    if shown < len(times):
        which = "first" if not getattr(args, "tail", None) else "last"
        console.print(f"[dim]{which} {shown} of {len(times)} rows -- "
                      f"--head N / --tail N to change, --output FILE.csv for all"
                      f"[/dim]")
    console.print()


def _known(meta, name, group=None):
    """Kept as a name the stats command imports; the logic lives in shared."""
    return shared.known_name(meta, name, group)
