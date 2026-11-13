"""`case check plt <case> --verify`: the binary PLTs in binary/ against their
copies on the remote, by size and md5 read now on both sides
(src/core/transfer/verify.py). Exit code 0 only when every one is verified."""

from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.markup import escape
from rich.table import Table

from ...case_iteration import is_wildcard_case, load_cases_from_directory


def _window(t1, t2) -> Optional[tuple]:
    return None if t1 is None and t2 is None else (t1, t2)


def _steps(names) -> str:
    """'8950, 9000 ... 9900 (20)' for a list of <problem>.<step>.plt names."""
    steps = [n.rsplit('.', 2)[-2] for n in names]
    if len(steps) <= 6:
        return ', '.join(steps)
    return f"{', '.join(steps[:3])} ... {steps[-1]} ({len(steps)})"


def execute_verify(args) -> int:
    from src.cli.context import current_case, current_dir
    from src.core.simflow_config import SimflowConfig
    from src.core.transfer.cloud import CloudError, open_for_folder
    from src.core.transfer.ledger import Ledger
    from src.core.transfer.verify import verify_plts

    console = Console()
    name = getattr(args, 'case', None) or current_case()
    if not name:
        console.print("[red]Error:[/red] No case directory specified.")
        console.print("Usage:  case check plt <dir> --verify --remote NAME")
        return 1
    if is_wildcard_case(name):
        cases = [Path(c['path']) for c in load_cases_from_directory(current_dir())]
        if not cases:
            console.print("[red]Error:[/red] No cases found in .cases.yml")
            return 1
    else:
        cases = [Path(name)]
    remote = getattr(args, 'remote', None)
    window = _window(getattr(args, 't1', None), getattr(args, 't2', None))
    freq = getattr(args, 'freq', None)
    verbose = bool(getattr(args, 'verbose', False))

    clouds, ledgers, code = {}, {}, 0
    try:
        for case_dir in cases:
            if not case_dir.is_dir():
                console.print(f"[red]Error:[/red] Case directory not found: {case_dir}")
                code = 1
                continue
            case_dir = case_dir.resolve()
            folder = case_dir.parent
            cfg = SimflowConfig(str(case_dir / 'simflow.config'))
            problem = cfg.problem
            if not problem:
                console.print(f"[red]Error:[/red] {case_dir.name}: 'problem' not set in "
                              f"simflow.config, so the PLT names are not known")
                code = 1
                continue
            try:
                if folder not in clouds:
                    clouds[folder] = open_for_folder(folder, remote)
                    ledgers[folder] = Ledger(folder)
                cloud = clouds[folder]
                console.print(f"[bold]PLT verify[/bold]  [dim]{escape(case_dir.name)}: binary/"
                              f"{escape(problem)}.<step>.plt against {escape(cloud.where)}[/dim]")
                say = (lambda line: console.print(f"  [dim]{escape(line)}[/dim]")) if verbose else None
                result = verify_plts(case_dir, problem, cloud, remote, ledgers[folder],
                                     window=window, freq=freq, say=say,
                                     run_dir=cfg.run_dir(case_dir))
            except CloudError as e:
                console.print(f"[red]Error:[/red] {escape(str(e))}")
                return 1
            _print(console, result)
            if not result.ok:
                code = 1
    finally:
        for cloud in clouds.values():
            cloud.close()
    return code


def _print(console, result) -> None:
    rows = Table.grid(padding=(0, 2))
    rows.add_column(no_wrap=True)
    rows.add_column()
    if result.verified:
        rows.add_row("[green]verified[/green]", _steps(result.verified))
    if result.size_only:
        rows.add_row("[yellow]size only[/yellow]",
                     f"{_steps(result.size_only)}  [dim]the remote gave no md5; "
                     f"not counted as verified[/dim]")
    for name, why in result.differs.items():
        rows.add_row("[red]differs[/red]", f"{escape(name)}: {escape(why)}")
    if result.not_there:
        rows.add_row("[red]not on the remote[/red]", _steps(result.not_there))
    for name, why in result.broken.items():
        how = result.rebuild.get(name, '')
        hint = f"\n[dim]make it again:[/dim] {escape(how)}" if how else ''
        rows.add_row("[red]broken here[/red]", f"{escape(name)}: {escape(why)}{hint}")
    if result.kept_there:
        rows.add_row("[green]only on the remote[/green]",
                     f"{_steps(result.kept_there)}  [dim]as recorded when verified[/dim]")
    if result.only_there:
        rows.add_row("[yellow]only on the remote[/yellow]",
                     f"{_steps(result.only_there)}  [dim]no record of a verified copy "
                     f"to compare with[/dim]")
    for name, why in result.changed_there.items():
        rows.add_row("[red]changed on the remote[/red]", f"{escape(name)}: {escape(why)}")
    if result.nowhere:
        rows.add_row("[red]in neither place[/red]",
                     _steps([f"x.{s}.plt" for s in result.nowhere]))
    console.print(rows)
    mark = "[green]✓[/green]" if result.ok else "[red]✗[/red]"
    console.print(f"  {mark} {escape(result.summary())}")
    console.print()
