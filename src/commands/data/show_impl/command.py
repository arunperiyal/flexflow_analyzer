"""
`data show` -- what a case's time-history data holds.

Not a preview of the numbers: `data table` prints those. This answers the
questions you ask before tabulating anything -- how many files, how many nodes,
over what span, and which variables can be named to --var. The old version
printed ten rows of displacement, which answered none of them and buried the
one fact it did carry.
"""

import sys

from rich.console import Console
from rich import box
from rich.table import Table

from ....utils.logger import Logger
from .. import shared


def _describe(console, kind, meta, freq):
    """One block per file kind: counts, span, and the variable list."""
    console.print(f"[bold cyan]{kind.upper()}[/bold cyan]")

    info = Table(box=box.SIMPLE, show_header=False, pad_edge=False)
    info.add_column(style="white")
    info.add_column(style="yellow")
    info.add_row("Files", str(len(meta.files)))
    if len(meta.groups) > 1:
        info.add_row(f"{meta.group_label}s",
                     ", ".join(str(g) for g in meta.groups)
                     + "  [dim](--group N picks one)[/dim]")
    for group in meta.groups:
        # Parentheses, not brackets: rich reads [othId 0] as a markup tag and
        # swallows it, which is how this label went out empty the first time.
        label = ("Nodes" if len(meta.groups) == 1
                 else f"Nodes ({meta.group_label} {group})")
        if meta.integrated_of(group):
            info.add_row(label, "1  [dim](integrated output)[/dim]")
        else:
            info.add_row(label, str(meta.nodes_of(group)))
    info.add_row("Timesteps", str(len(meta.times)))
    info.add_row("Time", f"{meta.times.min():.6g} .. {meta.times.max():.6g}")
    info.add_row("tsId", f"{meta.tsids.min()} .. {meta.tsids.max()}")
    if freq:
        # The steps that also have a PLT beside them, which is what a --t1/--t2
        # window is usually being chosen against.
        with_plt = [t for t in meta.tsids.tolist() if t % freq == 0]
        if with_plt:
            info.add_row(f"tsId every {freq}",
                         f"{min(with_plt)} .. {max(with_plt)}  "
                         f"[dim]({len(with_plt)} with a PLT)[/dim]")
    console.print(info)

    for group in meta.groups:
        found = meta.variables_of(group)
        if not found:
            console.print("  [yellow]no variables found[/yellow]\n")
            continue
        variables = Table(box=box.SIMPLE, show_header=True,
                          header_style="bold yellow")
        if len(meta.groups) > 1:
            variables.title = f"{meta.group_label} {group}"
            variables.title_justify = "left"
            variables.title_style = "dim"
        variables.add_column("Variable", style="cyan")
        variables.add_column("Components", justify="right", style="white")
        variables.add_column("Name for --var", style="green")
        variables.add_column("Short", style="magenta")
        for name in sorted(found):
            var = found[name]
            variables.add_row(
                name, str(var.ncomp),
                name if var.ncomp == 1 else ", ".join(var.columns),
                shared.alias_of(name, var) or "")
        console.print(variables)
        console.print()


def execute_preview(args):
    """Execute `data show`."""
    from .help_messages import print_preview_help, print_preview_examples

    if getattr(args, "help", False):
        print_preview_help()
        return
    if getattr(args, "examples", False):
        print_preview_examples()
        return
    if not getattr(args, "case", None):
        print_preview_help()
        return

    logger = Logger(verbose=getattr(args, "verbose", False))
    case_dir = shared.resolve_case(args.case, logger)
    kinds = shared.which_kinds(args)
    metas = shared.scan_kinds(case_dir, kinds, logger)

    console = Console()
    console.print()
    console.print(f"[bold]Case:[/bold] {case_dir}")

    if not metas:
        asked = " or ".join(f"{k}_files/" for k in kinds)
        logger.error(f"No {asked} data found under {case_dir}")
        sys.exit(1)

    freq = shared.out_freq(case_dir)
    console.print()
    for kind in kinds:
        if kind in metas:
            _describe(console, kind, metas[kind], freq)
        elif len(kinds) > 1:
            console.print(f"[bold cyan]{kind.upper()}[/bold cyan]  "
                          f"[dim]no {kind}_files/ in this case[/dim]\n")

    # The two are written by the same run, so a disagreement in their step count
    # means one of them stopped early -- worth saying rather than leaving to be
    # noticed later when two tables do not line up.
    if len(metas) == 2:
        othd, oisd = metas["othd"], metas["oisd"]
        if len(othd.times) != len(oisd.times):
            logger.warning(f"othd has {len(othd.times)} timesteps but oisd has "
                           f"{len(oisd.times)}; one of them stopped early")

    console.print("[dim]Tabulate with `data table --var NAME`, "
                  "summarise with `data stats --var NAME --func max`.[/dim]")
    console.print()
